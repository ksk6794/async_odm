from core.model import MongoModel
from core.fields import StringField, ListField
from tests.base import BaseAsyncTestCase


class User(MongoModel):
    class Meta:
        collection_name = 'user_test_1'

    username = StringField()
    email = StringField()
    numbers = ListField()


class QuerysetFieldsDeferOnlyTests(BaseAsyncTestCase):
    async def setUp(self):
        self.username = 'Ivan'
        self.email = 'ivan@test.com'
        self.numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        self.user = await User.objects.create(
            username=self.username,
            email=self.email,
            numbers=self.numbers
        )

    async def tearDown(self):
        await self.user.delete()

    async def test_get_defer(self):
        user = await User.objects.defer('numbers').get(email=self.email)
        self.assertEqual(user.username, 'Ivan')
        self.assertEqual(user.email, 'ivan@test.com')
        self.assertEqual(hasattr(user, 'numbers'), False)

    async def test_get_only(self):
        user = await User.objects.only('numbers').get(email=self.email)
        self.assertEqual(hasattr(user, 'username'), False)
        self.assertEqual(hasattr(user, 'email'), False)
        self.assertEqual(user.numbers, self.numbers)

    async def test_get_fields_defer(self):
        user = await User.objects.fields(numbers=False).get(email=self.email)
        self.assertEqual(user.username, 'Ivan')
        self.assertEqual(user.email, 'ivan@test.com')
        self.assertEqual(hasattr(user, 'numbers'), False)

    async def test_get_fields_only(self):
        user = await User.objects.fields(numbers=True).get(email=self.email)
        self.assertEqual(hasattr(user, 'username'), False)
        self.assertEqual(hasattr(user, 'email'), False)
        self.assertEqual(user.numbers, self.numbers)

    async def test_get_fields_slice_first_n_items(self):
        user = await User.objects.fields(numbers__slice=5).get(email=self.email)
        self.assertEqual(len(user.numbers), 5)

    async def test_get_get_slice(self):
        user = await User.objects.fields(numbers__slice=(5, 10)).get(email=self.email)
        self.assertEqual(len(user.numbers), 5)

    async def test_filter_defer(self):
        users = await User.objects.filter(email=self.email).defer('email')
        self.assertEqual(users[0].username, 'Ivan')
        self.assertEqual(hasattr(users[0], 'email'), False)
        self.assertEqual(users[0].numbers, self.numbers)

    async def test_filter_only(self):
        users = await User.objects.filter(email=self.email).only('email')
        self.assertEqual(hasattr(users[0], 'username'), False)
        self.assertEqual(users[0].email, 'ivan@test.com')
        self.assertEqual(hasattr(users[0], 'numbers'), False)
