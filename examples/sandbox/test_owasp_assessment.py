"""Exercise outcome assertions against both safe and deliberately broken controls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest


def load(name):
    path = Path(__file__).with_name("assessment") / f"{name}.py"
    spec = importlib.util.spec_from_file_location("assessment_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture, runner = load("fixture"), load("run")


class AssessmentTests(unittest.TestCase):
    def exercise(self, mode):
        server = fixture.serve("127.0.0.1", 0, mode, "test-control-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            return runner.fixture_checks(f"http://127.0.0.1:{server.server_port}", "test-control-token")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_secure_fixture_passes_outcome_and_concurrency_checks(self):
        checks = self.exercise("secure")
        self.assertEqual(len(checks), 7, checks)
        self.assertTrue(all(c["status"] == "pass" for c in checks), checks)
        self.assertEqual({c["category"] for c in checks}, {"A04", "A06", "A08", "A09"})

    def test_broken_controls_are_detected_in_each_application_category(self):
        checks = self.exercise("vulnerable")
        failed = {c["category"] for c in checks if c["status"] == "fail"}
        self.assertEqual(failed, {"A04", "A06", "A08", "A09"}, checks)
        self.assertFalse(any(c["status"] == "error" for c in checks), checks)
        concurrent = next(c for c in checks if c["check"] == "concurrent_stock_budget")
        self.assertEqual(concurrent["status"], "pass", "Other failed design checks must not contaminate the stock-budget test")

    def test_local_http_exemption_is_not_a_tls_pass(self):
        self.assertEqual(runner.transport_check("http://localhost:8090")["status"], "fail")
        self.assertEqual(runner.transport_check("http://localhost:8090", True)["status"], "not_assessed")
        self.assertEqual(runner.transport_check("http://example.com", True)["status"], "fail")

    def test_denial_before_application_setup_is_an_error_not_a_pass(self):
        server = fixture.serve("127.0.0.1", 0, "secure", "correct-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            checks = runner.fixture_checks(f"http://127.0.0.1:{server.server_port}", "wrong-token")
            self.assertEqual([c["status"] for c in checks], ["error"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_missing_lockfile_is_a_finding_and_manifest_is_inventoried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "examples/sandbox/aiwaf-test/package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"dependencies": {"example": "^1.0.0"}}))
            report = runner.supply_chain(root)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["evidence"]["inventory"][0]["dependencies"], {"example": "^1.0.0"})
            self.assertIn("package-lock.json", report["evidence"]["findings"][0])


if __name__ == "__main__":
    unittest.main()
