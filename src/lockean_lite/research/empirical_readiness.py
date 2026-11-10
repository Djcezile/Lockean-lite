"""Offline readiness checks for generated research protocols and evidence."""

from dataclasses import dataclass, fields, replace
from datetime import date, datetime, timezone
from functools import cache
from hashlib import sha256
import re
from types import MappingProxyType, UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from .reporting import canonical
from .validation import NY, validate_partition


SCHEMA = "lite.research.m7.v1"
PURPOSE = "synthetic-empirical-readiness"
_MAX_ITEMS = 4096
_MAX_RAW = 8 * 1024 * 1024
_REQUIRED_SCOPES = frozenset({
    "internal_research", "non_display", "retain_raw", "retain_derived", "reviewer_access",
})
_SCOPES = _REQUIRED_SCOPES | {"commercial_research", "model_development", "redistribute"}
SyntheticID = Annotated[str, "synthetic"]
Digest = Annotated[str, "sha256"]


@dataclass(frozen=True, slots=True)
class Design:
    hypothesis: str
    null_hypothesis: str
    universe_filter: str
    price_schema: str
    lookback_sessions: int
    holding_sessions: int
    schedule: str
    benchmark: str
    endpoint: str
    multiplicity: str = "holm-familywise-0.05"
    exposure: str = "long-cash-no-volatility-scaling"
    execution_cost_model: str = "executable-sides-fees-slippage-missed-fills"


DESIGNS = MappingProxyType({
    "trend": Design(
        "positive-trailing-total-return-adds-incremental-return",
        "nonpositive-incremental-return",
        "liquid-unlevered-etfs", "daily-total-return-and-execution-quotes", 252, 21,
        "monthly-after-prior-completed-close", "exposure-matched-passive",
        "paired-21-session-incremental-total-return",
    ),
    "earnings": Design(
        "positive-as-issued-eps-surprise-adds-incremental-return",
        "nonpositive-incremental-return",
        "liquid-us-common-shares", "as-issued-eps-pre-release-consensus-and-execution-quotes",
        1, 20, "first-eligible-session-after-original-release",
        "sector-and-liquidity-matched-nonsurprises",
        "paired-20-session-sector-liquidity-adjusted-return",
    ),
})


@dataclass(frozen=True, slots=True)
class Session:
    open_at: datetime
    close_at: datetime


@dataclass(frozen=True, slots=True)
class Calendar:
    sessions: Annotated[tuple[Session, ...], 2048]


@dataclass(frozen=True, slots=True)
class Decision:
    at: datetime
    execute_at: datetime


@dataclass(frozen=True, slots=True)
class Fold:
    name: str
    start: date
    end: date
    decisions: Annotated[tuple[Decision, ...], 512]


@dataclass(frozen=True, slots=True)
class Limits:
    min_effect_bp: int
    capacity_cents: int
    max_drawdown_bp: int
    spread_bp: int
    slippage_bp: int
    fee_bp: int
    provider_cap_cents: int
    infrastructure_cap_cents: int
    recurring_cap_cents: int
    total_cap_cents: int


@dataclass(frozen=True, slots=True)
class Study:
    study_id: SyntheticID
    candidate: str
    universe: Annotated[tuple[SyntheticID, ...], 32]
    calendar: Calendar
    folds: Annotated[tuple[Fold, ...], 3]
    purpose: str
    scopes: Annotated[tuple[str, ...], 8]
    retain_raw_until: date
    retain_derived_until: date
    reviewer: SyntheticID
    provenance_ref: SyntheticID
    license_ref: SyntheticID
    limits: Limits
    embargo_sessions: int


@dataclass(frozen=True, slots=True)
class Instrument:
    reference: SyntheticID
    scheme: SyntheticID
    listed_on: date
    delisted_on: date | None
    coverage_start: date
    coverage_end: date
    eligible: bool


@dataclass(frozen=True, slots=True)
class Earnings:
    original_release_at: datetime
    consensus_at: datetime
    consensus_received_at: datetime
    actual_period: SyntheticID
    consensus_period: SyntheticID
    actual_version: SyntheticID
    consensus_version: SyntheticID
    actual_basis: SyntheticID
    consensus_basis: SyntheticID


@dataclass(frozen=True, slots=True)
class Sample:
    instrument: SyntheticID
    decision_at: datetime
    observed_at: datetime
    published_at: datetime
    provider_received_at: datetime
    local_received_at: datetime
    actions_at: datetime
    benchmark_at: datetime
    revision_at: datetime
    earnings: Earnings | None


