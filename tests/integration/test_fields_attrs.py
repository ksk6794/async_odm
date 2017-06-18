from core.exceptions import ValidationError
from core.fields import StringField, BoolField
from tests.base import BaseAsyncTestCase
from core.base import MongoModel


class Settings(MongoModel):
    param_1 = StringField(max_length=3)
    param_2 = StringField(unique=True)
    param_3 = StringField(blank=True)
    param_4 = StringField(default=lambda: 'test')


class Test(MongoModel):
    param = BoolField(required=True)


class FieldsAttrsTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_length(self):
        settings = Settings(param_1='test')
        exception = False

        try:
            await settings.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_unique(self):
        settings = Settings(param_2='test')
        await settings.save()
        exception = False

        try:
            settings_2 = Settings(param_2='test')
            await settings_2.save()
        except BaseException as e:
            exception = True

        self.assertTrue(exception)
        await settings.delete()

    async def test_blank(self):
        settings = Settings(param_3='')

        try:
            await settings.save()
        except Exception as e:
            self.assertTrue(isinstance(e, ValueError))

        await settings.delete()

    async def test_default(self):
        settings = Settings()
        await settings.save()

        self.assertEqual(settings.param_4, 'test')

        await settings.delete()

    async def test_required(self):
        test = Test()

        try:
            await test.save()
        except Exception as e:
            self.assertTrue(isinstance(e, ValidationError))

        await test.delete()
