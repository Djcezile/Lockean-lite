"""Generated synthetic evidence only."""
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from functools import cache
from hashlib import sha256
from importlib import import_module
import os
import subprocess
import sys

import pytest

from lockean_lite.research.validation import NY


RAW = b"generated M7 evidence fixture"
AS_OF = datetime(2026, 6, 1, 16, tzinfo=timezone.utc)


def api():
    return import_module("lockean_lite.research.empirical_readiness")


def utc(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), NY).astimezone(timezone.utc)


@cache
def calendar(start=date(2021, 1, 1)):
    m = api()
    weekdays = (start + timedelta(days=i) for i in range(1300))
    return m.Calendar(tuple(m.Session(utc(day, 9, 30), utc(day, 16))
                            for day in weekdays if day.weekday() < 5))


def local(at):
    return at.astimezone(NY).date()


@cache
def fixture(candidate="trend", start=date(2021, 1, 1)):
    m = api()
    cal = calendar(start)
    sessions = cal.sessions
    indexes = (258, 558, 858)
    if candidate == "earnings":
        indexes = (20, 100, 180)
    folds, samples = [], []
    for name, i in zip(("development", "validation", "holdout"), indexes):
        at = sessions[i].open_at + timedelta(minutes=30)
        decision = m.Decision(at, at + timedelta(minutes=15))
        folds.append(m.Fold(name, local(at), local(at), (decision,)))
        event = sessions[i-1].close_at
        published = event + timedelta(minutes=1)
        earnings = None
        if candidate == "earnings":
            earnings = m.Earnings(published, event - timedelta(hours=1), event - timedelta(minutes=30),
                                  "syn-q1", "syn-q1", "syn-as-issued", "syn-estimate-v1",
                                  "syn-basis", "syn-basis")
        samples.append(m.Sample("syn-instrument", at, event, published,
                                published + timedelta(minutes=1), published + timedelta(minutes=2),
                                event, event, published, earnings))
    study = m.Study(
        "syn-study", candidate, ("syn-instrument",), cal, tuple(folds),
        "synthetic-empirical-readiness",
        ("internal_research", "commercial_research", "non_display", "retain_raw",
         "retain_derived", "reviewer_access"),
        date(2026, 7, 1), date(2026, 8, 1), "syn-reviewer", "syn-provenance", "syn-license",
        m.Limits(10, 100_000, 1000, 5, 5, 1, 50_000, 20_000, 30_000, 100_000), 21,
    )
    instrument = m.Instrument("syn-instrument", "syn-security-id", local(sessions[0].open_at),
                              None, local(sessions[0].open_at), local(sessions[-1].close_at), True)
    data = m.Dataset("syn-source", "syn-feed", "syn-v1", sha256(RAW).hexdigest(),
                     "syn-provenance", m.identity(cal), (instrument,), tuple(samples),
                     True, True, True, True, True)
    rights = m.Rights("syn-license", "syn-issuer", "syn-terms", "syn-source", "syn-feed", "syn-v1",
                      study.purpose, study.scopes, "syn-reviewer", AS_OF - timedelta(days=1),
                      AS_OF + timedelta(days=120), date(2026, 7, 2), date(2026, 8, 2))
    costs = m.Costs(m.identity(study), m.identity(data), 40_000, 15_000, 20_000,
                    AS_OF + timedelta(days=1))
    checkpoint = m.Checkpoint("syn-controller", 1, AS_OF - timedelta(hours=1),
                              AS_OF + timedelta(hours=1),
                              (m.Registration(study.study_id, m.identity(study)),),
                              data, rights, costs)
    return study, data, checkpoint


def rebind(study, data, checkpoint):
    m = api()
    costs = checkpoint.costs
    if costs is not None:
        costs = replace(costs, study_sha256=m.identity(study), dataset_sha256=m.identity(data))
    return replace(checkpoint, registry=(m.Registration(study.study_id, m.identity(study)),),
                   dataset=data, costs=costs)


def run(study, data, checkpoint, **overrides):
    m = api()
    args = dict(raw_bytes=RAW, checkpoint=checkpoint, expected_checkpoint_sha256=m.identity(checkpoint),
                as_of=AS_OF, intended_purpose=study.purpose)
    args.update(overrides)
    return m.qualify(study, data, **args)


