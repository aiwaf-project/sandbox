# AIWAF Multi-Runtime Sandbox

Unified sandbox for validating AIWAF behavior across Node.js, Python, PHP, and Java services using OWASP Juice Shop as the target application.

## Overview

This repository is designed for:

- Running many framework/runtime integrations in one stack
- Comparing direct (unprotected) vs protected traffic
- Executing repeatable attack simulations
- Generating machine-readable comparison reports
- Verifying parity and detection performance across runtimes

The stack is intentionally practical: one command to start, one suite to test, one report format to compare.

## Architecture

Traffic model:

- `direct` target points to Juice Shop without AIWAF
- `protected_*` targets proxy requests through AIWAF-enabled services
- attack suites send normal and malicious traffic to each target
- results are aggregated into JSON summaries

Core components:

- `juice` service (OWASP Juice Shop backend)
- Runtime-specific AIWAF proxy/services (Node, Python, PHP, Java)
- Test harness scripts (Python and PHP)
- Compare scripts for tabular summaries

## Service Matrix

### Node targets

- `protected_node` (Express)
- `protected_fastify`
- `protected_hapi`
- `protected_koa`
- `protected_nest`
- `protected_next`
- `protected_adonis`
- `protected_sails`

### Python targets

- `protected_django`
- `protected_flask`
- `protected_fastapi`

### PHP targets

- `protected_laravel`
- `protected_symfony`
- `protected_wordpress`

### Java targets

- `protected_java`
- `protected_spring`
- `protected_java_r`
- `protected_spring_r`

### Baseline target

- `direct` (no WAF, expected low detection)

## Repository Layout

- `docker-compose.yml`: root stack for all runtimes
- `examples/`: shared examples and package setup
- `examples/sandbox/`: runtime service implementations and test tooling
- `examples/sandbox/attack-suite.py`: primary end-to-end runner
- `examples/sandbox/compare-results-modes.py`: normal vs attack summary
- `examples/sandbox/compare-results.py`: per-attack comparison helper
- `examples/attack-suite.php`: PHP-focused suite (requires PHP curl extension)

## Prerequisites

- Docker Desktop or Docker Engine + Compose plugin
- Python 3.10+ recommended
- Optional: PHP CLI with `curl` extension if using PHP attack scripts locally

## Quick Start

The sandbox targets the current releases in the sibling AIWAF checkout: Python
`1.0.8`, Rust `0.2.1`, Node package `aiwaf` `1.0.2`, WASM `0.2.0`, and Java
`1.3.0`. Spring uses Boot `4.0.8` to match AIWAF Java's Spring 7 dependencies.
Node proxies now import `aiwaf`; the old `aiwaf-js` dependency and WASM symlink
workarounds have been removed. PHP continues to use its separate Composer package.

From repo root:

```bash
docker compose up -d --build
docker compose ps
```

## Standard Validation Workflow

Install the Python runner dependency before running the suite locally:

```bash
python -m pip install requests
python -m unittest discover -s examples/sandbox -p 'test_*.py'
node --test examples/sandbox/common/redis-cache.test.js
python examples/sandbox/smoke-test.py
```

Rate-limit and brute-force scenarios now retain one client IP for the entire
scenario, with a fresh generated IP for the next scenario. Other probes retain
per-request rotation. This allows the suite to exercise cumulative rate limits
and reputation blocking without mixing unrelated generated clients.

The smoke test checks normal requests, a disallowed automation user agent, and a burst from one
client against Node, all three Python and PHP proxies, Java, and Spring. Select individual
targets with repeated `--target NAME=URL` arguments. It exits with a failure status
when a proxy is unreachable, blocks normal traffic, or misses the automation/burst.

### Redis integration

Redis is part of the default root stack. `docker compose up -d --build` starts it
and waits for its health check before starting protected services. Redis uses AOF
persistence in the `redis_data` volume and is accessible only inside the Compose
network. The former optional Redis override has been merged into the root file.

| Runtime | Redis-backed state | Database |
| --- | --- | --- |
| Node frameworks | Rate-limit lists through AIWAF's cache adapter | 0-7, one per framework |
| Django | Django cache: rate limits, honeypot and anomaly history | 8 |
| Flask | Rate-limit cache | 9 |
| FastAPI | Rate-limit cache | 10 |
| Laravel / Symfony / WordPress | Rate-limit counters via the PHP Redis extension | 11 / 12 / 13 |
| Java / Spring, including R variants | Engine state, including reputation and distributed counters | 14, separate prefixes |

Python and Node blacklist/model storage continues to use the backends supported
by those AIWAF adapters. Redis integration does not move that storage into Redis.
Each service has an isolated database or key prefix. Startup state clearing is
disabled so service restarts preserve state. Rate-limit keys still expire normally.

PHP routers load Composer's autoloader from `examples/vendor`. Their UUID-only
path rule is disabled because Juice Shop routes do not require UUIDs; the PHP
package otherwise rejects ordinary paths before they reach the target.

