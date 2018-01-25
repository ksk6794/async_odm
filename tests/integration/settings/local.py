DATABASES = {
    'async_odm': {
        'host': 'localhost',
        'port': 27017,
        'models': {
            'tests.models': ['Post', 'Name'],
            'tests.integration.models': ['Profile'],
            'tests.integration.test_fields_attrs': ['Test', 'Settings'],
            'tests.integration.test_fields_types': ['User', 'TestDT'],
            'tests.integration.test_manager': ['Folder'],
            'tests.integration.test_one_to_one': ['UserTest', 'ProfileTest'],
            'tests.integration.test_queryset_fields_defer_only': ['User'],
            'tests.integration.test_queryset_exclude': ['Profile'],
            'tests.integration.test_several_relations': ['User', 'Post', 'Comment'],
            'tests.integration.test_abstract': ['User']
        },
    },
    'test_odm': {
        'host': 'localhost',
        'port': 27017,
        'models': {
            'tests.models': ['Author']
        },
    }
}
