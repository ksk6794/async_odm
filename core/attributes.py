from asyncio import iscoroutinefunction
from datetime import datetime
from typing import get_type_hints, Any, Sequence

from core.constants import CREATE, UPDATE
from core.exceptions import ValidationError


class BaseAttr:
    _default: Any
    name = None

    def __init__(self, value=None):
        self._default = value

    def __set__(self, instance, value):
        hints = get_type_hints(self.__class__)
        required_type = hints.get('_default')

        if required_type is Any or isinstance(value, required_type):
            instance.set_field_attr(self.name, value)
        else:
            raise TypeError(
                f'Reserved attr \'{self.name}\' has wrong type! '
                f'Expected \'{required_type}\'.'
            )

    def __get__(self, instance, owner):
        self.field_instance = instance
        return self

    @property
    def value(self):
        attr_value = self.field_instance.get_field_attr(self.name)

        if attr_value is None:
            attr_value = self._default

        return attr_value

    def validate(self, field_value):
        raise NotImplementedError()


class RequiredAttr(BaseAttr):
    _default: bool
    name = 'required'

    def validate(self, field_value):
        if self.value is True and field_value is None:
            field_name = self.field_instance.field_name

            raise ValidationError(
                f'Field `{field_name}` is required',
                self.field_instance.is_subfield
            )


class BlankAttr(BaseAttr):
    _default: bool
    name = 'blank'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.value is False and field_value == '':
            raise ValidationError(
                f'Field `{field_name}` can not be blank',
                self.field_instance.is_subfield
            )


class MinLengthAttr(BaseAttr):
    _default: int
    name = 'min_length'

    def validate(self, field_value):
        if self.value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) < self.value:
                field_name = self.field_instance.field_name

                raise ValidationError(
                    f'Field `{field_name}` exceeds the min length {self.value}',
                    self.field_instance.is_subfield
                )


class MaxLengthAttr(BaseAttr):
    _default: int
    name = 'max_length'

    def validate(self, field_value):
        if self.value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) > self.value:
                field_name = self.field_instance.field_name

                raise ValidationError(
                    f'Field `{field_name}` exceeds the max length {self.value}',
                    self.field_instance.is_subfield
                )


class UniqueAttr(BaseAttr):
    _default: bool
    name = 'unique'

    def validate(self, field_value):
        pass


class IndexAttr(BaseAttr):
    _default: Any
    name = 'index'

    def validate(self, field_value):
        pass


class DefaultAttr(BaseAttr):
    _default: Any
    name = 'default'

    def validate(self, field_value):
        pass

    async def transform(self, field_value, action):
        default = self.value

        if default and field_value is None:
            if iscoroutinefunction(default):
                field_value = await default()
            elif callable(default):
                field_value = default()
            else:
                field_value = default

        return field_value


class ChoiceAttr(BaseAttr):
    _default: Sequence
    _name = 'choice'

    def validate(self, field_value):
        choices = {k: v for k, v in self.value} if self.value else {}

        if choices and field_value and field_value not in choices:
            field_name = self.field_instance.field_name

            raise ValidationError(
                f'Field `{field_name}` expects the one of {choices}',
                self.field_instance.is_subfield
            )


class AutoNowCreateAttr(BaseAttr):
    _default: bool
    _name = 'auto_now_create'

    def validate(self, field_value):
        pass

    async def transform(self, field_value, action):
        if self.value and not field_value and action is CREATE:
            # MonogoDB rounds microseconds,
            # and ODM does not request the created document,
            # for data consistency I reset them
            field_value = datetime.now().replace(microsecond=0)

        return field_value


class AutoNowUpdateAttr(BaseAttr):
    _default: bool
    _name = 'auto_now_update'

    def validate(self, field_value):
        pass

    async def transform(self, field_value, action):
        if self.value and action is UPDATE:
            # MonogoDB rounds microseconds,
            # and ODM does not request the created document,
            # for data consistency I reset them
            field_value = datetime.now().replace(microsecond=0)

        return field_value
