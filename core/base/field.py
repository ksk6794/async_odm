import copy
from collections import deque
from typing import get_type_hints, AnyStr, Any, Awaitable, NoReturn, Optional, Union

from bson import DBRef

from ..exceptions import ValidationError
from ..attributes import BaseAttr


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
        self._attributes = {}

        # Get default values for field attributes
        options = {arg: getattr(self, arg, None) for arg in get_type_hints(self.__class__)}
        options.update(kwargs)

        # Set filed attributes
        deque(map(lambda i: setattr(self, *i), options.items()))

    def set_field_attr(self, name, value):
        self._attributes[name] = value

    def get_field_attr(self, name):
        return self._attributes.get(name)

    def __setattr__(self, key, value):
        hints = get_type_hints(self.__class__)

        if key in hints:
            required_type = hints.get(key)

            if getattr(required_type, '__origin__', None) is Union:
                required_type = tuple([t for t in required_type.__args__ if t not in (Any, None)])

            if required_type is not Any and not isinstance(value, required_type):
                raise TypeError(
                    f'Reserved attr `{key}` has wrong type! '
                    f'Expected `{required_type}`'
                )

        super().__setattr__(key, value)

    def __get__(self, instance, owner):
        field_name = self.field_name

        if instance:
            output = instance.get_field(field_name)

            if not output:
                raise AttributeError()
        else:
            declared_fields = owner.get_declared_fields()
            output = declared_fields.get(field_name)

        return output

    def __set__(self, instance, value):
        instance.set_field(self.field_name, value)

    def __set_name__(self, owner, name):
        if '__' in name:
            raise AttributeError(
                f'You can not use \'__\' in the field name {name}'
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

    def get_choice_value(self, value: Any) -> Any:
        choices = self.choices.value if hasattr(self, 'choices') else None

        if choices:
            choices = {key: value for key, value in choices}

            if value in choices:
                value = choices.get(value)

            else:
                raise ValueError(
                    f'The value \'{value}\' is not specified in the \'choices\' attribute.'
                )

        return value

    async def transform(self, field_value: Any, action=None) -> Any:
        # Get all field attributes
        attributes = [k for k, v in self.__class__.__dict__.items()
                      if isinstance(v, BaseAttr) and hasattr(v, 'transform')]

        # Validate each field attribute
        for attr in attributes:
            field_value = await getattr(self, attr).transform(field_value, action)

        return field_value

    def validate(self, field_value):
        self._validate_type(field_value)
        self._validate_attributes(field_value)

    def _validate_type(self, field_value):
        field_type = self.Meta.field_type

        if field_value is not None:
            if field_type and not isinstance(field_value, field_type):
                raise ValidationError(
                    f'Field \'{self.field_name}\' has wrong type! '
                    f'Expected {field_type}`',
                    self.is_subfield
                )

    def _validate_attributes(self, field_value):
        # Get all field attributes
        attributes = [k for k, v in self.__class__.__dict__.items() if isinstance(v, BaseAttr)]

        # Validate each field attribute
        for attr in attributes:
            getattr(self, attr).validate(field_value)

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
        field_value = instance.get_field(field.field_name)

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

    async def validate(self, field_value):
        super().validate(field_value)

        document_id = getattr(field_value, '_id', field_value)

        # For consistency check if exist related object in the database
        if document_id is not None:
            if not await self.relation.objects.filter(_id=document_id).count():
                raise ValueError(
                    f'Relation document with ObjectId(\'{str(document_id)}\') does not exist.\n'
                    f'Model: \'{self.__class__.__name__}\', Field: \'{self.field_name}\''
                )

    def to_internal_value(self, value: Any):
        collection_name = self.relation.get_collection_name()
        document_id = getattr(value, 'id', value)
        internal_value = DBRef(collection_name, document_id)

        return internal_value


class BaseBackwardRelationField(BaseField):
    _query = None

    relation: Any = None

    def __get__(self, instance, owner):
        field = copy.deepcopy(self)
        field_value = instance.get_field('_id')

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
