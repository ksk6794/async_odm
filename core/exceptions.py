class DoesNotExist(Exception):
    pass


class MultipleObjectsReturned(Exception):
    pass


class QuerysetError(Exception):
    pass


class ProtectedError(Exception):
    pass


class SettingsError(Exception):
    pass


class IndexCollectionError(Exception):
    pass


class CollectionError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, message, is_subfield=False):
        sub_text = ' (Sub-field exception)'
        message = message + sub_text if is_subfield else message
        super().__init__(message)
