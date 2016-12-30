from __future__ import unicode_literals

from rest_framework import status, response

from nodeconductor.core import models
from nodeconductor.core.exceptions import IncorrectStateException


class UpdateOnlyStableMixin(object):
    """
    Allow modification of entities in stable state only.
    """

    def initial(self, request, *args, **kwargs):
        acceptable_states = {
            'update': models.SynchronizationStates.STABLE_STATES,
            'partial_update': models.SynchronizationStates.STABLE_STATES,
            'destroy': models.SynchronizationStates.STABLE_STATES | {models.SynchronizationStates.NEW},
        }
        if self.action in acceptable_states.keys():
            obj = self.get_object()
            if obj and isinstance(obj, models.SynchronizableMixin):
                if obj.state not in acceptable_states[self.action]:
                    raise IncorrectStateException(
                        'Modification allowed in stable states only.')

        return super(UpdateOnlyStableMixin, self).initial(request, *args, **kwargs)


class UserContextMixin(object):
    """ Pass current user to serializer context """

    def get_serializer_context(self):
        context = super(UserContextMixin, self).get_serializer_context()
        context['user'] = self.request.user
        return context


class StateMixin(object):
    """ Raise exception if object is not in correct state for action """

    acceptable_states = {}

    def initial(self, request, *args, **kwargs):
        States = models.StateMixin.States
        acceptable_states = {
            'update': [States.OK],
            'partial_update': [States.OK],
            'destroy': [States.OK, States.ERRED],
        }
        acceptable_states.update(self.acceptable_states)
        acceptable_state = acceptable_states.get(self.action)
        if acceptable_state:
            obj = self.get_object()
            if obj.state not in acceptable_state:
                raise IncorrectStateException('Modification allowed in stable states only.')

        return super(StateMixin, self).initial(request, *args, **kwargs)


# deprecated
class RuntimeStateMixin(object):
    runtime_acceptable_states = {}

    def initial(self, request, *args, **kwargs):
        if self.action in self.runtime_acceptable_states:
            self.check_operation(request, self.get_object(), self.action)
        return super(RuntimeStateMixin, self).initial(request, *args, **kwargs)

    def check_operation(self, request, obj, action):
        acceptable_state = self.runtime_acceptable_states.get(action)
        if acceptable_state:
            if obj.state != models.StateMixin.States.OK or obj.runtime_state != acceptable_state:
                raise IncorrectStateException(
                    'Performing %s operation is not allowed for resource in its current state.' % action)


class AsyncExecutor(object):
    async_executor = True


class CreateExecutorMixin(AsyncExecutor):
    create_executor = NotImplemented

    def perform_create(self, serializer):
        instance = serializer.save()
        self.create_executor.execute(instance, async=self.async_executor)
        instance.refresh_from_db()


class UpdateExecutorMixin(AsyncExecutor):
    update_executor = NotImplemented

    def perform_update(self, serializer):
        instance = self.get_object()
        # Save all instance fields before update.
        # To avoid additional DB queries - store foreign keys as ids.
        # Warning! M2M fields will be ignored.
        before_update_fields = {f: getattr(instance, f.attname) for f in instance._meta.fields}
        super(UpdateExecutorMixin, self).perform_update(serializer)
        instance.refresh_from_db()
        updated_fields = {f.name for f, v in before_update_fields.items() if v != getattr(instance, f.attname)}
        self.update_executor.execute(instance, async=self.async_executor, updated_fields=updated_fields)
        instance.refresh_from_db()


class DeleteExecutorMixin(AsyncExecutor):
    delete_executor = NotImplemented

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.delete_executor.execute(
            instance, async=self.async_executor, force=instance.state == models.StateMixin.States.ERRED)
        return response.Response(
            {'detail': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)


class ExecutorMixin(CreateExecutorMixin, UpdateExecutorMixin, DeleteExecutorMixin):
    """ Executer create/update/delete operation with executor """
    pass


class EagerLoadMixin(object):
    """ Reduce number of requests to DB.

        Serializer should implement static method "eager_load", that selects
        objects that are necessary for serialization.
    """

    def get_queryset(self):
        queryset = super(EagerLoadMixin, self).get_queryset()
        serializer_class = self.get_serializer_class()
        if self.action in ('list', 'retrieve') and hasattr(serializer_class, 'eager_load'):
            queryset = serializer_class.eager_load(queryset)
        return queryset
