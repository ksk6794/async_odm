from asyncio import iscoroutinefunction
from typing import get_type_hints, AnyStr, Any, Sequence, Awaitable

from ..validators import FieldValidator


class BaseField:
    """
    Base class of any field.
    """
    _name = None
    _value = None

    field_type = None
    is_sub_field = False

    null: bool
    blank: bool
    min_length: int
    max_length: int
    unique: bool
    choices: Sequence
    on_delete: int

    def __setattr__(self, key, value):
        hints = get_type_hints(self)

        if key in hints:
            required_type = hints.get(key)

            if value is not None and not isinstance(value, required_type):
                raise TypeError(
                    f'Reserved attr `{key}` has wrong type! '
                    f'Expected `{required_type.__name__}`'
                )

        super().__setattr__(key, value)

    def set_field_name(self, name: AnyStr):
        self._name = name

    def get_field_name(self) -> AnyStr:
        return self._name

    def set_field_value(self, value: Any):
        self._value = value

    def get_field_value(self) -> Any:
        return self._value

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
    backward_class = None
    _query = None

    def __init__(self, relation: Any, related_name=None, default=None, null=True, on_delete=None):
        self.relation = relation
        self.related_name = related_name
        self.default = default
        self.null = null
        self.on_delete = on_delete

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for item in self._get_query():
            return item
        raise StopAsyncIteration()

    def __await__(self):
        return self._get_query().__await__()

    def _get_query(self):
        raise NotImplementedError

    async def validate(self, name, value):
        await FieldValidator(self, name, value).validate_rel()


class BaseBackwardRelationField(BaseField):
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

    def __await__(self) -> Awaitable:
        return self.get_query().__await__()
