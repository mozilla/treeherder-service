from __future__ import division

import datetime
import time
from collections import namedtuple

from django.conf import settings
from django.db import transaction

from treeherder.model.models import (Job,
                                     Push)
from treeherder.perf.models import (PerformanceAlert,
                                    PerformanceAlertSummary,
                                    PerformanceDatum,
                                    PerformanceSignature)
from treeherder.perfalert.perfalert import (RevisionDatum,
                                            detect_changes)


def check_confirming_perf_alerts_status():
    confirming_interval = settings.PERFHERDER_CONFIRMING_INTERVAL

    def traceback_producer_job_type(perf_alert):
        push = perf_alert.summary.push
        signature = perf_alert.series_signature

        associated_perf_datum = PerformanceDatum.objects.filter(push=push, signature=signature).first()
        return associated_perf_datum.job.job_type if associated_perf_datum else None

    def extract_pushes_to_check(many_nearby_pushes, alert_push, push_range=2):
        many_nearby_pushes = list(many_nearby_pushes)

        alert_push_idx = None
        for index, push in enumerate(many_nearby_pushes):
            if alert_push.id == push.id:
                alert_push_idx = index
                break

        from_push = alert_push_idx - push_range
        from_push = from_push if from_push > 0 else 0
        to_push = alert_push_idx + push_range

        return list(many_nearby_pushes[from_push:to_push])

    confirming_alerts = PerformanceAlert.objects.filter(status=PerformanceAlert.CONFIRMING)
    for alert in confirming_alerts:
        alert_push = alert.summary.push
        alert_repository = alert.series_signature.repository
        _from, _to = alert_push.time-confirming_interval, alert_push.time+confirming_interval

        job_type = traceback_producer_job_type(alert)
        if job_type is None:
            raise LookupError('Could not find job type for perf alert with id {}'.format(alert.id))

        many_nonempty_nearby_pushes = Push.objects.filter(
            time__gte=_from, time__lte=_to, repository=alert_repository,
            jobs__performancedatum__isnull=False, jobs__job_type=job_type,
        ).order_by('time')
        pushes_to_check = extract_pushes_to_check(many_nonempty_nearby_pushes, alert_push)

        if not Job.objects.filter(
                push__in=pushes_to_check, job_type=job_type, state='pending').exists():
            alert.status = PerformanceAlert.CONFIRMED
            alert.save()


def get_alert_properties(prev_value, new_value, lower_is_better):
    AlertProperties = namedtuple('AlertProperties',
                                 'pct_change delta is_regression prev_value new_value')
    if prev_value != 0:
        pct_change = (100.0 * abs(new_value -
                                  prev_value) /
                      float(prev_value))
    else:
        pct_change = 0.0

    delta = (new_value - prev_value)

    is_regression = ((delta > 0 and lower_is_better) or
                     (delta < 0 and not lower_is_better))

    return AlertProperties(pct_change, delta, is_regression, prev_value, new_value)


def generate_new_alerts_in_series(signature):
    # get series data starting from either:
    # (1) the last alert, if there is one
    # (2) the alerts max age
    # (use whichever is newer)
    max_alert_age = (datetime.datetime.now() -
                     settings.PERFHERDER_ALERTS_MAX_AGE)
    series = PerformanceDatum.objects.filter(signature=signature).filter(
        push_timestamp__gte=max_alert_age).order_by('push_timestamp')
    latest_alert_timestamp = PerformanceAlert.objects.filter(
        series_signature=signature).select_related(
            'summary__push__time').order_by(
                '-summary__push__time').values_list(
                    'summary__push__time', flat=True)[:1]
    if latest_alert_timestamp:
        series = series.filter(
            push_timestamp__gt=latest_alert_timestamp[0])

    revision_data = {}
    for d in series:
        if not revision_data.get(d.push_id):
            revision_data[d.push_id] = RevisionDatum(
                int(time.mktime(d.push_timestamp.timetuple())),
                d.push_id, [])
        revision_data[d.push_id].values.append(d.value)

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

    analyzed_series = detect_changes(revision_data.values(),
                                     min_back_window=min_back_window,
                                     max_back_window=max_back_window,
                                     fore_window=fore_window)

    with transaction.atomic():
        for (prev, cur) in zip(analyzed_series, analyzed_series[1:]):
            if cur.change_detected:
                prev_value = cur.historical_stats['avg']
                new_value = cur.forward_stats['avg']
                alert_properties = get_alert_properties(
                    prev_value, new_value, signature.lower_is_better)

                # ignore regressions below the configured regression
                # threshold
                if ((signature.alert_change_type is None or
                     signature.alert_change_type == PerformanceSignature.ALERT_PCT) and
                    alert_properties.pct_change < alert_threshold) or \
                    (signature.alert_change_type == PerformanceSignature.ALERT_ABS and
                     alert_properties.delta < alert_threshold):
                    continue

                summary, _ = PerformanceAlertSummary.objects.get_or_create(
                    repository=signature.repository,
                    framework=signature.framework,
                    push_id=cur.push_id,
                    prev_push_id=prev.push_id,
                    defaults={
                        'manually_created': False,
                        'last_updated': datetime.datetime.utcfromtimestamp(
                            cur.push_timestamp)
                    })

                # django/mysql doesn't understand "inf", so just use some
                # arbitrarily high value for that case
                t_value = cur.t
                if t_value == float('inf'):
                    t_value = 1000

                PerformanceAlert.objects.update_or_create(
                    summary=summary,
                    series_signature=signature,
                    defaults={
                        'is_regression': alert_properties.is_regression,
                        'amount_pct': alert_properties.pct_change,
                        'amount_abs': alert_properties.delta,
                        'prev_value': prev_value,
                        'new_value': new_value,
                        't_value': t_value
                    })
