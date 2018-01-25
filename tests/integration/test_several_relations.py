from core.base import MongoModel
from core.fields import StringField, ForeignKey, OneToOne
from tests.base import BaseAsyncTestCase
from core.constants import CASCADE, SET_NULL


class User(MongoModel):
    class Meta:
        collection_name = 'rel_user'

    username = StringField()


class Post(MongoModel):
    class Meta:
        collection_name = 'rel_post'

    author = ForeignKey(User, related_name='posts', on_delete=CASCADE)


class Comment(MongoModel):
    class Meta:
        collection_name = 'rel_comment'

    post = ForeignKey(Post, related_name='comments', on_delete=SET_NULL)
    author = ForeignKey(User, related_name='comments', on_delete=SET_NULL)
    content = StringField()


# on_delete определяет поведение потомков, при удалении родителя:
# Для модели User - Post и Comment являются потомками, для модели Post - Comment является потомком.
# При удалении пользователя, удалятся его посты и комментарии
# при удалении поста, поле `post` комментария установится в NULL


class SeveralRelationsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_on_delete_cascade(self):
        user = await User.objects.create(username='Mike')
        post = await Post.objects.create(author=user)
        await Comment.objects.create(post=post, author=user, content='text...')

        await user.delete()

        # При удалении пользователя должны удалиться всего посты, а автор у комментариев установится в null.
        users_count = await User.objects.filter(username='Mike').count()
        self.assertEqual(users_count, 0)

        posts_count = await Post.objects.count()
        self.assertEqual(posts_count, 0)

        comment = await Comment.objects.get(content='text...')
        # TODO: Fix the await null Rel
        await comment.post
        await comment.author
        await comment.delete()


    # async def test_some(self):
    #     user = await User.objects.create(username='Ivan')
    #     post = await Post.objects.create(author=user)
    #
    #     comment = await Comment.objects.create(post=post, author=user, content='text...')
    #
    #     comments = await Comment.objects.all()
    #     n_author = await post.author
    #     u_comments = await n_author.comments
    #     n_comments = await post.comments
    #     p_data = await post.data
    #
    #     await user.delete()
    #     pass
