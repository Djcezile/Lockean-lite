"""M1 synthetic-only immutable contracts and separate, typed canonical encoding."""
from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re

from .validation import utc


def require(condition, reason='invalid_manifest'):
    if not condition:
        raise ValueError(reason)


def text(value):
    return type(value) is str and 0 < len(value) <= 256


def sha(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def day(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None)
    return date.fromisoformat(value)


def decimal_text(value):
    require(type(value) is Decimal and value.is_finite()
            and value.adjusted() <= 18 and value.as_tuple().exponent >= -12,
            'invalid_decimal')
    result = format(value, 'f')
    return (result.rstrip('0').rstrip('.') if '.' in result else result) if value else '0'


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str

    def __post_init__(self):
        require(day(self.start) <= day(self.end))


@dataclass(frozen=True)
class Session:
    session_date: str
    opens_at: datetime
    closes_at: datetime

    def __post_init__(self):
        day(self.session_date)
        utc(self.opens_at)
        utc(self.closes_at)
        require(self.opens_at < self.closes_at)


@dataclass(frozen=True)
class Calendar:
    schema: str
    calendar_id: str
    version: str
    start_date: str
    end_date: str
    source_reference: str | None
    sessions: tuple[Session, ...]

    def __post_init__(self):
        require(self.schema == 'lite.calendar.v1' and type(self.schema) is str)
        require(text(self.calendar_id) and text(self.version))
        require(day(self.start_date) <= day(self.end_date))
        require(self.source_reference is None or text(self.source_reference))
        require(type(self.sessions) in (tuple, list))
        require(all(type(s) is Session for s in self.sessions))
        require(len(self.sessions) <= 1000)
        object.__setattr__(self, 'sessions', tuple(self.sessions))


@dataclass(frozen=True)
class Bar:
    event_start: datetime
    event_end: datetime
    available_at: datetime | None
    captured_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self):
        for value in (self.event_start, self.event_end, self.captured_at):
            utc(value)
        if self.available_at is not None:
            utc(self.available_at)
        require(all(type(v) is Decimal for v in (self.open, self.high, self.low, self.close)),
                'invalid_observation')
        require(type(self.volume) is int, 'invalid_observation')


@dataclass(frozen=True)
class Policy:
    schema: str
    version: str
    decision_at: datetime
    max_age_seconds: int

    def __post_init__(self):
        require(type(self.schema) is str and self.schema == 'lite.qualification-policy.v1')
        require(text(self.version))
        utc(self.decision_at)
        require(type(self.max_age_seconds) is int and 0 <= self.max_age_seconds <= 31536000)


@dataclass(frozen=True)
class Manifest:
    schema: str
    dataset_id: str
    dataset_version: str
    provider: str
    feed: str
    symbol: str
    market: str
    interval: str
    adjustment: str
    requested: DateRange
    coverage: DateRange
    warmup: DateRange | None
    measurement: DateRange | None
    payload_sha256: str
    payload_length: int
    dataset_sha256: str
    calendar_sha256: str
    policy_sha256: str
    capture_at: datetime
    source_revision: str | None
    availability_reference: str | None

    def __post_init__(self):
        require(type(self.schema) is str and self.schema == 'lite.dataset-manifest.v1')
        require(text(self.dataset_id) and text(self.dataset_version))
        for value, allowed in ((self.provider, ('fixture',)), (self.feed, ('synthetic',)),
                               (self.symbol, ('SPY',)), (self.market, ('XNYS',)),
                               (self.interval, ('1m', '1d')), (self.adjustment, ('unadjusted',))):
            require(type(value) is str and value in allowed)
        require(type(self.requested) is DateRange and type(self.coverage) is DateRange)
        require(all(v is None or type(v) is DateRange for v in (self.warmup, self.measurement)))
        require(all(sha(v) for v in (self.payload_sha256, self.dataset_sha256,
                                    self.calendar_sha256, self.policy_sha256)))
        require(type(self.payload_length) is int and 0 <= self.payload_length <= 64*1024*1024)
        utc(self.capture_at)
        require(all(v is None or text(v) for v in (self.source_revision, self.availability_reference)))


@dataclass(frozen=True)
class Approval:
    schema: str
    approval_id: str
    manifest_sha256: str
    purpose: str
    calendar_sha256: str
    policy_sha256: str
    license_reference: str | None
    require_options: bool

    def __post_init__(self):
        require(type(self.schema) is str and self.schema == 'lite.dataset-approval.v1')
        require(text(self.approval_id) and text(self.purpose))
        require(all(sha(v) for v in (self.manifest_sha256, self.calendar_sha256, self.policy_sha256)))
        require(self.license_reference is None or text(self.license_reference))
        require(type(self.require_options) is bool)


@dataclass(frozen=True)
class QualificationReport:
    schema: str
    status: str
    reasons: tuple[str, ...]
    evidence_kind: str
    purpose: str
    manifest_sha256: str | None
    approval_sha256: str | None
    dataset_sha256: str | None
    calendar_sha256: str | None
    policy_sha256: str | None
    requested: DateRange | None
    coverage: DateRange | None
    expected_count: int
    observed_count: int
    missing_intervals: tuple[tuple[datetime, datetime], ...]
    options_status: str = 'UNKNOWN'
    limitations: tuple[str, ...] = ('SYNTHETIC_ONLY', 'NO_PROVIDER_AUTHENTICATION',
                                    'NO_OPTIONS_PROFITABILITY', 'NO_EXECUTION_AUTHORITY')


def _typed(value):
    """Type tags also wrap containers, so user data cannot impersonate a Decimal tag."""
    if type(value) in (DateRange, Session, Calendar, Bar, Policy, Manifest, Approval,
                       QualificationReport):
        return [type(value).__name__, [[f.name, _typed(getattr(value, f.name))] for f in fields(value)]]
    if value is None:
        return ['null']
    if type(value) is bool:
        return ['bool', value]
    if type(value) is int:
        return ['int', str(value)]
    if type(value) is str:
        return ['str', value]
    if type(value) is Decimal:
        return ['decimal', decimal_text(value)]
    if type(value) is datetime:
        utc(value)
        return ['utc', value.isoformat().replace('+00:00', 'Z')]
    if type(value) in (tuple, list):
        return [type(value).__name__, [_typed(v) for v in value]]
    if type(value) is dict:
        require(all(type(k) is str for k in value), 'unsupported_serialization')
        return ['dict', [[k, _typed(value[k])] for k in sorted(value)]]
    raise ValueError('unsupported_serialization')


def canonical(value):
    return json.dumps(['lite.typed-json.v1', _typed(value)], separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
