from asyncio import iscoroutine

from pymongo import ReturnDocument
from .exceptions import DoesNotExist, MultipleObjectsReturned


class MongoDispatcher:
    def __init__(self, database, collection_name):
        self.database = database
        self.collection_name = collection_name

    async def count(self, **kwargs):
        collection = await self.get_collection()
        return await collection.count(kwargs)

    async def get_collection(self):
        if iscoroutine(self.database):
            self.database = await self.database

        return self.database[self.collection_name]

    async def create(self, **kwargs):
        """
        Insert document.
        :param kwargs: dict (Fields to update)
        :return: InsertOneResult (object with inserted_id)
        """
        collection = await self.get_collection()
        return await collection.insert_one(kwargs)

    async def bulk_create(self, documents):
        collection = await self.get_collection()
        return await collection.bulk_write(documents)

    async def update_one(self, _id, **kwargs):
        """
        Find and modify by `_id`.
        :param _id: ObjectId
        :param kwargs: dict (Fields to update)
        :return: dict (Document before the changes)
        """
        collection = await self.get_collection()
        return await collection.find_one_and_update(
            filter={'_id': _id},
            update={'$set': kwargs},
            return_document=ReturnDocument.AFTER
        )

    async def update_many(self, find, **kwargs):
        collection = await self.get_collection()
        return await collection.update_many(find, {'$set': kwargs})

    async def get(self, projection, **kwargs):
        count = await self.count(**kwargs)

        if count == 1:
            collection = await self.get_collection()
            params = {'projection': projection} if projection else {}
            return await collection.find_one(kwargs, **params)

        elif count < 1:
            raise DoesNotExist('Document does not exists!')

        elif count > 1:
            raise MultipleObjectsReturned('Got more than 1 document - it returned {count}'.format(count=count))

    async def find(self, **kwargs):
        collection = await self.get_collection()
        return collection.find(**kwargs)

    async def delete_one(self, **kwargs):
        collection = await self.get_collection()
        return await collection.delete_one(filter=kwargs)

    async def delete_many(self, **kwargs):
        collection = await self.get_collection()
        return await collection.delete_many(filter=kwargs)
