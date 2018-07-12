from datetime import datetime

from core.abstract.field import BaseRelationField, BaseBackwardRelationField
from .abstract.field import BaseField
from .constants import CREATE, UPDATE


class BoolField(BaseField):
    field_type = bool

    def __init__(self, null=True, default=None, choices=None):
        self.null = null
        self.default = default
        self.choices = choices


class StringField(BaseField):
    field_type = str

    def __init__(self, null=True, blank=True, min_length=None, max_length=None,
                 unique=False, index=None, default=None, choices=None):
        self.null = null
        self.blank = blank
        self.min_length = min_length
        self.max_length = max_length
        self.unique = unique
        self.index = index
        self.default = default
        self.choices = choices


class IntegerField(BaseField):
    field_type = int

    def __init__(self, null=True, unique=False, default=None, choices=None):
        self.null = null
        self.unique = unique
        self.default = default
        self.choices = choices


class FloatField(BaseField):
    field_type = float

    def __init__(self, null=True, unique=False, default=None, choices=None):
        self.null = null
        self.unique = unique
        self.default = default
        self.choices = choices


class ListField(BaseField):
    field_type = list

    def __init__(self, child=None, null=True, length=None, unique=False, default=None):
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


class DictField(BaseField):
    field_type = dict

    def __init__(self, null=True, unique=False, min_length=None, max_length=None, default=None):
        self.null = null
        self.unique = unique
        self.min_length = min_length
        self.max_length = max_length
        self.default = default

    # For IDE tips
    def __iter__(self):
        return self


class DateTimeField(BaseField):
    field_type = datetime

    def __init__(self, null=True, auto_now_create=False, auto_now_update=False):
        self.null = null
        self.auto_now_create = auto_now_create
        self.auto_now_update = auto_now_update

    async def process_value(self, value, action: CREATE | UPDATE=None):
        if (action is CREATE and self.auto_now_create) or (action is UPDATE and self.auto_now_update) and not value:
            # MonogoDB rounds microseconds,
            # and ODM does not request the created document,
            # for data consistency I reset them
            value = datetime.now().replace(microsecond=0)

        return value


class ForeignKeyBackward(BaseBackwardRelationField):
    def get_query(self):
        if not self._query:
            self._query = self.relation.objects.filter(**{
                self._name: self._value
            })

        return self._query


class OneToOneBackward(BaseBackwardRelationField):
    def get_query(self):
        if not self._query:
            self._query = self.relation.objects.get(**{
                self._name: self._value
            })

        return self._query


class ForeignKey(BaseRelationField):
    backward_class = ForeignKeyBackward

    def _get_query(self):
        if not self._query:
            self._query = self.relation.objects.get(**{
                '_id': self._value
            })

        return self._query


class OneToOne(BaseRelationField):
    backward_class = OneToOneBackward

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique = True

    def _get_query(self):
        return self.relation.objects.get(**{
            '_id': self._value
        })
