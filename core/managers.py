import copy

from core.constants import CASCADE, PROTECTED, SET_NULL, SET_DEFAULT
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
        method = getattr(self, 'on_{}'.format(action_name), None)

        if callable(method):
            await method(field_instance)

    @staticmethod
    async def on_cascade(field_instance):
        if isinstance(field_instance, OneToOneBackward):
            filter_kwargs = {
                field_instance.get_field_name(): field_instance.get_field_value()
            }
            await field_instance.relation.objects.filter(**filter_kwargs).delete()

        elif isinstance(field_instance, ForeignKeyBackward):
            await field_instance.get_query().delete()

    @staticmethod
    async def on_protected(field_instance):
        raise Exception('ProtectedError')

    @staticmethod
    async def on_set_null(field_instance):
        if isinstance(field_instance, OneToOneBackward):
            field_name = field_instance.get_field_name()
            result = await field_instance
            setattr(result, field_name, None)

        elif isinstance(field_instance, ForeignKeyBackward):
            field_name = field_instance.get_field_name()
            await field_instance.get_query().update(**{field_name: None})

    @staticmethod
    async def on_set_default(field_instance):
        # TODO: Implement setting the default value
        pass

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

                    # await the copied object (prevent 'can not reuse awaitable coroutine')
                    rel_odm_objects = await copy.deepcopy(bwd_field_instance)
                    rel_odm_objects = rel_odm_objects if isinstance(rel_odm_objects, list) else [rel_odm_objects]

                    # Recursively process related objects
                    children = {
                        bwd_field_instance: await self.analyze_backwards(odm_objects=rel_odm_objects)
                    }

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

                        # Handle the 'on_delete' parameter in relationships from depth
                        if isinstance(key, BaseBackwardRelationField):
                            # In the nested structure key might be an BaseBackwardRelationField
                            await self.process(field_instance=key, action=action)

                pass

        for obj in objects:
            relationship_tree = await self.analyze_backwards(obj)
            await _walk(tree=relationship_tree)