@dataclass(frozen=True, slots=True)
class Dataset:
    source: SyntheticID | None
    product: SyntheticID | None
    version: SyntheticID
    raw_sha256: Digest | None
    provenance_ref: SyntheticID
    calendar_sha256: Digest
    instruments: Annotated[tuple[Instrument, ...], 32]
    samples: tuple[Sample, ...]
    point_in_time_universe: bool | None
    delistings_complete: bool | None
    actions_complete: bool | None
    distributions_complete: bool | None
    revisions_as_known: bool | None


@dataclass(frozen=True, slots=True)
class Rights:
    reference: SyntheticID
    issuer: SyntheticID
    agreement_version: SyntheticID
    source: SyntheticID
    product: SyntheticID
    dataset_version: SyntheticID
    purpose: str
    scopes: Annotated[tuple[str, ...], 8]
    reviewer: SyntheticID | None
    valid_from: datetime
    valid_until: datetime
    raw_until: date
    derived_until: date


@dataclass(frozen=True, slots=True)
class Costs:
    study_sha256: Digest
    dataset_sha256: Digest
    provider_cents: int | None
    infrastructure_cents: int | None
    recurring_cents: int | None
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class Registration:
    study_id: SyntheticID
    study_sha256: Digest


@dataclass(frozen=True, slots=True)
class Review:
    study_sha256: Digest
    dataset_sha256: Digest
    reviewer: SyntheticID
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class Checkpoint:
    authority: SyntheticID
    sequence: int
    observed_at: datetime
    valid_until: datetime
    registry: Annotated[tuple[Registration, ...], 128]
    dataset: Dataset | None
    rights: Rights | None
    costs: Costs | None
    review: Review | None = None
    revoked: tuple[SyntheticID, ...] = ()
    replayed: tuple[SyntheticID, ...] = ()


@dataclass(frozen=True, slots=True)
class Report:
    status: str
    reasons: tuple[str, ...]
    missing: tuple[str, ...]
    protocol_sha256: str | None
    dataset_sha256: str | None
    checkpoint_sha256: str | None
    evaluated_at: datetime | None
    review_status: str
    qualification_domain: str = "SYNTHETIC_ONLY"
    real_world_authenticity: str = "UNVERIFIED"
    profitability: str = "UNKNOWN"
    empirical_authority: str = "NONE"
    trading_authority: str = "NONE"


_RECORDS = (
    Design, Session, Calendar, Decision, Fold, Limits, Study, Instrument, Earnings,
    Sample, Dataset, Rights, Costs, Registration, Review, Checkpoint,
)
_DATA_FLAGS = (
    "point_in_time_universe", "delistings_complete", "actions_complete",
    "distributions_complete", "revisions_as_known",
)
_NULLABLE_CLAIMS = ("source", "product", "raw_sha256", *_DATA_FLAGS)
_MISSING_FIELD = object()


@cache
def _annotations(kind):
    return get_type_hints(kind, include_extras=True)


def _valid(value, kind):
    origin, args = get_origin(kind), get_args(kind)
    if origin is Annotated:
        if type(args[1]) is int:
            return type(value) is tuple and len(value) <= args[1] and _valid(value, args[0])
        pattern = r"syn-[a-z0-9][a-z0-9.-]{0,59}" if args[1] == "synthetic" else r"[a-f0-9]{64}"
        return type(value) is str and len(value) <= 64 and re.fullmatch(pattern, value) is not None
    if origin in (Union, UnionType):
        return any(_valid(value, choice) for choice in args)
    if origin is tuple:
        return type(value) is tuple and len(value) <= _MAX_ITEMS and all(
            _valid(item, args[0]) for item in value
        )
    if type(value) is not kind:
        return False
    if kind in _RECORDS:
        return all(_valid(getattr(value, name, _MISSING_FIELD), annotation)
                   for name, annotation in _annotations(kind).items())
    if kind is datetime:
        return value.tzinfo is timezone.utc and not value.fold and 1900 <= value.year <= 2200
    if kind is date:
        return 1900 <= value.year <= 2200
    if kind is str:
        return len(value) <= 96 and re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", value) is not None
    if kind is int:
        return 0 <= value <= 10**12
    return kind in (bool, type(None))


