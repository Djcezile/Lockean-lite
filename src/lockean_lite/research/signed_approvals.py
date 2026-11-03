"""Synthetic Ed25519 approval verification; trusted root custody is external."""
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
import hashlib
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import evidence_admission as m2
from .data_contracts import DateRange, canonical, digest
from .validation import utc, validate_partition

DOMAIN = b'LOCKEAN-LITE-SYNTHETIC-APPROVAL-V1\x00'
SIGNING_PURPOSE = 'synthetic-evidence-approval'


def _require(ok):
    if not ok:
        raise ValueError('invalid_signed_approval_metadata')


def _id(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}', value) is not None


def _hex(value, size):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}', value) is not None


def _tuple(obj, field, kind):
    values = getattr(obj, field)
    _require(type(values) in (tuple, list) and len(values) <= 128)
    _require(all(type(v) is kind for v in values))
    object.__setattr__(obj, field, tuple(values))


@dataclass(frozen=True)
class PublicKey:
    issuer_id: str
    key_id: str
    public_key_hex: str
    fingerprint: str
    status: str
    signing_purpose: str
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self):
        _require(all(_id(v) for v in (self.issuer_id, self.key_id, self.signing_purpose)))
        _require(_hex(self.public_key_hex, 64) and _hex(self.fingerprint, 64))
        _require(type(self.status) is str and self.status in ('ACTIVE', 'REVOKED'))
        utc(self.valid_from)
        utc(self.valid_until)
        _require(self.valid_from < self.valid_until)


@dataclass(frozen=True)
class TrustPolicy:
    schema: str
    policy_id: str
    version: str
    keys: tuple[PublicKey, ...]
    approved_reviewers: tuple[str, ...]
    purpose: str
    dates: DateRange
    valid_from: datetime
    valid_until: datetime
    max_approval_seconds: int

    def __post_init__(self):
        _require(type(self.schema) is str and self.schema == 'lite.signing-policy.v1')
        _require(all(_id(v) for v in (self.policy_id, self.version, self.purpose)))
        _require(type(self.dates) is DateRange)
        utc(self.valid_from)
        utc(self.valid_until)
        _require(self.valid_from < self.valid_until)
        _require(type(self.max_approval_seconds) is int and 0 < self.max_approval_seconds <= 31536000)
        _tuple(self, 'keys', PublicKey)
        _tuple(self, 'approved_reviewers', str)
        _require(all(_id(v) for v in self.approved_reviewers))


@dataclass(frozen=True)
class ApprovalMessage:
    schema: str
    artifact_type: str
    policy_id: str
    policy_version: str
    issuer_id: str
    key_id: str
    key_fingerprint: str
    approval_id: str
    issued_at: datetime
    context: m2.TrustContext

    def __post_init__(self):
        _require(all(_id(v) for v in (self.schema, self.artifact_type, self.policy_id,
                                     self.policy_version, self.issuer_id, self.key_id, self.approval_id)))
        _require(_hex(self.key_fingerprint, 64))
        utc(self.issued_at)
        _require(type(self.context) is m2.TrustContext)


@dataclass(frozen=True)
class SignedEnvelope:
    schema: str
    algorithm: str
    message: ApprovalMessage
    signature_hex: str | None

    def __post_init__(self):
        _require(_id(self.schema) and _id(self.algorithm))
        _require(type(self.message) is ApprovalMessage)
        _require(self.signature_hex is None or
                 (type(self.signature_hex) is str and len(self.signature_hex) <= 256))


@dataclass(frozen=True)
class SignedAdmissionReport:
    schema: str
    status: str
    reasons: tuple[str, ...]
    package_sha256: str | None
    policy_sha256: str | None
    expected_policy_sha256: str | None
    message_sha256: str | None
    envelope_sha256: str | None
    m2_report_sha256: str | None
    evaluated_at: datetime | None
    signature_status: str
    evidence_kind: str = 'SYNTHETIC_ONLY'
    data_authenticity: str = 'UNVERIFIED'
    options_eligibility: str = 'UNKNOWN'
    profitability: str = 'UNKNOWN'
    downstream_authority: str = 'NONE'