@pytest.mark.parametrize("candidate", ["trend", "earnings"])
def test_synthetic_readiness_without_prior_approval(candidate):
    m = api()
    study, data, checkpoint = fixture(candidate)
    report = run(study, data, checkpoint)
    assert report.status == "ELIGIBLE_FOR_REVIEW", report.reasons
    assert report.review_status == "PENDING"
    assert report.protocol_sha256 == m.identity(study)
    assert report.real_world_authenticity == "UNVERIFIED"
    assert report.empirical_authority == report.trading_authority == "NONE"
    assert report.profitability == "UNKNOWN"
    assert m.report_bytes(report) == m.report_bytes(run(study, data, checkpoint))
    assert RAW not in m.report_bytes(report)


@pytest.mark.parametrize(("change", "status", "reason"), [
    ({"source": None}, "DRAFT", "source_missing"),
    ({"product": None}, "DRAFT", "product_missing"),
    ({"source": "syn-forged"}, "BLOCKED", "dataset_mismatch"),
    ({"raw_sha256": "a" * 64}, "BLOCKED", "raw_digest_mismatch"),
    ({"instruments": ()}, "BLOCKED", "universe_mismatch"),
    ({"point_in_time_universe": None}, "DRAFT", "point_in_time_universe_missing"),
    ({"point_in_time_universe": False}, "BLOCKED", "point_in_time_universe_failed"),
    ({"delistings_complete": False}, "BLOCKED", "delistings_complete_failed"),
    ({"revisions_as_known": False}, "BLOCKED", "revisions_as_known_failed"),
])
def test_dataset_contract(change, status, reason):
    study, data, checkpoint = fixture()
    changed = replace(data, **change)
    if reason != "dataset_mismatch":
        checkpoint = rebind(study, changed, checkpoint)
    report = run(study, changed, checkpoint)
    assert report.status == status
    assert reason in report.reasons


def test_unpinned_declarations_and_trusted_raw_comparison():
    study, data, checkpoint = fixture()
    assert run(study, data, checkpoint, expected_checkpoint_sha256=None).status == "DRAFT"
    missing = replace(data, raw_sha256=None)
    assert run(study, missing, checkpoint).status == "DRAFT"
    report = run(study, missing, checkpoint, raw_bytes=b"synthetic substitution")
    assert report.status == "BLOCKED"
    assert "raw_digest_mismatch" in report.reasons
    assert "raw_digest_missing" in report.missing
    assert "raw_bytes_missing" in run(study, data, checkpoint, raw_bytes=None).missing


@pytest.mark.parametrize(("change", "reason"), [
    ({"valid_until": AS_OF}, "checkpoint_stale"),
    ({"revoked": ("syn-controller",)}, "revoked_authority"),
    ({"replayed": ("syn-study",)}, "replayed_study"),
])
def test_checkpoint_rejects_invalid_current_state(change, reason):
    study, data, checkpoint = fixture()
    report = run(study, data, replace(checkpoint, **change))
    assert report.status == "BLOCKED"
    assert reason in report.reasons
    assert "checkpoint_pin_mismatch" in run(
        study, data, checkpoint, expected_checkpoint_sha256="0" * 64).reasons


def test_duplicate_study_registration_and_unauthorized_purpose():
    study, data, checkpoint = fixture()
    duplicate = replace(checkpoint, registry=checkpoint.registry * 2)
    assert "duplicate_study_identity" in run(study, data, duplicate).reasons
    assert "purpose_mismatch" in run(study, data, checkpoint, intended_purpose="syn-other").reasons


@pytest.mark.parametrize(("field", "reason"), [
    ("published_at", "historical_availability"),
    ("local_received_at", "historical_availability"),
    ("actions_at", "historical_availability"),
    ("revision_at", "historical_availability"),
])
def test_decision_time_availability(field, reason):
    study, data, checkpoint = fixture()
    sample = replace(data.samples[0], **{field: data.samples[0].decision_at + timedelta(seconds=1)})
    data = replace(data, samples=(sample, *data.samples[1:]))
    assert reason in run(study, data, rebind(study, data, checkpoint)).reasons


@pytest.mark.parametrize(("field", "reason"), [
    ("consensus_at", "earnings_consensus_late"),
    ("consensus_received_at", "earnings_consensus_late"),
    ("original_release_at", "earnings_release_mismatch"),
    ("consensus_period", "earnings_basis_mismatch"),
])
def test_earnings_provenance(field, reason):
    study, data, checkpoint = fixture("earnings")
    row = data.samples[0]
    value = "syn-wrong-quarter" if field == "consensus_period" else row.decision_at
    earnings = replace(row.earnings, **{field: value})
    changed = replace(data, samples=(replace(row, earnings=earnings), *data.samples[1:]))
    report = run(study, changed, rebind(study, changed, checkpoint))
    assert report.status == "BLOCKED"
    assert reason in report.reasons


