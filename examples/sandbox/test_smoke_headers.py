"""Ensure the live header-casing check changes the actual HTTP field names."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location("smoke_test", Path(__file__).with_name("smoke-test.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class HeaderCasingTests(unittest.TestCase):
    def test_lowercase_probe_preserves_lowercase_names_on_wire(self):
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                observed.append(dict(self.headers.raw_items()))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(smoke.request(base, "/", "93.184.216.50"), 200)
            self.assertEqual(smoke.request(base, "/", "93.184.216.50", lowercase=True), 200)
            self.assertIn("User-Agent", observed[0])
            self.assertIn("user-agent", observed[1])
            self.assertNotIn("User-Agent", observed[1])
            self.assertIn("x-forwarded-for", observed[1])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
