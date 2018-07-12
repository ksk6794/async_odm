from core.model import MongoModel
from core.fields import StringField, OneToOne
from tests.base import BaseAsyncTestCase
from core.constants import CASCADE, SET_NULL


class User(MongoModel):
    class Meta:
        collection_name = 'rel_o2o_user'

    username = StringField()


class UserProfile(MongoModel):
    class Meta:
        collection_name = 'rel_o2o_user_profile'

    user = OneToOne(User, related_name='profile', on_delete=CASCADE)


class Address(MongoModel):
    class Meta:
        collection_name = 'rel_o2o_address'

    user = OneToOne(User, related_name='address', on_delete=SET_NULL)
    data = StringField()


class SeveralRelationsTests(BaseAsyncTestCase):
    async def test_o2o_on_delete(self):
        user = await User.objects.create(username='Mike')
        await UserProfile.objects.create(user=user)
        await Address.objects.create(user=user, data='text...')

        await user.delete()

        users_count = await User.objects.filter(username='Mike').count()
        self.assertEqual(users_count, 0)

        profiles_count = await UserProfile.objects.count()
        self.assertEqual(profiles_count, 0)

        address = await Address.objects.get(data='text...')
        self.assertIsNone(address.user)
        await address.delete()
