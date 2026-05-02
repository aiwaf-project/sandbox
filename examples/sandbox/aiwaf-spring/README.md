# aiwaf-spring Example

Spring Boot reverse proxy protected by AIWAF filter.

## Build image

```bash
docker build -f examples/sandbox/aiwaf-spring/Dockerfile -t aiwaf-spring-example .
```

## Run

```bash
docker run --rm -p 8081:8081 \
  -e TARGET_BASE_URL=http://host.docker.internal:3000 \
  aiwaf-spring-example
```
