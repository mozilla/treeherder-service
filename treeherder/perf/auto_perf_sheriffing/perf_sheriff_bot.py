import logging
import re
import requests
from datetime import datetime, timedelta
from json import dumps, JSONDecodeError
from logging import INFO, WARNING
from typing import List, Tuple

import taskcluster
from django.conf import settings
from django.db.models import QuerySet
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from taskcluster.helper import TaskclusterConfig

from treeherder.intermittents_commenter.commenter import Commenter
from treeherder.model.models import Job, Push, Commit
from treeherder.perf.auto_perf_sheriffing.alert_manager import AlertManager, AlertInvalidated
from treeherder.perf.auto_perf_sheriffing.bugzilla_helper import BugzillaHelper
from treeherder.perf.auto_perf_sheriffing.backfill_reports import BackfillReportMaintainer
from treeherder.perf.auto_perf_sheriffing.backfill_tool import BackfillTool
from treeherder.perf.auto_perf_sheriffing.outcome_checker import OutcomeChecker
from treeherder.perf.auto_perf_sheriffing.secretary_tool import SecretaryTool
from treeherder.perf.email import BackfillNotificationWriter, EmailWriter
from treeherder.perf.exceptions import CannotBackfill, MaxRuntimeExceeded
from treeherder.perf.models import BackfillRecord, BackfillReport, PerformanceAlertSummary, PerformanceDatum
from treeherder.perfalert.perfalert import detect_changes
from treeherder.utils.http import make_request

logger = logging.getLogger(__name__)

CLIENT_ID = settings.PERF_SHERIFF_BOT_CLIENT_ID
ACCESS_TOKEN = settings.PERF_SHERIFF_BOT_ACCESS_TOKEN


