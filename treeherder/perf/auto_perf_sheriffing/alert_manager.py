import logging

from django.conf import settings

from treeherder.model.models import Push
from treeherder.perf.models import BackfillRecord, PerformanceDatum
from treeherder.perf.auto_perf_sheriffing.utils import Helper
from treeherder.perfalert.perfalert import detect_changes

logger = logging.getLogger(__name__)


class AlertInvalidated(Exception):
    """Used to signify that the alert has been invalidated."""
    pass


class AlertManager:
    """Holds methods for recomputing alerts."""

    def __init__(self):
        pass

    @staticmethod
    def generate_instantaneous_alerts():
        """Used to generate instantaneous alerts for all series."""
        return

    @staticmethod
    def recompute_backfill_alert(record: BackfillRecord) -> Push:
        """Determine if the backfilled alert still has the same culprit push.

        Here, we recompute the alert by taking data around the current push,
        including the backfill and 12 after the push to determine the new
        culript commit (if there is one).
        """
        push = record.alert.summary.push
        prev_push = record.alert.summary.prev_push

        backfill = Helper.get_backfilled_data(record, buffer_points=20, pre_points=36)
        logger.info(backfill)

        if not backfill:
            logger.warning("Failed to obtain backfilled data")
            return push, prev_push, None

        signature = record.alert.series_signature

        min_back_window = signature.min_back_window
        if min_back_window is None:
            min_back_window = settings.PERFHERDER_ALERTS_MIN_BACK_WINDOW
        max_back_window = signature.max_back_window
        if max_back_window is None:
            max_back_window = settings.PERFHERDER_ALERTS_MAX_BACK_WINDOW
        fore_window = signature.fore_window
        if fore_window is None:
            fore_window = settings.PERFHERDER_ALERTS_FORE_WINDOW
        alert_threshold = signature.alert_threshold
        if alert_threshold is None:
            alert_threshold = settings.PERFHERDER_REGRESSION_THRESHOLD

        analyzed_series = detect_changes(
            backfill.values(),
            min_back_window=min_back_window,
            max_back_window=max_back_window,
            fore_window=fore_window,
            t_threshold=5,
        )

        first_changed = None
        prev_changed = None
        for (prev, cur) in zip(analyzed_series, analyzed_series[1:]):
            logger.info(cur.push_timestamp)
            if cur.change_detected:
                logger.info(f"Change found here {prev} vs. {cur}. Updating alert")
                first_changed = cur
                prev_changed = prev
                # break
            else:
                logger.info(f"Change not found here {prev} vs. {cur}")

        if not first_changed:
            # Is this technically a failure state which should mark the
            # alert as invalid? There is more data now, so it might show
            # that there are no meaningfull changes anymore.
            logger.info("failed")
            raise AlertInvalidated("Cannot find an alerting commit after backfill.")

        # Is the detected change different now? Check if we have a new push time
        # and that this push time is less than the current one. Otherwise, the chang
        changed = False
        new_alert_commit = PerformanceDatum.objects.filter(push_id=str(first_changed.push_id))[0]
        if new_alert_commit.push.time != record.alert.summary.push.time:
            if new_alert_commit.push.time > record.alert.summary.push.time:
                raise AlertInvalidated(
                    "New alerting commit is after the current push but should be "
                    "before it."
                )
            logger.info(f"Found new commit: {new_alert_commit.push.time}")
            logger.info(f"Previous commit: {record.alert.summary.push.time}")
            push = new_alert_commit.push
            prev_push = prev_changed
            changed = True
        else:
            logger.info("Culprit commit did not change.")

        return push, prev_push, changed
