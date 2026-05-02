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

From repo root:

```bash
docker compose up -d --build
docker compose ps
```

## Standard Validation Workflow

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

- PHP targets are configured for DB-backed rate limiting
- Environment variables set in root compose:
  - `AIWAF_RATE_LIMIT_BACKEND=db`
  - `AIWAF_RATE_LIMIT_DB_PATH=/workspace/resources/aiwaf.sqlite`

Why DB backend:

- Ensures rate-limit state persists across requests reliably in containerized execution
- Avoids transient behavior sometimes seen with in-memory-only setup

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
docker exec aiwaf_laravel_php81_all printenv | grep AIWAF_RATE_LIMIT
docker exec aiwaf_symfony_php82_all printenv | grep AIWAF_RATE_LIMIT
docker exec aiwaf_wordpress_php80_all printenv | grep AIWAF_RATE_LIMIT
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
