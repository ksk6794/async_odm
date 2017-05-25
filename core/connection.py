from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoDBConnection:
    _instance = None

    client = None
    database = None

    mongodb_host = 'localhost'
    mongodb_port = 27017
    mongodb_database = 'async_odm'

    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = object.__new__(cls)
            cls._instance.client = await cls.get_client(cls._instance)
            cls._instance.database = await cls.get_database(cls._instance)

        return cls._instance

    async def get_client(self):
        return AsyncIOMotorClient(self.mongodb_host, self.mongodb_port)

    async def get_database(self):
        return AsyncIOMotorDatabase(self.client, self.mongodb_database)
