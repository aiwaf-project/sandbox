FROM python:3.11-slim

WORKDIR /workspace

RUN pip install --default-timeout=1000 --no-cache-dir "aiwaf[fastapi,rust]==1.0.8" "aiwaf-rust==0.2.1" httpx

COPY . /workspace

WORKDIR /workspace/examples/sandbox/aiwaf-fastapi-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework fastapi --app app:app

CMD ["python", "app.py"]
