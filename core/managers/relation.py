from inspect import isclass

from ..base.field import BaseRelationField


class RelationManager:
    """
    The singleton manager that organize the relations of models.
    """
    def __init__(self):
        self._registered = {}
        self._waited = {}

    def register_model(self, model):
        """
        Add the model to the list to implement the relations between another models.
        Model names can not be duplicated.
        """
        name = '.'.join((model.__module__, model.__name__))

        self._registered[name] = model
        self._process_relations(model)

        # If the registered model is expected by other models to establish a relation.
        if self._waited.get(name):
            self._process_waited_relation(name)

    def get_model(self, model_name):
        return self._registered.get(model_name)

    def get_models(self):
        return self._registered

    def _process_relations(self, model):
        declared_fields = model.get_declared_fields()

        for field_name, field_instance in declared_fields.items():
            if isinstance(field_instance, BaseRelationField):
                relation = field_instance.relation

                # Get a relationship model
                if isinstance(relation, str):
                    if '.' not in relation:
                        relation = '.'.join((model.__module__, relation))
                        field_instance.relation = relation

                    rel_model = self.get_model(relation)

                elif isclass(relation):
                    rel_model = relation

                else:
                    raise TypeError(
                        'Wrong relation type! '
                        'You should specify the model class '
                        'or str with name of class model.'
                    )

                if rel_model:
                    self._process_relation(field_name, model, rel_model)
                else:
                    if not self._waited.get(relation):
                        self._waited[relation] = []

                    # Add model to the waiting list
                    self._waited[relation].append({
                        'field_name': field_name,
                        'model': model
                    })

    @staticmethod
    def _process_relation(field_name, model, rel_model):
        # The model referred to by the current model
        declared_fields = model.get_declared_fields()
        field_instance = declared_fields.get(field_name)
        field_instance.relation = rel_model

        # If the parameter 'related_name' is not specified - {collection name}_set
        alter = f'{model.get_collection_name()}_set'
        related_name = getattr(field_instance, 'related_name', alter)

        # Add a field to retrieve referring objects to the current object
        backward_relation = field_instance.backward_class(relation=model)
        backward_relation.field_name = field_name

        # Add backward relation by related_name argument
        setattr(rel_model, related_name, backward_relation)
        rel_model.has_backwards = True

    def _process_waited_relation(self, name):
        waited_models = self._waited.get(name)

        for waited_model in waited_models:
            field_name = waited_model.get('field_name')
            model = waited_model.get('model')

            declared_fields = model.get_declared_fields()
            field_instance = declared_fields.get(field_name)
            rel_model = self.get_model(field_instance.relation)

            if rel_model:
                self._process_relation(field_name, model, rel_model)
                del self._waited[name]
