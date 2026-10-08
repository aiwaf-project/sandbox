FROM python:3.11-slim

WORKDIR /workspace

RUN pip install --default-timeout=1000 --no-cache-dir "aiwaf[django,rust]==1.0.8" "aiwaf-rust==0.2.1" "redis>=5,<7"

COPY . /workspace

WORKDIR /workspace/examples/sandbox/aiwaf-django-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework django --settings aiwaf_django_proxy.settings

CMD ["sh", "-c", "python manage.py migrate --noinput --run-syncdb && python manage.py runserver 0.0.0.0:${PORT:-3009}"]
