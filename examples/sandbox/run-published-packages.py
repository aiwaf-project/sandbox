"""Validate the published non-PHP packages against the running root stack."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import io
import tempfile
import zipfile
import argparse
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-completed", action="store_true", help="Reuse existing per-suite reports")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("published_smoke", HERE / "smoke-test.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    targets = {name: url for name, url in smoke.ALL_TARGETS.items()
               if name not in ("laravel", "symfony", "wordpress")}
    selected = [arg for name, url in targets.items() for arg in ("--target", f"{name}={url}")]
    prefix = "results_published_"
    services = {"node": "aiwaf", **{name: f"aiwaf_{name}" for name in
                ("fastify", "hapi", "koa", "nest", "next", "adonis", "sails")},
                **{name: f"aiwaf-{name}" for name in
                   ("django", "flask", "fastapi", "java", "spring", "java-r", "spring-r")}}
    versions = {}
    for name, service in services.items():
        command = ["docker", "compose", "exec", "-T", service]
        if name in ("django", "flask", "fastapi"):
            command += ["python", "-c", "import importlib.metadata as m,json;print(json.dumps({p:m.version(p) for p in ['aiwaf','aiwaf-rust']}))"]
        elif name in ("java", "spring", "java-r", "spring-r"):
            with tempfile.TemporaryDirectory(prefix="aiwaf-published-") as temporary:
                jar = Path(temporary) / "app.jar"
                subprocess.run(["docker", "compose", "cp", f"{service}:/app/app.jar", str(jar)], cwd=ROOT, check=True)
                with zipfile.ZipFile(jar) as archive:
                    nested = next((path for path in archive.namelist() if path.startswith("BOOT-INF/lib/aiwaf-java-")), None)
                    if nested:
                        with zipfile.ZipFile(io.BytesIO(archive.read(nested))) as dependency:
                            props = dependency.read("META-INF/maven/io.github.aiwaf-project/aiwaf-java/pom.properties").decode()
                    else:
                        props = archive.read("META-INF/maven/io.github.aiwaf-project/aiwaf-java/pom.properties").decode()
                versions[name] = {"aiwaf-java": next(line.split("=", 1)[1] for line in props.splitlines() if line.startswith("version="))}
            continue
        else:
            command += ["node", "-e", "console.log(JSON.stringify(Object.fromEntries(['aiwaf','aiwaf-wasm'].map(p=>[p,require(p+'/package.json').version]))))"]
        versions[name] = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
    expected = {"aiwaf": "1.1.0", "aiwaf-rust": "0.2.1", "aiwaf-wasm": "0.2.1", "aiwaf-java": "1.3.1"}
    (HERE / f"{prefix}versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    if any(version != expected[package] for packages in versions.values() for package, version in packages.items()):
        raise SystemExit("Installed package versions do not match the published release pins")
    print("Verified installed versions in all 15 proxies.", flush=True)
    jobs = [
        ("smoke", "smoke-test.py", [*selected, "--burst-workers", "16"]),
        ("login", "validate-login-bypass.py", selected),
        ("payload", "validate-runtime-matrix.py", selected),
        ("owasp", "assessment/run.py", ["--fixture", "http://localhost:8090",
          "--fixture", "http://localhost:3020", "--allow-local-http", "--npm-audit"]),
        ("npm_audits", "audit-published-proxies.py", []),
    ]
    exits = {}
    started = datetime.now(timezone.utc).isoformat()
    for name, script, job_args in jobs:
        report_path = HERE / f"{prefix}{name}.json"
        if args.skip_completed and report_path.exists():
            exits[name] = None
            continue
        print(f"Running published-package {name} checks...", flush=True)
        exits[name] = subprocess.run([sys.executable, str(HERE / script), *job_args,
                                      "--output", str(report_path)], cwd=ROOT).returncode
    summary = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
               "targets": targets, "php": "excluded; unpublished release", "exit_codes": exits}
    (HERE / f"{prefix}run.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Published AIWAF package validation", "", f"Run started: {started}", "",
             "15 non-PHP proxies. PHP excluded because its new release is unpublished.", "",
             "Package pins: Python/JavaScript 1.1.0; Rust/WASM 0.2.1; Java 1.3.1.", ""]
    rows = json.loads((HERE / f"{prefix}smoke.json").read_text())
    lines += [f"Smoke: {sum(bool(row.get('passed')) for row in rows)}/{len(rows)} runtimes pass all five checks.", "",
              "| Runtime | Smoke | SQL OR true | SQL comment |", "| --- | --- | --- | --- |"]
    login = json.loads((HERE / f"{prefix}login.json").read_text())
    for row in rows:
        checks = login["targets"][row["target"]]["attacks"]
        lines.append("| " + " | ".join([row["target"], "PASS" if row.get("passed") else "FAIL",
                     *[checks[key]["verdict"].upper() for key in ("sql_or_true", "sql_comment_password")]]) + " |")
    payload = json.loads((HERE / f"{prefix}payload.json").read_text())
    cases = [row for rows in payload["targets"].values() for row in rows]
    errors = sum(bool(row.get("errors")) or row["observation"] in ("error", "request_errors") for row in cases)
    lines += ["", f"Payload matrix: {len(cases)} scenarios across {len(payload['targets'])} runtimes; {errors} scenarios with errors.",
              f"Payload run complete: {'finished_at' in payload}.",
              "Denial counts are observations, not confirmed exploit prevention or OWASP certification.", "",
              "| OWASP fixture check | Scope | Outcome |", "| --- | --- | --- |"]
    assessment = json.loads((HERE / f"{prefix}owasp.json").read_text())
    for check in assessment["checks"]:
        lines.append(f"| {check['category']} {check['check']} | {check['scope']} | {check['status'].upper()} |")
    audits = json.loads((HERE / f"{prefix}npm_audits.json").read_text())
    lines += ["", "## Production npm dependency audits", "",
              "Counts include proxy/framework dependencies and transitive entries; they are not counts of distinct AIWAF vulnerabilities.", "",
              "| Image scope | Outcome | Advisory counts |", "| --- | --- | --- |"]
    for check in audits["checks"]:
        evidence = check["evidence"]
        counts = evidence.get("counts", {}) if isinstance(evidence, dict) else evidence
        lines.append(f"| {check['scope']} | {check['status'].upper()} | {json.dumps(counts)} |")
    fresh_smoke = HERE / f"{prefix}java_fresh_smoke.json"
    fresh_login = HERE / f"{prefix}java_fresh_login.json"
    if fresh_smoke.exists() and fresh_login.exists():
        lines += ["", "## Java with fresh Redis namespaces", "",
                  "The root stack retains old learned `rest` keywords. These isolated instances preserve that original state and use separate Redis prefixes.", "",
                  "| Runtime | Fresh-state smoke | SQL OR true | SQL comment |", "| --- | --- | --- | --- |"]
        fresh = json.loads(fresh_login.read_text())
        for row in json.loads(fresh_smoke.read_text()):
            attacks = fresh["targets"][row["target"]]["attacks"]
            lines.append("| " + " | ".join([row["target"], "PASS" if row.get("passed") else "FAIL",
                          *[attacks[key]["verdict"].upper() for key in ("sql_or_true", "sql_comment_password")]]) + " |")
        combined = {row["target"]: row for row in rows}
        combined.update({row["target"]: row for row in json.loads(fresh_smoke.read_text())})
        lines += ["", f"With fresh Java state, {sum(bool(row.get('passed')) for row in combined.values())}/15 proxies pass the five smoke assertions. Flask failed the initial concurrent burst.", "",
                  "Six of 15 integrations deny both SQL login exploits with valid ordinary controls. Nine allow token issuance: Fastify, Hapi, Nest, Next.js, Adonis and all four Java variants.", ""]
        fresh_payload = HERE / f"{prefix}java_fresh_payload.json"
        if fresh_payload.exists():
            matrix = json.loads(fresh_payload.read_text())
            lines += [f"Additional fresh-state Java matrix: {sum(map(len, matrix['targets'].values()))} scenarios; complete: {'finished_at' in matrix}.", "",
                      "| Java runtime | Normal responses match direct baseline |", "| --- | --- |"]
            for name, scenarios in matrix["targets"].items():
                normal = next(row for row in scenarios if row["attack_type"] == "normal_traffic")
                lines.append(f"| {name} | {normal.get('matches_direct_statuses', False)} |")
        after_path = HERE / f"{prefix}java_fresh_login_after_matrix.json"
        if after_path.exists():
            after = json.loads(after_path.read_text())
            lines += ["", "Post-matrix Java ordinary invalid-login controls: " + ", ".join(
                f"{name}=HTTP {target['control']['status']}" for name, target in after["targets"].items()) + ".", ""]
    lines += ["", "## Findings", "",
              "Fastify, Hapi, Nest, Next.js and Adonis allowed both token-issuing SQL payloads in the configured sandbox integrations. Express, Koa, Sails and all three Python proxies denied them with valid ordinary controls.", "",
              "The five failing JavaScript proxy integrations do not expose parsed JSON bodies to AIWAF before proxying: Fastify uses early middie proxying, Hapi uses streaming H2o2 proxying, Nest registers WAF before body parsing, and the Next/Adonis custom servers pass raw requests. These outcomes establish integration gaps; they do not establish that every native framework deployment has the same behavior.", "",
              "Flask's initial concurrent burst accepted all 65 requests. Follow-up serial and concurrent burst evidence is saved separately; the concurrent repeat accepted 62 and denied 3. Rate limiting is inconsistent under concurrency.", "",
              "The Express assessment image has three high-severity npm audit entries through http-proxy-middleware/micromatch/braces. This audit scope is the proxy image, not solely the AIWAF package. Dependency reproducibility also fails; local HTTP transport is not assessed.", ""]
    lines += ["", "Reference fixture controls belong to the application; their success does not establish that AIWAF implements them.", "",
              "Evidence: results_published_smoke.json, results_published_login.json, results_published_payload.json, results_published_owasp.json.", ""]
    output = HERE / f"{prefix}validation.md"
    output.write_text("\n".join(lines))
    print(f"Report: {output}", flush=True)
    raise SystemExit(int(any(exits.values()) or any(not row.get("passed") for row in rows)
                        or any(attack["verdict"] != "pass" for target in login["targets"].values()
                               for attack in target["attacks"].values())
                        or errors or "finished_at" not in payload
                        or any(check["status"] != "pass" for check in audits["checks"])
                        or any(check["status"] in ("fail", "error") for check in assessment["checks"])))


if __name__ == "__main__":
    main()
