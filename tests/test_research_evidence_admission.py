"""Synthetic metadata only. No market observations or external approval issuers."""
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
import ast
import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest


def api():
    return importlib.import_module('lockean_lite.research.evidence_admission')


T = datetime(2026, 6, 1, 14, tzinfo=timezone.utc)


def fixture(**changes):
    m = api()
    evidence = [m.Evidence(k, 'fixture-'+k, str(i)*64)
                for i, k in enumerate(m.KINDS, 1)]
    p = m.Package('lite.admission-package.v1', 'synthetic-spy', '1',
                  'synthetic_metadata_research', m.DateRange('2026-06-01','2026-06-01'),
                  T-timedelta(minutes=2), T-timedelta(minutes=1), T-timedelta(minutes=1),
                  T, evidence)
    p = replace(p, **changes)
    return issue(p)


def issue(package, reviews=None, **approval_changes):
    """Simulated trusted issuer only; never issuance of a real authorization."""
    m = api()
    if reviews is None:
        reviews = [m.Review(e.kind, m.identity(e), 'VERIFIED', 'sentinel-fixture')
                   for e in package.evidence]
    approval = m.Approval('lite.admission-approval.v1','approval-1','founder-fixture',
                         m.identity(package),package.purpose,package.dates,
                         T-timedelta(days=1),T+timedelta(days=1),reviews)
    approval = replace(approval, **approval_changes)
    context = m.TrustContext('lite.admission-context.v1','fixture-context','1',
                             ['founder-fixture'],['sentinel-fixture'],[approval])
    return dict(package=package, approval_id=approval.approval_id,
                trusted_context=context, expected_context_sha256=m.identity(context), as_of=T)


def result(bundle, status, reason):
    r = api().admit(**bundle)
    assert r.status == status
    assert reason in r.reasons
    assert r.evidence_kind == 'SYNTHETIC_ONLY'
    assert r.data_authenticity == 'UNVERIFIED' and r.options_eligibility == 'UNKNOWN'
    assert r.profitability == 'UNKNOWN' and r.downstream_authority == 'NONE'
    return r


def test_valid_synthetic_metadata_admitted_and_immutable():
    m=api(); b=fixture()
    r=result(b,'ADMITTED','all_required_synthetic_checks_satisfied')
    with pytest.raises(FrozenInstanceError): r.status='PASS'
    with pytest.raises(FrozenInstanceError): b['package'].purpose='other'
    original=list(b['package'].evidence)
    p=replace(b['package'],evidence=original)
    original.clear()
    assert len(p.evidence)==4
    approvals=list(b['trusted_context'].approvals)
    c=replace(b['trusted_context'],approvals=approvals)
    approvals.clear()
    assert len(c.approvals)==1
    assert m.identity(c)==m.identity(b['trusted_context'])


def test_matching_self_hash_does_not_substitute_trusted_context():
    m=api(); original=fixture()
    forged=fixture(package_id='attacker-package')
    # Attacker reissues matching package/approval/context hashes; trusted pin stays put.
    forged['expected_context_sha256']=original['expected_context_sha256']
    result(forged,'REJECTED','trust_anchor_mismatch')


def test_package_cannot_carry_its_own_approval_or_anchor():
    b=fixture()
    for field in ('approval','trusted_context','expected_context_sha256'):
        with pytest.raises(TypeError): replace(b['package'],**{field:'self-issued'})


@pytest.mark.parametrize('field,value,reason', [
    ('package_id','other','package_identity_mismatch'),
    ('purpose','options_profitability','unsupported_purpose'),
    ('version','2','package_identity_mismatch'),
])
def test_package_changes_cannot_reuse_approval(field,value,reason):
    b=fixture(); b['package']=replace(b['package'],**{field:value})
    result(b,'REJECTED',reason)


@pytest.mark.parametrize('kind', ['provenance','availability','licensing','retention'])
def test_altered_evidence_rejected(kind):
    b=fixture()
    rows=tuple(replace(e,artifact_sha256='f'*64) if e.kind==kind else e
               for e in b['package'].evidence)
    b['package']=replace(b['package'],evidence=rows)
    result(b,'REJECTED','package_identity_mismatch')


