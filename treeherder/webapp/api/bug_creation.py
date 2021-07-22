import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from treeherder.model.models import FilesBugzillaMap
from treeherder.webapp.api import serializers

logger = logging.getLogger(__name__)


class FilesBugzillaMapViewSet(viewsets.ReadOnlyModelViewSet):
    @action(detail=True, methods=['get'])
    def get_queryset(self):
        """
        Gets a set of bug suggestions for this job
        """
        path = self.request.query_params.get('path')
        path = path.replace('\\', '/')
        # Drop parameters
        path = (path.split('?'))[0]
        file = (path.split('/'))[-1]
        fileNameParts = file.split('.')
        file_without_extension = fileNameParts[0] + ('.' if len(fileNameParts) > 1 else '')
        queryset = (
            FilesBugzillaMap.objects.select_related('bugzilla_component')
            .filter(path__endswith=path)
            .exclude(path__startswith='testing/web-platform/meta/')
            .values('bugzilla_component__product', 'bugzilla_component__component')
            .distinct()
        )
        if len(queryset) == 0:
            # E.g. web-platform-tests ("wpt") can use test files generated from
            # other files which just have different file extensions.
            path_without_extension = (path.rsplit('/', 1))[0] + '/' + file_without_extension
            queryset = (
                FilesBugzillaMap.objects.select_related('bugzilla_component')
                .filter(path__contains=path_without_extension)
                .exclude(path__startswith='testing/web-platform/meta/')
                .values('bugzilla_component__product', 'bugzilla_component__component')
                .distinct()
            )
        if len(queryset) > 0:
            return queryset[: min(5, len(queryset))]
        queryset = (
            FilesBugzillaMap.objects.select_related('bugzilla_component')
            .filter(file_name=file)
            .values('bugzilla_component__product', 'bugzilla_component__component')
            .distinct()
        )
        if len(queryset) > 0:
            return queryset[: min(5, len(queryset))]
        queryset = (
            FilesBugzillaMap.objects.select_related('bugzilla_component')
            .filter(file_name__startswith=file_without_extension)
            .values('bugzilla_component__product', 'bugzilla_component__component')
            .distinct()
        )
        return queryset[: min(5, len(queryset))]

    serializer_class = serializers.FilesBugzillaMapSerializer

    def list(self, request, *args, **kwargs):
        resp = super().list(request, *args, **kwargs)
        return Response(resp.data)
