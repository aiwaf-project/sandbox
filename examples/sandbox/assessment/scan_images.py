"""Scan all 15 built non-PHP images with pinned Grype, including OS packages.

Requires Docker's Linux engine. Raw reports include package locations so source
lockfile findings can be distinguished from installed runtime dependencies.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'examples/sandbox'
SCANNER = 'anchore/grype:v0.120.0@sha256:5c88961f4130e830542d441c7ed6c78baa28e799163abac53d2be4923fb5ab7d'
SERVICES = ['aiwaf', *['aiwaf_' + name for name in ('fastify', 'hapi', 'koa', 'nest', 'next', 'adonis', 'sails')],
            *['aiwaf-' + name for name in ('django', 'flask', 'fastapi', 'java', 'spring', 'java-r', 'spring-r')]]
RESUME = False


def scan(service):
    try:
        return scan_image(service)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {'service': service, 'status': 'error', 'error': str(error)}


def scan_image(service):
    image = 'sandbox-' + service
    inspection = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True))[0]
    image_id = inspection['Id']
    output = HERE / ('results_owasp_scan_' + service + '.json')
    data = None
    if RESUME and output.exists():
        try:
            previous = json.loads(output.read_text(encoding='utf-8'))
            source = previous.get('source', {}).get('target', {})
            layers_equal = [layer['digest'] for layer in source.get('layers', [])] == inspection['RootFS']['Layers']
            configuration = json.loads(base64.b64decode(source['config']))['config']
            runtime_equal = all(configuration.get(key, '') == inspection['Config'].get(key, '')
                                for key in ('Env', 'Cmd', 'Entrypoint', 'WorkingDir', 'User'))
            # Containerd's inspect ID may name an OCI index; Grype reports its
            # selected platform's config ID. Compare actual files and runtime
            # configuration rather than incorrectly treating these as one ID.
            if layers_equal and runtime_equal:
                data = previous
        except (ValueError, KeyError, TypeError):
            pass
    command = ['docker', 'run', '--rm',
               '--mount', 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
               '--mount', 'type=volume,source=sandbox_grype_db,target=/cache/grype',
               '--mount', f'type=bind,source={HERE},target=/reports',
               '-e', 'GRYPE_DB_CACHE_DIR=/cache/grype', SCANNER, 'docker:' + image,
               '-o', 'json', '--file', '/reports/' + output.name]
    reused = data is not None
    if not reused:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1200)
        if process.returncode:
            return {'service': service, 'image_id': image_id, 'status': 'error', 'error': process.stderr[-2000:]}
        data = json.loads(output.read_text(encoding='utf-8'))
    findings = [{'id': match['vulnerability']['id'], 'severity': match['vulnerability']['severity'],
                 'package': match['artifact']['name'], 'version': match['artifact']['version'],
                 'type': match['artifact']['type'], 'fix': match['vulnerability']['fix'],
                 'locations': match['artifact'].get('locations', [])} for match in data['matches']]
    counts = {level: sum(row['severity'] == level for row in findings)
              for level in ('Critical', 'High', 'Medium', 'Low', 'Negligible', 'Unknown')}
    row = {'service': service, 'image_id': image_id, 'status': 'findings' if findings else 'pass',
           'counts': counts, 'findings': findings, 'report': output.name, 'reused_same_filesystem_and_config': reused,
           'scanned_config_id': data['source']['target']['imageID'],
           'scanned_at': datetime.fromtimestamp(output.stat().st_mtime, timezone.utc).isoformat(),
           'database': data.get('descriptor', {}).get('db'), 'distro': data.get('distro')}
    print(service + ': ' + str(counts), flush=True)
    return row


def main():
    global RESUME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', action='append', choices=SERVICES)
    parser.add_argument('--resume', action='store_true', help='Reuse completed reports only when filesystem layers and runtime config match; retain original scan dates')
    parser.add_argument('--output', type=Path, default=HERE / 'results_local_image_advisories.json')
    args = parser.parse_args()
    RESUME = args.resume
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(scan, args.service or SERVICES))
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanner': SCANNER, 'images': rows,
              'limits': 'Advisory matches require triage; no ignored vulnerabilities. Source locks may also be catalogued. Not supply-chain certification.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(1 if any(row['status'] == 'error' or row.get('counts', {}).get('High', 0)
                             or row.get('counts', {}).get('Critical', 0) for row in rows) else 0)


if __name__ == '__main__':
    main()
