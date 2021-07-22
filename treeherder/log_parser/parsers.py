import json
import logging
import re

import jsonschema
from django.conf import settings

from treeherder.log_parser.utils import validate_perf_data

logger = logging.getLogger(__name__)


class ParserBase:
    """
    Base class for all parsers.

    """

    def __init__(self, name):
        """Setup the artifact to hold the extracted data."""
        self.name = name
        self.clear()

    def clear(self):
        """Reset this parser's values for another run."""
        self.artifact = []
        self.complete = False

    def parse_line(self, line, lineno):
        """Parse a single line of the log"""
        raise NotImplementedError  # pragma no cover

    def finish_parse(self, last_lineno_seen):
        """Clean-up/summary tasks run at the end of parsing."""
        pass

    def get_artifact(self):
        """By default, just return the artifact as-is."""
        return self.artifact


class ErrorParser(ParserBase):
    """A generic error detection sub-parser"""

    IN_SEARCH_TERMS = (
        "TEST-UNEXPECTED-",
        "fatal error",
        "FATAL ERROR",
        "Hit MOZ_CRASH",
        "REFTEST ERROR",
        "PROCESS-CRASH",
        "Assertion fail",
        "###!!! ABORT:",
        "SUMMARY: AddressSanitizer",
        "SUMMARY: ThreadSanitizer",
        "SUMMARY: UndefinedBehaviorSanitizer",
        "ThreadSanitizer: nested bug",
        "Automation Error:",
        "command timed out:",
        "wget: unable ",
        "bash.exe: *** ",
        "Unsuccessful task run with exit code: 137",
        "YOU ARE LEAKING THE WORLD",
    )

    RE_ERR_MATCH = re.compile(
        (
            r"^g?make(?:\[\d+\])?: \*\*\*"
            r"|^[A-Za-z.]+Error: "
            r"|^[A-Za-z.]*Exception: "
            r"|^\[  FAILED  \] "
            r"|^remoteFailed:"
            r"|^rm: cannot "
            r"|^abort:"
            r"|^\[taskcluster\] Error:"
            r"|^\[[\w._-]+:(?:error|exception)\]"
        )
    )

    RE_ERR_SEARCH = re.compile(
        (
            r" error\(\d*\):"
            r"|:\d+: error:"
            r"| error R?C\d*:"
            r"|ERROR [45]\d\d:"
            r"|mozmake\.(?:exe|EXE)(?:\[\d+\])?: \*\*\*"
        )
    )

    RE_EXCLUDE_1_SEARCH = re.compile(r"TEST-(?:INFO|PASS) ")

    RE_EXCLUDE_2_SEARCH = re.compile(
        r"I[ /](Gecko|TestRunner).*TEST-UNEXPECTED-"
        r"|^TimeoutException: "
        r"|^ImportError: No module named pygtk$"
        r"|^non-fatal error"
    )

    RE_ERR_1_MATCH = re.compile(r"^\d+:\d+:\d+ +(?:ERROR|CRITICAL|FATAL) - ")

    # Looks for a leading value inside square brackets containing a "YYYY-"
    # year pattern but isn't a TaskCluster error indicator (like
    # ``taskcluster:error``.
    #
    # This matches the following:
    #   [task 2016-08-18T17:50:56.955523Z]
    #   [2016- task]
    #
    # But not:
    #   [taskcluster:error]
    #   [taskcluster:something 2016-]
    RE_TASKCLUSTER_NORMAL_PREFIX = re.compile(r"^\[(?!taskcluster:)[^\]]*20\d{2}-[^\]]+\]\s")

    RE_MOZHARNESS_PREFIX = re.compile(r"^\d+:\d+:\d+ +(?:DEBUG|INFO|WARNING) - +")

    def __init__(self):
        """A simple error detection sub-parser"""
        super().__init__("errors")
        self.is_taskcluster = False

    def add(self, line, lineno):
        self.artifact.append({"linenumber": lineno, "line": line.rstrip()})

    def parse_line(self, line, lineno):
        """Check a single line for an error.  Keeps track of the linenumber"""

        if len(self.artifact) >= settings.MAX_ERROR_LINES:
            return
        # TaskCluster logs are a bit wonky.
        #
        # TaskCluster logs begin with output coming from TaskCluster itself,
        # before it has transitioned control of the task to the configured
        # process. These "internal" logs look like the following:
        #
        #   [taskcluster 2016-09-09 17:41:43.544Z] Worker Group: us-west-2b
        #
        # If an error occurs during this "setup" phase, TaskCluster may emit
        # lines beginning with ``[taskcluster:error]``.
        #
        # Once control has transitioned from TaskCluster to the configured
        # task process, lines can be whatever the configured process emits.
        # The popular ``run-task`` wrapper prefixes output to emulate
        # TaskCluster's "internal" logs. e.g.
        #
        #   [vcs 2016-09-09T17:45:02.842230Z] adding changesets
        #
        # This prefixing can confuse error parsing. So, we strip it.
        #
        # Because regular expression matching and string manipulation can be
        # expensive when performed on every line, we only strip the TaskCluster
        # log prefix if we know we're in a TaskCluster log.

        # First line of TaskCluster logs almost certainly has this.
        if line.startswith('[taskcluster '):
            self.is_taskcluster = True

        # For performance reasons, only do this if we have identified as
        # a TC task.
        if self.is_taskcluster:
            line = re.sub(self.RE_TASKCLUSTER_NORMAL_PREFIX, "", line)

        if self.is_error_line(line) and (
            len(self.artifact) == 0 or self.artifact[-1]["line"] != line.rstrip()
        ):
            self.add(line, lineno)

    def is_error_line(self, line):
        if self.RE_EXCLUDE_1_SEARCH.search(line):
            return False

        if self.RE_ERR_1_MATCH.match(line):
            return True

        # Remove mozharness prefixes prior to matching
        trimline = re.sub(self.RE_MOZHARNESS_PREFIX, "", line).rstrip()
        if self.RE_EXCLUDE_2_SEARCH.search(trimline):
            return False

        return bool(
            any(term for term in self.IN_SEARCH_TERMS if term in trimline)
            or self.RE_ERR_MATCH.match(trimline)
            or self.RE_ERR_SEARCH.search(trimline)
        )


class PerformanceParser(ParserBase):
    """a sub-parser to find generic performance data"""

    # Using $ in the regex as an end of line bounds causes the
    # regex to fail on windows logs. This is likely due to the
    # ^M character representation of the windows end of line.
    RE_PERFORMANCE = re.compile(r'.*?PERFHERDER_DATA:\s+({.*})')

    def __init__(self):
        super().__init__("performance_data")

    def parse_line(self, line, lineno):
        match = self.RE_PERFORMANCE.match(line)
        if match:
            try:
                data = json.loads(match.group(1))
                if not bool(data):
                    raise EmptyPerformanceData("The perf data is empty.")
                validate_perf_data(data)
                self.artifact.append(data)
            except ValueError:
                logger.warning("Unable to parse Perfherder data from line: %s", line)
            except jsonschema.ValidationError as e:
                logger.warning(
                    "Perfherder line '%s' does not comply with " "json schema: %s", line, e
                )

            # Don't mark the parser as complete, in case there are multiple performance artifacts.


class EmptyPerformanceData(Exception):
    pass
