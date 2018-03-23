from core.exceptions import ValidationError


class Inject:
    def __init__(self, *attrs):
        self.required_attrs = attrs

    def __call__(self, f):
        required_attrs = self.required_attrs

        def _decorated(*args):
            field_instance = args[0].field_instance
            inject = {}

            for required_attr in required_attrs:
                if hasattr(field_instance, required_attr):
                    attr_value = getattr(field_instance, required_attr)
                    inject.update({required_attr: attr_value})
                else:
                    # If at least one attribute is missing
                    return

            res = f(*args, **inject)
            return res

        return _decorated


class FieldValidator:
    def __init__(self, field_instance, name, value):
        self.field_instance = field_instance
        self.name = name
        self.value = value

    @property
    def field_type(self):
        return self.field_instance.field_type

    @property
    def is_sub_field(self):
        return self.field_instance.is_sub_field

    def validate(self):
        self.validate_type()
        self.validate_blank()
        self.validate_null()
        self.validate_length()

    def validate_type(self):
        if self.name and self.value is not None:
            if self.field_type and not isinstance(self.value, self.field_type):
                raise ValidationError(
                    'Field `{field_name} has wrong type! '
                    'Expected {field_type}`'.format(
                        field_name=self.name,
                        field_type=self.field_type.__name__
                    ), self.is_sub_field
                )

    @Inject('blank')
    def validate_blank(self, blank):
        if blank is False and self.value == '':
            raise ValidationError(
                'Field `{field_name}` can not be blank'.format(
                    field_name=self.name
                ), self.is_sub_field
            )

    @Inject('null')
    def validate_null(self, null):
        if null is False and self.value is None:
            raise ValidationError(
                'Field `{field_name}` can not be null'.format(
                    field_name=self.name
                ), self.is_sub_field
            )

    @Inject('min_length', 'max_length')
    def validate_length(self, min_length, max_length):
        if self.name and self.value is not None:
            if min_length or max_length:
                if hasattr(self.value, '__len__'):
                    if max_length and len(self.value) > max_length:
                        raise ValidationError(
                            'Field `{field_name}` exceeds the max length {length}'.format(
                                field_name=self.name,
                                length=max_length
                            ), self.is_sub_field
                        )

                    elif min_length and len(self.value) < min_length:
                        raise ValidationError(
                            'Field `{field_name}` exceeds the min length {length}'.format(
                                field_name=self.name,
                                length=min_length
                            ), self.is_sub_field
                        )

    async def validate_rel(self):
        document_id = getattr(self.value, '_id', self.value)

        # For consistency check if exist related object in the database
        if document_id is not None:
            if not await self.field_instance.relation.objects.filter(_id=document_id).count():
                raise ValueError(
                    'Relation document with ObjectId(\'{document_id}\') does not exist.\n'
                    'Model: \'{model_name}\', Field: \'{field_name}\''.format(
                        document_id=str(document_id),
                        model_name=self.__class__.__name__,
                        field_name=self.name
                    ))
