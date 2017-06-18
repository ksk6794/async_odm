import os
import re
import asyncio
import importlib
from bson import DBRef
from .utils import classproperty
from collections import namedtuple
from .queryset import QuerySet
from .dispatchers import MongoDispatcher
from core.connection import MongoConnection
from .fields import Field, BaseRelationField, BaseBackwardRelationField

WaitedRelation = namedtuple('WaitedRelation', ['field_name', 'field_instance', 'model_name'])


class BaseModel(type):
    """
    Metaclass for all models.
    """
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __new__(mcs, name, bases, attrs):
        if name != 'MongoModel':
            attrs['_collection_name'] = mcs._get_collection_name(name, attrs)
            attrs['_connection'] = mcs._get_connection(name, attrs)
            attrs['_dispatcher'] = mcs._get_dispatcher(attrs)
            attrs['_sorting'] = mcs._get_sorting(attrs)
            attrs['_declared_fields'] = mcs._get_declared_fields(attrs)

        model = super().__new__(mcs, name, bases, attrs)
        RelationManager().add_model(model)

        return model

    @classmethod
    def _get_connection(mcs, name, attrs):
        model = '.'.join((attrs.get('__module__'), name))
        settings_module = os.environ.get('ODM_SETTINGS_MODULE')

        if not settings_module:
            raise ImportError('Specify an `ODM_SETTINGS_MODULE` variable in the environment.')

        settings = importlib.import_module(settings_module)
        connection = None

        for db_name, db_settings in settings.DATABASES.items():
            if model in db_settings.get('models'):
                connection = MongoConnection(
                    host=db_settings.get('host'),
                    port=db_settings.get('port'),
                    database=db_name
                )
                break

        if not connection:
            exception = 'There is no database configuration for the `{}` model'
            raise Exception(exception.format(model))

        return connection

    @classmethod
    def _get_collection_name(mcs, name, attrs):
        """
        Get the collection name or generate it by the collection name.
        :param name: str - collection name
        :param attrs: list - class attributes
        :return: str - collection name
        """
        meta = attrs.get('Meta')
        collection_name = getattr(meta, 'collection_name', None) or '_'.join(re.findall(r'[A-Z][^A-Z]*', name)).lower()

        for model_name, model in RelationManager().get_models().items():
            if collection_name in model.get_collection_name():
                raise ValueError(
                    'The collection name `{collection_name}` already used by `{model_name}` model. '
                    'Please, specify collection_name manually.'.format(
                        collection_name=collection_name,
                        model_name=model_name
                    )
                )

        return collection_name

    @classmethod
    def _get_dispatcher(mcs, attrs):
        """
        Get the dispatcher - the driver that organizes queries to the database.
        :param attrs: list - class attributes
        :return: MongoDispatcher instance
        """
        connection = attrs.get('_connection')
        collection_name = attrs.get('_collection_name')
        return MongoDispatcher(connection, collection_name)

    @classmethod
    def _get_sorting(mcs, attrs):
        meta = attrs.get('Meta')
        return getattr(meta, 'sorting', ())

    @classmethod
    def _get_declared_fields(mcs, attrs):
        """
        Get the collection fields, declared by the user when designing the model.
        :param attrs: list - class attributes
        :return: dict - `key` is name of the field, `value` is a Field subclasses
        """
        declared_fields = {}

        for field_name, field_instance in attrs.copy().items():
            if isinstance(field_instance, Field):
                if '__' in field_name:
                    exception = 'You can not use `__` in the field name {field_name}'.format(
                        field_name=field_name
                    )
                    raise AttributeError(exception)

                # Add dispatcher and field name to each field instance (for validation)
                field_instance.set_field_name(field_name)

                declared_fields[field_name] = field_instance
                attrs.pop(field_name)

        return declared_fields


class RelationManager:
    """
    The singleton manager that organize the relations of models.
    """
    _instance = None
    _models = {}
    _waited_relations = []

    def __new__(cls):
        if not cls._instance:
            cls._instance = object.__new__(cls)
        return cls._instance

    def add_model(self, model):
        """
        Add the model to the list to implement the relations between another models.
        Model names can not be duplicated.
        :param model: MongoModel instance
        :return: void
        """
        name = '.'.join((model.__module__, model.__name__))

        if model.__name__ is not 'MongoModel':
            self._models[name] = model
            self._process_relations(model)

            if self._waited_relations:
                self._handle_waited_relations()

    def get_model(self, model_name):
        return self._models.get(model_name)

    def get_models(self):
        return self._models

    def _process_relations(self, model):
        for field_name, field_instance in model.get_declared_fields().items():
            if isinstance(field_instance, BaseRelationField):
                relation = field_instance.relation

                # Get a relationship model
                if isinstance(relation, BaseModel):
                    rel_model = relation

                elif isinstance(relation, str):
                    if '.' not in relation:
                        relation = '.'.join((model.__module__, relation))
                        field_instance.relation = relation

                    rel_model = self.get_model(relation)

                else:
                    exception = 'Wrong relation type! ' \
                                'You should specify the model class ' \
                                'or str with name of class model.'
                    raise Exception(exception)

                # If the model is not yet registered
                if rel_model:
                    self._handle_relation(field_name, field_instance, rel_model, model)
                else:
                    # Add model to the waiting list
                    waited_relation = WaitedRelation(
                        field_name=field_name,
                        field_instance=field_instance,
                        model_name='.'.join((model.__module__, model.__name__))
                    )
                    self._waited_relations.append(waited_relation)

    @staticmethod
    def _handle_relation(field_name, field_instance, rel_model, model):
        # The model referred to by the current model
        field_instance.relation = rel_model
        related_name = field_instance.related_name

        # If the parameter `related_name` was specified
        if related_name:
            # Add a field to retrieve referring objects to the current object
            backward_relation = field_instance.backward_class(model)
            backward_relation._name = field_name

            # Add backward relation by related_name argument
            declared_fields = getattr(rel_model, '_declared_fields')
            declared_fields[related_name] = backward_relation

    def _handle_waited_relations(self):
        for waited_relation in self._waited_relations:
            field_name = waited_relation.field_name
            field_instance = waited_relation.field_instance
            model_name = waited_relation.model_name

            model = self.get_model(model_name)
            rel_model = self.get_model(field_instance.relation)

            if rel_model:
                self._handle_relation(field_name, field_instance, rel_model, model)
                index = self._waited_relations.index(waited_relation)
                del self._waited_relations[index]


