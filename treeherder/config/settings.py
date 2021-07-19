import os
import platform
import re
from datetime import timedelta
from os.path import abspath, dirname, join

import environ
from furl import furl
from kombu import Exchange, Queue

from treeherder.config.utils import connection_should_use_tls, get_tls_redis_url

# TODO: Switch to pathlib once using Python 3.
SRC_DIR = dirname(dirname(dirname(abspath(__file__))))

env = environ.Env()

# Checking for OS type
IS_WINDOWS = "windows" in platform.system().lower()

# Top Level configuration
DEBUG = env.bool("TREEHERDER_DEBUG", default=False)
LOGGING_LEVEL = env("LOGGING_LEVEL", default="INFO")

NEW_RELIC_INSIGHTS_API_KEY = env("NEW_RELIC_INSIGHTS_API_KEY", default=None)
NEW_RELIC_INSIGHTS_API_URL = 'https://insights-api.newrelic.com/v1/accounts/677903/query'

# Make this unique, and don't share it with anybody.
SECRET_KEY = env(
    "TREEHERDER_DJANGO_SECRET_KEY",
    default='secret-key-of-at-least-50-characters-to-pass-check-deploy',
)

# Delete the Pulse automatically when no consumers left
PULSE_AUTO_DELETE_QUEUES = env.bool("PULSE_AUTO_DELETE_QUEUES", default=False)

# Changing PULSE_AUTO_DELETE_QUEUES to True when Treeherder is running inside of virtual environment
if os.environ.get("VIRTUAL_ENV"):
    PULSE_AUTO_DELETE_QUEUES = True

# Hosts
SITE_URL = env("SITE_URL", default='http://localhost:8000')

SITE_HOSTNAME = furl(SITE_URL).host
# Including localhost allows using the backend locally
ALLOWED_HOSTS = [SITE_HOSTNAME, 'localhost', '127.0.0.1']

# URL handling
APPEND_SLASH = False
ROOT_URLCONF = "treeherder.config.urls"
WSGI_APPLICATION = 'treeherder.config.wsgi.application'

# Send full URL within origin but only origin for cross-origin requests
SECURE_REFERRER_POLICY = "origin-when-cross-origin"

# We can't set X_FRAME_OPTIONS to DENY since renewal of an Auth0 token
# requires opening the auth handler page in an invisible iframe with the
# same origin.
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Application definition
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    # Disable Django's own staticfiles handling in favour of WhiteNoise, for
    # greater consistency between gunicorn and `./manage.py runserver`.
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    # 3rd party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'dockerflow.django',
    # treeherder apps
    'treeherder.model',
    'treeherder.webapp',
    'treeherder.log_parser',
    'treeherder.etl',
    'treeherder.perf',
    'treeherder.seta',
    'treeherder.intermittents_commenter',
    'treeherder.changelog',
]

# Docker/outside-of-Docker/CircleCI
if DEBUG:
    NEW_RELIC_DEVELOPER_MODE = True
    # This controls whether the Django debug toolbar should be shown or not
    # https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#show-toolbar-callback
    # "You can provide your own function callback(request) which returns True or False."
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
    }
    INSTALLED_APPS.append('debug_toolbar')
    INSTALLED_APPS.append('django_extensions')

# Middleware
MIDDLEWARE = [
    middleware
    for middleware in [
        # Adds custom New Relic annotations. Must be first so all transactions are annotated.
        'treeherder.middleware.NewRelicMiddleware',
        # Redirect to HTTPS/set HSTS and other security headers.
        'django.middleware.security.SecurityMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        'corsheaders.middleware.CorsMiddleware',
        # Allows both Django static files and those specified via `WHITENOISE_ROOT`
        # to be served by WhiteNoise, avoiding the need for Apache/nginx on Heroku.
        'treeherder.middleware.CustomWhiteNoise',
        'django.middleware.gzip.GZipMiddleware',
        'debug_toolbar.middleware.DebugToolbarMiddleware' if DEBUG else False,
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'dockerflow.django.middleware.DockerflowMiddleware',
    ]
    if middleware
]

# Database
# The database config is defined using environment variables of form:
#
#   'mysql://username:password@host:optional_port/database_name'
#
# which django-environ converts into the Django DB settings dict format.
LOCALHOST_MYSQL_HOST = 'mysql://root@{}:3306/treeherder'.format(
    'localhost' if IS_WINDOWS else '127.0.0.1'
)
DATABASES = {
    'default': env.db_url('DATABASE_URL', default=LOCALHOST_MYSQL_HOST),
}

