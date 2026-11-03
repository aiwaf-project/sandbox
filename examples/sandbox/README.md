# Sandbox tools

Run Docker Compose commands from the repository root. The root
[README](../../README.md) documents package versions, services, Redis,
validation, and the optional OWASP assessment. The root
[docker-compose.yml](../../docker-compose.yml) is the stack definition.

## Validation entry points

- `run-published-packages.py`: verify and test the fifteen registry-package integrations.
- `registry-versions.py`: query registries and overwrite the package pins in `package-versions.json`.
- `smoke-test.py`: normal requests, automation, rate limits, and JSON forwarding.
- `validate-login-bypass.py`: SQL login outcomes with benign controls.
- `validate-runtime-matrix.py`: payload observations across selected integrations.
- `attack-suite.py`: normal/attack traffic comparisons.
- `run-and-compare.py`: repeated comparison runs and aggregate statistics.
- `assessment/`: reference outcomes, TLS, outages, image scans, and runtime hardening.

The independent `docker-compose.adapters.yml` runs optional PHP Redis/MySQL
adapter tests. It is separate from the root stack.

Generated results are local artifacts, not package/configuration files.
Keep source, manifests, lockfiles, fixtures, and tests when cleaning a workspace.
HTTP block counts alone do not demonstrate exploit prevention or complete OWASP coverage.