def _plain(value):
    if type(value) in (*_RECORDS, Report):
        return {"type": type(value).__name__, "fields": {
            field.name: _plain(getattr(value, field.name)) for field in fields(value)
        }}
    if type(value) is date:
        return {"date": value.isoformat()}
    if type(value) is tuple:
        return tuple(map(_plain, value))
    return value


def _encoded(value):
    envelope = {"schema": SCHEMA, "record": _plain(value)}
    if type(value) is Study:
        envelope["design"] = _plain(DESIGNS.get(value.candidate))
    return canonical(envelope)


def _digest(value):
    return sha256(_encoded(value)).hexdigest()


def identity(value):
    """Hash a bounded typed record and its versioned schema."""
    if type(value) not in _RECORDS or not _valid(value, type(value)):
        raise ValueError("invalid_m7_record")
    return _digest(value)


def report_bytes(report):
    if type(report) is not Report:
        raise ValueError("invalid_m7_report")
    return _encoded(report)


def _day(value):
    return value.astimezone(NY).date()


def _protect(start, end, blocked):
    try:
        validate_partition(start.isoformat(), end.isoformat(), "development")
    except ValueError as error:
        blocked.add("protected_holdout_overlap" if str(error) == "protected_holdout_overlap"
                    else "reversed_date_span")


def _unique(values):
    return len(values) == len(set(values))


def _session_days(calendar, blocked):
    days = tuple(_day(session.open_at) for session in calendar.sessions)
    if (not days or not _unique(days) or days != tuple(sorted(days))
            or any(s.open_at >= s.close_at or _day(s.open_at) != _day(s.close_at)
                   for s in calendar.sessions)):
        blocked.add("calendar_invalid")
        return ()
    _protect(days[0], days[-1], blocked)
    return days


def _decision_windows(study, design, days, blocked):
    """Return decision dependency windows and declared calendar-backed fold spans."""
    sessions = study.calendar.sessions
    indices = {day: i for i, day in enumerate(days)}
    windows, fold_spans, dependency_spans, months = {}, [], [], set()
    prior_end = None
    for fold in study.folds:
        _protect(fold.start, fold.end, blocked)
        if prior_end is not None and fold.start <= prior_end:
            blocked.add("fold_overlap")
        prior_end = fold.end
        if (fold.start not in indices or fold.end not in indices
                or fold.start > fold.end or not fold.decisions):
            blocked.add("fold_schedule_invalid")
            continue
        lower, upper = indices[fold.start], indices[fold.end]
        fold_spans.append((days[lower], days[upper]))
        times = tuple(d.at for d in fold.decisions)
        if not _unique(times) or times != tuple(sorted(times)):
            blocked.add("decision_schedule_invalid")
        for decision in fold.decisions:
            day = _day(decision.at)
            _protect(min(day, _day(decision.execute_at)), max(day, _day(decision.execute_at)), blocked)
            i = indices.get(day)
            if i is None or not fold.start <= day <= fold.end or decision.at in windows:
                blocked.add("decision_schedule_invalid")
                continue
            session = sessions[i]
            if not session.open_at <= decision.at < decision.execute_at <= session.close_at:
                blocked.add("execution_window_invalid")
            month = (day.year, day.month)
            if study.candidate == "trend" and month in months:
                blocked.add("monthly_schedule_conflict")
            months.add(month)
            left, right = i - design.lookback_sessions, i + design.holding_sessions
            if left < 0:
                blocked.add("lookback_incomplete")
            if right >= len(days):
                blocked.add("holding_incomplete")
            if 0 <= left <= right < len(days):
                windows[decision.at] = (left, i, right)
                lower, upper = min(lower, left), max(upper, right)
        dependency_spans.append((lower, upper))
    for (_, end), (start, _) in zip(dependency_spans, dependency_spans[1:]):
        if start <= end:
            blocked.add("fold_dependency_overlap")
        elif start - end - 1 < study.embargo_sessions:
            blocked.add("embargo_incomplete")
    return windows, fold_spans


