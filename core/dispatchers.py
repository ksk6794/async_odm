from asyncio import iscoroutine
from typing import Dict, List, AnyStr

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.cursor import Cursor
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult, BulkWriteResult

from .exceptions import DoesNotExist, MultipleObjectsReturned


class MongoDispatcher:
    def __init__(self, database: AsyncIOMotorDatabase, collection_name: AnyStr):
        self.database = database
        self.collection_name = collection_name

    async def count(self, **kwargs) -> int:
        collection = await self.get_collection()
        return await collection.count_documents(kwargs)

    async def get_collection(self) -> Collection:
        if iscoroutine(self.database):
            self.database = await self.database

        return self.database[self.collection_name]

    async def create(self, **kwargs) -> InsertOneResult:
        """
        Insert document.
        """
        collection = await self.get_collection()
        return await collection.insert_one(kwargs)

    async def bulk_create(self, documents: List) -> BulkWriteResult:
        collection = await self.get_collection()
        return await collection.bulk_write(documents)

    async def update_one(self, _id: ObjectId, **kwargs) -> Dict:
        """
        Find and modify document by `_id`.
        """
        collection = await self.get_collection()
        return await collection.find_one_and_update(
            filter={'_id': _id},
            update={'$set': kwargs},
            return_document=ReturnDocument.AFTER
        )

    async def update_many(self, find: Dict, **kwargs) -> UpdateResult:
        collection = await self.get_collection()
        return await collection.update_many(find, {'$set': kwargs})

    async def get(self, projection: Dict, **kwargs) -> Dict:
        count = await self.count(**kwargs)

        if count == 1:
            collection = await self.get_collection()
            params = {'projection': projection} if projection else {}
            return await collection.find_one(kwargs, **params)

        elif count < 1:
            raise DoesNotExist('Document does not exist!')

        elif count > 1:
            raise MultipleObjectsReturned(f'Got more than 1 document - it returned {count}')

    async def find(self, **kwargs) -> Cursor:
        collection = await self.get_collection()
        return collection.find(**kwargs)

    async def delete_one(self, **kwargs) -> DeleteResult:
        collection = await self.get_collection()
        return await collection.delete_one(filter=kwargs)

    async def delete_many(self, **kwargs) -> DeleteResult:
        collection = await self.get_collection()
        return await collection.delete_many(filter=kwargs)
