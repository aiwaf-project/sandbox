FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

WORKDIR /workspace

COPY examples/sandbox/aiwaf-django-proxy/requirements.lock /opt/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r /opt/requirements.lock
COPY --from=aiwaf_source /py /opt/aiwaf-source/py
COPY --from=aiwaf_source /setup.py /pyproject.toml /MANIFEST.in /README.md /LICENSE /opt/aiwaf-source/
RUN pip install --no-deps --no-build-isolation /opt/aiwaf-source && pip check

COPY examples/sandbox/aiwaf-django-proxy /workspace/examples/sandbox/aiwaf-django-proxy
COPY examples/sandbox/common /workspace/examples/sandbox/common

WORKDIR /workspace/examples/sandbox/aiwaf-django-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework django --settings aiwaf_django_proxy.settings

CMD ["sh", "-c", "python manage.py migrate --noinput --run-syncdb && python manage.py runserver 0.0.0.0:${PORT:-3009}"]
LABEL io.github.aiwaf.source="https://github.com/aayushgauba/aiwaf.git#843a35f4fd48b4ef565e3c1ec8a42db9b1c41946"
