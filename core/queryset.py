from .utils import update
from .node import Q, QNode, QNot, QCombination
from pymongo import DESCENDING, ASCENDING, InsertOne


class QuerySet:
    model = None

    def __init__(self, **kwargs):
        self.query = {}

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

    def filter(self, *args, **kwargs):
        self._find = update(self._find, self._to_query(*args, **kwargs))
        return self

    def exclude(self, *args, **kwargs):
        self._find = update(self._find, self._to_query(*args, invert=True, **kwargs))
        return self

    def sort(self, *args):
        # If not specified in queryset - take from meta
        args = args if args else self.model.get_sorting()

        for arg in args:
            if isinstance(arg, str):
                field_name = arg[1:] if arg.startswith('-') else arg
                ordering = DESCENDING if arg.startswith('-') else ASCENDING
                self._sort.append((field_name, ordering))

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

    async def create(self, **kwargs):
        document = self.model(**kwargs)
        await document.save()
        return document

    async def bulk_create(self, *args):
        documents = []

        for index, document in enumerate(args):
            field_value = await document.get_internal_values()

            # Wrap each document with InsertOne
            document = InsertOne(field_value)
            documents.append(document)

        await self.model.get_dispatcher().bulk_create(documents)

    def _recursive_invert(self, q_item):
        """
        Recursive invert all items inside QCombination.
        :param q_item: QCombination
        :return: list
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

    def _to_query(self, *args, invert=False, **kwargs):
        """
        Convert a Q-parameters into a format that is accessible to the mongodb.
        :param invert: bool
        :param kwargs: dict - key is a field name of the model, value is a sought value
        :return: dict (converted to MongoDB query format)
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

    def _to_object(self, document):
        return self.model(**document)

    def __getitem__(self, item):
        if isinstance(item, slice):
            self._skip = item.start
            self._limit = item.stop
        else:
            raise TypeError('\'{class_name}\' object does not support indexing'.format(
                class_name=self.__class__.__name__)
            )

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

    def __aiter__(self):
        return self

    # TODO: Test it!
    async def __anext__(self):
        async for document in await self.cursor:
            odm_object = self._to_object(document)
            return odm_object
        raise StopAsyncIteration()

    def __await__(self):
        return self._to_list().__await__()
