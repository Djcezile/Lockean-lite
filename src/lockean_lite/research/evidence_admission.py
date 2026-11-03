"""Offline synthetic metadata admission; the caller must control the trust anchor."""
from dataclasses import dataclass, fields
from datetime import datetime
import re

from .data_contracts import DateRange, canonical, digest
from .validation import NY, utc, validate_partition

KINDS = ('provenance', 'availability', 'licensing', 'retention')
PURPOSE = 'synthetic_metadata_research'


def _require(ok):
    if not ok:
        raise ValueError('invalid_admission_metadata')


def _id(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}', value) is not None


def _sha(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _schema(value, expected):
    _require(type(value) is str and value == expected)


def _tuple(obj, field, item_type, limit=128):
    value = getattr(obj, field)
    _require(type(value) in (tuple, list) and len(value) <= limit)
    _require(all(type(x) is item_type for x in value))
    object.__setattr__(obj, field, tuple(value))


@dataclass(frozen=True)
class Evidence:
    kind: str
    reference: str
    artifact_sha256: str

    def __post_init__(self):
        _require(type(self.kind) is str and self.kind in KINDS)
        _require(_id(self.reference) and _sha(self.artifact_sha256))


@dataclass(frozen=True)
class Package:
    schema: str
    package_id: str
    version: str
    purpose: str
    dates: DateRange
    event_start: datetime
    event_end: datetime
    available_at: datetime | None
    captured_at: datetime
    evidence: tuple[Evidence, ...]
    provider: str = 'fixture'
    feed: str = 'synthetic'

    def __post_init__(self):
        _schema(self.schema, 'lite.admission-package.v1')
        _require(all(_id(x) for x in (self.package_id, self.version, self.purpose)))
        _require(type(self.dates) is DateRange)
        _require(type(self.provider) is str and self.provider == 'fixture')
        _require(type(self.feed) is str and self.feed == 'synthetic')
        for t in (self.event_start, self.event_end, self.captured_at):
            utc(t)
        if self.available_at is not None:
            utc(self.available_at)
        _tuple(self, 'evidence', Evidence)


@dataclass(frozen=True)
class Review:
    kind: str
    evidence_sha256: str
    verdict: str
    reviewer_id: str

    def __post_init__(self):
        _require(type(self.kind) is str and self.kind in KINDS)
        _require(_sha(self.evidence_sha256) and _id(self.reviewer_id))
        _require(type(self.verdict) is str and self.verdict in ('VERIFIED', 'UNVERIFIED', 'DENIED'))


@dataclass(frozen=True)
class Approval:
    schema: str
    approval_id: str
    issuer_id: str
    package_sha256: str
    purpose: str
    dates: DateRange
    valid_from: datetime
    valid_until: datetime
    reviews: tuple[Review, ...]

    def __post_init__(self):
        _schema(self.schema, 'lite.admission-approval.v1')
        _require(all(_id(x) for x in (self.approval_id, self.issuer_id, self.purpose)))
        _require(_sha(self.package_sha256) and type(self.dates) is DateRange)
        utc(self.valid_from)
        utc(self.valid_until)
        _require(self.valid_from < self.valid_until)
        _tuple(self, 'reviews', Review)


@dataclass(frozen=True)
class TrustContext:
    schema: str
    context_id: str
    version: str
    approved_issuers: tuple[str, ...]
    approved_reviewers: tuple[str, ...]
    approvals: tuple[Approval, ...]

    def __post_init__(self):
        _schema(self.schema, 'lite.admission-context.v1')
        _require(_id(self.context_id) and _id(self.version))
        for field in ('approved_issuers', 'approved_reviewers'):
            _tuple(self, field, str)
            _require(all(_id(x) for x in getattr(self, field)))
        _tuple(self, 'approvals', Approval)


@dataclass(frozen=True)
class AdmissionReport:
    schema: str
    status: str
    reasons: tuple[str, ...]
    package_sha256: str | None
    context_sha256: str | None
    expected_context_sha256: str | None
    approval_sha256: str | None
    evaluated_at: datetime | None
    evidence_kind: str = 'SYNTHETIC_ONLY'
    data_authenticity: str = 'UNVERIFIED'
    options_eligibility: str = 'UNKNOWN'
    profitability: str = 'UNKNOWN'
    downstream_authority: str = 'NONE'


def _plain(value):
    if type(value) in (Evidence, Package, Review, Approval, TrustContext, AdmissionReport, DateRange):
        return {'record_type': type(value).__name__,
                'fields': {f.name: _plain(getattr(value, f.name)) for f in fields(value)}}
    if type(value) is tuple:
        return tuple(_plain(x) for x in value)
    if value is None or type(value) in (str, datetime):
        return value
    raise ValueError('invalid_admission_metadata')


def identity(value):
    """Separate admission identities using the unchanged M1 typed encoder."""
    return digest(_plain(value))


def report_bytes(report):
    _require(type(report) is AdmissionReport)
    return canonical(_plain(report))


def _duplicates(values):
    return len(values) != len(set(values))


def admit(package, approval_id, *, trusted_context, expected_context_sha256, as_of):
    """No defaults/discovery for trust or time; ADMITTED grants no downstream authority.

    The trusted caller must obtain the expected context pin independently of the
    package. This pure API does not authenticate the caller or the pin's issuance.
    """
    rejected = set()
    unknown = set()
    package_hash = identity(package) if type(package) is Package else None
    context_hash = identity(trusted_context) if type(trusted_context) is TrustContext else None
    approval_hash = None
    valid_time = True
    try:
        utc(as_of)
    except ValueError:
        valid_time = False
        rejected.add('invalid_evaluation_time')

    def protect(start, end):
        try:
            validate_partition(start, end, 'development')
        except ValueError as error:
            rejected.add('protected_holdout_overlap' if str(error) == 'protected_holdout_overlap'
                         else 'invalid_chronology')

    def local_date(value):
        try:
            local = value.astimezone(NY)
        except OverflowError:
            rejected.add('timestamp_out_of_range')
            return None
        return local.date().isoformat()

    def protect_time(start, end):
        a, b = local_date(start), local_date(end)
        if a is not None and b is not None:
            protect(a, b)

    if type(package) is not Package:
        rejected.add('invalid_package')
    else:
        if package.purpose != PURPOSE:
            rejected.add('unsupported_purpose')
        protect(package.dates.start, package.dates.end)
        protect_time(package.event_start, package.event_end)
        if package.available_at is not None:
            protect_time(package.available_at, package.available_at)
        if not package.event_start < package.event_end <= package.captured_at:
            rejected.add('invalid_chronology')
        if valid_time and package.captured_at > as_of:
            rejected.add('invalid_chronology')
        if package.available_at is None:
            unknown.add('historical_availability_unverified')
        elif not package.event_end <= package.available_at <= package.captured_at:
            rejected.add('invalid_chronology')
        for t in (package.event_start, package.event_end):
            local = local_date(t)
            if local is not None and not package.dates.start <= local <= package.dates.end:
                rejected.add('event_outside_declared_dates')
        if _duplicates([e.kind for e in package.evidence]):
            rejected.add('duplicate_metadata')

    trusted = False
    if expected_context_sha256 is not None and not _sha(expected_context_sha256):
        rejected.add('invalid_trust_anchor')
    if trusted_context is not None and type(trusted_context) is not TrustContext:
        rejected.add('invalid_trust_context')
    if rejected.intersection(('invalid_trust_anchor', 'invalid_trust_context')):
        pass
    elif trusted_context is None or expected_context_sha256 is None:
        unknown.add('trust_context_unverified')
    elif context_hash != expected_context_sha256:
        rejected.add('trust_anchor_mismatch')
    else:
        trusted = True

    approval = None
    if not _id(approval_id):
        rejected.add('invalid_approval_identity')
    elif trusted:
        if (any(_duplicates(x) for x in (trusted_context.approved_issuers,
                                         trusted_context.approved_reviewers))
                or _duplicates([a.approval_id for a in trusted_context.approvals])):
            rejected.add('duplicate_metadata')
        matches = [a for a in trusted_context.approvals if a.approval_id == approval_id]
        if len(matches) != 1:
            rejected.add('approval_not_found')
        else:
            approval = matches[0]
            approval_hash = identity(approval)
            if approval.issuer_id not in trusted_context.approved_issuers:
                rejected.add('untrusted_issuer')
            protect(approval.dates.start, approval.dates.end)
            if valid_time:
                if as_of < approval.valid_from:
                    rejected.add('approval_not_yet_valid')
                if as_of >= approval.valid_until:
                    rejected.add('approval_expired')
            if _duplicates([r.kind for r in approval.reviews]):
                rejected.add('duplicate_metadata')

    if approval is not None and type(package) is Package:
        if approval.package_sha256 != package_hash:
            rejected.add('package_identity_mismatch')
        if approval.purpose != package.purpose:
            rejected.add('approval_purpose_mismatch')
        if approval.dates != package.dates:
            rejected.add('unauthorized_dates')
        evidence = {e.kind: e for e in package.evidence}
        reviews = {r.kind: r for r in approval.reviews}
        for kind in KINDS:
            if kind not in evidence:
                unknown.add(kind+'_evidence_missing')
            if kind not in reviews:
                unknown.add(kind+'_review_missing')
                continue
            review = reviews[kind]
            if review.reviewer_id not in trusted_context.approved_reviewers:
                rejected.add('untrusted_reviewer')
            if kind in evidence and review.evidence_sha256 != identity(evidence[kind]):
                rejected.add(kind+'_evidence_mismatch')
            if review.verdict == 'DENIED':
                rejected.add(kind+'_review_denied')
            if review.verdict == 'UNVERIFIED':
                unknown.add(kind+'_review_unverified')

    status = 'REJECTED' if rejected else 'UNKNOWN' if unknown else 'ADMITTED'
    reasons = tuple(sorted(rejected if rejected else unknown)) or ('all_required_synthetic_checks_satisfied',)
    return AdmissionReport('lite.research.evidence-admission.v1', status, reasons,
                           package_hash, context_hash,
                           expected_context_sha256 if _sha(expected_context_sha256) else None,
                           approval_hash, as_of if valid_time else None)
