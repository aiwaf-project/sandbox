"""Verify registry-installed releases and run fresh end-to-end OWASP scenarios."""
import argparse
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PREFIX='results_published_'

def read(name):
    return json.loads((HERE/(PREFIX+name+'.json')).read_text())

def image_lines(report):
    rows=report['images']
    failed=sum(r['status']=='error' or r.get('counts',{}).get('Critical',0)>0 or r.get('counts',{}).get('High',0)>0 for r in rows)
    lines=['','## Container image audit','',
        f'{failed}/{len(rows)} images fail the high/critical advisory gate. Advisory matches require location and exploitability triage.','',
        '| Image | Critical | High | Medium |', '| --- | ---: | ---: | ---: |']
    for row in rows:
        counts=row.get('counts',{})
        lines.append('| '+row['service']+' | '+' | '.join(str(counts.get(k,'error')) for k in ('Critical','High','Medium'))+' |')
    lines+=['','Full package locations, database provenance and findings are recorded in results_published_image_advisories.json and results_published_owasp_summary.md.','']
    return lines

def verify_versions(targets):
    pins=json.loads((HERE/'package-versions.json').read_text())
    versions={}
    for name in targets:
        service='aiwaf' if name=='node' else 'aiwaf_'+name if name in ('fastify','hapi','koa','nest','next','adonis','sails') else 'aiwaf-'+name
        command=['docker','compose','exec','-T',service]
        if name in ('django','flask','fastapi'):
            program="import importlib.metadata as m,json; print(json.dumps({p:m.version(p) for p in ('aiwaf','aiwaf-rust')})); assert m.distribution('aiwaf').read_text('direct_url.json') is None"
            value=json.loads(subprocess.check_output(command+['python','-c',program],cwd=ROOT,text=True))
            assert value=={p:pins[p] for p in ('aiwaf','aiwaf-rust')},value
        elif name in ('java','spring','java-r','spring-r'):
            with tempfile.TemporaryDirectory(prefix='aiwaf-registry-') as directory:
                jar=Path(directory)/'app.jar'
                subprocess.run(['docker','compose','cp',service+':/app/app.jar',str(jar)],cwd=ROOT,check=True)
                with zipfile.ZipFile(jar) as archive:
                    nested=next((p for p in archive.namelist() if p.startswith('BOOT-INF/lib/aiwaf-java-')),None)
                    dependency=zipfile.ZipFile(io.BytesIO(archive.read(nested))) if nested else archive
                    props=dependency.read('META-INF/maven/io.github.aiwaf-project/aiwaf-java/pom.properties').decode()
                    version=next(line.split('=',1)[1] for line in props.splitlines() if line.startswith('version='))
                    value={'aiwaf-java':version}
                    assert version==pins['aiwaf-java'],value
                    if nested: dependency.close()
        else:
            program="const path=require('path');const sdk=require.resolve('aiwaf'); const wasm=require.resolve('aiwaf-wasm/package.json',{paths:[path.dirname(sdk)]}); console.log(JSON.stringify({aiwaf:require('aiwaf/package.json').version,'aiwaf-wasm':require(wasm).version})); if(sdk.startsWith('/opt/aiwaf-js')) process.exit(1)"
            value=json.loads(subprocess.check_output(command+['node','-e',program],cwd=ROOT,text=True))
            assert value=={'aiwaf':pins['npm-aiwaf'],'aiwaf-wasm':pins['aiwaf-wasm']},value
        image=subprocess.check_output(['docker','compose','images','-q',service],cwd=ROOT,text=True).strip()
        versions[name]={**value,'image':image}
    (HERE/(PREFIX+'versions.json')).write_text(json.dumps(versions,indent=2)+'\n')
    print('Verified registry release versions in all 15 integrations',flush=True)
    return versions

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--skip-image-scans',action='store_true',help='Mark image scans unassessed instead of running Grype')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('published_smoke',HERE/'smoke-test.py')
    smoke=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    targets={name:url.replace('localhost','127.0.0.1') for name,url in smoke.ALL_TARGETS.items() if name not in ('laravel','symfony','wordpress')}
    versions=verify_versions(targets)
    if args.verify_only:return
    selected=[arg for name,url in targets.items() for arg in ('--target',name+'='+url)]
    jobs=[
      ('hardening','assessment/check_runtime_hardening.py',[]),
      ('smoke','smoke-test.py',[*selected,'--burst-workers','16']),
      ('login','validate-login-bypass.py',selected),
      ('payload','validate-runtime-matrix.py',selected),
      ('login_after_matrix','validate-login-bypass.py',selected),
      ('owasp_extended','assessment/run.py',['--fixture','http://127.0.0.1:8090','--fixture','http://127.0.0.1:3020',
         '--extended','--allow-local-http','--local-runtime-scope','--npm-audit','--tls-url','https://localhost:8443',
         '--tls-url','https://localhost:8444','--ca-file',str(HERE/'assessment/.tls/root.crt')]),
      ('npm_audits','audit-published-proxies.py',[]),
      ('outages','assessment/outages.py',[])]
    if not args.skip_image_scans:jobs.append(('image_advisories','assessment/scan_images.py',[]))
    exits={}
    started=datetime.now(timezone.utc).isoformat()
    for name,script,options in jobs:
        output=HERE/(PREFIX+name+'.json')
        if output.exists(): output.unlink()
        print('Running registry-package '+name+' checks...',flush=True)
        exits[name]=subprocess.run([sys.executable,str(HERE/script),*options,'--output',str(output)],cwd=ROOT).returncode
    run={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'versions':versions,'targets':targets,'exit_codes':exits}
    (HERE/(PREFIX+'run.json')).write_text(json.dumps(run,indent=2)+'\n')
    missing=[name for name in exits if not (HERE/(PREFIX+name+'.json')).exists()]
    if missing: raise SystemExit('Incomplete run; missing reports: '+', '.join(missing))
    lines=['# Published AIWAF sandbox validation','',
       'Installed from PyPI, npm and Maven Central. PHP is a separate package and excluded from this release run.','',
       '| Runtime | Smoke | SQL OR bypass | SQL comment bypass | Post-matrix SQL controls |',
       '| --- | --- | --- | --- | --- |']
    after=read('login_after_matrix')['targets']
    login=read('login')['targets']
    for row in read('smoke'):
        name=row['target']; attacks=login[name]['attacks']
        lines.append('| '+' | '.join([name,'PASS' if row.get('passed') else 'FAIL',
          *[attacks[k]['verdict'].upper() for k in ('sql_or_true','sql_comment_password')],
          'PASS' if all(a['verdict']=='pass' for a in after[name]['attacks'].values()) else 'FAIL'])+' |')
    matrix=read('payload')
    scenarios=[r for rows in matrix['targets'].values() for r in rows]
    errors=sum(bool(r.get('errors')) or r['observation'] in ('error','request_errors') for r in scenarios)
    lines+=['',f'Payload matrix: {len(scenarios)} scenarios; {errors} request errors. Denial counts are observations, not proof of exploit prevention.','',
       f"Runtime hardening: {sum(row['passed'] for row in read('hardening')['runtimes'])}/15 serving runtimes pass effective permission checks.",'',
       '## Assessment outcomes','', '| Check | Scope | Result |', '| --- | --- | --- |']
    for name in ('owasp_extended','npm_audits','outages'):
        for check in read(name)['checks']:
            lines.append('| '+check['category']+' '+check['check']+' | '+check['scope']+' | '+check['status']+' |')
    lines+=['','Reference application controls do not establish that AIWAF supplies authorization, MFA, cryptography or business rules. These selected scenarios do not establish complete OWASP category coverage.','']
    if not args.skip_image_scans:lines+=image_lines(read('image_advisories'))
    (HERE/(PREFIX+'validation.md')).write_text('\n'.join(lines))
    if not args.skip_image_scans:
        subprocess.run([sys.executable,str(HERE/'assessment/render_report.py'),'--prefix','published'],cwd=ROOT,check=True)
    print('Report: '+str(HERE/(PREFIX+'validation.md')),flush=True)
    raise SystemExit(int(any(exits.values()) or errors or any(not r.get('passed') for r in read('smoke'))
       or any(a['verdict']!='pass' for report in (login,after) for row in report.values() for a in row['attacks'].values())))

if __name__=='__main__':main()
