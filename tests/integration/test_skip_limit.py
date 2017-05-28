from tests.integration.models import Profile
from tests.base import BaseAsyncTestCase


class FilterConditionsTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = Profile(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = Profile(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = Profile(username='Geoff', age=18, docs=[1, 2, 4])
        self.user_4 = Profile(username='Den', age=35, docs=[2, 4])

        await self.user_1.save()
        await self.user_2.save()
        await self.user_3.save()
        await self.user_4.save()

    async def tearDown(self):
        await Profile.objects.all().delete()

    async def test_all_limit(self):
        users_all = await Profile.objects.all()

        users = await Profile.objects.all()[:2]
        self.assertEqual(len(users), 2)

        for index, user in enumerate(users):
            self.assertEqual(users_all[index]._id, user._id)

    async def test_all_skip(self):
        users_all = await Profile.objects.all()

        users = await Profile.objects.all()[2:]
        self.assertEqual(len(users), 2)

        for index, user in enumerate(users):
            index += 2
            self.assertEqual(users_all[index]._id, user._id)

    async def test_all_skip_limit(self):
        users_all = await Profile.objects.all()

        users = await Profile.objects.all()[2:1]
        self.assertEqual(len(users), 1)

        for index, user in enumerate(users):
            index += 2
            self.assertEqual(users_all[index]._id, user._id)

        users = await Profile.objects.all()[1:3]
        self.assertEqual(len(users), 3)

        for index, user in enumerate(users):
            index += 1
            self.assertEqual(users_all[index]._id, user._id)
