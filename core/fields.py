from datetime import datetime
from core.validators import FieldValidator
from .constants import CREATE, UPDATE


class Field:
    """
    Base class of any field.
    """
    field_type = None
    _name = None
    _value = None
    is_sub_field = False
    _reserved_attributes = {
        'null': bool,
        'blank': bool,
        'min_length': int,
        'max_length': int,
        'unique': bool,
        'choices': (tuple, list),
        'on_delete': int
    }

    def __setattr__(self, key, value):
        if key in self._reserved_attributes:
            required_type = self._reserved_attributes.get(key)

            if value is not None and not isinstance(value, required_type):
                raise TypeError(
                    'Reserved attr `{attr_name}` has wrong type! '
                    'Expected `{attr_type}`'.format(
                        attr_name=key,
                        attr_type=required_type.__name__
                    )
                )

        super().__setattr__(key, value)

    def set_field_name(self, name):
        self._name = name

    def get_field_name(self):
        return self._name

    def set_field_value(self, value):
        self._value = value

    def get_field_value(self):
        return self._value

    def get_choice_key(self, value):
        choices = getattr(self, 'choices', None)

        if choices:
            choices = {key: value for key, value in choices}

            if value in choices.keys():
                value = choices.get(value)

            elif value not in choices.values():
                raise ValueError(
                    'The value \'{field_value}\' is not specified in the \'choices\' attribute.'.format(
                        field_value=value
                    )
                )

        return value

    def get_choice_value(self, key):
        choices = getattr(self, 'choices', None)
        value = key

        if choices:
            choices = {value: key for key, value in choices}

            if key not in choices.keys():
                raise ValueError(
                    'The value \'{field_value}\' is not specified in the \'choices\' attribute.'.format(
                        field_value=key
                    )
                )

            value = choices.get(key)

        return value

    def get_value(self, name, value, action):
        default = getattr(self, 'default', None)
        choices = getattr(self, 'choices', None)

        # Process the 'default' attribute
        if default is not None and not value:
            value = default() if callable(default) else default

        # Process the 'choices' attribute
        if value and choices:
            value = self.get_choice_key(value)

        return value

    def validate(self, name, value):
        field_validator = FieldValidator(self, name, value)
        field_validator.validate()

        return value

    def to_internal_value(self, value):
        """
        Define this method if you need to save specific data format.
        Here you must to serialize your data.
        """
        return value

    def to_external_value(self, value):
        """
        Define this method if you specified `to_internal_value`,
        to represent data from the storage.
        Here you must to deserialize your data.
        """
        return value


class BoolField(Field):
    field_type = bool

    def __init__(self, null=False, default=None, choices=None):
        self.null = null
        self.default = default
        self.choices = choices


class StringField(Field):
    field_type = str

    def __init__(self, null=False, blank=True, min_length=None, max_length=None,
                 unique=False, index=None, default=None, choices=None):
        self.null = null
        self.blank = blank
        self.min_length = min_length
        self.max_length = max_length
        self.unique = unique
        self.index = index
        self.default = default
        self.choices = choices


class IntegerField(Field):
    field_type = int

    def __init__(self, null=False, unique=False, default=None, choices=None):
        self.null = null
        self.unique = unique
        self.default = default
        self.choices = choices


class FloatField(Field):
    field_type = float

    def __init__(self, null=False, unique=False, default=None, choices=None):
        self.null = null
        self.unique = unique
        self.default = default
        self.choices = choices


class ListField(Field):
    field_type = list

    def __init__(self, child=None, null=False, length=None, unique=False, default=None):
        self.child = child
        self.null = null
        self.length = length
        self.unique = unique
        self.default = default

    # For IDE tips
    def __iter__(self):
        return self

    def validate(self, name, value):
        value = super().validate(name, value)

        # TODO: use multiprocessing pool of workers
        if value and self.child is not None:
            for list_item in value:
                self.child.is_sub_field = True
                self.child.validate(name, list_item)

        return value


class DictField(Field):
    field_type = dict

    def __init__(self, null=False, unique=False, min_length=None, max_length=None, default=None):
        self.null = null
        self.unique = unique
        self.min_length = min_length
        self.max_length = max_length
        self.default = default

    # For IDE tips
    def __iter__(self):
        return self


class DateTimeField(Field):
    field_type = datetime

    def __init__(self, null=False, auto_now_create=False, auto_now_update=False):
        self.null = null
        self.auto_now_create = auto_now_create
        self.auto_now_update = auto_now_update

    def get_value(self, name, value, action):
        if (action is CREATE and self.auto_now_create) or (action is UPDATE and self.auto_now_update) and not value:
            # MonogoDB rounds microseconds, and ODM does not request the created document,
            # for data consistency I reset them
            value = datetime.now().replace(microsecond=0)

        return value


class BaseRelationField(Field):
    backward_class = None
    _query = None

    def __init__(self, relation, related_name=None, null=False, on_delete=None):
        self.relation = relation
        self.related_name = related_name
        self.null = null
        self.on_delete = on_delete

    def __aiter__(self):
        return self

    # TODO: Test it!
    async def __anext__(self):
        async for item in self._get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self):
        return self._get_query().__await__()

    def _get_query(self):
        raise NotImplementedError


class BaseBackwardRelationField(Field):
    _query = None

    def get_query(self):
        raise NotImplementedError

    def __init__(self, relation):
        self.relation = relation

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for item in self.get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self):
        return self.get_query().__await__()


class ForeignKeyBackward(BaseBackwardRelationField):
    def get_query(self):
        if not self._query:
            filter_kwargs = {self._name: self._value}
            self._query = self.relation.objects.filter(**filter_kwargs)

        return self._query


class OneToOneBackward(BaseBackwardRelationField):
    def get_query(self):
        if not self._query:
            filter_kwargs = {self._name: self._value}
            self._query = self.relation.objects.get(**filter_kwargs)

        return self._query


class ForeignKey(BaseRelationField):
    backward_class = ForeignKeyBackward

    def _get_query(self):
        if not self._query:
            get_kwargs = {'_id': self._value.id}
            self._query = self.relation.objects.get(**get_kwargs)

        return self._query


class OneToOne(BaseRelationField):
    backward_class = OneToOneBackward

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique = True

    def _get_query(self):
        get_kwargs = {'_id': self._value.id}
        return self.relation.objects.get(**get_kwargs)
