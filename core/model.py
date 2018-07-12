import asyncio
import copy
import re
from typing import Dict, Tuple, AnyStr, Any, List

from bson import DBRef, ObjectId

from .abstract.model import BaseModel
from .abstract.field import BaseField
from .constants import CREATE, UPDATE
from .dispatchers import MongoDispatcher
from .exceptions import ValidationError
from core.abstract.field import BaseRelationField, BaseBackwardRelationField
from .managers import OnDeleteManager
from .queryset import QuerySet
from .utils import classproperty


class MongoModel(metaclass=BaseModel):
    class Meta:
        abstract = True

    _id = None
    _management = None

    def __init__(self, **document):
        # Fields that were set in the model instance, but not declared.
        self._undeclared_fields = {}
        self._modified_fields = []

        # Save fields not declared in the model.
        for field_name, field_value in document.items():
            declared_fields = self.get_declared_fields()

            if field_name not in declared_fields and field_name != '_id':
                self._undeclared_fields[field_name] = field_value

        if '_id' in document:
            document = self.get_external_values(document)

        self.__dict__.update(document)

    def __repr__(self):
        return f'{self.__class__.__name__} _id: {self.__dict__.get("_id")}'

    def __setattr__(self, key, value):
        # Ignore private properties
        if not key.startswith('_'):
            declared_fields = self.get_declared_fields()

            if key not in declared_fields:
                self._undeclared_fields[key] = value
            self._modified_fields.append(key)
        super().__setattr__(key, value)

    def __getattr__(self, item):
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
            field_value = self.__dict__.get(field_name)
            display = field_instance.get_choice_value(field_value)

            return display

        return _func

    def __getattribute__(self, item):
        def __getattribute(obj, attribute):
            return object.__getattribute__(obj, attribute)

        attr = super().__getattribute__(item)
        declared_fields = __getattribute(self, '_management').declared_fields
        field_instance = declared_fields.get(item)
        field_value = None

        if isinstance(field_instance, (BaseRelationField, BaseBackwardRelationField)):
            # Prevent 'can not reuse awaitable coroutine' exception
            field_instance = copy.deepcopy(field_instance)

            # Set the value with relation object id for a field to provide base relation
            if isinstance(field_instance, BaseRelationField):
                field_value = __getattribute(self, '__dict__').get(item)

            # Set the _id of the current object as a value
            # provide backward relationship for relation fields
            elif isinstance(field_instance, BaseBackwardRelationField):
                field_value = __getattribute(self, '_id')

            if field_value is not None:
                if isinstance(field_value, DBRef):
                    field_value = field_value.id

                if field_value:
                    field_instance.set_field_value(field_value)
                    attr = field_instance
                else:
                    attr = None

        return attr

    @classproperty
    def objects(cls) -> QuerySet:
        return QuerySet(model=cls)

    @property
    def id(self) -> ObjectId:
        return self._id

    @classproperty
    def has_backwards(cls) -> bool:
        return cls._get_management_param('has_backwards')

    @classmethod
    def get_declared_fields(cls) -> Dict:
        return cls._get_management_param('declared_fields')

    @classmethod
    def get_dispatcher(cls) -> MongoDispatcher:
        return cls._get_management_param('dispatcher')

    @classmethod
    def get_sorting(cls) -> Tuple:
        return cls._get_management_param('sorting')

    @classmethod
    def get_collection_name(cls) -> AnyStr:
        return cls.get_dispatcher().collection_name

    @classmethod
    def _get_management_param(cls, param: AnyStr) -> Any:
        return getattr(cls._management, param, None)

    async def save(self):
        document = await self._update() if self._id else await self._create()
        self.__dict__.update(document)

    async def delete(self):
        if self.has_backwards:
            await OnDeleteManager().handle_backwards([self])

        await self.objects.internal_query.delete_one(_id=self.id)

        # Remove document id from the ODM object
        self._id = None

    def get_external_values(self, document: Dict) -> Dict:
        """
        Convert internal values to external for representation to user.
        :param document: dict
        :return: dict
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
    async def get_internal_values(cls, action: CREATE | UPDATE, field_values: Dict, modified: List, undeclared: Dict):
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

            internal_value = None

            if isinstance(field_instance, BaseRelationField):
                # Set the DBRef for the field value (create) or leave the same (update)
                collection_name = field_instance.relation.get_collection_name()
                document_id = getattr(field_value, '_id', field_value)
                internal_value = DBRef(collection_name, document_id)

            elif isinstance(field_instance, BaseField):
                # Bring to the internal value
                internal_value = field_instance.to_internal_value(field_value)

            internal_values[field_name] = internal_value

        # Undeclared fields are not validated
        undeclared = undeclared
        internal_values.update(undeclared)

        return internal_values

    async def _create(self):
        """
        Create document with all defined fields.
        :return: dict
        """
        internal_values = await self.get_internal_values(
            action=CREATE,
            field_values=self.__dict__,
            modified=self._modified_fields,
            undeclared=self._undeclared_fields
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
            field_values=self.__dict__,
            modified=self._modified_fields,
            undeclared=self._undeclared_fields
        )
        document = await self.objects.internal_query.update_one(self._id, **internal_values)
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
            field_type = cls.get_declared_fields().get(field_name).field_type

            # The validator must return a value in the type of the specified model field.
            if not isinstance(new_value, field_type):
                raise ValidationError(
                    f'\'{validator.__name__}\' function returns the object '
                    f'of the type \'{type(new_value).__name__}\', '
                    f'but \'{field_type.__name__}\' expected.'
                )

        return new_value
