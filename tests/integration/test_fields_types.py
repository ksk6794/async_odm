from datetime import datetime, timedelta
from core.base import MongoModel
from core.exceptions import ValidationError
from tests.base import BaseAsyncTestCase
from core.fields import StringField, IntegerField, ListField, DictField, FloatField, DateTimeField, BoolField


class User(MongoModel):
    username = StringField()
    age = IntegerField()
    billing = FloatField()
    addresses = ListField()
    list_subfield = ListField(StringField(max_length=3))
    data = DictField()
    registered = DateTimeField()
    is_active = BoolField()


class TestDT(MongoModel):
    test = StringField()
    dt = DateTimeField(auto_now_create=True, auto_now_update=True)


class FieldsTypesTests(BaseAsyncTestCase):
    def setUp(self):
        pass

    async def test_dt_auto_now_create(self):
        test_dt = await TestDT.objects.create()
        self.assertTrue(isinstance(test_dt.dt, datetime))
        await test_dt.delete()

    async def test_dt_auto_now_update(self):
        create_dt = datetime.now() - timedelta(hours=1)
        test_dt = await TestDT.objects.create(dt=create_dt)

        test_dt.test = 'updated'
        await test_dt.save()
        update_dt = test_dt.dt
        self.assertTrue(update_dt > create_dt)
        
        await test_dt.delete()

    async def test_type_char(self):
        user = User(username='Bill')
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.username, 'Bill')
        await user.delete()

    async def test_type_char_exception(self):
        user = User(username=7)
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_type_int(self):
        user = User(age=30)
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.age, 30)
        await user.delete()

    async def test_type_int_exception(self):
        user = User(age='30')
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_type_float(self):
        user = User(billing=7.5)
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.billing, 7.5)
        await user.delete()

    async def test_type_float_exception(self):
        user = User(billing='7.5')
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_type_list(self):
        user = User(addresses=[1, 2, 3])
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.addresses, [1, 2, 3])
        await user.delete()

    async def test_type_list_exception(self):
        user = User(addresses={})
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_type_list_sub_field(self):
        user = User(list_subfield=['abc'])
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.list_subfield, ['abc'])
        await user.delete()

    async def test_type_list_sub_field_wrong(self):
        user = User(list_subfield=['abcd'])
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_type_dict(self):
        user = User(data={'key': 'value'})
        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.data, {'key': 'value'})
        await user.delete()

    async def test_type_dict_exception(self):
        user = User(data=[])
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_datetime(self):
        user = User(registered=datetime.now())
        await user.save()

        self.assertTrue(user._id)
        self.assertTrue(isinstance(user.registered, datetime))
        await user.delete()

    async def test_datetime_exception(self):
        user = User(registered='not datetime')
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_bool(self):
        user = User(is_active=7)
        exception = False

        try:
            await user.save()
        except Exception as e:
            exception = True
            self.assertTrue(isinstance(e, ValidationError))

        self.assertTrue(exception)

    async def test_complex_types(self):
        registered = datetime.now().replace(minute=0, second=0, microsecond=0)

        user = User(username='Bill',
                    age=30,
                    billing=5000.55,
                    addresses=[1, 2, 3],
                    data={'key': 777},
                    registered=registered,
                    is_active=True)

        await user.save()

        self.assertTrue(user._id)
        self.assertEqual(user.username, 'Bill')
        self.assertEqual(user.age, 30)
        self.assertEqual(user.billing, 5000.55)
        self.assertEqual(user.addresses, [1, 2, 3])
        self.assertEqual(user.data, {'key': 777})
        self.assertEqual(user.registered, registered)
        self.assertEqual(user.is_active, True)

        await user.delete()
