from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class DatabaseManager:
    _instance = None
    _databases = []

    def __new__(cls):
        if not cls._instance:
            cls._instance = object.__new__(cls)

        return cls._instance

    def get_database(self, db_name):
        database_instance = None

        for database in self._databases:
            if database.name == db_name:
                database_instance = database

        return database_instance

    def get_client(self, host, port):
        client = None

        for database in self._databases:
            if database.client.HOST == host and database.client.PORT == port:
                client = database.client
                break

        return client

    def set_database(self, database):
        self._databases.append(database)


class MongoConnection:
    host = None
    port = None
    database = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    async def get_database(self):
        client = DatabaseManager().get_client(self.host, self.port)

        if not client:
            client = AsyncIOMotorClient(self.host, self.port)

        database = DatabaseManager().get_database(self.database)

        if not database:
            database = AsyncIOMotorDatabase(client, self.database)
            DatabaseManager().set_database(database)

        return database
