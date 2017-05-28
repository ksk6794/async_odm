from tests.integration.models import Profile
from tests.base import BaseAsyncTestCase


class FilterConditionsTests(BaseAsyncTestCase):
    async def setUp(self):
        self.user_1 = Profile(username='Ivan', age=30, docs=[1, 2])
        self.user_2 = Profile(username='Peter', age=20, docs=[1, 2, 3, 4])
        self.user_3 = Profile(username='Geoff', age=18, docs=[1, 2, 4])

        await self.user_1.save()
        await self.user_2.save()
        await self.user_3.save()

    async def tearDown(self):
        await Profile.objects.all().delete()

    async def test_all_username_sort_asc(self):
        users = await Profile.objects.all().sort('username')
        usernames_ordering = ('Geoff', 'Ivan', 'Peter')

        for index, username in enumerate(usernames_ordering):
            self.assertEqual(users[index].username, username)

    async def test_all_username_sort_desc(self):
        users = await Profile.objects.all().sort('-username')
        usernames_ordering = ('Peter', 'Ivan', 'Geoff')

        for index, username in enumerate(usernames_ordering):
            self.assertEqual(users[index].username, username)

    async def test_all_age_sort_asc(self):
        users = await Profile.objects.all().sort('age')
        ages_ordering = (18, 20, 30)

        for index, age in enumerate(ages_ordering):
            self.assertEqual(users[index].age, age)

    async def test_all_age_sort_desc(self):
        users = await Profile.objects.all().sort('-age')
        ages_ordering = (30, 20, 18)

        for index, age in enumerate(ages_ordering):
            self.assertEqual(users[index].age, age)
