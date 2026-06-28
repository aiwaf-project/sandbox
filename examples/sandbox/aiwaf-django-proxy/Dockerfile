FROM python:3.11-slim

WORKDIR /workspace
COPY . /workspace

RUN pip install --no-cache-dir "Django>=3.2" requests aiwaf aiwaf-rust

WORKDIR /workspace/examples/sandbox/aiwaf-django-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework django --settings aiwaf_django_proxy.settings

CMD ["sh", "-c", "python manage.py migrate --noinput --run-syncdb && python manage.py runserver 0.0.0.0:${PORT:-3009}"]
