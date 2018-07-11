import os
import re
import copy
import asyncio
import importlib
from types import ModuleType
from typing import Any, AnyStr, List, Dict, Tuple

from bson import DBRef, ObjectId

from .exceptions import SettingsError, ValidationError
from .managers import RelationManager, OnDeleteManager, DatabaseManager, IndexManager
from .queryset import QuerySet
from .utils import classproperty
from .dispatchers import MongoDispatcher
from .constants import UPDATE, CREATE
from .fields import Field, BaseRelationField, BaseBackwardRelationField


class ModelManagement:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class BaseModel(type):
    """
    Metaclass for all models.
    """
    _db_manager = None

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __new__(mcs, name, bases, attrs):
        # If it is not MongoModel
        if bases:
            attrs['_management'] = ModelManagement(
                declared_fields=mcs._get_declared_fields(bases, attrs),
                dispatcher=mcs._get_dispatcher(name, attrs),
                sorting=mcs._get_sorting(attrs),
                has_backwards=False
            )

        model = super().__new__(mcs, name, bases, attrs)

        if not mcs._is_abstract(attrs):
            RelationManager().add_model(model)

            if getattr(mcs.settings, 'AUTO_INSPECT', True) is True:
                loop = asyncio.get_event_loop()
                task = IndexManager().process(model)
                loop.run_until_complete(task)

        return model

    @classproperty
    def db_manager(mcs):
        if not mcs._db_manager:
            try:
                mcs._db_manager = DatabaseManager(**mcs.settings.DATABASES)
            except AttributeError:
                raise SettingsError(
                    'There is no database configuration! '
                    'Please, define the \'DATABASES\' variable in the your settings module'
                )

        return mcs._db_manager

    @classproperty
    def settings(mcs) -> ModuleType:
        env_var = 'ODM_SETTINGS_MODULE'
        settings_module = os.environ.get(env_var)

        if not settings_module:
            raise SettingsError(f'Specify an \'{env_var}\' variable in the environment.')

        try:
            return importlib.import_module(settings_module)
        except ImportError:
            raise SettingsError('Can not import settings module, make sure the path is correct.')

    @classmethod
    def _is_abstract(mcs, attrs: Dict) -> bool:
        return bool(getattr(attrs.get('Meta'), 'abstract', None))

    @classmethod
    def _get_model_module(mcs, name: AnyStr, attrs: Dict) -> AnyStr:
        return '.'.join((attrs.get('__module__'), name))

    @classmethod
    def _get_db_alias(mcs, attrs):
        return getattr(attrs.get('Meta'), 'db', 'default')

    @classmethod
    def _get_dispatcher(mcs, name: AnyStr, attrs: []) -> MongoDispatcher:
        """
        Get the dispatcher - the driver that organizes queries to the database.
        """
        dispatcher = None

        if not mcs._is_abstract(attrs):
            collection_name = mcs._get_collection_name(name, attrs)
            alias = mcs._get_db_alias(attrs)
            database = mcs._db_manager.get_database(alias)
            dispatcher = MongoDispatcher(database, collection_name)

        return dispatcher

    @classmethod
    def _get_collection_name(mcs, name: AnyStr, attrs: Dict) -> AnyStr:
        """
        Get the collection name or generate it by the model class name.
        """
        auto_name = '_'.join(re.findall(r'[A-Z][^A-Z]*', name[0].title() + name[1:])).lower()
        collection_name = getattr(attrs.get('Meta'), 'collection_name', auto_name)

        # Ensure that collection names do not match within the current database
        alias = mcs._get_db_alias(attrs)
        db_name = mcs.db_manager.get_db_name(alias)
        models = RelationManager().get_models()

        for model_name, model in models.items():
            init_db_alias = mcs._get_db_alias(model.__dict__)
            init_db_name = mcs.db_manager.get_db_name(init_db_alias)
            init_collection_name = model.get_collection_name()

            current = collection_name, db_name
            initial = init_collection_name, init_db_name

            if current == initial:
                cur_model = mcs._get_model_module(name, attrs)
                raise ValueError(
                    f'The collection name `{collection_name}` already used by `{model_name}` model. '
                    f'Please, specify a unique collection_name manually for {cur_model}.'
                )

        return collection_name

    @classmethod
    def _get_sorting(mcs, attrs: Dict) -> Tuple:
        """
        Get sorting attribute from the Meta.
        """
        return None if mcs._is_abstract(attrs) else getattr(attrs.get('Meta'), 'sorting', ())

    @classmethod
    def _get_declared_fields(mcs, bases: Tuple, attrs: Dict) -> Dict:
        """
        Get the collection fields, declared by the user when designing the model.
        """
        declared_fields = {}

        for field_name, field_instance in attrs.copy().items():
            if isinstance(field_instance, Field):
                if '__' in field_name:
                    raise AttributeError(
                        f'You can not use `__` in the field name {field_name}'
                    )

                declared_fields[field_name] = field_instance
                attrs.pop(field_name)

        # Inherit the declared fields of an abstract model
        for base in bases:
            if base is not MongoModel:
                declared_fields.update(base.get_declared_fields())

        return declared_fields


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
            if isinstance(field_instance, Field):
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

            elif isinstance(field_instance, Field):
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
    async def _validate(cls, field_instance: Field, field_name: AnyStr, field_value: Any) -> Any:
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
