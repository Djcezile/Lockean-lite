from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import subprocess
import sys

import pytest

from lockean_lite.research import provenance_qualification as m5


def at(hour, minute=0):
    return datetime(2026, 6, 1, hour, minute, tzinfo=timezone.utc)


RAW = b"generated M5 document\n"
RAW_DIGEST = sha256(RAW).hexdigest()


def fixture():
    facts = m5.Facts(
        reference="syn-raw", series="syn-series", source="syn-source",
        product="syn-feed", instrument_scheme="syn-scheme", instrument="syn-instrument",
        raw_sha256=RAW_DIGEST, event_at=at(9), first_published_at=at(10),
        published_at=at(10), received_at=at(11), collected_at=at(12),
        lineage=(m5.Step("syn-transformer", "syn-normalize", RAW_DIGEST, "b" * 64),),
    )
    grant = m5.Grant(
        "syn-agreement", "syn-v1", "syn-issuer", facts.source, facts.product,
        ("internal_research", "model_development", "retain_data"), ("development",),
        at(0), at(23), at(22),
    )
    intent = m5.Intent("development", ("internal_research",), at(13))
    approval = m5.Approval(
        "syn-approval", "syn-signer", m5.identity(facts), m5.identity(grant),
        m5.identity(intent), at(12), at(23),
    )
    package = m5.Package(facts, grant, intent, approval.reference, "syn-policy")
    checkpoint = m5.Checkpoint(
        "syn-policy", 1, at(13), at(23),
        (m5.Entry(facts, grant, approval),), ("syn-issuer",),
        ("syn-transformer",), ("syn-signer",),
    )
    return package, checkpoint


def run(package, state, **overrides):
    kwargs = dict(
        raw_bytes=RAW, checkpoint=state, expected_checkpoint_sha256=m5.identity(state),
        as_of=at(14), intended_use=fixture()[0].intent,
    )
    kwargs.update(overrides)
    return m5.qualify(package, **kwargs)


def bound(package, checkpoint):
    approval = replace(
        checkpoint.entries[0].approval, facts_sha256=m5.identity(package.facts),
        grant_sha256=m5.identity(package.grant), intent_sha256=m5.identity(package.intent),
    )
    return replace(checkpoint, entries=(m5.Entry(package.facts, package.grant, approval),))


def test_synthetic_qualification_and_public_audit():
    package, checkpoint = fixture()
    result = run(package, checkpoint)
    assert result.status == "QUALIFIED_SYNTHETIC_ONLY"
    assert result.source_identity == "syn-source"
    assert result.product_identity == "syn-feed"
    assert result.rights_status == result.chronology_status == "QUALIFIED_SYNTHETIC_ONLY"
    assert result.real_world_authenticity == "UNVERIFIED"
    assert result.profitability == "UNKNOWN"
    assert result.downstream_authority == "NONE"
    assert result.package_sha256 == m5.identity(package)
    assert result.checkpoint_sha256 == m5.identity(checkpoint)
    assert result.evaluated_at == at(14)
    assert m5.report_bytes(result) == m5.report_bytes(run(package, checkpoint))
    assert RAW.strip() not in m5.report_bytes(result)


@pytest.mark.parametrize(("changes", "reason"), [
    ({"source": None}, "source_identity_missing"),
    ({"reference": None}, "raw_reference_missing"),
    ({"first_published_at": None}, "first_publication_missing"),
    ({"published_at": None}, "publication_missing"),
    ({"received_at": None}, "receipt_missing"),
    ({"collected_at": None}, "collection_missing"),
    ({"lineage": None}, "lineage_missing"),
])
def test_missing_claims(changes, reason):
    package, checkpoint = fixture()
    report = run(replace(package, facts=replace(package.facts, **changes)), checkpoint)
    assert report.status == "UNKNOWN"
    assert reason in report.missing


@pytest.mark.parametrize(("changes", "reason"), [
    ({"source": "syn-forged"}, "source_mismatch"),
    ({"product": "syn-other-feed"}, "source_mismatch"),
    ({"instrument": "syn-other"}, "instrument_mismatch"),
    ({"instrument_scheme": "syn-other"}, "instrument_mismatch"),
    ({"raw_sha256": "a" * 64}, "raw_digest_mismatch"),
    ({"published_at": at(10, 1)}, "availability_mismatch"),
    ({"lineage": ()}, "lineage_mismatch"),
    ({"source": "external-token-do-not-echo"}, "invalid_package"),
    ({"collected_at": at(12).replace(tzinfo=None)}, "invalid_package"),
])
def test_substitution_and_malformed_metadata(changes, reason):
    package, checkpoint = fixture()
    report = run(replace(package, facts=replace(package.facts, **changes)), checkpoint)
    assert report.status == "REJECTED"
    assert reason in report.reasons
    assert b"external-token-do-not-echo" not in m5.report_bytes(report)


