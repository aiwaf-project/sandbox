"""Refresh Linux/Python 3.11 wheel hash locks from the running local proxies."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import argparse

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = r'''
import hashlib, importlib.metadata as m, json, pathlib, subprocess, sys, tempfile, zipfile
from email.parser import BytesParser
packages = sorted({d.metadata['Name'] + '==' + d.version for d in m.distributions()
                   if d.metadata['Name'].lower() not in ('aiwaf', 'pip', 'wheel', 'setuptools')})
if len(sys.argv) > 1 and sys.argv[1] == 'build-tools':
    packages = []
with tempfile.TemporaryDirectory(prefix='aiwaf-lock-') as directory:
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--no-deps',
                    '--dest', directory, *packages, 'wheel', 'setuptools'], check=True, stdout=sys.stderr)
    rows = []
    for wheel in pathlib.Path(directory).glob('*.whl'):
        with zipfile.ZipFile(wheel) as archive:
            metadata = BytesParser().parsebytes(archive.read(next(p for p in archive.namelist() if p.endswith('.dist-info/METADATA'))))
        rows.append(metadata['Name'] + '==' + metadata['Version'] + ' --hash=sha256:' + hashlib.sha256(wheel.read_bytes()).hexdigest())
    print('# Linux x86_64 / CPython 3.11; refresh with lock-python-dependencies.py\n' + '\n'.join(sorted(rows, key=str.lower)))
'''


def refresh(framework, build_tools_only=False):
    output = subprocess.check_output(['docker', 'compose', 'exec', '-T', f'aiwaf-{framework}',
                                      'python', '-c', PROGRAM, *(['build-tools'] if build_tools_only else [])], cwd=ROOT, text=True)
    destination = ROOT / f'examples/sandbox/aiwaf-{framework}-proxy/requirements.lock'
    if build_tools_only:
        retained = [line for line in destination.read_text().splitlines()
                    if not line.startswith(('setuptools==', 'wheel==')) and not line.startswith('#')]
        output = '# Linux x86_64 / CPython 3.11; refresh with lock-python-dependencies.py\n' + '\n'.join(
            sorted(retained + [line for line in output.splitlines() if not line.startswith('#')], key=str.lower)) + '\n'
    destination.write_text(output, encoding='utf-8')
    print(destination, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-build-tools', action='store_true', help='Update only setuptools/wheel hash pins, preserving other resolved dependencies')
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda framework: refresh(framework, args.refresh_build_tools), ('django', 'flask', 'fastapi')))
