FROM python:3.7.11

# Variables that are not specific to a particular environment.
ENV NEW_RELIC_CONFIG_FILE newrelic.ini

# libmysqlclient-dev and gcc are required for the mysqlclient Python package.
# netcat is used for the MySQL readiness check in entrypoint.sh.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# Bug in Firefox which requires GTK+ and GLib in headless mode
# https://bugzilla.mozilla.org/show_bug.cgi?id=1372998
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    && rm -rf /var/lib/apt/lists/*
# Enable Firefox headless mode, avoiding the need for xvfb.
ENV MOZ_HEADLESS=1
ENV PATH="/usr/local/bin/firefox:${PATH}"

# /app will be mounted via a volume defined in docker-compose
ADD . /app
WORKDIR /app

# Common and dev deps installed separately to prove that common.txt works standalone
RUN pip install --no-cache-dir --disable-pip-version-check --require-hashes -r requirements/common.txt
RUN pip install --no-cache-dir --disable-pip-version-check --require-hashes -r requirements/dev.txt