def _study(study, as_of, intended_purpose, blocked):
    design = DESIGNS.get(study.candidate)
    if design is None:
        blocked.add("unsupported_candidate")
    if (study.purpose != PURPOSE or type(intended_purpose) is not str
            or intended_purpose != study.purpose):
        blocked.add("purpose_mismatch")
    if (not study.universe or len(study.universe) > 32 or not _unique(study.universe)):
        blocked.add("universe_invalid")
    if tuple(f.name for f in study.folds) != ("development", "validation", "holdout"):
        blocked.add("fold_set_invalid")
    if not _unique(study.scopes) or not _REQUIRED_SCOPES <= set(study.scopes) <= _SCOPES:
        blocked.add("usage_invalid")
    limits = study.limits
    if (not 0 < limits.max_drawdown_bp <= 10_000 or not limits.capacity_cents
            or not limits.min_effect_bp or not limits.total_cap_cents
            or any(value > 10_000 for value in
                   (limits.min_effect_bp, limits.spread_bp, limits.slippage_bp, limits.fee_bp))):
        blocked.add("economic_limits_invalid")
    if as_of is not None and min(study.retain_raw_until, study.retain_derived_until) <= _day(as_of):
        blocked.add("retention_conflict")
    days = _session_days(study.calendar, blocked)
    if days and as_of is not None and study.calendar.sessions[-1].close_at > as_of:
        blocked.add("calendar_after_evaluation")
    if design is not None and study.embargo_sessions < design.holding_sessions:
        blocked.add("embargo_incomplete")
    windows, fold_spans = _decision_windows(study, design, days, blocked) if days and design else ({}, ())
    return days, windows, fold_spans


def _sample(row, study, i, left, days, blocked, missing):
    timestamps = (
        row.observed_at, row.published_at, row.revision_at, row.provider_received_at,
        row.local_received_at, row.actions_at, row.benchmark_at, row.decision_at,
    )
    stamp_days = tuple(map(_day, timestamps))
    _protect(min(stamp_days), max(stamp_days), blocked)
    if (not row.observed_at <= row.published_at <= row.revision_at <= row.provider_received_at
            <= row.local_received_at <= row.decision_at
            or max(row.actions_at, row.benchmark_at) > row.decision_at
            or min(stamp_days) < days[left]):
        blocked.add("historical_availability")
    previous, current = study.calendar.sessions[i-1:i+1]
    if study.candidate == "trend":
        if row.observed_at != previous.close_at or row.earnings is not None:
            blocked.add("completed_observation_required")
        return

    earnings = row.earnings
    if earnings is None:
        missing.add("earnings_evidence_missing")
        return
    earnings_days = tuple(map(_day, (
        earnings.original_release_at, earnings.consensus_at, earnings.consensus_received_at,
    )))
    _protect(min(earnings_days), max(earnings_days), blocked)
    if (earnings.original_release_at != row.published_at or row.revision_at != row.published_at
            or not previous.open_at <= earnings.original_release_at < current.open_at):
        blocked.add("earnings_release_mismatch")
    if not (previous.open_at <= earnings.consensus_at <= earnings.consensus_received_at
            < earnings.original_release_at):
        blocked.add("earnings_consensus_late")
    if (earnings.actual_period, earnings.actual_basis) != (earnings.consensus_period, earnings.consensus_basis):
        blocked.add("earnings_basis_mismatch")


def _dataset(data, study, raw_hash, days, windows, fold_spans, blocked, missing):
    for field, code in (("source", "source_missing"), ("product", "product_missing"),
                        ("raw_sha256", "raw_digest_missing")):
        if getattr(data, field) is None:
            missing.add(code)
    if raw_hash is not None and data.raw_sha256 is not None and raw_hash != data.raw_sha256:
        blocked.add("raw_digest_mismatch")
    if data.provenance_ref != study.provenance_ref or data.calendar_sha256 != _digest(study.calendar):
        blocked.add("provenance_binding_mismatch")
    for flag in _DATA_FLAGS:
        value = getattr(data, flag)
        if value is None:
            missing.add(f"{flag}_missing")
        elif not value:
            blocked.add(f"{flag}_failed")

    instrument_ids = tuple(i.reference for i in data.instruments)
    universe = set(study.universe)
    if not _unique(instrument_ids) or set(instrument_ids) != universe:
        blocked.add("universe_mismatch")
    earliest = min((span[0] for span in windows.values()), default=None)
    latest = max((span[2] for span in windows.values()), default=None)
    session_days = set(days)
    for instrument in data.instruments:
        _protect(instrument.coverage_start, instrument.coverage_end, blocked)
        if (instrument.coverage_start not in session_days or instrument.coverage_end not in session_days
                or not instrument.eligible or instrument.listed_on > instrument.coverage_start
                or (instrument.delisted_on is not None and instrument.delisted_on < instrument.coverage_end)):
            blocked.add("instrument_coverage_invalid")
        if any(instrument.coverage_start > start or instrument.coverage_end < end
               for start, end in fold_spans):
            blocked.add("fold_coverage_incomplete")
        if earliest is not None and instrument.coverage_start > days[earliest]:
            blocked.add("lookback_incomplete")
        if latest is not None and instrument.coverage_end < days[latest]:
            blocked.add("holding_incomplete")

    seen = set()
    by_decision = {}
    for row in data.samples:
        key = (row.decision_at, row.instrument)
        window = windows.get(row.decision_at)
        if key in seen or row.instrument not in universe or window is None:
            blocked.add("observation_mapping_mismatch")
            for at in (row.observed_at, row.published_at, row.decision_at):
                _protect(_day(at), _day(at), blocked)
            continue
        seen.add(key)
        by_decision[row.decision_at] = by_decision.get(row.decision_at, 0) + 1
        left, i, _ = window
        _sample(row, study, i, left, days, blocked, missing)
    required_count = len(universe) if study.candidate == "trend" else 1
    if any(by_decision.get(at, 0) < required_count for at in windows):
        missing.add("observation_evidence_missing")


