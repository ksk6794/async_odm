from pymongo import ReturnDocument
from .exceptions import DoesNotExist, MultipleObjectsReturned


class MongoDispatcher:
    def __init__(self, connection, collection_name):
        self.connection = connection
        self.collection_name = collection_name

    async def count(self, **kwargs):
        collection = await self.get_collection()
        count = await collection.count(kwargs)
        return count

    async def get_collection(self):
        # TODO: Disallow conflicting collection names ('name', ...)
        database = await self.connection.get_database()
        collection = getattr(database, self.collection_name)
        return collection

    async def create(self, **kwargs):
        """
        Insert document.
        :param kwargs: dict (Fields to update)
        :return: InsertOneResult (object with inserted_id)
        """
        collection = await self.get_collection()
        insert_result = await collection.insert_one(kwargs)
        return insert_result

    async def bulk_create(self, documents):
        collection = await self.get_collection()
        results = await collection.bulk_write(documents)
        return results

    async def update_one(self, _id, **kwargs):
        """
        Find and modify by `_id`.
        :param _id: ObjectId
        :param kwargs: dict (Fields to update)
        :return: dict (Document before the changes)
        """
        collection = await self.get_collection()
        document = await collection.find_one_and_update(
            filter={'_id': _id},
            update={'$set': kwargs},
            return_document=ReturnDocument.AFTER
        )
        return document

    async def update_many(self, find, **kwargs):
        collection = await self.get_collection()
        result = await collection.update_many(find, {'$set': kwargs})
        return result

    async def get(self, projection, **kwargs):
        count = await self.count(**kwargs)

        if count == 1:
            collection = await self.get_collection()
            params = {'projection': projection} if projection else {}
            document = await collection.find_one(kwargs, **params)
            return document

        elif count < 1:
            raise DoesNotExist('Document does not exists!')

        elif count > 1:
            raise MultipleObjectsReturned('Got more than 1 document - it returned {count}'.format(count=count))

    async def find(self, **kwargs):
        collection = await self.get_collection()

        # TODO: Move check and processing to QuerySet
        available_params = {
            'filter': dict,
            'sort': list,
            'limit': int,
            'skip': int,
            'projection': dict,
        }
        params = {}
        for param_name, param_type in available_params.items():
            param_value = kwargs.get(param_name)

            if isinstance(param_value, param_type):
                if hasattr(param_value, '__len__') and not len(param_value):
                    continue

                params[param_name] = param_value

        cursor = collection.find(**params)

        return cursor

    async def delete_one(self, _id):
        collection = await self.get_collection()
        result = await collection.delete_one(filter={'_id': _id})
        return result

    async def delete_many(self, **kwargs):
        collection = await self.get_collection()
        result = await collection.delete_many(filter=kwargs)
        return result
