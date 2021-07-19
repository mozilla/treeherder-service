#!/bin/bash

# The `release` process type specifies the command to run during deployment, and is where
# we run DB migrations and other tasks that are 'release' rather than 'build' specific:
# https://devcenter.heroku.com/articles/release-phase
# https://devcenter.heroku.com/articles/runtime-principles#build-release-run
if [ "$1" == "release" ]; then
    exec ./bin/pre_deploy

# We set the maximum request duration to 20 seconds, to ensure that poorly performing API
# queries do not consume a gunicorn worker for unbounded lengths of time. 
elif [ "$1" == "web" ]; then
    exec newrelic-admin run-program gunicorn treeherder.config.wsgi:application --timeout 20 --bind 0.0.0.0

# All other process types can have arbitrary names.
# The Celery options such as `--without-heartbeat` are from the recommendations here:
# https://www.cloudamqp.com/docs/celery.html
# The REMAP_SIGTERM is as recommended by:
# https://devcenter.heroku.com/articles/celery-heroku#using-remap_sigterm

# This schedules (but does not run itself) the cron-like tasks listed in `CELERY_BEAT_SCHEDULE`.
elif [ "$1" == "celery_scheduler" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery beat -A treeherder

# Push/job data is consumed from exchanges on pulse.mozilla.org using these kombu-powered
# Django management commands. They do not ingest the data themselves, instead adding tasks
# to the `store_pulse_{pushes,jobs}` queues for `worker_store_pulse_data` to process.
# NB: These should not be scaled up to more than 1 of each.
# TODO: Merge these two listeners into one since they use so little CPU each (bug 1530965).
elif [ "$1" == "pulse_listener_pushes" ]; then
    exec newrelic-admin run-program ./manage.py pulse_listener_pushes
elif [ "$1" == "pulse_listener_tasks" ]; then
    exec newrelic-admin run-program ./manage.py pulse_listener_tasks

# Processes pushes/jobs from Pulse that were collected by `pulse_listener_{pushes,tasks}`.
elif [ "$1" == "worker_store_pulse_data" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q store_pulse_pushes,store_pulse_tasks --concurrency=3

# Handles the log parsing tasks scheduled by `worker_store_pulse_data` as part of job ingestion.
elif [ "$1" == "worker_log_parser" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q log_parser --concurrency=7
elif [ "$1" == "worker_log_parser_fail_raw_sheriffed" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q log_parser_fail_raw_sheriffed --concurrency=1
elif [ "$1" == "worker_log_parser_fail_raw_unsheriffed" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q log_parser_fail_raw_unsheriffed --concurrency=1
elif [ "$1" == "worker_log_parser_fail_json_sheriffed" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q log_parser_fail_json_sheriffed --concurrency=7
elif [ "$1" == "worker_log_parser_fail_json_unsheriffed" ]; then
    export REMAP_SIGTERM=SIGQUIT
    newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q log_parser_fail_json_unsheriffed --concurrency=7

# Tasks that don't need a dedicated worker.
elif [ "$1" == "worker_misc" ]; then
    export REMAP_SIGTERM=SIGQUIT
    exec newrelic-admin run-program celery worker -A treeherder --without-gossip --without-mingle --without-heartbeat -Q default,generate_perf_alerts,pushlog,seta_analyze_failures --concurrency=3

# Cron jobs
elif [ "$1" == "run_intermittents_commenter" ]; then
    newrelic-admin run-program ./manage.py run_intermittents_commenter -m auto

elif [ "$1" == "update_bugscache" ]; then
    newrelic-admin run-program ./manage.py update_bugscache

elif [ "$1" == "cache_failure_history" ]; then
    newrelic-admin run-program ./manage.py cache_failure_history

elif [ "$1" == "cycle_data" ]; then
    shift
    ./manage.py cycle_data "$@"

elif [ "$1" == "perf_sheriff" ]; then
    shift
    newrelic-admin run-program ./manage.py perf_sheriff "$@"

elif [ "$1" == "update_changelog" ]; then
    newrelic-admin run-program ./manage.py update_changelog --days 2

else
    echo "Unknown command: $1"
    exit 1
fi
