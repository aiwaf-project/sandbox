"""Run every configured payload scenario with browser headers and a direct baseline.

Payload rows describe observed denials, not proof that a particular AIWAF control
prevented an exploit. Use smoke-test.py for explicit header/rate-limit assertions.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import secrets
import sys


HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    suite = load("attack_suite_matrix", "attack-suite.py")
    smoke = load("smoke_suite_matrix", "smoke-test.py")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="Reuse saved baselines and completed targets")
    parser.add_argument("--target", action="append", metavar="NAME=URL")
    parser.add_argument("--exclude", action="append", choices=list(smoke.ALL_TARGETS), default=[])
    parser.add_argument("--timeout", type=float, default=5, help="Per-request timeout in seconds")
    parser.add_argument("--output", type=Path, default=HERE / "results_aiwaf_payload_matrix.json")
    args = parser.parse_args()
    send = suite.requests.request
    suite.requests.request = lambda **kwargs: send(**{**kwargs, "timeout": args.timeout})
    original_request = suite.request_once
    observed = []
    def request(*args, **kwargs):
        response = original_request(*args, **kwargs)
        observed.append(response.status)
        return response
    suite.request_once = request
    browser = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
               "accept": "application/json,text/html;q=0.9,*/*;q=0.8", "accept-language": "en-US,en;q=0.9"}
    targets = dict(item.split("=", 1) for item in args.target) if args.target else smoke.ALL_TARGETS
    targets = {name: url for name, url in targets.items() if name not in args.exclude}
    report = {"started_at": suite._utc_iso(), "scope": f"{len(targets)} selected root-stack proxies; browser-header payload runs",
              "limits": "Denial counts are observations, not exploit assertions or correlated WAF decision evidence.",
              "baselines": {}, "targets": {}}
    run_id = secrets.token_hex(12)
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.resume and output.exists():
        report = json.loads(output.read_text())
        report.pop("finished_at", None)
    def save():
        output.write_text(json.dumps(report, indent=2) + "\n")
    def run(label, url, php=False):
        prefix = f"93.{secrets.randbelow(254)+1}.{secrets.randbelow(254)+1}"
        headers = suite.make_header_generator(browser, suite.make_ip_generator(prefix, run_id + label, 0))
        tests = [("normal_traffic", suite.attack_normal_traffic)] + suite.build_attack_tests_for_target("protected_laravel" if php else label)
        cases = []
        if original_request("GET", url + "/", headers=browser).status == 0:
            return [{"attack_type": name, "observation": "error", "error": "target unreachable; scenario not run"}
                    for name, _ in tests]
        for name, function in tests:
            observed.clear()
            try:
                partial = suite.run_test_suite(url, label, None, [(name, function)], headers)
                row = partial["attacks"][0]
                statuses = observed[1:]  # Exclude the runner's reachability request.
                row["response_statuses"] = statuses
                row["observation"] = ("request_errors" if row["errors"] else
                                      "all_denied" if row["blocked"] == row["requests_sent"] else
                                      "some_denied" if row["blocked"] else "none_denied")
                cases.append(row)
            except Exception as error:
                cases.append({"attack_type": name, "observation": "error", "error": str(error)})
        return cases
    for label, php in (("generic", False), ("php", True)):
        if label in report["baselines"]:
            continue
        print(f"Running direct {label} baseline...", flush=True)
        report["baselines"][label] = run("direct_" + label, "http://127.0.0.1:3001", php)
        save()
    for name, url in targets.items():
        if name in args.exclude:
            continue
        if args.resume and not args.target and name in report["targets"]:
            previous = report['targets'][name]
            if previous and all(not row.get('errors') and row.get('observation') not in ('error', 'request_errors') for row in previous):
                continue
        php = name in ("laravel", "symfony", "wordpress")
        print(f"Running all scenarios: {name}", flush=True)
        cases = run("protected_" + name, url, php)
        baselines = {c["attack_type"]: c for c in report["baselines"]["php" if php else "generic"]}
        for row in cases:
            direct = baselines.get(row["attack_type"], {})
            row["direct_status_counts"] = direct.get("status_counts", {})
            row["direct_blocked"] = direct.get("blocked")
            if row["attack_type"] == "normal_traffic" and "response_statuses" in row:
                row["matches_direct_statuses"] = row["response_statuses"] == direct.get("response_statuses")
        report["targets"][name] = cases
        save()
        print(f"Finished {name}: {len(cases)} scenarios", flush=True)
    if set(targets).issubset(report["targets"]):
        report["finished_at"] = suite._utc_iso()
    save()
    print(f"Report: {output}", flush=True)
    raise SystemExit(1 if any(row.get("errors") or row["observation"] in ("error", "request_errors")
                             for cases in report["targets"].values() for row in cases) else 0)


if __name__ == "__main__":
    main()
