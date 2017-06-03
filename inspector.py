import asyncio
import importlib
import inspect
import json
import os

from core.base import MongoModel


class Inspector:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def is_mongo_model(obj):
        return inspect.isclass(obj) and issubclass(obj, MongoModel) and getattr(obj, '_declared_fields')

    def get_models(self):
        # Recursive walk by project directory
        for dirpath, dirnames, filenames in os.walk(self.BASE_PATH):
            module_path = dirpath[len(self.BASE_PATH) + 1:].replace('/', '.')

            # Check each file
            for filename in filenames:
                if filename.endswith('.py'):
                    filename = filename[:-3]
                    module_name = '.'.join([module_path, filename]) if module_path else filename
                    module_object = importlib.import_module(module_name)

                    for name, obj in module_object.__dict__.copy().items():
                        if self.is_mongo_model(obj):
                            yield obj


# https://habrahabr.ru/post/192870/#1
# https://www.compose.com/articles/document-validation-in-mongodb-by-example/
async def main():
    for model in Inspector().get_models():
        dispatcher = model._dispatcher
        connection = dispatcher.connection
        collection = await dispatcher._get_collection()
        index_res = await collection.create_index('author')

        database = await connection.get_database()
        collection_indexes = await database.eval('db.{collection_name}.getIndexes()'.format(collection_name=collection.name))

        data = json.dumps({'name': collection.name})
        collection_info = await database.eval('db.getCollectionInfos({})'.format(data))
        pass


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
