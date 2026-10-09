"""Check normal headers, automation detection, and stateful rate limits."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import secrets
import time
import urllib.parse


DEFAULT_TARGETS = {
    "node": "http://localhost:3000",
    "django": "http://localhost:3009",
    "flask": "http://localhost:3010",
    "fastapi": "http://localhost:3011",
    "laravel": "http://localhost:8081",
    "symfony": "http://localhost:8082",
    "wordpress": "http://localhost:8083",
    "java": "http://localhost:8080",
    "spring": "http://localhost:8084",
}
ALL_TARGETS = {**DEFAULT_TARGETS,
    "fastify": "http://localhost:3002", "hapi": "http://localhost:3003",
    "koa": "http://localhost:3004", "nest": "http://localhost:3005",
    "next": "http://localhost:3006", "adonis": "http://localhost:3007",
    "sails": "http://localhost:3008", "java-r": "http://localhost:8085",
    "spring-r": "http://localhost:8086"}


def request(base, path, ip, *, scanner=False, lowercase=False, method="GET", body=None):
    headers = {
        "User-Agent": "python-requests/2.34.2" if scanner else "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Forwarded-For": ip,
    }
    if lowercase:
        headers = {k.lower(): v for k, v in headers.items()}
    payload = json.dumps(body).encode() if body is not None else None
    if payload is not None:
        headers["Content-Type"] = "application/json"
    url = urllib.parse.urlsplit(base.rstrip("/") + path)
    connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(url.hostname, url.port, timeout=15)
    try:
        # http.client preserves field-name casing; urllib.Request normalizes it.
        connection.request(method, urllib.parse.urlunsplit(("", "", url.path, url.query, "")), body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read()
        if b"Fatal error:" in body or b"Failed opening required" in body:
            raise ValueError("Proxy returned a PHP runtime error")
        if method == "POST" and response.status == 401 and b"Invalid email or password" not in body:
            raise ValueError("Login response does not match the upstream invalid-credentials result")
        return response.status
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", metavar="NAME=URL", help="Repeat to select targets")
    parser.add_argument("--all", action="store_true", help="Select all 18 production-style proxies")
    parser.add_argument("--output", type=Path, help="Save all per-runtime checks as JSON")
    parser.add_argument("--burst-workers", type=int, default=1, help="Concurrent requests for a burst (1..64)")
    args = parser.parse_args()
    if not 1 <= args.burst_workers <= 64:
        parser.error('--burst-workers must be 1..64')
    targets = dict(item.split("=", 1) for item in args.target) if args.target else (ALL_TARGETS if args.all else DEFAULT_TARGETS)
    failures = 0
    results = []
    path = "/rest/products/search?q=apple"
    for name, base in targets.items():
        # Fresh public client ranges prevent old reputation state affecting a rerun.
        prefix = f"93.{secrets.randbelow(254) + 1}.{secrets.randbelow(254) + 1}"
        try:
            normal = [request(base, path, f"{prefix}.10", lowercase=lower) for lower in (False, True)]
            scanner = request(base, path, f"{prefix}.11", scanner=True)
            started = time.monotonic()
            with ThreadPoolExecutor(max_workers=args.burst_workers) as pool:
                burst = list(pool.map(lambda _: request(base, path, f"{prefix}.12"), range(65)))
            burst_elapsed = time.monotonic() - started
            post_error = None
            try:
                post = request(base, "/rest/user/login", f"{prefix}.13", method="POST",
                               body={"email": "sandbox-probe-" + secrets.token_hex(12) + "@example.invalid",
                                     "password": "sandbox-invalid-password"})
            except (OSError, ValueError) as error:
                post, post_error = 0, str(error)
            burst_limited = 200 in burst and any(status in (403, 429) for status in burst)
            passed = normal == [200, 200] and scanner == 403 and burst_limited and post == 401
            result = {"target": name, "passed": passed, "normal": normal, "scanner": scanner,
                      "burst_workers": args.burst_workers, "burst_elapsed_seconds": round(burst_elapsed, 3),
                      "post_status": post, "post_error": post_error,
                      "checks": {"normal_headers": normal[0] == 200, "lowercase_headers": normal[1] == 200,
                                 "automation_denied": scanner == 403,
                                 "burst_limited": burst_limited,
                                 "json_post_forwarded": post == 401},
                      "burst": {str(code): burst.count(code) for code in sorted(set(burst))}}
        except (OSError, ValueError) as error:
            passed = False
            result = {"target": name, "passed": False, "error": str(error)}
        failures += not passed
        results.append(result)
        print(json.dumps(result), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
