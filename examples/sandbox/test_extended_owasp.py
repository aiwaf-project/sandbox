"""Ensure each extended outcome assertion detects deliberately broken controls."""
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).with_name('assessment')))
from application_checks import application_checks
from fixture import serve
from deployment_checks import deployment_checks


class ExtendedApplicationTests(unittest.TestCase):
    def exercise(self, mode, checker=application_checks):
        server = serve('127.0.0.1', 0, mode, 'extended-test-only')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            return checker(f'http://127.0.0.1:{server.server_port}', 'extended-test-only')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_secure_access_and_authentication_controls_pass(self):
        checks = self.exercise('secure')
        self.assertEqual(len(checks), 7, checks)
        self.assertTrue(all(c['status'] == 'pass' for c in checks), checks)

    def test_each_deliberately_broken_control_fails(self):
        checks = self.exercise('vulnerable')
        self.assertEqual(len(checks), 7, checks)
        self.assertTrue(all(c['status'] == 'fail' for c in checks), checks)

    def test_deployment_assertions_detect_exposure_and_exception_leaks(self):
        secure = self.exercise('secure', deployment_checks)
        broken = self.exercise('vulnerable', deployment_checks)
        self.assertEqual(len(secure), 3)
        self.assertEqual(len(broken), 3)
        self.assertTrue(all(c['status'] == 'pass' for c in secure), secure)
        self.assertTrue(all(c['status'] == 'fail' for c in broken), broken)


if __name__ == '__main__':
    unittest.main()
