from datetime import datetime


class Field:
    """
    Base class of any field.
    """
    type = None
    _model_instance = None
    _dispatcher = None
    _name = None
    _value = None
    _reserved_attributes = {
        'null': bool,
        'blank': bool,
        'length': int,
        'unique': bool,
    }

    def __setattr__(self, key, value):
        if key in self._reserved_attributes:
            required_type = self._reserved_attributes.get(key)

            if value is not None and not isinstance(value, required_type):
                exception = 'Reserved attr `{attr_name}` has wrong type! ' \
                            'Expected `{attr_type}`'.format(
                                attr_name=key,
                                attr_type=required_type.__name__
                            )
                raise TypeError(exception)

        super().__setattr__(key, value)

    def __len__(self):
        return len(self._value)

    async def validate(self):
        if self._dispatcher and self._name:
            null = getattr(self, 'null', True) or True
            blank = getattr(self, 'blank', True) or True
            length = getattr(self, 'length', None)
            unique = getattr(self, 'unique', False) or False
            default = getattr(self, 'default', None)

            if default is not None and not self._value:
                # If the `default` attribute is a callable object.
                self._value = default() if callable(default) else default

            if self._value is not None:
                if self.type and not isinstance(self._value, self.type):
                    exception = 'Field `{field_name} has wrong type! ' \
                                'Expected {field_type}`'.format(
                                    field_name=self._name,
                                    field_type=self.type.__name__
                                )
                    raise TypeError(exception)

                if length:
                    if hasattr(self._value, '__len__'):
                        if len(self._value) > length:
                            exception = 'Field `{field_name}` exceeds the length {length}'.format(
                                field_name=self._name,
                                length=length
                            )
                            raise ValueError(exception)
                    else:
                        exception = 'Cannot count the length of the field `{field_name}`.' \
                                    'Define the __len__ method'.format(
                                        field_name=self._name,
                                        length=length
                                    )
                        raise ValueError(exception)
            else:
                if null is False and self._value is None:
                    exception = 'Field `{field_name}` can not be null'.format(
                        field_name=self._name
                    )
                    raise ValueError(exception)

                if blank is False and self._value == '':
                    exception = 'Field `{field_name}` can not be blank'.format(
                        field_name=self._name
                    )
                    raise ValueError(exception)

            if unique:
                # TODO: In the future, remove this and implement it in migrations using unique indexes.
                object_id = self._model_instance.get_object_id()
                filter_kwargs = {self._name: self._value} if not isinstance(self, OneToOne) else {self._name: self._value.id}
                exclude_kwargs = {'_id': object_id} if object_id else {}

                count = await self._model_instance.objects.filter(**filter_kwargs).exclude(**exclude_kwargs).count()

                if count > 0:
                    exception = 'Field `{field_name}` with value `{field_value}` already exists'.format(
                        field_name=self._name,
                        field_value=self._value
                    )
                    raise ValueError(exception)

        return self._value

    @staticmethod
    def to_internal_value(value):
        """
        Define this method if you need to save specific data format.
        Here you must to serialize your data.
        """
        return value

    @staticmethod
    def to_external_value(value):
        """
        Define this method if you specified `to_internal_value`,
        to represent data from the storage.
        Here you must to deserialize your data.
        """
        return value


class BoolField(Field):
    type = bool

    def __init__(self, null=None, default=None):
        self.null, self.default = null, default


class StringField(Field):
    type = str

    def __init__(self, null=None, blank=None, length=None, unique=None, default=None):
        self.null, self.blank, self.length, self.unique, self.default = null, blank, length, unique, default


class IntegerField(Field):
    type = int

    def __init__(self, null=None, unique=None, default=None):
        self.null, self.unique, self.default = null, unique, default


class FloatField(Field):
    type = float

    def __init__(self, null=True, unique=False, default=None):
        self.null, self.unique, self.default = null, unique, default


class ListField(Field):
    type = list

    def __init__(self, null=True, length=None, unique=False, default=None):
        self.null, self.length, self.unique, self.default = null, length, unique, default

    # For IDE tips
    def __iter__(self):
        return self


class DictField(Field):
    type = dict

    def __init__(self, null=True, unique=False, length=None, default=None):
        self.null, self.unique, self.length, self.default = null, unique, length, default

    # For IDE tips
    def __iter__(self):
        return self


class DateTimeField(Field):
    type = datetime

    def __init__(self, null=True):
        self.null = null


class BaseRelationField(Field):
    backward_class = None
    _query = None

    def _get_query(self):
        raise NotImplementedError

    def __init__(self, relation, related_name=None, null=True):
        self.relation, self.related_name, self.null = relation, related_name, null

    async def __aiter__(self):
        return self

    # TODO: Test it!
    async def __anext__(self):
        async for item in self._get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self):
        return self._get_query().__await__()


class BaseBackwardRelationField(Field):
    _query = None

    def _get_query(self):
        raise NotImplementedError

    def __init__(self, relation):
        self.relation = relation

    async def __aiter__(self):
        return self

    async def __anext__(self):
        async for item in self._get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self):
        return self._get_query().__await__()


class _ForeignKeyBackward(BaseBackwardRelationField):
    def _get_query(self):
        if not self._query:
            filter_kwargs = {self._name: self._value}
            self._query = self.relation.objects.filter(**filter_kwargs)

        return self._query


class _OneToOneBackward(BaseBackwardRelationField):
    def _get_query(self):
        if not self._query:
            filter_kwargs = {self._name: self._value}
            self._query = self.relation.objects.get(**filter_kwargs)

        return self._query


class ForeignKey(BaseRelationField):
    backward_class = _ForeignKeyBackward

    def _get_query(self):
        if not self._query:
            get_kwargs = {'_id': self._value.id}
            self._query = self.relation.objects.get(**get_kwargs)

        return self._query


class OneToOne(BaseRelationField):
    backward_class = _OneToOneBackward

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique = True

    def _get_query(self):
        get_kwargs = {'_id': self._value.id}
        return self.relation.objects.get(**get_kwargs)