def _current(checkpoint, pin, at, blocked, missing):
    valid = _valid(checkpoint, Checkpoint)
    valid_pin = _valid(pin, Digest)
    if checkpoint is not None and not valid:
        blocked.add("checkpoint_invalid")
    if pin is not None and not valid_pin:
        blocked.add("checkpoint_pin_invalid")
    if checkpoint is None or pin is None:
        missing.add("current_anchor_missing")
    if not valid or not valid_pin:
        return None
    if _digest(checkpoint) != pin:
        blocked.add("checkpoint_pin_mismatch")
        return None
    if not checkpoint.sequence or at is None or not checkpoint.observed_at <= at < checkpoint.valid_until:
        blocked.add("checkpoint_stale")
        return None
    if not _unique([item.study_id for item in checkpoint.registry]):
        blocked.add("duplicate_study_identity")
        return None
    if not _unique(checkpoint.revoked) or not _unique(checkpoint.replayed):
        blocked.add("conflicting_checkpoint")
        return None
    if checkpoint.authority in checkpoint.revoked:
        blocked.add("revoked_authority")
        return None
    return checkpoint


def _registered(checkpoint, study, protocol, blocked, missing):
    registration = next((item for item in checkpoint.registry if item.study_id == study.study_id), None)
    if study.study_id in checkpoint.replayed:
        blocked.add("replayed_study")
    if study.study_id in checkpoint.revoked:
        blocked.add("revoked_study")
    if study.license_ref in checkpoint.revoked:
        blocked.add("rights_revoked")
    if study.reviewer in checkpoint.revoked:
        blocked.add("reviewer_access_mismatch")
    if registration is None:
        missing.add("study_registration_missing")
        return False
    if registration.study_sha256 != protocol:
        blocked.add("study_registration_mismatch")
        return False
    if study.provenance_ref in checkpoint.revoked:
        blocked.add("provenance_revoked")
    return True


def _same_dataset(submitted, known):
    # Omissions remain missing. Nonempty contradictory claims still fail.
    omitted = {name: None for name in _NULLABLE_CLAIMS
               if getattr(submitted, name) is None or getattr(known, name) is None}
    return replace(submitted, **omitted) == replace(known, **omitted)


def _rights(grant, study, known, checkpoint, at, blocked, missing):
    if grant is None:
        missing.add("rights_missing")
        return
    if (grant.reference != study.license_ref or grant.purpose != study.purpose
            or (known is not None and (
                grant.dataset_version != known.version
                or any(getattr(known, k) is not None and getattr(known, k) != getattr(grant, k)
                       for k in ("source", "product"))
            ))):
        blocked.add("rights_binding_mismatch")
    if {grant.reference, grant.issuer, grant.agreement_version} & set(checkpoint.revoked):
        blocked.add("rights_revoked")
    if not grant.valid_from <= checkpoint.observed_at <= at < grant.valid_until:
        blocked.add("rights_expired_or_unobserved")
    if not _unique(grant.scopes) or not set(study.scopes) <= set(grant.scopes) <= _SCOPES:
        blocked.add("rights_scope_mismatch")
    if grant.reviewer is None:
        missing.add("reviewer_access_missing")
    elif grant.reviewer != study.reviewer or grant.reviewer in checkpoint.revoked:
        blocked.add("reviewer_access_mismatch")
    if (study.retain_raw_until > grant.raw_until or study.retain_derived_until > grant.derived_until
            or max(grant.raw_until, grant.derived_until) >= _day(grant.valid_until)):
        blocked.add("retention_conflict")


