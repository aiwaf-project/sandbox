"""Each pin rule must catch the mismatch it exists for."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("package_pins", Path(__file__).with_name("check-package-pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

VERSIONS = {"aiwaf": "1.1.8", "aiwaf-rust": "0.2.7", "npm-aiwaf": "1.1.5", "aiwaf-wasm": "0.2.5", "aiwaf-java": "1.3.5"}


class PackagePinsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.sandbox = self.root / "examples/sandbox"
        self.write("package-versions.json", json.dumps(VERSIONS))
        self.write_node()
        self.write_lock()
        self.write_pom()
        self.write("aiwaf-proxy/Dockerfile", "FROM scratch\n")
        (self.root / "docker-compose.yml").write_text("    dockerfile: examples/sandbox/aiwaf-proxy/Dockerfile\n", encoding="utf-8")

    def write(self, relative, text):
        path = self.sandbox / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_node(self, manifest="1.1.5", locked="1.1.5"):
        self.write("aiwaf-proxy/package.json", json.dumps({"dependencies": {"aiwaf": manifest, "aiwaf-wasm": "0.2.5"}}))
        self.write("aiwaf-proxy/package-lock.json", json.dumps({"packages": {
            "node_modules/aiwaf": {"version": locked}, "node_modules/aiwaf-wasm": {"version": "0.2.5"}}}))

    def write_lock(self, rust="0.2.7"):
        self.write("aiwaf-flask-proxy/requirements.lock", f"aiwaf==1.1.8 --hash=sha256:aa \\\n    --hash=sha256:bb\naiwaf-rust=={rust} --hash=sha256:cc\n")

    def write_pom(self, version="1.3.5"):
        self.write("aiwaf-java/pom.xml", f"<properties><aiwaf.version>{version}</aiwaf.version></properties>")

    def problems(self):
        return pins.find_problems(self.root)

    def test_consistent_files_pass(self):
        self.assertEqual(self.problems(), [])

    def test_node_manifest_mismatch_is_reported(self):
        self.write_node(manifest="1.1.4")
        self.assertEqual(self.problems(), ["aiwaf-proxy: package.json has aiwaf 1.1.4, expected 1.1.5"])

    def test_node_lockfile_mismatch_is_reported(self):
        self.write_node(locked="1.1.4")
        self.assertEqual(self.problems(), ["aiwaf-proxy: package-lock.json has aiwaf 1.1.4, expected 1.1.5"])

    def test_missing_node_lockfile_is_reported(self):
        (self.sandbox / "aiwaf-proxy/package-lock.json").unlink()
        self.assertEqual(self.problems(), ["aiwaf-proxy: package-lock.json is missing"])

    def test_python_lock_mismatch_is_reported(self):
        self.write_lock(rust="0.2.6")
        self.assertEqual(self.problems(), ["aiwaf-flask-proxy: requirements.lock has aiwaf-rust 0.2.6, expected 0.2.7"])

    def test_java_mismatch_is_reported(self):
        self.write_pom("1.3.4")
        self.assertEqual(self.problems(), ["aiwaf-java: pom.xml has aiwaf-java 1.3.4, expected 1.3.5"])

    def test_missing_dockerfile_is_reported(self):
        (self.sandbox / "aiwaf-proxy/Dockerfile").unlink()
        self.assertEqual(self.problems(), ["docker-compose.yml: examples/sandbox/aiwaf-proxy/Dockerfile doesn't exist"])

    def test_new_release_only_warns(self):
        published = lambda: dict(VERSIONS, aiwaf="1.1.9")
        self.assertEqual(pins.registry_warnings(VERSIONS, published), ["package-versions.json has aiwaf 1.1.8, but 1.1.9 is published."])

    def test_network_problems_only_warn(self):
        def offline():
            raise OSError("offline")

        self.assertEqual(pins.registry_warnings(VERSIONS, offline), ["Skipped the registry check: offline"])


if __name__ == "__main__":
    unittest.main()
