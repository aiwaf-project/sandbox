"""Read release versions directly from the public package registries."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET

URLS = {
    'aiwaf': 'https://pypi.org/pypi/aiwaf/json',
    'aiwaf-rust': 'https://pypi.org/pypi/aiwaf-rust/json',
    'npm-aiwaf': 'https://registry.npmjs.org/aiwaf/latest',
    'aiwaf-wasm': 'https://registry.npmjs.org/aiwaf-wasm/latest',
    'aiwaf-java': 'https://repo.maven.apache.org/maven2/io/github/aiwaf-project/aiwaf-java/maven-metadata.xml',
}

def fetch(item):
    name, url = item
    with urlopen(url, timeout=30) as response:
        body=response.read()
    if name == 'aiwaf-java':
        return name, ET.fromstring(body).findtext('versioning/release')
    data=json.loads(body)
    return name, data['info']['version'] if 'info' in data else data['version']

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=5) as pool:
        versions=dict(pool.map(fetch, URLS.items()))
    output=Path(__file__).with_name('package-versions.json')
    output.write_text(json.dumps(versions,indent=2)+'\n')
    print(json.dumps(versions,indent=2))