def _costs(costs, limits, protocol, data_hash, at, blocked, missing):
    if costs is None:
        missing.add("costs_missing")
        return
    if costs.study_sha256 != protocol or (data_hash is not None and costs.dataset_sha256 != data_hash):
        blocked.add("cost_binding_mismatch")
    if at >= costs.valid_until:
        blocked.add("cost_quote_expired")
    values = (costs.provider_cents, costs.infrastructure_cents, costs.recurring_cents)
    caps = (limits.provider_cap_cents, limits.infrastructure_cap_cents, limits.recurring_cap_cents)
    known = [value for value in values if value is not None]
    if len(known) != len(values):
        missing.add("costs_unknown")
    if (any(value is not None and value > cap for value, cap in zip(values, caps))
            or sum(known) > limits.total_cap_cents):
        blocked.add("cost_cap_exceeded")


def _review(checkpoint, study, protocol, data_hash, blocked, missing):
    review = checkpoint.review
    if review is None:
        return "PENDING"
    if (review.study_sha256 != protocol or review.reviewer != study.reviewer
            or review.reviewer == checkpoint.authority or review.reviewer in checkpoint.revoked
            or review.reviewed_at > checkpoint.observed_at
            or (study.calendar.sessions and review.reviewed_at < study.calendar.sessions[-1].close_at)
            or (data_hash is not None and review.dataset_sha256 != data_hash)):
        blocked.add("review_binding_mismatch")
        return "INVALID"
    if data_hash is None:
        missing.add("review_dataset_unverified")
        return "PENDING"
    return "RECORDED_SYNTHETIC_ONLY"


def qualify(study, dataset, *, raw_bytes, checkpoint, expected_checkpoint_sha256,
            as_of, intended_purpose):
    """Evaluate review eligibility under an independently pinned synthetic checkpoint."""
    blocked, missing = set(), set()
    at = as_of if _valid(as_of, datetime) else None
    if at is None:
        blocked.add("evaluation_time_invalid")
    current = _current(checkpoint, expected_checkpoint_sha256, at, blocked, missing)

    raw_hash = None
    if raw_bytes is None:
        missing.add("raw_bytes_missing")
    elif type(raw_bytes) is not bytes or not 0 < len(raw_bytes) <= _MAX_RAW:
        blocked.add("raw_bytes_invalid")
    else:
        raw_hash = sha256(raw_bytes).hexdigest()

    protocol, submitted_hash = None, None
    review_status = "PENDING"
    valid_data = _valid(dataset, Dataset)
    if dataset is None:
        missing.add("dataset_missing")
    elif not valid_data:
        blocked.add("dataset_invalid")
    else:
        submitted_hash = _digest(dataset)
    if not _valid(study, Study):
        blocked.add("study_invalid")
    else:
        protocol = _digest(study)
        days, windows, fold_spans = _study(study, at, intended_purpose, blocked)
        if valid_data:
            _dataset(dataset, study, raw_hash, days, windows, fold_spans, blocked, missing)
        if current is not None and _registered(current, study, protocol, blocked, missing):
            known = current.dataset
            known_hash = None
            if known is None:
                missing.add("independent_provenance_missing")
            else:
                known_hash = _digest(known)
                if valid_data and not _same_dataset(dataset, known):
                    blocked.add("dataset_mismatch")
                if (study.calendar.sessions and
                        study.calendar.sessions[-1].close_at > current.observed_at):
                    blocked.add("checkpoint_precedes_coverage")
                if {known.source, known.product, known.version, known.provenance_ref} & set(current.revoked):
                    blocked.add("provenance_revoked")
                _dataset(known, study, raw_hash, days, windows, fold_spans, blocked, missing)
            _rights(current.rights, study, known, current, at, blocked, missing)
            _costs(current.costs, study.limits, protocol, known_hash, at, blocked, missing)
            review_status = _review(current, study, protocol, known_hash, blocked, missing)
    status = "BLOCKED" if blocked else "DRAFT" if missing else "ELIGIBLE_FOR_REVIEW"
    return Report(status, tuple(sorted(blocked | missing)) or ("synthetic_review_checks_satisfied",),
                  tuple(sorted(missing)), protocol, submitted_hash,
                  expected_checkpoint_sha256 if current is not None else None, at, review_status)
