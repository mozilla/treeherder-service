## Frontend stage
FROM node:16.5.0 AS frontend

WORKDIR /app

COPY ui/ /app/ui/
COPY .neutrinorc.js package.json webpack.config.js yarn.lock /app/

RUN npm install -g --force yarn@1.22.5
RUN yarn install
RUN yarn build


## Backend stage
FROM python:3.7.11-slim

# libmysqlclient-dev is required for the mysqlclient Python package.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ /app/requirements/
RUN apt-get update && apt-get install -q --yes gcc && \
    pip install -r requirements/common.txt && \
    apt-get -q --yes remove gcc && \
    apt-get -q --yes autoremove && \
    apt-get clean && \
    rm -rf /root/.cache

COPY bin/ /app/bin/
COPY docker/entrypoint_prod.sh /app/docker/entrypoint_prod.sh
COPY treeherder/ /app/treeherder/
COPY schemas/ /app/schemas/
COPY manage.py newrelic.ini version.json /app/

COPY --from=frontend /app/.build/ /app/.build/

RUN python manage.py collectstatic --noinput

ENTRYPOINT ["/bin/bash", "/app/docker/entrypoint_prod.sh"]
CMD ["web"]
