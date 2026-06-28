FROM python:3.11-slim

WORKDIR /workspace
COPY . /workspace

RUN pip install --no-cache-dir "flask>=2.3" requests numpy scikit-learn joblib aiwaf aiwaf-rust

WORKDIR /workspace/examples/sandbox/aiwaf-flask-proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m aiwaf.cli init --framework flask --app app:create_app

CMD ["python", "app.py"]