@pytest.mark.parametrize(("changes", "reason"), [
    ({"event_at": at(11)}, "chronology_conflict"),
    ({"published_at": at(14)}, "publication_after_decision"),
    ({"received_at": at(14)}, "receipt_after_decision"),
    ({"collected_at": at(14)}, "collection_after_decision"),
    ({"event_at": datetime.min.replace(tzinfo=timezone.utc)}, "timestamp_out_of_range"),
    ({"event_at": datetime.max.replace(tzinfo=timezone.utc)}, "chronology_conflict"),
])
def test_chronology_even_without_anchor(changes, reason):
    package, checkpoint = fixture()
    report = run(replace(package, facts=replace(package.facts, **changes)), checkpoint,
                 expected_checkpoint_sha256=None)
    assert report.status == "REJECTED"
    assert reason in report.reasons
    assert "current_anchor_missing" in report.missing


def test_normalizes_fixed_offsets():
    package, checkpoint = fixture()
    offset = timezone(timedelta(hours=-4))
    local = replace(package, facts=replace(package.facts, event_at=at(9).astimezone(offset)))
    assert m5.identity(local) == m5.identity(package)
    assert m5.report_bytes(run(local, checkpoint)) == m5.report_bytes(run(package, checkpoint))


@pytest.mark.parametrize(("event", "decision", "rejected"), [
    ("2026-10-20T03:59:58+00:00", "2026-10-20T03:59:59+00:00", False),
    ("2026-10-20T03:59:59+00:00", "2026-10-20T04:00:00+00:00", True),
    ("2027-01-01T04:59:59+00:00", "2027-01-01T05:00:00+00:00", True),
    ("2027-01-01T05:00:00+00:00", "2027-01-01T05:00:01+00:00", False),
    ("2026-10-20T03:59:59+00:00", "2027-01-01T05:00:00+00:00", True),
])
def test_new_york_holdout(event, decision, rejected):
    package, checkpoint = fixture()
    event, decision = map(datetime.fromisoformat, (event, decision))
    facts = replace(package.facts, event_at=event, first_published_at=decision,
                    published_at=decision, received_at=decision, collected_at=decision)
    intent = replace(package.intent, decision_at=decision)
    package = replace(package, facts=facts, intent=intent)
    report = run(package, checkpoint, intended_use=intent, as_of=decision,
                 expected_checkpoint_sha256=None)
    assert ("protected_holdout_overlap" in report.reasons) is rejected


def test_revision_uses_current_release_and_cannot_replay_superseded_record():
    original, checkpoint = fixture()
    revised = replace(original, facts=replace(
        original.facts, reference="syn-revision", revision=2, supersedes="syn-raw",
        published_at=at(13, 1), received_at=at(13, 2), collected_at=at(13, 3)))
    current = bound(revised, checkpoint)
    report = run(revised, current)
    assert report.status == "REJECTED"
    assert "publication_after_decision" in report.reasons
    assert "superseded_evidence" in run(original, current).reasons


def test_late_observation_can_qualify_only_after_collection():
    package, checkpoint = fixture()
    package = replace(package, facts=replace(package.facts, event_at=at(0)))
    assert run(package, bound(package, checkpoint)).status == "QUALIFIED_SYNTHETIC_ONLY"


def test_self_assertion_and_stale_or_conflicting_checkpoint():
    package, checkpoint = fixture()
    assert run(package, checkpoint, expected_checkpoint_sha256=None).status == "UNKNOWN"
    assert run(package, checkpoint, checkpoint=None).status == "UNKNOWN"
    assert "checkpoint_pin_mismatch" in run(
        package, checkpoint, expected_checkpoint_sha256="0" * 64).reasons
    stale = replace(checkpoint, valid_until=at(14))
    assert "checkpoint_stale" in run(package, stale).reasons
    conflicting = replace(checkpoint, entries=checkpoint.entries * 2)
    assert "conflicting_current_state" in run(package, conflicting).reasons


def test_duplicate_replay_and_revoked_authorities():
    package, checkpoint = fixture()
    for change, reason in [
        ({"replayed": ("syn-raw",)}, "replayed_evidence"),
        ({"revoked": ("syn-signer",)}, "untrusted_approval_signer"),
        ({"signers": ()}, "untrusted_approval_signer"),
        ({"revoked": ("syn-agreement",)}, "revoked_rights"),
        ({"issuers": ()}, "untrusted_rights_issuer"),
        ({"transformers": ()}, "untrusted_transformer"),
    ]:
        assert reason in run(package, replace(checkpoint, **change)).reasons


def test_custody_and_transformation_integrity():
    package, checkpoint = fixture()
    assert "raw_bytes_missing" in run(package, checkpoint, raw_bytes=None).missing
    assert "raw_digest_mismatch" in run(package, checkpoint, raw_bytes=b"substitution").reasons
    facts = replace(package.facts, lineage=(
        replace(package.facts.lineage[0], input_sha256="d" * 64),))
    broken = replace(package, facts=facts)
    assert "lineage_conflict" in run(broken, bound(broken, checkpoint)).reasons


