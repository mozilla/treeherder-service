import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import connection, IntegrityError

from treeherder.model.data_cycling import MaxRuntime
from treeherder.model.data_cycling import PerfherderCycler
from treeherder.model.data_cycling import PublicSignatureRemover
from treeherder.model.data_cycling.removal_strategies import (
    MainRemovalStrategy,
    TryDataRemoval,
    IrrelevantDataRemoval,
    StalledDataRemoval,
)
from treeherder.model.models import Push
from treeherder.perf.exceptions import MaxRuntimeExceeded
from treeherder.perf.models import (
    PerformanceDatum,
    PerformanceSignature,
    PerformanceAlertSummary,
    PerformanceAlert,
    MultiCommitDatum,
    BackfillReport,
)


@pytest.fixture
def empty_backfill_report(test_perf_alert_summary) -> BackfillReport:
    return BackfillReport.objects.create(summary=test_perf_alert_summary)


@pytest.mark.parametrize(
    'repository_name',
    [
        'autoland',
        'mozilla-inbound',
        'mozilla-beta',
        'mozilla-central',
    ],
)
def test_cycle_performance_data(
    test_repository,
    try_repository,
    repository_name,
    push_stored,
    test_perf_signature,
    taskcluster_notify_mock,
):
    test_repository.name = repository_name
    test_repository.save()

    expired_timestamp = datetime.now() - timedelta(days=400)

    test_perf_signature_2 = PerformanceSignature.objects.create(
        signature_hash='b' * 40,
        repository=test_perf_signature.repository,
        framework=test_perf_signature.framework,
        platform=test_perf_signature.platform,
        option_collection=test_perf_signature.option_collection,
        suite=test_perf_signature.suite,
        test='test 2',
        last_updated=expired_timestamp,
        has_subtests=False,
    )

    push1 = Push.objects.get(id=1)
    push1.time = datetime.now()
    push1.save()

    push2 = Push.objects.get(id=2)
    push2.time = expired_timestamp
    push2.save()

    # this shouldn't be deleted in any circumstance
    PerformanceDatum.objects.create(
        id=1,
        repository=test_repository,
        push=push1,
        job=None,
        signature=test_perf_signature,
        push_timestamp=push1.time,
        value=1.0,
    )

    # the performance datum that which we're targeting
    PerformanceDatum.objects.create(
        id=2,
        repository=test_repository,
        push=push2,
        job=None,
        signature=test_perf_signature_2,
        push_timestamp=push2.time,
        value=1.0,
    )

    command = filter(
        lambda arg: arg is not None,
        ['cycle_data', 'from:perfherder'],
    )
    call_command(*list(command))  # test repository isn't a main one

    assert list(PerformanceDatum.objects.values_list('id', flat=True)) == [1]
    assert list(PerformanceSignature.objects.values_list('id', flat=True)) == [
        test_perf_signature.id
    ]


def test_performance_signatures_are_deleted(test_perf_signature, taskcluster_notify_mock):
    cycler = PerfherderCycler(chunk_size=100, sleep_time=0)
    expired_timestamp = cycler.max_timestamp

    perf_signature_to_delete = PerformanceSignature.objects.create(
        signature_hash='b' * 40,
        repository=test_perf_signature.repository,
        framework=test_perf_signature.framework,
        platform=test_perf_signature.platform,
        option_collection=test_perf_signature.option_collection,
        suite=test_perf_signature.suite,
        test='test_perf_signature_to_delete',
        last_updated=expired_timestamp,
        has_subtests=False,
    )

    perf_signature_to_keep = PerformanceSignature.objects.create(
        signature_hash='h' * 40,
        repository=test_perf_signature.repository,
        framework=test_perf_signature.framework,
        platform=test_perf_signature.platform,
        option_collection=test_perf_signature.option_collection,
        suite=test_perf_signature.suite,
        test='test_perf_signature_to_keep',
        last_updated=datetime.now(),
        has_subtests=False,
    )

    call_command('cycle_data', 'from:perfherder')

    assert perf_signature_to_keep.id in list(
        PerformanceSignature.objects.values_list('id', flat=True)
    )
    assert perf_signature_to_delete.id not in list(
        PerformanceSignature.objects.values_list('id', flat=True)
    )