def test_insufficient_lookback_and_incomplete_holding():
    study, data, checkpoint = fixture()
    ins = data.instruments[0]
    short = replace(ins, coverage_start=study.folds[0].start, coverage_end=study.folds[-1].end)
    data = replace(data, instruments=(short,))
    report = run(study, data, rebind(study, data, checkpoint))
    assert {"lookback_incomplete", "holding_incomplete"} <= set(report.reasons)


def test_folds_and_embargo_use_dependency_windows():
    study, data, checkpoint = fixture()
    overlap = replace(study, folds=(replace(study.folds[0], end=study.folds[1].end), *study.folds[1:]))
    assert "fold_overlap" in run(overlap, data, rebind(overlap, data, checkpoint)).reasons
    tight = replace(study, embargo_sessions=30)
    assert "embargo_incomplete" in run(tight, data, rebind(tight, data, checkpoint)).reasons


@pytest.mark.parametrize("start", [date(2026, 10, 20), date(2026, 10, 19), date(2026, 12, 31)])
def test_protected_new_york_dates_and_straddling(start):
    study, data, checkpoint = fixture(start=start)
    assert "protected_holdout_overlap" in run(study, data, checkpoint).reasons


@pytest.mark.parametrize(("mode", "status", "reason"), [
    ("missing_rights", "DRAFT", "rights_missing"),
    ("commercial", "BLOCKED", "rights_scope_mismatch"),
    ("reviewer", "BLOCKED", "reviewer_access_mismatch"),
    ("retention", "BLOCKED", "retention_conflict"),
    ("cost_cap", "BLOCKED", "cost_cap_exceeded"),
    ("unknown_cost", "DRAFT", "costs_unknown"),
])
def test_rights_cost_and_retention(mode, status, reason):
    study, data, checkpoint = fixture()
    rights = checkpoint.rights
    changes = {
        "missing_rights": {"rights": None},
        "commercial": {"rights": replace(rights, scopes=tuple(s for s in rights.scopes
                                                             if s != "commercial_research"))},
        "reviewer": {"rights": replace(rights, reviewer="syn-other")},
        "retention": {"rights": replace(rights, derived_until=date(2026, 7, 1))},
        "cost_cap": {"costs": replace(checkpoint.costs, provider_cents=50_001)},
        "unknown_cost": {"costs": replace(checkpoint.costs, provider_cents=None)},
    }
    report = run(study, data, replace(checkpoint, **changes[mode]))
    assert report.status == status
    assert reason in report.reasons


def test_review_is_bound_and_never_grants_authority():
    m = api()
    study, data, checkpoint = fixture()
    review = m.Review(m.identity(study), m.identity(data), study.reviewer,
                      checkpoint.observed_at - timedelta(minutes=1))
    report = run(study, data, replace(checkpoint, review=review))
    assert report.review_status == "RECORDED_SYNTHETIC_ONLY"
    assert report.empirical_authority == "NONE"
    invalid = replace(checkpoint, review=replace(review, study_sha256="0" * 64))
    assert "review_binding_mismatch" in run(study, data, invalid).reasons


def test_import_is_offline_and_non_operational():
    script = """
import sys
from lockean_lite.research import empirical_readiness
assert not any(k.startswith(('alpaca', 'openai', 'requests')) for k in sys.modules)
assert all(not k.startswith('lockean_lite.') or k.startswith('lockean_lite.research')
           for k in sys.modules)
"""
    subprocess.run([sys.executable, "-B", "-c", script], check=True,
                   env={**os.environ, "PYTHONPATH": "src"})


def test_coverage_cannot_extend_past_the_frozen_calendar():
    study, data, checkpoint = fixture()
    instrument = replace(data.instruments[0], coverage_end=local(AS_OF) + timedelta(days=2))
    changed = replace(data, instruments=(instrument,))
    report = run(study, changed, rebind(study, changed, checkpoint))
    assert report.status == "BLOCKED"
    assert "instrument_coverage_invalid" in report.reasons


