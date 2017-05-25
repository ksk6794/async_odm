import asyncio
import functools

from core.node import Q, QNode
from core.utils import update


class DocumentsManager:
    model = None

    def __init__(self, **kwargs):
        # TODO: limit, skip, sort, aggregate
        self._all = False
        self._get = {}
        self._find = {}
        self._count = False
        self.__dict__.update(**kwargs)

    def all(self):
        self._all = True
        return self

    def get(self, *args, **kwargs):
        self._get = update(self._get, self._to_query(*args, **kwargs))
        return self

    def filter(self, **kwargs):
        self._find = update(self._find, self._to_query(**kwargs))
        return self

    def exclude(self, **kwargs):
        self._find = update(self._find, self._to_query(invert=True, **kwargs))
        return self

    def to_query(self, *args):
        if args:
            q_items = [arg for arg in args if isinstance(arg, QNode)]
            query = functools.reduce((lambda q_cur, q_next: q_cur & q_next), q_items)
            update(self._find, query.to_query(self))

        return self

    def raw(self, raw_condition):
        if isinstance(raw_condition, dict):
            update(self._find, raw_condition)

        return self

    def count(self):
        self._count = True
        return self

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

    def _get_query(self):
        if self._count:
            query = self.model.get_dispatcher().count(**self._find)

        elif self._get:
            query = self.model.get_dispatcher().get(**self._get)

        elif self._find:
            query = self.model.get_dispatcher().find(**self._find)

        elif self._all:
            query = self.model.get_dispatcher().find()

        else:
            raise Exception('Wrong queryset')

        return query

    def _to_object(self, document):
        return self.model(**document)

    def __await__(self):
        result = yield from asyncio.wait_for(self._get_query(), 60)

        if isinstance(result, list):
            odm_objects_list = []

            for document in result:
                odm_object = self._to_object(document)
                odm_objects_list.append(odm_object)

            output = odm_objects_list

        elif isinstance(result, dict):
            output = self._to_object(result)

        else:
            output = result

        return output