@pytest.mark.parametrize('kind', ['provenance','availability','licensing','retention'])
def test_missing_evidence_is_unknown(kind):
    b=fixture(); p=b['package']
    result(issue(replace(p,evidence=tuple(e for e in p.evidence if e.kind!=kind))),
           'UNKNOWN',kind+'_evidence_missing')


@pytest.mark.parametrize('kind', ['provenance','availability','licensing','retention'])
@pytest.mark.parametrize('verdict,status,suffix', [('UNVERIFIED','UNKNOWN','review_unverified'),
                                                 ('DENIED','REJECTED','review_denied')])
def test_independent_review_dispositions(kind,verdict,status,suffix):
    b=fixture(); a=b['trusted_context'].approvals[0]
    reviews=tuple(replace(r,verdict=verdict) if r.kind==kind else r for r in a.reviews)
    result(issue(b['package'],reviews),status,kind+'_'+suffix)


def test_missing_review_unknown_and_wrong_evidence_digest_rejected():
    m=api(); b=fixture(); a=b['trusted_context'].approvals[0]
    result(issue(b['package'],a.reviews[1:]),'UNKNOWN','provenance_review_missing')
    reviews=(replace(a.reviews[0],evidence_sha256='f'*64),)+a.reviews[1:]
    result(issue(b['package'],reviews),'REJECTED','provenance_evidence_mismatch')


@pytest.mark.parametrize('mode', ['no-context','no-pin','malformed-pin'])
def test_missing_or_invalid_anchor(mode):
    b=fixture()
    if mode=='no-context': b['trusted_context']=None
    if mode=='no-pin': b['expected_context_sha256']=None
    if mode=='malformed-pin': b['expected_context_sha256']='DO_NOT_DISCLOSE'
    result(b,'REJECTED' if mode=='malformed-pin' else 'UNKNOWN',
           'invalid_trust_anchor' if mode=='malformed-pin' else 'trust_context_unverified')


@pytest.mark.parametrize('mode,reason', [('issuer','untrusted_issuer'),('reviewer','untrusted_reviewer'),
                                       ('approval','approval_not_found')])
def test_wrong_authority(mode,reason):
    m=api(); b=fixture(); context=b['trusted_context']
    if mode=='issuer': context=replace(context,approved_issuers=['other'])
    if mode=='reviewer': context=replace(context,approved_reviewers=['other'])
    b['trusted_context']=context; b['expected_context_sha256']=m.identity(context)
    if mode=='approval': b['approval_id']='forged-approval'
    result(b,'REJECTED',reason)


@pytest.mark.parametrize('mode,reason', [('purpose','approval_purpose_mismatch'),
                                       ('dates','unauthorized_dates')])
def test_wrong_approval_bindings(mode,reason):
    m=api(); b=fixture()
    changes={'purpose':'other'} if mode=='purpose' else {'dates':m.DateRange('2026-06-02','2026-06-02')}
    result(issue(b['package'],**changes),'REJECTED',reason)


@pytest.mark.parametrize('delta,reason', [(-90000,'approval_not_yet_valid'),(86400,'approval_expired')])
def test_expiration_is_explicit_and_end_exclusive(delta,reason):
    b=fixture(); b['as_of']=T+timedelta(seconds=delta)
    result(b,'REJECTED',reason)


def test_explicit_evaluation_time_required():
    b=fixture()
    for bad in (None,'now',T.replace(tzinfo=None),T.replace(fold=1)):
        b['as_of']=bad
        result(b,'REJECTED','invalid_evaluation_time')


@pytest.mark.parametrize('field,value,reason', [
    ('event_start',T,'invalid_chronology'),
    ('available_at',T-timedelta(minutes=3),'invalid_chronology'),
    ('captured_at',T-timedelta(minutes=2),'invalid_chronology'),
    ('captured_at',T+timedelta(seconds=1),'invalid_chronology'),
])
def test_chronology_violations(field,value,reason):
    result(fixture(**{field:value}),'REJECTED',reason)


def test_availability_time_missing_unknown_even_if_review_verified():
    result(fixture(available_at=None),'UNKNOWN','historical_availability_unverified')


