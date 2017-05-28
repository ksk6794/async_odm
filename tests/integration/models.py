from core.base import MongoModel
from core.fields import CharField, IntegerField, ListField, DictField
from tests.integration.test_connection import TestConnection


class Profile(MongoModel):
    username = CharField()
    age = IntegerField()
    docs = ListField()
    data = DictField()
