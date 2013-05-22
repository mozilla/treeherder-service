import json
from ..sample_data_generator import job_json, job_data
from ..sampledata import SampleData
from treeherder.log_parser.logparsecollection import LogParseCollection
from treeherder.model import utils

import urllib2

"""
    will need tests with:
        multiple log references
        artifacts with logs
"""


def do_job_ingestion(jm, job_data):
    """
    Ingest ``job_data`` which will be JSON job blobs.

    setup code to test the log parser.
    """
    jobs = []
    starttime = utils.get_now_timestamp()
    for blob in job_data:
        jm.store_job_data(json.dumps(blob))
        jobs = jm.process_objects(1)
        assert len(jobs) == 1, "Blob:\n{0}\n\nError:\n{1}".format(
            blob,
            jm.get_os_errors(starttime, utils.get_now_timestamp()
        ))

    complete_count = jm.get_os_dhub().execute(
        proc="objectstore_test.counts.complete")[0]["complete_count"]
    loading_count = jm.get_os_dhub().execute(
        proc="objectstore_test.counts.loading")[0]["loading_count"]

    assert complete_count == len(job_data)
    assert loading_count == 0

    return jobs


def test_single_log_header(jm, initial_data, monkeypatch):
    """Process a job with a single log reference."""

    def mock_log_handle(mockself, url):
        """Opens the log as a file, rather than a url"""
        return open(SampleData().get_log_path(url))

    monkeypatch.setattr(LogParseCollection, 'get_log_handle', mock_log_handle)

    name = "unittest",
    url = "mozilla-central_ubuntu32_vm_test-crashtest-ipc-bm67-tests1-linux-build18.txt.gz"

    lpm = LogParseCollection(url, name)
    lpm.parse()
    act = lpm.artifacts["unittest"]["header"]
    exp = {
        "slave": "tst-linux32-ec2-137",
        "buildid": "20130513091541",
        "builder": "mozilla-central_ubuntu32_vm_test-crashtest-ipc",
        "results": "success (0)",
        "starttime": "1368466076.01",
        "builduid": "acddb5f7043c4d5b9f66619f9433cab0",
        "revision": "c80dc6ffe865"
    }
    assert act == exp, json.dumps(lpm.artifacts["unittest"]["header"], indent=4)


def xtest_download_logs(sample_data):
    """
    http://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-win32/1367008984/mozilla-central_win8_test-dirtypaint-bm74-tests1-windows-build6.txt.gz
    """
    lognames = []
    for job in sample_data.job_data:
        logrefs = job["job"]["log_references"]
        for log in logrefs:
            lognames.append(log["name"])
            url = log["url"]
            try:
                handle = urllib2.urlopen(url)
                with open(url.rsplit("/", 1)[1], "wb") as out:
                    while True:
                        data = handle.read(1024)
                        if len(data) == 0: break
                        out.write(data)
            except urllib2.HTTPError:
                pass

    assert set(lognames) == ""
