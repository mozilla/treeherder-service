import uuid
from copy import copy, deepcopy
from datetime import datetime, timedelta

import pytest
import simplejson as json
from freezegun import freeze_time

from tests.conftest import SampleDataJSONLoader, create_perf_signature, create_perf_alert
from treeherder.model.models import MachinePlatform, Job
from treeherder.perf.auto_perf_sheriffing.secretary_tool import SecretaryTool
from treeherder.perf.models import (
    BackfillReport,
    BackfillRecord,
    PerformanceSettings,
    PerformanceSignature,
    PerformanceAlert,
)

# For testing PerfSheriffBot
from treeherder.utils import default_serializer

load_json_fixture = SampleDataJSONLoader('perf_sheriff_bot')


@pytest.fixture(scope="module")
def record_context_sample():
    # contains 5 data points that can be backfilled
    return load_json_fixture('recordContext.json')


@pytest.fixture(params=['totally_broken_json', 'missing_job_fields', 'null_job_fields'])
def broken_context_str(record_context_sample: dict, request) -> list:
    context_str = json.dumps(record_context_sample)
    specific = request.param

    if specific == 'totally_broken_json':
        return copy(context_str).replace(r'"', '<')

    else:
        record_copy = deepcopy(record_context_sample)
        if specific == 'missing_job_fields':
            for data_point in record_copy:
                del data_point['job_id']

        elif specific == 'null_job_fields':
            for data_point in record_copy:
                data_point['job_id'] = None
        return json.dumps(record_copy)


@pytest.fixture(params=['preliminary', 'from_non_linux'])
def record_unsuited_for_backfill(test_perf_alert, request):
    report = BackfillReport.objects.create(summary=test_perf_alert.summary)

    if request.param == 'preliminary':
        return BackfillRecord.objects.create(alert=test_perf_alert, report=report)
    elif request.param == 'from_non_linux':
        # test_perf_alert originates from wind platform, by default
        return BackfillRecord.objects.create(
            alert=test_perf_alert, report=report, status=BackfillRecord.READY_FOR_PROCESSING
        )


@pytest.fixture
def linux_signature(test_repository, test_perf_framework) -> PerformanceSignature:
    linux_platform = MachinePlatform.objects.create(
        os_name='linux', platform='linux', architecture='x86'
    )
    return create_perf_signature(test_perf_framework, test_repository, linux_platform)


@pytest.fixture
def linux_perf_alert(linux_signature, test_perf_alert_summary) -> PerformanceAlert:
    return create_perf_alert(summary=test_perf_alert_summary, series_signature=linux_signature)


@pytest.fixture
def record_ready_for_processing(linux_perf_alert, record_context_sample):
    report = BackfillReport.objects.create(summary=linux_perf_alert.summary)
    record = BackfillRecord.objects.create(
        alert=linux_perf_alert,
        report=report,
        status=BackfillRecord.READY_FOR_PROCESSING,
    )
    record.set_context(record_context_sample)
    record.save()
    return record


@pytest.fixture
def record_from_mature_report(test_perf_alert_2):
    # create a record from a mature report
    date_past = datetime.utcnow() - timedelta(hours=10)

    with freeze_time(date_past):
        report = BackfillReport.objects.create(summary=test_perf_alert_2.summary)
        record = BackfillRecord.objects.create(alert=test_perf_alert_2, report=report)

    return record


@pytest.fixture
def report_maintainer_mock():
    return type('', (), {'provide_updated_reports': lambda *params: []})


@pytest.fixture
def backfill_tool_mock():
    def backfill_job(job_id):
        if job_id is None:
            raise Job.DoesNotExist
        return 'RANDOM_TASK_ID'

    return type('', (), {'backfill_job': backfill_job})


@pytest.fixture
def secretary():
    return SecretaryTool()


@pytest.fixture
def sheriff_settings(secretary, db):
    secretary.validate_settings()
    return PerformanceSettings.objects.get(name='perf_sheriff_bot')


@pytest.fixture
def empty_sheriff_settings(secretary):
    all_of_them = 1_000_000_000
    secretary.validate_settings()
    secretary.consume_backfills(on_platform='linux', amount=all_of_them)
    return PerformanceSettings.objects.get(name='perf_sheriff_bot')


# For testing SecretaryTool
@pytest.fixture
def performance_settings(db):
    settings = {
        "limits": 500,
        "last_reset_date": datetime.utcnow(),
    }
    return PerformanceSettings.objects.create(
        name="perf_sheriff_bot",
        settings=json.dumps(settings, default=default_serializer),
    )


@pytest.fixture
def expired_performance_settings(db):
    settings = {
        "limits": 500,
        "last_reset_date": datetime.utcnow() - timedelta(days=30),
    }
    return PerformanceSettings.objects.create(
        name="perf_sheriff_bot",
        settings=json.dumps(settings, default=default_serializer),
    )


@pytest.fixture
def create_record():
    def _create_record(alert):
        report = BackfillReport.objects.create(summary=alert.summary)
        return BackfillRecord.objects.create(alert=alert, report=report)

    return _create_record


@pytest.fixture
def record_backfilled(test_perf_alert, record_context_sample):
    report = BackfillReport.objects.create(summary=test_perf_alert.summary)
    record = BackfillRecord.objects.create(
        alert=test_perf_alert,
        report=report,
        status=BackfillRecord.BACKFILLED,
    )
    record.set_context(record_context_sample)
    record.save()
    return record


@pytest.fixture
def range_dates(record_context_sample):

    from_date = datetime.fromisoformat(record_context_sample[0]['push_timestamp'])
    to_date = datetime.fromisoformat(record_context_sample[-1]['push_timestamp'])

    return {
        'before_date': from_date - timedelta(days=5),
        'from_date': from_date,
        'in_range_date': from_date + timedelta(hours=13),
        'to_date': to_date,
        'after_date': to_date + timedelta(days=3),
    }


@pytest.fixture
def outcome_checking_pushes(
    create_push, range_dates, record_context_sample, test_repository, test_repository_2
):
    from_push_id = record_context_sample[0]['push_id']
    to_push_id = record_context_sample[-1]['push_id']

    pushes = [
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['before_date']),
        create_push(
            test_repository,
            revision=uuid.uuid4(),
            time=range_dates['from_date'],
            explicit_id=from_push_id,
        ),
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['in_range_date']),
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['in_range_date']),
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['in_range_date']),
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['in_range_date']),
        create_push(
            test_repository,
            revision=uuid.uuid4(),
            time=range_dates['to_date'],
            explicit_id=to_push_id,
        ),
        create_push(test_repository, revision=uuid.uuid4(), time=range_dates['after_date']),
    ]

    return pushes