class MongoModel(metaclass=BaseModel):
    _id = None
    _dispatcher = None
    _collection_name = None
    _declared_fields = None
    _sorting = None

    def __init__(self, **document):
        # Fields that were set in the model instance, but not declared.
        self._undeclared_fields = {}
        self._modified_fields = []

        # Save fields not declared in the model.
        for field_name, field_value in document.items():
            if field_name not in self.get_declared_fields() and field_name != '_id':
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
            if key not in self._declared_fields:
                self._undeclared_fields[key] = value
            self._modified_fields.append(key)
        super().__setattr__(key, value)

    def __getattribute__(self, item):
        attr = super().__getattribute__(item)

        declared_fields = object.__getattribute__(self, '_declared_fields')
        field_instance = declared_fields.get(item)

        if isinstance(field_instance, (BaseRelationField, BaseBackwardRelationField)):
            attr = field_instance

            # Set the _id of the current object as a value
            # provide backward relationship for relation fields
            if isinstance(attr, BaseBackwardRelationField):
                attr._value = object.__getattribute__(self, '_id')

        return attr

    @classproperty
    def objects(cls):
        return QuerySet(model=cls)

    @classmethod
    def get_declared_fields(cls):
        return cls._declared_fields

    @classmethod
    def get_dispatcher(cls):
        return cls._dispatcher

    @classmethod
    def get_collection_name(cls):
        return cls._collection_name

    @classmethod
    def get_sorting(cls):
        return cls._sorting

    @property
    def id(self):
        return self._id

    async def save(self):
        document = await self._update() if self._id else await self._create()
        self.__dict__.update(document)

    async def delete(self):
        await self._dispatcher.delete_one(self._id)

    def _process_relation_field(self, field_name, field_instance):
        # TODO: Check if the object exists in the database
        field_value = self.__dict__.get(field_name)

        # Set the DBRef for the field value (create) or leave the same (update)
        # TODO: Can't get collection_name of None if relation class is a string
        collection_name = field_instance.relation.get_collection_name()
        document_id = getattr(field_value, '_id', field_value)
        field_value = DBRef(collection_name, document_id)

        return field_value

    async def _child_validator(self, field_name):
        """
        Call user-defined validation methods.
        :param field_name: str
        :return: validated data
        """
        new_value = None
        validate_method = getattr(self, 'validate_{}'.format(field_name), None)

        if callable(validate_method):
            value = self.__dict__.get(field_name)
            is_coroutine = asyncio.iscoroutinefunction(validate_method)
            new_value = await validate_method(value=value) if is_coroutine else validate_method(value=value)

        return new_value

    async def _create(self):
        """
        Create document with all defined fields.
        :return: dict
        """
        field_values = await self.get_internal_values()
        insert_result = await self._dispatcher.create(**field_values)

        # Generate document from field_values and inserted_id
        field_values.update({'_id': insert_result.inserted_id})
        document = self.get_external_values(field_values)

        return document

    async def _update(self):
        """
        Update only modified document fields.
        :return: dict
        """
        field_values = await self.get_internal_values()
        modified = {key: value for key, value in field_values.items() if key in self._modified_fields}
        document = await self._dispatcher.update_one(self._id, **modified)
        document = self.get_external_values(document)

        return document

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
        :return: dict
        """
        fields_values = {}

        for field_name, field_instance in self.get_declared_fields().items():
            field_value = self.__dict__.get(field_name)
            field_instance.set_field_value(field_value)

            # Replace to relation ObjectId
            if isinstance(field_instance, BaseRelationField):
                field_value = self._process_relation_field(field_name, field_instance)

            elif isinstance(field_instance, Field):
                # Validate field value
                field_value = field_instance.validate()

                # Call Model child (custom) validate methods
                new_value = await self._child_validator(field_name)

                # Set the post validate value
                if new_value is not None:
                    field_value = new_value

                # Bring to the internal value
                field_value = field_instance.to_internal_value(field_value)

            fields_values[field_name] = field_value

            # Undeclared fields are not validated
            undeclared = self._undeclared_fields
            fields_values.update(undeclared)

        return fields_values
