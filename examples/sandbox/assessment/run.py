"""Outcome-based OWASP 2025 companion checks, separate from payload block counts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"


def result(category, name, scope, passed, evidence):
    return {"category": category, "check": name, "scope": scope,
            "status": "pass" if passed else "fail", "evidence": evidence}


def supply_chain(root, runtime_scope=False):
    """Inventory declared dependencies and reproducibility gaps, not a CVE scan."""
    inventory, gaps = [], []
    selected = {f'aiwaf-{name}-proxy' for name in ('django', 'flask', 'fastapi', 'fastify', 'hapi', 'koa', 'nest', 'next', 'adonis', 'sails')}
    selected.update(('aiwaf-proxy', 'aiwaf-java', 'aiwaf-spring', 'aiwaf-java-r', 'aiwaf-spring-r'))
    for package in sorted((root / "examples/sandbox").glob("aiwaf-*/package.json")):
        if runtime_scope and package.parent.name not in selected:
            continue
        manifest = json.loads(package.read_text())
        deps = manifest.get("dependencies", {})
        lock = package.with_name("package-lock.json")
        inventory.append({"manifest": package.relative_to(root).as_posix(), "ecosystem": "npm",
                          "dependencies": deps, "lockfile": lock.exists(),
                          "sha256": hashlib.sha256(package.read_bytes()).hexdigest()})
        if not lock.exists():
            gaps.append(f"{package.parent.name}: no committed package-lock.json; image uses npm install")
    composer = root / "examples/composer.lock"
    if composer.exists() and not runtime_scope:
        packages = json.loads(composer.read_text()).get("packages", [])
        inventory.append({"manifest": "examples/composer.lock", "ecosystem": "composer",
                          "dependencies": {p["name"]: p["version"] for p in packages},
                          "sha256": hashlib.sha256(composer.read_bytes()).hexdigest()})
        if any(p.get("version", "").startswith("dev-") for p in packages):
            gaps.append("Composer locks a development branch; review its pinned source revision")
    for dockerfile in sorted((root / "examples/sandbox").glob("aiwaf-*/Dockerfile")):
        if runtime_scope and dockerfile.parent.name not in selected:
            continue
        source = dockerfile.read_text()
        for image in re.findall(r"^FROM\s+(\S+)", source, re.M | re.I):
            if "@sha256:" not in image:
                gaps.append(f"{dockerfile.parent.name}: mutable base image {image}")
        if "pip install" in source:
            inventory.append({"manifest": dockerfile.relative_to(root).as_posix(), "ecosystem": "python",
                              "declared_install": [line.strip() for line in source.splitlines() if "pip install" in line],
                              "sha256": hashlib.sha256(dockerfile.read_bytes()).hexdigest()})
            if "--require-hashes" not in source:
                gaps.append(f"{dockerfile.parent.name}: pip dependencies are not hash-locked")
    for pom in sorted((root / "examples/sandbox").glob("aiwaf-*/pom.xml")):
        if runtime_scope and pom.parent.name not in selected:
            continue
        inventory.append({"manifest": pom.relative_to(root).as_posix(), "ecosystem": "maven",
                          "sha256": hashlib.sha256(pom.read_bytes()).hexdigest()})
    return result("A03", "dependency_reproducibility", "15 non-PHP local runtime build declarations" if runtime_scope else "sandbox repository", bool(inventory) and not gaps,
                  {"inventory": inventory, "findings": gaps,
                   "limits": "Declared manifest inventory, not a resolved SBOM, provenance verification or vulnerability scan."})


def npm_audit(root, service="aiwaf-assessment", workdir=None):
    command = ["docker", "compose", "exec", "-T"]
    if workdir:
        command += ["--workdir", workdir]
    command += [service, "npm", "audit", "--omit=dev", "--json"]
    scope = f"running {service} image only" + (f" ({workdir})" if workdir else "")
    try:
        response = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
        data = json.loads(response.stdout)
        counts = data.get("metadata", {}).get("vulnerabilities")
        if (response.returncode not in (0, 1) or not isinstance(counts, dict)
                or type(counts.get("total")) is not int or "error" in data):
            raise ValueError("npm audit did not return a usable advisory report")
        return result("A03", "npm_advisories", scope, counts.get("total", 0) == 0,
                      {"counts": counts, "packages": sorted(data.get("vulnerabilities", {})),
                       "findings": [{"package": name, "severity": entry.get("severity"),
                                     "direct": entry.get("isDirect"), "range": entry.get("range"),
                                     "via": entry.get("via"), "fix_available": entry.get("fixAvailable")}
                                    for name, entry in sorted(data.get("vulnerabilities", {}).items())],
                       "limits": "Live npm registry audit; other runtimes and OS packages are not scanned."})
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"category": "A03", "check": "npm_advisories", "scope": scope,
                "status": "error", "evidence": str(error)}


class Client:
    def __init__(self, base, token="sandbox-assessment-only", ca_file=None):
        self.base, self.token = base.rstrip("/"), token
        self.ip = f"93.{secrets.randbelow(254)+1}.{secrets.randbelow(254)+1}.20"
        # Do not inherit machine HTTP proxies or follow redirects to unrelated destinations.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                return None
        context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))

    def post(self, path, data, request_id=None, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), headers={
            "Content-Type": "application/json", "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "User-Agent": BROWSER, "Accept-Language": "en-US,en;q=0.9",
            "X-Forwarded-For": self.ip, "X-Assessment-Token": self.token,
            "X-Request-ID": request_id or secrets.token_hex(12), **(headers or {})})
        try:
            response = self.opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("oversized assessment response")
            return response.status, json.loads(raw)


def fixture_checks(base, token, ca_file=None):
    client, checks, created = Client(base, token, ca_file), [], []
    scope = base + " (reference application controls; not AIWAF implementations)"
    def fresh():
        password = secrets.token_urlsafe(24)
        status, data = client.post("/runs", {"password": password})
        if status != 201 or not isinstance(data.get("run"), str):
            raise ValueError("fixture setup failed; application controls were not reached")
        created.append(data["run"])
        return data, password
    def snap(run):
        status, data = client.post("/snapshot", {"run": run})
        if status != 200 or "password_storage" not in data:
            raise ValueError("fixture snapshot missing")
        return data
    try:
        setup, password = fresh()
        run = setup["run"]
        second, _ = fresh()
        storage, other = snap(run)["password_storage"], snap(second["run"])["password_storage"]
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(storage["salt"]), storage["iterations"]).hex()
        checks.append(result("A04", "password_storage", scope,
                             storage["algorithm"] == "pbkdf2-sha256" and storage["iterations"] >= 600000
                             and digest == storage["digest"] and storage["salt"] != other["salt"]
                             and not storage["plaintext_present"],
                             {"salt_unique": storage["salt"] != other["salt"], "plaintext_present": storage["plaintext_present"],
                              "algorithm": storage["algorithm"], "iterations": storage["iterations"]}))
        good_status, good = client.post("/login", {"run": run, "password": password})
        request_id, bad_password = secrets.token_hex(12), secrets.token_urlsafe(24)
        bad_status, bad = client.post("/login", {"run": run, "password": bad_password}, request_id)
        events = snap(run)
        logged = [e for e in events["events"] if e.get("request_id") == request_id and e.get("kind") == "login_failed"]
        alerted = [e for e in events["alerts"] if e.get("request_id") == request_id and e.get("kind") == "login_failed"]
        secret_free = all(secret not in json.dumps(events) for secret in (password, bad_password, token))
        checks.append(result("A09", "failure_event_redaction_and_alert", scope,
                             good_status == 200 and good.get("authenticated") is True
                             and bad_status == 401 and bad.get("authenticated") is False
                             and len(logged) == 1 and len(alerted) == 1 and secret_free,
                             {"login_statuses": [good_status, bad_status], "correlated_events": len(logged),
                              "correlated_alerts": len(alerted), "secrets_redacted": secret_free,
                              "limits": "In-process fixture alert sink; no external SIEM delivery verified."}))
        _, valid_events = client.post("/verify-events", {"run": run, "events": events["events"]})
        changed = json.loads(json.dumps(events["events"]))
        changed[0]["kind"] = "forged"
        _, invalid_events = client.post("/verify-events", {"run": run, "events": changed})
        _, truncated = client.post("/verify-events", {"run": run, "events": events["events"][:-1]})
        checks.append(result("A09", "event_tampering_and_truncation", scope,
                             valid_events.get("valid") is True and invalid_events.get("valid") is False
                             and truncated.get("valid") is False,
                             {"original_valid": valid_events.get("valid"), "modified_valid": invalid_events.get("valid"),
                              "truncated_valid": truncated.get("valid")}))
        payload = {"run": run, "value": setup["value"], "signature": setup["signature"]}
        accepted_status, accepted = client.post("/verify", payload)
        payload["value"] = {**setup["value"], "subject": "administrator"}
        rejected_status, rejected = client.post("/verify", payload)
        payload["value"], payload["signature"] = setup["value"], "0" * 64
        signature_status, signature_rejected = client.post("/verify", payload)
        checks.append(result("A08", "signed_data_tampering", scope,
                             accepted_status == 200 and accepted.get("accepted") is True
                             and rejected_status == 403 and rejected.get("accepted") is False
                             and signature_status == 403 and signature_rejected.get("accepted") is False,
                             {"original": accepted_status, "modified_data": rejected_status, "forged_signature": signature_status}))
        order_run, _ = fresh()
        run = order_run["run"]
        invalid_status, invalid = client.post("/order", {"run": run, "quantity": -1, "idempotency_key": "negative"})
        before = snap(run)
        checks.append(result("A06", "negative_quantity_has_no_side_effect", scope,
                             invalid_status == 422 and invalid.get("error") == "quantity_positive"
                             and before["stock"] == 5 and before["orders"] == 0,
                             {"status": invalid_status, "remaining": before["stock"], "orders": before["orders"]}))
        # Each business rule starts with independent state: a failed negative-
        # quantity check must not alter the replay or concurrency verdicts.
        order_run, _ = fresh()
        run = order_run["run"]
        order = {"run": run, "quantity": 1, "idempotency_key": "replay"}
        first_status, first = client.post("/order", order)
        replay_status, replay = client.post("/order", order)
        replay_snapshot = snap(run)
        checks.append(result("A06", "idempotent_order_replay", scope,
                             first_status == 201 and replay_status == 200 and first == replay
                             and replay_snapshot["orders"] == 1 and replay_snapshot["stock"] == 4,
                             {"statuses": [first_status, replay_status], "orders": replay_snapshot["orders"],
                              "remaining": replay_snapshot["stock"]}))
        order_run, _ = fresh()
        run = order_run["run"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            attempts = list(pool.map(lambda i: client.post("/order", {"run": run, "quantity": 1,
                                      "idempotency_key": f"parallel-{i}"}), range(8)))
        final = snap(run)
        checks.append(result("A06", "concurrent_stock_budget", scope,
                             sum(s == 201 for s, _ in attempts) == 5 and sum(s == 409 for s, _ in attempts) == 3
                             and final["stock"] == 0 and final["orders"] == 5,
                             {"created": sum(s == 201 for s, _ in attempts), "rejected": sum(s == 409 for s, _ in attempts),
                              "remaining": final["stock"], "orders": final["orders"]}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        checks.append({"category": "fixture", "check": "application_controls_reachable", "scope": scope,
                       "status": "error", "evidence": str(error)})
    finally:
        for run in created:
            try:
                status, data = client.post("/cleanup", {"run": run})
                if status != 200 or data.get("deleted") is not True:
                    raise ValueError("fixture cleanup rejected")
            except (OSError, ValueError) as error:
                checks.append({"category": "fixture", "check": "cleanup", "scope": scope,
                               "status": "error", "evidence": str(error)})
    return checks


def transport_check(url, allow_local_http=False):
    parts = urllib.parse.urlsplit(url)
    scope = url
    if parts.scheme != "https":
        exempt = allow_local_http and parts.hostname in ("localhost", "127.0.0.1", "::1")
        return {"category": "A04", "check": "transport_security", "scope": scope,
                "status": "not_assessed" if exempt else "fail",
                "evidence": "Local HTTP explicitly excluded from TLS assessment" if exempt else "HTTP provides no TLS transport confidentiality"}
    import socket
    try:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((parts.hostname, parts.port or 443), timeout=10) as connection:
            with context.wrap_socket(connection, server_hostname=parts.hostname) as tls:
                return result("A04", "transport_security", scope, tls.version() in ("TLSv1.2", "TLSv1.3"),
                              {"negotiated": tls.version(), "certificate_and_hostname_validated": True,
                               "limits": "Does not prove old protocol versions are disabled or audit keys/at-rest encryption."})
    except (OSError, ValueError) as error:
        return {"category": "A04", "check": "transport_security", "scope": scope, "status": "error", "evidence": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="append", help="Repeat for direct/protected fixture URLs; omitted means fixture checks are not assessed")
    parser.add_argument("--extended", action="store_true", help="Authorization, authentication, deployment and exception outcomes")
    parser.add_argument("--ca-file", type=Path, help="Explicit sandbox CA trust; never changes host trust")
    parser.add_argument("--tls-url", action="append", default=[], help="Test TLS 1.2/1.3, reject older protocols and invalid certificates")
    parser.add_argument("--transport-url", action="append", default=[])
    parser.add_argument("--allow-local-http", action="store_true", help="Explicitly mark loopback HTTP as not assessed, never passed")
    parser.add_argument("--local-runtime-scope", action="store_true", help="Inventory only the 15 locally built non-PHP runtime Dockerfiles; excludes PHP and helper/test images")
    parser.add_argument("--npm-audit", action="store_true", help="Query npm advisories for the selected running Express service; requires Docker/network")
    parser.add_argument("--audit-service", choices=("aiwaf", "aiwaf-assessment"), default="aiwaf-assessment")
    parser.add_argument("--output", type=Path, default=ROOT / "examples/sandbox/results_owasp_assessment.json")
    args = parser.parse_args()
    checks = [supply_chain(ROOT, args.local_runtime_scope)]
    checks.append(npm_audit(ROOT, args.audit_service) if args.npm_audit else {"category": "A03", "check": "npm_advisories", "scope": "Express image",
                                                       "status": "not_assessed", "evidence": "Use --npm-audit for a live advisory query"})
    token = os.environ.get("AIWAF_ASSESSMENT_TOKEN", "sandbox-assessment-only")
    for url in args.fixture or []:
        checks.extend(fixture_checks(url, token, args.ca_file))
        if args.extended:
            from application_checks import application_checks
            from deployment_checks import deployment_checks
            checks.extend(application_checks(url, token, args.ca_file))
            try:
                checks.extend(deployment_checks(url, token, args.ca_file))
            except (OSError, ValueError) as error:
                checks.append({'category': 'deployment', 'check': 'deployment_reachable', 'scope': url,
                               'status': 'error', 'evidence': str(error)})
    if not args.fixture:
        for category in ("A04", "A06", "A08", "A09"):
            checks.append({"category": category, "check": "reference_application_controls", "scope": "fixture",
                           "status": "not_assessed", "evidence": "No --fixture URL supplied"})
    for url in args.transport_url or ([] if args.tls_url else args.fixture) or []:
        checks.append(transport_check(url, args.allow_local_http))
    if args.tls_url:
        from deployment_checks import tls_checks
        for url in args.tls_url:
            try:
                checks.extend(tls_checks(url, args.ca_file))
            except (OSError, ValueError) as error:
                checks.append({'category': 'A04', 'check': 'tls_reachable', 'scope': url,
                               'status': 'error', 'evidence': str(error)})
    report = {"owasp_edition": 2025, "generated_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "limits": "Reference fixture outcomes and repository checks; not OWASP certification or proof that AIWAF supplies these application controls."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for check in checks:
        print(f"{check['category']} {check['status']}: {check['check']} [{check['scope']}]")
    print(f"Report: {args.output}")
    raise SystemExit(1 if any(c["status"] in ("fail", "error") for c in checks) else 0)


if __name__ == "__main__":
    main()
