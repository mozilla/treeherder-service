#!/usr/bin/env python
""" Script to compare tasks from pushes on different Treeherder instances"""
import argparse
import logging
import pprint
import uuid

import slugid

from deepdiff import DeepDiff
from thclient import TreeherderClient

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
HOSTS = {
    "localhost": "http://localhost:8000",
    "stage": "https://treeherder.allizom.org",
    "production": "https://treeherder.mozilla.org",
}


def remove_some_attributes(job, production_job):
    # I belive these differences are expected since they are dependant to when the data
    # was inserted inside of the database
    del job["build_platform_id"]
    del job["id"]
    del job["job_group_id"]
    del job["job_type_id"]
    del job["last_modified"]
    del job["push_id"]
    del job["result_set_id"]
    del production_job["build_platform_id"]
    del production_job["id"]
    del production_job["job_group_id"]
    del production_job["job_type_id"]
    del production_job["last_modified"]
    del production_job["push_id"]
    del production_job["result_set_id"]

    if job.get("end_timestamp"):
        del job["end_timestamp"]
        del job["start_timestamp"]
        del production_job["end_timestamp"]
        del production_job["start_timestamp"]

    if job.get("failure_classification_id"):
        del job["failure_classification_id"]
        del production_job["failure_classification_id"]


def print_url_to_taskcluster(job_guid):
    job_guid = job["job_guid"]
    (decoded_task_id, _) = job_guid.split("/")
    # As of slugid v2, slugid.encode() returns a string not bytestring under Python 3.
    taskId = slugid.encode(uuid.UUID(decoded_task_id))
    logger.info("https://firefox-ci-tc.services.mozilla.com/tasks/%s", taskId)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Compare a push from a Treeherder instance to the production instance."
    )
    parser.add_argument(
        "--host", default="localhost", help="Host to compare. It defaults to localhost"
    )
    parser.add_argument("--revision", required=True, help="Revision to compare")
    parser.add_argument(
        "--project",
        default="mozilla-central",
        help="Project to compare. It defaults to mozilla-central",
    )

    args = parser.parse_args()

    th_instance = TreeherderClient(server_url=HOSTS[args.host])
    th_instance_pushid = th_instance.get_pushes(args.project, revision=args.revision)[0]["id"]
    th_instance_jobs = (
        th_instance.get_jobs(args.project, push_id=th_instance_pushid, count=None) or []
    )

    production = TreeherderClient(server_url=HOSTS["production"])
    production_pushid = production.get_pushes(args.project, revision=args.revision)[0]["id"]
    production_jobs = production.get_jobs(args.project, push_id=production_pushid, count=None)

    production_dict = {}
    for job in production_jobs:
        production_dict[job["job_guid"]] = job

    th_instance_dict = {}
    th_instance_not_found = []
    for job in th_instance_jobs:
        production_job = production_dict.get(job["job_guid"])
        if production_job is None:
            th_instance_not_found.append(job)
        else:
            # You can use this value in a url with &selectedJob=
            jobId = job["id"]
            remove_some_attributes(job, production_job)

            differences = DeepDiff(job, production_dict[job["job_guid"]])
            if differences:
                pprint.pprint(differences)
                logger.info(jobId)
            else:
                # Delete jobs that don"t have any differences
                del production_dict[job["job_guid"]]

    logger.info("We have found: %s jobs on %s instance.", len(th_instance_jobs), args.host)
    logger.info("We have found: %s jobs on the production instance.", len(production_jobs))

    if production_dict:
        logger.info(
            "There are the first 10 production jobs we do not have th_instancely. Follow the link to investigate."
        )
        for job in list(production_dict.values())[0:10]:
            print_url_to_taskcluster(job["job_guid"])

    if th_instance_not_found:
        logger.info("Number of jobs not found th_instancely: %s jobs", len(th_instance_not_found))
        for job in th_instance_not_found:
            print_url_to_taskcluster(job["job_guid"])

    if production_dict is None and th_instance_not_found is None:
        logger.info("We have not found any differences between the two pushes!! :D")
