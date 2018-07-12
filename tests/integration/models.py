from core.model import MongoModel
from core.fields import StringField, IntegerField, ListField, DictField


class Profile(MongoModel):
    class Meta:
        # collection_name = 'main_profile'
        sorting = ('age',)

    username = StringField()
    age = IntegerField()
    docs = ListField()
    data = DictField()