@pytest.mark.parametrize('start,end', [('2026-10-20','2026-12-31'),
                                    ('2026-10-19','2027-01-04'),('2026-12-31','2027-01-01')])
def test_protected_declared_ranges(start,end):
    m=api()
    result(fixture(dates=m.DateRange(start,end)),'REJECTED','protected_holdout_overlap')


@pytest.mark.parametrize('stamp', ['2026-10-20T04:00:00+00:00','2027-01-01T04:59:00+00:00'])
def test_protected_event_and_availability_instants(stamp):
    t=datetime.fromisoformat(stamp)
    result(fixture(event_start=t,event_end=t+timedelta(seconds=1)),
           'REJECTED','protected_holdout_overlap')
    result(fixture(available_at=t),'REJECTED','protected_holdout_overlap')


def test_enclosing_event_interval_rejected():
    result(fixture(event_start=datetime(2026,10,19,14,tzinfo=timezone.utc),
                   event_end=datetime(2027,1,4,14,tzinfo=timezone.utc)),
           'REJECTED','protected_holdout_overlap')


def test_rejected_over_unknown_even_with_missing_context():
    b=fixture(available_at=None); b['trusted_context']=None
    b['package']=replace(b['package'],purpose='trade_execution')
    result(b,'REJECTED','unsupported_purpose')


def test_denied_rights_over_unknown_availability():
    b=fixture(available_at=None); reviews=b['trusted_context'].approvals[0].reviews
    reviews=tuple(replace(r,verdict='DENIED') if r.kind=='licensing' else r for r in reviews)
    result(issue(b['package'],reviews),'REJECTED','licensing_review_denied')


@pytest.mark.parametrize('which', ['evidence','reviews','approvals','issuers'])
def test_duplicates_fail_closed(which):
    m=api(); b=fixture(); c=b['trusted_context']; a=c.approvals[0]
    if which=='evidence':
        b=issue(replace(b['package'],evidence=b['package'].evidence*2))
    elif which=='reviews': b=issue(b['package'],a.reviews*2)
    else:
        c=replace(c,**({'approvals':c.approvals*2} if which=='approvals' else
                       {'approved_issuers':c.approved_issuers*2}))
        b['trusted_context']=c; b['expected_context_sha256']=m.identity(c)
    result(b,'REJECTED','duplicate_metadata')


@pytest.mark.parametrize('field,value', [('version',1),('provider','alpaca'),('feed','iex'),
                                       ('package_id',True),('schema','future')])
def test_strict_package_types_and_synthetic_scope(field,value):
    b=fixture()
    with pytest.raises(ValueError): replace(b['package'],**{field:value})


def test_versioned_context_and_approval_and_review_types():
    m=api(); b=fixture()
    for obj in (b['trusted_context'],b['trusted_context'].approvals[0]):
        with pytest.raises(ValueError): replace(obj,schema='future')
    with pytest.raises(ValueError): m.Review('licensing','a'*64,'PASS','reviewer')
    with pytest.raises(ValueError): m.Evidence('options_profit','ref','a'*64)


def test_report_determinism_and_safe_diagnostics():
    m=api(); b=fixture(); r=m.admit(**b)
    raw=m.report_bytes(r)
    assert raw==m.report_bytes(m.admit(**fixture()))
    assert hashlib.sha256(raw).hexdigest()==m.identity(r)
    b['approval_id']='CONFIDENTIAL_SENTINEL_TOKEN'
    bad=m.admit(**b)
    assert b'CONFIDENTIAL_SENTINEL_TOKEN' not in m.report_bytes(bad)
    assert b'founder-fixture' not in raw and b'synthetic-spy' not in raw


