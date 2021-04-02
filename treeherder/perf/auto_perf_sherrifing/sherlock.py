import logging
from datetime import datetime, timedelta
from json import JSONDecodeError
from logging import INFO, WARNING
from typing import List, Tuple

import taskcluster
from django.conf import settings
from django.db.models import QuerySet
from taskcluster.helper import TaskclusterConfig

from treeherder.model.models import Job
from treeherder.perf.auto_perf_sherrifing.backfill_reports import BackfillReportMaintainer
from treeherder.perf.auto_perf_sherrifing.backfill_tool import BackfillTool
from treeherder.perf.auto_perf_sherrifing.secretary import Secretary
from treeherder.perf.email import BackfillNotificationWriter, EmailWriter
from treeherder.perf.exceptions import CannotBackfill, MaxRuntimeExceeded
from treeherder.perf.models import BackfillRecord, BackfillReport

logger = logging.getLogger(__name__)

CLIENT_ID = settings.PERF_SHERIFF_BOT_CLIENT_ID
ACCESS_TOKEN = settings.PERF_SHERIFF_BOT_ACCESS_TOKEN


class Sherlock:
    """
    Robot variant of a performance sheriff (the main class)

    Automates backfilling of skipped perf jobs.
    """

    DEFAULT_MAX_RUNTIME = timedelta(minutes=50)

    def __init__(
        self,
        report_maintainer: BackfillReportMaintainer,
        backfill_tool: BackfillTool,
        secretary: Secretary,
        notify_client: taskcluster.Notify,
        max_runtime: timedelta = None,
        email_writer: EmailWriter = None,
    ):
        self.report_maintainer = report_maintainer
        self.backfill_tool = backfill_tool
        self.secretary = secretary
        self._notify = notify_client
        self._max_runtime = self.DEFAULT_MAX_RUNTIME if max_runtime is None else max_runtime
        self._email_writer = email_writer or BackfillNotificationWriter()

        self._wake_up_time = datetime.now()
        self.backfilled_records = []  # useful for reporting backfill outcome

    def sheriff(self, since: datetime, frameworks: List[str], repositories: List[str]):
        self.assert_can_run()
        logger.info("Sherlock: Validating settings...")
        self.secretary.validate_settings()

        logger.info("Sherlock: Marking reports for backfill...")
        self.secretary.mark_reports_for_backfill()
        self.assert_can_run()

        # secretary checks the status of all backfilled jobs
        # TODO: should not be enabled during soft launch - enable for the real launch
        # self.secretary.check_outcome()

        # reporter tool should always run *(only handles preliminary records/reports)*
        logger.info("Sherlock: Reporter tool is creating/maintaining  reports...")
        self._report(since, frameworks, repositories)
        self.assert_can_run()

        # backfill tool follows
        logger.info("Sherlock: Starting to backfill...")
        self._backfill()
        self.assert_can_run()

        logger.info("Sherlock: Notifying backfill outcome...")
        self._notify_backfill_outcome()

    def runtime_exceeded(self) -> bool:
        elapsed_runtime = datetime.now() - self._wake_up_time
        return self._max_runtime <= elapsed_runtime

    def assert_can_run(self):
        if self.runtime_exceeded():
            raise MaxRuntimeExceeded(f'Max runtime for {self.__class__.__name__} exceeded')

    def _report(
        self, since: datetime, frameworks: List[str], repositories: List[str]
    ) -> List[BackfillReport]:
        return self.report_maintainer.provide_updated_reports(since, frameworks, repositories)

    def _backfill(self):
        left = self.secretary.backfills_left(on_platform='linux')
        total_consumed = 0

        # TODO: make this platform generic
        records_to_backfill = self.__fetch_records_requiring_backfills()
        logger.info(f"Sherlock: {records_to_backfill.count()} records found to backfill.")
        for record in records_to_backfill:
            if left <= 0 or self.runtime_exceeded():
                break
            left, consumed = self._backfill_record(record, left)
            logger.info(f"Sherlock: Backfilled record with id {record.alert.id}.")
            self.backfilled_records.append(record)
            total_consumed += consumed

        self.secretary.consume_backfills('linux', total_consumed)
        logger.info(f"Sherlock: Consumed {total_consumed} backfills for Linux.")
        logger.debug(f"Sherlock: Having {left} backfills left.")

    @staticmethod
    def __fetch_records_requiring_backfills() -> QuerySet:
        records_to_backfill = BackfillRecord.objects.select_related(
            'alert', 'alert__series_signature', 'alert__series_signature__platform'
        ).filter(
            status=BackfillRecord.READY_FOR_PROCESSING,
            alert__series_signature__platform__platform__icontains='linux',
        )
        return records_to_backfill

    def _backfill_record(self, record: BackfillRecord, left: int) -> Tuple[int, int]:
        consumed = 0

        try:
            context = record.get_context()
        except JSONDecodeError:
            logger.warning(f'Failed to backfill record {record.alert.id}: invalid JSON context.')
            record.status = BackfillRecord.FAILED
            record.save()
        else:
            data_points_to_backfill = self.__get_data_points_to_backfill(context)
            for data_point in data_points_to_backfill:
                if left <= 0 or self.runtime_exceeded():
                    break
                try:
                    using_job_id = data_point['job_id']
                    self.backfill_tool.backfill_job(using_job_id)
                    left, consumed = left - 1, consumed + 1
                except (KeyError, CannotBackfill, Exception) as ex:
                    logger.debug(f'Failed to backfill record {record.alert.id}: {ex}')
                else:
                    self.__try_setting_job_type_of(record, using_job_id)

            success, outcome = self._note_backfill_outcome(
                record, len(data_points_to_backfill), consumed
            )
            log_level = INFO if success else WARNING
            logger.log(log_level, f'{outcome} (for backfill record {record.alert.id})')

        return left, consumed

    @staticmethod
    def __try_setting_job_type_of(record, job_id):
        try:
            if record.job_type is None:
                record.job_type = Job.objects.get(id=job_id).job_type
                record.save()
        except Job.DoesNotExist as ex:
            logger.warning(ex)

    @staticmethod
    def _note_backfill_outcome(
        record: BackfillRecord, to_backfill: int, actually_backfilled: int
    ) -> Tuple[bool, str]:
        success = False

        record.total_backfills_triggered = actually_backfilled

        if actually_backfilled == to_backfill:
            record.status = BackfillRecord.BACKFILLED
            success = True
            outcome = 'Backfilled all data points'
        else:
            record.status = BackfillRecord.FAILED
            if actually_backfilled == 0:
                outcome = 'Backfill attempts on all data points failed right upon request.'
            elif actually_backfilled < to_backfill:
                outcome = 'Backfill attempts on some data points failed right upon request.'
            else:
                raise ValueError(
                    f'Cannot have backfilled more than available attempts ({actually_backfilled} out of {to_backfill}).'
                )

        record.set_log_details({'action': 'BACKFILL', 'outcome': outcome})
        record.save()
        return success, outcome

    @staticmethod
    def _is_queue_overloaded(provisioner_id: str, worker_type: str, acceptable_limit=100) -> bool:
        """
        Helper method for Sherlock to check load on processing queue.
        Usage example: _queue_is_too_loaded('gecko-3', 'b-linux')
        :return: True/False
        """
        tc = TaskclusterConfig('https://firefox-ci-tc.services.mozilla.com')
        tc.auth(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
        queue = tc.get_service('queue')

        pending_tasks_count = queue.pendingTasks(provisioner_id, worker_type).get('pendingTasks')

        return pending_tasks_count > acceptable_limit

    def _notify_backfill_outcome(self):
        backfill_notification = self._email_writer.prepare_new_email(self.backfilled_records)

        # send email
        self._notify.email(backfill_notification)

    @staticmethod
    def __get_data_points_to_backfill(context: List[dict]) -> List[dict]:
        context_len = len(context)
        start = None

        if context_len == 1:
            start = 0
        elif context_len > 1:
            start = 1

        return context[start:]
