from core.exceptions import QuerysetError


class Operator:
    def process(self, operator, field_name, value):
        method = getattr(self, f'op_{operator}', None)

        if not callable(method):
            raise QuerysetError(f'Unknown condition `{operator}`')

        return method(field_name, value)

    @staticmethod
    def op_base(field_name, value):
        return {
            field_name: value
        }

    @staticmethod
    def op_rel(field_name, value):
        # Set the id of the related document
        field_name = f'{field_name}.$id'
        field_value = getattr(value, '_id') if hasattr(value, '_id') else value

        return {
            field_name: field_value
        }

    @staticmethod
    def op_exists(field_name, value):
        return {
            field_name: {
                '$exists': value
            }
        }

    @staticmethod
    def op_gt(field_name, value):
        return {
            field_name: {
                '$gt': value
            }
        }

    @staticmethod
    def op_gte(field_name, value):
        return {
            field_name: {
                '$gte': value
            }
        }

    @staticmethod
    def op_in(field_name, value):
        return {
            field_name: {
                '$in': value
            }
        }

    @staticmethod
    def op_isnull(field_name, value):
        return {
            field_name: {
                '$exists': True,
                '$ne': None
            }
        }

    @staticmethod
    def op_lt(field_name, value):
        return {
            field_name: {
                '$lt': value
            }
        }

    @staticmethod
    def op_lte(field_name, value):
        return {
            field_name: {
                '$lte': value
            }
        }

    @staticmethod
    def op_ne(field_name, value):
        return {
            field_name: {
                '$ne': value
            }
        }

    @staticmethod
    def op_all(field_name, value):
        return {
            field_name: {
                '$all': value
            }
        }
