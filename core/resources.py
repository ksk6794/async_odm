import importlib
import os

from .exceptions import SettingsError
from .managers import DatabaseManager, RelationManager, IndexManager


class ResourcesManager:
    _instance = None

    _database_manager: DatabaseManager = None
    _relation_manager: RelationManager = None
    _index_manager: IndexManager = None

    def __new__(cls, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls)

        return cls._instance

    @property
    def settings(self):
        env_var = 'ODM_SETTINGS_MODULE'
        settings_module = os.environ.get(env_var)

        if not settings_module:
            raise SettingsError(f'Specify an \'{env_var}\' variable in the environment.')

        try:
            return importlib.import_module(settings_module)
        except ImportError:
            raise SettingsError('Can not import settings module, make sure the path is correct.')

    @property
    def databases(self):
        if not self._database_manager:
            if not hasattr(self.settings, 'DATABASES'):
                raise SettingsError(
                    'There is no database configuration! '
                    'Please, define the \'DATABASES\' variable in the your settings module'
                )

            self._database_manager = DatabaseManager(**self.settings.DATABASES)

        return self._database_manager

    @property
    def relations(self):
        if not self._relation_manager:
            self._relation_manager = RelationManager()

        return self._relation_manager

    @property
    def indexes(self):
        if not self._index_manager:
            self._index_manager = IndexManager()

        return self._index_manager
