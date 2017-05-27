from core.connection import MongoConnection


class TestConnection(MongoConnection):
    host = 'localhost'
    port = 27017
    database = 'async_odm'
