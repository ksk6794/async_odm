from pymongo import DESCENDING, ASCENDING, InsertOne

from .utils import update
from .node import Q, QNode, QNot, QCombination


class InternalQuery:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    async def create_one(self, **kwargs):
        return await self.dispatcher.create(**kwargs)

    async def update_one(self, document_id, **kwargs):
        return await self.dispatcher.update_one(document_id, **kwargs)

    async def delete_one(self, **kwargs):
        return await self.dispatcher.delete_one(**kwargs)


class QuerySet:
    model = None

    def __init__(self, **kwargs):
        self._params_types = {
            'filter': dict,
            'sort': list,
            'limit': int,
            'skip': int,
            'projection': dict,
        }

        self._projection = {}
        self._all = False
        self._filter = {}
        self._sort = []
        self._limit = None
        self._skip = None
        self._cursor = None

        self.__dict__.update(**kwargs)
        dispatcher = self.model.get_dispatcher()
        self.internal_query = InternalQuery(dispatcher)

    def all(self):
        self._all = True
        return self

    async def get(self, **kwargs):
        get_kwargs = self._to_query(**kwargs)
        result = await self.model.get_dispatcher().get(self._projection, **get_kwargs)
        odm_object = self._to_object(result)
        return odm_object

    def filter(self, *args, **kwargs):
        self._filter = update(self._filter, self._to_query(*args, **kwargs))
        return self

    def exclude(self, *args, **kwargs):
        self._filter = update(self._filter, self._to_query(*args, invert=True, **kwargs))
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

    def raw_query(self, raw_query):
        if isinstance(raw_query, dict):
            update(self._filter, raw_query)
        return self

    async def delete(self):
        """
        If the object to be deleted contains backwards relations, handle them
        """
        result = None

        if not self.model.has_backwards:
            result = await self.model.get_dispatcher().delete_many(**self._filter)
        else:
            async for document in await self.cursor:
                odm_object = self._to_object(document)
                await odm_object.delete()

        return result

    async def count(self):
        result = await self.model.get_dispatcher().count(**self._filter)
        return result

    async def create(self, **kwargs):
        document = self.model(**kwargs)
        await document.save()
        return document

    async def update(self, **kwargs):
        # await self.model.get_dispatcher().update_many(self._filter, **internal_values)

        for odm_object in await self.model.objects.filter(**self._filter):
            for field_name, field_value in kwargs.items():
                setattr(odm_object, field_name, field_value)
                await odm_object.save()

    def fields(self, **kwargs):
        available_operators = ('slice',)

        for key, value in kwargs.items():
            parts = key.split('__')

            if parts[-1] in available_operators:
                operator = parts.pop()
                value = {f'${operator}': value}

            key = '.'.join(parts)
            self._projection[key] = value

        return self

    def defer(self, *args):
        self.fields(**{field_name: False for field_name in args})
        return self

    def only(self, *args):
        self.fields(**{field_name: True for field_name in args})
        return self

    async def bulk_create(self, *args):
        documents = []

        for index, document in enumerate(args):
            internal_values = await document.get_internal_values()

            # Wrap each document with InsertOne
            document = InsertOne(internal_values)
            documents.append(document)

        # TODO: Return all created objects
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
            raise TypeError(f'\'{self.__class__.__name__}\' object does not support indexing')

        return self

    @property
    async def cursor(self):
        if not self._cursor:
            params = {}

            for param_name, param_type in self._params_types.items():
                param_value = getattr(self, f'_{param_name}')

                if isinstance(param_value, param_type):
                    # Value must not be empty
                    if hasattr(param_value, '__len__') and not len(param_value):
                        continue

                    params[param_name] = param_value

            self._cursor = await self.model.get_dispatcher().find(**params)

        return self._cursor

    async def _to_list(self):
        res = [self._to_object(document) async for document in await self.cursor]
        self._cursor = None
        return res

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for document in await self.cursor:
            return self._to_object(document)
        raise StopAsyncIteration()

    def __await__(self):
        return self._to_list().__await__()
