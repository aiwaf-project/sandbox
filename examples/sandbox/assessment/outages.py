"""Run isolated live outage assertions without stopping shared services."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'examples/sandbox'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'results_local_outages.json')
    args = parser.parse_args()
    script = '/workspace/examples/sandbox/assessment/outages.js'
    installed = subprocess.check_output(['docker', 'compose', 'exec', '-T', 'aiwaf', 'cat', script], cwd=ROOT)
    if hashlib.sha256(installed).digest() != hashlib.sha256(Path(__file__).with_suffix('.js').read_bytes()).digest():
        raise RuntimeError('Outage assertions changed; rebuild the Express image before testing')
    process = subprocess.run(['docker', 'compose', 'exec', '-T', 'aiwaf', 'node', script],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
    reports = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{"checks":')]
    if not reports:
        raise RuntimeError('Outage test did not produce a report')
    report = {**reports[-1], 'generated_at': datetime.now(timezone.utc).isoformat(),
              'limits': 'Isolated Express SDK and shared JavaScript proxy helper; no shared Redis outage or production failover simulated.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for check in report['checks']:
        print(check['check'] + ': ' + check['status'])
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
