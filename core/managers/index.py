from pymongo.errors import OperationFailure
from pymongo import ASCENDING, DESCENDING, GEO2D, GEOHAYSTACK, GEOSPHERE, HASHED, TEXT

from core.logger import Logger
from core.index import Index


class IndexManager:
    def __init__(self):
        self.logger = Logger()

    async def process(self, model):
        collection = await self.get_collection(model)
        collection_indexes = await self.get_indexes(collection)

        # TODO: Validate index types
        indexes = self.get_model_indexes(model)

        if isinstance(indexes, (tuple, list)):
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
                        self.logger.info(
                            f'Index successfully removed: \n'
                            f'Name: {index_name} \n'
                        )

            # Find Meta Indexes missing in MongoDB - create them
            indexes_for_create = model_indexes - mongo_indexes

            for index in indexes_for_create:
                # Create composite index
                unique = list(filter(lambda elem: isinstance(elem, bool), index))[0]
                index = list(filter(lambda elem: not isinstance(elem, bool), index))
                index_name = await collection.create_index(index, unique=unique)

                self.logger.info(
                    f'Index successfully created: \n'
                    f'Model: {model.__module__}.{model.__name__} \n'
                    f'Name: {index_name} \n'
                    f'Compound: {len(index) > 1} \n'
                    f'Unique: {unique} \n'
                )

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
        except OperationFailure as err:
            # TODO: Log it!
            pass
        return indexes

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

