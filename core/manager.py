import functools
from .utils import update
from .node import Q, QNode
from pymongo import DESCENDING, ASCENDING


class DocumentsManager:
    model = None

    def __init__(self, **kwargs):
        # TODO: aggregate
        self._all = False
        self._find = {}
        self._sort = []
        self._limit = None
        self._skip = None
        self._cursor = None
        self.__dict__.update(**kwargs)

    def all(self):
        self._all = True
        return self

    async def get(self, **kwargs):
        get_kwargs = self._to_query(**kwargs)
        result = await self.model.get_dispatcher().get(**get_kwargs)
        odm_object = self._to_object(result)
        return odm_object

    def filter(self, **kwargs):
        self._find = update(self._find, self._to_query(**kwargs))
        return self

    def exclude(self, **kwargs):
        self._find = update(self._find, self._to_query(invert=True, **kwargs))
        return self

    def sort(self, *args):
        for arg in args:
            if isinstance(arg, str):
                field_name = arg[1:] if arg.startswith('-') else arg
                ordering = DESCENDING if arg.startswith('-') else ASCENDING
                self._sort.append((field_name, ordering))

        return self

    def q_query(self, *args):
        if args:
            q_items = [arg for arg in args if isinstance(arg, QNode)]
            query = functools.reduce((lambda q_cur, q_next: q_cur & q_next), q_items)
            update(self._find, query.to_query(self))

        return self

    # TODO: Test it!
    def raw_query(self, raw_query):
        if isinstance(raw_query, dict):
            update(self._find, raw_query)

        return self

    # TODO: Test it!
    async def delete(self):
        result = await self.model.get_dispatcher().delete_many(**self._find)
        return result

    async def count(self):
        result = await self.model.get_dispatcher().count(**self._find)
        return result

    def _to_query(self, invert=False, **kwargs):
        """
        Convert a Q-parameters into a format that is accessible to the mongodb.
        :param invert: bool
        :param kwargs: dict - key is a field name of the model, value is a sought value
        :return: dict - converted to MongoDB query format
        """
        raw_query = {}

        if kwargs:
            # Convert named arguments to Q
            q_items = (Q(**{field_name: field_value}) for field_name, field_value in kwargs.items())

            # Combine Q-elements to single QCombination object via & operator
            query = functools.reduce((lambda q_cur, q_next: q_cur & q_next), q_items)

            # Invert query (it's necessary for exclude-operation)
            if invert:
                query = ~query

            raw_query = query.to_query(self)

        return raw_query

    def _to_object(self, document):
        return self.model(**document)

    def __getitem__(self, item):
        if not isinstance(item, slice):
            raise TypeError('\'{class_name}\' object does not support indexing'.format(
                class_name=self.__class__.__name__)
            )

        self._skip = item.start
        self._limit = item.stop

        return self

    @property
    async def cursor(self):
        if not self._cursor:
            self._cursor = await self.model.get_dispatcher().find(
                sort=self._sort,
                limit=self._limit,
                skip=self._skip,
                filter=self._find
            )
        return self._cursor

    async def _to_list(self):
        return [self._to_object(document) async for document in await self.cursor]

    async def __aiter__(self):
        return self

    # TODO: Test it!
    async def __anext__(self):
        async for document in await self.cursor:
            odm_object = self._to_object(document)
            return odm_object
        raise StopAsyncIteration()

    def __await__(self):
        return self._to_list().__await__()
