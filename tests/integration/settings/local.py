DATABASES = {
    'async_odm': {
        'host': 'localhost',
        'port': 27017,
        'models': [
            'tests.models.Post',
            'tests.models.Name',
            'tests.integration.models.Profile',
            'tests.integration.test_fields_attrs.Test',
            'tests.integration.test_fields_attrs.Settings',
            'tests.integration.test_fields_types.User',
            'tests.integration.test_fields_types.TestDT',
            'tests.integration.test_manager.Folder',
            'tests.integration.test_one_to_one.UserTest',
            'tests.integration.test_one_to_one.ProfileTest',
            'tests.integration.test_queryset_fields_defer_only.User',
            'tests.integration.test_queryset_exclude.Profile',

            'tests.integration.test_several_relations.User',
            'tests.integration.test_several_relations.Post',
            'tests.integration.test_several_relations.Comment',
            'tests.integration.test_several_relations.PostData',
        ]
    },
    'test_odm': {
        'host': 'localhost',
        'port': 27017,
        'models': [
            'tests.models.Author',
        ]
    }
}
