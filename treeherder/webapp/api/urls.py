from django.urls import include, re_path
from rest_framework import routers

from treeherder.webapp.api import (
    auth,
    bug,
    bug_creation,
    bugzilla,
    changelog,
    csp_report,
    infra_compare,
    intermittents_view,
    investigated_test,
    job_log_url,
    jobs,
    machine_platforms,
    note,
    performance_data,
    push,
    refdata,
    seta,
)

# router for views that are bound to a project
# i.e. all those views that don't involve reference data
# DEPRECATED: We will be slowly transitioning away from this router
# in favor of a router that does not require the ``project`` property.
project_bound_router = routers.SimpleRouter()

# DEPRECATED (in process): The UI is transitioning to the /jobs/ endpoint
# from the default_router.
project_bound_router.register(
    r'jobs',
    jobs.JobsProjectViewSet,
    basename='jobs',
)

project_bound_router.register(
    r'seta/job-priorities', seta.SetaJobPriorityViewSet, basename='seta-job-priorities'
)

project_bound_router.register(
    r'push',
    push.PushViewSet,
    basename='push',
)


project_bound_router.register(
    r'investigated-tests',
    investigated_test.InvestigatedViewSet,
    basename='investigated-tests',
)

project_bound_router.register(
    r'note',
    note.NoteViewSet,
    basename='note',
)

project_bound_router.register(
    r'bug-job-map',
    bug.BugJobMapViewSet,
    basename='bug-job-map',
)

project_bound_router.register(
    r'job-log-url',
    job_log_url.JobLogUrlViewSet,
    basename='job-log-url',
)

project_bound_router.register(
    r'performance/data', performance_data.PerformanceDatumViewSet, basename='performance-data'
)

project_bound_router.register(
    r'performance/signatures',
    performance_data.PerformanceSignatureViewSet,
    basename='performance-signatures',
)

project_bound_router.register(
    r'performance/platforms',
    performance_data.PerformancePlatformViewSet,
    basename='performance-signatures-platforms',
)


# refdata endpoints:
default_router = routers.DefaultRouter()
default_router.register(r'jobs', jobs.JobsViewSet, basename='jobs')
default_router.register(r'repository', refdata.RepositoryViewSet)
default_router.register(
    r'taskclustermetadata', refdata.TaskclusterMetadataViewSet, basename='taskclustermetadata'
)
default_router.register(
    r'optioncollectionhash', refdata.OptionCollectionHashViewSet, basename='optioncollectionhash'
)
default_router.register(r'failureclassification', refdata.FailureClassificationViewSet)
default_router.register(
    r'bugzilla-component',
    bug_creation.FilesBugzillaMapViewSet,
    basename='bugzilla-component',
)
default_router.register(r'user', refdata.UserViewSet, basename='user')
default_router.register(
    r'machineplatforms', machine_platforms.MachinePlatformsViewSet, basename='machineplatforms'
)
default_router.register(
    r'performance/tag', performance_data.PerformanceTagViewSet, basename='performance-tags'
)
default_router.register(
    r'performance/alertsummary',
    performance_data.PerformanceAlertSummaryViewSet,
    basename='performance-alert-summaries',
)
default_router.register(
    r'performance/alert', performance_data.PerformanceAlertViewSet, basename='performance-alerts'
)
default_router.register(
    r'performance/framework',
    performance_data.PerformanceFrameworkViewSet,
    basename='performance-frameworks',
)
default_router.register(
    r'performance/bug-template',
    performance_data.PerformanceBugTemplateViewSet,
    basename='performance-bug-template',
)
default_router.register(
    r'performance/issue-tracker',
    performance_data.PerformanceIssueTrackerViewSet,
    basename='performance-issue-tracker',
)
default_router.register(
    r'performance/validity-dashboard',
    performance_data.TestSuiteHealthViewSet,
    basename='validity-dashboard',
)
default_router.register(r'bugzilla', bugzilla.BugzillaViewSet, basename='bugzilla')
default_router.register(r'auth', auth.AuthViewSet, basename='auth')
default_router.register(r'changelog', changelog.ChangelogViewSet, basename='changelog')

urlpatterns = [
    re_path(r'^project/(?P<project>[\w-]{0,50})/', include(project_bound_router.urls)),
    re_path(r'^', include(default_router.urls)),
    re_path(r'^failures/$', intermittents_view.Failures.as_view(), name='failures'),
    re_path(
        r'^failuresbybug/$',
        intermittents_view.FailuresByBug.as_view(),
        name='failures-by-bug',
    ),
    re_path(r'^failurecount/$', intermittents_view.FailureCount.as_view(), name='failure-count'),
    re_path(r'^infracompare/$', infra_compare.InfraCompareView.as_view(), name='infra-compare'),
    re_path(
        r'^performance/summary/$',
        performance_data.PerformanceSummary.as_view(),
        name='performance-summary',
    ),
    re_path(r'^csp-report/$', csp_report.csp_report_collector, name='csp-report'),
]
