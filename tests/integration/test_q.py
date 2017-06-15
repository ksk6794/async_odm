from core.node import Q
from tests.base import BaseAsyncTestCase
from tests.integration.models import Profile


class QConditionsTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = Profile(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = Profile(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = Profile(username='Geoff', age=18, docs=[1, 2, 4])
        await self.user_1.save()
        await self.user_2.save()
        await self.user_3.save()

    async def tearDown(self):
        await Profile.objects.all().delete()

    async def test_filter_q_and(self):
        users = await Profile.objects.filter(Q(age=30) & Q(username='Ivan'))
        self.assertEqual(len(users), 1)

    async def test_exclude_invert_q_and(self):
        users = await Profile.objects.exclude(~Q(age=30) & ~Q(username='Ivan'))
        self.assertEqual(len(users), 1)

    async def test_exclude_invert_q_and_or(self):
        users_count = await Profile.objects.exclude(~Q(age=30) & ~Q(username='Ivan') & Q(docs=[1, 2])).count()
        self.assertEqual(users_count, 0)

    async def test_exclude_invert_q_single(self):
        users = await Profile.objects.exclude(~Q(age=30))
        self.assertEqual(len(users), 1)

    async def test_filter_q_or(self):
        users = await Profile.objects.filter(Q(age=20) | Q(username='Ivan'))
        self.assertEqual(len(users), 2)

    async def test_filter_q_or_count(self):
        users_count = await Profile.objects.filter(Q(age=20) | Q(username='Ivan')).count()
        self.assertEqual(users_count, 2)

    async def test_filter_invert_q_and(self):
        users = await Profile.objects.filter(~Q(age=20) & ~Q(username='Ivan'))

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 18)

    async def test_exclude_invert_combination(self):
        users = await Profile.objects.exclude(~(Q(age=20) | Q(username='Ivan')) & Q(age=18))

        expected_ages = (20, 30)

        self.assertEqual(len(users), 2)

        self.assertIn(users[0].age, expected_ages)
        self.assertIn(users[1].age, expected_ages)

    async def test_exclude_invert_combination_invert_q(self):
        users = await Profile.objects.exclude(~(~Q(age=20) | Q(username='Ivan')))

        expected_ages = (18, 30)

        self.assertEqual(len(users), 2)
        self.assertIn(users[0].age, expected_ages)
        self.assertIn(users[1].age, expected_ages)

    async def test_filter_invert_q_or(self):
        users = await Profile.objects.filter(~Q(age=20) | ~Q(username='Ivan'))
        self.assertEqual(len(users), 3)

    async def test_filter_q_or_and(self):
        users = await Profile.objects.filter((Q(username='Ivan') | Q(username='Peter')) & Q(age__gte=20))

        expected_ages = (20, 30)

        self.assertEqual(len(users), 2)

        self.assertIn(users[0].age, expected_ages)
        self.assertIn(users[1].age, expected_ages)

    async def test_exclude_q_or_and(self):
        users = await Profile.objects.exclude((Q(username='Ivan') | Q(username='Peter')) & ~Q(age=18))
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 18)

    async def test_exclude_single_q(self):
        users = await Profile.objects.exclude(Q(username='Ivan'))
        self.assertEqual(len(users), 2)

    async def test_exclude_single_invert_q(self):
        users = await Profile.objects.exclude(~Q(username='Ivan'))
        self.assertEqual(len(users), 1)