def test_review_cannot_predate_the_frozen_evidence_coverage():
    m = api()
    study, data, checkpoint = fixture()
    review = m.Review(m.identity(study), m.identity(data), study.reviewer,
                      study.calendar.sessions[-1].close_at - timedelta(seconds=1))
    report = run(study, data, replace(checkpoint, review=review))
    assert report.status == "BLOCKED"
    assert "review_binding_mismatch" in report.reasons


def test_unregistered_study_cannot_borrow_trusted_raw_digest():
    study, data, checkpoint = fixture()
    report = run(study, replace(data, raw_sha256=None), replace(checkpoint, registry=()),
                 raw_bytes=b"another synthetic document")
    assert report.status == "DRAFT"
    assert "study_registration_missing" in report.missing
    assert "raw_digest_mismatch" not in report.reasons


def test_known_over_budget_component_wins_over_unknown_cost():
    study, data, checkpoint = fixture()
    costs = replace(checkpoint.costs, provider_cents=None, recurring_cents=30_001)
    report = run(study, data, replace(checkpoint, costs=costs))
    assert report.status == "BLOCKED"
    assert "cost_cap_exceeded" in report.reasons
    assert "costs_unknown" in report.missing


def test_instrument_scheme_cannot_be_substituted():
    study, data, checkpoint = fixture()
    changed = replace(data, instruments=(replace(data.instruments[0], scheme="syn-other-scheme"),))
    assert "dataset_mismatch" in run(study, changed, checkpoint).reasons


def test_invalid_digest_and_operational_authority_cannot_be_smuggled_in():
    study, data, checkpoint = fixture()
    invalid = replace(data, raw_sha256="invalid-private-marker")
    report = run(study, invalid, checkpoint)
    assert report.status == "BLOCKED"
    assert "dataset_invalid" in report.reasons
    assert report.trading_authority == "NONE"
    assert b"invalid-private-marker" not in api().report_bytes(report)


def test_intended_purpose_requires_an_exact_contract_value():
    class UntrustedPurpose(str):
        pass

    study, data, checkpoint = fixture()
    report = run(study, data, checkpoint, intended_purpose=UntrustedPurpose(study.purpose))
    assert report.status == "BLOCKED"
    assert "purpose_mismatch" in report.reasons


def test_known_license_and_reviewer_revocations_survive_missing_grant():
    study, data, checkpoint = fixture()
    changed = replace(checkpoint, rights=None, revoked=(study.license_ref, study.reviewer))
    report = run(study, data, changed)
    assert report.status == "BLOCKED"
    assert {"rights_revoked", "reviewer_access_mismatch"} <= set(report.reasons)
    assert "rights_missing" in report.missing


def _session_date(study, index):
    return local(study.calendar.sessions[index].open_at)


def _decision_index(study, fold):
    return next(i for i, session in enumerate(study.calendar.sessions)
                if local(session.open_at) == local(fold.decisions[0].at))


def test_full_fold_tail_requires_coverage_beyond_last_holding_horizon():
    study, data, checkpoint = fixture()
    holdout = study.folds[-1]
    holding_end = _decision_index(study, holdout) + api().DESIGNS["trend"].holding_sessions
    holdout = replace(holdout, end=_session_date(study, holding_end + 11))
    study = replace(study, folds=(*study.folds[:-1], holdout))
    instrument = replace(data.instruments[0], coverage_end=_session_date(study, holding_end))
    short = replace(data, instruments=(instrument,))
    report = run(study, short, rebind(study, short, checkpoint))
    assert report.status == "BLOCKED"
    assert report.reasons == ("fold_coverage_incomplete",)
    assert run(study, data, rebind(study, data, checkpoint)).status == "ELIGIBLE_FOR_REVIEW"


def test_full_fold_start_requires_coverage_before_first_lookback():
    study, data, checkpoint = fixture()
    development = study.folds[0]
    lookback_start = _decision_index(study, development) - api().DESIGNS["trend"].lookback_sessions
    development = replace(development, start=_session_date(study, lookback_start - 2))
    study = replace(study, folds=(development, *study.folds[1:]))
    instrument = replace(data.instruments[0], coverage_start=_session_date(study, lookback_start))
    short = replace(data, instruments=(instrument,))
    report = run(study, short, rebind(study, short, checkpoint))
    assert report.status == "BLOCKED"
    assert report.reasons == ("fold_coverage_incomplete",)


