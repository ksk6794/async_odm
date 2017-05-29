from uuid import uuid4
from core.base import MongoModel
from tests.integration.test_connection import TestConnection
from core.fields import CharField, IntegerField, FloatField, ListField, DictField, DateTimeField, ForeignKey


class Post(MongoModel):
    class Meta:
        collection_name = 'post'

    title = CharField()
    author = ForeignKey('Author', related_name='posts', null=False)
    published = DateTimeField(null=True)


class Author(MongoModel):
    username = CharField(length=10, null=True)
    age = IntegerField(null=True)
    billing = FloatField(null=True)
    documents = ListField(null=True)
    data = DictField(null=True) 


class Name(MongoModel):
    class Meta:
        connection = TestConnection
        collection_name = 'name_collection'

    name = CharField(unique=True, default=uuid4)

    @staticmethod
    def validate_name(value):
        if value and value.isdigit():
            value = 'number'

        return value
