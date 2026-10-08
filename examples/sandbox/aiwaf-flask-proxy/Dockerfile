FROM python:3.11-slim

WORKDIR /workspace

RUN pip install --default-timeout=1000 --no-cache-dir "aiwaf[flask,rust]==1.0.8" "aiwaf-rust==0.2.1"

COPY . /workspace

WORKDIR /workspace/examples/sandbox/aiwaf-flask-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework flask --app app:create_app

CMD ["python", "app.py"]
