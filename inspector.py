import os
import glob
import json
import inspect
import asyncio
import importlib

from core.base import MongoModel


class Inspector:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

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
        for field_name, field_instance in model.get_declared_fields().items():

            # Process indexes
            unique = getattr(field_instance, 'unique', None)

            if unique is not None:
                dispatcher = model._dispatcher
                collection = await dispatcher._get_collection()
                connection = dispatcher.connection
                database = await connection.get_database()

                # Get collection Indexes
                collection_indexes = await database.eval(
                    'db.{collection_name}.getIndexes()'.format(collection_name=collection.name)
                )
                # TODO: Check for presence or absence

                # Create Index
                # index_name = await collection.create_index(field_name, unique=True)

                # Drop Index
                # index_res = await collection.drop_index()
                
                # Get collection info (validators)
                # collection_info = await database.eval('db.getCollectionInfos({data})'.format(
                #     data=json.dumps({'name': collection.name})
                # ))

    async def process_field(self, model, field):
        pass

# https://habrahabr.ru/post/192870/#1
# https://www.compose.com/articles/document-validation-in-mongodb-by-example/
async def main():
    await Inspector().process_models()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
