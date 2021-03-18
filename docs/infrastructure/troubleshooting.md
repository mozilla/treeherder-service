# Infrastructure Troubleshooting

## Monitoring & metrics

- Heroku apps
  - Deployment activity:
    [prototype](https://dashboard.heroku.com/apps/treeherder-prototype/activity) |
    [stage](https://dashboard.heroku.com/apps/treeherder-stage/activity) |
    [prod](https://dashboard.heroku.com/apps/treeherder-prod/activity)
  - HTTP & dyno metrics:
    [prototype](https://dashboard.heroku.com/apps/treeherder-prototype/metrics) |
    [stage](https://dashboard.heroku.com/apps/treeherder-stage/metrics) |
    [prod](https://dashboard.heroku.com/apps/treeherder-prod/metrics)
  - Service status: <https://status.heroku.com>
- New Relic
  - Overview:
    [prototype](https://rpm.newrelic.com/accounts/677903/applications/7385291) |
    [stage](https://rpm.newrelic.com/accounts/677903/applications/14179733) |
    [prod](https://rpm.newrelic.com/accounts/677903/applications/14179757)
  - Error analytics:
    [prototype](https://rpm.newrelic.com/accounts/677903/applications/7385291/filterable_errors) |
    [stage](https://rpm.newrelic.com/accounts/677903/applications/14179733/filterable_errors) |
    [prod](https://rpm.newrelic.com/accounts/677903/applications/14179757/filterable_errors)
  - Web transactions:
    [prototype](https://rpm.newrelic.com/accounts/677903/applications/7385291/transactions?type=app) |
    [stage](https://rpm.newrelic.com/accounts/677903/applications/14179733/transactions?type=app) |
    [prod](https://rpm.newrelic.com/accounts/677903/applications/14179757/transactions?type=app)
  - Non-web transactions (background tasks):
    [prototype](https://rpm.newrelic.com/accounts/677903/applications/7385291/transactions?type=other&show_browser=false) |
    [stage](https://rpm.newrelic.com/accounts/677903/applications/14179733/transactions?type=other&show_browser=false) |
    [prod](https://rpm.newrelic.com/accounts/677903/applications/14179757/transactions?type=other&show_browser=false)
  - MySQL/Redis client request stats:
    [prototype](https://rpm.newrelic.com/accounts/677903/applications/7385291/datastores) |
    [stage](https://rpm.newrelic.com/accounts/677903/applications/14179733/datastores) |
    [prod](https://rpm.newrelic.com/accounts/677903/applications/14179757/datastores)
- Amazon RDS
  - CloudWatch metrics:
    [dev](https://console.aws.amazon.com/rds/home?region=us-east-1#database:id=treeherder-dev;is-cluster=false;tab=monitoring) |
    [stage](https://console.aws.amazon.com/rds/home?region=us-east-1#database:id=treeherder-stage;is-cluster=false;tab=monitoring) |
    [prod](https://console.aws.amazon.com/rds/home?region=us-east-1#database:id=treeherder-prod;is-cluster=false;tab=monitoring) |
    [prod-ro](https://console.aws.amazon.com/rds/home?region=us-east-1#database:id=treeherder-prod-ro;is-cluster=false;tab=monitoring)
  - Service status: <https://status.aws.amazon.com>
- CloudAMQP RabbitMQ add-on
  - Management & metrics dashboard:
    [prototype](https://addons-sso.heroku.com/apps/treeherder-prototype/addons/cloudamqp) |
    [stage](https://addons-sso.heroku.com/apps/treeherder-stage/addons/cloudamqp) |
    [prod](https://addons-sso.heroku.com/apps/treeherder-prod/addons/cloudamqp)
  - Service status: <http://status.cloudamqp.com>
- Heroku Redis add-on
  - Management & metrics dashboard:
    [prototype](https://addons-sso.heroku.com/apps/treeherder-prototype/addons/heroku-redis) |
    [stage](https://addons-sso.heroku.com/apps/treeherder-stage/addons/heroku-redis) |
    [prod](https://addons-sso.heroku.com/apps/treeherder-prod/addons/heroku-redis)
  - Service status: <https://status.heroku.com>

## Logging

The Heroku apps are configured to use [Papertrail] as a [log drain]. The aggregated
HTTP router, dyno and app output logs can be viewed and searched at:
[prototype](https://papertrailapp.com/systems/treeherder-prototype/events) |
[stage](https://papertrailapp.com/systems/treeherder-stage/events) |
[prod](https://papertrailapp.com/systems/treeherder-prod/events).

See the Heroku [logging] and [error codes] documentation for help understanding the log output.

[papertrail]: https://papertrailapp.com
[log drain]: https://devcenter.heroku.com/articles/log-drains
[logging]: https://devcenter.heroku.com/articles/logging
[error codes]: https://devcenter.heroku.com/articles/error-codes

<!-- prettier-ignore -->
!!! note
    Django is configured to only output log levels `WARNING` and above, unless debug
    mode is enabled (such in Vagrant).

## Errors and performance monitoring

With Sentry, you can now track all errors produced and the performance of every transaction.
You can also create alerts and assign on-going errors to a team member.
Sentry also tracks releases automaticaly to help you determine which release introduced an error.

NOTE: The SDKs, when doing local development, have been configured to report to a release called `dev`
instead of letting it report releases based on a commit hash of your local checkout.

## Scenarios

### Regression from a deployment

1. Check that the deployment did not involve schema migrations, using the "Compare diff"
   link on the Heroku app "activity" tab. (If it did, it might be easier to fix the
   regression in place rather than rolling back the deployment.)
2. [Revert the deployment](administration.md#reverting-deployments)
3. Notify the rest of the team, so that they do not unknowingly re-deploy the regression.
4. If a bug had not already been filed for the regression, either file one now, or re-open
   the bug that caused the regression, explaining the issue encountered.

### Web request HTTP 500s

1. Check the New Relic "Error Analytics" section for details of the Python exception.
2. (If needed) Search Papertrail for the exception name/message for additional information.
3. File a bug with steps to reproduce and the exception stack trace.

### Web request HTTP 503s

If the Heroku [HTTP router] returns an HTTP 503 for a request, it means that a web dyno was
unable (or refused) to provide a response. There are several reasons this may occur, which
can be differentiated by finding out which [error code][error codes] occurred.

To discover the error code, check either:

- the Heroku app "metrics" tab with the "web" dyno type selected, then inspect the timeline.
- the Papertrail logs, by searching for `status=503`

The most common error codes we see, are:

- [H12 - Request timeout][error-h12]

  This means that the HTTP request took longer than 30 seconds to complete, so was interrupted
  by the Heroku router. This occurs when a request backlog has formed due to the number or
  duration of web requests exceeding the capacity of the gunicorn workers available.

  This can be confirmed by looking at the New Relic "Overview" section (making sure the
  selector at the top of the page is set to "Web transactions time") and checking for spikes
  in the [Request Queuing] time (which measures how long requests were waiting before a
  gunicorn worker was able to begin processing them).

  To resolve, first try [restarting] the web dynos in case one of them has an issue (eg: failing
  dyno or noisy neighbours on that instance). If that doesn't work, check the New Relic web
  transactions page to see if either there has been a spike in the throughput of requests
  (in which case consider [scaling] the web dynos), or if an external service (such as MySQL
  or Redis) is taking longer to respond than before.

- [H13 - Connection closed without response][error-h13]:

  This means that the request exceeded the gunicorn's configured time limit (currently set
  at 20 seconds, see the `--timeout` gunicorn argument in `Procfile`), so it aborted the
  request.

  If most other web requests are succeeding, this suggests that the particular API endpoint
  and query-parameter combination needs optimisation (in which case file an API bug with
  steps to reproduce), or if not, try the suggested steps for the `H12` error code above.

[http router]: https://devcenter.heroku.com/articles/http-routing
[error code]: https://devcenter.heroku.com/articles/error-codes
[error-h12]: https://devcenter.heroku.com/articles/error-codes#h12-request-timeout
[error-h13]: https://devcenter.heroku.com/articles/error-codes#h13-connection-closed-without-response
[request queuing]: https://docs.newrelic.com/docs/apm/applications-menu/features/request-queuing-tracking-front-end-time
[restarting]: administration.md#restarting-dynos
[scaling]: administration.md#scaling-dynos

### Celery queue backlogs

When the RabbitMQ queues used by Celery exceeds the configured threshold, CloudAMQP sends
an email alert to the `treeherder-internal@moco` mailing list. If this occurs:

1. Open the CloudAMQP management dashboard using the links above, then:
   - Check the "Metrics" tab, to see a timeline of total queue length.
   - Click the "RabbitMQ Manager" button, and switch to the "Queues" tab to see
     the per-queue breakdown and message incoming/delivery rates.
2. Check New Relic's "Error Analytics" section, in case tasks are failing and being
   retried due to a Python exception.
3. In the New Relic's "Transactions" section, switch to the "Non-web" transactions view
   (or use the direct links above), and click the relevant Celery task to see if there
   has been a change in either throughput or time per task.
4. Depending on the information discovered above, you may want to try [restarting] or
   [scaling] the worker dynos associated with the backlogged queues.

### New pushes/jobs not appearing

If new pushes or CI job results are not appearing in Treeherder's UI:

1. Follow the steps in [Celery queue backlogs](#celery-queue-backlogs) to rule out
   task backlogs/Python exceptions.
2. Check the upstream Pulse queues [using Pulse Guardian] (you must be an co-owner of
   the Treeherder queues to see them listed). If there is a Pulse queue backlog,
   it suggests that Treeherder's `pulse_listener_{pushes,jobs}` dynos have stopped
   consuming Pulse events, and so might need [restarting].
3. Failing that, it's possible the issue might lie in the services that send events to
   those Pulse exchanges, such as `taskcluster-github` or
   the Taskcluster systems upstream of those. Ask for help in the IRC channel
   `#taskcluster`.

[using pulse guardian]: https://pulseguardian.mozilla.org/queues
