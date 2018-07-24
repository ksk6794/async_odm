import re
import asyncio
from typing import Dict, AnyStr

from ..resources import ResourcesManager
from ..dispatchers import MongoDispatcher


class BaseModel(type):
    """
    Metaclass for all models.
    """
    _resources = ResourcesManager()

    def __init__(cls, name, bases, attrs):
        if not cls.is_abstract(attrs):
            # Process models relations
            cls._resources.relations.register_model(cls)
            auto_inspect = getattr(cls._resources.settings, 'AUTO_INSPECT', True)

            if auto_inspect is True:
                loop = asyncio.get_event_loop()
                task = cls._resources.indexes.process(cls)
                loop.run_until_complete(task)

        super().__init__(name, bases, attrs)

    def __new__(mcs, name, bases, attrs):
        if not mcs.is_abstract(attrs):
            attrs['_dispatcher'] = mcs.get_dispatcher(name, attrs)

        return super().__new__(mcs, name, bases, attrs)

    @classmethod
    def is_abstract(mcs, attrs: Dict) -> bool:
        meta = attrs.get('Meta')
        return bool(getattr(meta, 'abstract', None))

    @classmethod
    def get_db_alias(mcs, attrs: Dict):
        meta = attrs.get('Meta')
        return getattr(meta, 'db', 'default')

    @classmethod
    def get_dispatcher(mcs, name: AnyStr, attrs: Dict) -> MongoDispatcher:
        """
        Get the dispatcher - the driver that organizes queries to the database.
        """
        collection_name = mcs.get_collection_name(name, attrs)
        alias = mcs.get_db_alias(attrs)
        database = mcs._resources.databases.get_database(alias)

        return MongoDispatcher(database, collection_name)

    @classmethod
    def check_match(mcs, attrs: Dict, collection_name: AnyStr):
        """
        Ensure that collection names do not match within the current database.
        """
        match = None
        alias = mcs.get_db_alias(attrs)
        db_name = mcs._resources.databases.get_db_name(alias)
        registered = mcs._resources.relations.get_registered()
        models = registered.get(db_name, {})

        if collection_name in models.keys():
            match = models[collection_name]

        return match

    @classmethod
    def get_collection_name(mcs, name: AnyStr, attrs: Dict) -> AnyStr:
        """
        Get the collection name or generate it by the model class name.
        """
        auto_name = '_'.join(re.findall(r'[A-Z][^A-Z]*', name[0].title() + name[1:])).lower()
        collection_name = getattr(attrs.get('Meta'), 'collection_name', auto_name)
        match = mcs.check_match(attrs, collection_name)

        if match:
            cur_model = f'{attrs.get("__module__")}.{name}'
            match_model = f'{match.__module__}.{match.__name__}'

            raise ValueError(
                f'The collection name \'{collection_name}\' already used by \'{match_model}\' model. '
                f'Please, specify a unique collection_name manually for \'{cur_model}\'.'
            )

        return collection_name
