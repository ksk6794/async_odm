from core.node import Q
from tests.base import BaseAsyncTestCase
from tests.integration.models import Profile


class ToQueryConditionsTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = Profile(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = Profile(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = Profile(username='Geoff', age=18, docs=[1, 2, 4])
        await self.user_1.save()
        await self.user_2.save()
        await self.user_3.save()

    async def tearDown(self):
        await self.user_1.delete()
        await self.user_2.delete()
        await self.user_3.delete()

    async def test_to_query_q_or(self):
        users = await Profile.objects.q_query(Q(age=20) | Q(username='Ivan'))
        self.assertEqual(len(users), 2)

    async def test_filter_q_or_count(self):
        users_count = await Profile.objects.q_query(Q(age=20) | Q(username='Ivan')).count()
        self.assertEqual(users_count, 2)

    async def test_to_query_invert_q_and(self):
        users = await Profile.objects.q_query(~Q(age=20) & ~Q(username='Ivan'))

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 18)

    async def test_to_query_invert_q_or(self):
        users = await Profile.objects.q_query(~Q(age=20) | ~Q(username='Ivan'))
        self.assertEqual(len(users), 3)

    async def test_to_query_q_or_and(self):
        users = await Profile.objects.q_query((Q(username='Ivan') | Q(username='Peter')) & Q(age__gte=20))
        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, (20, 30))
        self.assertIn(users[1].age, (20, 30))
