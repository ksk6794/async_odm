from collections import namedtuple
from core.fields import BaseRelationField


WaitedRelation = namedtuple('WaitedRelation', [
    'field_name',
    'field_instance',
    'model_name'
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
                    raise TypeError(
                        'Wrong relation type!'
                        'You should specify the model class '
                        'or str with name of class model.'
                    )

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
        related_name = field_instance.related_name or f'{model.get_collection_name()}_set'

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
