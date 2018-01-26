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


class SeveralRelationsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_fk_on_delete_cascade(self):
        """
        The `on_delete` parameter specifies the behavior of the children when the parent is deleted:
        For the User model, Post and Comment are children.
        For the Post, Comment model is a child.
        When deleting a user: his posts will be deleted, the `author` field of his comments will set to null.
        When deleting a post, the `post` field of comments will set to null.
        """
        user = await User.objects.create(username='Mike')
        post = await Post.objects.create(author=user)
        await Comment.objects.create(post=post, author=user, content='text...')

        await user.delete()

        # The user must be deleted
        users_count = await User.objects.filter(username='Mike').count()
        self.assertEqual(users_count, 0)

        # All user's posts must be deleted
        posts_count = await Post.objects.count()
        self.assertEqual(posts_count, 0)

        # All user's comments must remain in the database
        comment = await Comment.objects.get(content='text...')

        # When referring to indefinite FK fields
        self.assertIsNone(comment.post)
        self.assertIsNone(comment.author)

        await comment.delete()

