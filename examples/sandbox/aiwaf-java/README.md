# aiwaf-java Example

Plain Java reverse proxy protected by AIWAF engine.

## Build image

```bash
docker build -f examples/sandbox/aiwaf-java/Dockerfile -t aiwaf-java-example .
```

## Run

```bash
docker run --rm -p 8080:8080 \
  -e TARGET_BASE_URL=http://host.docker.internal:3000 \
  aiwaf-java-example
```
