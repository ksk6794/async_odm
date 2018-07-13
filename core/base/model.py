import re
import asyncio
from typing import Dict, AnyStr, Tuple, List

from ..resources import ResourcesManager
from ..dispatchers import MongoDispatcher
from ..managers import IndexManager


class ModelManagement:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class BaseModel(type):
    """
    Metaclass for all models.
    """
    _resources = ResourcesManager()

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __new__(mcs, name, bases, attrs):
        # If it is not MongoModel
        if bases:
            attrs['_management'] = ModelManagement(
                dispatcher=mcs._get_dispatcher(name, attrs),
                sorting=mcs._get_sorting(attrs),
                has_backwards=False
            )

        model = super().__new__(mcs, name, bases, attrs)

        if not mcs._is_abstract(attrs):
            mcs._resources.relations.register_model(model)

            if getattr(mcs._resources.settings, 'AUTO_INSPECT', True) is True:
                loop = asyncio.get_event_loop()
                task = IndexManager().process(model)
                loop.run_until_complete(task)

        return model

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
            database = mcs._resources.databases.get_database(alias)
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
        db_name = mcs._resources.databases.get_db_name(alias)
        models = mcs._resources.relations.get_models()

        for model_name, model in models.items():
            init_db_alias = mcs._get_db_alias(model.__dict__)
            init_db_name = mcs._resources.databases.get_db_name(init_db_alias)
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
