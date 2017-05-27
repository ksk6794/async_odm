import copy
from .utils import update
from .fields import BaseRelationField


class QNodeVisitor(object):
    """
    Base visitor class for visiting Q-object nodes in a query tree.
    """
    def visit_combination(self, combination):
        """
        Called by QCombination objects.
        """
        return combination

    def visit_query(self, query):
        """
        Called by (New)Q objects.
        """
        return query


class DuplicateQueryConditionsError(RuntimeError):
    pass


class SimplificationVisitor(QNodeVisitor):
    """
    Simplifies query trees by combinging unnecessary 'and' 
    connection nodes into a single Q-object.
    """
    def visit_combination(self, combination):
        if combination.operation == combination.AND:
            # The simplification only applies to 'simple' queries
            if all(isinstance(node, Q) for node in combination.children):
                queries = [n.query for n in combination.children]
                try:
                    return Q(**self._query_conjunction(queries))
                except DuplicateQueryConditionsError:
                    # Cannot be simplified
                    pass
        return combination

    def _query_conjunction(self, queries):
        """
        Merges query dicts - effectively &ing them together.
        """
        query_ops = set()
        combined_query = {}

        for query in queries:
            ops = set(query.keys())
            # Make sure that the same operation isn't applied more than once
            # to a single field
            intersection = ops.intersection(query_ops)
            if intersection:
                raise DuplicateQueryConditionsError()

            query_ops.update(ops)
            combined_query.update(copy.deepcopy(query))
        return combined_query


class QueryCompilerVisitor(QNodeVisitor):
    """
    Compiles the nodes in a query tree to a PyMongo-compatible query dictionary.
    """
    possible_conditions = ('gt', 'gte', 'lt', 'lte', 'in', 'all')
    delimiter = '__'

    def __init__(self, manager):
        self.manager = manager

    def visit_combination(self, combination):
        operator = "$and"
        if combination.operation == combination.OR:
            operator = "$or"

        return {operator: combination.children}

    def visit_query(self, query):
        return self.transform_query(self.manager, **query.query)

    def transform_query(self, manager, **kwargs):
        mongo_query = {}

        for field_name, field_value in kwargs.copy().items():
            # Split query conditions by delimiter and modify it to MongoDB format.
            if self.delimiter in field_name:
                field_name_splt = field_name.split(self.delimiter)
                field_name = field_name_splt[0]
                condition = field_name_splt[1]

                if condition in self.possible_conditions:
                    field_value = {'${}'.format(condition): field_value}

                else:
                    exception = 'Unknown condition `{condition}`'.format(
                        condition=condition
                    )
                    raise Exception(exception)

            if field_name != '_id' and field_name not in manager.model.get_declared_fields():
                exception = 'Unknown field `{field_name}`'.format(
                    field_name=field_name
                )
                raise Exception(exception)

            field_instance = manager.model.get_declared_fields().get(field_name)

            # Set the id of the related document
            if isinstance(field_instance, BaseRelationField):
                field_name = '{}.$id'.format(field_name)

                if hasattr(field_value, '_id'):
                    field_value = getattr(field_value, '_id')

            update(mongo_query, {field_name: field_value})

        return mongo_query


class QNode(object):
    """
    Base class for nodes in query trees.
    """
    AND = 0
    OR = 1

    def to_query(self, manager):
        query = self.accept(SimplificationVisitor(), manager)
        query = query.accept(QueryCompilerVisitor(manager), manager)
        return query

    def accept(self, visitor, manager):
        raise NotImplementedError

    def _combine(self, other, operation):
        """
        Combine this node with another node into a QCombination object.
        """
        if getattr(other, 'empty', True):
            return self

        if self.empty:
            return other

        return QCombination(operation, [self, other])

    @property
    def empty(self):
        return False

    def __or__(self, other):
        return self._combine(other, self.OR)

    def __and__(self, other):
        return self._combine(other, self.AND)

    def __invert__(self):
        return QNot(self)


class QCombination(QNode):
    """
    Represents the combination of several conditions by a given logical operator.
    """
    def __init__(self, operation, children):
        self.operation = operation
        self.children = []
        for node in children:
            # If the child is a combination of the same type, we can merge its
            # children directly into this combinations children
            if isinstance(node, QCombination) and node.operation == operation:
                self.children += node.children
            else:
                self.children.append(node)

    def accept(self, visitor, manager):
        for i in range(len(self.children)):
            if isinstance(self.children[i], QNode):
                self.children[i] = self.children[i].accept(visitor, manager)

        return visitor.visit_combination(self)

    @property
    def empty(self):
        return not bool(self.children)


class Q(QNode):
    def __init__(self, *arguments, **query):
        if arguments and len(arguments) == 1 and isinstance(arguments[0], dict):
            self.query = {'raw': arguments[0]}
        else:
            self.query = query

    def accept(self, visitor, manager):
        return visitor.visit_query(self)

    @property
    def empty(self):
        return not bool(self.query)


class QNot(QNode):
    def __init__(self, query):
        self.query = query

    def accept(self, visitor, manager):
        return self.to_query(manager)

    def to_query(self, manager):
        query = self.query.to_query(manager)
        result = {}

        for key, value in query.items():
            if isinstance(value, (dict, )):
                result[key] = {
                    '$not': value
                }
            elif isinstance(value, (tuple, set, list)):
                result[key] = {
                    '$nin': value
                }
            else:
                result[key] = {
                    '$ne': value
                }

        return result
