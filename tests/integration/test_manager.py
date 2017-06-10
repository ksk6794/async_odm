from core.base import MongoModel
from core.fields import StringField
from tests.base import BaseAsyncTestCase


class Folder(MongoModel):
    name = StringField()


class QueryManagerTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_save(self):
        folder = Folder(name='test')
        await folder.save()

        name = await Folder.objects.get(name='test')
        self.assertTrue(name._id)
        self.assertEqual(name.name, 'test')

        await name.delete()

    async def test_save_undeclared_field(self):
        folder = Folder(name='test', test='test')
        await folder.save()

        folder = await Folder.objects.get(name='test')
        self.assertEqual(folder.test, 'test')

        await folder.delete()

    async def test_update_undeclared_field(self):
        folder = Folder(name='test', test='test')
        await folder.save()

        folder = await Folder.objects.get(name='test')
        folder.test = 'test2'
        await folder.save()
        self.assertEqual(folder.test, 'test2')

        await folder.delete()

    async def test_get(self):
        folder_1 = Folder(name='movies')
        await folder_1.save()

        folder_2 = Folder(name='music')
        await folder_2.save()

        self.assertEqual(folder_1.name, 'movies')
        self.assertEqual(folder_2.name, 'music')

        folder_1 = await Folder.objects.get(name='movies')
        folder_2 = await Folder.objects.get(name='music')

        self.assertEqual(folder_1.name, 'movies')
        self.assertEqual(folder_2.name, 'music')

        await folder_1.delete()
        await folder_2.delete()

    async def test_delete(self):
        folder = Folder(name='test')
        await folder.save()

        folder = await Folder.objects.get(name='test')
        self.assertTrue(folder._id)
        self.assertEqual(folder.name, 'test')

        await folder.delete()

        try:
            await Folder.objects.get(name='test')
        except Exception as e:
            self.assertTrue(isinstance(e, Exception))

        names = await Folder.objects.filter(name='test')
        self.assertEqual(names, [])
