from core.connection import MongoDBConnection


class MongoDispatcher:
    def __init__(self, collection_name):
        self.collection_name = collection_name

    async def count(self, **kwargs):
        collection = await self._get_collection()
        count = await collection.count(kwargs)

        return count

    async def _get_collection(self):
        # TODO: Disallow conflicting collection names ('name', ...)
        mongodb_connection = await MongoDBConnection.get_instance()
        collection = getattr(mongodb_connection.database, self.collection_name)

        return collection

    async def create(self, **kwargs):
        document = kwargs
        collection = await self._get_collection()
        insert_result = await collection.insert_one(document)

        document = None

        if insert_result:
            document = await self.get(_id=insert_result.inserted_id)

        return document

    async def update(self, _id, **kwargs):
        collection = await self._get_collection()
        document = await collection.find_and_modify(query={'_id': _id}, update=kwargs)

        return document

    async def get(self, **kwargs):
        count = await self.count(**kwargs)

        if count == 1:
            collection = await self._get_collection()
            document = await collection.find_one(kwargs)

            return document

        elif count < 1:
            raise Exception('Document does not exists!')

        elif count > 1:
            raise Exception('Got more than 1 document!')

    async def find(self, **kwargs):
        collection = await self._get_collection()
        cursor = collection.find(kwargs)
        documents = []

        while await cursor.fetch_next:
            documents.append(cursor.next_object())

        return documents

    async def delete(self, _id):
        collection = await self._get_collection()
        result = await collection.delete_one(filter={'_id': _id})

        return result
