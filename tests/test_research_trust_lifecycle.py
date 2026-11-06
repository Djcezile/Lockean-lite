"""Synthetic ephemeral lifecycle keys; no operational state or network."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import runpy
import importlib
import hashlib
from concurrent.futures import ThreadPoolExecutor
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def fixture():
    m=importlib.import_module('lockean_lite.research.trust_lifecycle')
    ns=runpy.run_path(str(Path(__file__).with_name('test_research_signed_approvals.py')))
    b,key=ns['fixture']();s=ns['api']();t=b['as_of']
    key=Ed25519PrivateKey.generate()
    raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    controller=replace(b['policy'].keys[0],key_id='controller-1',public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest(),signing_purpose=m.PURPOSE)
    state=m.State('authority-1',1,t,t+timedelta(hours=1),controller,None,())
    anchor=m.Anchor('authority-1',controller,m.identity(state),t-timedelta(days=1),t+timedelta(days=1))
    cp=m.Checkpoint(m.identity(anchor),None,0,t,t+timedelta(minutes=30))
    return m,b,key,state,anchor,cp


def transition(m,key,prior,next_state,action,anchor,t,**kw):
    p=m.Transition('change-'+str(next_state.sequence),action,
       m.identity(prior) if prior else None,m.identity(next_state),next_state,
       m.identity(anchor),t,t,t+timedelta(minutes=10),None)
    return replace(p,signature_hex=key.sign(m.signing_bytes(p)).hex(),**kw)


def advance_fixture():
    m,b,key,genesis,a,cp=fixture();t=b['as_of']
    p=transition(m,key,None,genesis,'BOOTSTRAP',a,t)
    assert m.validate_transition(None,p,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=t).status=='ACCEPTED'
    current=replace(genesis,sequence=2,policy=b['policy'])
    cp=m.Checkpoint(m.identity(a),m.identity(genesis),1,t,t+timedelta(minutes=30))
    p=transition(m,key,genesis,current,'ACTIVATE',a,t)
    assert m.validate_transition(genesis,p,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=t).status=='ACCEPTED'
    cp=replace(cp,state_sha256=m.identity(current),sequence=2)
    return m,b,key,current,a,cp


def check(m,b,key,state,a,cp,p,reason=None):
    r=m.validate_transition(state,p,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of'])
    if reason:assert r.status=='REJECTED' and reason in r.reasons
    assert r.evidence_kind=='SYNTHETIC_ONLY' and r.data_authenticity=='UNVERIFIED'
    assert r.profitability==r.options_eligibility=='UNKNOWN' and r.downstream_authority=='NONE'
    return r


def test_bootstrap_activation_admission_and_determinism():
    m,b,key,state,a,cp=advance_fixture()
    r=m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of'])
    assert r.status=='ADMITTED'
    assert m.report_bytes(r)==m.report_bytes(m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of']))
    assert hashlib.sha256(m.report_bytes(r)).hexdigest()==m.identity(r)


@pytest.mark.parametrize('mode',['missing-anchor','bad-pin','self-bootstrap','missing-checkpoint','bad-genesis'])
def test_bootstrap_fail_closed(mode):
    m,b,key,state,a,cp=fixture();p=transition(m,key,None,state,'BOOTSTRAP',a,b['as_of'])
    pin=m.identity(a)
    if mode=='missing-anchor':a=None
    if mode=='bad-pin':pin='0'*64
    if mode=='self-bootstrap':p=replace(p,signature_hex=Ed25519PrivateKey.generate().sign(m.signing_bytes(p)).hex())
    if mode=='missing-checkpoint':cp=None
    if mode=='bad-genesis':p=transition(m,key,None,replace(state,sequence=2),'BOOTSTRAP',a,b['as_of'])
    assert m.validate_transition(None,p,anchor=a,expected_anchor_sha256=pin,checkpoint=cp,as_of=b['as_of']).status=='REJECTED'


@pytest.mark.parametrize('mode,reason',[
 ('prior','predecessor_mismatch'),('next','successor_mismatch'),('sequence','sequence_mismatch'),
 ('signature','invalid_signature'),('missing','invalid_signature'),('domain','invalid_signature'),
 ('new-signer','invalid_signature'),('expired','authorization_time'),('future','authorization_time'),
 ('checkpoint','checkpoint_mismatch'),('stale','checkpoint_time'),('future-state','state_time'),
 ('revoked','revoked_signer'),('policy-version','policy_version'),('protected','protected_holdout_overlap')])
def test_transition_adversaries(mode,reason):
    m,b,key,state,a,cp=advance_fixture();t=b['as_of'];n=replace(state,sequence=3,policy=replace(state.policy,version='2'))
    p=transition(m,key,state,n,'SUPERSEDE',a,t)
    if mode=='prior':p=replace(p,prior_sha256='0'*64)
    if mode=='next':p=replace(p,next_sha256='0'*64)
    if mode=='sequence':p=transition(m,key,state,replace(n,sequence=4),'SUPERSEDE',a,t)
    if mode in ('signature','new-signer'):p=replace(p,signature_hex=Ed25519PrivateKey.generate().sign(m.signing_bytes(p)).hex())
    if mode=='missing':p=replace(p,signature_hex=None)
    if mode=='domain':p=replace(p,signature_hex=key.sign(b'OTHER'+m.signing_bytes(p)).hex())
    if mode=='expired':p=replace(p,valid_until=t)
    if mode=='future':p=replace(p,issued_at=t+timedelta(seconds=1))
    if mode=='checkpoint':cp=replace(cp,state_sha256='0'*64)
    if mode=='stale':cp=replace(cp,observed_at=t-timedelta(minutes=1),valid_until=t)
    if mode=='future-state':p=transition(m,key,state,replace(n,effective_at=t+timedelta(seconds=1)),'SUPERSEDE',a,t)
    if mode=='revoked':state=replace(state,revoked=(state.controller.fingerprint,));cp=replace(cp,state_sha256=m.identity(state));p=transition(m,key,state,n,'SUPERSEDE',a,t)
    if mode=='policy-version':p=transition(m,key,state,replace(n,policy=replace(n.policy,version='1')),'SUPERSEDE',a,t)
    if mode=='protected':p=transition(m,key,state,replace(n,policy=replace(n.policy,dates=m.m3.DateRange('2026-06-01','2027-01-01'))),'SUPERSEDE',a,t)
    check(m,b,key,state,a,cp,p,reason)


def test_rotation_revocation_old_policy_replay_and_cas():
    m,b,key,state,a,cp=advance_fixture();t=b['as_of'];new=Ed25519PrivateKey.generate()
    raw=new.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    k=replace(state.policy.keys[0],key_id='key-2',public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest())
    rotated=replace(state,sequence=3,policy=replace(state.policy,version='2',keys=(k,)),revoked=(state.policy.keys[0].fingerprint,))
    p=transition(m,key,state,rotated,'ROTATE',a,t)
    assert check(m,b,key,state,a,cp,p).status=='ACCEPTED'
    holder=m.SyntheticStore(state,a,m.identity(a),cp)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:holder.advance(p,expected_state_sha256=m.identity(state),as_of=t),range(2)))
    assert sorted(r.status for r in results)==['ACCEPTED','REJECTED']
    assert holder.advance(p,expected_state_sha256=m.identity(state),as_of=t).status=='REJECTED'
    cp2=replace(cp,state_sha256=m.identity(rotated),sequence=3)
    r=m.admit(b['package'],b['envelope'],state=rotated,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp2,as_of=t)
    assert r.status=='REJECTED'
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp2,as_of=t).status=='REJECTED'
    revoked=replace(rotated,sequence=4,policy=replace(rotated.policy,version='3',keys=()),revoked=tuple(sorted(rotated.revoked+(k.fingerprint,))))
    assert check(m,b,key,rotated,a,cp2,transition(m,key,rotated,revoked,'REVOKE',a,t)).status=='ACCEPTED'


@pytest.mark.parametrize('mode',['unsafe','unavailable','programming-error'])
def test_validator_contract(mode,monkeypatch):
    m,b,key,state,a,cp=fixture();p=transition(m,key,None,state,'BOOTSTRAP',a,b['as_of'])
    if mode=='unsafe':monkeypatch.setattr(m,'crypto_core_ed25519_is_valid_point',lambda _:False)
    if mode=='unavailable':
        def fail(_):raise m.UnavailableError('sensitive text')
        monkeypatch.setattr(m,'crypto_core_ed25519_is_valid_point',fail)
    if mode=='programming-error':
        def fail(_):raise RuntimeError('bug')
        monkeypatch.setattr(m,'crypto_core_ed25519_is_valid_point',fail)
        with pytest.raises(RuntimeError):check(m,b,key,None,a,cp,p)
    else:
        r=check(m,b,key,None,a,cp,p)
        assert r.status=='REJECTED' and b'sensitive text' not in m.report_bytes(r)


def test_trusted_checkpoint_replacement_is_explicit_external_limit():
    first=advance_fixture();other=advance_fixture();m,b,key,state,a,cp=other
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=first[0].identity(first[4]),checkpoint=cp,as_of=b['as_of']).status=='REJECTED'
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of']).status=='ADMITTED'

@pytest.mark.parametrize('mode',['new-self-signer','drop-revocation','resurrect','controller-rotation'])
def test_rotation_boundaries(mode):
    m,b,key,state,a,cp=advance_fixture();t=b['as_of'];new=Ed25519PrivateKey.generate()
    raw=new.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    ctrl=replace(state.controller,key_id='controller-2',public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest())
    n=replace(state,sequence=3,controller=ctrl,revoked=(state.controller.fingerprint,))
    signer=new if mode=='new-self-signer' else key
    if mode=='drop-revocation':n=replace(n,revoked=())
    if mode=='resurrect':
        state=replace(state,revoked=('0'*64,));cp=replace(cp,state_sha256=m.identity(state))
    r=check(m,b,key,state,a,cp,transition(m,signer,state,n,'ROTATE',a,t))
    assert r.status==('ACCEPTED' if mode=='controller-rotation' else 'REJECTED')


def test_identity_point_forgery_rejected_in_bootstrap():
    m,b,key,state,a,cp=fixture();raw=bytes.fromhex('01'+'00'*31)
    ctrl=replace(state.controller,public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest())
    state=replace(state,controller=ctrl);a=replace(a,controller=ctrl,genesis_sha256=m.identity(state));cp=replace(cp,anchor_sha256=m.identity(a))
    p=transition(m,key,None,state,'BOOTSTRAP',a,b['as_of']);p=replace(p,signature_hex='01'+'00'*63)
    check(m,b,key,None,a,cp,p,'unsafe_public_key')


@pytest.mark.parametrize('mode',['substituted-policy','missing-current','invalid-time','stale-checkpoint','bad-pin'])
def test_admission_gate_never_delegates_on_untrusted_state(mode,monkeypatch):
    m,b,key,state,a,cp=advance_fixture();pin=m.identity(a);at=b['as_of']
    def forbidden(*args,**kwargs):raise AssertionError('untrusted state reached M3')
    monkeypatch.setattr(m.m3,'verify_admission',forbidden)
    if mode=='substituted-policy':state=replace(state,policy=replace(state.policy,version='2'))
    if mode=='missing-current':state=None
    if mode=='invalid-time':at=None
    if mode=='stale-checkpoint':cp=replace(cp,observed_at=at-timedelta(minutes=1),valid_until=at)
    if mode=='bad-pin':pin='0'*64
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=pin,checkpoint=cp,as_of=at).status=='REJECTED'


def test_transition_cannot_use_m3_evidence_signature():
    m,b,key,state,a,cp=advance_fixture();p=transition(m,key,state,replace(state,sequence=3,policy=replace(state.policy,version='2')),'SUPERSEDE',a,b['as_of'])
    check(m,b,key,state,a,cp,replace(p,signature_hex=b['envelope'].signature_hex),'invalid_signature')


@pytest.mark.parametrize('field,value',[('sequence',True),('revoked',['0'*64,'0'*64]),('authority_id','!'),('controller',{}),('policy',{})])
def test_constructor_rejects_malformed_state(field,value):
    m,b,key,state,a,cp=advance_fixture()
    with pytest.raises(ValueError):replace(state,**{field:value})


def test_rejected_precedes_missing_evidence():
    m,b,key,state,a,cp=advance_fixture()
    p=replace(b['package'],available_at=None)
    r=m.admit(p,b['envelope'],state=state,anchor=a,expected_anchor_sha256='0'*64,checkpoint=cp,as_of=b['as_of'])
    assert r.status=='REJECTED'


def test_conflicting_same_sequence_and_deterministic_transition_reports():
    m,b,key,state,a,cp=advance_fixture();t=b['as_of'];n=replace(state,sequence=3,policy=replace(state.policy,version='2'))
    p=transition(m,key,state,n,'SUPERSEDE',a,t)
    q=transition(m,key,state,replace(n,policy=replace(n.policy,max_approval_seconds=86400)),'SUPERSEDE',a,t)
    assert m.identity(p)!=m.identity(q)
    r=check(m,b,key,state,a,cp,p)
    assert m.report_bytes(r)==m.report_bytes(check(m,b,key,state,a,cp,p))
    holder=m.SyntheticStore(state,a,m.identity(a),cp)
    assert holder.advance(p,expected_state_sha256=m.identity(state),as_of=t).status=='ACCEPTED'
    assert holder.advance(q,expected_state_sha256=m.identity(state),as_of=t).status=='REJECTED'


def imported_revocation_fixture(inherit=True):
    """One valid live approval key and one separately generated revoked key."""
    m,b,controller,genesis,a,cp=fixture();t=b['as_of']
    retired_private=Ed25519PrivateKey.generate()
    raw=retired_private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    retired=replace(b['policy'].keys[0],key_id='retired-key',status='REVOKED',
                    public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest())
    policy=replace(b['policy'],keys=b['policy'].keys+(retired,))
    state=replace(genesis,sequence=2,policy=policy,revoked=(retired.fingerprint,) if inherit else ())
    cp=replace(cp,state_sha256=m.identity(genesis),sequence=1)
    proposal=transition(m,controller,genesis,state,'ACTIVATE',a,t)
    return m,b,controller,genesis,a,cp,retired_private,retired,state,proposal


def resurrection(m,b,controller,state,a,retired_private,retired,rename_issuer=False):
    alias=replace(retired,key_id='new-alias',issuer_id='alias-issuer' if rename_issuer else retired.issuer_id,status='ACTIVE')
    nxt=replace(state,sequence=state.sequence+1,policy=replace(state.policy,version='2',keys=(state.policy.keys[0],alias)))
    proposal=transition(m,controller,state,nxt,'ROTATE',a,b['as_of'])
    message=b['envelope'].message
    ctx=replace(message.context,approved_issuers=(alias.issuer_id,),
                approvals=tuple(replace(x,issuer_id=alias.issuer_id) for x in message.context.approvals))
    message=replace(message,key_id=alias.key_id,issuer_id=alias.issuer_id,key_fingerprint=alias.fingerprint,policy_version='2',context=ctx)
    envelope=m.m3.sign(message,retired_private)
    return nxt,proposal,envelope


@pytest.mark.parametrize('rename_issuer',[False,True])
def test_entire_imported_revocation_exploit_store_and_admission(rename_issuer):
    m,b,key,genesis,a,cp,retired_private,retired,state,p=imported_revocation_fixture(False)
    holder=m.SyntheticStore(genesis,a,m.identity(a),cp)
    activation=holder.advance(p,expected_state_sha256=m.identity(genesis),as_of=b['as_of'])
    print('activation:',activation.status,activation.reasons)
    if activation.status=='ACCEPTED':
        # On the vulnerable revision reproduce the entire demonstrated chain, not
        # just state_checks: real controller signature, Store advance, M3 admission.
        nxt,rotation,envelope=resurrection(m,b,key,state,a,retired_private,retired,rename_issuer)
        advanced=holder.advance(rotation,expected_state_sha256=m.identity(state),as_of=b['as_of'])
        assert advanced.status=='ACCEPTED'
        newcp=replace(cp,state_sha256=m.identity(nxt),sequence=3)
        admitted=m.admit(b['package'],envelope,state=nxt,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=newcp,as_of=b['as_of'])
        print('rotation:',advanced.status,'qualified admission:',admitted.status)
        assert admitted.status=='ADMITTED'
    assert activation.status=='REJECTED'
    assert 'missing_revocation_inheritance' in activation.reasons
    assert holder._state==genesis


def test_legitimate_activation_inherits_and_retains_revocations():
    m,b,key,genesis,a,cp,private,retired,state,p=imported_revocation_fixture(True)
    holder=m.SyntheticStore(genesis,a,m.identity(a),cp)
    assert holder.advance(p,expected_state_sha256=m.identity(genesis),as_of=b['as_of']).status=='ACCEPTED'
    assert retired.fingerprint in holder._state.revoked
    assert holder.advance(p,expected_state_sha256=m.identity(genesis),as_of=b['as_of']).status=='REJECTED'


@pytest.mark.parametrize('rename_issuer',[False,True])
def test_inherited_revoked_fingerprint_cannot_reactivate_under_alias(rename_issuer):
    m,b,key,genesis,a,cp,private,retired,state,p=imported_revocation_fixture(True)
    cp=replace(cp,state_sha256=m.identity(state),sequence=2)
    nxt,p,envelope=resurrection(m,b,key,state,a,private,retired,rename_issuer)
    check(m,b,key,state,a,cp,p,'revoked_signer')
    # Even a matching externally supplied next checkpoint cannot make an active
    # key in the retained fingerprint ledger pass admission or delegate to M3.
    cp=replace(cp,state_sha256=m.identity(nxt),sequence=3)
    r=m.admit(b['package'],envelope,state=nxt,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of'])
    assert r.status=='REJECTED' and 'revoked_signer' in r.reasons


@pytest.mark.parametrize('action',['ROTATE','REVOKE','SUPERSEDE'])
@pytest.mark.parametrize('inherit',[False,True])
def test_newly_imported_revocations_in_all_policy_transitions(action,inherit):
    m,b,key,state,a,cp=advance_fixture();t=b['as_of']
    retired_private=Ed25519PrivateKey.generate()
    raw=retired_private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    retired=replace(state.policy.keys[0],key_id='imported-retired',status='REVOKED',public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest())
    keys=state.policy.keys+(retired,)
    if action=='ROTATE':
        new=Ed25519PrivateKey.generate();raw=new.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        keys+=(replace(retired,key_id='genuinely-new',status='ACTIVE',public_key_hex=raw.hex(),fingerprint=hashlib.sha256(raw).hexdigest()),)
    # REVOKE without inheritance would otherwise have no new revocation at all;
    # an unrelated fingerprint keeps its pre-existing action rules satisfied.
    ledger=('0'*64,) if action=='REVOKE' else ()
    if inherit:ledger=tuple(sorted(ledger+(retired.fingerprint,)))
    nxt=replace(state,sequence=3,policy=replace(state.policy,version='2',keys=keys),revoked=ledger)
    r=check(m,b,key,state,a,cp,transition(m,key,state,nxt,action,a,t))
    assert r.status==('ACCEPTED' if inherit else 'REJECTED')
    if not inherit:assert 'missing_revocation_inheritance' in r.reasons


def test_inconsistent_current_state_rejects_before_m3(monkeypatch):
    m,b,key,genesis,a,cp,private,retired,state,p=imported_revocation_fixture(False)
    cp=replace(cp,state_sha256=m.identity(state),sequence=2)
    def forbidden(*args,**kwargs):raise AssertionError('inconsistent state reached M3')
    monkeypatch.setattr(m.m3,'verify_admission',forbidden)
    r=m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of'])
    assert r.status=='REJECTED' and r.reasons==('missing_revocation_inheritance',)
    assert m.report_bytes(r)==m.report_bytes(m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=cp,as_of=b['as_of']))


def test_retired_history_survives_removal_and_checkpoint_replay_limit():
    m,b,key,genesis,a,cp,private,retired,state,p=imported_revocation_fixture(True)
    holder=m.SyntheticStore(genesis,a,m.identity(a),cp)
    assert holder.advance(p,expected_state_sha256=m.identity(genesis),as_of=b['as_of']).status=='ACCEPTED'
    newer=replace(state,sequence=3,policy=replace(state.policy,version='2',keys=(state.policy.keys[0],)))
    p=transition(m,key,state,newer,'SUPERSEDE',a,b['as_of'])
    assert holder.advance(p,expected_state_sha256=m.identity(state),as_of=b['as_of']).status=='ACCEPTED'
    assert retired.fingerprint in holder._state.revoked
    dropped=replace(newer,sequence=4,policy=replace(newer.policy,version='3'),revoked=())
    p=transition(m,key,newer,dropped,'SUPERSEDE',a,b['as_of'])
    assert holder.advance(p,expected_state_sha256=m.identity(newer),as_of=b['as_of']).status=='REJECTED'
    oldcp=replace(cp,state_sha256=m.identity(state),sequence=2)
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=holder._checkpoint,as_of=b['as_of']).status=='REJECTED'
    # SAME original anchor: replacing both checkpoint and matching legitimate old
    # state is outside freshness/custody proof, and can restore obsolete history.
    assert m.admit(b['package'],b['envelope'],state=state,anchor=a,expected_anchor_sha256=m.identity(a),checkpoint=oldcp,as_of=b['as_of']).status=='ADMITTED'


def test_imported_revoked_key_fingerprint_must_match_public_material():
    m,b,key,genesis,a,cp,private,retired,state,p=imported_revocation_fixture(True)
    false=replace(retired,fingerprint='0'*64)
    state=replace(state,policy=replace(state.policy,keys=(state.policy.keys[0],false)),revoked=(false.fingerprint,))
    assert 'key_identity_mismatch' in m.state_checks(state,b['as_of'])
