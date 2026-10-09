"""Audit production npm dependencies in each running JavaScript proxy image."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results_published_npm_audits.json")
    parser.add_argument("--include-sdk", action="store_true", help="Also audit the local SDK symlink target")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("published_assessment", HERE / "assessment/run.py")
    assessment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assessment)
    services = ["aiwaf", *[f"aiwaf_{name}" for name in
                ("fastify", "hapi", "koa", "nest", "next", "adonis", "sails")]]
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(lambda service: assessment.npm_audit(assessment.ROOT, service), services))
    if args.include_sdk:
        checks.append(assessment.npm_audit(assessment.ROOT, 'aiwaf', '/opt/aiwaf-js'))
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "limits": "Running proxy production npm dependencies only; not solely AIWAF, and not an OS/Python/Java vulnerability scan."}, indent=2) + "\n")
    for check in checks:
        print(check["scope"], check["status"], json.dumps(check["evidence"].get("counts", {}))
              if isinstance(check["evidence"], dict) else check["evidence"], flush=True)
    print(output)
    raise SystemExit(int(any(check["status"] != "pass" for check in checks)))


if __name__ == "__main__":
    main()