def public_snapshot(value):
    """Only supported public contracts; private key objects cannot be serialized."""
    allowed = (PublicKey, TrustPolicy, ApprovalMessage, SignedEnvelope, SignedAdmissionReport,
               m2.Evidence, m2.Package, m2.Review, m2.Approval, m2.TrustContext, DateRange)
    if type(value) in allowed:
        return {'record_type': type(value).__name__,
                'fields': {f.name: public_snapshot(getattr(value, f.name)) for f in fields(value)}}
    if type(value) is tuple:
        return tuple(public_snapshot(v) for v in value)
    if value is None or type(value) in (str, int, datetime):
        return value
    raise ValueError('unsupported_public_snapshot')


def identity(value):
    return digest({'schema': 'lite.m3.identity.v1', 'record': public_snapshot(value)})


def signing_bytes(message):
    _require(type(message) is ApprovalMessage)
    return DOMAIN + canonical({'schema': 'lite.m3.signing-frame.v1',
                                'message': public_snapshot(message)})


def sign(message, private_key):
    """Caller supplies ephemeral test key; this helper grants no issuance authority."""
    _require(type(message) is ApprovalMessage and isinstance(private_key, Ed25519PrivateKey))
    return SignedEnvelope('lite.signed-approval-envelope.v1', 'Ed25519', message,
                          private_key.sign(signing_bytes(message)).hex())


def report_bytes(report):
    _require(type(report) is SignedAdmissionReport)
    return canonical({'schema': 'lite.m3.identity.v1', 'record': public_snapshot(report)})


def _duplicates(values):
    return len(values) != len(set(values))


