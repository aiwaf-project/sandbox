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

The 15 non-PHP proxies build Python and JavaScript `1.1.1` and Java `1.3.2`
from [AIWAF on GitHub](https://github.com/aayushgauba/aiwaf), pinned to commit
`843a35f4fd48b4ef565e3c1ec8a42db9b1c41946`. Docker BuildKit clones the
repository as the `aiwaf_source` additional build context; a separate checkout
is unnecessary. Builds require GitHub network access. To update the source,
change the `x-aiwaf-source` URL in Compose and matching source labels in the
Dockerfiles, review SDK version requirements, then rebuild. Rust/WASM remain
registry `0.2.1`. Spring uses Boot `4.0.8` to match AIWAF Java's Spring 7 dependencies.
Its dependency management overrides Tomcat to `11.0.25` and Jackson to
`2.22.3`/`3.1.7` for security fixes. Node builds use a separate compiler stage
and a digest-pinned slim runtime, with patched npm CLI components. Python
uses a refreshed digest-pinned 3.11 base and hash-locked setuptools/wheel.
Java/R images pin the patched Ubuntu OpenSSL packages. Runtime images copy
only their own application and shared proxy helpers.
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
python examples/sandbox/smoke-test.py --all --output examples/sandbox/results_aiwaf_smoke_matrix.json
python examples/sandbox/smoke-test.py --all --burst-workers 16
python examples/sandbox/validate-runtime-matrix.py
python examples/sandbox/validate-login-bypass.py
python examples/sandbox/run-source-packages.py
python examples/sandbox/render-validation-report.py
```

`run-source-packages.py` verifies the GitHub source label and tests the 15 non-PHP proxies, saving separate
`results_local_*.json` evidence and `results_local_validation.md`. It runs smoke,
SQL token-issuance assertions, the payload matrix, post-matrix login controls,
reference application checks, and production npm audits of all eight proxy
dependency trees plus the source-built SDK. Start the assessment profile first with
`docker compose --profile assessment up -d --build`. PHP is excluded from this
runner while its new release is unpublished. `--verify-only` checks the running
source labels and SDK versions. `--skip-completed` reuses suite reports only
when the recorded source URL and commit match; omit it for a new run.

The old published-package runner expects registry versions and should not be
used against this source build configuration. Existing reports from earlier local
draft runs remain historical evidence; rebuild and run fresh suites for this commit.

Local runtime builds use `npm ci` with lockfiles, Python wheel hashes for Linux
x86_64/CPython 3.11, and base-image digests. Refresh Python locks explicitly with
`python examples/sandbox/lock-python-dependencies.py` after reviewing dependency
updates. The local dependency inventory scopes its assertion to these 15 runtime
build declarations; PHP and helper images are excluded. It is not a full SBOM,
OS package audit, or proof that builds are bit-for-bit identical.

Rate-limit and brute-force scenarios now retain one client IP for the entire
scenario, with a fresh generated IP for the next scenario. Other probes retain
per-request rotation. This allows the suite to exercise cumulative rate limits
and reputation blocking without mixing unrelated generated clients.

The smoke test checks normal requests, a disallowed automation user agent, and a burst from one
client against Node, all three Python and PHP proxies, Java, and Spring. Select individual
targets with repeated `--target NAME=URL` arguments. It exits with a failure status
when a proxy is unreachable, blocks normal traffic, or misses the automation/burst.
`--all` selects all 18 proxies and `--output` saves the individual header and
rate-limit assertions. Header casing is preserved on the wire. The runtime
matrix uses browser headers for payload probes, except where a scenario deliberately
overrides them, and saves per-scenario responses alongside direct generic/PHP
baselines in `results_aiwaf_payload_matrix.json`. Its rows describe observed denials,
not exploit prevention or correlated AIWAF decisions. Request errors produce
exit code 1; an exit code 0 means the run completed, not that every payload was denied.

The login-bypass check confirms whether two SQL payloads issue authentication
tokens, using a normal invalid-credentials request as the control. It reports
failures for tokens issued through the proxy and errors when the control cannot
reach the application. Tokens are excluded from reports. The renderer combines
saved smoke, payload, login and companion results into `results_aiwaf_validation.md`.
Runs retain learned Redis state: later normal-request failures can expose false
positives caused by earlier attack traffic. Burst checks require both accepted
and denied requests, so blanket blocking cannot pass that assertion.

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

## OWASP 2025 companion assessment

The payload suite does not establish coverage of all OWASP risks. The companion
assessment adds authorization, authentication, deployment, transport, supply
chain, business-rule, integrity, logging and exception outcomes. It keeps
repository findings, transport findings and reference-application outcomes
separate from the original runner's HTTP block counts.

Start the optional assessment profile from this repository's root:

```bash
docker compose --profile assessment up -d --build security-fixture aiwaf-assessment
python -m unittest discover -s examples/sandbox -p 'test_*.py' -v
python examples/sandbox/assessment/run.py --fixture http://localhost:8090 --fixture http://localhost:3020 --npm-audit --transport-url http://localhost:3020
```

Both new ports bind to loopback. Port 8090 is the direct reference application;
3020 runs the same checks through an Express AIWAF proxy using Redis database 15
and the `sandbox:assessment:rate:` prefix. Its rate budget is deliberately high
so concurrent business-rule checks can reach the application. The existing
rate-limit smoke checks remain separate. No assessment service starts with the
default profile, and these endpoints are not added to Juice Shop.

| OWASP category | Added checks | Scope and remaining limits |
| --- | --- | --- |
| A01 Broken Access Control | Cross-user reads/writes, anonymous access, role spoofing, protected-field assignment and CSRF | Reference application authorization. AIWAF does not supply the application's identity/ownership policy. |
| A02 Security Misconfiguration | Sensitive-file/debug probes and observable security response headers | Fixture and protected endpoint. Host/cloud configuration audits remain separate. |
| A03 Software Supply Chain Failures | Hash-locked Python installs, npm locks, pinned runtime base images, npm production audit; pinned Grype image scans for Java/Python/JS/OS advisories | Fifteen non-PHP images. Advisory matches require package-location triage. Package provenance and PHP are not assessed. |
| A04 Cryptographic Failures | TLS 1.2/1.3 with trusted certificates, rejection of TLS 1.0/1.1, untrusted certificates and incorrect hostname; PBKDF2 hashes and independent salts | Sandbox TLS termination and reference passwords. At-rest encryption and production key management remain separate. |
| A05 Injection | SQL login-bypass assertions and benign login controls across all fifteen local integrations | Other payloads remain observations until an application outcome assertion is provided; no blanket injection pass. |
| A06 Insecure Design | Negative quantities, idempotent replay, conflicting payloads under one idempotency key, concurrent inventory budget | Isolated reference business rules; application-owned controls. |
| A07 Authentication Failures | Session rotation, logout/revocation/expiry, reset token actor binding/expiry/single use, MFA requirement/actor binding/replay | Reference identities. Reset delivery and MFA codes use test-only fixture controls, not a real provider. |
| A08 Software or Data Integrity Failures | Accept original signed data; reject a modified subject and forged signature | HMAC-protected reference data. No claim about package signing or Juice Shop's integrity boundaries. |
| A09 Security Logging and Alerting Failures | Correlate a failed login with exactly one redacted event and alert; reject modified or truncated event history | In-memory reference event/alert sink. External SIEM delivery and persistent append-only storage are not assessed. |
| A10 Mishandling of Exceptional Conditions | Generic injected-error response and subsequent recovery; isolated real Redis/upstream connection failures; SDK outage regression tests | Live Express outage checks and Python unit/HTTP regressions. Per-runtime failover and production chaos testing remain separate. |

The runner generates fresh test passwords and isolated inventory for each run,
checks both statuses and response fields/side effects, and removes its reference
state afterward. An unexpected WAF denial cannot pass an application check just
because it returns 403. Regression tests run against secure and deliberately
broken fixture modes to demonstrate that failures are detected in A04/A06/A08/A09.
The vulnerable mode is available only via the fixture CLI for regression tests;
the Compose service always starts in secure mode.

`AIWAF_ASSESSMENT_TOKEN` can override the local control credential. Set the same
value in the shell for Compose and the runner, then recreate the fixture. The
default `sandbox-assessment-only` credential is test-only; this is an isolated
reference application, not a production service. Passwords and control tokens
are excluded from reports. Fixture state and its signing key are ephemeral.

Results are written to `examples/sandbox/results_owasp_assessment.json`, separately
from `comparison_modes_*.json`. Checks report `pass`, `fail`, `error` or
`not_assessed`; any failure/error produces exit code 1. Current reproducibility
gaps and local HTTP are findings, so a completed assessment can correctly exit 1.
To exclude loopback HTTP from TLS assessment explicitly, add `--allow-local-http`;
this records `not_assessed`, never a TLS pass. Omit `--npm-audit` for an offline
repository check; the advisory check is then explicitly unassessed. Use
`--audit-service aiwaf` to audit the original running Express service instead.
Neither command installs updates or repairs findings automatically.

Stop only the optional services when finished:

```bash
docker compose --profile assessment stop aiwaf-assessment security-fixture
```

Category definitions: [OWASP Top 10:2025](https://top10.owasp.org/).

### Extended outcomes and TLS

The TLS profile binds only to loopback. Its CA stays in a dedicated Docker
volume; export only the public certificate and pass it explicitly to the runner.
No host trust-store installation or disabled certificate verification is needed.

```powershell
docker compose --profile assessment --profile assessment-tls up -d --build security-fixture aiwaf-assessment assessment-tls
New-Item -ItemType Directory -Force examples/sandbox/assessment/.tls
docker compose --profile assessment --profile assessment-tls cp assessment-tls:/data/caddy/pki/authorities/local/root.crt examples/sandbox/assessment/.tls/root.crt
python examples/sandbox/assessment/run.py --extended --fixture https://localhost:8443 --fixture https://localhost:8444 --ca-file examples/sandbox/assessment/.tls/root.crt --tls-url https://localhost:8443 --tls-url https://localhost:8444 --local-runtime-scope --output examples/sandbox/results_local_owasp_extended.json
python examples/sandbox/assessment/outages.py
python examples/sandbox/assessment/scan_images.py
python examples/sandbox/assessment/render_report.py
```

Use both profiles together because the TLS service depends on assessment
services. Caddy renews its short-lived local leaf certificates; restart
`assessment-tls` after a large host clock change. The Grype scanner requires
Docker's Linux engine and network access to its advisory database. Its image is
pinned by digest; its database uses the dedicated `sandbox_grype_db` Docker
volume to avoid slow SQLite access through a Windows bind mount. Caches and
reports are ignored and excluded from build images.
The scanner exits 1 for scan errors or high/critical findings and records lower
severity findings too. A category can have passing scenarios and outstanding
findings: these checks are not OWASP certification or complete risk coverage.

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
