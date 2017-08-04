import asyncio

from core.base import MongoModel, OnDeleteManager
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


class PostData(MongoModel):
    class Meta:
        collection_name = 'rel_post_data'

    post = OneToOne(Post, related_name='data', on_delete=CASCADE)
    content = StringField()


class Comment(MongoModel):
    class Meta:
        collection_name = 'rel_comment'

    post = ForeignKey(Post, related_name='comments', on_delete=SET_NULL)
    author = ForeignKey(User, related_name='comments', on_delete=CASCADE)
    content = StringField()


# on_delete определяет поведение потомков, при удалении родителя:
# Для модели User - Post и Comment являются потомками, для модели Post - Comment является потомком.
# При удалении пользователя, удалятся его посты и комментарии
# при удалении поста, поле `post` комментария установится в NULL


class SeveralRelationsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_some(self):
        user = await User.objects.create(username='Ivan')
        post = await Post.objects.create(author=user)

        post_data = await PostData.objects.create(post=post, content='content...')
        comment = Comment.objects.create(post=post, author=user, content='text...')

        comments = Comment.objects.all()

        n_author = await post.author
        u_comments = await n_author.comments
        n_comments = await post.comments
        p_data = await post.data

        await user.delete()
        pass
