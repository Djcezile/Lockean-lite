"""Ephemeral test keys only; no providers or real approvals."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import ast
import hashlib
import importlib
import inspect
import runpy
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

T=datetime(2026,6,1,14,tzinfo=timezone.utc)

def api():
    return importlib.import_module('lockean_lite.research.signed_approvals')

def fixture():
    s=api()
    ns=runpy.run_path(str(Path(__file__).with_name('test_research_evidence_admission.py')))
    base=ns['fixture']()
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    key=s.PublicKey('issuer-1','key-1',public.hex(),hashlib.sha256(public).hexdigest(),
                    'ACTIVE','synthetic-evidence-approval',T-timedelta(days=2),T+timedelta(days=2))
    policy=s.TrustPolicy('lite.signing-policy.v1','policy-1','1',(key,),
                         ('sentinel-fixture',),'synthetic_metadata_research',
                         s.DateRange('2026-06-01','2026-06-01'),
                         T-timedelta(days=2),T+timedelta(days=2),3*86400)
    approval=base['trusted_context'].approvals[0]
    context=replace(base['trusted_context'],approved_issuers=('issuer-1',),
                    approvals=(replace(approval,issuer_id='issuer-1'),))
    message=s.ApprovalMessage('lite.signed-approval-message.v1','synthetic-evidence-approval',
                             policy.policy_id,policy.version,'issuer-1','key-1',key.fingerprint,
                             'approval-1',T-timedelta(days=1),context)
    return dict(package=base['package'],envelope=s.sign(message,private),policy=policy,
                expected_policy_sha256=s.identity(policy),as_of=T),private

def outcome(b,status,reason):
    r=api().verify_admission(**b)
    assert r.status==status and reason in r.reasons
    assert r.evidence_kind=='SYNTHETIC_ONLY' and r.data_authenticity=='UNVERIFIED'
    assert r.options_eligibility==r.profitability=='UNKNOWN' and r.downstream_authority=='NONE'
    return r

def resign(b,key,**changes):
    b=dict(b);b['envelope']=api().sign(replace(b['envelope'].message,**changes),key)
    return b

def repolicy(b,**changes):
    s=api();b=dict(b);b['policy']=replace(b['policy'],**changes)
    b['expected_policy_sha256']=s.identity(b['policy'])
    return b

def test_valid_signature_determinism_and_stateless_replay():
    s=api();b,key=fixture()
    r=outcome(b,'ADMITTED','all_required_synthetic_checks_satisfied')
    assert r.signature_status=='VERIFIED'
    assert s.report_bytes(r)==s.report_bytes(s.verify_admission(**b))
    assert s.sign(b['envelope'].message,key)==b['envelope']
    assert hashlib.sha256(s.report_bytes(r)).hexdigest()==s.identity(r)

@pytest.mark.parametrize('field,value', [('approval_id','other'),('issuer_id','other'),
 ('key_id','other'),('policy_version','obsolete'),('artifact_type','trade-authorization'),
 ('schema','future'),('issued_at',T)])
def test_modified_signed_message_rejects(field,value):
    b,_=fixture();b['envelope']=replace(b['envelope'],message=replace(b['envelope'].message,**{field:value}))
    assert api().verify_admission(**b).status=='REJECTED'

def test_wrong_private_key_rejects():
    b,_=fixture();b['envelope']=api().sign(b['envelope'].message,Ed25519PrivateKey.generate())
    outcome(b,'REJECTED','invalid_signature')

@pytest.mark.parametrize('signature',[None,'','xx','00','0'*128])
def test_missing_or_malformed_signature(signature):
    b,_=fixture();b['envelope']=replace(b['envelope'],signature_hex=signature)
    assert api().verify_admission(**b).status=='REJECTED'

@pytest.mark.parametrize('algorithm',['HS256','none','Ed448'])
def test_unsupported_algorithm(algorithm):
    b,_=fixture();b['envelope']=replace(b['envelope'],algorithm=algorithm)
    outcome(b,'REJECTED','unsupported_algorithm')

def test_self_supplied_root_and_policy_substitution():
    b,_=fixture()
    for field in ('public_key','policy','expected_policy_sha256'):
        with pytest.raises(TypeError):replace(b['envelope'],**{field:'attacker'})
    forged,_=fixture();forged['expected_policy_sha256']=b['expected_policy_sha256']
    outcome(forged,'REJECTED','trust_policy_mismatch')

def test_package_tampering_and_cross_package_replay():
    b,_=fixture();b['package']=replace(b['package'],package_id='other-package')
    outcome(b,'REJECTED','package_identity_mismatch')

@pytest.mark.parametrize('mode,reason',[('issuer','unknown_issuer'),('key','unknown_key'),
 ('revoked','key_revoked'),('fingerprint','key_identity_mismatch'),('purpose','unapproved_signing_purpose')])
def test_policy_constraints(mode,reason):
    b,_=fixture();k=b['policy'].keys[0]
    if mode=='issuer':k=replace(k,issuer_id='other')
    if mode=='key':k=replace(k,key_id='other')
    if mode=='revoked':k=replace(k,status='REVOKED')
    if mode=='fingerprint':k=replace(k,fingerprint='0'*64)
    if mode=='purpose':k=replace(k,signing_purpose='other')
    outcome(repolicy(b,keys=(k,)),'REJECTED',reason)

@pytest.mark.parametrize('delta,reason',[(-86401,'approval_not_yet_valid'),(86400,'approval_expired')])
def test_approval_expiry(delta,reason):
    b,_=fixture();b['as_of']=T+timedelta(seconds=delta)
    outcome(b,'REJECTED',reason)

@pytest.mark.parametrize('mode,reason',[('expired','key_expired'),('future','key_not_yet_valid')])
def test_key_validity(mode,reason):
    b,_=fixture();k=b['policy'].keys[0]
    k=replace(k,valid_until=T) if mode=='expired' else replace(k,valid_from=T+timedelta(seconds=1))
    outcome(repolicy(b,keys=(k,)),'REJECTED',reason)

def test_revocation_rotation_and_obsolete_policy():
    s=api();b,key=fixture();old=dict(b)
    current=repolicy(b,version='2');old['expected_policy_sha256']=current['expected_policy_sha256']
    outcome(old,'REJECTED','trust_policy_mismatch')
    k=b['policy'].keys[0];rotated=replace(k,key_id='rotated-key')
    b=repolicy(b,keys=(replace(k,status='REVOKED'),rotated))
    outcome(b,'REJECTED','key_revoked')
    b=resign(b,key,key_id='rotated-key')
    outcome(b,'ADMITTED','all_required_synthetic_checks_satisfied')

@pytest.mark.parametrize('mode,reason',[('purpose','unsupported_purpose'),('dates','unauthorized_dates'),
 ('reviewer','untrusted_reviewer'),('lifetime','approval_lifetime_exceeded')])
def test_approval_policy_bindings(mode,reason):
    b,_=fixture()
    changes={'purpose':'other'} if mode=='purpose' else {'dates':api().DateRange('2026-06-02','2026-06-02')} if mode=='dates' else {'approved_reviewers':('other',)} if mode=='reviewer' else {'max_approval_seconds':1}
    outcome(repolicy(b,**changes),'REJECTED',reason)

@pytest.mark.parametrize('field',['purpose','dates','review','reference'])
def test_signed_evidence_context_tampering(field):
    s=api();b,_=fixture();e=b['envelope'];a=e.message.context.approvals[0]
    if field=='review':a=replace(a,reviews=(replace(a.reviews[0],verdict='DENIED'),)+a.reviews[1:])
    elif field=='dates':a=replace(a,dates=s.DateRange('2026-06-02','2026-06-02'))
    elif field=='reference':a=replace(a,reviews=(replace(a.reviews[0],evidence_sha256='f'*64),)+a.reviews[1:])
    else:a=replace(a,purpose='other')
    b['envelope']=replace(e,message=replace(e.message,context=replace(e.message.context,approvals=(a,))))
    outcome(b,'REJECTED','invalid_signature')

def test_signed_unknown_and_rejected_precedence():
    b,key=fixture();a=b['envelope'].message.context.approvals[0]
    a=replace(a,reviews=(replace(a.reviews[0],verdict='UNVERIFIED'),)+a.reviews[1:])
    b=resign(b,key,context=replace(b['envelope'].message.context,approvals=(a,)))
    assert outcome(b,'UNKNOWN','provenance_review_unverified').signature_status=='VERIFIED'
    b['envelope']=replace(b['envelope'],signature_hex='0'*128)
    outcome(b,'REJECTED','invalid_signature')

@pytest.mark.parametrize('mode',['keys','approvals','reviewers'])
def test_duplicate_metadata(mode):
    b,key=fixture()
    if mode=='keys':b=repolicy(b,keys=b['policy'].keys*2)
    elif mode=='reviewers':b=repolicy(b,approved_reviewers=b['policy'].approved_reviewers*2)
    else:
        c=b['envelope'].message.context;b=resign(b,key,context=replace(c,approvals=c.approvals*2))
    outcome(b,'REJECTED','duplicate_metadata')

@pytest.mark.parametrize('bad',[None,'now',T.replace(tzinfo=None),T.replace(fold=1)])
def test_invalid_evaluation_time(bad):
    b,_=fixture();b['as_of']=bad
    outcome(b,'REJECTED','invalid_evaluation_time')

def test_extreme_and_protected_enclosing_timestamps():
    s=api();b,key=fixture();p=replace(b['package'],event_start=datetime.min.replace(tzinfo=timezone.utc))
    a=b['envelope'].message.context.approvals[0];a=replace(a,package_sha256=s.m2.identity(p))
    b=resign(dict(b,package=p),key,context=replace(b['envelope'].message.context,approvals=(a,)))
    outcome(b,'REJECTED','timestamp_out_of_range')
    b,key=fixture();dates=s.DateRange('2026-10-19','2027-01-04');p=replace(b['package'],dates=dates)
    a=b['envelope'].message.context.approvals[0];a=replace(a,dates=dates,package_sha256=s.m2.identity(p))
    b=resign(dict(b,package=p),key,context=replace(b['envelope'].message.context,approvals=(a,)))
    outcome(b,'REJECTED','protected_holdout_overlap')

def test_no_unsigned_legacy_bypass(monkeypatch):
    s=api();b,_=fixture();b['envelope']=None
    def forbidden(*args,**kwargs):raise AssertionError('legacy bypass')
    monkeypatch.setattr(s.m2,'admit',forbidden)
    outcome(b,'REJECTED','missing_signed_approval')

def test_domain_separation_and_typed_fields():
    s=api();b,key=fixture();message=b['envelope'].message;raw=s.signing_bytes(message)
    assert raw.startswith(b'LOCKEAN-LITE-SYNTHETIC-APPROVAL-V1\x00')
    signature=key.sign(b'OTHER-DOMAIN\x00'+raw)
    outcome(dict(b,envelope=replace(b['envelope'],signature_hex=signature.hex())),'REJECTED','invalid_signature')
    assert raw==s.signing_bytes(message)
    with pytest.raises(ValueError):replace(b['policy'],max_approval_seconds=True)

def test_no_private_export_network_or_operational_imports():
    s=api();b,_=fixture()
    assert b'private' not in s.canonical(s.public_snapshot(b['envelope'])).lower()
    assert b'issuer-1' not in s.report_bytes(s.verify_admission(**b))
    tree=ast.parse(inspect.getsource(s))
    imports=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
        if isinstance(n,ast.ImportFrom):
            imports.extend([n.module] if n.module is not None else [a.name for a in n.names])
    assert not any(x.split('.')[0] in ('os','socket','requests','alpaca','urllib') for x in imports)
    assert not any(isinstance(n,ast.Attribute) and n.attr=='private_bytes' for n in ast.walk(tree))

def test_m2_report_identity_preserved():
    s=api();ns=runpy.run_path(str(Path(__file__).with_name('test_research_evidence_admission.py')))
    assert s.m2.identity(s.m2.admit(**ns['fixture']()))=='8dceca7227bc6bad9846a2954ed98eeef6fc5efb053bcee78abc15d013c93adf'

def test_rfc8032_public_verification_vector_without_private_key_import():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    public=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    signature=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f'
                            'b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    Ed25519PublicKey.from_public_bytes(public).verify(signature,b'')

def test_actual_key_rotation_with_new_ephemeral_key():
    s=api();b,_=fixture();new=Ed25519PrivateKey.generate()
    public=new.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    old=b['policy'].keys[0]
    rotated=replace(old,key_id='key-2',public_key_hex=public.hex(),
                    fingerprint=hashlib.sha256(public).hexdigest())
    b=repolicy(b,keys=(replace(old,status='REVOKED'),rotated))
    outcome(b,'REJECTED','key_revoked')
    b=resign(b,new,key_id='key-2',key_fingerprint=rotated.fingerprint)
    outcome(b,'ADMITTED','all_required_synthetic_checks_satisfied')

@pytest.mark.parametrize('mode',['missing','wrong-type','wrong-pin'])
def test_missing_untrusted_policy(mode):
    b,_=fixture()
    if mode=='missing':b['policy']=None
    if mode=='wrong-type':b['policy']={}
    if mode=='wrong-pin':b['expected_policy_sha256']='0'*64
    assert api().verify_admission(**b).status=='REJECTED'

@pytest.mark.parametrize('mode',['start','end','issuance'])
def test_policy_validity_and_issuance_constraints(mode):
    b,key=fixture()
    if mode=='start':b=repolicy(b,valid_from=T+timedelta(seconds=1))
    if mode=='end':b=repolicy(b,valid_until=T)
    if mode=='issuance':b=resign(b,key,issued_at=T+timedelta(seconds=1))
    assert api().verify_admission(**b).status=='REJECTED'

def test_validity_start_inclusive_and_end_exclusive():
    b,key=fixture();a=b['envelope'].message.context.approvals[0]
    a=replace(a,valid_from=T,valid_until=T+timedelta(seconds=1))
    c=replace(b['envelope'].message.context,approvals=(a,))
    b=resign(b,key,context=c,issued_at=T)
    outcome(b,'ADMITTED','all_required_synthetic_checks_satisfied')
    b['as_of']=T+timedelta(seconds=1)
    outcome(b,'REJECTED','approval_expired')

def test_signature_failure_never_calls_legacy_even_if_evidence_unknown(monkeypatch):
    s=api();b,_=fixture();b['package']=replace(b['package'],available_at=None)
    b['envelope']=replace(b['envelope'],signature_hex='0'*128)
    def forbidden(*args,**kwargs):raise AssertionError('unsigned fallback')
    monkeypatch.setattr(s.m2,'admit',forbidden)
    outcome(b,'REJECTED','invalid_signature')

def test_known_signed_evidence_denial_remains_rejected():
    b,key=fixture();a=b['envelope'].message.context.approvals[0]
    a=replace(a,reviews=(replace(a.reviews[0],verdict='DENIED'),)+a.reviews[1:])
    c=replace(b['envelope'].message.context,approvals=(a,))
    b=resign(b,key,context=c)
    assert outcome(b,'REJECTED','provenance_review_denied').signature_status=='VERIFIED'

def test_unrelated_verifier_programming_error_propagates(monkeypatch):
    s=api();b,_=fixture()
    def broken(value):raise RuntimeError('synthetic-code-defect')
    monkeypatch.setattr(s,'signing_bytes',broken)
    with pytest.raises(RuntimeError,match='^synthetic-code-defect$'):
        s.verify_admission(**b)

def test_public_policy_collections_are_detached_and_immutable():
    from dataclasses import FrozenInstanceError
    b,_=fixture();keys=list(b['policy'].keys)
    p=replace(b['policy'],keys=keys);keys.clear()
    assert len(p.keys)==1
    with pytest.raises(FrozenInstanceError):p.purpose='other'

def test_typed_canonical_format_and_sanitized_rejection():
    from decimal import Decimal
    s=api();b,_=fixture()
    assert s.canonical(Decimal('1'))!=s.canonical('1')
    assert s.canonical(True)!=s.canonical(1)
    b['expected_policy_sha256']='synthetic-redaction-marker'
    r=s.verify_admission(**b)
    assert r.status=='REJECTED' and b'synthetic-redaction-marker' not in s.report_bytes(r)

def test_duplicate_context_issuer_and_unknown_signed_approval():
    b,key=fixture();c=b['envelope'].message.context
    outcome(resign(b,key,context=replace(c,approved_issuers=c.approved_issuers*2)),
            'REJECTED','duplicate_metadata')
    outcome(resign(b,key,approval_id='nonexistent-approval'),'REJECTED','invalid_signed_context')

def test_untrusted_package_key_material_cannot_choose_verification_root():
    b,_=fixture()
    for field in ('public_key','trusted_root','expected_policy_sha256'):
        with pytest.raises(TypeError):replace(b['package'],**{field:b['policy'].keys[0].public_key_hex})
    # Key-looking bytes in ordinary evidence metadata neither select a root nor
    # preserve the package identity authenticated by the original signed approval.
    p=b['package']
    p=replace(p,evidence=(replace(p.evidence[0],reference=b['policy'].keys[0].public_key_hex),)+p.evidence[1:])
    outcome(dict(b,package=p),'REJECTED','package_identity_mismatch')

@pytest.mark.parametrize('message', [b'first synthetic message', b'distinct synthetic message'])
def test_backend_identity_forgery_explains_why_key_validation_is_mandatory(message):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    # This probe documents backend behavior, not acceptance by the M3 gate.
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex('01'+'00'*31)).verify(
            bytes.fromhex('01'+'00'*63),message)
    except InvalidSignature:
        pass  # A future backend may additionally harden this; the gate must stay strict.

def test_identity_root_trivial_forgery_must_be_rejected_end_to_end():
    s=api();b,_=fixture();public=bytes.fromhex('01'+'00'*31)
    k=replace(b['policy'].keys[0],public_key_hex=public.hex(),
              fingerprint=hashlib.sha256(public).hexdigest())
    b=repolicy(b,keys=(k,))
    message=replace(b['envelope'].message,key_fingerprint=k.fingerprint)
    b['envelope']=replace(b['envelope'],message=message,signature_hex='01'+'00'*63)
    outcome(b,'REJECTED','unsafe_public_key')

@pytest.mark.parametrize('encoding', ['00'*32,'01'+'00'*31,'ff'*32,
                                     'ec'+'ff'*30+'7f','ee'+'ff'*30+'7f'])
def test_unsafe_root_encodings_rejected_before_backend_verification(encoding,monkeypatch):
    s=api();b,_=fixture();raw=bytes.fromhex(encoding)
    class ForbiddenVerifier:
        @staticmethod
        def from_public_bytes(value):raise AssertionError('unsafe key reached verifier')
    monkeypatch.setattr(s,'Ed25519PublicKey',ForbiddenVerifier)
    k=replace(b['policy'].keys[0],public_key_hex=encoding,
              fingerprint=hashlib.sha256(raw).hexdigest())
    b=repolicy(b,keys=(k,))
    b['envelope']=replace(b['envelope'],message=replace(b['envelope'].message,key_fingerprint=k.fingerprint))
    outcome(b,'REJECTED','unsafe_public_key')

def test_mixed_order_root_rejected_using_vetted_fixture_arithmetic():
    from nacl.bindings import crypto_core_ed25519_add
    s=api();b,_=fixture();k=b['policy'].keys[0]
    # Test fixture only: maintained libsodium addition, no hand-written curve math.
    mixed=crypto_core_ed25519_add(bytes.fromhex(k.public_key_hex),bytes(32))
    k=replace(k,public_key_hex=mixed.hex(),fingerprint=hashlib.sha256(mixed).hexdigest())
    b=repolicy(b,keys=(k,))
    b['envelope']=replace(b['envelope'],message=replace(b['envelope'].message,key_fingerprint=k.fingerprint))
    outcome(b,'REJECTED','unsafe_public_key')

def test_point_validator_unavailable_fails_closed(monkeypatch):
    from nacl.exceptions import UnavailableError
    s=api();b,_=fixture()
    def unavailable(value):raise UnavailableError('synthetic-sensitive-diagnostic')
    monkeypatch.setattr(s,'crypto_core_ed25519_is_valid_point',unavailable)
    r=outcome(b,'REJECTED','public_key_validation_unavailable')
    assert b'synthetic-sensitive-diagnostic' not in s.report_bytes(r)

def test_point_validator_programming_errors_not_suppressed(monkeypatch):
    s=api();b,_=fixture()
    def broken(value):raise RuntimeError('synthetic-code-defect')
    monkeypatch.setattr(s,'crypto_core_ed25519_is_valid_point',broken)
    with pytest.raises(RuntimeError,match='^synthetic-code-defect$'):
        s.verify_admission(**b)
