FROM python:3.11-slim-trixie@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY examples/sandbox/aiwaf-django-proxy/requirements.lock /opt/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r /opt/requirements.lock
RUN pip check

COPY examples/sandbox/aiwaf-django-proxy /workspace/examples/sandbox/aiwaf-django-proxy
COPY examples/sandbox/common /workspace/examples/sandbox/common

WORKDIR /workspace/examples/sandbox/aiwaf-django-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework django --settings aiwaf_django_proxy.settings

RUN groupadd --gid 10001 aiwaf && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp aiwaf && \
    mkdir -p /logs /state && chown -R 10001:10001 /logs /state
ENV HOME=/tmp AIWAF_DATA_DIR=/state/data DJANGO_DB_PATH=/state/db.sqlite3
USER 10001:10001
CMD ["sh", "-c", "python manage.py migrate --noinput --run-syncdb && python manage.py runserver 0.0.0.0:${PORT:-3009}"]
LABEL io.github.aiwaf.distribution="pypi"
