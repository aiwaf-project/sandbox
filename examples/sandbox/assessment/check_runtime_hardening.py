"""Verify effective permissions of the 15 running, published-package runtimes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SERVICES = ['aiwaf', *['aiwaf_' + name for name in ('fastify', 'hapi', 'koa', 'nest', 'next', 'adonis', 'sails')],
            *['aiwaf-' + name for name in ('django', 'flask', 'fastapi', 'java', 'spring', 'java-r', 'spring-r')]]


def check(service):
    cid = subprocess.check_output(['docker', 'compose', 'ps', '-q', service], cwd=ROOT, text=True).strip()
    item = json.loads(subprocess.check_output(['docker', 'inspect', cid], text=True))[0]
    config, host = item['Config'], item['HostConfig']
    status = subprocess.check_output(['docker', 'compose', 'exec', '-T', service, 'cat', '/proc/1/status'], cwd=ROOT, text=True)
    fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    # A real creation attempt verifies read-only code, while temp and logs remain usable.
    probe = 'set -eu; probe=.aiwaf-hardening-probe; if ( : > "$probe" ) 2>/dev/null; then rm -f "$probe"; exit 1; fi; touch /tmp/.aiwaf-hardening-probe /logs/.aiwaf-hardening-probe; rm /tmp/.aiwaf-hardening-probe /logs/.aiwaf-hardening-probe'
    write = subprocess.run(['docker', 'compose', 'exec', '-T', service, 'sh', '-c', probe], cwd=ROOT, capture_output=True, text=True)
    checks = {
        'non_root_pid1': all(int(uid) == 10001 for uid in fields.get('Uid', '').split()) and bool(fields.get('Uid', '').strip()),
        'no_effective_capabilities': int(fields.get('CapEff', '-1').strip(), 16) == 0,
        'no_new_privileges': fields.get('NoNewPrivs', '').strip() == '1',
        'read_only_root': host['ReadonlyRootfs'] is True,
        'not_privileged': host['Privileged'] is False,
        'capabilities_dropped': host.get('CapDrop') == ['ALL'],
        'code_read_only_logs_and_tmp_writable': write.returncode == 0,
        'loopback_ports': all(row['HostIp'] in ('127.0.0.1', '::1') for rows in (host.get('PortBindings') or {}).values() for row in rows),
    }
    if service == 'aiwaf' or service.startswith('aiwaf_'):
        result = subprocess.run(['docker', 'compose', 'exec', '-T', service, 'sh', '-c',
            '! command -v npm && ! command -v npx && test ! -d /usr/local/lib/node_modules/npm && ! command -v yarn'], cwd=ROOT, capture_output=True)
        checks['no_npm_npx_yarn'] = result.returncode == 0
        checks['direct_node_start'] = config['Cmd'][0] == 'node'
    if service in ('aiwaf-java', 'aiwaf-spring'):
        checks['unused_pebble_removed'] = subprocess.run(['docker', 'compose', 'exec', '-T', service, 'test', '!', '-e', '/usr/bin/pebble'], cwd=ROOT).returncode == 0
    return {'service': service, 'image_id': item['Image'], 'checks': checks, 'passed': all(checks.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples/sandbox/results_published_hardening.json')
    args = parser.parse_args()
    rows = []
    for service in SERVICES:
        try:
            row = check(service)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            row = {'service': service, 'passed': False, 'error': str(error)}
        rows.append(row)
        print(service, 'PASS' if row['passed'] else 'FAIL', flush=True)
    args.output.write_text(json.dumps({'generated_at': datetime.now(timezone.utc).isoformat(), 'runtimes': rows,
        'limits': 'Serving runtime checks only. One-shot log ownership initializer runs as root with narrowly scoped capabilities; Redis, Juice Shop, PHP and assessment fixtures are separate scopes.'}, indent=2) + '\n')
    raise SystemExit(int(any(not row['passed'] for row in rows)))


if __name__ == '__main__':
    main()
