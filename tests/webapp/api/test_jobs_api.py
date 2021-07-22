import datetime

import pytest
from dateutil import parser
from django.urls import reverse
from rest_framework.status import HTTP_400_BAD_REQUEST

from treeherder.model.models import Job, TextLogError


@pytest.mark.parametrize(
    ('offset', 'count', 'expected_num'),
    [(None, None, 10), (None, 5, 5), (5, None, 6), (0, 5, 5), (10, 10, 1)],
)
def test_job_list(client, eleven_jobs_stored, test_repository, offset, count, expected_num):
    """
    test retrieving a list of json blobs from the jobs-list
    endpoint.
    """
    url = reverse("jobs-list", kwargs={"project": test_repository.name})
    params = '&'.join(
        ['{}={}'.format(k, v) for k, v in [('offset', offset), ('count', count)] if v]
    )
    if params:
        url += '?{}'.format(params)
    resp = client.get(url)
    assert resp.status_code == 200
    response_dict = resp.json()
    jobs = response_dict["results"]
    assert isinstance(jobs, list)
    assert len(jobs) == expected_num
    exp_keys = [
        "submit_timestamp",
        "start_timestamp",
        "push_id",
        "result_set_id",
        "who",
        "option_collection_hash",
        "reason",
        "id",
        "job_guid",
        "state",
        "result",
        "build_platform_id",
        "end_timestamp",
        "build_platform",
        "machine_name",
        "job_group_id",
        "job_group_symbol",
        "job_group_name",
        "job_type_id",
        "job_type_name",
        "job_type_description",
        "build_architecture",
        "build_system_type",
        "job_type_symbol",
        "platform",
        "job_group_description",
        "platform_option",
        "machine_platform_os",
        "build_os",
        "machine_platform_architecture",
        "failure_classification_id",
        "tier",
        "last_modified",
        "ref_data_name",
        "signature",
        "task_id",
        "retry_id",
    ]
    for job in jobs:
        assert set(job.keys()) == set(exp_keys)


def test_job_list_bad_project(client, transactional_db):
    """
    test retrieving a job list with a bad project throws 404.
    """
    badurl = reverse("jobs-list", kwargs={"project": "badproject"})

    resp = client.get(badurl)
    assert resp.status_code == 404


def test_job_list_equals_filter(client, eleven_jobs_stored, test_repository):
    """
    test retrieving a job list with a querystring filter.
    """
    url = reverse("jobs-list", kwargs={"project": test_repository.name})
    final_url = url + "?job_guid=f1c75261017c7c5ce3000931dce4c442fe0a1297"

    resp = client.get(final_url)
    assert resp.status_code == 200
    assert len(resp.json()['results']) == 1


job_filter_values = [
    (u'build_architecture', u'x86_64'),
    (u'build_os', u'mac'),
    (u'build_platform', u'osx-10-7'),
    (u'build_platform_id', 3),
    (u'build_system_type', u'buildbot'),
    (u'end_timestamp', 1384364849),
    (u'failure_classification_id', 1),
    (u'id', 4),
    (u'job_group_id', 2),
    (u'job_group_name', u'Mochitest'),
    (u'job_group_symbol', u'M'),
    (u'job_guid', u'ab952a4bbbc74f1d9fb3cf536073b371029dbd02'),
    (u'job_type_id', 2),
    (u'job_type_name', u'Mochitest Browser Chrome'),
    (u'job_type_symbol', u'bc'),
    (u'machine_name', u'talos-r4-lion-011'),
    (u'machine_platform_architecture', u'x86_64'),
    (u'machine_platform_os', u'mac'),
    (u'option_collection_hash', u'32faaecac742100f7753f0c1d0aa0add01b4046b'),
    (u'platform', u'osx-10-7'),
    (u'reason', u'scheduler'),
    (
        u'ref_data_name',
        u'Rev4 MacOSX Lion 10.7 mozilla-release debug test mochitest-browser-chrome',
    ),
    (u'result', u'success'),
    (u'result_set_id', 4),
    (u'signature', u'aebe9066ff1c765815ec0513a3389238c80ef166'),
    (u'start_timestamp', 1384356880),
    (u'state', u'completed'),
    (u'submit_timestamp', 1384356854),
    (u'tier', 1),
    (u'who', u'tests-mozilla-release-lion-debug-unittest'),
]


@pytest.mark.parametrize(('fieldname', 'expected'), job_filter_values)
def test_job_list_filter_fields(client, eleven_jobs_stored, test_repository, fieldname, expected):
    """
    test retrieving a job list with a querystring filter.

    values chosen above are from the 3rd of the ``eleven_stored_jobs`` so that
    we aren't just getting the first one every time.

    The field of ``last_modified`` is auto-generated, so just skipping that
    to make this test easy.
    """
    url = reverse("jobs-list", kwargs={"project": test_repository.name})
    final_url = url + "?{}={}".format(fieldname, expected)
    resp = client.get(final_url)
    assert resp.status_code == 200
    first = resp.json()['results'][0]
    assert first[fieldname] == expected


