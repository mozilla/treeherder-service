from django.db.models import Q

from treeherder.model.models import Push
from treeherder.perf.auto_perf_sheriffing.utils import Helper


def test_helper_identifies_pushes_in_range(
    record_backfilled, test_repository, test_repository_2, range_dates, outcome_checking_pushes
):
    # TODO: retarget this test to BackfillRecord.get_pushes_in_range()
    total_pushes = Push.objects.count()

    from_time = range_dates['from_date']
    to_time = range_dates['to_date']

    total_outside_pushes = Push.objects.filter(
        Q(repository=test_repository) & (Q(time__lt=from_time) | Q(time__gt=to_time))
    ).count()

    pushes_in_range = Helper.get_pushes_in_range(from_time, to_time, test_repository.id)
    assert len(pushes_in_range) == total_pushes - total_outside_pushes

    # change repository for the first 2 pushes in range
    assert test_repository.id != test_repository_2.id

    total_changed_pushes = 2
    for push in pushes_in_range[:total_changed_pushes]:
        push.repository = test_repository_2
        push.save()

    total_other_repo_pushes = Push.objects.filter(repository=test_repository_2).count()
    assert total_other_repo_pushes == total_changed_pushes

    updated_pushes_in_range = Helper.get_pushes_in_range(
        from_time, to_time, test_repository.id
    )

    assert len(updated_pushes_in_range) == len(pushes_in_range) - total_other_repo_pushes
