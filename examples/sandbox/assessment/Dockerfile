FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
WORKDIR /assessment
COPY examples/sandbox/assessment/fixture.py ./fixture.py
USER 65534:65534
CMD ["python", "fixture.py"]
