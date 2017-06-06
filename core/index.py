class CompositeIndex:
    def __init__(self, composite_dict, unique=False):
        self.composite_dict = composite_dict
        self.unique = unique
        self._cur = 0

    def __setattr__(self, key, value):
        if key == 'composite_dict' and not isinstance(value, (tuple, list)):
            raise ValueError('You must specify dict like {field_name: index_type}')
        super().__setattr__(key, value)
