from pymongo.errors import DuplicateKeyError

from core.exceptions import ValidationError
from core.fields import StringField, BoolField, IntegerField
from tests.base import BaseAsyncTestCase
from core.model import MongoModel


class Settings(MongoModel):
    CHOICES = (
        (1, 'test_1'),
        (2, 'test_2')
    )
    param_1 = StringField(max_length=3)
    param_2 = StringField(unique=True)
    param_3 = StringField(blank=True)
    param_4 = StringField(default=lambda: 'test')
    param_5 = IntegerField(choices=CHOICES)


class Test(MongoModel):
    param = BoolField(null=False)


class FieldsAttrsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_choices(self):
        settings = await Settings.objects.create(param_5=1)
        self.assertEqual(settings.param_5, 1)

        display = settings.get_param_5_display()
        self.assertEqual(display, 'test_1')

        await settings.delete()

    async def test_choice_wrong_foo_display(self):
        settings = await Settings.objects.create(param_5=2)
        exception = False

        try:
            settings.get_param_1_display()
        except AttributeError:
            exception = True

        self.assertTrue(exception)

        await settings.delete()

    async def test_choices_wrong_key(self):
        exception = False
        try:
            await Settings.objects.create(param_5='wrong')
        except ValidationError:
            exception = True

        self.assertTrue(exception)

    async def test_length(self):
        settings = Settings(param_1='test')
        exception = False

        try:
            await settings.save()
        except ValidationError:
            exception = True

        self.assertTrue(exception)

    async def test_unique(self):
        settings = Settings(param_2='test')
        await settings.save()
        exception = False

        try:
            settings_2 = Settings(param_2='test')
            await settings_2.save()
        except DuplicateKeyError:
            exception = True

        self.assertTrue(exception)
        await settings.delete()

    async def test_blank(self):
        settings = Settings(param_3='')
        exception = False

        try:
            await settings.save()
        except ValueError:
            exception = True

        self.assertFalse(exception)
        await settings.delete()

    async def test_default(self):
        settings = Settings()
        await settings.save()

        self.assertEqual(settings.param_4, 'test')
        await settings.delete()

    async def test_required(self):
        test = Test()
        exception = False

        try:
            await test.save()
        except ValidationError:
            exception = True

        self.assertTrue(exception)
        await test.delete()
