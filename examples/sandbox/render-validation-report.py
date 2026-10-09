"""Render saved live outcomes without relabeling payload denial counts as passes."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    lines = ["# AIWAF live validation", "",
             "AIWAF does not pass every tested control. This report covers the configured local sandbox, not OWASP certification.", "",
             "Smoke assertions test expected HTTP behavior. Payload rows show observed denials, not confirmed exploit prevention or WAF attribution.", "",
             "Reference application checks validate its own controls. Failures on the deliberately vulnerable application behind AIWAF show controls the proxy did not compensate for.", ""]
    assessment = HERE / "results_owasp_aiwaf_validation.json"
    if assessment.exists():
        report = json.loads(assessment.read_text())
        lines += ["## OWASP companion outcomes", "", "| Category | Check | Target / scope | Result |", "| --- | --- | --- | --- |"]
        for check in report["checks"]:
            lines.append(f"| {check['category']} | {check['check']} | {check['scope']} | {check['status'].upper()} |")
        lines += ["", "### Companion evidence", ""]
        for check in report["checks"]:
            evidence = check.get("evidence", {})
            if check["category"] == "A03" and isinstance(evidence, dict):
                evidence = {key: (len(value) if key == "findings" else value)
                            for key, value in evidence.items()
                            if key in ("counts", "findings", "limits")}
            lines.append(f"- {check['check']} [{check['scope']}]: `{json.dumps(evidence, sort_keys=True)}`")
        lines += ["", "The vulnerable reference app used ports 8091 (direct) and 3021 (through AIWAF). Those temporary containers were removed after recording results.", ""]
    smoke = HERE / "results_aiwaf_smoke_matrix.json"
    if smoke.exists():
        smoke_rows = json.loads(smoke.read_text())
        lines += [f"Smoke: {sum(bool(row.get('passed')) for row in smoke_rows)}/{len(smoke_rows)} runtimes pass all five assertions.", ""]
        lines += ["## Proxy, header and rate-limit assertions", "", "| Runtime | Browser headers | Lowercase headers | Automation denied | Burst limited | JSON POST forwarded |", "| --- | --- | --- | --- | --- | --- |"]
        for row in smoke_rows:
            checks = row.get("checks", {})
            values = ["PASS" if checks.get(k) else "FAIL" if k in checks else "ERROR"
                      for k in ("normal_headers", "lowercase_headers", "automation_denied", "burst_limited", "json_post_forwarded")] if checks else ["ERROR"] * 5
            lines.append("| " + " | ".join([row["target"], *values]) + " |")
            if row.get("error"):
                lines += ["", f"{row['target']}: {row['error']}", ""]
        lines.append("")
    login = HERE / "results_aiwaf_login_bypass.json"
    if login.exists():
        report = json.loads(login.read_text())
        outcomes = [attack["verdict"] for row in report["targets"].values() for attack in row["attacks"].values()]
        lines += [f"SQL login bypass: {outcomes.count('fail')} confirmed failures, {outcomes.count('error')} errors, {outcomes.count('pass')} passes.", ""]
        lines += ["## Confirmed SQL login bypass checks", "",
                  "The direct baseline issues authentication tokens for both SQL payloads. PASS requires ordinary invalid credentials to reach the application (401) and the exploit to be denied without a token. ERROR means the ordinary control or transport failed, so exploit prevention is not established.", "",
                  "| Runtime | Control status | OR-true payload | Comment payload | Control rejection reason |",
                  "| --- | --- | --- | --- | --- |"]
        for name, row in report["targets"].items():
            outcomes = [f"{attack['verdict'].upper()} (HTTP {attack['status']}, token={attack['token_issued']})"
                        for attack in row["attacks"].values()]
            lines.append("| " + " | ".join([name, str(row["control"]["status"]), *outcomes,
                                             str(row["control"].get("blocked_reason", ""))]) + " |")
        lines += ["", "These two payloads do not exhaust injection or authentication risks. Java/Spring control failures were observed after the payload matrix; learned state was retained throughout the run.", ""]
    payload = HERE / "results_aiwaf_payload_matrix.json"
    if payload.exists():
        report = json.loads(payload.read_text())
        lines += [f"Payload matrix: {sum(map(len, report['targets'].values()))} scenario/runtime combinations across {len(report['targets'])} runtimes.", ""]
        lines += ["## Payload scenarios", "", "Browser headers are supplied except where a scenario deliberately overrides them. Direct baseline responses are included; 403/405/409/429 count as denials, even when produced by the target application. A denial does not automatically establish a WAF pass.", ""]
        for target, cases in report["targets"].items():
            lines += [f"### {target}", "", "| Scenario | Direct denials | Protected denials | Observation | Protected statuses |", "| --- | --- | --- | --- | --- |"]
            for row in cases:
                count = row.get("requests_sent", "?")
                direct = row.get("direct_blocked", "?")
                protected = row.get("blocked", "?")
                status = json.dumps(row.get("status_counts", {}), sort_keys=True)
                lines.append(f"| {row['attack_type']} | {direct}/{count} | {protected}/{count} | {row['observation']} | `{status}` |")
            normal = next((r for r in cases if r["attack_type"] == "normal_traffic"), {})
            lines += ["", f"Normal response statuses match direct baseline: {normal.get('matches_direct_statuses', 'not established')}.", ""]
        if "finished_at" not in report:
            lines += ["**Payload run is incomplete.** Only completed targets are shown.", ""]
    output = HERE / "results_aiwaf_validation.md"
    output.write_text("\n".join(lines) + "\n")
    print(output)


if __name__ == "__main__":
    main()
