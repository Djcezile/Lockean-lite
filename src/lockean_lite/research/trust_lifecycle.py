"""Offline synthetic lifecycle validation. Authentic checkpoint custody is external."""
from dataclasses import dataclass, fields
from datetime import datetime
from threading import Lock
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from nacl.bindings import crypto_core_ed25519_is_valid_point
from nacl.exceptions import UnavailableError
from . import signed_approvals as m3
from .data_contracts import canonical
from .validation import utc, validate_partition

PURPOSE = 'synthetic-trust-lifecycle'
DOMAIN = b'LOCKEAN-LITE-SYNTHETIC-LIFECYCLE-V1\x00'
ACTIONS = ('BOOTSTRAP', 'ACTIVATE', 'ROTATE', 'REVOKE', 'SUPERSEDE')


def require(ok):
    if not ok:
        raise ValueError('invalid_lifecycle_metadata')


def times(*values):
    for value in values:
        utc(value)


@dataclass(frozen=True)
class State:
    authority_id: str
    sequence: int
    effective_at: datetime
    valid_until: datetime
    controller: m3.PublicKey
    policy: m3.TrustPolicy | None
    revoked: tuple[str, ...]

    def __post_init__(self):
        require(m3._id(self.authority_id) and type(self.sequence) is int and 1 <= self.sequence < 2**63)
        times(self.effective_at, self.valid_until)
        require(self.effective_at < self.valid_until and type(self.controller) is m3.PublicKey)
        require(self.policy is None or type(self.policy) is m3.TrustPolicy)
        require(type(self.revoked) in (tuple, list) and len(self.revoked) <= 128)
        require(all(m3._hex(x, 64) for x in self.revoked))
        require(tuple(self.revoked) == tuple(sorted(set(self.revoked))))
        object.__setattr__(self, 'revoked', tuple(self.revoked))


@dataclass(frozen=True)
class Anchor:
    authority_id: str
    controller: m3.PublicKey
    genesis_sha256: str
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self):
        require(m3._id(self.authority_id) and type(self.controller) is m3.PublicKey)
        require(m3._hex(self.genesis_sha256, 64))
        times(self.valid_from, self.valid_until)
        require(self.valid_from < self.valid_until)


@dataclass(frozen=True)
class Checkpoint:
    anchor_sha256: str
    state_sha256: str | None
    sequence: int
    observed_at: datetime
    valid_until: datetime

    def __post_init__(self):
        require(m3._hex(self.anchor_sha256, 64))
        require(self.state_sha256 is None or m3._hex(self.state_sha256, 64))
        require(type(self.sequence) is int and 0 <= self.sequence < 2**63)
        times(self.observed_at, self.valid_until)
        require(self.observed_at < self.valid_until)


@dataclass(frozen=True)
class Transition:
    transition_id: str
    action: str
    prior_sha256: str | None
    next_sha256: str
    next_state: State
    anchor_sha256: str
    issued_at: datetime
    effective_at: datetime
    valid_until: datetime
    signature_hex: str | None

    def __post_init__(self):
        require(m3._id(self.transition_id) and type(self.action) is str and self.action in ACTIONS)
        require(self.prior_sha256 is None or m3._hex(self.prior_sha256, 64))
        require(m3._hex(self.next_sha256, 64) and m3._hex(self.anchor_sha256, 64))
        require(type(self.next_state) is State)
        times(self.issued_at, self.effective_at, self.valid_until)
        require(self.signature_hex is None or (type(self.signature_hex) is str and len(self.signature_hex) <= 256))


@dataclass(frozen=True)
class Report:
    action: str
    status: str
    reasons: tuple[str, ...]
    prior_sha256: str | None
    next_sha256: str | None
    anchor_sha256: str | None
    transition_sha256: str | None
    evaluated_at: datetime | None
    m3_report_sha256: str | None = None
    evidence_kind: str = 'SYNTHETIC_ONLY'
    data_authenticity: str = 'UNVERIFIED'
    options_eligibility: str = 'UNKNOWN'
    profitability: str = 'UNKNOWN'
    downstream_authority: str = 'NONE'


def snapshot(value):
    if type(value) in (State, Anchor, Checkpoint, Transition, Report):
        return {'type': type(value).__name__, 'fields': {f.name: snapshot(getattr(value, f.name)) for f in fields(value)}}
    if type(value) in (m3.PublicKey, m3.TrustPolicy):
        return m3.public_snapshot(value)
    if type(value) is tuple:
        return tuple(snapshot(x) for x in value)
    if value is None or type(value) in (str, int, datetime):
        return value
    raise ValueError('unsupported_lifecycle_record')


def encoded(value):
    return canonical({'schema': 'lite.m4.lifecycle.v1', 'record': snapshot(value)})


