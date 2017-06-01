from datetime import datetime
from core.dispatchers import MongoDispatcher
from core.fields import CharField, ForeignKey
from tests.base import BaseAsyncTestCase
from tests.models import Author, Post, Name


class IntegrationTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_auto_model_name(self):
        user = Author()

        self.assertEqual(user._dispatcher.collection_name, 'author')

    async def test_model_instance(self):
        name = Name(name='Bob')

        self.assertTrue(isinstance(name._dispatcher, MongoDispatcher))
        self.assertEqual(name._dispatcher.collection_name, 'name_collection')
        self.assertEqual(len(name._declared_fields), 1)
        self.assertTrue(isinstance(name._declared_fields.get('name'), CharField))

        # TODO: В поле name, в _value попадает значение с других тестов.
        # TODO Это не критично и переписывается при сохранении, но все-же лучше поправить!
        # self.assertEqual(name._declared_fields.get('name')._value, 'Bob')

    async def test_save(self):
        name = Name(name='test')
        await name.save()

        name = await Name.objects.get(name='test')
        self.assertTrue(name._id)
        self.assertEqual(name.name, 'test')

        await name.delete()

    async def test_update_unique_field(self):
        exception = False
        name = Name(name='test')
        await name.save()
        name.name = 'test'

        try:
            await name.save()
        except BaseException:
            exception = True

        self.assertEqual(exception, False)

        await name.delete()

    async def test_get(self):
        name_1 = Name(name='Ivan')
        await name_1.save()

        name_2 = Name(name='Peter')
        await name_2.save()

        self.assertEqual(name_1.name, 'Ivan')
        self.assertEqual(name_2.name, 'Peter')

        name_1 = await Name.objects.get(name='Ivan')
        name_2 = await Name.objects.get(name='Peter')

        self.assertEqual(name_1.name, 'Ivan')
        self.assertEqual(name_2.name, 'Peter')

        await name_1.delete()
        await name_2.delete()

    async def test_delete(self):
        name = Name(name='test')
        await name.save()

        name = await Name.objects.get(name='test')
        self.assertTrue(name._id)
        self.assertEqual(name.name, 'test')

        await name.delete()

        try:
            await Name.objects.get(name='test')
        except Exception as e:
            self.assertTrue(isinstance(e, Exception))

        names = await Name.objects.filter(name='test')
        self.assertEqual(names, [])

    async def test_get_by_foreignkey_instance(self):
        user = Author(username='Frank')
        await user.save()

        post = Post(title='News', author=user, published=datetime.now())
        await post.save()

        post = await Post.objects.get(title='News', author=user)

        # TODO: Test it!
        # posts = []
        # async for post in user.posts:
        #     posts.append(post)

        self.assertEqual(post.title, 'News')

        await user.delete()
        await post.delete()

    async def test_filter_by_foreignkey_instance(self):
        user = Author(username='Frank')
        await user.save()

        post = Post(title='News', author=user, published=datetime.now())
        await post.save()

        posts = await Post.objects.filter(title='News', author=user)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].title, 'News')

        await user.delete()
        await post.delete()

    async def test_filter_count(self):
        user = Author(username='Frank')
        await user.save()

        users_count = await Author.objects.filter(username='Frank').count()

        self.assertEqual(users_count, 1)

        await user.delete()

    async def test_all_count(self):
        user_1 = Author(username='Frank')
        await user_1.save()

        user_2 = Author(username='Bill')
        await user_2.save()

        users_count = await Author.objects.all().count()

        self.assertEqual(users_count, 2)

        await user_1.delete()
        await user_2.delete()

    async def test_count(self):
        user = Author(username='Frank')
        await user.save()

        users_count = await Author.objects.count()

        self.assertEqual(users_count, 1)

        await user.delete()

    async def test_foreignkey(self):
        user = Author(username='Frank')
        await user.save()

        post = Post(title='News', author=user)
        await post.save()

        author = await post.author

        self.assertTrue(isinstance(post.author, ForeignKey))
        self.assertEqual(author.username, 'Frank')

        await post.delete()
        await author.delete()

    async def test_foreignkey_null(self):
        post = Post(title='News')

        try:
            await post.save()
        except Exception as e:
            self.assertTrue(isinstance(e, ValueError))

        await post.delete()

    async def test_foreignkey_backward(self):
        user = Author(username='Frank')
        await user.save()

        post_1 = Post(title='News', author=user)
        post_2 = Post(title='News 2', author=user)
        await post_1.save()
        await post_2.save()

        posts = await user.posts

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]._id, post_1._id)
        self.assertEqual(posts[1]._id, post_2._id)

        await post_1.delete()
        await post_2.delete()
        await user.delete()

    async def test_validate_field(self):
        name = Name(name='123')
        await name.save()

        self.assertEqual(name.name, 'number')

        await name.delete()
