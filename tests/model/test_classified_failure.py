from decimal import Decimal

from tests.autoclassify.utils import (create_failure_lines,
                                      create_text_log_errors,
                                      test_line)
from treeherder.model.models import (ClassifiedFailure,
                                     FailureLine,
                                     FailureMatch)


def test_set_bug(classified_failures):
    rv = classified_failures[0].set_bug(1234)
    assert rv == classified_failures[0]
    assert classified_failures[0].bug_number == 1234


def test_set_bug_duplicate(failure_lines, classified_failures, test_matcher):
    classified_failures[0].bug_number = 1234
    classified_failures[0].save()
    match = failure_lines[0].matches.all()[0]
    match.score = 0.7
    match.save()
    # Add a FailureMatch that will have the same (failure_line_id, classified_failure_id)
    # as another FailureMatch when classified_failure[1] is replaced by classified_failure[0]
    duplicate_match = FailureMatch(
        failure_line=failure_lines[0],
        classified_failure=classified_failures[1],
        matcher=test_matcher.db_object,
        score=0.8)
    duplicate_match.save()
    assert len(failure_lines[0].matches.all()) == 2
    rv = classified_failures[1].set_bug(1234)
    assert rv == classified_failures[0]
    assert rv.bug_number == 1234
    for item in failure_lines:
        item.refresh_from_db()
    match.refresh_from_db()
    # Check that we updated the best classification that previously pointed
    # to the now-defunct classified_failures[0]
    assert failure_lines[1].best_classification == classified_failures[0]
    # Check that we only have one match for the first failure line
    matches = failure_lines[0].matches.all()
    assert len(matches) == 1
    # Check we picked the better of the two scores for the new match.
    assert matches[0].score == Decimal("0.8")
    # Ensure we deleted the ClassifiedFailure on which we tried to set the bug
    assert len(ClassifiedFailure.objects.filter(id=classified_failures[1].id)) == 0


def test_update_autoclassification_bug(test_job, test_job_2,
                                       classified_failures):
    # Job 1 has two failure lines so nothing should be updated
    assert test_job.update_autoclassification_bug(1234) is None

    failure_lines = create_failure_lines(test_job_2,
                                         [(test_line, {})])
    failure_lines[0].best_classification = classified_failures[0]
    failure_lines[0].save()
    classified_failures[0].bug_number = None
    lines = [(item, {}) for item in FailureLine.objects.filter(job_guid=test_job_2.guid).values()]
    create_text_log_errors(test_job_2, lines)

    assert test_job_2.update_autoclassification_bug(1234) == classified_failures[0]
    classified_failures[0].refresh_from_db()
    assert classified_failures[0].bug_number == 1234
