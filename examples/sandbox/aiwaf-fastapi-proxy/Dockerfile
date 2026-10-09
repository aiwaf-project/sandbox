FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

WORKDIR /workspace

COPY examples/sandbox/aiwaf-fastapi-proxy/requirements.lock /opt/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r /opt/requirements.lock
COPY --from=aiwaf_source /py /opt/aiwaf-source/py
COPY --from=aiwaf_source /setup.py /pyproject.toml /MANIFEST.in /README.md /LICENSE /opt/aiwaf-source/
RUN pip install --no-deps --no-build-isolation /opt/aiwaf-source && pip check

COPY examples/sandbox/aiwaf-fastapi-proxy /workspace/examples/sandbox/aiwaf-fastapi-proxy
COPY examples/sandbox/common /workspace/examples/sandbox/common

WORKDIR /workspace/examples/sandbox/aiwaf-fastapi-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework fastapi --app app:app

CMD ["python", "app.py"]
LABEL io.github.aiwaf.source="https://github.com/aayushgauba/aiwaf.git#843a35f4fd48b4ef565e3c1ec8a42db9b1c41946"
