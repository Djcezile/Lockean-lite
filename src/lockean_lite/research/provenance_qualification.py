"""Pure synthetic provenance qualification against an independently pinned snapshot."""

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from hashlib import sha256
import re

from .reporting import canonical
from .validation import NY, validate_partition


_SCHEMA = "lite.research.m5.v1"
_QUALIFIED = "QUALIFIED_SYNTHETIC_ONLY"
_PURPOSES = ("development", "validation")
_STORAGE = ("retain_data", "store_derived_features")
_SCOPES = (
    "internal_research", "commercial_research", "model_development",
    *_STORAGE, "redistribute", "external_reporting",
)
_MAX_ITEMS = 128
_MAX_RAW_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Step:
    actor: str
    transform: str
    input_sha256: str
    output_sha256: str


@dataclass(frozen=True, slots=True)
class Facts:
    reference: str | None
    series: str | None
    source: str | None
    product: str | None
    instrument_scheme: str | None
    instrument: str | None
    raw_sha256: str | None
    event_at: datetime | None
    first_published_at: datetime | None
    published_at: datetime | None
    received_at: datetime | None
    collected_at: datetime | None
    lineage: tuple[Step, ...] | None
    revision: int = 1
    supersedes: str | None = None


@dataclass(frozen=True, slots=True)
class Grant:
    agreement: str
    version: str
    issuer: str
    source: str
    product: str
    scopes: tuple[str, ...]
    purposes: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime
    retain_until: datetime | None


@dataclass(frozen=True, slots=True)
class Intent:
    purpose: str
    scopes: tuple[str, ...]
    decision_at: datetime
    retain_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class Approval:
    reference: str
    signer: str
    facts_sha256: str
    grant_sha256: str
    intent_sha256: str
    issued_at: datetime
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class Package:
    facts: Facts
    grant: Grant | None
    intent: Intent
    approval_reference: str | None
    policy_reference: str | None


@dataclass(frozen=True, slots=True)
class Entry:
    facts: Facts
    grant: Grant | None
    approval: Approval | None


@dataclass(frozen=True, slots=True)
class Checkpoint:
    policy_reference: str
    sequence: int
    observed_at: datetime
    valid_until: datetime
    entries: tuple[Entry, ...]
    issuers: tuple[str, ...]
    transformers: tuple[str, ...]
    signers: tuple[str, ...]
    revoked: tuple[str, ...] = ()
    replayed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Report:
    schema: str
    status: str
    reasons: tuple[str, ...]
    missing: tuple[str, ...]
    package_sha256: str | None
    checkpoint_sha256: str | None
    policy_reference: str | None
    checkpoint_sequence: int | None
    source_identity: str | None
    product_identity: str | None
    source_status: str
    rights_status: str
    chronology_status: str
    evaluated_at: datetime | None
    evidence_basis: str
    intended_use_sha256: str | None
    purpose: str | None
    requested_scopes: tuple[str, ...]
    qualification_domain: str = "SYNTHETIC_ONLY"
    real_world_authenticity: str = "UNVERIFIED"
    profitability: str = "UNKNOWN"
    downstream_authority: str = "NONE"


_FACT_IDS = ("reference", "series", "source", "product", "instrument_scheme", "instrument")
_TIME_FIELDS = (
    ("event_at", "event"), ("first_published_at", "first_publication"),
    ("published_at", "publication"), ("received_at", "receipt"), ("collected_at", "collection"),
)
_FACT_FIELDS = (
    ("reference", "raw_reference"), ("series", "series_identity"),
    ("source", "source_identity"), ("product", "product_identity"),
    ("instrument_scheme", "instrument_scheme"), ("instrument", "instrument_identity"),
    ("raw_sha256", "raw_digest"), ("lineage", "lineage"), *_TIME_FIELDS,
)


def _id(value):
    return type(value) is str and re.fullmatch(r"syn-[a-z0-9][a-z0-9.-]{0,59}", value) is not None


