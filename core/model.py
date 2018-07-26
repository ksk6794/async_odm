import asyncio
import inspect
import re
from collections import deque
from typing import Dict, Tuple, AnyStr, Any

from bson import ObjectId

from .base.model import BaseModel
from .base.field import BaseField, BaseBackwardRelationField
from .constants import CREATE, UPDATE
from .dispatchers import MongoDispatcher
from .exceptions import ValidationError
from .managers import OnDeleteManager
from .queryset import QuerySet
from .utils import classproperty


class MongoModel(metaclass=BaseModel):
    class Meta:
        abstract = True

    _dispatcher = None

    def __init__(self, **document):
        self.__document = {}
        self.__modified_fields = []

        if '_id' in document:
            document = self.get_external_values(document)

        deque(map(lambda i: setattr(self, *i), document.items()))

    def __setattr__(self, key, value):
        if not key.startswith(f'_{MongoModel.__name__}__'):
            declared_fields = self.get_declared_fields()

            if key not in declared_fields:
                self.__document[key] = value
            else:
                super().__setattr__(key, value)
        else:
            super().__setattr__(key, value)

    def __repr__(self):
        return f'{self.__class__.__name__} _id: {self.__document.get("_id")}'

    def __getattr__(self, item):
        if item in self.__document:
            return self.__document.get(item)

        match = re.match('get_(?P<field_name>\w+)_display', item)

        if not match:
            raise AttributeError(
                f'\'{self.__class__.__name__}\' model has no attribute \'{item}\''
            )

        field_name = match.group('field_name')
        declared_fields = self.get_declared_fields()

        if field_name not in declared_fields:
            raise AttributeError(
                f'Field \'{field_name}\' is not declared'
            )

        field_instance = declared_fields.get(field_name)
        choices = field_instance.choices.value if hasattr(field_instance, 'choices') else None

        if not choices:
            raise AttributeError(
                f'Field \'{field_name}\' has not attribute \'choices\''
            )

        # Closure is used to make get_FOO_display callable
        def _func():
            field_value = self.__document.get(field_name)
            display = field_instance.get_choice_value(field_value)

            return display

        return _func

    def get_document(self):
        return self.__document

    def set_field(self, field_name, field_value):
        self.__document[field_name] = field_value
        self.__modified_fields.append(field_name)

    def get_field(self, name):
        return self.__document.get(name)

    @classproperty
    def objects(cls) -> QuerySet:
        return QuerySet(model=cls)

    @property
    def id(self) -> ObjectId:
        return self.__document.get('_id')

    @classproperty
    def has_backwards(cls) -> bool:
        field_instances = cls.get_declared_fields().values()
        return any([isinstance(f, BaseBackwardRelationField) for f in field_instances])

    @classmethod
    def get_declared_fields(cls) -> Dict:
        declared_fields = {}

        for c in inspect.getmro(cls):
            for k, v in c.__dict__.items():
                if isinstance(v, BaseField):
                    declared_fields[k] = v

        return declared_fields

    @classmethod
    def get_dispatcher(cls) -> MongoDispatcher:
        return cls._dispatcher

    @classmethod
    def get_sorting(cls) -> Tuple:
        return getattr(cls.Meta, 'sorting', None)

    @classmethod
    def get_collection_name(cls) -> AnyStr:
        return cls.get_dispatcher().collection_name

    async def save(self):
        document = await self._update() if self.id else await self._create()
        self.__document.update(document)
        self.__modified_fields = []

    async def delete(self):
        if self.has_backwards:
            await OnDeleteManager().handle_backwards([self])

        await self.objects.internal_query.delete_one(_id=self.id)

        # Remove document id from the ODM object
        self.__document['_id'] = None

    def get_external_values(self, document: Dict) -> Dict:
        """
        Convert internal values to external for representation to user.
        """
        for field_name, field_value in document.copy().items():
            field_instance = self.get_declared_fields().get(field_name)

            # Bring each field to an external value
            if isinstance(field_instance, BaseField):
                field_value = field_instance.to_external_value(field_value)

                # Update document with an external value
                document.update({field_name: field_value})

        return document

    async def get_internal_values(self, action: int):
        """
        Convert external values to internal for saving to a database.
        """
        document = self.get_document()
        return await self.to_internal(document, action)

    @classmethod
    async def to_internal(cls, field_values, action):
        internal_values = {}
        declared_fields = cls.get_declared_fields()
        declared = set(declared_fields)
        to_update = set(field_values)
        modified = declared & to_update

        for field_name, field_instance in declared_fields.items():
            # Bring to internal values only modified fields (only for UPDATE)
            if action is UPDATE and field_name not in modified:
                continue

            field_value = field_values.get(field_name)

            # Validate fields
            field_value = await cls._validate(field_name, field_value)

            # Prepare the fields values
            field_value = await field_instance.prepare(field_value, action)

            internal_values[field_name] = field_instance.to_internal_value(field_value)

        undeclared = to_update - declared
        undeclared_field_values = {k: v for k, v in field_values.items() if k in undeclared}
        internal_values.update(undeclared_field_values)

        return internal_values

    async def _create(self):
        """
        Create document with all defined fields.
        :return: dict
        """
        internal_values = await self.get_internal_values(CREATE)
        insert_result = await self.objects.internal_query.create_one(**internal_values)

        # Generate document from field_values and inserted_id
        internal_values.update({'_id': insert_result.inserted_id})
        return self.get_external_values(internal_values)

    async def _update(self):
        """
        Update only modified document fields.
        :return: dict
        """
        internal_values = await self.get_internal_values(UPDATE)
        document_id = internal_values.pop('_id')
        document = await self.objects.internal_query.update_one(document_id, **internal_values)
        external_values = self.get_external_values(document)

        return external_values

    @classmethod
    async def _validate(cls, field_name: AnyStr, field_value: Any) -> Any:
        field_instance = cls.get_declared_fields().get(field_name)

        # Validate field value by default validators
        v = field_instance.validate
        is_coro = asyncio.iscoroutinefunction(v)
        await v(field_value) if is_coro else v(field_value)

        # Call Model child (custom) validate methods
        new_value = await cls._child_validator(field_name, field_value)

        # Set the post-validate value
        if new_value is not None:
            field_value = new_value

        return field_value

    @classmethod
    async def _child_validator(cls, field_name: AnyStr, field_value: Any) -> Any:
        """
        Call user-defined validation methods.
        """
        new_value = None
        validator = getattr(cls, f'validate_{field_name}', None)

        if callable(validator):
            is_coro = asyncio.iscoroutinefunction(validator)
            new_value = await validator(value=field_value) if is_coro else validator(value=field_value)
            field_type = cls.get_declared_fields().get(field_name).Meta.field_type

            # The validator must return a value in the type of the specified model field.
            if not isinstance(new_value, field_type):
                raise ValidationError(
                    f'\'{validator.__name__}\' function returns the object '
                    f'of the type \'{type(new_value).__name__}\', '
                    f'but \'{field_type.__name__}\' expected.'
                )

        return new_value
