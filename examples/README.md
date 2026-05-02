# AIWAF Java Examples

This folder contains Java implementations of runnable AIWAF examples.

## Example Projects

- `sandbox/aiwaf-java/`: plain Java reverse proxy protected by `AiwafEngine`.
- `sandbox/aiwaf-spring/`: Spring Boot reverse proxy protected by `AiwafFilter`.
- `sandbox/`: sandbox utilities and additional compatibility proxies.

## Build Docker Images

From repository root:

```bash
docker build -f examples/sandbox/aiwaf-java/Dockerfile -t aiwaf-java-example .
docker build -f examples/sandbox/aiwaf-spring/Dockerfile -t aiwaf-spring-example .
```

## Run Together

```bash
docker compose -f examples/sandbox/docker-compose.yml up --build
```

Endpoints:

- `http://localhost:8080` -> aiwaf-java proxy
- `http://localhost:8081` -> aiwaf-spring proxy
- `http://localhost:3001` -> direct Juice Shop
