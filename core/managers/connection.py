from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class DatabaseManager:
    _instance = None
    _databases = []

    def __new__(cls):
        if not cls._instance:
            cls._instance = object.__new__(cls)

        return cls._instance

    @staticmethod
    def get_connection(**kwargs):
        return MongoConnection(**kwargs)

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
    username = None
    password = None
    database = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def get_client(self):
        client = DatabaseManager().get_client(self.host, self.port)

        if not client:
            client = AsyncIOMotorClient(self.host, self.port)

        return client

    async def get_database(self, client):
        database = DatabaseManager().get_database(self.database)

        if not database:
            database = AsyncIOMotorDatabase(client, self.database)
            DatabaseManager().set_database(database)

        if self.username:
            await self.auth(database)

        return database

    async def auth(self, database):
        await database.authenticate(self.username, self.password)
