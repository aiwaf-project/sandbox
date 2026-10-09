"""Isolated application controls for OWASP assessment; not AIWAF implementations."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class State:
    def __init__(self, mode="secure"):
        self.mode = mode
        self.key = secrets.token_bytes(32)
        self.lock = threading.RLock()
        self.runs = {}

    def create(self, password, other_password=None):
        run = secrets.token_hex(16)
        salt = secrets.token_bytes(16)
        record = {"salt": salt, "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)}
        if self.mode == "vulnerable":
            record["plaintext"] = password
        other_salt = secrets.token_bytes(16)
        self.runs[run] = {"password": record, "stock": 5, "orders": {}, "events": [], "alerts": [],
            "users": {"owner": record, "other": {"salt": other_salt,
                "hash": hashlib.pbkdf2_hmac("sha256", (other_password or secrets.token_urlsafe(24)).encode(), other_salt, 600000)}},
            "sessions": {}, "resets": {}, "challenges": {}, "mfa": False,
            "object": {"id": secrets.token_hex(12), "owner": "owner", "value": "private-value"}}
        return run

    def session(self, data, actor, supplied=""):
        token = supplied or "fixed-session" if self.mode == "vulnerable" else secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        data['sessions'][token] = {'actor': actor, 'expires': time.time() + 300, 'csrf': csrf}
        return {'authenticated': True, 'session': token, 'csrf': csrf}

    def sign(self, value):
        return hmac.new(self.key, canonical(value), hashlib.sha256).hexdigest()

    def event(self, run, kind, request_id, secret=None):
        data = self.runs[run]
        event = {"sequence": len(data["events"]) + 1, "kind": kind, "request_id": request_id,
                 "previous": data["events"][-1]["mac"] if data["events"] else ""}
        if secret and self.mode == "vulnerable":
            event["password"] = secret
        event["mac"] = self.sign(event)
        data["events"].append(event)
        if kind == "login_failed" and self.mode != "vulnerable":
            data["alerts"].append({"kind": "login_failed", "request_id": request_id})


def handler(state, admin_token):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'SandboxFixture' if state.mode == 'secure' else 'BaseHTTP/0.6'
        sys_version = ''
        def log_message(self, *_args):
            pass  # Never put request bodies, passwords or control credentials in server logs.

        def reply(self, status, value):
            payload = canonical(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            if state.mode == 'secure':
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                self.reply(200, {"ok": True})
            elif self.path in ('/.env', '/.git/config', '/debug') and state.mode == 'vulnerable':
                self.reply(200, {'debug': True, 'test_secret': 'fixture-secret'})
            elif self.path == '/fault':
                # Inject a predictable application failure without taking down
                # the shared stack or changing persistent Redis state.
                try:
                    raise RuntimeError('fixture-internal-detail')
                except RuntimeError:
                    self.reply(503, {'error': 'temporarily_unavailable'}) if state.mode == 'secure' else self.reply(500, {'error': 'RuntimeError: fixture-internal-detail', 'traceback': '/assessment/fixture.py'})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            # Control endpoints are test-only, authenticated, and bound to local ports in Compose.
            if not hmac.compare_digest(self.headers.get("X-Assessment-Token", ""), admin_token):
                self.reply(401, {"error": "control_auth_required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 16384:
                    self.reply(413, {"error": "body_size"})
                    return
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, json.JSONDecodeError):
                self.reply(400, {"error": "invalid_json"})
                return
            request_id = self.headers.get("X-Request-ID", "")[:128]
            with state.lock:
                if self.path == "/runs":
                    password = body.get("password", "")
                    if not isinstance(password, str) or not 12 <= len(password) <= 128:
                        self.reply(400, {"error": "password_length"})
                        return
                    if len(state.runs) >= 100:
                        self.reply(429, {"error": "run_capacity"})
                        return
                    other_password = body.get('other_password')
                    if other_password is not None and (not isinstance(other_password, str) or not 12 <= len(other_password) <= 128):
                        self.reply(400, {'error': 'password_length'})
                        return
                    run = state.create(password, other_password)
                    value = {"run": run, "subject": "shopper", "quantity": 1}
                    self.reply(201, {"run": run, "value": value, "signature": state.sign(value),
                                     'object_id': state.runs[run]['object']['id']})
                    return
                run = body.get("run")
                if not isinstance(run, str) or run not in state.runs:
                    self.reply(404, {"error": "run_not_found"})
                    return
                data = state.runs[run]
                if self.path.startswith(('/object/', '/session/', '/reset/', '/mfa/')) or self.path in ('/admin', '/logout'):
                    try:
                        self.control_route(state, run, data, body, request_id)
                    except (TypeError, ValueError, KeyError):
                        self.reply(400, {'error': 'invalid_request'})
                    return
                if self.path == "/cleanup":
                    del state.runs[run]
                    self.reply(200, {"deleted": True})
                elif self.path == "/snapshot":
                    record = data["password"]
                    self.reply(200, {"stock": data["stock"], "orders": len(data["orders"]),
                                     "events": data["events"], "alerts": data["alerts"],
                                     "password_storage": {"algorithm": "pbkdf2-sha256", "iterations": 600000,
                                                          "salt": record["salt"].hex(),
                                                          "digest": record["hash"].hex(),
                                                          "plaintext_present": "plaintext" in record}})
                elif self.path == "/login":
                    password = body.get("password", "")
                    if not isinstance(password, str):
                        self.reply(400, {"error": "invalid_password_type"})
                        return
                    actor = body.get('actor', 'owner')
                    record = data['users'].get(actor, data['password']) if isinstance(actor, str) else data['password']
                    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), record["salt"], 600000)
                    valid = isinstance(actor, str) and actor in data['users'] and hmac.compare_digest(candidate, record['hash'])
                    state.event(run, "login_success" if valid else "login_failed", request_id, password)
                    if valid and data['mfa'] and state.mode != 'vulnerable':
                        challenge = secrets.token_urlsafe(32)
                        data['challenges'][challenge] = {'actor': actor, 'code': str(secrets.randbelow(1000000)).zfill(6),
                                                         'expires': time.time() + 120, 'attempts': 0}
                        self.reply(202, {'authenticated': False, 'challenge': challenge})
                    else:
                        self.reply(200 if valid else 401, state.session(data, actor, body.get('session', '')) if valid else {'authenticated': False})
                elif self.path == "/verify":
                    value = body.get("value")
                    signature = body.get("signature", "")
                    valid = (isinstance(value, dict) and value.get("run") == run
                             and isinstance(signature, str) and hmac.compare_digest(signature, state.sign(value)))
                    if state.mode == "vulnerable":
                        valid = True
                    state.event(run, "integrity_valid" if valid else "integrity_rejected", request_id)
                    self.reply(200 if valid else 403, {"accepted": valid})
                elif self.path == "/verify-events":
                    events = body.get("events", [])
                    valid = isinstance(events, list) and len(events) == len(data["events"])
                    previous = ""
                    for index, event in enumerate(events if isinstance(events, list) else []):
                        if not isinstance(event, dict):
                            valid = False
                            break
                        unsigned = {k: v for k, v in event.items() if k != "mac"}
                        valid = valid and event.get("previous") == previous and event.get("sequence") == index + 1
                        valid = valid and isinstance(event.get("mac"), str) and hmac.compare_digest(event["mac"], state.sign(unsigned))
                        previous = event.get("mac", "")
                    self.reply(200, {"valid": valid})
                elif self.path == "/order":
                    quantity, key = body.get("quantity"), body.get("idempotency_key")
                    if type(quantity) is not int or not isinstance(key, str) or not 1 <= len(key) <= 128:
                        self.reply(400, {"error": "invalid_order"})
                    elif state.mode != "vulnerable" and quantity <= 0:
                        self.reply(422, {"error": "quantity_positive"})
                    elif key in data["orders"] and state.mode != "vulnerable":
                        prior = data["orders"][key]
                        self.reply(200 if prior["quantity"] == quantity else 409, prior)
                    elif quantity > data["stock"]:
                        self.reply(409, {"error": "out_of_stock"})
                    else:
                        data["stock"] -= quantity
                        order = {"quantity": quantity, "remaining": data["stock"], "order": secrets.token_hex(8)}
                        data["orders"][key] = order
                        state.event(run, "order_created", request_id)
                        self.reply(201, order)
                else:
                    self.reply(404, {"error": "not_found"})

        def control_route(self, state, run, data, body, request_id):
            secure = state.mode != 'vulnerable'
            token = self.headers.get('X-Session-Token', '')
            session = data['sessions'].get(token)
            valid = session and (not secure or session['expires'] > time.time())
            actor = session['actor'] if valid else None
            if self.path == '/reset/request':
                # Test-only simulated delivery. The assessment credential protects
                # this endpoint; production reset delivery is outside this fixture.
                target = body.get('actor', 'owner')
                if target not in data['users']:
                    self.reply(202, {'requested': True})
                    return
                reset = secrets.token_urlsafe(32)
                data['resets'][reset] = {'actor': target, 'expires': time.time() + 120}
                self.reply(202, {'requested': True, 'reset_token': reset})
            elif self.path == '/reset/expire':
                record = data['resets'].get(body.get('reset_token', ''))
                if record:
                    record['expires'] = 0
                self.reply(200, {'expired': bool(record)})
            elif self.path == '/reset/confirm':
                reset = body.get('reset_token', '')
                record = data['resets'].get(reset)
                target = body.get('actor', 'owner')
                password = body.get('password', '')
                allowed = record and record['actor'] == target and record['expires'] > time.time()
                if not secure:
                    allowed = target in data['users']
                if not allowed or not isinstance(password, str) or not 12 <= len(password) <= 128:
                    self.reply(403, {'error': 'invalid_reset'})
                    return
                salt = secrets.token_bytes(16)
                data['users'][target] = {'salt': salt, 'hash': hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)}
                if target == 'owner':
                    data['password'] = data['users'][target]
                if secure:
                    del data['resets'][reset]
                    data['sessions'] = {key: value for key, value in data['sessions'].items() if value['actor'] != target}
                self.reply(200, {'changed': True})
            elif self.path == '/mfa/enable':
                data['mfa'] = True
                self.reply(200, {'enabled': True})
            elif self.path == '/mfa/deliver':
                challenge = data['challenges'].get(body.get('challenge', ''))
                self.reply(200, {'code': challenge['code']} if challenge else {'error': 'missing_challenge'})
            elif self.path == '/mfa/verify':
                key = body.get('challenge', '')
                challenge = data['challenges'].get(key)
                if challenge:
                    challenge['attempts'] += 1
                allowed = (challenge and challenge['expires'] > time.time() and challenge['attempts'] <= 5
                           and challenge['actor'] == body.get('actor', 'owner')
                           and hmac.compare_digest(str(body.get('code', '')), challenge['code']))
                if not allowed:
                    self.reply(401, {'authenticated': False})
                    return
                del data['challenges'][key]
                self.reply(200, state.session(data, challenge['actor']))
            elif self.path == '/session/expire':
                if session:
                    session['expires'] = 0
                self.reply(200, {'expired': bool(session)})
            elif not valid:
                self.reply(401, {'error': 'session_required'})
            elif self.path == '/logout':
                if secure:
                    del data['sessions'][token]
                self.reply(200, {'logged_out': True})
            elif self.path == '/session/check':
                self.reply(200, {'authenticated': True, 'actor': actor})
            elif self.path == '/admin':
                self.reply(403 if secure else 200, {'authorized': not secure})
            elif self.path.startswith('/object/'):
                obj = data['object']
                if body.get('object_id') != obj['id']:
                    self.reply(404, {'error': 'object_not_found'})
                elif secure and actor != obj['owner']:
                    self.reply(403, {'error': 'forbidden'})
                elif self.path == '/object/read':
                    self.reply(200, obj)
                elif self.path == '/object/write':
                    if secure and not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
                        self.reply(403, {'error': 'csrf_required'})
                    elif secure and any(key in body for key in ('owner', 'role', 'is_admin')):
                        self.reply(422, {'error': 'protected_fields'})
                    elif not isinstance(body.get('value'), str) or len(body['value']) > 128:
                        self.reply(400, {'error': 'invalid_value'})
                    else:
                        obj['value'] = body['value']
                        if not secure:
                            obj['owner'] = body.get('owner', obj['owner'])
                        self.reply(200, {'updated': True})
                else:
                    self.reply(404, {'error': 'not_found'})
            else:
                self.reply(404, {'error': 'not_found'})
    return Handler


def serve(host="0.0.0.0", port=8090, mode="secure", token=None):
    token = token or os.environ.get("AIWAF_ASSESSMENT_TOKEN", "sandbox-assessment-only")
    return ThreadingHTTPServer((host, port), handler(State(mode), token))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--mode", choices=("secure", "vulnerable"), default="secure")
    args = parser.parse_args()
    serve(args.host, args.port, args.mode).serve_forever()