def test_try_data_removal(
    try_repository,
    test_repository,
    try_push_stored,
    test_perf_signature,
    test_perf_signature_2,
    taskcluster_notify_mock,
):
    total_removals = 3
    test_perf_signature.repository = try_repository
    test_perf_signature.save()

    try_pushes = list(Push.objects.filter(repository=try_repository).order_by('id').all())

    for idx, push in enumerate(try_pushes[:-2]):
        push_timestamp = datetime.now()
        if idx < total_removals:
            push_timestamp -= timedelta(weeks=10)

        PerformanceDatum.objects.create(
            repository=try_repository,
            push=push,
            job=None,
            signature=test_perf_signature,
            push_timestamp=push_timestamp,
            value=1.0,
        )

    for push in try_pushes[-2:]:
        push_timestamp = datetime.now() - timedelta(weeks=10)

        # try data removal shouldn't delete these non-try data
        PerformanceDatum.objects.create(
            repository=test_repository,
            push=push,
            job=None,
            signature=test_perf_signature_2,
            push_timestamp=push_timestamp,
            value=1.0,
        )

    total_initial_data = PerformanceDatum.objects.count()

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceDatum.objects.count() == total_initial_data - total_removals
    assert not PerformanceDatum.objects.filter(
        push_timestamp__lt=datetime.now() - timedelta(weeks=6),
        repository=try_repository,
    ).exists()
    assert (
        PerformanceDatum.objects.exclude(repository=try_repository).count() == 2
    )  # non-try data remained intact


@pytest.mark.parametrize(
    'repository_name',
    ['autoland', 'mozilla-beta', 'mozilla-central', 'fenix', 'reference-browser'],
)
def test_irrelevant_repos_data_removal(
    test_repository,
    relevant_repository,
    repository_name,
    push_stored,
    test_perf_signature,
    taskcluster_notify_mock,
):
    # test_repository is considered irrelevant repositories

    relevant_repository.name = repository_name
    relevant_repository.save()

    six_months_ago_timestamp = datetime.now() - timedelta(days=(6 * 30))

    push = Push.objects.first()

    # performance datum for irrelevant repository which has an expired push_timestamp ( older than 6 months )
    # this one should be deleted, because it's expired
    PerformanceDatum.objects.create(
        repository=test_repository,
        push=push,
        job=None,
        signature=test_perf_signature,
        push_timestamp=six_months_ago_timestamp,
        value=1.0,
    )

    # performance datum for relevant repository which has a push_timestamp older than 6 months
    # this one should still be kept in db
    PerformanceDatum.objects.create(
        repository=relevant_repository,
        push=push,
        job=None,
        signature=test_perf_signature,
        push_timestamp=six_months_ago_timestamp,
        value=1.0,
    )

    # performance datum for irrelevant repository which has a one week old push_timestamp
    # this one should still be kept in db
    PerformanceDatum.objects.create(
        repository=test_repository,
        push=push,
        job=None,
        signature=test_perf_signature,
        push_timestamp=datetime.now() - timedelta(weeks=1),
        value=1.0,
    )

    total_initial_data = PerformanceDatum.objects.count()

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceDatum.objects.count() == total_initial_data - 1
    assert PerformanceDatum.objects.filter(repository=relevant_repository).exists()
    assert not PerformanceDatum.objects.filter(
        push_timestamp__lte=six_months_ago_timestamp,
        repository=test_repository,
    ).exists()


def test_signature_remover(
    test_perf_signature,
    test_perf_signature_2,
    test_perf_data,
    taskcluster_notify_mock,
    mock_tc_prod_notify_credentials,
):
    cycler = PerfherderCycler(chunk_size=100, sleep_time=0)
    expired_timestamp = cycler.max_timestamp
    test_perf_signature_2.last_updated = expired_timestamp
    test_perf_signature_2.save()

    assert len(PerformanceSignature.objects.all()) == 2

    call_command('cycle_data', 'from:perfherder')

    assert taskcluster_notify_mock.email.call_count == 1
    assert len(PerformanceSignature.objects.all()) == 1
    assert PerformanceSignature.objects.first() == test_perf_signature


