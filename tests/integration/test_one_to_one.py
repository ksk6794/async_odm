from core.base import MongoModel
from core.fields import CharField, OneToOne
from tests.base import BaseAsyncTestCase
from tests.integration.test_connection import TestConnection


class UserTest(MongoModel):
    class Meta:
        connection = TestConnection

    username = CharField()
    profile = OneToOne('ProfileTest', related_name='user')


class ProfileTest(MongoModel):
    class Meta:
        connection = TestConnection

    position = CharField()


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

        exception = False

        try:
            user_2 = UserTest(username='Vasya2', profile=profile)
            await user_2.save()
        except BaseException:
            exception = True

        self.assertTrue(exception)