def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def signing_bytes(proposal):
    require(type(proposal) is Transition)
    # Signature excluded; every other field, including the complete successor, is bound.
    return DOMAIN + canonical({'schema': 'lite.m4.transition-signature.v1',
        'fields': {f.name: snapshot(getattr(proposal, f.name)) for f in fields(proposal) if f.name != 'signature_hex'}})


def report_bytes(report):
    require(type(report) is Report)
    return encoded(report)


def key_checks(key, revoked, at, purpose):
    errors = set()
    if key.fingerprint != hashlib.sha256(bytes.fromhex(key.public_key_hex)).hexdigest():
        errors.add('key_identity_mismatch')
    if key.status != 'ACTIVE' or key.fingerprint in revoked:
        errors.add('revoked_signer')
    if key.signing_purpose != purpose:
        errors.add('key_purpose')
    if not key.valid_from <= at < key.valid_until:
        errors.add('key_time')
    try:
        if not crypto_core_ed25519_is_valid_point(bytes.fromhex(key.public_key_hex)):
            errors.add('unsafe_public_key')
    except UnavailableError:
        errors.add('public_key_validation_unavailable')
    return errors


def state_checks(state, at):
    errors = key_checks(state.controller, state.revoked, at, PURPOSE)
    if not state.effective_at <= at < state.valid_until:
        errors.add('state_time')
    policy = state.policy
    if policy is not None:
        if policy.purpose != m3.m2.PURPOSE or not policy.version.isascii() or not policy.version.isdecimal() or str(int(policy.version)) != policy.version:
            errors.add('policy_version')
        if not policy.valid_from <= at < policy.valid_until:
            errors.add('policy_time')
        if len({k.key_id for k in policy.keys}) != len(policy.keys) or len(set(policy.approved_reviewers)) != len(policy.approved_reviewers):
            errors.add('duplicate_metadata')
        try:
            validate_partition(policy.dates.start, policy.dates.end, 'development')
        except ValueError:
            errors.add('protected_holdout_overlap')
        for key in policy.keys:
            # Revoked entries may be retained as evidence, but are never active authorities.
            if key.status == 'ACTIVE':
                errors.update(key_checks(key, state.revoked, at, m3.SIGNING_PURPOSE))
    return errors


def current_checks(state, anchor, pin, checkpoint, at):
    errors = set()
    try:
        utc(at)
    except ValueError:
        return {'invalid_evaluation_time'}
    if type(anchor) is not Anchor or not m3._hex(pin, 64) or identity(anchor) != pin:
        return {'untrusted_anchor'}
    if not anchor.valid_from <= at < anchor.valid_until:
        errors.add('anchor_time')
    if type(checkpoint) is not Checkpoint:
        return errors | {'missing_checkpoint'}
    if checkpoint.anchor_sha256 != pin or checkpoint.state_sha256 != (identity(state) if type(state) is State else None) or checkpoint.sequence != (state.sequence if type(state) is State else 0):
        errors.add('checkpoint_mismatch')
    if not checkpoint.observed_at <= at < checkpoint.valid_until:
        errors.add('checkpoint_time')
    if state is not None:
        if type(state) is not State:
            errors.add('invalid_state')
        else:
            if state.authority_id != anchor.authority_id:
                errors.add('authority_mismatch')
            if state.effective_at > checkpoint.observed_at:
                errors.add('checkpoint_chronology')
            errors.update(state_checks(state, at))
    return errors


def result(action, errors, state, anchor, at, proposal=None, legacy=None):
    valid_time = type(at) is datetime and at.tzinfo is not None
    try:
        utc(at)
    except ValueError:
        valid_time = False
    return Report(action, 'REJECTED' if errors else (legacy.status if legacy else 'ACCEPTED'),
        tuple(sorted(errors)) if errors else (legacy.reasons if legacy else ('transition_authorized',)),
        identity(state) if type(state) is State else None,
        proposal.next_sha256 if type(proposal) is Transition else None,
        identity(anchor) if type(anchor) is Anchor else None,
        identity(proposal) if type(proposal) is Transition else None, at if valid_time else None,
        m3.identity(legacy) if legacy else None)


