# -*- coding: utf-8 -*-
import inspect
import logging

from django.db.utils import IntegrityError
from first import first

from treeherder.model.models import (Job,
                                     JobNote,
                                     TextLogError,
                                     TextLogErrorMatch)

logger = logging.getLogger(__name__)

# The minimum goodness of match we need to mark a particular match as the best match
AUTOCLASSIFY_CUTOFF_RATIO = 0.7
# A goodness of match after which we will not run further detectors
AUTOCLASSIFY_GOOD_ENOUGH_RATIO = 0.9


def get_matchers():
    """
    Get matcher functions from treeherder.autoclassify.matchers

    We classify matchers as any function treeherder.autoclassify.matchers with
    a name ending in _matcher.  This is currently overkill but protects against
    the unwarey engineer adding new functions to the matchers module that
    shouldn't be treated as matchers.
    """
    from . import matchers

    def is_matcher_func(member):
        return inspect.isfunction(member) and member.__name__.endswith("_matcher")

    members = inspect.getmembers(matchers, is_matcher_func)

    for name, func in members:
        yield func


def match_errors(job, matchers=None):
    # Only try to autoclassify where we have a failure status; sometimes there can be
    # error lines even in jobs marked as passing.

    if job.autoclassify_status < Job.CROSSREFERENCED:
        logger.error("Tried to autoclassify job %i without crossreferenced error lines", job.id)
        return

    if job.autoclassify_status == Job.AUTOCLASSIFIED:
        logger.error("Tried to autoclassify job %i which was already autoclassified", job.id)
        return

    if job.result not in ["testfailed", "busted", "exception"]:
        return

    all_errors = set(TextLogError.objects.filter(step__job=job, classified_failures=None)
                                         .prefetch_related('step', '_metadata', '_metadata__failure_line'))
    errors = [t for t in all_errors if t.metadata and t.metadata.failure_line]

    if not errors:
        logger.info("Skipping autoclassify of job %i because it has no unmatched errors", job.id)
        return

    if matchers is None:
        matchers = get_matchers()

    try:
        matches = list(find_best_matches(errors, matchers))
        if not matches:
            return

        update_db(matches)

        # did we find matches for every error?
        matches_over_threshold = {m.text_log_error_id for m in matches if m.score >= AUTOCLASSIFY_GOOD_ENOUGH_RATIO}
        all_matched = {tle.id for tle in all_errors} <= matches_over_threshold

        create_note(job, all_matched)
    except Exception:
        logger.error("Autoclassification of job %s failed", job.id)
        job.autoclassify_status = Job.FAILED
        raise
    else:
        logger.debug("Autoclassification of job %s suceeded", job.id)
        job.autoclassify_status = Job.AUTOCLASSIFIED
    finally:
        job.save(update_fields=['autoclassify_status'])


def find_best_matches(errors, matchers):
    """
    Find the best match for each error

    We use the Good Enough™ ratio as a watershed level for match scores.
    """
    for text_log_error in errors:
        matches = find_all_matches(text_log_error, matchers)  # TextLogErrorMatch instances, unsaved!

        best_match = first(matches, key=lambda m: (-m.score, -m.classified_failure_id))
        if not best_match:
            continue

        yield best_match


def find_all_matches(text_log_error, matchers):
    """
    Find matches for the given error using the given matcher classes

    Returns *unsaved* TextLogErrorMatch instances.
    """
    for matcher_func in matchers:
        matches = matcher_func(text_log_error)
        # matches: iterator of (score, ClassifiedFailure.id)
        if not matches:
            continue

        for score, classified_failure_id in matches:
            yield TextLogErrorMatch(
                score=score,
                matcher_name=matcher_func.__name__,
                classified_failure_id=classified_failure_id,
                text_log_error=text_log_error,
            )


def update_db(matches):
    """
    Save TextLogErrorMatch instances to the DB

    We loop each Match instance instead of calling bulk_create() so we can
    catch any potential IntegrityErrors and continue.
    """
    for match in matches:
        try:
            match.save()
        except IntegrityError:
            args = (match.text_log_error_id, match.matcher_name, match.classified_failure_id)
            logger.warning(
                "Tried to create duplicate match for TextLogError %i with matcher %s and classified_failure %i",
                args,
            )

        # TODO: document what this does
        best_match = match.text_log_error.best_automatic_match(AUTOCLASSIFY_CUTOFF_RATIO)
        if best_match:
            match.text_log_error.mark_best_classification(match.classified_failure_id)


def create_note(job, all_matched):
    if not (all_matched and job.is_fully_autoclassified()):
        return

    # We don't want to add a job note after an autoclassification if there is
    # already one and after a verification if there is already one not supplied
    # by the autoclassifier
    if not JobNote.objects.filter(job=job).exists():
        JobNote.create_autoclassify_job_note(job)
