import asyncio
import inspect
import re
from collections import deque
from typing import Dict, Tuple, AnyStr, Any, List

from bson import DBRef, ObjectId

from .base.model import BaseModel
from .base.field import BaseField, BaseRelationField, BaseBackwardRelationField
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
        choices = getattr(field_instance, 'choices', None)

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

    def get_undeclared_fields(self):
        """
        Fields that were set in the model instance, but not declared.
        """
        declared_fields_names = set(self.get_declared_fields().keys())
        document_fields = set(self.__document.keys())
        undeclared_names = list(document_fields - declared_fields_names)
        undeclared_fields = {k: v for k, v in self.__document.items() if k in undeclared_names and k != '_id'}
        return undeclared_fields

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

    @classmethod
    async def get_internal_values(cls, action: int, field_values: Dict, modified: List, undeclared: Dict):
        """
        Convert external values to internal for saving to a database.
        """
        internal_values = {}

        for field_name, field_instance in cls.get_declared_fields().items():
            # Bring to internal values only modified fields (for update action)
            if action is UPDATE and field_name not in modified:
                continue

            value = await field_instance.process_value(field_values.get(field_name), action)
            field_value = await cls._validate(field_instance, field_name, value)
            internal_values[field_name] = field_instance.to_internal_value(field_value)

        # Undeclared fields are not validated
        internal_values.update(undeclared)

        return internal_values

    async def _create(self):
        """
        Create document with all defined fields.
        :return: dict
        """
        internal_values = await self.get_internal_values(
            action=CREATE,
            field_values=self.__document,
            modified=self.__modified_fields,
            undeclared=self.get_undeclared_fields()
        )
        insert_result = await self.objects.internal_query.create_one(**internal_values)

        # Generate document from field_values and inserted_id
        internal_values.update({'_id': insert_result.inserted_id})
        return self.get_external_values(internal_values)

    async def _update(self):
        """
        Update only modified document fields.
        :return: dict
        """
        internal_values = await self.get_internal_values(
            action=UPDATE,
            field_values=self.__document,
            modified=self.__modified_fields,
            undeclared=self.get_undeclared_fields()
        )
        document = await self.objects.internal_query.update_one(self.id, **internal_values)
        return self.get_external_values(document)

    @classmethod
    async def _validate(cls, field_instance: BaseField, field_name: AnyStr, field_value: Any) -> Any:
        # Validate field value by default validators
        v = field_instance.validate
        is_coro = asyncio.iscoroutinefunction(v)
        await v(field_name, field_value) if is_coro else v(field_name, field_value)

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