@pytest.mark.parametrize('total_signatures', [3, 4, 8, 10])
def test_total_emails_sent(
    test_perf_signature, try_repository, total_signatures, mock_tc_prod_notify_credentials
):
    notify_client_mock = MagicMock()
    timer = MaxRuntime()
    timer.start_timer()
    total_rows = 2
    total_emails = 4
    signatures_remover = PublicSignatureRemover(
        timer=timer,
        notify_client=notify_client_mock,
        max_rows_allowed=total_rows,
        max_emails_allowed=total_emails,
    )

    for n in range(0, total_signatures):
        PerformanceSignature.objects.create(
            repository=test_perf_signature.repository,
            signature_hash=(20 * ('t%s' % n)),
            framework=test_perf_signature.framework,
            platform=test_perf_signature.platform,
            option_collection=test_perf_signature.option_collection,
            suite='mysuite%s' % n,
            test='mytest%s' % n,
            application='firefox',
            has_subtests=test_perf_signature.has_subtests,
            extra_options=test_perf_signature.extra_options,
            last_updated=datetime.now(),
        )

    for n in range(0, 10):
        PerformanceSignature.objects.create(
            repository=try_repository,
            signature_hash=(20 * ('e%s' % n)),
            framework=test_perf_signature.framework,
            platform=test_perf_signature.platform,
            option_collection=test_perf_signature.option_collection,
            suite='mysuite%s' % n,
            test='mytest%s' % n,
            application='firefox',
            has_subtests=test_perf_signature.has_subtests,
            extra_options=test_perf_signature.extra_options,
            last_updated=datetime.now(),
        )

    total_signatures += 1  # is incremented because of test_perf_signature
    total_of_possible_emails = math.ceil(total_signatures / total_rows)
    expected_call_count = (
        total_of_possible_emails if total_of_possible_emails <= total_emails else total_emails
    )

    signatures = PerformanceSignature.objects.filter(last_updated__lte=datetime.now())
    signatures_remover.remove_in_chunks(signatures)

    assert notify_client_mock.email.call_count == expected_call_count
    assert not PerformanceSignature.objects.filter(repository__name='try').exists()


def test_remove_try_signatures_without_data(
    test_perf_signature, test_perf_data, try_repository, mock_tc_prod_notify_credentials
):
    notify_client_mock = MagicMock()
    timer = MaxRuntime()
    timer.start_timer()
    total_rows = 2
    total_emails = 2
    signatures_remover = PublicSignatureRemover(
        timer=timer,
        notify_client=notify_client_mock,
        max_rows_allowed=total_rows,
        max_emails_allowed=total_emails,
    )
    signature_with_perf_data = PerformanceSignature.objects.create(
        repository=try_repository,
        signature_hash=(20 * 'e1'),
        framework=test_perf_signature.framework,
        platform=test_perf_signature.platform,
        option_collection=test_perf_signature.option_collection,
        suite='mysuite',
        test='mytest',
        application='firefox',
        has_subtests=test_perf_signature.has_subtests,
        extra_options=test_perf_signature.extra_options,
        last_updated=datetime.now(),
    )
    push = Push.objects.first()
    PerformanceDatum.objects.create(
        repository=signature_with_perf_data.repository,
        push=push,
        job=None,
        signature=signature_with_perf_data,
        push_timestamp=datetime.now(),
        value=1.0,
    )

    signatures = PerformanceSignature.objects.filter(last_updated__lte=datetime.now())
    signatures_remover.remove_in_chunks(signatures)

    assert PerformanceSignature.objects.filter(id=signature_with_perf_data.id).exists()


def test_performance_cycler_quit_indicator(taskcluster_notify_mock):
    ten_minutes_ago = datetime.now() - timedelta(minutes=10)
    one_second = timedelta(seconds=1)

    two_seconds_ago = datetime.now() - timedelta(seconds=2)
    five_minutes = timedelta(minutes=5)

    with pytest.raises(MaxRuntimeExceeded):
        PerfherderCycler(chunk_size=100, sleep_time=0)

        max_runtime = MaxRuntime(max_runtime=one_second)
        max_runtime.started_at = ten_minutes_ago
        max_runtime.quit_on_timeout()
    try:
        PerfherderCycler(chunk_size=100, sleep_time=0)

        max_runtime = MaxRuntime(max_runtime=five_minutes)
        max_runtime.started_at = two_seconds_ago
        max_runtime.quit_on_timeout()
    except MaxRuntimeExceeded:
        pytest.fail('Performance cycling shouldn\'t have timed out')