class PerfSheriffBot:
    """
    Automates backfilling of skipped perf jobs.
    """

    DEFAULT_MAX_RUNTIME = timedelta(minutes=50)

    def __init__(
        self,
        report_maintainer: BackfillReportMaintainer,
        backfill_tool: BackfillTool,
        secretary_tool: SecretaryTool,
        notify_client: taskcluster.Notify,
        max_runtime: timedelta = None,
        email_writer: EmailWriter = None,
    ):
        self.report_maintainer = report_maintainer
        self.backfill_tool = backfill_tool
        self.secretary = secretary_tool
        self._notify = notify_client
        self._max_runtime = self.DEFAULT_MAX_RUNTIME if max_runtime is None else max_runtime
        self._email_writer = email_writer or BackfillNotificationWriter()

        self._wake_up_time = datetime.now()
        self.backfilled_records = []  # useful for reporting backfill outcome

    def sheriff(self, since: datetime, frameworks: List[str], repositories: List[str]):
        self.assert_can_run()
        logger.info('Perfsheriff bot: Validating settings')
        self.secretary.validate_settings()

        logger.info('Perfsheriff bot: Marking reports for backfill')
        self.secretary.mark_reports_for_backfill()
        self.assert_can_run()

        # secretary tool checks the status of all backfilled jobs
        # TODO: should not be enabled during soft launch - enable for the real launch
        # self.secretary.check_outcome()

        # reporter tool should always run *(only handles preliminary records/reports)*
        logger.info('Perfsheriff bot: Reporter tool is creating/maintaining  reports')
        self._report(since, frameworks, repositories)
        self.assert_can_run()

        # backfill tool follows
        logger.info('Perfsheriff bot: Start backfills')
        self._backfill()
        self.assert_can_run()

        logger.info('Perfsheriff bot: Notify backfill outcome')
        self._notify_backfill_outcome()

        logger.info('Perfsheriff bot: Handling backfilled alerts')
        self._handle_backfill_alerts()

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
        logger.info('Perfsheriff bot: %s records found to backfill', records_to_backfill.count())
        for record in records_to_backfill:
            if left <= 0 or self.runtime_exceeded():
                break
            left, consumed = self._backfill_record(record, left)
            logger.info('Perfsheriff bot: backfilled record with id %s', record.alert.id)
            self.backfilled_records.append(record)
            total_consumed += consumed

        self.secretary.consume_backfills('linux', total_consumed)
        logger.info('Perfsheriff bot: consumed %s backfills for linux', total_consumed)
        logger.debug(f'Perfsheriff bot: Having {left} backfills left.')

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
            for data_point in context:
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

            success, outcome = self._note_backfill_outcome(record, len(context), consumed)
            log_level = INFO if success else WARNING
            logger.log(log_level, f'{outcome} (for backfill record {record.alert.id})')

        return left, consumed

    @staticmethod
    def __try_setting_job_type_of(record, job_id):
        try:
            if record.job_type is None:
                record.job_type = Job.objects.get(id=job_id).job_type
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
        Helper method for PerfSheriffBot to check load on processing queue.
        Usage example: _queue_is_too_loaded('gecko-3', 'b-linux')
        :return: True/False
        """
        tc = TaskclusterConfig('https://firefox-ci-tc.services.mozilla.com')
        tc.auth(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
        queue = tc.get_service('queue')

        pending_tasks_count = queue.pendingTasks(provisioner_id, worker_type).get('pendingTasks')

        return pending_tasks_count > acceptable_limit

    def _notify_backfill_outcome(self):
        try:
            backfill_notification = self._email_writer.prepare_new_email(self.backfilled_records)
        except (JSONDecodeError, KeyError, Push.DoesNotExist) as ex:
            logger.warning(f"Failed to email backfill report.{type(ex)}: {ex}")
            return

        # send email
        self._notify.email(backfill_notification)

    def _handle_backfill_alerts(self):
        # Get backfilled alerts
        bugzilla = BugzillaHelper()
        backfilled_records = BackfillRecord.objects.select_related(
            'alert', 'alert__series_signature', 'alert__series_signature__platform'
        ).filter(
            # TODO: Enable this filter once we start getting more backfills
            # status=BackfillRecord.SUCCESSFUL,
            alert__series_signature__platform__platform__icontains='linux',
        )

        for record in backfilled_records:
            # Start by recomputing the alert to see if we have a new
            # culprit commit
            # TODO: Use a try/catch on this later rather than the changed variable
            try:
                cur_push, prev_push, changed = AlertManager.recompute_backfill_alert(record)
                if changed is None:
                    logger.warning(f"Failed to recompute the alert in record {record}")
                    continue
            except AlertInvalidated as e:
                # TODO: Mark the alert as invalid
                logger.info(
                    f"The alert that was backfilled is now invalid. Reason: {e}"
                )
                continue

            # Check if this push has an alert summary already. If it does, reassign
            # the alerts to it, delete this summary.
            existing_summary = PerformanceAlertSummary.objects.filter(push=cur_push)

            if existing_summary and len(existing_summary) > 0:
                existing_summary = existing_summary[0]
                if existing_summary != record.alert.summary:
                    # TODO: Reassign alerts to that existing summary (delete this one too?)
                    logger.info("reassigning...")
            else:
                existing_summary = record.alert.summary

            if existing_summary.bug_number:
                logger.info("Bug exists for this summary, make a comment on it")
                bugzilla.create_alert_comment(
                    # TODO: Use template for alert
                    {'comment': {'body': "Alert!"}},
                    existing_summary.bug_number
                )
                continue

            base_params = {
                'type': "defect",
                'product': "Testing",
                'component': "Raptor",
                'version': "unspecified",
                'severity': "S3",
                'priority': "P5",
                'comment_tags': "treeherder",
            }

            # File a bug for this alert
            new_bug_number = None
            try:
                logger.info(f"Creating bug with the following paramaters: {base_params}")
                response = bugzilla.create_alert_bug(cur_push, base_params)
                if response.status_code != "200":
                    logger.info(
                        f"Failed to create bug.\n"
                        f"Status: {response.status_code}\n"
                        f"Failure: {dumps(response.json(), indent=4)}"
                    )
                    # return
                logger.info(response.json())
                new_bug_number = response.json()["id"]
            except Exception as e:
                logger.exception(str(e))
                # raise

            # TODO: Update alert summary with the new bug_number
