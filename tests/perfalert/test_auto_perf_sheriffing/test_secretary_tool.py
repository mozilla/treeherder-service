from datetime import datetime, timedelta

import pytest
import simplejson as json
from django.db.models import Q
from mock import patch

from treeherder.config.settings import IS_WINDOWS
from treeherder.perf.auto_perf_sheriffing.secretary_tool import SecretaryTool
from treeherder.model.models import Push, Job
from treeherder.perf.models import BackfillRecord, BackfillReport, PerformanceSettings
from treeherder.perf.auto_perf_sheriffing.outcome_checker import OutcomeChecker, OutcomeStatus
from treeherder.perf.auto_perf_sheriffing.utils import Helper

# we're testing against this (automatically provided by fixtures)
JOB_TYPE_ID = 1


def get_middle_index(successful_jobs):
    # get middle index to make sure the push is in range
    index_in_range = int((len(successful_jobs) + 1) / 2)
    return index_in_range


@pytest.fixture
def successful_jobs(outcome_checking_pushes, eleven_jobs_stored):
    jobs = Job.objects.all()
    _successful_jobs = []
    pairs = zip(outcome_checking_pushes, jobs)
    for push, job in pairs:
        job.push = push
        job.result = 'success'
        job.job_type_id = JOB_TYPE_ID
        job.save()
        _successful_jobs.append(job)
    return _successful_jobs


@pytest.fixture
def jobs_with_one_failed(successful_jobs):
    index_in_range = get_middle_index(successful_jobs)
    job_to_fail = successful_jobs[index_in_range]
    job_to_fail.result = 'testfailed'
    job_to_fail.save()


@pytest.fixture
def jobs_with_one_pending(successful_jobs):
    index_in_range = get_middle_index(successful_jobs)
    job_pending = successful_jobs[index_in_range]
    job_pending.result = 'unknown'
    job_pending.save()


@pytest.fixture
def get_outcome_checker_mock():
    def get_outcome_checker_mock(outcome: OutcomeStatus):
        return type('', (), {'check': lambda *params: outcome})

    return get_outcome_checker_mock


@pytest.mark.skipif(IS_WINDOWS, reason="datetime logic does not work when OS not on GMT")
def test_secretary_tool_updates_only_matured_reports(
    test_perf_alert, create_record, record_from_mature_report
):
    # create new report with records
    create_record(test_perf_alert)

    assert BackfillRecord.objects.count() == 2
    assert BackfillRecord.objects.filter(status=BackfillRecord.PRELIMINARY).count() == 2

    SecretaryTool.mark_reports_for_backfill()
    assert BackfillRecord.objects.filter(status=BackfillRecord.PRELIMINARY).count() == 1


def test_secretary_tool_uses_existing_settings(performance_settings):
    assert PerformanceSettings.objects.count() == 1
    last_reset_date_before = json.loads(performance_settings.settings)["last_reset_date"]

    SecretaryTool.validate_settings()

    assert PerformanceSettings.objects.count() == 1
    settings_after = PerformanceSettings.objects.filter(name="perf_sheriff_bot").first()
    assert json.loads(settings_after.settings)["last_reset_date"] == last_reset_date_before


def test_secretary_tool_resets_settings_if_expired(expired_performance_settings):
    assert PerformanceSettings.objects.count() == 1
    expired_last_reset_date = json.loads(expired_performance_settings.settings)["last_reset_date"]

    SecretaryTool.validate_settings()

    assert PerformanceSettings.objects.count() == 1
    settings_after = PerformanceSettings.objects.filter(name="perf_sheriff_bot").first()
    assert json.loads(settings_after.settings)["last_reset_date"] != expired_last_reset_date


def test_secretary_tool_creates_new_settings_if_none_exist(db):
    assert PerformanceSettings.objects.count() == 0

    SecretaryTool.validate_settings()

    assert PerformanceSettings.objects.count() == 1


def test_check_outcome_after_success(get_outcome_checker_mock, record_backfilled):
    outcome_checker_mock = get_outcome_checker_mock(OutcomeStatus.SUCCESSFUL)
    secretary = SecretaryTool(outcome_checker_mock)

    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 1
    assert BackfillRecord.objects.filter(status=BackfillRecord.SUCCESSFUL).count() == 0
    secretary.check_outcome()
    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 0
    assert BackfillRecord.objects.filter(status=BackfillRecord.SUCCESSFUL).count() == 1


def test_check_outcome_after_fail(get_outcome_checker_mock, record_backfilled):
    outcome_checker_mock = get_outcome_checker_mock(OutcomeStatus.FAILED)
    secretary = SecretaryTool(outcome_checker_mock)

    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 1
    assert BackfillRecord.objects.filter(status=BackfillRecord.FAILED).count() == 0
    secretary.check_outcome()
    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 0
    assert BackfillRecord.objects.filter(status=BackfillRecord.FAILED).count() == 1


def test_no_action_when_in_progress(get_outcome_checker_mock, record_backfilled):
    outcome_checker_mock = get_outcome_checker_mock(OutcomeStatus.IN_PROGRESS)
    secretary = SecretaryTool(outcome_checker_mock)

    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 1
    secretary.check_outcome()
    assert BackfillRecord.objects.filter(status=BackfillRecord.BACKFILLED).count() == 1


class TestOutcomeChecker:
    @patch('treeherder.perf.auto_perf_sheriffing.outcome_checker.get_job_type')
    def test_successful_jobs_mean_successful_outcome(
        self, mock_get_job_type, record_backfilled, outcome_checking_pushes, successful_jobs
    ):
        # TODO: remove job type mock after soft launch lands
        mock_get_job_type.return_value = JOB_TYPE_ID
        outcome_checker = OutcomeChecker()

        response = outcome_checker.check(record_backfilled)
        assert response == OutcomeStatus.SUCCESSFUL

    @patch('treeherder.perf.auto_perf_sheriffing.outcome_checker.get_job_type')
    def test_failed_job_means_failed_outcome(
        self, mock_get_job_type, record_backfilled, outcome_checking_pushes, jobs_with_one_failed
    ):
        mock_get_job_type.return_value = JOB_TYPE_ID
        outcome_checker = OutcomeChecker()

        response = outcome_checker.check(record_backfilled)
        assert response == OutcomeStatus.FAILED

    @patch('treeherder.perf.auto_perf_sheriffing.outcome_checker.get_job_type')
    def test_pending_job_means_in_progress_outcome(
        self, mock_get_job_type, record_backfilled, outcome_checking_pushes, jobs_with_one_pending
    ):
        mock_get_job_type.return_value = JOB_TYPE_ID
        outcome_checker = OutcomeChecker()

        response = outcome_checker.check(record_backfilled)
        assert response == OutcomeStatus.IN_PROGRESS