# Only used when syncing local database with production replicas
UPSTREAM_DATABASE_URL = env('UPSTREAM_DATABASE_URL', default=None)
if UPSTREAM_DATABASE_URL:
    DATABASES['upstream'] = env.db_url_config(UPSTREAM_DATABASE_URL)

# We're intentionally not using django-environ's query string options feature,
# since it hides configuration outside of the repository, plus could lead to
# drift between environments.
for alias in DATABASES:
    # Persist database connections for 5 minutes, to avoid expensive reconnects.
    DATABASES[alias]['CONN_MAX_AGE'] = 300
    DATABASES[alias]['OPTIONS'] = {
        # Override Django's default connection charset of 'utf8', otherwise it's
        # still not possible to insert non-BMP unicode into utf8mb4 tables.
        'charset': 'utf8mb4',
        # From MySQL 5.7 onwards and on fresh installs of MySQL 5.6, the default value of the sql_mode
        # option contains STRICT_TRANS_TABLES. That option escalates warnings into errors when data are
        # truncated upon insertion, so Django highly recommends activating a strict mode for MySQL to
        # prevent data loss (either STRICT_TRANS_TABLES or STRICT_ALL_TABLES).
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    }
    if connection_should_use_tls(DATABASES[alias]['HOST']):
        # The default cert is for access to the stage replica; for accessing
        # prototype this variable will need to reference deployment/gcp/ca-cert-prototype.pem.
        # See treeherder docs for more details.
        DATABASES[alias]['OPTIONS']['ssl'] = {
            'ca': env("TLS_CERT_PATH", default='deployment/gcp/ca-cert.pem'),
        }

# Caches
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379')
if connection_should_use_tls(REDIS_URL):
    # Connect using TLS on Heroku.
    REDIS_URL = get_tls_redis_url(REDIS_URL)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            # Override the default of no timeout, to avoid connection hangs.
            'SOCKET_CONNECT_TIMEOUT': 5,
        },
    },
}

# Internationalization
TIME_ZONE = "UTC"
USE_I18N = False
USE_L10N = True

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = join(SRC_DIR, ".django-static")
STATIC_URL = "/static/"

# Create hashed+gzipped versions of assets during collectstatic,
# which will then be served by WhiteNoise with a suitable max-age.
# http://whitenoise.evans.io/en/stable/django.html#add-compression-and-caching-support
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Authentication
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'treeherder.auth.backends.AuthBackend',
]

# Use the cache-based backend rather than the default of database.
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# Path to redirect to on successful login.
LOGIN_REDIRECT_URL = '/'

# Path to redirect to on unsuccessful login attempt.
LOGIN_REDIRECT_URL_FAILURE = '/'

# Path to redirect to on logout.
LOGOUT_REDIRECT_URL = '/'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
        },
        'json': {'()': 'dockerflow.logging.JsonLogFormatter', 'logger_name': 'treeherder'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
        'json': {'class': 'logging.StreamHandler', 'formatter': 'json', 'level': 'DEBUG'},
    },
    'loggers': {
        'django': {
            'filters': ['require_debug_true'],
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'treeherder': {
            'handlers': ['console'],
            'level': LOGGING_LEVEL,
            'propagate': LOGGING_LEVEL != 'WARNING',
        },
        'kombu': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'request.summary': {
            'handlers': ['json'],
            'level': 'DEBUG',
        },
    },
}

# SECURITY
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if SITE_URL.startswith('https://'):
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_SECONDS = int(timedelta(days=365).total_seconds())
    # Mark session and CSRF cookies as being HTTPS-only.
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True  # Set the `X-Content-Type-Options` header to `nosniff`.
SECURE_BROWSER_XSS_FILTER = True  # Sets the `X-XSS-Protection` header.

# System Checks
SILENCED_SYSTEM_CHECKS = [
    # We can't set CSRF_COOKIE_HTTPONLY to True since the requests to the API
    # made using Angular's `httpProvider` require access to the cookie.
    'security.W017',
    'security.W019',
]

