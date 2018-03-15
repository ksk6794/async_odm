import os
import re
import copy
import asyncio
import importlib
from bson import DBRef

from core.exceptions import SettingsError
from core.managers import RelationManager, OnDeleteManager
from .queryset import QuerySet
from .utils import classproperty
from .managers import MongoConnection, IndexManager
from .dispatchers import MongoDispatcher
from .constants import UPDATE, CREATE
from .fields import Field, BaseRelationField, BaseBackwardRelationField


class ModelManagement:
    # __slots__ = ('declared_fields', 'dispatcher', 'sorting', 'has_backwards')

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class BaseModel(type):
    """
    Metaclass for all models.
    """
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

        if not mcs._is_abstract(attrs) and model.__name__ != 'MongoModel':
            RelationManager().add_model(model)

            if getattr(mcs.settings, 'AUTO_INSPECT', True) is True:
                loop = asyncio.get_event_loop()
                task = IndexManager().process(model)
                loop.run_until_complete(task)

        return model

    @classproperty
    def settings(mcs):
        settings_module = os.environ.get('ODM_SETTINGS_MODULE')

        if not settings_module:
            raise ImportError(
                'Specify an \'ODM_SETTINGS_MODULE\' variable in the environment.'
            )

        return importlib.import_module(settings_module)

    @classmethod
    def _is_abstract(mcs, attrs):
        return bool(getattr(attrs.get('Meta'), 'abstract', None))

    @classmethod
    def _get_model_module(mcs, name, attrs):
        return '.'.join((attrs.get('__module__'), name))

    @classmethod
    def _get_models_list(mcs, models):
        """
        Join each model name to the path.
        :param models: dict - {'module_path': 'model_name'}
        :return: list - list of models with full path
        """
        models_list = []

        for path, models in models.items():
            for model in models:
                models_list.append('.'.join([path, model]))

        return models_list

    @classmethod
    def _get_db_settings(mcs, name, attrs):
        """
        Get current model settings from the settings module.
        :param name: str - model name
        :param attrs: list - class attributes
        :return: tuple - database name, database settings
        """
        model = mcs._get_model_module(name, attrs)
        db = getattr(attrs.get('Meta'), 'db', 'default')
        db_settings = mcs.settings.DATABASES.get(db)

        if not db_settings:
            raise SettingsError(
                'There is no database configuration for the \'{}\' model'.format(model)
            )

        return db_settings

    @classmethod
    def _get_connection(mcs, name, attrs):
        """
        Get the settings and connect to the database.
        :param name: str - collection name
        :param attrs: list - class attributes
        :return: MongoConnection instance
        """
        db_settings = mcs._get_db_settings(name, attrs)
        connection = MongoConnection(**db_settings)

        return connection

    @classmethod
    def _get_collection_name(mcs, name, attrs):
        """
        Get the collection name or generate it by the model class name.
        :param name: str - collection name
        :param attrs: list - class attributes
        :return: str - collection name
        """
        # TODO: If more than one upper-case char (.isupper)
        auto_name = '_'.join(re.findall(r'[A-Z][^A-Z]*', name)).lower()
        collection_name = getattr(attrs.get('Meta'), 'collection_name', auto_name)
        db_name = mcs._get_connection(name, attrs).database

        models = RelationManager().get_models()

        for model_name, model in models.items():
            init_db_name = model.get_connection().database
            init_collection_name = model.get_collection_name()

            # Ensure that collection names do not match within the current database
            current = collection_name, db_name
            initial = init_collection_name, init_db_name

            if current == initial:
                raise ValueError(
                    'The collection name `{collection_name}` already used by `{model_name}` model. '
                    'Please, specify a unique collection_name manually for {cur_model}.'.format(
                        collection_name=collection_name,
                        model_name=model_name,
                        cur_model=mcs._get_model_module(name, attrs)
                    )
                )

        return collection_name

    @classmethod
    def _get_dispatcher(mcs, name, attrs):
        """
        Get the dispatcher - the driver that organizes queries to the database.
        :param attrs: list - class attributes
        :return: MongoDispatcher instance
        """
        dispatcher = None

        if not mcs._is_abstract(attrs):
            connection = mcs._get_connection(name, attrs)
            collection_name = mcs._get_collection_name(name, attrs)
            dispatcher = MongoDispatcher(connection, collection_name)

        return dispatcher

    @classmethod
    def _get_sorting(mcs, attrs):
        """
        Get sorting attribute from the Meta.
        :param attrs: list - class attributes
        :return: tuple - list of field names
        """
        return None if mcs._is_abstract(attrs) else getattr(attrs.get('Meta'), 'sorting', ())

    @classmethod
    def _get_declared_fields(mcs, bases, attrs):
        """
        Get the collection fields, declared by the user when designing the model.
        :param attrs: list - class attributes
        :return: dict - `key` is name of the field, `value` is a Field subclasses
        """
        declared_fields = {}

        for field_name, field_instance in attrs.copy().items():
            if isinstance(field_instance, Field):
                if '__' in field_name:
                    raise AttributeError(
                        'You can not use `__` in the field name {field_name}'.format(
                            field_name=field_name
                        )
                    )

                declared_fields[field_name] = field_instance
                attrs.pop(field_name)

        # Inherit the declared fields of an abstract model
        for base in bases:
            if base is not MongoModel:
                declared_fields.update(base.get_declared_fields())

        return declared_fields


