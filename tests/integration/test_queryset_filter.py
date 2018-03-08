from core.exceptions import QuerysetError
from tests.integration.models import Profile
from tests.base import BaseAsyncTestCase


class QuerySetFilterTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = Profile(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = Profile(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = Profile(username='Geoff', age=18, docs=[1, 2, 4])

        await self.user_1.save()
        await self.user_2.save()
        await self.user_3.save()

    async def tearDown(self):
        await Profile.objects.all().delete()

    async def test_filter_gt(self):
        users = await Profile.objects.filter(age__gt=25)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, 'Ivan')

    async def test_filter_gte(self):
        users = await Profile.objects.filter(age__gte=20)
        self.assertEqual(len(users), 2)

    async def test_filter_lt(self):
        users = await Profile.objects.filter(age__lt=20)
        self.assertEqual(len(users), 1)

    async def test_filter_lte(self):
        users = await Profile.objects.filter(age__lte=30)
        self.assertEqual(len(users), 3)

    async def test_filter_lt_gt(self):
        users = await Profile.objects.filter(age__lt=30, age__gt=18)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 20)

    async def test_filter_in(self):
        users = await Profile.objects.filter(age__in=[20, 18])

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (18, 20))
        self.assertIn(users[1].age, (18, 20))

    async def test_filter_all(self):
        users = await Profile.objects.filter(docs__all=[1, 2])
        self.assertEqual(len(users), 3)

        users = await Profile.objects.filter(docs__all=[3])
        self.assertEqual(len(users), 1)

    async def test_multiple_filter(self):
        users = await Profile.objects.filter(age=20).filter(username='Peter')
        self.assertEqual(len(users), 1)

        users = await Profile.objects.filter(age=20).filter(username='Ivan')
        self.assertEqual(len(users), 0)

    async def test_filter_wrong_condition(self):
        exception = False

        try:
            await Profile.objects.filter(age__ggg=50)
        except QuerysetError:
            exception = True

        self.assertTrue(exception)
