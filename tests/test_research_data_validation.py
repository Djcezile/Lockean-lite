"""Generated fixtures only: no provider data, account access or network clients."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest


def api():
    return (importlib.import_module('lockean_lite.research.data_contracts'),
            importlib.import_module('lockean_lite.research.data_validation'))


def stamp(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def fixture(interval='1m', day='2026-06-01', opening='13:30', closing='13:32'):
    c, _ = api()
    start = stamp(f'{day}T{opening}:00Z')
    end = stamp(f'{day}T{closing}:00Z')
    decision = end + timedelta(minutes=1)
    sessions = [c.Session(day, start, end)]
    calendar = c.Calendar('lite.calendar.v1', 'fixture-XNYS', '1', day, day,
                          'synthetic-approved-schedule', sessions)
    rows = []
    t = start
    while t < end:
        finish = end if interval == '1d' else t + timedelta(minutes=1)
        rows.append(c.Bar(t, finish, finish, decision, Decimal('100'),
                          Decimal('102'), Decimal('99'), Decimal('101'), 5))
        t = finish
    policy = c.Policy('lite.qualification-policy.v1', '1', decision, 120)
    return assemble(tuple(rows), calendar, policy, interval)


def assemble(rows, calendar, policy, interval='1m', **changes):
    c, v = api()
    raw = v.encode_payload(rows)
    span = c.DateRange(calendar.start_date, calendar.end_date)
    manifest = c.Manifest(
        'lite.dataset-manifest.v1', 'fixture-spy', '1', 'fixture', 'synthetic',
        'SPY', 'XNYS', interval, 'unadjusted', span, span, None, None,
        hashlib.sha256(raw).hexdigest(), len(raw), v.dataset_digest(raw),
        c.digest(calendar), c.digest(policy), policy.decision_at,
        'synthetic-revision-1', 'synthetic-availability-evidence')
    manifest = replace(manifest, **changes)
    approval = c.Approval('lite.dataset-approval.v1', 'founder-fixture-approval',
                          c.digest(manifest), 'spy_bar_research',
                          c.digest(calendar), c.digest(policy),
                          'synthetic-no-external-data', False)
    return dict(manifest=manifest, records=rows, payload_bytes=raw,
                approval=approval, calendar=calendar, policy=policy,
                approved_approval_sha256=c.digest(approval))


def qualify(bundle):
    return api()[1].qualify(**bundle)


def assert_reason(bundle, status, reason):
    report = qualify(bundle)
    assert report.status == status
    assert reason in report.reasons
    return report


def repin(bundle, **changes):
    c, _ = api()
    out = dict(bundle, **changes)
    out['approval'] = replace(out['approval'],
                              manifest_sha256=c.digest(out['manifest']),
                              calendar_sha256=c.digest(out['calendar']),
                              policy_sha256=c.digest(out['policy']))
    out['approved_approval_sha256'] = c.digest(out['approval'])
    return out


@pytest.mark.parametrize('interval', ['1m', '1d'])
def test_valid_manifest_and_report_are_immutable(interval):
    c, _ = api()
    b = fixture(interval)
    r = qualify(b)
    assert r.status == 'QUALIFIED'
    assert r.reasons == ('all_required_checks_satisfied',)
    assert r.options_status == 'UNKNOWN'
    assert r.evidence_kind == 'SYNTHETIC_ONLY'
    assert r.expected_count == r.observed_count == (2 if interval == '1m' else 1)
    for obj, field in ((b['manifest'], 'dataset_id'), (r, 'status')):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, 'changed')
    sessions = list(b['calendar'].sessions)
    calendar = replace(b['calendar'], sessions=sessions)
    sessions.clear()
    assert len(calendar.sessions) == 1
    assert type(calendar.sessions) is tuple
    assert c.digest(calendar) == c.digest(b['calendar'])


@pytest.mark.parametrize('field,value', [('payload_sha256', '0'*64),
                                       ('payload_length', 1),
                                       ('dataset_sha256', '0'*64)])
def test_payload_integrity(field, value):
    b = fixture()
    b = repin(b, manifest=replace(b['manifest'], **{field: value}))
    assert_reason(b, 'REJECTED', 'payload_integrity_mismatch')


def test_payload_record_binding():
    b = fixture()
    b['records'] = (replace(b['records'][0], close=Decimal('100')), b['records'][1])
    assert_reason(b, 'REJECTED', 'payload_record_mismatch')


@pytest.mark.parametrize('mode', ['missing', 'untrusted', 'changed', 'wrong-purpose'])
def test_independent_approval(mode):
    c, _ = api()
    b = fixture()
    if mode == 'missing': b['approved_approval_sha256'] = None
    if mode == 'untrusted': b['approved_approval_sha256'] = '0'*64
    if mode == 'changed': b['approval'] = replace(b['approval'], approval_id='other')
    if mode == 'wrong-purpose':
        b['approval'] = replace(b['approval'], purpose='options_profitability')
        b['approved_approval_sha256'] = c.digest(b['approval'])
    assert_reason(b, 'REJECTED', 'approval_not_verified')


@pytest.mark.parametrize('change', [dict(open=Decimal('-1')), dict(high=Decimal('99')),
                                    dict(low=Decimal('103')), dict(volume=-1),
                                    dict(close=Decimal('NaN'))])
def test_invalid_ohlcv(change):
    b = fixture()
    row = replace(b['records'][0], **change)
    # Payload encoding must fail closed for values outside its numeric contract.
    if not row.close.is_finite():
        with pytest.raises(ValueError): api()[1].encode_payload((row,))
        return
    b = assemble((row, b['records'][1]), b['calendar'], b['policy'])
    assert_reason(b, 'REJECTED', 'invalid_observation')


@pytest.mark.parametrize('mode', ['duplicate', 'unordered', 'outside'])
def test_order_and_scope(mode):
    b = fixture()
    rows = b['records']
    if mode == 'duplicate': rows = (rows[0], rows[0], rows[1])
    if mode == 'unordered': rows = tuple(reversed(rows))
    if mode == 'outside':
        rows = (replace(rows[0], event_start=rows[0].event_start-timedelta(minutes=1),
                        event_end=rows[0].event_start),) + rows
    b = assemble(rows, b['calendar'], b['policy'])
    reason = 'observation_outside_scope' if mode == 'outside' else 'duplicate_or_unordered_observation'
    assert_reason(b, 'REJECTED', reason)


@pytest.mark.parametrize('interval', ['1m', '1d'])
@pytest.mark.parametrize('empty', [False, True])
def test_missing_required_intervals(interval, empty):
    b = fixture(interval)
    rows = () if empty else b['records'][:-1]
    b = assemble(rows, b['calendar'], b['policy'], interval)
    r = assert_reason(b, 'UNKNOWN', 'required_coverage_incomplete')
    assert len(r.missing_intervals) == r.expected_count-len(rows)
    assert r.observed_count == len(rows)


def test_early_close_uses_approved_schedule_not_390_minutes():
    b = fixture(day='2026-11-27')  # Dates in holdout must reject even a valid schedule.
    assert_reason(b, 'REJECTED', 'protected_holdout_overlap')
    b = fixture(day='2025-11-28', opening='14:30', closing='18:00')
    assert qualify(b).expected_count == 210
    assert qualify(b).status == 'QUALIFIED'


@pytest.mark.parametrize('mode', ['missing-time', 'missing-evidence'])
def test_availability_unknown(mode):
    b = fixture()
    if mode == 'missing-time':
        b = assemble((replace(b['records'][0], available_at=None), b['records'][1]),
                     b['calendar'], b['policy'])
    else:
        b = repin(b, manifest=replace(b['manifest'], availability_reference=None))
    assert_reason(b, 'UNKNOWN', 'point_in_time_availability_unverified')


@pytest.mark.parametrize('mode', ['before-end', 'after-capture', 'after-decision', 'capture-mismatch'])
def test_contradictory_timestamps(mode):
    b = fixture()
    row = b['records'][0]
    if mode == 'before-end': row = replace(row, available_at=row.event_start)
    if mode == 'after-capture': row = replace(row, available_at=row.captured_at+timedelta(seconds=1))
    if mode == 'after-decision':
        row = replace(row, available_at=b['policy'].decision_at+timedelta(seconds=1),
                      captured_at=b['policy'].decision_at+timedelta(seconds=2))
    if mode == 'capture-mismatch': row = replace(row, captured_at=row.event_end)
    b = assemble((row, b['records'][1]), b['calendar'], b['policy'])
    assert_reason(b, 'REJECTED', 'invalid_observation')


def test_staleness_is_versioned_and_configurable():
    b = fixture()
    b = repin(b, policy=replace(b['policy'], max_age_seconds=59))
    # Manifest binds the policy separately; stale identity is not accepted.
    assert_reason(b, 'REJECTED', 'identity_mismatch')
    b = assemble(b['records'], b['calendar'], b['policy'])
    assert_reason(b, 'UNKNOWN', 'observation_stale')
    assert qualify(fixture()).status == 'QUALIFIED'


@pytest.mark.parametrize('field', ['requested', 'coverage', 'warmup', 'measurement'])
def test_holdout_enclosing_ranges(field):
    c, _ = api()
    b = fixture()
    span = c.DateRange('2026-10-19', '2027-01-04')
    b = repin(b, manifest=replace(b['manifest'], **{field: span}))
    assert_reason(b, 'REJECTED', 'protected_holdout_overlap')


@pytest.mark.parametrize('day', ['2026-10-20', '2026-11-02', '2026-12-31'])
def test_holdout_observation_dates(day):
    assert_reason(fixture(day=day), 'REJECTED', 'protected_holdout_overlap')


def test_enclosing_observation_interval_rejected_before_scope_error():
    b = fixture()
    row = replace(b['records'][0], event_start=stamp('2026-10-19T14:00:00Z'),
                  event_end=stamp('2027-01-04T14:00:00Z'),
                  available_at=stamp('2027-01-04T14:00:00Z'),
                  captured_at=stamp('2027-01-04T14:01:00Z'))
    b = assemble((row,), b['calendar'], b['policy'])
    assert_reason(b, 'REJECTED', 'protected_holdout_overlap')


@pytest.mark.parametrize('start,end,protected', [
    ('2026-10-20T03:58:00Z', '2026-10-20T03:59:00Z', False),
    ('2026-10-20T03:59:00Z', '2026-10-20T04:00:00Z', True),
    ('2027-01-01T04:59:00Z', '2027-01-01T05:00:00Z', True),
    ('2027-01-01T05:00:00Z', '2027-01-01T05:01:00Z', False),
])
def test_holdout_new_york_boundaries(start, end, protected):
    b = fixture()
    t, finish = stamp(start), stamp(end)
    row = replace(b['records'][0], event_start=t, event_end=finish,
                  available_at=finish, captured_at=finish)
    b = assemble((row,), b['calendar'], b['policy'])
    r = qualify(b)
    assert ('protected_holdout_overlap' in r.reasons) is protected
    assert r.status == 'REJECTED'  # Nonprotected rows still lie outside the approved session.


@pytest.mark.parametrize('day,opening,closing', [('2026-03-06','14:30','14:32'),
                                               ('2026-03-09','13:30','13:32')])
def test_dst_uses_explicit_utc_schedule(day, opening, closing):
    assert qualify(fixture(day=day, opening=opening, closing=closing)).status == 'QUALIFIED'


def test_options_unknown_is_not_profitability_or_global_qualification():
    c, _ = api()
    b = fixture()
    b['approval'] = replace(b['approval'], require_options=True)
    b['approved_approval_sha256'] = c.digest(b['approval'])
    r = assert_reason(b, 'UNKNOWN', 'historical_options_evidence_unavailable')
    assert r.options_status == 'UNKNOWN'


@pytest.mark.parametrize('field,reason', [('source_reference','calendar_unverified'),
                                        ('license_reference','license_unverified')])
def test_missing_external_evidence(field, reason):
    c, _ = api()
    b = fixture()
    if field == 'source_reference':
        b = assemble(b['records'], replace(b['calendar'], source_reference=None), b['policy'])
    else:
        b['approval'] = replace(b['approval'], license_reference=None)
        b['approved_approval_sha256'] = c.digest(b['approval'])
    assert_reason(b, 'UNKNOWN', reason)


def test_canonical_determinism_typed_values_and_context_independence():
    c, _ = api()
    b = fixture()
    before = c.canonical(qualify(b))
    with localcontext() as ctx:
        ctx.prec = 2
        assert c.canonical(qualify(b)) == before
    assert c.canonical({'a': 1, 'b': 2}) == c.canonical({'b': 2, 'a': 1})
    assert c.canonical(Decimal('1')) != c.canonical('1')
    assert c.canonical(True) != c.canonical(1)
    assert c.canonical(Decimal('1.00')) == c.canonical(Decimal('1'))
    assert hashlib.sha256(before).hexdigest() == c.digest(qualify(b))


@pytest.mark.parametrize('change', [dict(payload_length=True), dict(payload_length='1'),
                                    dict(dataset_version=Decimal('1')),
                                    dict(symbol='QQQ'), dict(interval='5m'),
                                    dict(provider='alpaca'), dict(schema='future')])
def test_strict_manifest_field_types_and_supported_scope(change):
    b = fixture()
    with pytest.raises(ValueError): replace(b['manifest'], **change)


@pytest.mark.parametrize('mode', ['duplicate-key', 'unknown-field', 'numeric-price',
                                 'unknown-schema', 'malformed-json'])
def test_payload_decode_fails_closed(mode):
    c, v = api()
    b = fixture()
    body = json.loads(b['payload_bytes'])
    if mode == 'duplicate-key': raw = b'{"schema":"a","schema":"b","records":[]}'
    elif mode == 'malformed-json': raw = b'not-json SECRET_DO_NOT_PRINT'
    else:
        if mode == 'unknown-field': body['secret'] = 'SECRET_DO_NOT_PRINT'
        if mode == 'numeric-price': body['records'][0]['open'] = 100
        if mode == 'unknown-schema': body['schema'] = 'future'
        raw = json.dumps(body).encode()
    m = replace(b['manifest'], payload_length=len(raw), payload_sha256=hashlib.sha256(raw).hexdigest(),
                dataset_sha256=v.dataset_digest(raw))
    b = repin(b, manifest=m, payload_bytes=raw)
    r = assert_reason(b, 'REJECTED', 'invalid_payload')
    assert b'SECRET_DO_NOT_PRINT' not in c.canonical(r)


def test_unsupported_policy_calendar_and_approval_versions():
    b = fixture()
    for obj in ('policy', 'calendar', 'approval'):
        with pytest.raises(ValueError): replace(b[obj], schema='future')


def test_sources_have_no_network_credentials_broker_or_filesystem_dependencies(monkeypatch):
    import socket
    c, v = api()
    def forbidden(*args, **kwargs): raise AssertionError('network forbidden')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    b = fixture()
    assert qualify(b).status == 'QUALIFIED'
    for module in (c, v):
        tree = ast.parse(inspect.getsource(module))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(x.name for x in node.names)
            if isinstance(node, ast.ImportFrom): imports.append(node.module or '')
        assert set(imports) <= {'dataclasses','datetime','decimal','hashlib','json','re',
                               'data_contracts','validation'}
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id in ('open', 'eval', 'exec') for n in ast.walk(tree))


def test_m0_example_digest_unchanged():
    from lockean_lite.research.reporting import digest
    root = Path(__file__).resolve().parents[1]
    doc = (root/'docs/research/LITE-RESEARCH-001.md').read_text()
    import re
    body = json.loads(re.search(r'```json\n(.*?)\n```', doc, re.S).group(1))
    assert digest(body) == 'bf700dc17c42ba7bbcb02695b8c129182b9ac24ad692d1b70a6062c006dacec4'


def test_no_expected_sessions_never_qualifies_an_empty_dataset():
    b = fixture()
    b = assemble((), replace(b['calendar'], sessions=[]), b['policy'])
    assert_reason(b, 'UNKNOWN', 'no_expected_sessions')


def test_missing_approval_object_is_an_approval_failure():
    b = fixture()
    b['approval'] = None
    assert_reason(b, 'REJECTED', 'approval_not_verified')


def test_daily_multi_session_missing_session_is_reported():
    c, _ = api()
    b = fixture('1d')
    s = b['calendar'].sessions[0]
    second = c.Session('2026-06-02', s.opens_at+timedelta(days=1), s.closes_at+timedelta(days=1))
    calendar = replace(b['calendar'], end_date='2026-06-02', sessions=[s, second])
    policy = replace(b['policy'], decision_at=b['policy'].decision_at+timedelta(days=1),
                     max_age_seconds=90000)
    row = replace(b['records'][0], captured_at=policy.decision_at)
    r = assert_reason(assemble((row,), calendar, policy, '1d'), 'UNKNOWN', 'required_coverage_incomplete')
    assert r.expected_count == 2 and r.observed_count == 1
    assert r.missing_intervals == ((second.opens_at, second.closes_at),)


def test_capture_in_holdout_is_not_protected_market_evidence():
    b = fixture()
    capture = stamp('2026-10-30T14:00:00Z')
    rows = tuple(replace(row, captured_at=capture) for row in b['records'])
    b = assemble(rows, b['calendar'], b['policy'], capture_at=capture)
    assert qualify(b).status == 'QUALIFIED'


@pytest.mark.parametrize('value', [True, 1.0, '60', -1])
def test_staleness_policy_rejects_wrong_types_and_negative_limits(value):
    b = fixture()
    with pytest.raises(ValueError): replace(b['policy'], max_age_seconds=value)


@pytest.mark.parametrize('field', ['decision_at', 'available_at'])
def test_protected_decision_and_availability(field):
    b = fixture()
    t = stamp('2026-10-20T14:00:00Z')
    if field == 'decision_at':
        b = assemble(b['records'], b['calendar'], replace(b['policy'], decision_at=t))
    else:
        b = assemble((replace(b['records'][0], available_at=t), b['records'][1]),
                     b['calendar'], b['policy'])
    assert_reason(b, 'REJECTED', 'protected_holdout_overlap')


def test_duplicate_calendar_sessions_fail_closed():
    b = fixture()
    calendar = replace(b['calendar'], sessions=b['calendar'].sessions*2)
    b = assemble(b['records'], calendar, b['policy'])
    assert_reason(b, 'REJECTED', 'invalid_calendar')


def test_rejection_wins_over_unknown_evidence():
    b = fixture()
    b = assemble((replace(b['records'][0], available_at=None, high=Decimal('1')),
                  b['records'][1]), b['calendar'], b['policy'])
    assert_reason(b, 'REJECTED', 'invalid_observation')


def test_never_mutates_supplied_bundle():
    c, _ = api()
    b = fixture()
    before = c.canonical({k: v for k, v in b.items() if k != 'payload_bytes'})
    raw = b['payload_bytes']
    qualify(b)
    assert c.canonical({k: v for k, v in b.items() if k != 'payload_bytes'}) == before
    assert b['payload_bytes'] is raw