class MongoModel(metaclass=BaseModel):
    _id = None
    _management = None

    # Stores the current action (save/update) for field validation
    _action = None

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
        return '{model_name} _id: {document_id}'.format(
            model_name=self.__class__.__name__,
            document_id=self.__dict__.get('_id')
        )

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
                '\'{model_name}\' model has no attribute \'{attribute}\''.format(
                    model_name=self.__class__.__name__,
                    attribute=item
                )
            )

        field_name = match.group('field_name')
        declared_fields = self.get_declared_fields()

        if field_name not in declared_fields:
            raise AttributeError(
                'Field \'{field_name}\' is not declared'.format(
                    field_name=field_name
                )
            )

        field_instance = declared_fields.get(field_name)
        choices = getattr(field_instance, 'choices', None)

        if not choices:
            raise AttributeError(
                'Field \'{field_name}\' has not attribute \'choices\''.format(
                    field_name=field_name
                )
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
            # Prevent 'can not reuse awaitable coroutine'
            field_instance = copy.deepcopy(field_instance)

            # Set the value with relation object id for a field to provide base relation
            if isinstance(field_instance, BaseRelationField):
                field_value = __getattribute(self, '__dict__').get(item)

            # Set the _id of the current object as a value
            # provide backward relationship for relation fields
            elif isinstance(field_instance, BaseBackwardRelationField):
                field_value = __getattribute(self, '_id')

            if field_value is not None:
                field_instance.set_field_value(field_value)
                attr = field_instance

        return attr

    @classproperty
    def objects(cls):
        return QuerySet(model=cls)

    @property
    def id(self):
        return self._id

    @classproperty
    def has_backwards(cls):
        return cls._get_management_param('has_backwards')

    @classmethod
    def get_declared_fields(cls):
        return cls._get_management_param('declared_fields')

    @classmethod
    def get_dispatcher(cls):
        return cls._get_management_param('dispatcher')

    @classmethod
    def get_collection_name(cls):
        return cls.get_dispatcher().collection_name

    @classmethod
    def get_connection(cls):
        return cls.get_dispatcher().connection

    @classmethod
    def get_sorting(cls):
        return cls._get_management_param('sorting')

    @classmethod
    def _get_management_param(cls, param):
        return getattr(cls._management, param, None)

    async def save(self):
        document = await self._update() if self._id else await self._create()
        self.__dict__.update(document)
        self._action = None

    async def delete(self):
        if self.has_backwards:
            await OnDeleteManager().handle_backwards([self])

        await self.objects.internal_query.delete_one(_id=self.id)

        # Remove document id from the ODM object
        self._id = None

    def get_external_values(self, document):
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

    async def get_internal_values(self):
        """
        Convert external values to internal for saving to a database.
        """
        fields_values = {}

        for field_name, field_instance in self.get_declared_fields().items():
            # Bring to internal values only modified fields (for update action)
            if self._action is UPDATE and field_name not in self._modified_fields:
                continue

            field_value = None

            if isinstance(field_instance, BaseRelationField):
                field_value = await self._relation_field_to_internal(field_name, field_instance)

            elif isinstance(field_instance, Field):
                field_value = await self._field_to_internal(field_name, field_instance)

            fields_values[field_name] = field_value

        # Undeclared fields are not validated
        undeclared = self._undeclared_fields
        fields_values.update(undeclared)

        return fields_values

    async def _create(self):
        """
        Create document with all defined fields.
        :return: dict
        """
        self._action = CREATE
        field_values = await self.get_internal_values()
        insert_result = await self.objects.internal_query.create_one(**field_values)

        # Generate document from field_values and inserted_id
        field_values.update({'_id': insert_result.inserted_id})
        document = self.get_external_values(field_values)

        return document

    async def _update(self):
        """
        Update only modified document fields.
        :return: dict
        """
        self._action = UPDATE
        field_values = await self.get_internal_values()
        document = await self.objects.internal_query.update_one(self._id, **field_values)
        document = self.get_external_values(document)

        return document

    async def _relation_field_to_internal(self, field_name, field_instance):
        """
        Replace to relation ObjectId
        """
        field_value = self.__dict__.get(field_name)

        # Set the DBRef for the field value (create) or leave the same (update)
        collection_name = field_instance.relation.get_collection_name()
        document_id = getattr(field_value, '_id', field_value)

        # For consistency check if exist related object in the database
        if document_id is not None:
            if not await field_instance.relation.objects.filter(_id=document_id).count():
                raise ValueError(
                    'Relation document with ObjectId(\'{document_id}\') does not exist.\n'
                    'Model: \'{model_name}\', Field: \'{field_name}\''.format(
                        document_id=str(document_id),
                        model_name=self.__class__.__name__,
                        field_name=field_name
                    ))

            field_value = DBRef(collection_name, document_id)
        else:
            field_value = None

        return field_value

    async def _field_to_internal(self, field_name, field_instance):
        # Validate field value
        field_value = self.__dict__.get(field_name)
        field_value = field_instance.get_value(field_name, field_value, self._action)
        field_instance.validate(field_name, field_value)

        # Call Model child (custom) validate methods
        new_value = await self._child_validator(field_name)

        # TODO: Check if the validator returns a value of another type.

        # Set the post validate value
        if new_value is not None:
            field_value = new_value

        # Bring to the internal value
        field_value = field_instance.to_internal_value(field_value)

        return field_value

    async def _child_validator(self, field_name):
        """
        Call user-defined validation methods.
        :param field_name: str
        :return: validated data
        """
        new_value = None
        validator = getattr(self, 'validate_{}'.format(field_name), None)

        if callable(validator):
            value = self.__dict__.get(field_name)
            is_coro = asyncio.iscoroutinefunction(validator)
            new_value = await validator(value=value) if is_coro else validator(value=value)

        return new_value
