import copy

from core.constants import CASCADE, PROTECTED, SET_NULL, SET_DEFAULT
from core.exceptions import ProtectedError
from core.fields import BaseBackwardRelationField, OneToOneBackward, ForeignKeyBackward


class OnDeleteManager:
    async def process(self, field_instance, action):
        actions_names = {
            CASCADE: 'cascade',
            PROTECTED: 'protected',
            SET_NULL: 'set_null',
            SET_DEFAULT: 'set_default'
        }
        action_name = actions_names.get(action)
        method = getattr(self, f'on_{action_name}', None)

        if callable(method):
            await method(field_instance)

    @staticmethod
    async def on_cascade(field_instance):
        if isinstance(field_instance, OneToOneBackward):
            field_name = field_instance.get_field_name()
            field_value = field_instance.get_field_value()
            filter_kwargs = {field_name: field_value}
            await field_instance.relation.objects.filter(**filter_kwargs).delete()

        elif isinstance(field_instance, ForeignKeyBackward):
            await field_instance.get_query().delete()

    # TODO: Test it!
    @staticmethod
    async def on_protected(field_instance):
        raise ProtectedError()

    @staticmethod
    async def on_set_null(field_instance):
        if isinstance(field_instance, OneToOneBackward):
            field_name = field_instance.get_field_name()
            field_value = field_instance.get_field_value()
            model = field_instance.relation
            filter_kwargs = {field_name: field_value}
            update_data = {field_name: None}
            await model.objects.filter(**filter_kwargs).update(**update_data)

        elif isinstance(field_instance, ForeignKeyBackward):
            field_name = field_instance.get_field_name()
            await field_instance.get_query().update(**{field_name: None})

    @staticmethod
    async def on_set_default(field_instance):
        if isinstance(field_instance, OneToOneBackward):
            pass

        elif isinstance(field_instance, ForeignKeyBackward):
            field_name = field_instance.get_field_name()
            default = field_instance.relation.get_declared_fields().get(field_name).default

            if callable(default):
                default = default()

            await field_instance.get_query().update(**{field_name: default})

    async def analyze_backwards(self, obj=None, odm_objects=None):
        odm_objects = odm_objects if odm_objects is not None else [obj]
        items = []

        for odm_object in odm_objects:
            data = {}

            for field_name, field_instance in odm_object.get_declared_fields().items():
                # Find backward relationships
                if isinstance(field_instance, BaseBackwardRelationField):
                    bwd_field_instance = getattr(odm_object, field_name)
                    relation_field_name = bwd_field_instance.get_field_name()

                    # Get declared fields from the model referenced by backward field
                    declared_fields = bwd_field_instance.relation.get_declared_fields()
                    relation_field_instance = declared_fields.get(relation_field_name)

                    # Get 'on_delete' parameter with the action applied to bwd_field_instance documents
                    on_delete = relation_field_instance.on_delete

                    if on_delete is not None:
                        # await the copied object (prevent 'can not reuse awaitable coroutine')
                        rel_odm_objects = await copy.deepcopy(bwd_field_instance)
                        rel_odm_objects = rel_odm_objects if isinstance(rel_odm_objects, list) else [rel_odm_objects]

                        # Recursively process related objects
                        backwards = await self.analyze_backwards(odm_objects=rel_odm_objects)
                        children = {bwd_field_instance: backwards}

                        data.setdefault(on_delete, [])
                        data[on_delete].append(children)

            items.append(data)

        return items

    async def handle_backwards(self, objects):
        async def _walk(tree, action=None):
            for branch in tree:
                for key, value in branch.items():
                    # In the nested structure key might be an int (event marker)
                    if isinstance(key, int):
                        action = key

                    if isinstance(value, list) and value:
                        await _walk(tree=value, action=action)

                        # Process the 'on_delete' parameter in relationships from depth
                        if isinstance(key, BaseBackwardRelationField):
                            # In the nested structure key might be an BaseBackwardRelationField
                            await self.process(field_instance=key, action=action)

        for obj in objects:
            relationship_tree = await self.analyze_backwards(obj)
            await _walk(tree=relationship_tree)
