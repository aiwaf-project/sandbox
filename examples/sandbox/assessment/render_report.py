"""Combine measured outcomes without presenting scenario passes as certification."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((HERE / ('results_local_' + name + '.json')).read_text())


def main():
    extended, outages, scans = read('owasp_extended'), read('outages'), read('image_advisories')
    login, audits, payload = read('login_after_matrix'), read('npm_audits'), read('payload')
    observations = [row for rows in payload['targets'].values() for row in rows]
    request_errors = sum(bool(row.get('errors')) or row['observation'] in
                         ('error', 'request_errors') for row in observations)
    checks = extended['checks'] + outages['checks'] + audits['checks']
    for image in scans['images']:
        counts = image.get('counts', {})
        status = ('error' if image['status'] == 'error' else
                  'fail' if counts.get('High', 0) or counts.get('Critical', 0) else 'pass')
        checks.append({'category': 'A03', 'check': 'image_advisories', 'scope': image['service'],
                       'status': status, 'evidence': counts or image.get('error')})
    for runtime, row in login['targets'].items():
        for attack, evidence in row['attacks'].items():
            checks.append({'category': 'A05', 'check': attack, 'scope': runtime,
                           'status': evidence['verdict'], 'evidence': evidence})
    lines = ['# OWASP 2025 sandbox outcomes', '',
             'Generated: ' + datetime.now(timezone.utc).isoformat(), '',
             'Local Python/JavaScript 1.1.1 and Java 1.3.2; PHP excluded.', '',
             'Scenario passes below are measured checks, not complete category coverage or OWASP certification.', '',
             f'Payload matrix: {len(observations)} observations; {request_errors} scenarios with request errors. '
             'Django was rerun in isolation after earlier timeouts during concurrent validation; '
             'the other completed runtime observations were retained.', '',
             '| Category | Passed checks | Failures/errors | Not assessed |',
             '| --- | --- | --- | --- |']
    for category in ('A01', 'A02', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09', 'A10'):
        counts = Counter(check['status'] for check in checks if check['category'] == category)
        lines.append(f'| {category} | {counts["pass"]} | {counts["fail"] + counts["error"]} | {counts["not_assessed"]} |')
    lines += ['', 'A03 image checks fail for high/critical findings; lower severity findings remain recorded.', '',
              '| Scanned image | Critical | High | Medium | Low | Scan status |',
              '| --- | --- | --- | --- | --- | --- |']
    for image in scans['images']:
        counts = image.get('counts', {})
        lines.append('| ' + image['service'] + ' | ' + ' | '.join(str(counts.get(level, 'unknown'))
                     for level in ('Critical', 'High', 'Medium', 'Low')) + ' | ' + image['status'] + ' |')
    lines += ['', 'All advisory findings and package locations remain in results_local_image_advisories.json; no vulnerabilities are suppressed.', '',
              '## Scope and outstanding work', '',
              '- A01/A06/A07/A08: authorization, sessions, reset tokens, MFA, business rules and signed data are reference application controls. AIWAF does not implement those identity or business policies.',
              '- A02/A04: loopback fixture headers and Caddy TLS termination are measured. Production/cloud configuration, at-rest encryption and production key management are not audited.',
              '- A03: npm production audit plus pinned Grype image scans cover the listed non-PHP images. Advisory matches need location/exploitability triage; build provenance and package signing remain separate.',
              '- A05: two token-issuing SQL login bypasses are denied in fifteen integrations. The 375-case payload matrix records observations and cannot establish exploit prevention for every payload.',
              '- A09: redaction, event tampering/truncation and an in-process fixture alert sink are tested. External SIEM delivery and persistent append-only storage remain unassessed.',
              '- A10: reference application exception/recovery, real isolated Express Redis/upstream failures, and Python rate-cache regression tests are covered. Every-runtime outage/failover testing remains separate.', '',
              '## Failed or unassessed checks', '']
    for check in checks:
        if check['status'] in ('fail', 'error', 'not_assessed'):
            lines.append(f'- {check["category"]} {check["check"]} [{check["scope"]}]: {check["status"]}. ' + json.dumps(check['evidence']))
    grouped = {}
    for image in scans['images']:
        for finding in image.get('findings', []):
            if finding['severity'] in ('High', 'Critical'):
                key = (finding['severity'], finding['id'], finding['package'], finding['version'],
                       finding['fix']['state'], tuple(finding['fix'].get('versions', [])))
                grouped.setdefault(key, []).append(image['service'])
        if image['status'] == 'error':
            lines.append('- A03 scan error: ' + image['service'] + ': ' + image['error'])
    for (severity, advisory, package, version, state, versions), images in sorted(grouped.items()):
        lines.append(f'- A03 {severity} {advisory}: {package} {version}; fix state {state}, versions {list(versions)}; affected: '
                     + ', '.join(sorted(set(images))) + '.')
    output = HERE / 'results_local_owasp_summary.md'
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
