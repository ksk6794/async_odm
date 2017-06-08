import os
import glob
import json
import inspect
import asyncio
import importlib
from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from core.base import MongoModel
from core.index import Index


class BaseIndexInspector:
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


class FieldIndexInspector(BaseIndexInspector):
    async def process(self, model, field_instance):
        collection = await self.get_collection(model)

        unique = getattr(field_instance, 'unique', False)
        index = getattr(field_instance, 'index', None)
        index = ASCENDING if unique and not index else index
        field_name = field_instance.get_field_name()

        # Get collection Indexes
        collection_indexes = await self.get_indexes(collection)

        cur_index_name = None
        cur_index_type = None
        cur_index_unique = None

        for index_name, index_data in collection_indexes.items():
            index_key = index_data.get('key', {})
            index_unique = index_data.get('unique', False)

            # Compound indexes have several keys
            is_composite = len(index_key) > 1
            indexed_field = index_key[0][0]

            if not is_composite and field_name == indexed_field and isinstance(index_unique, bool):
                cur_index_name = index_name
                cur_index_type = {k: v for k, v in index_key}.get(field_name)
                cur_index_unique = index_unique
                break

        event = None

        if index or unique:
            if not cur_index_name:
                # Create index
                await collection.create_index([(field_name, index)], unique=unique)
                event = 'created'
            else:
                if index != cur_index_type or unique != cur_index_unique:
                    # Change index
                    await collection.drop_index(cur_index_name)
                    await collection.create_index([(field_name, index)], unique=unique)
                    event = 'changed'

        elif cur_index_name:
            # Remove index
            await collection.drop_index(cur_index_name)
            event = 'removed'

        # Log event
        if event:
            print('-------------------------------------------\n'
                  'Index for field `{field_name}` was {event}!\n'
                  'Index type: {index_type}\n'
                  'Unique: {unique}\n'.
                  format(
                    event=event,
                    field_name=field_name,
                    index_type=index,
                    unique=unique,
                  ))


class CompositeIndexInspector(BaseIndexInspector):
    async def process(self, model):
        collection = await self.get_collection(model)

        meta_data = getattr(model, 'Meta', None)
        indexes = getattr(meta_data, 'indexes', ())
        collection_indexes = await self.get_indexes(collection)

        if isinstance(indexes, (tuple, list)):
            mongo_indexes = set(tuple(item['key']) + (item.get('unique', False),) for item in collection_indexes.values() if len(item['key']) > 1)
            meta_indexes = set(item.composite_dict + (item.unique,) for item in indexes if isinstance(item, Index))

            # Find indexes in MongoDB that are not in Meta - delete them
            indexes_for_delete = mongo_indexes - meta_indexes

            for index in indexes_for_delete:
                find = list(filter(lambda elem: not isinstance(elem, bool), index))

                for index_name, index_data in collection_indexes.items():
                    if index_data.get('key') == find:
                        # Remove index
                        await collection.drop_index(index_name)
                        print('removed')

            # Find Meta Indexes missing in MongoDB - create them
            indexes_for_create = meta_indexes - mongo_indexes

            for index in indexes_for_create:
                # Create composite index
                unique = list(filter(lambda elem: isinstance(elem, bool), index))[0]
                index = list(filter(lambda elem: not isinstance(elem, bool), index))
                await collection.create_index(index, unique=unique)
                print('created')


class Inspector:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    PARAMS_INSPECTORS = {
        'unique': FieldIndexInspector,
        'index': FieldIndexInspector,
    }

    @staticmethod
    def is_odm_model(obj):
        return inspect.isclass(obj) and issubclass(obj, MongoModel)

    @staticmethod
    def has_declared_fields(obj):
        return hasattr(obj, 'get_declared_fields') and obj.get_declared_fields()

    def get_modules(self):
        # Recursive walk by project directory
        for filename in glob.iglob(self.BASE_PATH + '/**/*.py', recursive=True):
            # Cut the BASE_PATH and .py extension from filename
            module_path = filename[len(self.BASE_PATH) + 1:-3].replace('/', '.')
            module_object = importlib.import_module(module_path)
            yield module_object

    def get_odm_models(self):
        for module_object in self.get_modules():
            for name, obj in module_object.__dict__.copy().items():
                if self.is_odm_model(obj) and self.has_declared_fields(obj):
                    model = obj
                    yield model

    async def process_models(self):
        for model in self.get_odm_models():
            await self.process_model(model)

    async def process_model(self, model):
        await CompositeIndexInspector().process(model)

        for field_name, field_instance in model.get_declared_fields().items():
            for param_name in field_instance.kwargs:
                param_inspector = self.PARAMS_INSPECTORS.get(param_name)

                if param_inspector:
                    await param_inspector().process(model, field_instance)


# Get collection info (validators)
# collection_info = await database.eval(
#     'db.getCollectionInfos({data})'.format(
#         data=json.dumps({'name': collection.name})
#     )
# )


# https://habrahabr.ru/post/192870/#1
# https://www.compose.com/articles/document-validation-in-mongodb-by-example/
async def main():
    await Inspector().process_models()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