def test_job_list_in_filter(client, eleven_jobs_stored, test_repository):
    """
    test retrieving a job list with a querystring filter.
    """
    url = reverse("jobs-list", kwargs={"project": test_repository.name})
    final_url = url + (
        "?job_guid__in="
        "f1c75261017c7c5ce3000931dce4c442fe0a1297,"
        "9abb6f7d54a49d763c584926377f09835c5e1a32"
    )

    resp = client.get(final_url)
    assert resp.status_code == 200
    assert len(resp.json()['results']) == 2


def test_job_detail(client, test_job):
    """
    test retrieving a single job from the jobs-detail
    endpoint.
    """
    resp = client.get(
        reverse("jobs-detail", kwargs={"project": test_job.repository.name, "pk": test_job.id})
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
    assert resp.json()["id"] == test_job.id

    resp = client.get(
        reverse("jobs-detail", kwargs={"project": test_job.repository.name, "pk": test_job.id})
    )
    assert resp.status_code == 200
    assert resp.json()["taskcluster_metadata"] == {
        "task_id": 'V3SVuxO8TFy37En_6HcXLs',
        "retry_id": 0,
    }


def test_job_detail_bad_project(client, transactional_db):
    """
    test retrieving a single job from the jobs-detail
    endpoint.
    """
    badurl = reverse("jobs-detail", kwargs={"project": "badproject", "pk": 1})
    resp = client.get(badurl)
    assert resp.status_code == 404


def test_job_detail_not_found(client, test_repository):
    """
    test retrieving a HTTP 404 from the jobs-detail
    endpoint.
    """
    resp = client.get(
        reverse("jobs-detail", kwargs={"project": test_repository.name, "pk": -32767}),
    )
    assert resp.status_code == 404


def test_text_log_errors(client, test_job):

    TextLogError.objects.create(job=test_job, line='failure 1', line_number=101)
    TextLogError.objects.create(job=test_job, line='failure 2', line_number=102)
    resp = client.get(
        reverse(
            "jobs-text-log-errors", kwargs={"project": test_job.repository.name, "pk": test_job.id}
        )
    )
    assert resp.status_code == 200
    assert resp.json() == [
        {
            'id': 1,
            'job': 1,
            'line': 'failure 1',
            'line_number': 101,
            'bug_suggestions': {
                'search': 'failure 1',
                'path_end': None,
                'search_terms': ['failure 1'],
                'bugs': {'open_recent': [], 'all_others': []},
                'line_number': 101,
            },
            'metadata': None,
            'matches': [],
            'classified_failures': [],
        },
        {
            'id': 2,
            'job': 1,
            'line': 'failure 2',
            'line_number': 102,
            'bug_suggestions': {
                'search': 'failure 2',
                'path_end': None,
                'search_terms': ['failure 2'],
                'bugs': {'open_recent': [], 'all_others': []},
                'line_number': 102,
            },
            'metadata': None,
            'matches': [],
            'classified_failures': [],
        },
    ]


@pytest.mark.parametrize(
    ('offset', 'count', 'expected_num'),
    [(None, None, 3), (None, 2, 2), (1, None, 2), (0, 1, 1), (2, 10, 1)],
)
def test_list_similar_jobs(client, eleven_jobs_stored, offset, count, expected_num):
    """
    test retrieving similar jobs
    """
    job = Job.objects.get(id=1)

    url = reverse("jobs-similar-jobs", kwargs={"project": job.repository.name, "pk": job.id})
    params = '&'.join(
        ['{}={}'.format(k, v) for k, v in [('offset', offset), ('count', count)] if v]
    )
    if params:
        url += '?{}'.format(params)
    resp = client.get(url)

    assert resp.status_code == 200

    similar_jobs = resp.json()

    assert 'results' in similar_jobs

    assert isinstance(similar_jobs['results'], list)

    assert len(similar_jobs['results']) == expected_num


@pytest.mark.parametrize(
    'lm_key,lm_value,exp_status, exp_job_count',
    [
        ("last_modified__gt", "2016-07-18T22:16:58.000", 200, 8),
        ("last_modified__lt", "2016-07-18T22:16:58.000", 200, 3),
        ("last_modified__gt", "-Infinity", HTTP_400_BAD_REQUEST, 0),
        ("last_modified__gt", "whatever", HTTP_400_BAD_REQUEST, 0),
    ],
)
def test_last_modified(
    client, eleven_jobs_stored, test_repository, lm_key, lm_value, exp_status, exp_job_count
):
    try:
        param_date = parser.parse(lm_value)
        newer_date = param_date - datetime.timedelta(minutes=10)

        # modify job last_modified for 3 jobs
        Job.objects.filter(id__in=[j.id for j in Job.objects.all()[:3]]).update(
            last_modified=newer_date
        )
    except ValueError:
        # no problem.  these params are the wrong
        pass

    url = reverse("jobs-list", kwargs={"project": test_repository.name})
    final_url = url + ("?{}={}".format(lm_key, lm_value))

    resp = client.get(final_url)
    assert resp.status_code == exp_status
    if exp_status == 200:
        assert len(resp.json()["results"]) == exp_job_count
