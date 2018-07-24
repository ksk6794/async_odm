from datetime import datetime
from typing import Any, Sequence, Optional

from core.attributes import NullAttr, BlankAttr, MinLengthAttr, MaxLengthAttr, UniqueAttr
from .base.field import BaseField, BaseRelationField, BaseBackwardRelationField
from .constants import CREATE, UPDATE

__all__ = (
    'BoolField',
    'StringField',
    'IntegerField',
    'FloatField',
    'ListField',
    'DictField',
    'DateTimeField',
    'ForeignKey',
    'OneToOne'
)


class BoolField(BaseField):
    class Meta:
        field_type = bool

    null = NullAttr(value=True)
    default: Any
    choices: Optional[Sequence]


class StringField(BaseField):
    class Meta:
        field_type = str

    null = NullAttr(value=True)
    blank = BlankAttr(value=True)
    min_length = MinLengthAttr(value=None)
    max_length = MaxLengthAttr(value=None)
    unique = UniqueAttr(value=False)
    index: Any
    default: Any
    choices: Optional[Sequence]


class IntegerField(BaseField):
    class Meta:
        field_type = int

    null = NullAttr(value=True)
    unique = UniqueAttr(value=False)
    default: Any
    choices: Optional[Sequence]


class FloatField(BaseField):
    class Meta:
        field_type = float

    null = NullAttr(value=True)
    unique = UniqueAttr(value=False)
    default: Any
    choices: Optional[Sequence]


class ListField(BaseField):
    class Meta:
        field_type = list

    child: Any
    null = NullAttr(value=True)
    length: Optional[int]
    unique = UniqueAttr(value=False)
    default: Any

    # For IDE tips
    def __iter__(self):
        return self

    def validate(self, name, value):
        value = super().validate(name, value)

        # TODO: use multiprocessing pool of workers
        if value and self.child is not None:
            for list_item in value:
                self.child.is_subfield = True
                self.child.validate(name, list_item)

        return value


class DictField(BaseField):
    class Meta:
        field_type = dict

    null = NullAttr(value=True)
    unique = UniqueAttr(value=False)
    min_length = MinLengthAttr(value=None)
    max_length = MaxLengthAttr(value=None)
    default: Any

    # For IDE tips
    def __iter__(self):
        return self


class DateTimeField(BaseField):
    class Meta:
        field_type = datetime

    null = NullAttr(value=True)
    auto_now_create: bool = False
    auto_now_update: bool = False

    async def process_value(self, value, action: int=None):
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

    relation: Any
    related_name: Optional[str]
    default: Any
    null = NullAttr(value=True)
    on_delete: Optional[int]

    def get_query(self):
        if not self._query:
            self._query = self.relation.objects.get(**{
                '_id': self._value
            })

        return self._query


class OneToOne(BaseRelationField):
    backward_class = OneToOneBackward

    relation: Any
    related_name: Optional[str]
    default: Any
    null = NullAttr(value=True)
    on_delete: Optional[int]
    unique = UniqueAttr(value=True)

    def get_query(self):
        return self.relation.objects.get(**{
            '_id': self._value
        })
