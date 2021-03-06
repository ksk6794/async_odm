from core.base import MongoModel
from core.fields import StringField, IntegerField, ListField, DictField
from tests.base import BaseAsyncTestCase


class Profile(MongoModel):
    class Meta:
        collection_name = 'test_profile'

    username = StringField()
    age = IntegerField()
    docs = ListField()
    data = DictField()


class QuerySetExcludeTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = await Profile.objects.create(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = await Profile.objects.create(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = await Profile.objects.create(username='Geoff', age=18, docs=[1, 2, 4])

    async def tearDown(self):
        await Profile.objects.all().delete()

    async def test_exclude_gt(self):
        users = await Profile.objects.exclude(age__gt=25)

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (18, 20))
        self.assertIn(users[1].age, (18, 20))

    async def test_exclude_gte(self):
        users = await Profile.objects.exclude(age__gte=20)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 18)

    async def test_exclude_lt(self):
        users = await Profile.objects.exclude(age__lt=20)

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (20, 30))
        self.assertIn(users[1].age, (20, 30))

    async def test_exclude_lte(self):
        users = await Profile.objects.exclude(age__lte=30)
        self.assertEqual(len(users), 0)

    async def test_exclude_lt_gt(self):
        users = await Profile.objects.exclude(age__lt=30, age__gt=18)

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (18, 30))
        self.assertIn(users[1].age, (18, 30))

    async def test_exclude_in(self):
        users = await Profile.objects.exclude(age__in=[20, 18])

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 30)

    async def test_exclude_all(self):
        users_query = Profile.objects.exclude(docs__all=[2, 4])
        users = []

        async for user in users_query:
            users.append(user)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, 'Ivan')

        users_query = Profile.objects.exclude(docs__all=[1, 2])
        users = []

        async for user in users_query:
            users.append(user)

        self.assertEqual(len(users), 0)

    async def test_multiple_exclude(self):
        users = await Profile.objects.exclude(age=20).exclude(username='Peter')

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (18, 30))
        self.assertIn(users[1].age, (18, 30))

        users = await Profile.objects.exclude(age=20).exclude(username='Ivan').exclude(docs=[1, 2, 4])
        self.assertEqual(len(users), 0)
