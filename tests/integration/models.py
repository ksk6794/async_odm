from core.base import MongoModel
from core.fields import StringField, IntegerField, ListField, DictField


class Profile(MongoModel):
    class Meta:
        sorting = ('age',)

    username = StringField()
    age = IntegerField()
    docs = ListField()
    data = DictField()
