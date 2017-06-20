from datetime import datetime
from core.exceptions import ValidationError


class Field:
    """
    Base class of any field.
    """
    type = None
    _name = None
    _value = None
    is_sub_field = False
    _reserved_attributes = {
        'null': bool,
        'required': bool,
        'min_length': int,
        'max_length': int,
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

    def set_field_name(self, name):
        self._name = name

    def set_field_value(self, value):
        self._value = value

    def get_field_name(self):
        return self._name

    def validate(self):
        if self._name:
            required = getattr(self, 'required', False) or False
            blank = getattr(self, 'blank', True) or True
            min_length = getattr(self, 'min_length', None)
            max_length = getattr(self, 'max_length', None)
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
                    raise ValidationError(exception, self.is_sub_field)

                if min_length or max_length:
                    if hasattr(self._value, '__len__'):
                        if max_length and len(self._value) > max_length:
                            exception = 'Field `{field_name}` exceeds the max length {length}'.format(
                                field_name=self._name,
                                length=max_length
                            )
                            raise ValidationError(exception, self.is_sub_field)
                        elif min_length and len(self._value) < min_length:
                            exception = 'Field `{field_name}` exceeds the min length {length}'.format(
                                field_name=self._name,
                                length=min_length
                            )
                            raise ValidationError(exception, self.is_sub_field)
                    else:
                        exception = 'Cannot count the length of the field `{field_name}`.' \
                                    'Define the __len__ method'.format(
                                        field_name=self._name
                                    )
                        raise ValidationError(exception, self.is_sub_field)

            else:
                if required is True and self._value is None:
                    exception = 'Field `{field_name}` is required'.format(
                        field_name=self._name
                    )
                    raise ValidationError(exception, self.is_sub_field)

                if blank is False and self._value == '':
                    exception = 'Field `{field_name}` can not be blank'.format(
                        field_name=self._name
                    )
                    raise ValidationError(exception, self.is_sub_field)

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

    def __init__(self, required=False, default=None):
        self.required, self.default = required, default


class StringField(Field):
    type = str

    def __init__(self, required=False, blank=True, min_length=None, max_length=None, unique=False, index=None, default=None):
        self.required = required
        self.blank = blank
        self.min_length = min_length
        self.max_length = max_length
        self.unique = unique
        self.index = index
        self.default = default


class IntegerField(Field):
    type = int

    def __init__(self, required=False, unique=False, default=None):
        self.required = required
        self.unique = unique
        self.default = default


class FloatField(Field):
    type = float

    def __init__(self, required=False, unique=False, default=None):
        self.required = required
        self.unique = unique
        self.default = default


class ListField(Field):
    type = list

    def __init__(self, base_field=None, required=False, length=None, unique=False, default=None):
        self.base_field = base_field
        self.required = required
        self.length = length
        self.unique = unique
        self.default = default

    # For IDE tips
    def __iter__(self):
        return self

    def validate(self):
        value = super().validate()

        # TODO: use multiprocessing pool of workers
        if value and self.base_field is not None:
            for list_item in value:
                self.base_field.is_sub_field = True
                self.base_field.set_field_name(self.get_field_name())
                self.base_field.set_field_value(list_item)
                self.base_field.validate()

        return value


class DictField(Field):
    type = dict

    def __init__(self, required=False, unique=False, min_length=None, max_length=None, default=None):
        self.required = required
        self.unique = unique
        self.min_length = min_length
        self.max_length = max_length
        self.default = default

    # For IDE tips
    def __iter__(self):
        return self


class DateTimeField(Field):
    type = datetime

    # TODO: Tests for auto_now_*
    def __init__(self, required=False, auto_now_create=False, auto_now_update=False):
        self.required = required
        self.auto_now_create = auto_now_create
        self.auto_now_update = auto_now_update

    def validate(self):
        value = super().validate()

        if (self.auto_now_create and not self._value) or self.auto_now_update:
            value = datetime.now()

        return value


class BaseRelationField(Field):
    backward_class = None
    _query = None

    def _get_query(self):
        raise NotImplementedError

    def __init__(self, relation, related_name=None, required=False):
        self.relation = relation
        self.related_name = related_name
        self.required = required

    def __aiter__(self):
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

    def __aiter__(self):
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
