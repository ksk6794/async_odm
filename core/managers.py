import copy
from collections import namedtuple

from core.constants import CASCADE, PROTECTED, SET_NULL, SET_DEFAULT
from core.fields import BaseRelationField, BaseBackwardRelationField, OneToOneBackward, ForeignKeyBackward

WaitedRelation = namedtuple('WaitedRelation', [
    'field_name', 'field_instance', 'model_name'
])


class RelationManager:
    """
    The singleton manager that organize the relations of models.
    """
    _instance = None
    _models = {}
    _waited_relations = []

    def __new__(cls):
        if not cls._instance:
            cls._instance = object.__new__(cls)
        return cls._instance

    def add_model(self, model):
        """
        Add the model to the list to implement the relations between another models.
        Model names can not be duplicated.
        :param model: MongoModel instance
        :return: void
        """
        name = '.'.join((model.__module__, model.__name__))

        if model.__name__ is not 'MongoModel':
            self._models[name] = model
            self._process_relations(model)

            if self._waited_relations:
                self._handle_waited_relations()

    def get_model(self, model_name):
        return self._models.get(model_name)

    def get_models(self):
        return self._models

    def _process_relations(self, model):
        # To avoid cyclic import
        from core.base import BaseModel

        declared_fields = model.get_declared_fields()

        for field_name, field_instance in declared_fields.items():
            if isinstance(field_instance, BaseRelationField):
                relation = field_instance.relation

                # Get a relationship model
                if isinstance(relation, BaseModel):
                    rel_model = relation

                elif isinstance(relation, str):
                    if '.' not in relation:
                        relation = '.'.join((model.__module__, relation))
                        field_instance.relation = relation

                    rel_model = self.get_model(relation)

                else:
                    exception = 'Wrong relation type! ' \
                                'You should specify the model class ' \
                                'or str with name of class model.'
                    raise Exception(exception)

                # If the model is not yet registered
                if rel_model:
                    self._handle_relation(field_name, field_instance, rel_model, model)
                else:
                    # Add model to the waiting list
                    waited_relation = WaitedRelation(
                        field_name=field_name,
                        field_instance=field_instance,
                        model_name='.'.join([model.__module__, model.__name__])
                    )
                    self._waited_relations.append(waited_relation)

    @staticmethod
    def _handle_relation(field_name, field_instance, rel_model, model):
        # The model referred to by the current model
        field_instance.relation = rel_model

        # If the parameter `related_name` is not specified - (collection name)_set
        related_name = field_instance.related_name or '{}_set'.format(model.get_collection_name())

        # Add a field to retrieve referring objects to the current object
        backward_relation = field_instance.backward_class(model)
        backward_relation._name = field_name

        # Add backward relation by related_name argument
        declared_fields = rel_model.get_declared_fields()
        declared_fields[related_name] = backward_relation
        rel_model._management.has_backwards = True
        pass

    def _handle_waited_relations(self):
        for waited_relation in self._waited_relations:
            field_name = waited_relation.field_name
            field_instance = waited_relation.field_instance
            model_name = waited_relation.model_name

            model = self.get_model(model_name)
            rel_model = self.get_model(field_instance.relation)

            if rel_model:
                self._handle_relation(field_name, field_instance, rel_model, model)
                index = self._waited_relations.index(waited_relation)
                del self._waited_relations[index]


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
            # TODO: Update by ObjectId (Don't request the odm object)
            odm_obj = await field_instance.get_query()
            setattr(odm_obj, field_name, None)
            await odm_obj.save()

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

                    if on_delete is not None:
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

                        # Process the 'on_delete' parameter in relationships from depth
                        if isinstance(key, BaseBackwardRelationField):
                            # In the nested structure key might be an BaseBackwardRelationField
                            await self.process(field_instance=key, action=action)

        for obj in objects:
            relationship_tree = await self.analyze_backwards(obj)
            await _walk(tree=relationship_tree)
