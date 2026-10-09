"""Authorization and authentication outcomes in an isolated reference app."""
import secrets

from run import Client, result


def application_checks(base, token, ca_file=None):
    client = Client(base, token, ca_file)
    scope = base + ' (reference application controls; not AIWAF implementations)'
    checks, created = [], []

    def fresh():
        password, other = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        status, data = client.post('/runs', {'password': password, 'other_password': other})
        if status != 201 or 'object_id' not in data:
            raise ValueError('new fixture controls not reachable')
        created.append(data['run'])
        return data, password, other

    def login(run, password, actor='owner', **values):
        return client.post('/login', {'run': run, 'password': password, 'actor': actor, **values})

    def headers(session, csrf=True):
        return {'X-Session-Token': session.get('session', ''),
                **({'X-CSRF-Token': session.get('csrf', '')} if csrf else {})}

    def post(path, setup, session=None, **body):
        return client.post(path, {'run': setup['run'], 'object_id': setup['object_id'], **body},
                           headers=headers(session) if session else {})

    def add(category, name, passed, **evidence):
        checks.append(result(category, name, scope, bool(passed), evidence))

    try:
        setup, password, other_password = fresh()
        run = setup['run']
        owner_status, owner = login(run, password)
        other_status, other = login(run, other_password, 'other')
        if owner_status != 200 or other_status != 200 or not owner.get('session') or not other.get('session'):
            raise ValueError('ordinary login controls failed')
        own_status, original = post('/object/read', setup, owner)
        other_read, leaked = post('/object/read', setup, other)
        anonymous, _ = post('/object/read', setup)
        other_write, _ = post('/object/write', setup, other, value='unauthorized-change')
        _, unchanged = post('/object/read', setup, owner)
        add('A01', 'cross_user_object_access', own_status == 200 and other_read == 403
            and anonymous == 401 and other_write == 403 and original == unchanged
            and 'value' not in leaked, statuses=[own_status, other_read, anonymous, other_write],
            unauthorized_write_has_no_side_effect=original == unchanged)

        admin, _ = client.post('/admin', {'run': run, 'role': 'admin'},
                               headers={**headers(owner), 'X-User-Role': 'admin', 'X-User-ID': 'administrator'})
        mass, _ = post('/object/write', setup, owner, value='escalated', owner='other', role='admin')
        _, preserved = post('/object/read', setup, owner)
        add('A01', 'role_spoofing_and_mass_assignment', admin == 403 and mass == 422 and preserved == original,
            admin_status=admin, protected_fields_status=mass, object_unchanged=preserved == original)

        denied, _ = client.post('/object/write', {'run': run, 'object_id': setup['object_id'], 'value': 'csrf-change'},
                                headers=headers(owner, csrf=False))
        _, unchanged = post('/object/read', setup, owner)
        accepted, _ = post('/object/write', setup, owner, value='authorized-change')
        _, changed = post('/object/read', setup, owner)
        add('A01', 'csrf_write_protection', denied == 403 and unchanged == original and accepted == 200
            and changed.get('value') == 'authorized-change', statuses=[denied, accepted],
            rejected_write_has_no_side_effect=unchanged == original)

        fixed = secrets.token_urlsafe(24)
        status, session = login(run, password, session=fixed)
        check_status, _ = post('/session/check', setup, session)
        logout, _ = post('/logout', setup, session)
        revoked, _ = post('/session/check', setup, session)
        _, expiring = login(run, password)
        post('/session/expire', setup, expiring)
        expired, _ = post('/session/check', setup, expiring)
        second, _, _ = fresh()
        cross_run, _ = post('/session/check', second, owner)
        add('A07', 'session_rotation_revocation_expiry', status == 200 and session.get('session') != fixed
            and check_status == 200 and logout == 200 and revoked == expired == cross_run == 401,
            rotated=session.get('session') != fixed, statuses=[check_status, logout, revoked, expired, cross_run])

        setup, password, _ = fresh()
        run = setup['run']
        _, prior = login(run, password)
        new_password = secrets.token_urlsafe(24)
        _, reset = post('/reset/request', setup, actor='owner')
        reset_token = reset.get('reset_token', '')
        wrong_user, _ = post('/reset/confirm', setup, actor='other', reset_token=reset_token, password=new_password)
        forged, _ = post('/reset/confirm', setup, reset_token='forged-token', password=new_password)
        post('/reset/expire', setup, reset_token=reset_token)
        expired_reset, _ = post('/reset/confirm', setup, reset_token=reset_token, password=new_password)
        _, reset = post('/reset/request', setup)
        reset_token = reset.get('reset_token', '')
        changed_status, _ = post('/reset/confirm', setup, reset_token=reset_token, password=new_password)
        replay, _ = post('/reset/confirm', setup, reset_token=reset_token, password=secrets.token_urlsafe(24))
        revoked, _ = post('/session/check', setup, prior)
        old_status, _ = login(run, password)
        new_status, _ = login(run, new_password)
        add('A07', 'reset_binding_expiry_single_use_and_revocation', wrong_user == forged == expired_reset == replay == 403
            and changed_status == new_status == 200 and revoked == old_status == 401,
            statuses=[wrong_user, forged, expired_reset, changed_status, replay, revoked, old_status, new_status],
            limits='Reset delivery is a test-only authenticated control; no email provider is tested.')

        setup, password, _ = fresh()
        post('/mfa/enable', setup)
        status, challenge = login(setup['run'], password)
        key = challenge.get('challenge', '')
        _, delivery = post('/mfa/deliver', setup, challenge=key)
        wrong, wrong_body = post('/mfa/verify', setup, challenge=key, code='wrong-code')
        other_actor, _ = post('/mfa/verify', setup, challenge=key, code=delivery.get('code', ''), actor='other')
        good, verified = post('/mfa/verify', setup, challenge=key, code=delivery.get('code', ''))
        replay, _ = post('/mfa/verify', setup, challenge=key, code=delivery.get('code', ''))
        add('A07', 'mfa_required_bound_and_single_use', status == 202 and not challenge.get('session')
            and wrong == other_actor == replay == 401 and not wrong_body.get('session')
            and good == 200 and bool(verified.get('session')), statuses=[status, wrong, other_actor, good, replay],
            limits='Reference app one-time challenge; production MFA providers and enrollment recovery are not tested.')

        setup, _, _ = fresh()
        body = {'run': setup['run'], 'quantity': 1, 'idempotency_key': 'same-key'}
        first, _ = client.post('/order', body)
        conflict, _ = client.post('/order', {**body, 'quantity': 2})
        _, snapshot = post('/snapshot', setup)
        add('A06', 'idempotency_key_payload_conflict', first == 201 and conflict == 409
            and snapshot['stock'] == 4 and snapshot['orders'] == 1,
            statuses=[first, conflict], remaining=snapshot['stock'], orders=snapshot['orders'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        checks.append({'category': 'fixture', 'check': 'extended_controls_reachable', 'scope': scope,
                       'status': 'error', 'evidence': str(error)})
    finally:
        for run in created:
            try:
                status, body = client.post('/cleanup', {'run': run})
                if status != 200 or body.get('deleted') is not True:
                    raise ValueError('extended fixture cleanup rejected')
            except (OSError, ValueError) as error:
                checks.append({'category': 'fixture', 'check': 'cleanup', 'scope': scope,
                               'status': 'error', 'evidence': str(error)})
    return checks
