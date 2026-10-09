"""Observable deployment outcomes; application controls remain fixture-owned."""
import socket
import ssl
import secrets
import urllib.error
import urllib.parse
import urllib.request
import warnings

from run import Client, BROWSER, result


def deployment_checks(base, token, ca_file=None):
    client = Client(base, token, ca_file)

    def get(path):
        request = urllib.request.Request(base.rstrip('/') + path, headers={
            'User-Agent': BROWSER, 'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Forwarded-For': f'93.{secrets.randbelow(254)+1}.{secrets.randbelow(254)+1}.20'})
        try:
            response = client.opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, dict(response.headers), response.read(65536).decode()

    health, headers, _ = get('/health')
    probes = [get(path) for path in ('/.env', '/.git/config', '/debug')]
    fault, _, body = get('/fault')
    recovered, _, _ = get('/health')
    normalized = {key.lower(): value for key, value in headers.items()}
    return [
        result('A02', 'sensitive_configuration_not_exposed', base,
               health == 200 and all(code in (403, 404) and 'fixture-secret' not in text for code, _, text in probes),
               {'health': health, 'probe_statuses': [code for code, _, _ in probes]}),
        result('A02', 'response_security_headers', base,
               normalized.get('x-content-type-options') == 'nosniff'
               and normalized.get('referrer-policy') == 'no-referrer'
               and 'no-store' in normalized.get('cache-control', '')
               and (not base.startswith('https:') or 'max-age=' in normalized.get('strict-transport-security', '')),
               {'headers': {key: normalized.get(key) for key in ('x-content-type-options', 'referrer-policy',
                             'cache-control', 'strict-transport-security')},
                'limits': 'Observed response headers only; not a cloud or host configuration audit.'}),
        result('A10', 'injected_application_failure_and_recovery', base,
               fault == 503 and body.strip() == '{"error":"temporarily_unavailable"}' and recovered == 200,
               {'fault_status': fault, 'generic_response': body.strip() == '{"error":"temporarily_unavailable"}',
                'recovered_status': recovered, 'limits': 'Reference application exception; Redis/upstream outage checks are separate.'})
    ]


def tls_checks(url, ca_file):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname:
        raise ValueError('TLS checks require an HTTPS URL')
    host, port = parts.hostname, parts.port or 443
    checks = []

    def connect(context, hostname=host):
        with socket.create_connection((host, port), timeout=10) as connection:
            with context.wrap_socket(connection, server_hostname=hostname) as tls:
                return tls.version()

    for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
        context = ssl.create_default_context(cafile=str(ca_file))
        context.minimum_version = context.maximum_version = version
        try:
            negotiated = connect(context)
            checks.append(result('A04', 'tls_' + version.name, url, True,
                                 {'negotiated': negotiated, 'certificate_and_hostname_validated': True}))
        except (OSError, ValueError) as error:
            checks.append(result('A04', 'tls_' + version.name, url, False, {'error': str(error)}))
    for version in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            context = ssl.create_default_context(cafile=str(ca_file))
            context.minimum_version = context.maximum_version = version
            context.set_ciphers('ALL:@SECLEVEL=0')
        try:
            negotiated = connect(context)
            checks.append(result('A04', 'reject_' + version.name, url, False, {'negotiated': negotiated}))
        except ssl.SSLError as error:
            # Local cipher/protocol limitations cannot prove server rejection.
            rejected = error.reason == 'TLSV1_ALERT_PROTOCOL_VERSION'
            check = result('A04', 'reject_' + version.name, url, rejected, {'ssl_reason': error.reason})
            if not rejected:
                check['status'] = 'not_assessed'
            checks.append(check)
    for name, context, hostname in (
        ('reject_untrusted_certificate', ssl.create_default_context(), host),
        ('reject_wrong_hostname', ssl.create_default_context(cafile=str(ca_file)), '127.0.0.1')):
        try:
            connect(context, hostname)
            checks.append(result('A04', name, url, False, {}))
        except ssl.SSLCertVerificationError as error:
            expected = error.verify_code in (62, 64) if name == 'reject_wrong_hostname' else error.verify_code in (18, 19, 20, 21)
            checks.append(result('A04', name, url, expected, {'verification_code': error.verify_code}))
        except ssl.SSLError as error:
            checks.append(result('A04', name, url, False, {'ssl_reason': error.reason}))
    return checks
