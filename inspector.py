import os
import glob
import inspect
import asyncio
import importlib
from pymongo.errors import OperationFailure
from pymongo import ASCENDING, DESCENDING, GEO2D, GEOHAYSTACK, GEOSPHERE, HASHED, TEXT

from core.base import MongoModel
from core.exceptions import SettingsError
from core.index import Index


class BaseInspector:
    @staticmethod
    async def get_collection(model):
        dispatcher = model.get_dispatcher()
        collection = await dispatcher.get_collection()
        return collection

    @staticmethod
    async def get_indexes(collection):
        # Get collection Indexes
        indexes = {}
        try:
            indexes = await collection.index_information()
        except OperationFailure:
            pass
        return indexes


class IndexInspector(BaseInspector):
    @staticmethod
    def get_model_indexes(model):
        # Get indexes from Meta
        meta_data = getattr(model, 'Meta', None)
        meta_indexes = list(getattr(meta_data, 'indexes', ()))

        # Get indexes from fields
        field_indexes = []

        # Find and convert indexes from field attributes to Index instance
        for field_name, field_instance in model.get_declared_fields().items():
            unique = getattr(field_instance, 'unique', False)
            index = getattr(field_instance, 'index', None)

            if unique or index:
                index = ASCENDING if unique and not index else index
                field_index = Index(((field_name, index),), unique=unique)
                field_indexes.append(field_index)

        # Join meta and field indexes
        return meta_indexes + field_indexes

    async def process(self, model):
        collection = await self.get_collection(model)
        collection_indexes = await self.get_indexes(collection)

        # TODO: Validate index types
        indexes = self.get_model_indexes(model)

        if indexes and isinstance(indexes, (tuple, list)):
            mongo_indexes = set(
                tuple(item['key']) + (item.get('unique', False),)
                for name, item in collection_indexes.items()
                # Do not analyze the default _id index
                if name != '_id_'
            )
            model_indexes = set(
                item.composite_dict + (item.unique,)
                for item in indexes
                if isinstance(item, Index)
            )

            # Find indexes in MongoDB that are not in Meta - delete them
            indexes_for_delete = mongo_indexes - model_indexes

            for index in indexes_for_delete:
                find = list(filter(lambda elem: not isinstance(elem, bool), index))

                for index_name, index_data in collection_indexes.items():
                    if index_data.get('key') == find:
                        # Remove index
                        await collection.drop_index(index_name)
                        print('removed')

            # Find Meta Indexes missing in MongoDB - create them
            indexes_for_create = model_indexes - mongo_indexes

            for index in indexes_for_create:
                # Create composite index
                unique = list(filter(lambda elem: isinstance(elem, bool), index))[0]
                index = list(filter(lambda elem: not isinstance(elem, bool), index))
                await collection.create_index(index, unique=unique)
                print('created')


class Inspector:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def is_odm_model(obj):
        return inspect.isclass(obj) and issubclass(obj, MongoModel)

    @staticmethod
    def has_declared_fields(obj):
        return bool(obj.get_declared_fields())

    def get_modules(self):
        # Recursive walk by project directory
        for filename in glob.iglob(self.BASE_PATH + '/**/*.py', recursive=True):
            # Cut the BASE_PATH and .py extension from filename
            module_path = filename[len(self.BASE_PATH) + 1:-3].replace('/', '.')
            module_object = importlib.import_module(module_path)
            yield module_object

    @staticmethod
    def get_odm_models():
        settings_module = os.environ.get('ODM_SETTINGS_MODULE')

        if not settings_module:
            raise ImportError(
                'Specify an \'ODM_SETTINGS_MODULE\' variable in the environment.'
            )

        settings = importlib.import_module(settings_module)

        for db_name, db_settings in settings.DATABASES.items():
            for path, models in db_settings.get('models').items():
                for model_name in models:
                    model_module = importlib.import_module(path)

                    if not hasattr(model_module, model_name):
                        raise SettingsError(
                            'The model \'{model_name}\' is specified in the configuration, '
                            'but is not in the module \'{path}\'.'.format(
                                model_name=model_name,
                                path=path
                            )
                        )

                    model = getattr(model_module, model_name)
                    yield model

    async def process_models(self):
        for model in self.get_odm_models():
            await IndexInspector().process(model)


async def main():
    await Inspector().process_models()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