def verify_admission(package, envelope, *, policy, expected_policy_sha256, as_of):
    """Mandatory signature gate. Caller must supply authentic CURRENT policy/pin."""
    rejected = set()
    signature_verified = False
    legacy = None
    valid_time = True
    try:
        utc(as_of)
    except ValueError:
        valid_time = False
        rejected.add('invalid_evaluation_time')

    def report():
        status = 'REJECTED' if rejected else legacy.status
        reasons = tuple(sorted(rejected)) if rejected else legacy.reasons
        return SignedAdmissionReport(
            'lite.research.signed-admission.v1', status, reasons,
            m2.identity(package) if type(package) is m2.Package else None,
            identity(policy) if type(policy) is TrustPolicy else None,
            expected_policy_sha256 if _hex(expected_policy_sha256, 64) else None,
            hashlib.sha256(signing_bytes(envelope.message)).hexdigest() if type(envelope) is SignedEnvelope else None,
            identity(envelope) if type(envelope) is SignedEnvelope else None,
            m2.identity(legacy) if legacy is not None else None,
            as_of if valid_time else None, 'VERIFIED' if signature_verified else 'NOT_VERIFIED')

    if type(package) is not m2.Package:
        rejected.add('invalid_package')
    if type(policy) is not TrustPolicy:
        rejected.add('missing_trusted_policy')
    elif not _hex(expected_policy_sha256, 64) or identity(policy) != expected_policy_sha256:
        rejected.add('trust_policy_mismatch')
    if type(envelope) is not SignedEnvelope:
        rejected.add('missing_signed_approval')
    if rejected:
        return report()

    msg = envelope.message
    if envelope.schema != 'lite.signed-approval-envelope.v1' or msg.schema != 'lite.signed-approval-message.v1':
        rejected.add('unsupported_signed_schema')
    if envelope.algorithm != 'Ed25519':
        rejected.add('unsupported_algorithm')
    if msg.artifact_type != SIGNING_PURPOSE:
        rejected.add('wrong_approval_domain')
    if (msg.policy_id, msg.policy_version) != (policy.policy_id, policy.version):
        rejected.add('obsolete_or_wrong_policy')
    if policy.purpose != m2.PURPOSE:
        rejected.add('unsupported_purpose')
    if _duplicates([k.key_id for k in policy.keys]) or _duplicates(policy.approved_reviewers):
        rejected.add('duplicate_metadata')
    issuer_keys = [k for k in policy.keys if k.issuer_id == msg.issuer_id]
    if not issuer_keys:
        rejected.add('unknown_issuer')
    keys = [k for k in issuer_keys if k.key_id == msg.key_id]
    if len(keys) != 1:
        rejected.add('unknown_key')
    if rejected:
        return report()

    key = keys[0]
    fingerprint = hashlib.sha256(bytes.fromhex(key.public_key_hex)).hexdigest()
    if key.fingerprint != fingerprint or msg.key_fingerprint != fingerprint:
        rejected.add('key_identity_mismatch')
    if key.status != 'ACTIVE':
        rejected.add('key_revoked')
    if key.signing_purpose != SIGNING_PURPOSE:
        rejected.add('unapproved_signing_purpose')
    if not _hex(envelope.signature_hex, 128):
        rejected.add('missing_or_malformed_signature')
    if valid_time:
        if as_of < key.valid_from:
            rejected.add('key_not_yet_valid')
        if as_of >= key.valid_until:
            rejected.add('key_expired')
        if not policy.valid_from <= as_of < policy.valid_until:
            rejected.add('policy_not_current')
    if rejected:
        return report()
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key.public_key_hex)).verify(
            bytes.fromhex(envelope.signature_hex), signing_bytes(msg))
    except InvalidSignature:
        rejected.add('invalid_signature')
        return report()
    signature_verified = True

    context = msg.context
    if (_duplicates([a.approval_id for a in context.approvals])
            or _duplicates(context.approved_issuers) or _duplicates(context.approved_reviewers)):
        rejected.add('duplicate_metadata')
    matches = [a for a in context.approvals if a.approval_id == msg.approval_id]
    if len(matches) != 1 or len(context.approvals) != 1:
        rejected.add('invalid_signed_context')
        return report()
    approval = matches[0]
    if approval.issuer_id != msg.issuer_id or context.approved_issuers != (msg.issuer_id,):
        rejected.add('unauthorized_context_issuer')
    if (any(r not in policy.approved_reviewers for r in context.approved_reviewers)
            or any(r.reviewer_id not in policy.approved_reviewers for r in approval.reviews)):
        rejected.add('untrusted_reviewer')
    if approval.purpose != policy.purpose:
        rejected.add('unsupported_purpose')
    if not policy.dates.start <= approval.dates.start <= approval.dates.end <= policy.dates.end:
        rejected.add('unauthorized_dates')
    for dates in (policy.dates, approval.dates):
        try:
            validate_partition(dates.start, dates.end, 'development')
        except ValueError:
            rejected.add('protected_holdout_overlap')
    if not policy.valid_from <= msg.issued_at < policy.valid_until:
        rejected.add('invalid_policy_issuance_time')
    if not key.valid_from <= msg.issued_at < key.valid_until:
        rejected.add('invalid_key_issuance_time')
    if not msg.issued_at <= approval.valid_from or msg.issued_at > as_of:
        rejected.add('invalid_issuance_chronology')
    if as_of < approval.valid_from:
        rejected.add('approval_not_yet_valid')
    if as_of >= approval.valid_until:
        rejected.add('approval_expired')
    if approval.valid_until > min(key.valid_until, policy.valid_until):
        rejected.add('approval_exceeds_trust_window')
    if approval.valid_until - approval.valid_from > timedelta(seconds=policy.max_approval_seconds):
        rejected.add('approval_lifetime_exceeded')
    if rejected:
        return report()

    # This path is reached only after root, signature and signed-policy constraints.
    legacy = m2.admit(package, msg.approval_id, trusted_context=context,
                      expected_context_sha256=m2.identity(context), as_of=as_of)
    return report()
