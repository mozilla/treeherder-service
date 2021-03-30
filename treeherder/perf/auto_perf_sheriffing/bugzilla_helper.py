import logging
import re
from typing import List

import requests
from django.conf import settings
from requests.exceptions import RequestException

from treeherder.model.models import Push
from treeherder.perf.models import BackfillRecord, PerformanceDatum
from treeherder.perf.auto_perf_sheriffing.utils import Helper, PERF_SHERIFFS
from treeherder.perfalert.perfalert import detect_changes

logger = logging.getLogger(__name__)


class BugzillaBase:
    """Base class for standard bugzilla operations.

    TODO: Use this class in the intermittents_commenter.Commenter, and
    in the BugzillaViewSet.
    """
    def __init__(self):
        self.session = self._new_request()

    def submit_bug_changes(self, changes: dict, bug_id: int):
        """Submit chanages to a given bug number.

        The `changes` can include settings from anything in this list:
        https://bmo.readthedocs.io/en/latest/api/core/v1/bug.html#create-bug
        """
        url = '{}/rest/bug/{}'.format(settings.BZ_API_URL, str(bug_id))
        try:
            response = self.session.put(
                url, headers=self._get_comment_headers(), json=changes, timeout=30
            )
            response.raise_for_status()
        except RequestException as e:
            logger.error(f"Error posting comment to bugzilla for bug {bug_id} due to: {e}")

    def create_bug(self, params: dict) -> requests.Response:
        """Create a bugzilla bug with passed params."""

        if settings.BUGFILER_API_KEY is None:
            failure_response = requests.Response()
            failure_response.status_code = 400
            failure_response._content = b'{"failure" : "Bugzilla API key not set!"}'
            return failure_response

        description = params.get("description", "").encode("utf-8")
        summary = params.get("summary").encode("utf-8").strip()
        cc = str(params.get("cc")).encode("utf-8")

        data = {
            'type': params.get("type", "defect"),
            'product': params.get("product"),
            'component': params.get("component"),
            'summary': summary,
            "cc": cc,
            'regressed_by': params.get("regressed_by"),
            'version': params.get("version"),
            'severity': params.get("severity"),
            'priority': params.get("priority"),
            'description': description,
            'comment_tags': "treeherder",
        }

        for param in params:
            if param in data:
                continue
            data[param] = params[param]

        url = settings.BUGFILER_API_URL + "/rest/bug"
        try:
            response = self.session.put(url, headers=self._get_filing_headers(), json=data, timeout=60)
            response.raise_for_status()
        except RequestException as e:
            logger.error(f"Failed to create bug: {e}")

        return response

    def fetch_bug_details(self, bug_ids: List[int]) -> dict:
        """Fetches bug metadata from bugzilla and returns an encoded
        dict if successful, otherwise returns None."""
        params = {'include_fields': 'product, component, priority, whiteboard, id'}
        params['id'] = bug_ids
        try:
            response = self.session.get(
                settings.BZ_API_URL + '/rest/bug',
                headers=self.session.headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except RequestException as e:
            logger.warning(f"Failed fetching bugzilla metadata for bugs due to: {e}")
            return None

        if response.headers['Content-Type'] == 'text/html; charset=UTF-8':
            return None

        data = response.json()
        if 'bugs' not in data:
            return None

        return data['bugs']

    def fetch_all_bug_details(self, bug_ids: List[int]) -> dict:
        """Batch requests for bugzilla data in groups of 1200 (which is the safe
        limit for not hitting the max url length)"""
        min = 0
        max = 600
        bugs_list = []
        bug_ids_length = len(bug_ids)

        while bug_ids_length >= min and bug_ids_length > 0:
            data = self.fetch_bug_details(bug_ids[min:max])
            if data:
                bugs_list += data
            min = max
            max = max + 600

        return {bug['id']: bug for bug in bugs_list} if len(bugs_list) else None

    def _new_request(self) -> requests.Session:
        session = requests.Session()
        # Use a custom HTTP adapter, so we can set a non-zero max_retries value.
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=3))
        return session

    def _get_comment_headers(self) -> dict:
        return {
            'User-Agent': 'treeherder/{}'.format(settings.SITE_HOSTNAME),
            'x-bugzilla-api-key': settings.COMMENTER_API_KEY,
            'Accept': 'application/json',
        }

    def _get_filing_headers(self) -> dict:
        return {
            'User-Agent': 'treeherder/{}'.format(settings.SITE_HOSTNAME),
            'x-bugzilla-api-key': settings.BUGFILER_API_KEY,
            'Accept': 'application/json',
        }

    def _set_comment_headers(self):
        if not self.session:
            return
        self.session.headers = self._get_comment_headers()

    def _set_filing_headers(self):
        if not self.session:
            return
        self.session.headers = self._get_filing_headers()


class BugzillaHelper(BugzillaBase):
    """Contains methods for making bugzilla comments, getting bug
    information, and filing bugs (among other things)."""

    def __init__(self):
        super(BugzillaHelper, self).__init__()

    def create_alert_comment(self, changes: dict, bug_id: str):
        # TODO: Handle perf-alert formatting and settings
        self.submit_bug_changes(changes, bug_id)

    def create_alert_bug(self, push: Push, base_params: dict) -> requests.Response:
        """Create a bug for an alert.

        The push is used to get information on the culprit from HGMO which
        allows us to file the bug in the right place and attach the alert
        to the right bug. The `base_params` argument can be used to specify
        extra fields in the bug creation.
        """
        revision = push.revision
        hgmo_info = Helper.get_hgmo_bug_info(push.repository.name, revision)

        desc = hgmo_info["description"]
        logger.info(desc)
        bug_number = re.match(r"""Bug\s(\d*)[\s,]""", desc).groups(1)[0]
        author_email = re.match(r""".*\s<(.*)>""", hgmo_info["user"]).groups(1)[0]

        bug_details = self.fetch_bug_details([bug_number])[0]
        params = {
            "product": bug_details["product"],
            "component": bug_details["component"],
            "regressed_by": bug_number,
            "type": base_params.get("type", "defect"),
            "severity": base_params.get("severity", "S3"),
            "priority": base_params.get("priority", "P5"),
            "version": base_params.get("version", "unspecified"),
            "cc": PERF_SHERIFFS + [author_email],
            "summary": f"Performance alert in commit {revision} from bug {bug_number}",
            # TODO: Use a template here
            "description": "Alerting authors!"
        }

        for param in base_params:
            params.setdefault(param, base_params[param])

        return self.create_bug(params)
