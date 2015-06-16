from rest_framework import viewsets, mixins, status, response, exceptions

from nodeconductor.jira.backend import JiraClient, JiraBackendError
from nodeconductor.jira.serializers import IssueSerializer, CommentSerializer
from nodeconductor.jira.filters import JiraSearchFilter


class IssueViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin,
                   mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = IssueSerializer
    filter_backends = (JiraSearchFilter,)

    def get_queryset(self):
        return JiraClient().issues.list_by_user(self.request.user.uuid.hex)

    def get_object(self):
        try:
            return JiraClient().issues.get_by_user(
                self.request.user.uuid.hex, self.kwargs['pk'])
        except JiraBackendError as e:
            raise exceptions.NotFound(e)

    def perform_create(self, serializer):
        try:
            serializer.save(reporter=self.request.user.uuid.hex)
        except JiraBackendError as e:
            raise exceptions.ValidationError(e)


class CommentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        try:
            return JiraClient().comments.list(self.kwargs['pk'])
        except JiraBackendError as e:
            raise exceptions.NotFound(e)

    def perform_create(self, serializer):
        try:
            serializer.save(issue=self.kwargs['pk'])
        except JiraBackendError as e:
            raise exceptions.ValidationError(e)
