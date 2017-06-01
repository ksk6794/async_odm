from .exceptions import DoesNotExist, MultipleObjectsReturned


class MongoDispatcher:
    def __init__(self, connection, collection_name):
        self.connection = connection
        self.collection_name = collection_name

    async def count(self, **kwargs):
        collection = await self._get_collection()
        count = await collection.count(kwargs)

        return count

    async def _get_collection(self):
        # TODO: Disallow conflicting collection names ('name', ...)
        database = await self.connection.get_database()
        collection = getattr(database, self.collection_name)

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
            raise DoesNotExist('Document does not exists!')

        elif count > 1:
            raise MultipleObjectsReturned('Got more than 1 document - it returned {count}'.format(count=count))

    async def find(self, **kwargs):
        collection = await self._get_collection()

        # TODO: Move check and processing to DocumentsManager
        available_params = {
            'filter': dict,
            'sort': list,
            'limit': int,
            'skip': int
        }
        params = {}
        for param_name, param_type in available_params.items():
            param_value = kwargs.get(param_name)

            if isinstance(param_value, param_type):
                params[param_name] = param_value

        cursor = collection.find(**params)

        # async for document in cursor:
        #     documents.append(document)

        return cursor

    async def delete_one(self, _id):
        collection = await self._get_collection()
        result = await collection.delete_one(filter={'_id': _id})

        return result

    async def delete_many(self, **kwargs):
        collection = await self._get_collection()
        result = await collection.delete_many(filter=kwargs)

        return result
