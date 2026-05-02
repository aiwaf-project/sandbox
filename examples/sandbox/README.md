# AIWAF Java Sandbox

This sandbox runs two Java AIWAF proxies in front of OWASP Juice Shop:

- `aiwaf-java` (plain Java proxy)
- `aiwaf-spring` (Spring Boot proxy)

## Start

From repo root:

```bash
docker compose -f examples/sandbox/docker-compose.yml up -d --build
```

Or from this directory:

```bash
docker compose up -d --build
```

## Endpoints

- `http://localhost:8080` -> protected_java
- `http://localhost:8081` -> protected_spring
- `http://localhost:3001` -> direct (unprotected)

## Run Attack Suite

```bash
javac --release 17 AttackSuite.java CompareResults.java CompareResultsModes.java RunAndCompare.java

java AttackSuite http://127.0.0.1:3001 direct normal
java AttackSuite http://127.0.0.1:3001 direct attacks

java AttackSuite http://localhost:8080 protected_java normal
java AttackSuite http://localhost:8080 protected_java attacks

java AttackSuite http://localhost:8081 protected_spring normal
java AttackSuite http://localhost:8081 protected_spring attacks
```

## Compare

```bash
java CompareResults results_direct_*.json results_protected_*.json
java CompareResultsModes results_protected_java_normal_*.json results_protected_spring_normal_*.json -- results_protected_java_attacks_*.json results_protected_spring_attacks_*.json
```

## Expected Behavior

- Protected normal traffic should be mostly/fully allowed.
- Protected attack traffic should be mostly/fully blocked (403/429).
- Direct traffic is baseline behavior from Juice Shop.

## Cleanup

```bash
./clean-results.sh
docker compose down
```
