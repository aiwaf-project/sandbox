"""Check whether known Juice Shop SQL login bypasses actually issue auth tokens."""
from datetime import datetime, timezone
import argparse
import http.client
import importlib.util
import json
from pathlib import Path
import secrets
import urllib.parse

HERE = Path(__file__).resolve().parent


def send(base, credentials):
    url = urllib.parse.urlsplit(base)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    try:
        connection.request("POST", "/rest/user/login", json.dumps(credentials).encode(), {
            "Content-Type": "application/json", "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Forwarded-For": f"93.{secrets.randbelow(254)+1}.{secrets.randbelow(254)+1}.22"})
        response = connection.getresponse()
        raw = response.read(1024 * 1024)
        try:
            body = json.loads(raw)
        except ValueError:
            body = {}
        auth = body.get("authentication", {}) if isinstance(body, dict) else {}
        # Tokens and credentials are deliberately excluded from the report.
        result = {"status": response.status, "token_issued": isinstance(auth, dict) and bool(auth.get("token"))}
        if isinstance(body, dict) and body.get("blocked") is True:
            result["blocked_reason"] = body.get("reason")
        return result
    except (OSError, http.client.HTTPException) as error:
        return {"status": 0, "token_issued": False, "error": str(error)}
    finally:
        connection.close()


def verdict(control, attack, baseline):
    if baseline.get("token_issued") is not True:
        return "not_assessed"
    if control["status"] != 401 or control["token_issued"] or attack["status"] == 0 or attack["status"] >= 500:
        return "error"
    if attack["token_issued"]:
        return "fail"
    if attack["status"] in (403, 429):
        return "pass"
    return "inconclusive"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', action='append', metavar='NAME=URL')
    parser.add_argument('--output', type=Path, default=HERE / 'results_aiwaf_login_bypass.json')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("smoke_login", HERE / "smoke-test.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    control = {"email": "sandbox-control-" + secrets.token_hex(12) + "@example.invalid", "password": secrets.token_urlsafe(24)}
    payloads = {"sql_or_true": {"email": "admin@juice-sh.op' OR 1=1--", "password": "x"},
                "sql_comment_password": {"email": "admin@juice-sh.op'--", "password": "x"}}
    baseline = {"control": send("http://localhost:3001", control),
                "attacks": {name: send("http://localhost:3001", payload) for name, payload in payloads.items()}}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "category": ["A05", "A07"],
              "baseline": baseline, "targets": {},
              "limits": "Pass requires valid control forwarding plus denial of a token-issuing baseline exploit. This tests two SQL login bypasses, not all injection/authentication risks."}
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    targets = dict(item.split('=', 1) for item in args.target) if args.target else smoke.ALL_TARGETS
    for name, base in targets.items():
        normal = send(base, control)
        attacks = {}
        for label, payload in payloads.items():
            response = send(base, payload)
            response["verdict"] = verdict(normal, response, baseline["attacks"][label])
            attacks[label] = response
        report["targets"][name] = {"control": normal, "attacks": attacks}
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"target": name, "control": normal, "attacks": attacks}), flush=True)
    raise SystemExit(1 if any(a["verdict"] != "pass" for target in report["targets"].values() for a in target["attacks"].values()) else 0)


if __name__ == "__main__":
    main()
