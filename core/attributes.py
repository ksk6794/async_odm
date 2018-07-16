from typing import get_type_hints

from core.exceptions import ValidationError


class BaseAttr:
    name = None

    def __init__(self, value):
        self.value = value

    def __set__(self, instance, value):
        hints = get_type_hints(self)
        required_type = hints.get('value')

        if isinstance(value, required_type):
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
    def attr_value(self):
        attr_value = self.field_instance.get_field_attr(self.name)

        if attr_value is None:
            attr_value = self.value

        return attr_value

    def validate(self, field_value):
        raise NotImplementedError()


class NullAttr(BaseAttr):
    value: bool
    name = 'null'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.attr_value is False and field_value is None:
            raise ValidationError(
                f'Field `{field_name}` can not be null',
                self.field_instance.is_subfield
            )


class BlankAttr(BaseAttr):
    value: bool
    name = 'blank'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.attr_value is False and field_value == '':
            raise ValidationError(
                f'Field `{field_name}` can not be blank',
                self.field_instance.is_subfield
            )


class MinLengthAttr(BaseAttr):
    value: int
    name = 'min_length'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.attr_value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) < self.attr_value:
                raise ValidationError(
                    f'Field `{field_name}` exceeds the min length {self.attr_value}',
                    self.field_instance.is_subfield
                )


class MaxLengthAttr(BaseAttr):
    value: int
    name = 'max_length'

    def validate(self, field_value):
        field_name = self.field_instance.field_name

        if self.attr_value and field_value is not None:
            if hasattr(field_value, '__len__') and len(field_value) > self.attr_value:
                raise ValidationError(
                    f'Field `{field_name}` exceeds the max length {self.attr_value}',
                    self.field_instance.is_subfield
                )
