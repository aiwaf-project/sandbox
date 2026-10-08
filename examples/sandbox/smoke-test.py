"""Check normal headers, automation detection, and stateful rate limits."""
import argparse
import json
import secrets
import urllib.error
import urllib.request


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


def request(base, path, ip, *, scanner=False, lowercase=False):
    headers = {
        "User-Agent": "python-requests/2.34.2" if scanner else "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Forwarded-For": ip,
    }
    if lowercase:
        headers = {k.lower(): v for k, v in headers.items()}
    req = urllib.request.Request(base.rstrip("/") + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read()
            if b"Fatal error:" in body or b"Failed opening required" in body:
                raise ValueError("Proxy returned a PHP runtime error")
            return response.status
    except urllib.error.HTTPError as error:
        error.read()
        return error.code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", metavar="NAME=URL", help="Repeat to select targets")
    args = parser.parse_args()
    targets = dict(item.split("=", 1) for item in args.target) if args.target else DEFAULT_TARGETS
    failures = 0
    path = "/rest/products/search?q=apple"
    for name, base in targets.items():
        # Fresh public client ranges prevent old reputation state affecting a rerun.
        prefix = f"93.{secrets.randbelow(254) + 1}.{secrets.randbelow(254) + 1}"
        try:
            normal = [request(base, path, f"{prefix}.10", lowercase=lower) for lower in (False, True)]
            scanner = request(base, path, f"{prefix}.11", scanner=True)
            burst = [request(base, path, f"{prefix}.12") for _ in range(65)]
            passed = normal == [200, 200] and scanner == 403 and any(status in (403, 429) for status in burst)
            result = {"target": name, "passed": passed, "normal": normal, "scanner": scanner,
                      "burst": {str(code): burst.count(code) for code in sorted(set(burst))}}
        except (OSError, ValueError) as error:
            passed = False
            result = {"target": name, "passed": False, "error": str(error)}
        failures += not passed
        print(json.dumps(result), flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
