from typing import get_type_hints, List, Dict

from pymongo import DESCENDING, ASCENDING, InsertOne
from pymongo.results import InsertOneResult, DeleteResult
from motor.motor_asyncio import AsyncIOMotorCursor

from .dispatchers import MongoDispatcher
from .constants import CREATE, UPDATE
from .utils import update
from .node import Q, QNode, QNot, QCombination


class InternalQuery:
    def __init__(self, dispatcher: MongoDispatcher):
        self.dispatcher = dispatcher

    async def create_one(self, **kwargs) -> InsertOneResult:
        return await self.dispatcher.create(**kwargs)

    async def update_one(self, document_id, **kwargs) -> Dict:
        return await self.dispatcher.update_one(document_id, **kwargs)

    async def delete_one(self, **kwargs) -> DeleteResult:
        return await self.dispatcher.delete_one(**kwargs)


class QuerySet:
    model = None

    _filter: Dict
    _sort: List
    _limit: int
    _skip: int
    _projection: Dict

    def __init__(self, **kwargs):
        self._all = False
        self._cursor = None

        self._filter = {}
        self._sort = []
        self._limit = 0
        self._skip = 0
        self._projection = {}

        self.__dict__.update(**kwargs)
        dispatcher = self.model.get_dispatcher()
        self.internal_query = InternalQuery(dispatcher)

    def __setattr__(self, key, value):
        hints = get_type_hints(self)

        if key in hints:
            expected_type = hints.get(key)

            if not isinstance(value, expected_type):
                raise ValueError(
                    f'Attribute \'{key}\' expects type \'{expected_type.__name__}\', '
                    f'but got \'{type(value).__name__}\''
                )

        super().__setattr__(key, value)

    def all(self) -> 'QuerySet':
        self._all = True
        return self

    async def get(self, **kwargs) -> 'MongoModel':
        get_kwargs = self._to_query(**kwargs)
        result = await self.model.get_dispatcher().get(self._projection, **get_kwargs)
        odm_object = self._to_object(result)
        return odm_object

    def filter(self, *args, **kwargs) -> 'QuerySet':
        self._filter = update(self._filter, self._to_query(*args, **kwargs))
        return self

    def exclude(self, *args, **kwargs) -> 'QuerySet':
        self._filter = update(self._filter, self._to_query(*args, invert=True, **kwargs))
        return self

    def sort(self, *args) -> 'QuerySet':
        # If sorting is not specified in queryset - take it from meta.
        args = args if args else self.model.get_sorting()

        for arg in args:
            if isinstance(arg, str):
                field_name = arg[1:] if arg.startswith('-') else arg
                ordering = DESCENDING if arg.startswith('-') else ASCENDING
                self._sort.append((field_name, ordering))

        return self

    def raw_query(self, raw_query) -> 'QuerySet':
        if isinstance(raw_query, dict):
            update(self._filter, raw_query)

        return self

    async def delete(self) -> DeleteResult:
        """
        If the object to be deleted contains backwards relations - handle them.
        """
        result = None

        if not self.model.has_backwards:
            result = await self.model.get_dispatcher().delete_many(**self._filter)
        else:
            async for document in await self.cursor:
                odm_object = self._to_object(document)
                await odm_object.delete()

        return result

    async def count(self) -> int:
        result = await self.model.get_dispatcher().count(**self._filter)
        return result

    async def create(self, **kwargs) -> 'MongoModel':
        document = self.model(**kwargs)
        await document.save()
        return document

    async def update(self, **kwargs) -> None:
        declared_fields = set(self.model.get_declared_fields().keys())
        to_update_fields = set(kwargs.keys())
        modified = list(declared_fields & to_update_fields)
        undeclared = {k: v for k, v in kwargs.items() if k in to_update_fields - declared_fields}

        internal_values = await self.model.get_internal_values(
            action=UPDATE,
            field_values=kwargs,
            modified=modified,
            undeclared=undeclared
        )
        await self.model.get_dispatcher().update_many(self._filter, **internal_values)

    def fields(self, **kwargs) -> 'QuerySet':
        available_operators = ('slice',)

        for key, value in kwargs.items():
            parts = key.split('__')

            if parts[-1] in available_operators:
                operator = parts.pop()
                value = {f'${operator}': value}

            key = '.'.join(parts)
            self._projection[key] = value

        return self

    def defer(self, *args) -> 'QuerySet':
        self.fields(**{field_name: False for field_name in args})
        return self

    def only(self, *args) -> 'QuerySet':
        self.fields(**{field_name: True for field_name in args})
        return self

    async def bulk_create(self, *args):
        documents = []

        for document in args:
            internal_values = await document.get_internal_values(
                action=CREATE,
                field_values=document.__dict__,
                modified=[],
                undeclared={}
            )

            # Wrap each document with InsertOne
            document = InsertOne(internal_values)
            documents.append(document)

        # TODO: Return all created objects
        await self.model.get_dispatcher().bulk_create(documents)

    def _recursive_invert(self, q_item: QCombination) -> List:
        """
        Recursive invert all items inside QCombination.
        """
        children = []

        for q in q_item.children:
            if isinstance(q, Q):
                children.append(~q)

            elif isinstance(q, QNot):
                children.append(q.query)

            elif isinstance(q, QCombination):
                q.children = self._recursive_invert(q)
                children.append(q)

        return children

    def _to_query(self, *args, invert: bool=False, **kwargs) -> Dict:
        """
        Convert a Q-parameters into a format that is accessible to the MongoDB.
        """
        raw_query = {}

        if kwargs or args:
            q_args = args[0] if len(args) == 1 and isinstance(args[0], QNode) else None
            q_kwargs = Q(**kwargs)

            # Invert query (it's necessary for exclude operation)
            if invert:
                if q_args:
                    if isinstance(q_args, QCombination):
                        q_args.children = self._recursive_invert(q_args)

                    elif isinstance(q_args, QNot):
                        q_args = q_args.query

                    elif isinstance(q_args, Q):
                        q_args = QNot(q_args)

                if q_kwargs:
                    q_kwargs = QNot(q_kwargs)

            # Join conditions
            query = q_kwargs & q_args if q_args else q_kwargs

            raw_query = query.to_query(self)

        return raw_query

    def _to_object(self, document: Dict) -> 'MongoModel':
        return self.model(**document)

    def __getitem__(self, item):
        if isinstance(item, slice):
            self._skip = item.start or 0
            self._limit = item.stop or 0
        else:
            raise TypeError(
                f'\'{self.__class__.__name__}\' object does not support indexing'
            )

        return self

    @property
    async def cursor(self) -> AsyncIOMotorCursor:
        if not self._cursor:
            params = {}

            for param_name, param_type in get_type_hints(self).items():
                if param_name.startswith('_'):
                    param_value = getattr(self, param_name)

                    if isinstance(param_value, param_type):
                        # Value must not be empty
                        if hasattr(param_value, '__len__') and not len(param_value):
                            continue

                        params[param_name[1:]] = param_value

            self._cursor = await self.model.get_dispatcher().find(**params)

        return self._cursor

    async def _to_list(self) -> List:
        res = [self._to_object(document) async for document in await self.cursor]
        self._cursor = None
        return res

    def __aiter__(self) -> 'QuerySet':
        return self

    async def __anext__(self) -> 'MongoModel':
        async for document in await self.cursor:
            return self._to_object(document)
        raise StopAsyncIteration()

    def __await__(self):
        return self._to_list().__await__()
