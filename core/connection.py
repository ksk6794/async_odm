from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoConnection:
    _database = None

    host = None
    port = None
    database = None

    @classmethod
    async def get_database(cls):
        if not cls._database:
            client = AsyncIOMotorClient(cls.host, cls.port)
            cls._database = AsyncIOMotorDatabase(client, cls.database)

        return cls._database
