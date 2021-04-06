import pytest

from tests.test_utils import add_log_response
from treeherder.etl.jobs import store_job_data
from treeherder.etl.push import store_push_data
from treeherder.model.error_summary import get_error_summary
from treeherder.model.models import Job, TextLogError

from ..sampledata import SampleData


@pytest.fixture
def jobs_with_local_log(activate_responses):
    sample_data = SampleData()
    url = add_log_response(
        "mozilla-inbound_ubuntu64_vm-debug_test-mochitest-other-bm53-tests1-linux-build122.txt.gz"
    )

    job = sample_data.job_data[0]

    # substitute the log url with a local url
    job['job']['log_references'][0]['url'] = url
    return [job]


def test_create_error_summary(
    failure_classifications, jobs_with_local_log, sample_push, test_repository
):
    """
    check that a bug suggestions artifact gets inserted when running
    a parse_log task for a failed job, and that the number of
    bug search terms/suggestions matches the number of error lines.
    """
    store_push_data(test_repository, sample_push)

    jobs = jobs_with_local_log
    for job in jobs:
        job['job']['result'] = "testfailed"
        job['revision'] = sample_push[0]['revision']

    store_job_data(test_repository, jobs)

    bug_suggestions = get_error_summary(Job.objects.get(id=1))

    # we must have one bugs item per error in bug_suggestions.
    # errors with no bug suggestions will just have an empty
    # bugs list
    assert TextLogError.objects.count() == len(bug_suggestions)

    # We really need to add some tests that check the values of each entry
    # in bug_suggestions, but for now this is better than nothing.
    expected_keys = set(["search", "path_end", "search_terms", "bugs", "line_number"])
    for failure_line in bug_suggestions:
        assert set(failure_line.keys()) == expected_keys
