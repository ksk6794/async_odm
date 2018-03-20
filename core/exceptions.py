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


class ValidationError(Exception):
    def __init__(self, message, is_sub_field):
        sub_text = ' (Sub-field exception)'
        message = message + sub_text if is_sub_field else message
        super().__init__(message)
