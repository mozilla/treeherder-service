import logging
import re
import newrelic.agent

from django.core.cache import cache

from treeherder.model.models import Bugscache, TextLogError

logger = logging.getLogger(__name__)


# the amount of time we cache bug suggestion lookups (to speed up loading the
# bug suggestions panel for recently finished jobs)
BUG_SUGGESTION_CACHE_TIMEOUT = 86400

LEAK_RE = re.compile(r'\d+ bytes leaked \((.+)\)$|leak at (.+)$')
CRASH_RE = re.compile(r'.+ application crashed \[@ (.+)\]$')
MOZHARNESS_RE = re.compile(r'^\d+:\d+:\d+[ ]+(?:DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL) - [ ]?')
PROCESS_ID_RE = re.compile(r"(?:PID \d+|GECKO\(\d+\)) \| +")
REFTEST_RE = re.compile(r'\s+[=!]=\s+.*')
PREFIX_PATTERN = r'^(TEST-UNEXPECTED-\S+|PROCESS-CRASH)\s+\|\s+'


def get_error_summary(job):
    """
    Create a list of bug suggestions for a job.

    Caches the results if there are any.
    """
    cache_key = 'error-summary-{}'.format(job.id)
    cached_error_summary = cache.get(cache_key)
    if cached_error_summary is not None:
        return cached_error_summary

    # don't cache or do anything if we have no text log errors to get
    # results for
    errors = TextLogError.objects.filter(job=job)
    if not errors:
        return []

    # cache terms generated from error line to save excessive querying
    term_cache = {}

    error_summary = [bug_suggestions_line(err, term_cache) for err in errors]

    try:
        cache.set(cache_key, error_summary, BUG_SUGGESTION_CACHE_TIMEOUT)
    except Exception as e:
        newrelic.agent.record_custom_event('error caching error_summary for job', job.id)
        logger.error('error caching error_summary for job %s: %s', job.id, e, exc_info=True)

    return error_summary


def bug_suggestions_line(err, term_cache=None):
    """
    Get Bug suggestions for a given TextLogError (err).

    Tries to extract a search term from a clean version of the given error's
    line.  We build a search term from the cleaned line and use that to search
    for bugs.  Returns a dictionary with the cleaned line, the generated search
    term, and any bugs found with said search term.
    """
    if term_cache is None:
        term_cache = {}

    # remove the mozharness prefix
    clean_line = get_cleaned_line(err.line)

    # get a meaningful search term out of the error line
    search_info = get_error_search_term_and_path(clean_line)
    search_term = search_info["search_term"]
    path_end = search_info["path_end"]
    bugs = dict(open_recent=[], all_others=[])

    # collect open recent and all other bugs suggestions
    search_terms = []
    if search_term:
        search_terms.append(search_term)
        if search_term not in term_cache:
            term_cache[search_term] = Bugscache.search(search_term)
        bugs = term_cache[search_term]

    if not bugs or not (bugs['open_recent'] or bugs['all_others']):
        # no suggestions, try to use
        # the crash signature as search term
        crash_signature = get_crash_signature(clean_line)
        if crash_signature:
            search_terms.append(crash_signature)
            if crash_signature not in term_cache:
                term_cache[crash_signature] = Bugscache.search(crash_signature)
            bugs = term_cache[crash_signature]

    # TODO: Rename 'search' to 'error_text' or similar, since that's
    # closer to what it actually represents (bug 1091060).
    return {
        "search": clean_line,
        "search_terms": search_terms,
        "path_end": path_end,
        "bugs": bugs,
        "line_number": err.line_number,
    }


def get_cleaned_line(line):
    """Strip possible mozharness bits from the given line."""
    line_to_clean = MOZHARNESS_RE.sub('', line).strip()
    return PROCESS_ID_RE.sub('', line_to_clean)


def get_error_search_term_and_path(error_line):
    """
    Generate a search term from the given error_line string.

    Attempt to build a search term that will yield meaningful results when used
    in a MySQL FTS query.
    """
    if not error_line:
        return None

    # This is strongly inspired by
    # https://hg.mozilla.org/webtools/tbpl/file/tip/php/inc/AnnotatedSummaryGenerator.php#l73

    tokens = error_line.split(" | ")
    search_term = None
    path_end = None

    if len(tokens) >= 3:
        # it's in the "FAILURE-TYPE | testNameOrFilePath | message" type format.
        test_name_or_path = tokens[1]
        message = tokens[2]
        # Leak failure messages are of the form:
        # leakcheck | .*\d+ bytes leaked (Object-1, Object-2, Object-3, ...)
        match = LEAK_RE.search(message)
        if match:
            search_term = match.group(1) if match.group(1) is not None else match.group(2)
        else:
            # For reftests, remove the reference path from the tokens as this is
            # not very unique
            test_name_or_path = REFTEST_RE.sub("", test_name_or_path).replace("\\", "/")
            path_end = test_name_or_path
            # if this is a path, we are interested in the last part
            search_term = test_name_or_path.split("/")[-1]

    # If the failure line was not in the pipe symbol delimited format or the search term
    # will likely return too many (or irrelevant) results (eg: too short or matches terms
    # on the blacklist), then we fall back to searching for the entire failure line if
    # it is suitable.
    if not (search_term and is_helpful_search_term(search_term)):
        if is_helpful_search_term(error_line):
            search_term = error_line
        else:
            search_term = None
            if path_end and "/" not in path_end:
                path_end = None

    # Searching for extremely long search terms is undesirable, since:
    # a) Bugzilla's max summary length is 256 characters, and once "Intermittent "
    # and platform/suite information is prefixed, there are even fewer characters
    # left for us to use for the failure string against which we need to match.
    # b) For long search terms, the additional length does little to prevent against
    # false positives, but means we're more susceptible to false negatives due to
    # run-to-run variances in the error messages (eg paths, process IDs).
    if search_term:
        search_term = re.sub(PREFIX_PATTERN, '', search_term)
        search_term = search_term[:100]

    return {
        "search_term": search_term,
        "path_end": path_end,
    }


def get_crash_signature(error_line):
    """Try to get a crash signature from the given error_line string."""
    search_term = None
    match = CRASH_RE.match(error_line)
    if match and is_helpful_search_term(match.group(1)):
        search_term = match.group(1)
    return search_term


def is_helpful_search_term(search_term):
    """
    Decide if the given search_term string is helpful or not.

    We define "helpful" here as search terms that won't match an excessive
    number of bug summaries.  Very short terms and those matching generic
    strings (listed in the blacklist) are deemed unhelpful since they wouldn't
    result in useful suggestions.
    """
    # Search terms that will match too many bug summaries
    # and so not result in useful suggestions.
    search_term = search_term.strip()

    blacklist = [
        'automation.py',
        'remoteautomation.py',
        'Shutdown',
        'undefined',
        'Main app process exited normally',
        'Traceback (most recent call last):',
        'Return code: 0',
        'Return code: 1',
        'Return code: 2',
        'Return code: 10',
        'mozalloc_abort(char const*)',
        'mozalloc_abort',
        'CrashingThread(void *)',
        'gtest',
        'Last test finished',
        'leakcheck',
        'LeakSanitizer',
        '# TBPL FAILURE #',
    ]

    return len(search_term) > 4 and search_term not in blacklist


def get_useful_search_results(job):
    """
    Filter error_summary dicts if their search term is deemed "helpful"
    """
    return [item for item in get_error_summary(job) if is_helpful_search_term(item["search"])]