# User Agents
# User agents which will be blocked from making requests to the site.
DISALLOWED_USER_AGENTS = (
    re.compile(r'^Go-http-client/'),
    # This was the old Go http package user agent prior to Go-http-client/*
    # https://github.com/golang/go/commit/0d1ceef9452c495b6f6d60e578886689184e5e4b
    re.compile(r'^Go 1.1 package http'),
    # Note: This intentionally does not match the command line curl
    # tool's default User Agent, only the library used by eg PHP.
    re.compile(r'^libcurl/'),
    re.compile(r'^Python-urllib/'),
    re.compile(r'^python-requests/'),
)


# THIRD PARTY APPS

# Auth0 setup
AUTH0_DOMAIN = env('AUTH0_DOMAIN', default="auth.mozilla.auth0.com")
AUTH0_CLIENTID = env('AUTH0_CLIENTID', default="q8fZZFfGEmSB2c5uSI8hOkKdDGXnlo5z")

# Celery

# TODO: Replace the use of different log parser queues for failures vs not with the
# RabbitMQ priority feature (since the idea behind separate queues was only to ensure
# failures are dealt with first if there is a backlog). After that it should be possible
# to simplify the queue configuration, by using the recommended CELERY_TASK_ROUTES instead:
# http://docs.celeryproject.org/en/latest/userguide/routing.html#automatic-routing
CELERY_TASK_QUEUES = [
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('log_parser', Exchange('default'), routing_key='log_parser.normal'),
    Queue('log_parser_fail_raw_sheriffed', Exchange('default'), routing_key='log_parser.failures'),
    Queue(
        'log_parser_fail_raw_unsheriffed', Exchange('default'), routing_key='log_parser.failures'
    ),
    Queue('log_parser_fail_json_sheriffed', Exchange('default'), routing_key='log_parser.failures'),
    Queue(
        'log_parser_fail_json_unsheriffed', Exchange('default'), routing_key='log_parser.failures'
    ),
    Queue('pushlog', Exchange('default'), routing_key='pushlog'),
    Queue('generate_perf_alerts', Exchange('default'), routing_key='generate_perf_alerts'),
    Queue('store_pulse_tasks', Exchange('default'), routing_key='store_pulse_tasks'),
    Queue('store_pulse_pushes', Exchange('default'), routing_key='store_pulse_pushes'),
    Queue('seta_analyze_failures', Exchange('default'), routing_key='seta_analyze_failures'),
]

# Force all queues to be explicitly listed in `CELERY_TASK_QUEUES` to help prevent typos
# and so that `lints/queuelint.py` can check a corresponding worker exists in `Procfile`.
CELERY_TASK_CREATE_MISSING_QUEUES = False

# Celery broker setup
CELERY_BROKER_URL = env('BROKER_URL', default='amqp://guest:guest@localhost:5672//')

# Force Celery to use TLS when appropriate (ie if not localhost),
# rather than relying on `CELERY_BROKER_URL` having `amqps://` or `?ssl=` set.
# This is required since CloudAMQP's automatically defined URL uses neither.
if connection_should_use_tls(CELERY_BROKER_URL):
    CELERY_BROKER_USE_SSL = True

# Recommended by CloudAMQP:
# https://www.cloudamqp.com/docs/celery.html
# Raise timeout from default of 4s, in case of Linux DNS timeouts etc.
CELERY_BROKER_CONNECTION_TIMEOUT = 30
# Disable heartbeats since CloudAMQP uses TCP keep-alive instead.
CELERY_BROKER_HEARTBEAT = None

# default value when no task routing info is specified
CELERY_TASK_DEFAULT_QUEUE = 'default'

# Make Celery defer the acknowledgment of a task until after the task has completed,
# to prevent data loss in the case of celery master process crashes or infra failures.
# https://devcenter.heroku.com/articles/celery-heroku#using-acks_late
# http://docs.celeryproject.org/en/latest/userguide/tasks.html#Task.acks_late
CELERY_TASK_ACKS_LATE = True

# Default celery time limits in seconds. The gap between the soft and hard time limit
# is to give the New Relic agent time to report the `SoftTimeLimitExceeded` exception.
# NB: The per-task `soft_time_limit` must always be lower than `CELERY_TASK_TIME_LIMIT`.
CELERY_TASK_SOFT_TIME_LIMIT = 15 * 60
CELERY_TASK_TIME_LIMIT = CELERY_TASK_SOFT_TIME_LIMIT + 30

CELERY_BEAT_SCHEDULE = {
    # this is just a failsafe in case the Pulse ingestion misses something
    'fetch-push-logs-every-5-minutes': {
        'task': 'fetch-push-logs',
        'schedule': timedelta(minutes=5),
        'relative': True,
        'options': {"queue": "pushlog"},
    },
    'seta-analyze-failures': {
        'task': 'seta-analyze-failures',
        'schedule': timedelta(days=1),
        'relative': True,
        'options': {'queue': "seta_analyze_failures"},
    },
}

