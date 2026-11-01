"""Pure, deterministic qualification of bounded synthetic SPY payloads only."""
from dataclasses import fields
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
import re

from .data_contracts import (Approval, Bar, Calendar, DateRange, Manifest, Policy,
                             QualificationReport, day, decimal_text, digest, sha)
from .validation import NY, utc, validate_partition

PAYLOAD_SCHEMA = 'lite.synthetic-spy-ohlcv.v1'
MAX_RECORDS = 100000
MAX_BYTES = 64*1024*1024


def _timestamp(value):
    if value is None:
        return None
    utc(value)
    return value.isoformat().replace('+00:00', 'Z')


def encode_payload(records):
    """Explicit synthetic wire format; Decimal prices are schema-typed strings."""
    if type(records) is not tuple or len(records) > MAX_RECORDS:
        raise ValueError('invalid_payload')
    rows = []
    for row in records:
        if type(row) is not Bar:
            raise ValueError('invalid_payload')
        rows.append({f.name: (decimal_text(getattr(row, f.name)) if f.name in
                              ('open', 'high', 'low', 'close') else
                              _timestamp(getattr(row, f.name)) if f.name in
                              ('event_start', 'event_end', 'available_at', 'captured_at')
                              else row.volume) for f in fields(Bar)})
    raw = json.dumps({'schema': PAYLOAD_SCHEMA, 'records': rows}, sort_keys=True,
                     separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('invalid_payload')
    return raw


def dataset_digest(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError('invalid_payload')
    return digest({'payload_schema': PAYLOAD_SCHEMA, 'payload_sha256': hashlib.sha256(raw).hexdigest(),
                   'payload_length': len(raw)})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('invalid_payload')
        result[key] = value
    return result


def _parse_time(value):
    if type(value) is not str or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError('invalid_payload')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    utc(result)
    return result


def _decode(raw):
    body = json.loads(raw, object_pairs_hook=_pairs)
    if (type(body) is not dict or set(body) != {'schema', 'records'}
            or body['schema'] != PAYLOAD_SCHEMA or type(body['records']) is not list
            or len(body['records']) > MAX_RECORDS):
        raise ValueError('invalid_payload')
    rows = []
    keys = {f.name for f in fields(Bar)}
    for item in body['records']:
        if type(item) is not dict or set(item) != keys:
            raise ValueError('invalid_payload')
        values = {}
        for key, value in item.items():
            if key in ('open', 'high', 'low', 'close'):
                if type(value) is not str or not re.fullmatch(r'-?\d{1,19}(?:\.\d{1,12})?', value):
                    raise ValueError('invalid_payload')
                values[key] = Decimal(value)
                decimal_text(values[key])
            elif key == 'volume':
                if type(value) is not int:
                    raise ValueError('invalid_payload')
                values[key] = value
            else:
                values[key] = None if key == 'available_at' and value is None else _parse_time(value)
        rows.append(Bar(**values))
    return tuple(rows)


class _Reject(ValueError):
    pass


def _check(condition, reason):
    if not condition:
        raise _Reject(reason)


def _protect_dates(start, end):
    try:
        validate_partition(start, end, 'development')
    except ValueError:
        raise _Reject('protected_holdout_overlap') from None


def _protect_time(start, end):
    _protect_dates(start.astimezone(NY).date().isoformat(),
                   end.astimezone(NY).date().isoformat())


def _inside(inner, outer):
    return outer.start <= inner.start <= inner.end <= outer.end


def _expected(calendar, manifest):
    _check(calendar.start_date <= manifest.requested.start
           and manifest.requested.end <= calendar.end_date, 'invalid_calendar')
    expected = []
    previous = None
    for session in calendar.sessions:
        _check(calendar.start_date <= session.session_date <= calendar.end_date,
               'invalid_calendar')
        _check(previous is None or previous < session.session_date, 'invalid_calendar')
        previous = session.session_date
        for t in (session.opens_at, session.closes_at):
            _check(t.astimezone(NY).date().isoformat() == session.session_date
                   and t.second == 0 and t.microsecond == 0, 'invalid_calendar')
        if not manifest.requested.start <= session.session_date <= manifest.requested.end:
            continue
        t = session.opens_at
        while t < session.closes_at:
            end = session.closes_at if manifest.interval == '1d' else t+timedelta(minutes=1)
            expected.append((t, end))
            _check(len(expected) <= MAX_RECORDS, 'qualification_resource_limit')
            t = end
    return tuple(expected)


def qualify(*, manifest, records, payload_bytes, approval, calendar, policy,
            approved_approval_sha256):
    """Return UNKNOWN for missing evidence, REJECTED for violations; never execute."""
    valid_types = (type(manifest) is Manifest and type(approval) is Approval
                   and type(calendar) is Calendar and type(policy) is Policy)
    expected = ()
    missing = ()
    observed_count = 0

    def report(status, reasons):
        return QualificationReport(
            'lite.research.data-qualification.v1', status, tuple(sorted(set(reasons))),
            'SYNTHETIC_ONLY', 'spy_bar_research', digest(manifest) if valid_types else None,
            digest(approval) if valid_types else None,
            manifest.dataset_sha256 if valid_types else None,
            digest(calendar) if valid_types else None, digest(policy) if valid_types else None,
            manifest.requested if valid_types else None, manifest.coverage if valid_types else None,
            len(expected), observed_count, missing)

    try:
        _check(type(approval) is Approval, 'approval_not_verified')
        _check(valid_types, 'invalid_manifest')
        _check(sha(approved_approval_sha256) and digest(approval) == approved_approval_sha256
               and approval.purpose == 'spy_bar_research', 'approval_not_verified')
        _check(approval.manifest_sha256 == digest(manifest), 'approval_not_verified')
        # Exclude protected ranges before narrowing scope or calculating coverage.
        for span in (manifest.requested, manifest.coverage, manifest.warmup, manifest.measurement):
            if span is not None:
                _protect_dates(span.start, span.end)
        _protect_dates(calendar.start_date, calendar.end_date)
        _protect_time(policy.decision_at, policy.decision_at)
        for session in calendar.sessions:
            _protect_time(session.opens_at, session.closes_at)
        _check(manifest.calendar_sha256 == approval.calendar_sha256 == digest(calendar)
               and manifest.policy_sha256 == approval.policy_sha256 == digest(policy), 'identity_mismatch')
        _check(type(payload_bytes) is bytes and len(payload_bytes) <= MAX_BYTES,
               'invalid_payload')
        _check(len(payload_bytes) == manifest.payload_length
               and hashlib.sha256(payload_bytes).hexdigest() == manifest.payload_sha256
               and dataset_digest(payload_bytes) == manifest.dataset_sha256,
               'payload_integrity_mismatch')
        try:
            decoded = _decode(payload_bytes)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise _Reject('invalid_payload') from None
        # Check the actual bytes' intervals as well as their normalized representation.
        for row in decoded:
            _protect_time(row.event_start, row.event_end)
            if row.available_at is not None:
                _protect_time(row.available_at, row.available_at)
        _check(type(records) is tuple and all(type(row) is Bar for row in records)
               and records == decoded, 'payload_record_mismatch')
        observed_count = len(decoded)
        _check(all(_inside(span, manifest.requested) for span in
                   (manifest.coverage, manifest.warmup, manifest.measurement) if span is not None),
               'unauthorized_dataset_scope')
        expected = _expected(calendar, manifest)
        expected_set = set(expected)
        seen = set()
        previous = None
        unknown = []
        if not expected:
            unknown.append('no_expected_sessions')
        for row in decoded:
            try:
                prices = tuple(Decimal(decimal_text(v)) for v in
                               (row.open, row.high, row.low, row.close))
            except ValueError:
                raise _Reject('invalid_observation') from None
            _check(all(v > 0 for v in prices) and row.low <= min(prices)
                   and row.high >= max(prices) and row.volume >= 0,
                   'invalid_observation')
            _check(row.event_start < row.event_end and row.captured_at == manifest.capture_at
                   and row.event_end <= row.captured_at, 'invalid_observation')
            if row.available_at is None:
                unknown.append('point_in_time_availability_unverified')
            else:
                _check(row.event_end <= row.available_at <= row.captured_at
                       and row.available_at <= policy.decision_at, 'invalid_observation')
            _check(row.event_end <= policy.decision_at, 'invalid_observation')
            pair = (row.event_start, row.event_end)
            _check(pair in expected_set and
                   manifest.coverage.start <= row.event_start.astimezone(NY).date().isoformat()
                   <= manifest.coverage.end, 'observation_outside_scope')
            _check(pair not in seen and (previous is None or previous < pair),
                   'duplicate_or_unordered_observation')
            seen.add(pair)
            previous = pair
        missing = tuple(pair for pair in expected if pair not in seen)
        if missing:
            unknown.append('required_coverage_incomplete')
        if not calendar.source_reference:
            unknown.append('calendar_unverified')
        if not manifest.availability_reference:
            unknown.append('point_in_time_availability_unverified')
        if not manifest.source_revision:
            unknown.append('source_revision_unverified')
        if not approval.license_reference:
            unknown.append('license_unverified')
        if approval.require_options:
            unknown.append('historical_options_evidence_unavailable')
        if decoded and (policy.decision_at-decoded[-1].event_end).total_seconds() > policy.max_age_seconds:
            unknown.append('observation_stale')
        return report('UNKNOWN', unknown) if unknown else report('QUALIFIED', ('all_required_checks_satisfied',))
    except _Reject as error:
        return report('REJECTED', (str(error),))