@pytest.mark.parametrize(("scope", "reason"), [
    ("commercial_research", "usage_not_granted"),
    ("redistribute", "usage_not_granted"),
    ("external_reporting", "usage_not_granted"),
    ("store_derived_features", "usage_not_granted"),
])
def test_rights_are_purpose_and_scope_specific(scope, reason):
    package, checkpoint = fixture()
    intent = replace(package.intent, scopes=(scope,))
    package = replace(package, intent=intent)
    assert reason in run(package, bound(package, checkpoint), intended_use=intent).reasons


def test_grant_missing_forged_expired_and_wrong_purpose():
    package, checkpoint = fixture()
    assert "rights_missing" in run(replace(package, grant=None), checkpoint).missing
    forged = replace(package, grant=replace(package.grant, issuer="syn-fake-issuer"))
    assert "rights_mismatch" in run(forged, checkpoint).reasons
    expired = replace(package, grant=replace(package.grant, valid_until=at(14), retain_until=at(14)))
    assert "rights_time" in run(expired, bound(expired, checkpoint)).reasons
    intent = replace(package.intent, purpose="validation")
    wrong = replace(package, intent=intent)
    assert "purpose_not_granted" in run(wrong, bound(wrong, checkpoint), intended_use=intent).reasons
    assert "intended_use_mismatch" in run(wrong, checkpoint).reasons


def test_retention_is_bounded_and_requires_a_deadline():
    package, checkpoint = fixture()
    intent = replace(package.intent, scopes=("retain_data",))
    missing = replace(package, intent=intent)
    assert "retention_deadline_missing" in run(
        missing, bound(missing, checkpoint), intended_use=intent).missing
    intent = replace(intent, retain_until=at(22, 1))
    excessive = replace(package, intent=intent)
    assert "retention_not_granted" in run(
        excessive, bound(excessive, checkpoint), intended_use=intent).reasons


def test_import_has_no_operational_or_external_dependencies():
    script = """
import sys
from lockean_lite.research import provenance_qualification
assert not any(name.startswith(('alpaca', 'openai')) for name in sys.modules)
assert all(not name.startswith('lockean_lite.') or name.startswith(
    'lockean_lite.research') for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", script], check=True, env={"PYTHONPATH": "src"})

def test_revoked_policy_or_source_rejects_even_if_snapshot_is_pinned():
    package, checkpoint = fixture()
    for identity, reason in [
        ("syn-policy", "revoked_policy"), ("syn-source", "revoked_source"),
        ("syn-raw", "revoked_evidence"),
    ]:
        report = run(package, replace(checkpoint, revoked=(identity,)))
        assert report.status == "REJECTED"
        assert reason in report.reasons


def test_known_contradictions_win_when_submission_omits_times_or_rights():
    package, checkpoint = fixture()
    known = replace(package.facts, published_at=at(14))
    restricted = replace(package.grant, scopes=())
    checkpoint = replace(checkpoint, entries=(m5.Entry(known, restricted, None),))
    incomplete = replace(package, facts=replace(package.facts, published_at=None), grant=None)
    report = run(incomplete, checkpoint)
    assert report.status == "REJECTED"
    assert {"publication_after_decision", "usage_not_granted"} <= set(report.reasons)


def test_current_pin_rejects_an_obsolete_but_still_effective_checkpoint():
    package, old = fixture()
    current = replace(old, sequence=2, revoked=("syn-signer",))
    report = run(package, old, expected_checkpoint_sha256=m5.identity(current))
    assert report.status == "REJECTED"
    assert "checkpoint_pin_mismatch" in report.reasons


def test_audit_distinguishes_metadata_from_synthetic_attestation():
    package, checkpoint = fixture()
    verified = run(package, checkpoint)
    declared = run(package, checkpoint, expected_checkpoint_sha256=None)
    assert verified.evidence_basis == "PINNED_SYNTHETIC_SNAPSHOT"
    assert declared.evidence_basis == "METADATA_UNVERIFIED"
    assert verified.purpose == package.intent.purpose
    assert verified.requested_scopes == package.intent.scopes


def test_duplicate_observation_under_new_reference_is_rejected():
    package, checkpoint = fixture()
    renamed = replace(package, facts=replace(package.facts, reference="syn-alias", series="syn-alias"))
    assert "duplicate_observation" in run(renamed, checkpoint).reasons


def test_post_revision_decision_can_use_a_checkpointed_revision():
    package, checkpoint = fixture()
    facts = replace(package.facts, revision=2, supersedes="syn-older", published_at=at(10, 1))
    revised = replace(package, facts=facts)
    assert run(revised, bound(revised, checkpoint)).status == "QUALIFIED_SYNTHETIC_ONLY"
