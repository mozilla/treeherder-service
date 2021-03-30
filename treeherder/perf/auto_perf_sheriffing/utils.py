from typing import List, Tuple

import logging
import time
from datetime import datetime
from django.conf import settings
from django.db.models import Count
from enum import Enum
from json import JSONDecodeError

from treeherder.model.models import Job, Push
from treeherder.perf.models import (
    BackfillRecord, PerformanceAlert, PerformanceDatum,
)
from treeherder.perfalert.perfalert import RevisionDatum
from treeherder.utils.github import fetch_json

logger = logging.getLogger(__name__)

PERF_SHERIFFS = [
    "igoldan@mozilla.com",
    "bebe@mozilla.com",
    "aionescu@mozilla.com",
    "gmierz2@outlook.com"
]


class Helper:
    """A collection of general functions for perf sheriff tasks."""

    def __init__(self):
        pass

    @staticmethod
    def get_backfilled_data(
            record: BackfillRecord,
            post_points: int = 16,
            pre_points: int = 16,
            buffer_points: int = 4,
            alert_bound: bool = True,
        ) -> dict:
        """Helper function to get data around a backfill report.

        Use pre_/post_points to change the range of points returned.
        The buffer changes the amount we add to the end of the
        selection (for alert detection). The dict returned contains
        data which is unsorted, but has information within the
        RevisionDatum values that can be used to sort the data.
        """

        def __accumulate(data, min_pushes: int) -> dict:
            # Starts from the start of the list. Ensure that the data
            # is ordered properly before giving it to this function.
            accumulated_data = {}
            for d in data:
                if len(accumulated_data.keys()) >= min_pushes:
                    break
                if not accumulated_data.get(d.push_id):
                    accumulated_data[d.push_id] = RevisionDatum(
                        int(time.mktime(d.push_timestamp.timetuple())), d.push_id, []
                    )
                accumulated_data[d.push_id].values.append(d.value)
            return accumulated_data

        repository_id = record.alert.summary.repository.id
        max_alert_age = datetime.now() - settings.PERFHERDER_ALERTS_MAX_AGE
        series = PerformanceDatum.objects.filter(
            signature=record.alert.series_signature
        )

        # With this, we can bound the data between the previous and the
        # next alert. This way, we can pull in all the data we might need
        # without pulling in data from other alerts that may corrupt this
        # the data for analysis.
        if alert_bound:
            previous_alerts = (
                PerformanceAlert.objects.filter(
                    series_signature=record.alert.series_signature,
                    summary__push__time__lt=record.alert.summary.push.time
                )
                .select_related('summary__push__time')
                .order_by('-summary__push__time')
                .values_list('summary__push__time', flat=True)
            )
            future_alerts = (
                PerformanceAlert.objects.filter(
                    series_signature=record.alert.series_signature,
                    summary__push__time__gt=record.alert.summary.push.time
                )
                .select_related('summary__push__time')
                .order_by('-summary__push__time')
                .values_list('summary__push__time', flat=True)
            )

            if previous_alerts and len(previous_alerts) > 1:
                # The last one is the alert that occurred before this one.
                series = series.filter(push_timestamp__gt=previous_alerts[::-1][0])
            if future_alerts and len(future_alerts) > 1:
                # The first one is the alert that occurred after this one.
                series = series.filter(push_timestamp__lt=future_alerts[0])

        try:
            from_time, to_time = Helper.get_push_timestamp_range(record.get_context())
            pushes = Helper.get_pushes_in_range(from_time, to_time, repository_id)
        except (JSONDecodeError, KeyError, Push.DoesNotExist) as ex:
            logger.exception(f"Failed to obtain pushes in backfill range.{type(ex)}: {ex}")
            return {}

        # Run the accumulation immediately so that we can
        # pick up the correct number of pushes. series_prev is
        # passed to __accumulate in a reverse order because we want
        # to include the current push in the data.
        series_prev = series.filter(
            push_timestamp__lte=record.alert.summary.push.time
        ).order_by('push_timestamp')
        logger.info(series_prev)
        logger.info("Original data alert")
        logger.info(series_prev[0])
        logger.info(record.alert)
        revs_data_prev = __accumulate(
            series_prev[::-1],
            max(pre_points, len(pushes)+buffer_points)
        )

        series_post = series.filter(
            push_timestamp__gt=record.alert.summary.push.time
        ).order_by("push_timestamp")
        revs_data_post = __accumulate(series_post, post_points)

        revision_data = revs_data_prev
        revision_data.update(revs_data_post)

        return revision_data

    @staticmethod
    def get_pushes_in_range(from_time, to_time, repository_id) -> List[Push]:
        return Push.objects.filter(
            repository_id=repository_id, time__gte=from_time, time__lte=to_time
        ).all()

    @staticmethod
    def get_push_timestamp_range(context: List[dict]) -> Tuple[str, str]:
        from_time = context[0]["push_timestamp"]
        to_time = context[-1]["push_timestamp"]

        return from_time, to_time

    @staticmethod
    def get_hgmo_bug_info(repository: str, revision: str) -> dict:
        # Query HGMO for standard bug information
        if repository == "autoland":
            repository = "integration/autoland"

        url = f"https://hg.mozilla.org/{repository}/json-info?node={revision}&full=true"
        data = fetch_json(url)

        return list(data.values())[0]