# CORS Headers
CORS_ORIGIN_ALLOW_ALL = True  # allow requests from any host


# Rest Framework
REST_FRAMEWORK = {
    'ALLOWED_VERSIONS': ('1.0',),
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework.authentication.SessionAuthentication',),
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_PARSER_CLASSES': ('rest_framework.parsers.JSONParser',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'DEFAULT_VERSION': '1.0',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# Whitenoise
# http://whitenoise.evans.io/en/stable/django.html#available-settings
# Files in this directory will be served by WhiteNoise at the site root.
WHITENOISE_ROOT = join(SRC_DIR, ".build")
# Serve index.html for URLs ending in a trailing slash.
WHITENOISE_INDEX_FILE = True
# Only output the hashed filename version of static files and not the originals.
# Halves the time spent performing Brotli/gzip compression during deploys.
WHITENOISE_KEEP_ONLY_HASHED_FILES = True

# Templating
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': [WHITENOISE_ROOT],
    }
]

# TREEHERDER

# Bugzilla
# BZ_API_URL is used to fetch bug suggestions from bugzilla
# BUGFILER_API_URL is used when filing bugs
# these are no longer necessarily the same so stage treeherder can submit
# to stage bmo, while suggestions can still be fetched from prod bmo
BZ_API_URL = "https://bugzilla.mozilla.org"
BUGFILER_API_URL = env("BUGZILLA_API_URL", default=BZ_API_URL)
BUGFILER_API_KEY = env("BUG_FILER_API_KEY", default=None)
BZ_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

# For intermittents commenter
COMMENTER_API_KEY = env("BUG_COMMENTER_API_KEY", default=None)

# Log Parsing
MAX_ERROR_LINES = 100
FAILURE_LINES_CUTOFF = 35

# Perfherder
# Default minimum regression threshold for perfherder is 2% (otherwise
# e.g. the build size tests will alert on every commit)
PERFHERDER_REGRESSION_THRESHOLD = 2

# Various settings for treeherder's t-test "sliding window" alert algorithm
PERFHERDER_ALERTS_MIN_BACK_WINDOW = 12
PERFHERDER_ALERTS_MAX_BACK_WINDOW = 24
PERFHERDER_ALERTS_FORE_WINDOW = 12
# Assess if tests should be (non)sheriffed
QUANTIFYING_PERIOD = timedelta(weeks=24)  # how far back to look over Bugzilla data
BUG_COOLDOWN_TIME = timedelta(weeks=2)  # time after bug is ready for assessment

# Only generate alerts for data newer than this time in seconds in perfherder
PERFHERDER_ALERTS_MAX_AGE = timedelta(weeks=2)
# From the same job's log, ingest (or not) multiple PERFHERDER_DATA dumps
# pertaining to the same performance signature
PERFHERDER_ENABLE_MULTIDATA_INGESTION = env.bool(
    'PERFHERDER_ENABLE_MULTIDATA_INGESTION', default=True
)

# Sherlock' settings (the performance sheriff robot)
SUPPORTED_PLATFORMS = ['windows', 'linux', 'osx']
MAX_BACKFILLS_PER_PLATFORM = {
    'windows': 200,
    'linux': 200,
    'osx': 20,
}
RESET_BACKFILL_LIMITS = timedelta(hours=24)
TIME_TO_MATURE = timedelta(hours=4)

# Taskcluster credentials for Sherlock
# TODO: rename PERF_SHERIFF_BOT prefixes to SHERLOCK
PERF_SHERIFF_BOT_CLIENT_ID = env('PERF_SHERIFF_BOT_CLIENT_ID', default=None)
PERF_SHERIFF_BOT_ACCESS_TOKEN = env('PERF_SHERIFF_BOT_ACCESS_TOKEN', default=None)

# Taskcluster credentials for Notification Service
NOTIFY_CLIENT_ID = env('NOTIFY_CLIENT_ID', default=None)
NOTIFY_ACCESS_TOKEN = env('NOTIFY_ACCESS_TOKEN', default=None)

# This is only used for removing the rate limiting. You can create your own here:
# https://github.com/settings/tokens
GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)

# For dockerflow
BASE_DIR = SRC_DIR
