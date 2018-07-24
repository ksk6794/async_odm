from typing import get_type_hints, Any

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


class NullAttr(BaseAttr):
    _default: bool
    name = 'null'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.value is False and field_value is None:
            raise ValidationError(
                f'Field `{field_name}` can not be null',
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
        field_name = self.field_instance.field_name

        if self.value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) < self.value:
                raise ValidationError(
                    f'Field `{field_name}` exceeds the min length {self.value}',
                    self.field_instance.is_subfield
                )


class MaxLengthAttr(BaseAttr):
    _default: int
    name = 'max_length'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) > self.value:
                raise ValidationError(
                    f'Field `{field_name}` exceeds the max length {self.value}',
                    self.field_instance.is_subfield
                )


class UniqueAttr(BaseAttr):
    _default: bool
    name = 'unique'

    def validate(self, field_value):
        pass


class DefaultAttr(BaseAttr):
    _default: Any
    name = 'default'

    def validate(self, field_value):
        pass