def _hex(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _time(value):
    if type(value) is not datetime or type(value.tzinfo) is not timezone or value.fold:
        return False
    try:
        value.astimezone(timezone.utc)
    except OverflowError:
        return False
    return True


def _utc(value):
    return value.astimezone(timezone.utc)


def _optional(value, check):
    return value is None or check(value)


def _count(value):
    return type(value) is int and 1 <= value <= 2**31 - 1


def _bounded_tuple(value, check):
    return type(value) is tuple and len(value) <= _MAX_ITEMS and all(map(check, value))


def _choice_tuple(value, choices):
    return _bounded_tuple(value, lambda item: type(item) is str and item in choices) and (
        len(value) == len(set(value))
    )


def _step(value):
    return (type(value) is Step and _id(value.actor) and _id(value.transform)
            and _hex(value.input_sha256) and _hex(value.output_sha256))


def _facts(value):
    return (type(value) is Facts
            and all(_optional(getattr(value, name), _id) for name in _FACT_IDS)
            and _optional(value.raw_sha256, _hex)
            and all(_optional(getattr(value, name), _time) for name, _ in _TIME_FIELDS)
            and _optional(value.lineage, lambda steps: _bounded_tuple(steps, _step))
            and _count(value.revision) and _optional(value.supersedes, _id))


def _grant(value):
    return (type(value) is Grant
            and all(map(_id, (value.agreement, value.version, value.issuer, value.source, value.product)))
            and _choice_tuple(value.scopes, _SCOPES) and _choice_tuple(value.purposes, _PURPOSES)
            and _time(value.valid_from) and _time(value.valid_until)
            and _optional(value.retain_until, _time))


def _intent(value):
    return (type(value) is Intent and type(value.purpose) is str and value.purpose in _PURPOSES
            and _choice_tuple(value.scopes, _SCOPES) and bool(value.scopes)
            and _time(value.decision_at) and _optional(value.retain_until, _time))


def _approval(value):
    return (type(value) is Approval and _id(value.reference) and _id(value.signer)
            and all(map(_hex, (value.facts_sha256, value.grant_sha256, value.intent_sha256)))
            and _time(value.issued_at) and _time(value.valid_until))


def _package(value):
    return (type(value) is Package and _facts(value.facts) and _optional(value.grant, _grant)
            and _intent(value.intent) and _optional(value.approval_reference, _id)
            and _optional(value.policy_reference, _id))


def _entry(value):
    return (type(value) is Entry and _facts(value.facts)
            and _id(value.facts.reference) and _id(value.facts.series)
            and _optional(value.grant, _grant) and _optional(value.approval, _approval))


def _checkpoint(value):
    return (type(value) is Checkpoint and _id(value.policy_reference) and _count(value.sequence)
            and _time(value.observed_at) and _time(value.valid_until)
            and _bounded_tuple(value.entries, _entry)
            and all(_bounded_tuple(items, _id) for items in (
                value.issuers, value.transformers, value.signers, value.revoked, value.replayed)))


_RECORDS = {
    Step: _step, Facts: _facts, Grant: _grant, Intent: _intent, Approval: _approval,
    Package: _package, Entry: _entry, Checkpoint: _checkpoint,
}


def _snapshot(value):
    if type(value) in (*_RECORDS, Report):
        return {"type": type(value).__name__, "fields": {
            field.name: _snapshot(getattr(value, field.name)) for field in fields(value)
        }}
    if type(value) is tuple:
        return tuple(map(_snapshot, value))
    if type(value) is datetime:
        return _utc(value)
    return value


def _encoded(value):
    return canonical({"schema": _SCHEMA, "record": _snapshot(value)})


def identity(value):
    """Versioned, type-separated SHA-256 identity for a structurally valid input."""
    check = _RECORDS.get(type(value))
    if check is None or not check(value):
        raise ValueError("invalid_provenance_record")
    return sha256(_encoded(value)).hexdigest()


def report_bytes(report):
    if type(report) is not Report:
        raise ValueError("invalid_provenance_report")
    return _encoded(report)


def _chronology(facts, intent, at, rejected, missing):
    times = [(name, _utc(value)) for field, name in _TIME_FIELDS
             if (value := getattr(facts, field)) is not None]
    decision = _utc(intent.decision_at)
    ordered = [value for _, value in times] + [decision]
    observations = ordered[:-1]
    if any(a > b for a, b in zip(observations, observations[1:])):
        rejected.add("chronology_conflict")
    for name, value in times:
        if value > decision:
            rejected.add(f"{name}_after_decision")
    if at is not None and decision > at:
        rejected.add("decision_after_evaluation")

    try:
        days = [value.astimezone(NY).date().isoformat() for value in ordered]
        validate_partition(min(days), max(days), intent.purpose)
    except OverflowError:
        rejected.add("timestamp_out_of_range")
    except ValueError:
        rejected.add("protected_holdout_overlap")

    if any(getattr(facts, field) is None for field, _ in _TIME_FIELDS):
        missing.add("chronology_evidence_missing")
    if (facts.revision == 1) != (facts.supersedes is None) or (
        facts.supersedes is not None and facts.supersedes == facts.reference
    ):
        rejected.add("revision_conflict")
    if facts.first_published_at is not None and facts.published_at is not None:
        if (facts.revision == 1) != (facts.first_published_at == facts.published_at):
            rejected.add("revision_conflict")


def _lineage(facts, rejected):
    if facts.lineage is None:
        return
    previous = facts.raw_sha256
    seen = {previous}
    for step in facts.lineage:
        if (previous is not None and step.input_sha256 != previous) or step.output_sha256 in seen:
            rejected.add("lineage_conflict")
        seen.add(step.output_sha256)
        previous = step.output_sha256


def _rights(grant, facts, intent, at, rejected, missing):
    decision = intent.decision_at
    if grant is None:
        missing.add("rights_missing")
    else:
        if any(getattr(facts, field) is not None and getattr(facts, field) != getattr(grant, field)
               for field in ("source", "product")):
            rejected.add("rights_product_mismatch")
        if not grant.valid_from <= decision < grant.valid_until or (
            at is not None and not grant.valid_from <= at < grant.valid_until
        ):
            rejected.add("rights_time")
        if intent.purpose not in grant.purposes:
            rejected.add("purpose_not_granted")
        if not set(intent.scopes) <= set(grant.scopes):
            rejected.add("usage_not_granted")
        if grant.retain_until is not None and not grant.valid_from < grant.retain_until <= grant.valid_until:
            rejected.add("rights_time")

    if set(intent.scopes).intersection(_STORAGE):
        if intent.retain_until is None:
            missing.add("retention_deadline_missing")
        elif (intent.retain_until <= decision or (at is not None and intent.retain_until <= at)
              or (grant is not None and
                  (grant.retain_until is None or intent.retain_until > grant.retain_until))):
            rejected.add("retention_not_granted")
    elif intent.retain_until is not None:
        rejected.add("retention_scope_missing")


def _duplicates(values):
    return len(values) != len(set(values))


def _observation_key(facts):
    return facts.source, facts.product, facts.instrument_scheme, facts.instrument, facts.event_at


def _current(checkpoint, pin, at, rejected, missing):
    valid_checkpoint = _checkpoint(checkpoint)
    if checkpoint is not None and not valid_checkpoint:
        rejected.add("invalid_checkpoint")
    if pin is not None and not _hex(pin):
        rejected.add("invalid_current_anchor")
    if checkpoint is None or pin is None:
        missing.add("current_anchor_missing")
    if not valid_checkpoint or not _hex(pin):
        return None
    if identity(checkpoint) != pin:
        rejected.add("checkpoint_pin_mismatch")
        return None
    if at is None or not checkpoint.observed_at <= at < checkpoint.valid_until:
        rejected.add("checkpoint_stale")
        return None

    if checkpoint.policy_reference in checkpoint.revoked:
        rejected.add("revoked_policy")
        return None

    records = [entry.facts for entry in checkpoint.entries]
    references = [facts.reference for facts in records]
    prior = [facts.supersedes for facts in records if facts.supersedes is not None]
    keys = [key for facts in records if None not in (key := _observation_key(facts))]
    approvals = [entry.approval.reference for entry in checkpoint.entries if entry.approval is not None]
    if set(references).intersection(prior) or any(map(_duplicates, (
        references, prior, keys, approvals, [facts.series for facts in records],
        checkpoint.issuers, checkpoint.transformers, checkpoint.signers,
        checkpoint.revoked, checkpoint.replayed,
    ))):
        rejected.add("conflicting_current_state")
        return None
    return checkpoint


def _match(facts, checkpoint, rejected, missing):
    if facts.reference is None:
        return None
    if facts.reference in checkpoint.revoked:
        rejected.add("revoked_evidence")
    if facts.reference in checkpoint.replayed:
        rejected.add("replayed_evidence")
    for entry in checkpoint.entries:
        if entry.facts.reference == facts.reference:
            return entry
    key = _observation_key(facts)
    for entry in checkpoint.entries:
        if facts.reference == entry.facts.supersedes:
            rejected.add("superseded_evidence")
            return None
        if facts.series == entry.facts.series:
            rejected.add("superseded_evidence" if facts.revision < entry.facts.revision
                         else "revision_mismatch")
            return None
        if None not in key and key == _observation_key(entry.facts):
            rejected.add("duplicate_observation")
            return None
    missing.add("custody_unverified")
    return None


def _compare_claims(facts, known, fields_and_reasons, rejected, missing):
    for fields, reason in fields_and_reasons:
        for name in fields:
            supplied, verified = getattr(facts, name), getattr(known, name)
            if supplied is None or verified is None:
                missing.add(f"{name}_unverified")
            elif supplied != verified:
                rejected.add(reason)


def _bound_entry(package, entry, checkpoint, at, rejected, missing,
                 chronology_errors, chronology_missing, rights_errors, rights_missing):
    facts, known = package.facts, entry.facts
    _compare_claims(facts, known, (
        (("series", "revision"), "revision_mismatch"),
        (("instrument", "instrument_scheme"), "instrument_mismatch"),
        (("raw_sha256",), "raw_digest_mismatch"),
        (("lineage",), "lineage_mismatch"),
    ), rejected, missing)
    if facts.supersedes != known.supersedes:
        rejected.add("revision_mismatch")
    _lineage(known, rejected)
    _chronology(known, package.intent, at, chronology_errors, chronology_missing)
    if known.collected_at is not None and known.collected_at > checkpoint.observed_at:
        chronology_errors.add("checkpoint_precedes_collection")
    _compare_claims(facts, known, (
        (tuple(field for field, _ in _TIME_FIELDS), "availability_mismatch"),
    ), chronology_errors, chronology_missing)
    for step in known.lineage or ():
        if step.actor not in checkpoint.transformers or step.actor in checkpoint.revoked:
            rejected.add("untrusted_transformer")

    grant = entry.grant
    if grant is None:
        rights_missing.add("rights_unverified")
    else:
        _rights(grant, known, package.intent, at, rights_errors, rights_missing)
        if package.grant is not None and package.grant != grant:
            rights_errors.add("rights_mismatch")
        if grant.issuer not in checkpoint.issuers:
            rights_errors.add("untrusted_rights_issuer")
        if grant.issuer in checkpoint.revoked or grant.agreement in checkpoint.revoked:
            rights_errors.add("revoked_rights")

    approval = entry.approval
    if approval is None or package.approval_reference is None:
        missing.add("approval_unverified")
    if approval is None:
        return
    if package.approval_reference is not None and package.approval_reference != approval.reference:
        rejected.add("approval_reference_mismatch")
    if approval.signer not in checkpoint.signers or approval.signer in checkpoint.revoked:
        rejected.add("untrusted_approval_signer")
    if approval.reference in checkpoint.revoked:
        rejected.add("revoked_approval")
    if (not approval.issued_at <= checkpoint.observed_at <= at < approval.valid_until
            or (known.collected_at is not None and known.collected_at > approval.issued_at)):
        rejected.add("approval_time")
    if approval.facts_sha256 != identity(known) or approval.intent_sha256 != identity(package.intent):
        rejected.add("approval_binding_mismatch")
    if grant is not None and approval.grant_sha256 != identity(grant):
        rejected.add("approval_binding_mismatch")


def _status(rejected, missing):
    if rejected:
        return "REJECTED"
    return "UNKNOWN" if missing else _QUALIFIED


def qualify(package, *, raw_bytes, checkpoint, expected_checkpoint_sha256, as_of, intended_use):
    """Evaluate synthetic evidence. The caller owns the independent current pin and intent."""
    rejected, missing = set(), set()
    rights_errors, rights_missing = set(), set()
    chronology_errors, chronology_missing = set(), set()
    source_errors, source_missing = set(), set()
    source = product = None
    at = _utc(as_of) if _time(as_of) else None
    if at is None:
        rejected.add("invalid_evaluation_time")

    current = _current(checkpoint, expected_checkpoint_sha256, at, rejected, missing)
    valid_package = _package(package)
    if not valid_package:
        rejected.add("invalid_package")
    intent_hash = identity(intended_use) if _intent(intended_use) else None
    if intent_hash is None:
        rejected.add("invalid_intended_use")
    actual_raw_sha256 = None
    if raw_bytes is None:
        missing.add("raw_bytes_missing")
    elif type(raw_bytes) is not bytes or not 0 < len(raw_bytes) <= _MAX_RAW_BYTES:
        rejected.add("invalid_raw_bytes")
    else:
        actual_raw_sha256 = sha256(raw_bytes).hexdigest()

    if valid_package:
        facts = package.facts
        for field, label in _FACT_FIELDS:
            if getattr(facts, field) is None:
                missing.add(f"{label}_missing")
        if identity(package.intent) != intent_hash:
            rejected.add("intended_use_mismatch")
        if package.approval_reference is None:
            missing.add("approval_reference_missing")
        if package.policy_reference is None:
            missing.add("policy_reference_missing")
        if (actual_raw_sha256 is not None and facts.raw_sha256 is not None
                and actual_raw_sha256 != facts.raw_sha256):
            rejected.add("raw_digest_mismatch")
        _lineage(facts, rejected)
        _chronology(facts, package.intent, at, chronology_errors, chronology_missing)
        _rights(package.grant, facts, package.intent, at, rights_errors, rights_missing)

        if current is not None:
            if package.policy_reference is not None and package.policy_reference != current.policy_reference:
                rejected.add("policy_reference_mismatch")
            entry = _match(facts, current, rejected, missing)
            if entry is not None:
                trusted_raw_sha256 = entry.facts.raw_sha256
                if (actual_raw_sha256 is not None and trusted_raw_sha256 is not None
                        and actual_raw_sha256 != trusted_raw_sha256):
                    rejected.add("raw_digest_mismatch")
                _compare_claims(facts, entry.facts, ((("source", "product"), "source_mismatch"),),
                                source_errors, source_missing)
                _bound_entry(package, entry, current, at, rejected, missing,
                             chronology_errors, chronology_missing, rights_errors, rights_missing)
                if entry.facts.source in current.revoked or entry.facts.product in current.revoked:
                    source_errors.add("revoked_source")
                if not source_errors and not source_missing:
                    source, product = entry.facts.source, entry.facts.product

    if source is None:
        source_missing.add("source_binding_unverified")
        chronology_missing.add("availability_binding_unverified")
        rights_missing.add("rights_source_binding_unverified")

    rejected.update(source_errors | chronology_errors | rights_errors)
    missing.update(source_missing | chronology_missing | rights_missing)
    status = _status(rejected, missing)
    basis = {
        _QUALIFIED: "PINNED_SYNTHETIC_SNAPSHOT",
        "UNKNOWN": "METADATA_UNVERIFIED",
        "REJECTED": "REJECTED_EVIDENCE",
    }[status]
    return Report(
        _SCHEMA, status, tuple(sorted(rejected | missing)) or ("synthetic_contract_satisfied",),
        tuple(sorted(missing)), identity(package) if valid_package else None,
        expected_checkpoint_sha256 if current is not None else None,
        current.policy_reference if current is not None else None,
        current.sequence if current is not None else None, source, product,
        _status(source_errors, source_missing), _status(rights_errors, rights_missing),
        _status(chronology_errors, chronology_missing), at, basis, intent_hash,
        intended_use.purpose if intent_hash is not None else None,
        intended_use.scopes if intent_hash is not None else (),
    )