Java uses standalone Redis with bounded connection/socket/pool waits and defaults
to `fail_closed`. Set `AIWAF_REDIS_FAILURE_MODE=fail_open` before recreating Java
services to exercise the other policy. Other runtimes retain their library's
Redis failure behavior.

```bash
docker compose exec redis redis-cli INFO keyspace
docker compose exec redis redis-cli -n 14 --scan --pattern 'sandbox:*'
docker compose stop redis
docker compose start redis
```

Redis data survives normal `docker compose down`. Removing Compose volumes with
`down -v` removes the stored sandbox state.

The plain Java proxy reads `/app/aiwaf.json` and applies AIWAF environment
overrides. Mount another JSON file and set `AIWAF_CONFIG_FILE` to test a custom
policy. Spring uses AIWAF's Boot auto-configuration, including route discovery
and environment/property configuration. The plain Java proxy now supplies body
previews and decoded query values to the engine for inspection.

Spring trusts forwarded client IPs from `172.16.0.0/12` for the sandbox's Docker
bridge traffic. Override `AIWAF_SANDBOX_TRUSTED_PROXY_CIDRS` for a different Docker
network. This lets the runner simulate public client IPs instead of exempting all
traffic as private bridge traffic; use the actual proxy CIDRs in a deployment.

### 1) Run full multi-runtime suite

```bash
python3 examples/sandbox/attack-suite.py
```

### 2) Print summary table

```bash
python3 examples/sandbox/compare-results-modes.py
```

### 3) Inspect generated artifacts

Generated under `examples/sandbox/`:

- `results_<target>_normal_<run-id>.json`
- `results_<target>_attacks_<run-id>.json`
- `comparison_modes_<run-id>.json`

## Targeted Runs

Attack-only against one target:

```bash
python3 examples/sandbox/attack-suite.py http://localhost:8081 protected_laravel --mode attacks
```

Normal-only against one target:

```bash
python3 examples/sandbox/attack-suite.py http://localhost:3000 protected_node --mode normal
```

## Expected Results

Healthy behavior usually looks like:

- `direct`: low or near-zero blocked percentage for attacks
- `protected_*`: high blocked percentage for attacks
- `normal` traffic: near-zero blocked across all targets

Small variation across frameworks is normal due to middleware/runtime differences.

## PHP Configuration Notes

Package:

- Composer package: `aayushgauba/aiwaf` (`dev-main` in this sandbox)

Runtime behavior in this sandbox:

- PHP images install the Redis extension and initialize AIWAF's `RedisAdapter`.
- `AIWAF_REDIS_URL` selects the shared server and a separate database per framework.
- `AIWAF_RATE_CACHE_KEY_PREFIX` isolates rate-limit keys.
- The routers no longer force SQLite for rate limiting.

## Running PHP-Only Suite

From repo root:

```bash
php examples/attack-suite.php
php examples/compare-results-modes.php
```

If PHP reports `Call to undefined function curl_init()`, install/enable PHP curl or use the Python suite instead.

## Common Operations

### Rebuild all

```bash
docker compose down --remove-orphans
docker compose up -d --build
```

### Rebuild only PHP services

```bash
docker compose build aiwaf-laravel-php81 aiwaf-symfony-php82 aiwaf-wordpress-php80
docker compose up -d aiwaf-laravel-php81 aiwaf-symfony-php82 aiwaf-wordpress-php80
```

### Check container env

```bash
docker exec aiwaf_laravel_php81_all printenv | grep AIWAF_REDIS
docker exec aiwaf_symfony_php82_all printenv | grep AIWAF_REDIS
docker exec aiwaf_wordpress_php80_all printenv | grep AIWAF_REDIS
```

### Tail logs

```bash
docker logs --tail 200 aiwaf_laravel_php81_all
docker logs --tail 200 aiwaf_symfony_php82_all
docker logs --tail 200 aiwaf_wordpress_php80_all
```

### Check runtime health quickly

```bash
docker compose ps
curl -I http://localhost:3001
curl -I http://localhost:8081
```

## Troubleshooting

### Protected targets show low detection

Actions:

1. Rebuild/restart cleanly:
   - `docker compose down --remove-orphans`
   - `docker compose up -d --build`
2. Verify env vars exist in target containers.
3. Confirm you are testing against protected ports, not direct backend.
4. Re-run attack suite and compare scripts.

### Compose network cannot be removed

If `down` reports network still in use, another compose stack is attached.

Actions:

1. Stop other attached containers or stacks.
2. Re-run:
   - `docker compose down --remove-orphans`

### Python suite fails on some targets

If a service/port is unavailable, the runner stops with reachability error.

Actions:

1. `docker compose ps`
2. Restart missing services
3. Run targeted command for the affected target first

## Data and Git Hygiene

- Generated artifacts are ignored by `.gitignore`
- Runtime/log artifacts under sandbox resources are ignored
- Keep committed changes focused on code/config, not generated reports

## Security/Usage Notes

- This repository is for controlled testing and validation
- Attack payloads are for defensive WAF evaluation only
- Do not run this stack against systems you do not own or control
