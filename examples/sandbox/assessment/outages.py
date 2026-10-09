"""Run isolated live outage assertions without stopping shared services."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'examples/sandbox'


def main():
    subprocess.run(['docker', 'compose', 'cp', str(Path(__file__).with_suffix('.js')),
                    'aiwaf:/tmp/owasp-outages.js'], cwd=ROOT, check=True)
    process = subprocess.run(['docker', 'compose', 'exec', '-T', 'aiwaf', 'node', '/tmp/owasp-outages.js'],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
    reports = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{"checks":')]
    if not reports:
        raise RuntimeError('Outage test did not produce a report')
    report = {**reports[-1], 'generated_at': datetime.now(timezone.utc).isoformat(),
              'limits': 'Isolated Express SDK and shared JavaScript proxy helper; no shared Redis outage or production failover simulated.'}
    (HERE / 'results_local_outages.json').write_text(json.dumps(report, indent=2) + '\n')
    for check in report['checks']:
        print(check['check'] + ': ' + check['status'])
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
