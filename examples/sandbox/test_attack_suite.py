"""Offline regression tests for client identity in the end-to-end runner."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("attack_suite", Path(__file__).with_name("attack-suite.py"))
suite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = suite
with patch.dict(sys.modules, {"requests": Mock()}):
    spec.loader.exec_module(suite)


class ClientIdentityTests(unittest.TestCase):
    def test_stateful_attacks_keep_identity_and_scenarios_are_isolated(self):
        identities = {}
        headers = suite.make_header_generator({}, suite.make_ip_generator("93.184.216", "test", 0))

        def scenario(name):
            def run(url):
                identities[name] = [suite._get_default_headers("GET", url)["x-forwarded-for"] for _ in range(5)]
                return [suite.RequestResult(200, 1)] * 5
            return run

        with patch.object(suite, "request_once", return_value=suite.RequestResult(200, 1)):
            suite.run_test_suite("http://localhost", "test", None, [
                ("burst", scenario("burst")),
                ("brute_force", scenario("brute_force")),
                ("path_probe", scenario("path_probe")),
            ], headers)

        self.assertEqual(len(set(identities["burst"])), 1)
        self.assertEqual(len(set(identities["brute_force"])), 1)
        self.assertNotEqual(identities["burst"][0], identities["brute_force"][0])
        self.assertEqual(len(set(identities["path_probe"])), 5)
        self.assertEqual(len({suite._get_default_headers("GET", "/")["x-forwarded-for"] for _ in range(2)}), 2)


if __name__ == "__main__":
    unittest.main()
