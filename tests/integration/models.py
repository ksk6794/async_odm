from core.base import MongoModel
from core.fields import StringField, IntegerField, ListField, DictField


class Profile(MongoModel):
    username = StringField()
    age = IntegerField()
    docs = ListField()
    data = DictField()