@pytest.fixture
def empty_alert_summary(
    test_repository, push_stored, test_perf_framework, test_issue_tracker
) -> PerformanceAlertSummary:
    return PerformanceAlertSummary.objects.create(
        repository=test_repository,
        framework=test_perf_framework,
        prev_push_id=1,
        push_id=3,
        manually_created=True,
    )


@pytest.mark.parametrize(
    'expired_time',
    [
        datetime.now() - timedelta(days=365),
        datetime.now() - timedelta(days=181),
        datetime.now() - timedelta(days=180, hours=1),
    ],
)
def test_summary_without_any_kind_of_alerts_is_deleted(
    expired_time, empty_alert_summary, taskcluster_notify_mock
):
    empty_alert_summary.created = expired_time
    empty_alert_summary.save()

    assert PerformanceAlertSummary.objects.count() == 1
    assert empty_alert_summary.alerts.count() == 0
    assert empty_alert_summary.related_alerts.count() == 0

    call_command('cycle_data', 'from:perfherder')
    assert not PerformanceAlertSummary.objects.exists()


@pytest.mark.parametrize(
    'recently',
    [
        datetime.now(),
        datetime.now() - timedelta(minutes=30),
        datetime.now() - timedelta(weeks=4),
        datetime.now() - timedelta(days=179, hours=23),
    ],
)
def test_summary_without_any_kind_of_alerts_isnt_deleted(
    recently, empty_alert_summary, taskcluster_notify_mock
):
    empty_alert_summary.created = recently
    empty_alert_summary.save()

    assert PerformanceAlertSummary.objects.count() == 1
    assert empty_alert_summary.alerts.count() == 0
    assert empty_alert_summary.related_alerts.count() == 0

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceAlertSummary.objects.count() == 1


@pytest.mark.parametrize(
    'creation_time',
    [
        # expired
        datetime.now() - timedelta(days=365),
        datetime.now() - timedelta(days=181),
        datetime.now() - timedelta(days=180, hours=1),
        # not expired
        datetime.now(),
        datetime.now() - timedelta(minutes=30),
        datetime.now() - timedelta(weeks=4),
        datetime.now() - timedelta(days=179, hours=23),
    ],
)
def test_summary_with_alerts_isnt_deleted(
    creation_time,
    empty_alert_summary,
    test_perf_alert,
    test_perf_alert_2,
    test_perf_data,
    taskcluster_notify_mock,
):
    empty_alert_summary.created = creation_time
    empty_alert_summary.save()

    test_perf_data = list(test_perf_data)
    for datum in test_perf_data[2:]:
        datum.signature = test_perf_alert_2.series_signature
        datum.repository = test_perf_alert_2.series_signature.repository
        datum.save()

    # with alerts only
    test_perf_alert.summary = empty_alert_summary
    test_perf_alert.save()

    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()
    assert empty_alert_summary.alerts.count() == 1
    assert empty_alert_summary.related_alerts.count() == 0

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()

    # with both
    test_perf_alert_2.status = PerformanceAlert.REASSIGNED
    empty_alert_summary.related_alerts.add(test_perf_alert_2, bulk=False)

    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()
    assert empty_alert_summary.alerts.count() == 1
    assert empty_alert_summary.related_alerts.count() == 1

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()

    # with related_alerts only
    test_perf_alert.delete()

    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()
    assert empty_alert_summary.alerts.count() == 0
    assert empty_alert_summary.related_alerts.count() == 1

    call_command('cycle_data', 'from:perfherder')
    assert PerformanceAlertSummary.objects.filter(id=empty_alert_summary.id).exists()


def test_stalled_data_removal(
    test_perf_signature, test_perf_signature_2, test_perf_data, test_perf_alert
):
    max_timestamp = datetime.now() - timedelta(days=120)
    test_perf_signature.last_updated = max_timestamp - timedelta(days=1)
    test_perf_signature.save()
    test_perf_signature_2.last_updated = max_timestamp
    test_perf_signature_2.save()

    push = Push.objects.first()
    seg2_data = PerformanceDatum.objects.create(
        repository=test_perf_signature_2.repository,
        push=push,
        job=None,
        signature=test_perf_signature_2,
        push_timestamp=datetime.now(),
        value=1.0,
    )

    assert test_perf_signature in PerformanceSignature.objects.filter(
        last_updated__lt=max_timestamp
    )

    call_command('cycle_data', 'from:perfherder')

    assert test_perf_signature not in PerformanceSignature.objects.all()
    assert test_perf_data not in PerformanceDatum.objects.all()
    assert test_perf_alert not in PerformanceAlert.objects.all()
    assert test_perf_signature_2 in PerformanceSignature.objects.all()
    assert seg2_data in PerformanceDatum.objects.all()


