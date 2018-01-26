from core.base import MongoModel
from core.fields import StringField, ForeignKey, OneToOne
from tests.base import BaseAsyncTestCase
from core.constants import CASCADE, SET_NULL


class User(MongoModel):
    class Meta:
        collection_name = 'rel_o2o_user'

    username = StringField()


class UserProfile(MongoModel):
    class Meta:
        collection_name = 'rel_o2o_user_profile'

    profile = OneToOne(User, related_name='OneToOne', on_delete=CASCADE)


class SeveralRelationsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_o2o_on_delete(self):
        user = await User.objects.create(username='Mike')
        await UserProfile.objects.create(profile=user)

        await user.delete()

        users_count = await User.objects.filter(username='Mike').count()
        self.assertEqual(users_count, 0)

        profiles_count = await UserProfile.objects.count()
        self.assertEqual(profiles_count, 0)
