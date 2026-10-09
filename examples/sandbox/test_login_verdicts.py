"""Guard against false security passes when the baseline or control fails."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("login_bypass", Path(__file__).with_name("validate-login-bypass.py"))
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)


class LoginVerdictTests(unittest.TestCase):
    def test_token_issuing_exploit_fails(self):
        self.assertEqual(login.verdict({"status": 401, "token_issued": False},
                                      {"status": 200, "token_issued": True},
                                      {"token_issued": True}), "fail")

    def test_blanket_blocking_cannot_pass(self):
        self.assertEqual(login.verdict({"status": 403, "token_issued": False},
                                      {"status": 403, "token_issued": False},
                                      {"token_issued": True}), "error")

    def test_server_error_cannot_pass(self):
        self.assertEqual(login.verdict({"status": 401, "token_issued": False},
                                      {"status": 500, "token_issued": False},
                                      {"token_issued": True}), "error")

    def test_unconfirmed_baseline_is_not_assessed(self):
        self.assertEqual(login.verdict({"status": 401, "token_issued": False},
                                      {"status": 403, "token_issued": False},
                                      {"token_issued": False}), "not_assessed")

    def test_confirmed_exploit_denial_passes(self):
        self.assertEqual(login.verdict({"status": 401, "token_issued": False},
                                      {"status": 403, "token_issued": False},
                                      {"token_issued": True}), "pass")