def test_no_network_credentials_production_or_downstream_dependencies(monkeypatch):
    import socket
    m=api()
    def forbidden(*args,**kwargs): raise AssertionError('network prohibited')
    monkeypatch.setattr(socket,'socket',forbidden)
    monkeypatch.setattr(socket,'create_connection',forbidden)
    assert m.admit(**fixture()).status=='ADMITTED'
    tree=ast.parse(inspect.getsource(m))
    imports=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import): imports.update(a.name for a in n.names)
        if isinstance(n,ast.ImportFrom): imports.add(n.module)
    assert imports <= {'dataclasses','datetime','re','data_contracts','validation'}
    calls={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    assert not calls & {'open','eval','exec','qualify','evaluate'}


def test_does_not_mutate_inputs():
    m=api(); b=fixture(); before=m.identity(b['package']),m.identity(b['trusted_context'])
    m.admit(**b)
    assert before==(m.identity(b['package']),m.identity(b['trusted_context']))


@pytest.mark.parametrize('day,start', [('2026-10-19','2026-10-20T03:56:00+00:00'),
                                      ('2027-01-01','2027-01-01T05:00:00+00:00'),
                                      ('2026-03-06','2026-03-06T14:30:00+00:00'),
                                      ('2026-03-09','2026-03-09T13:30:00+00:00')])
def test_permitted_new_york_dates_and_dst(day,start):
    m=api(); b=fixture(); t=datetime.fromisoformat(start); capture=t+timedelta(minutes=3)
    p=replace(b['package'],dates=m.DateRange(day,day),event_start=t,
              event_end=t+timedelta(minutes=2),available_at=t+timedelta(minutes=2),captured_at=capture)
    b=issue(p,valid_from=t-timedelta(days=1),valid_until=t+timedelta(days=1))
    b['as_of']=capture
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')


def test_capture_and_administrative_expiry_are_not_market_observations():
    b=fixture(); capture=datetime(2026,11,1,14,tzinfo=timezone.utc)
    p=replace(b['package'],captured_at=capture)
    b=issue(p,valid_until=capture+timedelta(days=1)); b['as_of']=capture
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')


def test_event_outside_approved_dates_rejected():
    m=api()
    result(fixture(dates=m.DateRange('2026-06-02','2026-06-02')),
           'REJECTED','event_outside_declared_dates')


def test_changed_reference_with_same_artifact_hash_cannot_reuse_approval():
    b=fixture(); p=b['package']
    p=replace(p,evidence=(replace(p.evidence[0],reference='unreviewed-copy'),)+p.evidence[1:])
    b['package']=p
    result(b,'REJECTED','package_identity_mismatch')


def test_approval_valid_from_is_inclusive_and_until_exclusive():
    b=fixture(); b=issue(b['package'],valid_from=T,valid_until=T+timedelta(seconds=1))
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')
    b['as_of']=T+timedelta(seconds=1)
    result(b,'REJECTED','approval_expired')


def test_empty_approval_registry_and_collection_bounds_fail_closed():
    m=api(); b=fixture(); c=replace(b['trusted_context'],approvals=[])
    b['trusted_context']=c; b['expected_context_sha256']=m.identity(c)
    result(b,'REJECTED','approval_not_found')
    with pytest.raises(ValueError): replace(b['package'],evidence=b['package'].evidence*33)
    with pytest.raises(ValueError): replace(c,approved_reviewers=['r']*129)


def test_invalid_package_and_evaluation_types_do_not_leak_inputs():
    m=api(); b=fixture(); b['package']={'unexpected':'synthetic-redaction-marker'}
    r=result(b,'REJECTED','invalid_package')
    assert b'synthetic-redaction-marker' not in m.report_bytes(r)


def test_typed_identity_and_report_schema_remain_separate_from_m1():
    m=api(); b=fixture(); r=m.admit(**b)
    assert r.schema=='lite.research.evidence-admission.v1'
    assert m.identity(b['package'])!=m.identity(b['trusted_context'])
    assert r.evaluated_at==T
    with pytest.raises(ValueError): replace(b['package'],version=1.0)
    with pytest.raises(ValueError): replace(b['package'],dates=('2026-06-01','2026-06-01'))


@pytest.mark.parametrize('bad_context', [{}, 'not-a-context', 123])
def test_invalid_context_is_rejected_even_when_pin_is_missing(bad_context):
    b=fixture(); b['trusted_context']=bad_context; b['expected_context_sha256']=None
    result(b,'REJECTED','invalid_trust_context')


def test_full_caller_control_is_not_external_authentication():
    # The library has no OS isolation or signature service. Replacing BOTH the
    # supposedly trusted inputs is outside its security boundary, not a valid pin attack.
    b=fixture(package_id='different-simulated-issuer-package')
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')


@pytest.mark.parametrize('field', ['event_start','event_end','available_at'])
@pytest.mark.parametrize('missing_context', [False, True])
def test_minimum_utc_timestamp_rejected_without_projection_exception(field, missing_context):
    m=api(); b=fixture(); minimum=datetime.min.replace(tzinfo=timezone.utc)
    b=issue(replace(b['package'],**{field:minimum}))
    if missing_context:
        b['trusted_context']=None
    r=result(b,'REJECTED','timestamp_out_of_range')
    assert b'OverflowError' not in m.report_bytes(r)


def test_representable_new_york_boundary_and_one_microsecond_before():
    m=api(); b=fixture(); minimum=datetime.min.replace(tzinfo=timezone.utc)
    # Compute the local-range boundary from installed IANA timezone rules, not
    # today's UTC offset; New York has historical second-resolution offsets.
    boundary=minimum-m.NY.utcoffset(minimum)
    p=replace(b['package'],dates=m.DateRange('0001-01-01','0001-01-01'),
              event_start=boundary,event_end=boundary+timedelta(minutes=1),
              available_at=boundary+timedelta(minutes=1),captured_at=boundary+timedelta(minutes=2))
    b=issue(p,valid_from=minimum,valid_until=minimum+timedelta(days=1));b['as_of']=p.captured_at
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')
    b=issue(replace(p,event_start=boundary-timedelta(microseconds=1)),
            valid_from=minimum,valid_until=minimum+timedelta(days=1));b['as_of']=p.captured_at
    result(b,'REJECTED','timestamp_out_of_range')


def test_maximum_utc_timestamp_remains_representable_in_new_york():
    m=api(); b=fixture(); maximum=datetime.max.replace(tzinfo=timezone.utc)
    p=replace(b['package'],dates=m.DateRange('9999-12-31','9999-12-31'),
              event_start=maximum-timedelta(minutes=3),event_end=maximum-timedelta(minutes=2),
              available_at=maximum-timedelta(minutes=2),captured_at=maximum-timedelta(minutes=1))
    b=issue(p,valid_from=maximum-timedelta(days=1),valid_until=maximum);b['as_of']=p.captured_at
    result(b,'ADMITTED','all_required_synthetic_checks_satisfied')


def test_unrelated_projection_programming_error_is_not_suppressed(monkeypatch):
    from datetime import tzinfo
    m=api(); b=fixture()
    class BrokenZone(tzinfo):
        def fromutc(self, value): raise RuntimeError('synthetic-programming-error')
    monkeypatch.setattr(m,'NY',BrokenZone())
    with pytest.raises(RuntimeError,match='^synthetic-programming-error$'):
        m.admit(**b)


def test_bad_context_plus_extreme_timestamp_still_rejected():
    b=fixture(event_start=datetime.min.replace(tzinfo=timezone.utc))
    b['trusted_context']={};b['expected_context_sha256']=None
    r=result(b,'REJECTED','timestamp_out_of_range')
    assert 'invalid_trust_context' in r.reasons


def test_context_substitution_keeps_original_pin_even_for_forged_matching_package():
    m=api(); original=fixture(); forged=fixture(package_id='forged-but-consistent')
    assert m.identity(forged['trusted_context'])==forged['expected_context_sha256']
    forged['expected_context_sha256']=original['expected_context_sha256']
    result(forged,'REJECTED','trust_anchor_mismatch')
    # Deliberately replacing BOTH trusted inputs remains outside authentication.
    forged['expected_context_sha256']=m.identity(forged['trusted_context'])
    result(forged,'ADMITTED','all_required_synthetic_checks_satisfied')


def test_valid_report_matches_frozen_m2_identity():
    m=api(); r=m.admit(**fixture())
    assert m.identity(r)=='8dceca7227bc6bad9846a2954ed98eeef6fc5efb053bcee78abc15d013c93adf'
