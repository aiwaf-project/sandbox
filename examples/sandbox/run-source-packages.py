"""Validate GitHub source-built non-PHP SDK integrations without clearing Redis state."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def verify_source_packages(targets, output=None):
    config = json.loads(subprocess.check_output(['docker', 'compose', 'config', '--format', 'json'], cwd=ROOT, text=True))
    versions = {}
    for name in targets:
        service = 'aiwaf' if name == 'node' else ('aiwaf_' + name if name in
            ('fastify', 'hapi', 'koa', 'nest', 'next', 'adonis', 'sails') else 'aiwaf-' + name)
        command = ['docker', 'compose', 'exec', '-T', service]
        source = config['services'][service]['build']['additional_contexts']['aiwaf_source']
        container = subprocess.check_output(['docker', 'compose', 'ps', '-q', service], cwd=ROOT, text=True).strip()
        labels = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .Config.Labels}}', container], cwd=ROOT, text=True))
        assert labels.get('io.github.aiwaf.source') == source, f'{service}: rebuild required for {source}'
        if name in ('django', 'flask', 'fastapi'):
            program = "import importlib.metadata as m,json;d=m.distribution('aiwaf');print(json.dumps({'aiwaf':d.version,'source':json.loads(d.read_text('direct_url.json'))['url']}))"
            value = json.loads(subprocess.check_output(command + ['python', '-c', program], cwd=ROOT, text=True))
            assert value == {'aiwaf': '1.1.1', 'source': 'file:///opt/aiwaf-source'}, value
        elif name in ('java', 'spring', 'java-r', 'spring-r'):
            with tempfile.TemporaryDirectory(prefix='aiwaf-source-') as temporary:
                jar = Path(temporary) / 'app.jar'
                subprocess.run(['docker', 'compose', 'cp', f'{service}:/app/app.jar', str(jar)], cwd=ROOT, check=True)
                with zipfile.ZipFile(jar) as archive:
                    nested = next((p for p in archive.namelist() if p.startswith('BOOT-INF/lib/aiwaf-java-')), None)
                    dependency = zipfile.ZipFile(io.BytesIO(archive.read(nested))) if nested else archive
                    props = dependency.read('META-INF/maven/io.github.aiwaf-project/aiwaf-java/pom.properties').decode()
                    version = next(line.split('=', 1)[1] for line in props.splitlines() if line.startswith('version='))
                    assert version == '1.3.2' and 'com/aiwaf/core/SqlInjectionCore.class' in dependency.namelist()
                    value = {'aiwaf-java': version, 'sql_inspection_class': True}
                    if nested:
                        dependency.close()
        else:
            program = "console.log(JSON.stringify({aiwaf:require('aiwaf/package.json').version,source:require('fs').realpathSync(require.resolve('aiwaf'))}))"
            value = json.loads(subprocess.check_output(command + ['node', '-e', program], cwd=ROOT, text=True))
            assert value == {'aiwaf': '1.1.1', 'source': '/opt/aiwaf-js/index.js'}, value
        versions[name] = {**value, 'github_source': source}
    (output or HERE / 'results_local_versions.json').write_text(json.dumps(versions, indent=2) + '\n')
    print('Verified GitHub source SDKs in all 15 running proxies: ' + source, flush=True)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-completed', action='store_true')
    parser.add_argument('--verify-only', action='store_true', help='Verify running GitHub source builds without executing suites')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('local_smoke', HERE / 'smoke-test.py')
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    targets = {name: url.replace('localhost', '127.0.0.1') for name, url in smoke.ALL_TARGETS.items()
               if name not in ('laravel', 'symfony', 'wordpress')}
    source = verify_source_packages(targets)
    if args.verify_only:
        return
    if args.skip_completed:
        previous = HERE / 'results_local_run.json'
        if not previous.exists() or json.loads(previous.read_text()).get('github_source') != source:
            raise SystemExit('Cannot reuse reports from a different source. Run without --skip-completed.')
    selected = [arg for name, url in targets.items() for arg in ('--target', f'{name}={url}')]
    jobs = [
        ('smoke', 'smoke-test.py', [*selected, '--burst-workers', '16']),
        ('login', 'validate-login-bypass.py', selected),
        ('payload', 'validate-runtime-matrix.py', selected),
        ('login_after_matrix', 'validate-login-bypass.py', selected),
        ('owasp', 'assessment/run.py', ['--fixture', 'http://127.0.0.1:8090', '--fixture',
          'http://127.0.0.1:3020', '--allow-local-http', '--npm-audit', '--local-runtime-scope']),
        ('npm_audits', 'audit-published-proxies.py', ['--include-sdk']),
    ]
    exits = {}
    started = datetime.now(timezone.utc).isoformat()
    for name, script, options in jobs:
        output = HERE / f'results_local_{name}.json'
        if args.skip_completed and output.exists():
            exits[name] = None
            continue
        # Never render a previous report as if a failed subprocess produced it.
        if output.exists():
            output.unlink()
        print(f'Running local SDK {name} checks...', flush=True)
        exits[name] = subprocess.run([sys.executable, str(HERE / script), *options,
                                      '--output', str(output)], cwd=ROOT).returncode
    run = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
           'targets': targets, 'exit_codes': exits, 'github_source': source}
    (HERE / 'results_local_run.json').write_text(json.dumps(run, indent=2) + '\n')
    missing = [name for name in exits if not (HERE / f'results_local_{name}.json').exists()]
    if missing:
        (HERE / 'results_local_validation.md').write_text(
            '# Local AIWAF SDK validation\n\nIncomplete run. Missing fresh reports: '
            + ', '.join(missing) + '. See results_local_run.json for subprocess exit codes.\n')
        raise SystemExit(1)
    def read(name):
        return json.loads((HERE / f'results_local_{name}.json').read_text())
    rows, login, after, payload = [read(name) for name in ('smoke', 'login', 'login_after_matrix', 'payload')]
    cases = [row for group in payload['targets'].values() for row in group]
    errors = sum(bool(row.get('errors')) or row['observation'] in ('error', 'request_errors') for row in cases)
    assessment, audits = read('owasp'), read('npm_audits')
    lines = ['# Local AIWAF SDK validation', '', f'Started: {started}', '',
             'GitHub source builds: Python/JavaScript 1.1.1 and Java 1.3.2. PHP excluded.', '',
             'Source: ' + source, '',
             '| Runtime | Smoke | SQL OR true | SQL comment | Post-matrix SQL checks |',
             '| --- | --- | --- | --- | --- |']
    reused = [name for name, code in exits.items() if code is None]
    if reused:
        lines[4:4] = ['Reused existing suite reports: ' + ', '.join(reused) + '.', '']
    for row in rows:
        name = row['target']
        attacks = login['targets'][name]['attacks']
        post = after['targets'][name]
        lines.append('| ' + ' | '.join([name, 'PASS' if row.get('passed') else 'FAIL',
            *[attacks[key]['verdict'].upper() for key in ('sql_or_true', 'sql_comment_password')],
            'PASS' if all(a['verdict'] == 'pass' for a in post['attacks'].values()) else 'FAIL']) + ' |')
    lines += ['', f'Payload matrix: {len(cases)} scenarios; {errors} scenarios with request errors; complete: {"finished_at" in payload}.',
              f"Payload matrix timestamps: {payload.get('started_at')} to {payload.get('finished_at')}.",
              'Payload denial counts are observations, not confirmed exploit prevention.', '',
              '| Assessment | Scope | Outcome |', '| --- | --- | --- |']
    for check in assessment['checks'] + audits['checks']:
        lines.append(f"| {check['category']} {check['check']} | {check['scope']} | {check['status'].upper()} |")
        if check['status'] in ('fail', 'error'):
            lines += ['', 'Evidence: ' + json.dumps(check['evidence']), '']
    lines += ['', 'Reference application controls belong to the fixture. Passing them does not certify AIWAF against the OWASP Top 10.',
              'Local HTTP transport is not a TLS assessment. npm audits cover the proxy frameworks and the local SDK production tree; they do not scan Python, Java or OS dependencies.', '']
    output = HERE / 'results_local_validation.md'
    output.write_text('\n'.join(lines), encoding='utf-8')
    (HERE / 'results_local_run.json').write_text(json.dumps({'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'targets': targets, 'exit_codes': exits,
        'github_source': source}, indent=2) + '\n')
    print(output, flush=True)
    raise SystemExit(int(any(exits.values()) or errors or 'finished_at' not in payload
        or any(not r.get('passed') for r in rows)
        or any(a['verdict'] != 'pass' for report in (login, after) for t in report['targets'].values() for a in t['attacks'].values())
        or any(c['status'] in ('fail', 'error') for c in assessment['checks'] + audits['checks'])))


if __name__ == '__main__':
    main()
