from pymongo.errors import DuplicateKeyError

from core.model import MongoModel
from core.fields import StringField, OneToOne
from tests.base import BaseAsyncTestCase


class UserTest(MongoModel):
    username = StringField()
    profile = OneToOne('ProfileTest', related_name='user')


class ProfileTest(MongoModel):
    position = StringField()


class ToQueryConditionsTests(BaseAsyncTestCase):
    async def setUp(self):
        pass

    async def test_save_one_to_one(self):
        profile = ProfileTest(position='test_position')
        await profile.save()

        user = UserTest(username='Vasya', profile=profile)
        await user.save()

        profile = await user.profile
        user = await profile.user
        self.assertEqual(user.username, 'Vasya')

        exception = False

        try:
            user_2 = UserTest(username='Vasya2', profile=profile)
            await user_2.save()
        except DuplicateKeyError:
            exception = True

        self.assertTrue(exception)

    async def test_w(self):
        profile = await ProfileTest.objects.create(position='test_position')
        user = await UserTest.objects.create(username='Vasya', profile=profile)

        profile_2 = await ProfileTest.objects.create(position='test_position_2')
        user_2 = await UserTest.objects.create(username='Petya', profile=profile_2)

        profile = await user.profile
        self.assertEqual(profile.position, 'test_position')

        profile_2 = await user_2.profile
        self.assertEqual(profile_2.position, 'test_position_2')

        await ProfileTest.objects.delete()
        await UserTest.objects.delete()
