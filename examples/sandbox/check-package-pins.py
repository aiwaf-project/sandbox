"""Check that package manifests, lockfiles and Compose match package-versions.json.

Run: python examples/sandbox/check-package-pins.py [--check-registries]
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def node_problems(sandbox, pins):
    problems = []
    for manifest in sorted(sandbox.glob("aiwaf-*/package.json")):
        name = manifest.parent.name
        dependencies = json.loads(manifest.read_text(encoding="utf-8")).get("dependencies", {})
        lockfile = manifest.with_name("package-lock.json")
        if not lockfile.is_file():
            problems.append(f"{name}: package-lock.json is missing")
            continue
        packages = json.loads(lockfile.read_text(encoding="utf-8")).get("packages", {})
        for package, pin in (("aiwaf", "npm-aiwaf"), ("aiwaf-wasm", "aiwaf-wasm")):
            if package not in dependencies:
                continue
            if dependencies[package] != pins[pin]:
                problems.append(f"{name}: package.json has {package} {dependencies[package]}, expected {pins[pin]}")
            locked = packages.get(f"node_modules/{package}", {}).get("version")
            if locked != pins[pin]:
                problems.append(f"{name}: package-lock.json has {package} {locked}, expected {pins[pin]}")
    return problems


def python_problems(sandbox, pins):
    problems = []
    for lockfile in sorted(sandbox.glob("aiwaf-*/requirements.lock")):
        name = lockfile.parent.name
        text = lockfile.read_text(encoding="utf-8")
        for package in ("aiwaf", "aiwaf-rust"):
            match = re.search(rf"^{re.escape(package)}==([^\s\\]+)", text, re.M)
            found = match.group(1) if match else None
            if found != pins[package]:
                problems.append(f"{name}: requirements.lock has {package} {found}, expected {pins[package]}")
    return problems


def java_problems(sandbox, pins):
    problems = []
    for pom in sorted(sandbox.glob("aiwaf-*/pom.xml")):
        match = re.search(r"<aiwaf\.version>([^<]+)</aiwaf\.version>", pom.read_text(encoding="utf-8"))
        found = match.group(1) if match else None
        if found != pins["aiwaf-java"]:
            problems.append(f"{pom.parent.name}: pom.xml has aiwaf-java {found}, expected {pins['aiwaf-java']}")
    return problems


def compose_problems(root):
    problems = []
    for compose in (root / "docker-compose.yml", root / "examples/sandbox/docker-compose.adapters.yml"):
        if not compose.is_file():
            continue
        for dockerfile in sorted(set(re.findall(r"^\s*dockerfile:\s*(\S+)", compose.read_text(encoding="utf-8"), re.M))):
            if not (root / dockerfile).is_file() and not (compose.parent / dockerfile).is_file():
                problems.append(f"{compose.name}: {dockerfile} doesn't exist")
    return problems


def find_problems(root):
    sandbox = root / "examples/sandbox"
    pins = json.loads((sandbox / "package-versions.json").read_text(encoding="utf-8"))
    return [
        *node_problems(sandbox, pins),
        *python_problems(sandbox, pins),
        *java_problems(sandbox, pins),
        *compose_problems(root),
    ]


def registry_warnings(pins, fetch_all=None):
    """A new release must not fail unrelated pull requests, so these never fail the check."""
    try:
        published = fetch_all() if fetch_all else fetch_published()
    except Exception as error:  # Network problems aren't pin problems.
        return [f"Skipped the registry check: {error}"]
    return [
        f"package-versions.json has {name} {pins.get(name)}, but {version} is published."
        for name, version in published.items()
        if pins.get(name) != version
    ]


def fetch_published():
    spec = importlib.util.spec_from_file_location("registry_versions", HERE / "registry-versions.py")
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(pool.map(registry.fetch, registry.URLS.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-registries", action="store_true", help="Warn if newer versions are published.")
    args = parser.parse_args(argv)
    root = HERE.parents[1]
    if args.check_registries:
        pins = json.loads((HERE / "package-versions.json").read_text(encoding="utf-8"))
        for warning in registry_warnings(pins):
            print(f"::warning::{warning}")
    problems = find_problems(root)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"\n{len(problems)} problems. See package-versions.json.")
        return 1
    print("Package pins and Compose build files are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
