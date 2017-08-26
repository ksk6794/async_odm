from core.fields import StringField
from tests.base import BaseAsyncTestCase
from core.base import MongoModel


class BaseUser(MongoModel):
    class Meta:
        abstract = True

    username = StringField()
    password = StringField()


class User(BaseUser):
    class Meta:
        collection_name = 'real_user'

    first_name = StringField()


class AbstractTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_abstract_inheritance(self):
        self.assertTrue(all(key in User.get_declared_fields() for key in ['username', 'password', 'first_name']))
        user = await User.objects.create(username='tim', password='123', first_name='Tim')

        self.assertEqual(user.username, 'tim')
        self.assertEqual(user.password, '123')
        self.assertEqual(user.first_name, 'Tim')

        await user.delete()