def validate_transition(state, proposal, *, anchor, expected_anchor_sha256, checkpoint, as_of):
    errors = current_checks(state, anchor, expected_anchor_sha256, checkpoint, as_of)
    if type(proposal) is not Transition:
        return result('INVALID', errors | {'invalid_transition'}, state, anchor, as_of)
    if errors:
        return result(proposal.action, errors, state, anchor, as_of, proposal)
    next_state = proposal.next_state
    if proposal.anchor_sha256 != expected_anchor_sha256:
        errors.add('anchor_mismatch')
    if proposal.prior_sha256 != (identity(state) if state else None):
        errors.add('predecessor_mismatch')
    if proposal.next_sha256 != identity(next_state):
        errors.add('successor_mismatch')
    if next_state.sequence != (state.sequence + 1 if state else 1):
        errors.add('sequence_mismatch')
    if not proposal.issued_at <= proposal.effective_at <= as_of < proposal.valid_until or proposal.effective_at != next_state.effective_at:
        errors.add('authorization_time')
    if next_state.authority_id != anchor.authority_id:
        errors.add('authority_mismatch')
    errors.update(state_checks(next_state, as_of))
    signer = state.controller if state else anchor.controller
    revoked = state.revoked if state else ()
    errors.update(key_checks(signer, revoked, as_of, PURPOSE))
    if not signer.valid_from <= proposal.issued_at < signer.valid_until or not anchor.valid_from <= proposal.issued_at < anchor.valid_until:
        errors.add('authorization_time')
    if state and not state.effective_at <= proposal.issued_at < state.valid_until:
        errors.add('authorization_time')
    if state is None:
        if proposal.action != 'BOOTSTRAP' or identity(next_state) != anchor.genesis_sha256 or next_state.controller != anchor.controller or next_state.policy is not None or next_state.revoked:
            errors.add('invalid_bootstrap')
    else:
        errors.update(transition_rules(state, next_state, proposal.action))
    if not errors:
        if not m3._hex(proposal.signature_hex, 128):
            errors.add('invalid_signature')
        else:
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer.public_key_hex)).verify(bytes.fromhex(proposal.signature_hex), signing_bytes(proposal))
            except InvalidSignature:
                errors.add('invalid_signature')
    return result(proposal.action, errors, state, anchor, as_of, proposal)


def active(policy):
    return {k.fingerprint for k in policy.keys if k.status == 'ACTIVE'} if policy else set()


def transition_rules(old, new, action):
    errors = set()
    if not set(old.revoked) <= set(new.revoked) or new.effective_at < old.effective_at:
        errors.add('rollback')
    if action == 'BOOTSTRAP':
        return errors | {'invalid_bootstrap'}
    if old.policy is None:
        if action != 'ACTIVATE' or new.policy is None or new.policy.version != '1' or old.controller != new.controller or old.revoked != new.revoked:
            errors.add('invalid_activation')
        return errors
    if new.policy is None:
        return errors | {'missing_policy'}
    if new.policy.policy_id != old.policy.policy_id:
        errors.add('policy_identity')
    if identity(new.policy) != identity(old.policy):
        if not old.policy.version.isdecimal() or new.policy.version != str(int(old.policy.version) + 1):
            errors.add('policy_version')
    elif action != 'ROTATE':
        errors.add('policy_version')
    removed = active(old.policy) - active(new.policy)
    if not removed <= set(new.revoked):
        errors.add('missing_revocations')
    if action == 'ROTATE':
        if not (active(new.policy) - active(old.policy) or new.controller != old.controller):
            errors.add('invalid_rotation')
        if new.controller != old.controller and old.controller.fingerprint not in new.revoked:
            errors.add('missing_revocations')
    elif action == 'REVOKE':
        if not set(old.revoked) < set(new.revoked) or active(new.policy) - active(old.policy) or new.controller != old.controller:
            errors.add('invalid_revocation')
    elif action == 'SUPERSEDE':
        if active(new.policy) != active(old.policy) or new.revoked != old.revoked or new.controller != old.controller:
            errors.add('invalid_supersession')
    else:
        errors.add('invalid_action')
    return errors


def admit(package, envelope, *, state, anchor, expected_anchor_sha256, checkpoint, as_of):
    errors = current_checks(state, anchor, expected_anchor_sha256, checkpoint, as_of)
    if type(state) is not State or state.policy is None:
        errors.add('inactive_policy')
    if errors:
        return result('ADMISSION', errors, state, anchor, as_of)
    legacy = m3.verify_admission(package, envelope, policy=state.policy,
                                expected_policy_sha256=m3.identity(state.policy), as_of=as_of)
    return result('ADMISSION', set(), state, anchor, as_of, legacy=legacy)


class SyntheticStore:
    """In-memory lock/CAS demonstration, not durable or authenticated storage."""
    def __init__(self, state, anchor, expected_anchor_sha256, checkpoint):
        self._state, self._anchor, self._pin, self._checkpoint = state, anchor, expected_anchor_sha256, checkpoint
        self._lock = Lock()

    def advance(self, proposal, *, expected_state_sha256, as_of):
        with self._lock:
            current = identity(self._state) if type(self._state) is State else None
            if expected_state_sha256 != current:
                return result('CAS', {'compare_and_swap_conflict'}, self._state, self._anchor, as_of, proposal)
            report = validate_transition(self._state, proposal, anchor=self._anchor,
                expected_anchor_sha256=self._pin, checkpoint=self._checkpoint, as_of=as_of)
            if report.status == 'ACCEPTED':
                self._state = proposal.next_state
                self._checkpoint = Checkpoint(self._pin, identity(self._state), self._state.sequence,
                                               as_of, min(self._checkpoint.valid_until, self._state.valid_until))
            return report
