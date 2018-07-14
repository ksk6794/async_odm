import copy
from asyncio import iscoroutinefunction
from typing import get_type_hints, AnyStr, Any, Awaitable, NoReturn, Optional

from bson import DBRef

from ..validators import FieldValidator


class BaseField:
    """
    Base class of any field.
    """
    class Meta:
        field_type = None

    _name = None
    _value = None
    _is_subfield = False

    def __init__(self, **kwargs):
        # Get default values for field attributes
        options = {arg: getattr(self, arg, None) for arg in get_type_hints(self)}
        options.update(kwargs)
        self.__dict__.update(options)

    def __setattr__(self, key, value):
        hints = get_type_hints(self)

        if key in hints:
            required_type = hints.get(key)

            if required_type is not Any and value is not None and not isinstance(value, required_type):
                raise TypeError(
                    f'Reserved attr `{key}` has wrong type! '
                    f'Expected `{required_type.__name__}`'
                )

        super().__setattr__(key, value)

    def __get__(self, instance, owner):
        field_name = self.field_name

        if field_name not in instance._document:
            raise AttributeError()

        return instance._document[field_name]

    def __set__(self, instance, value):
        field_name = self.field_name
        instance._modified_fields.append(field_name)
        instance._document[field_name] = value

    def __set_name__(self, owner, name):
        if '__' in name:
            raise AttributeError(
                f'You can not use `__` in the field name {name}'
            )

        self._name = name

    @property
    def is_subfield(self):
        return self._is_subfield

    @is_subfield.setter
    def is_subfield(self, value):
        self._is_subfield = value if isinstance(value, bool) else False

    @property
    def field_name(self) -> AnyStr:
        return self._name

    @field_name.setter
    def field_name(self, value: Any) -> NoReturn:
        self._name = value

    @property
    def field_value(self) -> Any:
        return self._value

    @field_value.setter
    def field_value(self, value) -> NoReturn:
        self._value = value

    def get_choice_key(self, value: Any) -> Any:
        choices = getattr(self, 'choices', None)

        if choices:
            choices = {key: value for key, value in choices}

            if value in choices.keys():
                value = choices.get(value)

            elif value not in choices.values():
                raise ValueError(
                    f'The value \'{value}\' is not specified in the \'choices\' attribute.'
                )

        return value

    def get_choice_value(self, key: AnyStr) -> Any:
        choices = getattr(self, 'choices', None)
        value = key

        if choices:
            choices = {value: key for key, value in choices}

            if key not in choices.keys():
                raise ValueError(
                    f'The value \'{key}\' is not specified in the \'choices\' attribute.'
                )

            value = choices.get(key)

        return value

    async def process_value(self, value: Any, action=None) -> Any:
        default = getattr(self, 'default', None)
        choices = getattr(self, 'choices', None)

        # Process the 'default' attribute
        if value is None:
            value = await default() if iscoroutinefunction(default) else default() if callable(default) else default

        # Process the 'choices' attribute
        if value and choices:
            value = self.get_choice_key(value)

        return value

    def validate(self, name: AnyStr, value: Any) -> Any:
        FieldValidator(self, name, value).validate()
        return value

    def to_internal_value(self, value: Any) -> Any:
        """
        Define this method if you need to save specific data format.
        Here you must to serialize your data.
        """
        return value

    def to_external_value(self, value: Any) -> Any:
        """
        Define this method if you specified `to_internal_value`,
        to represent data from the storage.
        Here you must to deserialize your data.
        """
        return value


class BaseRelationField(BaseField):
    _query = None

    backward_class = None

    relation: Any
    related_name: Optional[str]

    def __get__(self, instance, owner):
        field = copy.deepcopy(self)
        field_value = instance._document.get(field.field_name)

        if field_value is not None:
            if isinstance(field_value, DBRef) and field_value.id:
                field.field_value = field_value.id
            else:
                field = None

        return field

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for item in self.get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self) -> Awaitable:
        return self.get_query().__await__()

    def get_query(self):
        raise NotImplementedError

    async def validate(self, name, value):
        await FieldValidator(self, name, value).validate_rel()


class BaseBackwardRelationField(BaseField):
    _query = None

    relation: Any = None

    def __get__(self, instance, owner):
        field = copy.deepcopy(self)
        field_value = instance._document.get('_id')

        if isinstance(self.field_value, DBRef):
            field_value = self.field_value.id

        field.field_value = field_value

        return field

    def get_query(self):
        raise NotImplementedError

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for item in self.get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self) -> Awaitable:
        return self.get_query().__await__()
