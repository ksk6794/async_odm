from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.exceptions import SettingsError


class DatabaseManager:
    _instance = None
    _db_settings = {}
    _databases = {}
    _clients = {}

    def __new__(cls, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        for alias, db_settings in kwargs.items():
            self._db_settings[alias] = db_settings

    def get_db_name(self, alias):
        db_settings = self._db_settings.get(alias)

        if not db_settings:
            raise SettingsError(
                f'Can\'t find settings for \'{alias}\' database! '
                f'Please, specify the \'{alias}\' database in your settings module.'
            )

        return db_settings.get('database')

    async def get_database(self, alias):
        db_settings = self._db_settings.get(alias)
        username = db_settings.get('username')
        password = db_settings.get('password')
        database = self._databases.get(alias)

        if not database:
            host = db_settings.get('host')
            port = db_settings.get('port')
            name = db_settings.get('database')
            database = AsyncIOMotorDatabase(
                client=self._get_client(host, port),
                name=name
            )
            self._databases[alias] = database

        if username:
            await database.authenticate(username, password)

        return database

    def _get_client(self, host, port):
        key = f'{host}:{port}'
        client = self._clients.get(key)

        if not client:
            client = AsyncIOMotorClient(host, port)
            self._clients[key] = client

        return client
