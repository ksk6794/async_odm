from uuid import uuid4
from pymongo import DESCENDING, ASCENDING
from core.base import MongoModel
from core.fields import StringField, IntegerField, FloatField, ListField, DictField, DateTimeField, ForeignKey
from core.index import Index


class Post(MongoModel):
    class Meta:
        collection_name = 'post'
        # indexes = (
        #     Index((('name', DESCENDING), ('author', DESCENDING)), unique=False),
        #     Index((('author', DESCENDING), ('published', ASCENDING)), unique=True)
        # )

    title = StringField()
    author = ForeignKey('Author', related_name='posts', null=False)
    published = DateTimeField(null=True)


class Author(MongoModel):
    username = StringField(max_length=10, null=True)
    age = IntegerField(null=True)
    billing = FloatField(null=True)
    documents = ListField(null=True)
    data = DictField(null=True)


class Name(MongoModel):
    class Meta:
        collection_name = 'name_collection'

    name = StringField(unique=True, index=DESCENDING, default=uuid4)

    @staticmethod
    def validate_name(value):
        if value and value.isdigit():
            value = 'number'

        return value