def test_missing_coverage_between_decisions_blocks_even_with_witnesses():
    m = api()
    study, data, checkpoint = fixture("earnings")
    first = study.folds[0].decisions[0]
    second_index = _decision_index(study, study.folds[0]) + 30
    second_at = study.calendar.sessions[second_index].open_at + timedelta(minutes=30)
    shift = second_at - first.at
    second = m.Decision(second_at, first.execute_at + shift)
    development = replace(study.folds[0], end=local(second.at), decisions=(first, second))
    study = replace(study, folds=(development, *study.folds[1:]))
    row = data.samples[0]
    earnings = replace(row.earnings, original_release_at=row.earnings.original_release_at + shift,
                       consensus_at=row.earnings.consensus_at + shift,
                       consensus_received_at=row.earnings.consensus_received_at + shift)
    dates = ("decision_at", "observed_at", "published_at", "provider_received_at",
             "local_received_at", "actions_at", "benchmark_at", "revision_at")
    witness = replace(row, earnings=earnings, **{name: getattr(row, name) + shift for name in dates})
    covered = replace(data, samples=(*data.samples, witness))
    assert run(study, covered, rebind(study, covered, checkpoint)).status == "ELIGIBLE_FOR_REVIEW"
    short = replace(covered, instruments=(replace(data.instruments[0],
                                                  coverage_end=_session_date(study, second_index-1)),))
    report = run(study, short, rebind(study, short, checkpoint))
    assert report.status == "BLOCKED"
    assert "fold_coverage_incomplete" in report.reasons


@pytest.mark.parametrize("case", ["invalid_fold", "invalid_calendar"])
def test_invalid_fold_or_calendar_cannot_establish_coverage(case):
    study, data, checkpoint = fixture()
    if case == "invalid_fold":
        fold = replace(study.folds[0], end=study.folds[0].start - timedelta(days=1))
        study = replace(study, folds=(fold, *study.folds[1:]))
        reason = "reversed_date_span"
    else:
        sessions = study.calendar.sessions
        calendar = replace(study.calendar, sessions=(sessions[0], *sessions))
        study = replace(study, calendar=calendar)
        data = replace(data, calendar_sha256=api().identity(calendar))
        reason = "calendar_invalid"
    report = run(study, data, rebind(study, data, checkpoint))
    assert report.status == "BLOCKED"
    assert reason in report.reasons
    assert "fold_coverage_incomplete" not in report.reasons


@pytest.mark.parametrize("revoked", [False, True])
def test_exact_registered_provenance_revocation_survives_absent_datasets(revoked):
    study, _, checkpoint = fixture()
    checkpoint = replace(checkpoint, dataset=None, revoked=(study.provenance_ref,) if revoked else ())
    report = run(study, None, checkpoint)
    assert report.status == ("BLOCKED" if revoked else "DRAFT")
    assert ("provenance_revoked" in report.reasons) is revoked
    assert {"dataset_missing", "independent_provenance_missing"} <= set(report.missing)


@pytest.mark.parametrize(("target", "reason"), [
    ("dataset", "dataset_invalid"),
    ("study", "study_invalid"),
    ("checkpoint", "checkpoint_invalid"),
    ("nested_sample", "dataset_invalid"),
    ("nested_fold", "study_invalid"),
    ("nested_rights", "checkpoint_invalid"),
])
def test_partial_exact_class_records_fail_closed_deterministically(target, reason):
    m = api()
    study, data, checkpoint = fixture()
    pin = m.identity(checkpoint)
    if target == "dataset":
        data = object.__new__(m.Dataset)
        object.__setattr__(data, "source", "syn-incomplete")
    elif target == "study":
        study = object.__new__(m.Study)
    elif target == "checkpoint":
        checkpoint = object.__new__(m.Checkpoint)
    elif target == "nested_sample":
        data = replace(data, samples=(object.__new__(m.Sample),))
    elif target == "nested_fold":
        study = replace(study, folds=(object.__new__(m.Fold),))
    else:
        checkpoint = replace(checkpoint, rights=object.__new__(m.Rights))
    args = dict(raw_bytes=RAW, checkpoint=checkpoint, expected_checkpoint_sha256=pin,
                as_of=AS_OF, intended_purpose="synthetic-empirical-readiness")
    report = m.qualify(study, data, **args)
    assert report.status == "BLOCKED"
    assert reason in report.reasons
    assert m.report_bytes(report) == m.report_bytes(m.qualify(study, data, **args))