@pytest.mark.parametrize(
    'nr_months, repository',
    [(8, 'autoland'), (6, 'autoland'), (5, 'mozilla-central')],
)
def test_equal_distribution_for_historical_data(
    test_repository,
    test_stalled_data_signature,
    test_perf_data,
    nr_months,
    repository,
):
    test_repository.name = repository
    test_repository.save()

    # Add 120 more days to timestamp because the concept of
    # historical data is only for stalled data
    timestamp = datetime.now() - timedelta(days=(nr_months * 30 + 120))
    perf_signature = test_stalled_data_signature

    push = Push.objects.first()
    perf_data = []
    data_points_count = 2 * nr_months

    # Prepare test data: add two performance data points per month
    for i in range(0, data_points_count):
        if i % 2 == 0:
            timestamp += timedelta(days=30)

        data = PerformanceDatum.objects.create(
            repository=perf_signature.repository,
            push=push,
            job=None,
            signature=perf_signature,
            push_timestamp=timestamp,
            value=1.0,
        )
        perf_data.append(data)

    call_command('cycle_data', 'from:perfherder')

    assert PerformanceSignature.objects.filter(id=perf_signature.id).exists()
    all_perf_datum = PerformanceDatum.objects.all()
    for data_point in perf_data:
        assert data_point in all_perf_datum


@pytest.mark.parametrize(
    'nr_months, repository',
    [(8, 'autoland'), (6, 'autoland'), (5, 'mozilla-central')],
)
def test_big_density_in_historical_data(
    test_repository,
    test_stalled_data_signature,
    test_perf_data,
    nr_months,
    repository,
):
    test_repository.name = repository
    test_repository.save()

    # Add 120 more days to timestamp because the concept of
    # historical data is only for stalled data
    timestamp = datetime.now() - timedelta(days=(nr_months * 30 + 120))
    perf_signature = test_stalled_data_signature

    push = Push.objects.first()
    perf_data = []
    data_points_count = 2 * nr_months

    # Prepare test data: add one data point per month
    for i in range(0, nr_months):
        timestamp += timedelta(days=30)

        data = PerformanceDatum.objects.create(
            repository=perf_signature.repository,
            push=push,
            job=None,
            signature=perf_signature,
            push_timestamp=timestamp,
            value=1.0,
        )
        perf_data.append(data)

    # Prepare test data: add the remaining data points to the last month which has data
    for i in range(0, (data_points_count - nr_months)):
        data = PerformanceDatum.objects.create(
            repository=perf_signature.repository,
            push=push,
            job=None,
            signature=perf_signature,
            push_timestamp=timestamp,
            value=1.0,
        )
        perf_data.append(data)

    call_command('cycle_data', 'from:perfherder')

    assert PerformanceSignature.objects.filter(id=perf_signature.id).exists()
    all_perf_datum = PerformanceDatum.objects.all()
    for data_point in perf_data:
        assert data_point in all_perf_datum


@pytest.mark.parametrize(
    'nr_months, repository',
    [(5, 'autoland'), (8, 'mozilla-central'), (11, 'mozilla-central')],
)
def test_one_month_worth_of_data_points(
    test_repository,
    test_stalled_data_signature,
    test_perf_data,
    nr_months,
    repository,
):
    assert nr_months >= 1  # as well need to subtract its start
    covered_month_start = nr_months - 1

    test_repository.name = repository
    test_repository.save()

    stalled_signature = test_stalled_data_signature
    timestamp = datetime.now() - timedelta(days=covered_month_start * 30)

    push = Push.objects.first()
    perf_data = []

    # Prepare test data: add data points to the parametrize month
    for i in range(0, 15):
        data = PerformanceDatum.objects.create(
            repository=stalled_signature.repository,
            push=push,
            job=None,
            signature=stalled_signature,
            push_timestamp=timestamp,
            value=1.0,
        )
        perf_data.append(data)

    timestamp += timedelta(days=30)
    data = PerformanceDatum.objects.create(
        repository=stalled_signature.repository,
        push=push,
        job=None,
        signature=stalled_signature,
        push_timestamp=timestamp,
        value=1.0,
    )
    perf_data.append(data)

    call_command('cycle_data', 'from:perfherder')

    stalled_signature.refresh_from_db()
    assert PerformanceSignature.objects.filter(id=stalled_signature.id).exists()
    all_perf_datum = PerformanceDatum.objects.all()
    for data_point in perf_data:
        assert data_point in all_perf_datum


