from core.base import MongoModel
from core.fields import CharField, IntegerField, ListField, DictField


class Profile(MongoModel):
    username = CharField()
    age = IntegerField()
    docs = ListField()
    data = DictField()
