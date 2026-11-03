# AIWAF Multi-Runtime Sandbox

Unified sandbox for validating AIWAF behavior across Node.js, Python, PHP, and Java services using OWASP Juice Shop as the target application.

## Overview

This repository is designed for:

- Running many framework/runtime integrations in one stack
- Comparing direct (unprotected) vs protected traffic
- Executing repeatable attack simulations
- Generating machine-readable comparison reports
- Verifying parity and detection performance across runtimes

Start with one protected endpoint, then expand to the fifteen published-package integrations. PHP examples and reference-application assessments have separate scopes. This README describes how to run checks; it does not record historical pass rates or certify OWASP compliance.

## Contents

- [Architecture](#architecture)
- [Service matrix](#service-matrix)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Standard validation workflow](#standard-validation-workflow)
- [Redis integration](#redis-integration)
- [OWASP companion assessment](#owasp-2025-companion-assessment)
- [Reports and exit statuses](#reports-and-exit-statuses)
- [Contributor tests](#contributor-tests)
- [Dependency maintenance](#dependency-maintenance)
- [Common operations](#common-operations)
- [Troubleshooting](#troubleshooting)

The [AIWAF sandbox documentation](https://aiwaf.org/docs/sandbox/) presents the same workflow as a tutorial, runtime reference, validation guide, OWASP scope guide, and operations guide.

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

All published host ports bind to `127.0.0.1`. Use the test name with
`--target NAME=URL` in smoke, login and matrix runners; use the service name with
Docker Compose. The older attack suite uses labels such as `protected_node`.

| Test name | Compose service | Host port | Redis DB |
| --- | --- | ---: | ---: |
| node (Express) | aiwaf | 3000 | 0 |
| fastify | aiwaf_fastify | 3002 | 1 |
| hapi | aiwaf_hapi | 3003 | 2 |
| koa | aiwaf_koa | 3004 | 3 |
| nest | aiwaf_nest | 3005 | 4 |
| next | aiwaf_next | 3006 | 5 |
| adonis | aiwaf_adonis | 3007 | 6 |
| sails | aiwaf_sails | 3008 | 7 |
| django | aiwaf-django | 3009 | 8 |
| flask | aiwaf-flask | 3010 | 9 |
| fastapi | aiwaf-fastapi | 3011 | 10 |
| java | aiwaf-java | 8080 | 14 |
| spring | aiwaf-spring | 8084 | 14 |
| java-r | aiwaf-java-r | 8085 | 14 |
| spring-r | aiwaf-spring-r | 8086 | 14 |
| laravel (separate PHP package) | aiwaf-laravel-php81 | 8081 | 11 |
| symfony (separate PHP package) | aiwaf-symfony-php82 | 8082 | 12 |
| wordpress (separate PHP package) | aiwaf-wordpress-php80 | 8083 | 13 |
| direct Juice Shop baseline | juice | 3001 | — |
| direct reference fixture | security-fixture | 8090 | — |
| protected reference fixture | aiwaf-assessment | 3020 | 15 |
| direct / protected TLS fixture | assessment-tls | 8443 / 8444 | — |

Java variants share DB 14 with distinct storage prefixes. R variants run the Java
engine in images containing R; they are not independent R SDKs. Redis has no host
port. The reference fixture and TLS services require optional profiles.

## Repository Layout

- `docker-compose.yml`: root stack for all runtimes
- `examples/`: shared examples and package setup
- `examples/sandbox/`: runtime service implementations and test tooling
- `examples/sandbox/run-published-packages.py`: full published-package validation
- `examples/sandbox/attack-suite.py`: legacy normal/attack observations
- `examples/sandbox/compare-results-modes.py`: normal vs attack summary
- `examples/sandbox/compare-results.py`: per-attack comparison helper

## Prerequisites

- Docker Desktop or Docker Engine + Compose plugin
- Python 3.10+ and `requests` for host runners
- Git and network access to package registries and container registries
- Docker Desktop running Linux containers; enough disk/memory for multiple builds
- Node.js 22 and npm only when running JavaScript helper tests on the host
- No host PHP, Java, Maven, or AIWAF checkout needed for the Compose runtime builds

Run commands from the repository root unless a block explicitly changes directory.
The commands use `python`; use `python3` if that is your interpreter name.
PowerShell-specific commands are labelled.

## Quick Start

The 15 non-PHP proxies install published releases directly from package managers:

| Registry | Package | Pinned version |
| --- | --- | --- |
| PyPI | aiwaf | 1.1.8 |
| PyPI | aiwaf-rust | 0.2.7 |
| npm | aiwaf | 1.1.5 |
| npm | aiwaf-wasm | 0.2.5 |
| Maven Central | io.github.aiwaf-project:aiwaf-java | 1.3.5 |

The pins are recorded in `examples/sandbox/package-versions.json`, Python wheel
hash locks, npm lockfiles and the example Maven properties. No GitHub source
build context or local SDK symlink is used. PHP continues to use its separate
Composer package and is excluded from this release validation run. Base-image
digests and the existing patched proxy dependencies remain pinned.

### First run: Express, Redis and Juice Shop

```bash
git clone https://github.com/aayushgauba/sandbox.git
cd sandbox
docker version
docker compose version
python -m pip install requests
docker compose build aiwaf
docker compose up -d aiwaf
docker compose ps
python examples/sandbox/smoke-test.py --target node=http://127.0.0.1:3000 --burst-workers 16 --output examples/sandbox/results_first_smoke.json
python examples/sandbox/validate-login-bypass.py --target node=http://127.0.0.1:3000 --output examples/sandbox/results_first_login.json
```

Build Express first: the one-shot log ownership initializer uses its
`sandbox-aiwaf` image. Compose starts Redis, Juice Shop and that initializer as
dependencies. The initializer finishing with exit 0 is expected. Wait for the
upstream to be healthy before testing. Direct traffic uses port 3001; protected
traffic uses port 3000. A normal browser request should reach Juice Shop; the
smoke runner supplies the headers needed for synthetic traffic.

### Expand to the published-package matrix

```bash
docker compose up -d --build aiwaf aiwaf_fastify aiwaf_hapi aiwaf_koa aiwaf_nest aiwaf_next aiwaf_adonis aiwaf_sails aiwaf-django aiwaf-flask aiwaf-fastapi aiwaf-java aiwaf-spring aiwaf-java-r aiwaf-spring-r
python examples/sandbox/run-published-packages.py --verify-only
```

The verifier checks installed package versions against `package-versions.json`
and records image IDs. It requires all fifteen services. A sibling SDK checkout
does not change the packages inside an image. To include the three PHP examples,
use `docker compose up -d --build` without a service selection; PHP is excluded
from the published-package runner.

## Standard Validation Workflow

After starting all fifteen integrations, prepare the reference services, isolated
audit image and TLS trust before running the full workflow:

```powershell
docker compose --profile assessment-tools build aiwaf-audit-tools
docker compose --profile assessment --profile assessment-tls up -d --build security-fixture aiwaf-assessment assessment-tls
New-Item -ItemType Directory -Force examples/sandbox/assessment/.tls
docker compose --profile assessment --profile assessment-tls cp assessment-tls:/data/caddy/pki/authorities/local/root.crt examples/sandbox/assessment/.tls/root.crt
python examples/sandbox/run-published-packages.py
```

On POSIX shells, replace `New-Item` with
`mkdir -p examples/sandbox/assessment/.tls`. Wait for Caddy to create the public
root certificate before copying it. This explicit CA file does not alter the host
trust store. Keep TLS verification enabled.

The runner checks installed versions, effective runtime hardening, smoke requests,
SQL login outcomes, payload observations, post-matrix SQL controls, extended
reference/TLS outcomes, eight proxy production npm lockfiles, isolated outages,
and image advisories, in that order. It writes `results_published_*` reports.
`--verify-only` performs version checks only. `--skip-image-scans` omits Grype;
it does not establish an image-audit pass and does not refresh an old image report.
The full runner has no resume flag. Run suites sequentially so builds and scans do
not distort request timing. Unit tests are described under [contributor tests](#contributor-tests).

The full runner also renders `results_published_owasp_summary.md` when image
scanning is enabled. To render a complete matching set of reports again:

```bash
python examples/sandbox/assessment/render_report.py --prefix published
```

Use fresh isolated Redis/log volumes for a fresh-state run without deleting old
volumes. A fresh image alone does not clear persistent state. Keep existing state
when deliberately testing upgrades or retention.

The 15 non-PHP serving runtimes run as UID/GID 10001, with a read-only root
filesystem, all capabilities dropped and privilege escalation disabled. Only
`/tmp`, `/state`, the shared `/logs` volume and Next's build cache are writable.
Application code and installed dependencies stay read-only. `/state` is temporary
test state and resets when the container stops or is recreated; Redis and `/logs` retain
their existing volume lifetimes. Django's demo SQLite database is under `/state`.
A one-shot `aiwaf-state-init` service creates log directories and migrates existing
log ownership; it runs as root with CHOWN/DAC_OVERRIDE capabilities only. Redis,
Juice Shop, PHP and the reference fixtures have separate security configurations.

Node serving images contain no npm/npx/Yarn and start Node directly. Audits use
the manifest and lockfile copied from each runtime in a short-lived audit tools
container; Grype separately scans the installed image contents. Java runtime
images remove the unused `pebble` executable. Host port bindings default to
loopback, including the deliberately vulnerable Juice Shop target. Distribution
updates are applied during builds; rebuild after new vendor fixes and review
image scans. These controls do not guarantee a vulnerability-free deployment.

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
| A05 Injection | SQL login-bypass assertions and benign login controls across all fifteen published-package integrations | Other payloads remain observations until an application outcome assertion is provided; no blanket injection pass. |
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
`not_assessed`; any failure/error produces exit code 1. Findings and local HTTP can cause a completed assessment to exit 1.
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

## PHP Configuration Notes

Package:

- Composer package: `aayushgauba/aiwaf` (`dev-main` in this sandbox)

Runtime behavior in this sandbox:

- PHP images install the Redis extension and initialize AIWAF's `RedisAdapter`.
- `AIWAF_REDIS_URL` selects the shared server and a separate database per framework.
- `AIWAF_RATE_CACHE_KEY_PREFIX` isolates rate-limit keys.
- The routers no longer force SQLite for rate limiting.

## Reports and exit statuses

Reports live under `examples/sandbox/` and are ignored by Git. They contain
observations from your own run, not release guarantees.

| Report / tool | Interpretation |
| --- | --- |
| `results_published_versions.json` | Installed package versions and container image IDs |
| `results_published_run.json` | Selected targets and per-suite exit codes |
| `results_published_smoke.json` | Normal and lowercase headers, automation, mixed accepted/denied burst, benign JSON forwarding |
| `results_published_login.json`, `results_published_login_after_matrix.json` | Two SQL token-issuance assertions plus benign login controls before/after attack traffic |
| `results_published_payload.json` | Payload response observations; exit 0 means no request errors, not that every exploit was prevented |
| `results_published_hardening.json` | Effective permissions and runtime isolation checks |
| `results_published_owasp_extended.json` | Reference application and transport assertions |
| `results_published_npm_audits.json` | Eight production proxy lockfile audits, including their transitive dependencies |
| `results_published_outages.json` | Isolated Express Redis/upstream connection failure checks |
| `results_published_image_advisories.json`, `results_owasp_scan_*.json` | Image summaries and raw package-location evidence |
| `results_published_validation.md`, `results_published_owasp_summary.md` | Aggregate runtime and category reports |

Assessment statuses mean: `pass` = the specific assertion holds; `fail` = an
assertion or advisory policy is violated; `error` = the check could not complete;
`not_assessed` = no conclusion for that control. Failures/errors produce exit 1.
Image scanning fails on high/critical findings or scan errors, while retaining
lower-severity matches. The full runner exits nonzero for failed suites or
required runtime assertions. Read the JSON evidence rather than treating an exit
code as an OWASP score.

The legacy attack suite treats HTTP 403/405/409/429 as blocked. Those responses
may come from the application or header validation before payload inspection;
block percentages are not proven detection rates. Reference application checks
require the expected response fields and side effects, so an unrelated WAF denial
cannot pass an authorization or business-rule assertion.

Standalone tools use their own output defaults. Pass `--output` explicitly when
assembling a report set. Do not mix reports from different versions, configurations
or state. Renderers combine saved files without establishing that every component
belongs to the same run. Retain provenance in reports, not historical results in
this guide.

## Contributor tests

Python harness tests start local HTTP listeners; they do not require the full
Compose matrix. Install `requests` first:

```bash
python -m pip install requests
python -m unittest discover -s examples/sandbox -p 'test_*.py'
node --test examples/sandbox/common/redis-cache.test.js
```

The shared proxy helper resolves `httpxy` from the current working directory.
For its tests, install the Express development tree and run from that directory:

```bash
cd examples/sandbox/aiwaf-proxy
npm ci
node --test ../common/proxy.test.js
cd ../../..
```

This installs host dependencies; it does not update the lockfile or the running
container. Do not commit `node_modules`. For a proxy change, also rebuild the
affected service and run targeted smoke and login checks. Use the full published
workflow for changes affecting shared configuration or multiple runtimes.

The separate `examples/sandbox/docker-compose.adapters.yml` describes PHP
Redis/MySQL adapter tests. It is not an override for the root stack and is outside
the fifteen-runtime release workflow. Review its PHPUnit/vendor prerequisites
before using it; do not count it as coverage from the published runner.

## Dependency maintenance

1. Choose a narrowly scoped update and review the package's release notes and
   advisory. Distinguish framework, transitive SDK, build-tool and OS packages.
2. Update the affected manifests and locks together. For npm, run the targeted
   update from the appropriate proxy directory; builds use `npm ci`. Avoid
   `npm audit fix --force` and unrelated major-version changes.
3. For an AIWAF release update, keep `package-versions.json`, npm manifests/locks,
   Python installation declarations and hash locks, and Java/Spring POM
   properties consistent. Changing the inventory alone does not install packages.
4. Rebuild/recreate affected services. Run installed-version verification after
   all fifteen containers reflect the selected release set, then targeted tests
   and the full workflow as appropriate.
5. Include old/new versions, relevant advisory, lockfile diff and test evidence in
   the PR. Document remaining findings; do not commit generated reports.

`registry-versions.py` queries public registries and **overwrites**
`package-versions.json` with their latest versions. It is a maintainer update tool,
not a read-only inspection command or a full upgrade. Review its diff and reconcile
all build declarations before committing.

`lock-python-dependencies.py` reads installed distributions from the running
Django/Flask/FastAPI containers and downloads matching wheels to regenerate
Linux x86_64 / CPython 3.11 hashes. It excludes the main `aiwaf` distribution and
refreshes wheel/setuptools separately. Preserve/reinsert the AIWAF release pin and
hash in each `requirements.lock`: a full refresh drops that distribution from
its output. Review the complete diff before rebuilding. Use only containers with the intended dependency set.
`--refresh-build-tools` replaces only wheel/setuptools lock entries. These
commands require network access and modify committed lockfiles.

Serving Node images deliberately omit npm/npx/Yarn. Use host lockfile auditing or
the separate audit tools image:

```bash
npm audit --prefix examples/sandbox/aiwaf-proxy --omit=dev --package-lock-only
docker compose --profile assessment-tools build aiwaf-audit-tools
python examples/sandbox/audit-published-proxies.py
python examples/sandbox/assessment/scan_images.py
```

Do not use the audit script's legacy `--include-sdk` option with registry images:
it expects the removed `/opt/aiwaf-js` source installation. Proxy production locks
already include installed AIWAF dependencies. Grype separately examines image
contents, including other ecosystems and OS packages. A pin improves input control;
it does not prove absence of vulnerabilities or bit-for-bit reproducibility.

## Common Operations

Run from the repository root:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 aiwaf
docker compose exec redis redis-cli INFO keyspace
```

Select a service name to rebuild or inspect one runtime. Keep named volumes
when restarting so retained state remains available for validation. `docker compose
stop` stops containers; `docker compose down` removes containers/network while
preserving named volumes. `docker compose down -v` deletes named volume state,
including Redis, logs and the assessment CA: use it only for an intentional reset.

Optional root profiles are `assessment` (fixture/proxy), `assessment-tls` (Caddy,
used with assessment), `assessment-tools` (audit image), `trainer` (PHP training
example) and `tests` (PHP test image). PHP helpers are independent of the published
runtime checks. Inspect their commands and prerequisites before use.

## Troubleshooting

### Docker is unavailable or an image is missing

Start Docker Desktop, select Linux containers and check `docker version` for a
server response. `docker compose config --quiet` checks configuration without
starting containers. If the initializer cannot find `sandbox-aiwaf`, run
`docker compose build aiwaf` first. A successful initializer exits instead of
remaining running. Resolve port conflicts using `docker compose ps` and the
service matrix before changing ports; pass matching URLs to targeted runners.

### Version checks or helper tests fail

Rebuild/recreate containers after changing package pins; `restart` alone keeps the
same image. A full verifier requires all fifteen non-PHP proxies. For missing
`httpxy`, follow the contributor test working-directory instructions. For registry
or wheel errors, check network/proxy access and the Linux x86_64/Python 3.11 lock
platform; do not substitute unreviewed versions.

### TLS or advisory checks fail

Start both assessment profiles, use `localhost` for TLS and export Caddy's public
root certificate. Restart Caddy after a large host-clock change. Advisory scanning
requires network access and Docker's Linux engine; a scan error is not a clean
result. npm can return nonzero even when the particular advisory being fixed has
been removed, because other findings remain.

### Protected targets show low detection

Actions:

1. Inspect logs and retained Redis state, then rebuild if configuration changed:
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