@pytest.mark.parametrize(
    'nr_months, repository',
    [(8, 'autoland'), (6, 'autoland'), (5, 'mozilla-central')],
)
def test_non_historical_stalled_data_is_removed(
    test_repository,
    test_stalled_data_signature,
    test_perf_data,
    nr_months,
    repository,
):
    test_repository.name = repository
    test_repository.save()

    # Add 120 more days to timestamp because the concept of
    # historical data is only for stalled data
    timestamp = datetime.now() - timedelta(days=(nr_months * 30 + 120))
    perf_signature = test_stalled_data_signature

    push = Push.objects.first()
    perf_data = []
    data_points_count = nr_months

    # Prepare test data: add one performance datum per month,
    # not enough data to meet the condition for historical value
    for i in range(0, data_points_count):
        timestamp += timedelta(days=30)

        data = PerformanceDatum.objects.create(
            repository=perf_signature.repository,
            push=push,
            job=None,
            signature=perf_signature,
            push_timestamp=timestamp,
            value=1.0,
        )
        perf_data.append(data)

    call_command('cycle_data', 'from:perfherder')

    assert not PerformanceSignature.objects.filter(id=perf_signature.id).exists()
    all_perf_datum = PerformanceDatum.objects.all()
    for data_point in perf_data:
        assert data_point not in all_perf_datum


def test_try_data_removal_errors_out_on_missing_try_data(try_repository):
    try_removal_strategy = TryDataRemoval(10000)

    with pytest.raises(LookupError):  # as we don't have data from try repository
        _ = try_removal_strategy.target_signatures


@patch('treeherder.config.settings.SITE_HOSTNAME', 'treeherder-production.com')
@pytest.mark.parametrize('days', [5, 30, 100, 364])
def test_explicit_days_validation_on_all_envs(days):
    with pytest.raises(ValueError):
        _ = PerfherderCycler(10_000, 0, days=days)

    with pytest.raises(ValueError):
        _ = MainRemovalStrategy(10_000, days=days)

    with pytest.raises(ValueError):
        _ = TryDataRemoval(10_000, days=days)

    with pytest.raises(ValueError):
        _ = IrrelevantDataRemoval(10_000, days=days)

    with pytest.raises(ValueError):
        _ = StalledDataRemoval(10_000, days=days)


def test_deleting_performance_data_cascades_to_perf_multicomit_data(test_perf_data):
    perf_datum = test_perf_data[0]
    MultiCommitDatum.objects.create(perf_datum=perf_datum)

    assert MultiCommitDatum.objects.count() == 1

    try:
        cursor = connection.cursor()
        cursor.execute(
            '''
            DELETE FROM `performance_datum`
            WHERE id = %s
            ''',
            [perf_datum.id],
        )
    except IntegrityError:
        pytest.fail()
    finally:
        cursor.close()

    assert MultiCommitDatum.objects.count() == 0


def test_alerts_older_than_a_year_are_removed_even_if_signature_is_active(test_perf_alert):
    # alert (fixture) comes pre linked to an active signature
    test_perf_alert.created = datetime.now() - timedelta(days=365)
    test_perf_alert.save()

    PerfherderCycler(10_000, 0).cycle()

    assert not PerformanceAlert.objects.filter(id=test_perf_alert.id).exists()


def test_empty_backfill_reports_get_removed(empty_backfill_report):
    empty_backfill_report.created = datetime.now() - timedelta(days=120)
    empty_backfill_report.save()

    PerfherderCycler(10_000, 0).cycle()

    assert BackfillReport.objects.count() == 0


@pytest.mark.parametrize('days_since_created', [0, 30, 100])
def test_empty_backfill_reports_arent_removed_if_not_enough_time_passed(
    empty_backfill_report, days_since_created
):
    empty_backfill_report.created = datetime.now() - timedelta(days=days_since_created)
    empty_backfill_report.save()

    PerfherderCycler(10_000, 0).cycle()

    assert BackfillReport.objects.filter(summary_id=empty_backfill_report.summary_id).exists()
