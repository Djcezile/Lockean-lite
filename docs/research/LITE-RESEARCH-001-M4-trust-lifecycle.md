# M4.0 — synthetic trust lifecycle v1

Baseline: 86f1be999294db9033d782692deeeab608aa9c3b. Owned additions only:
`src/lockean_lite/research/trust_lifecycle.py`,
`tests/test_research_trust_lifecycle.py`, and this document. No M3 changes,
new dependencies, network, persistent storage, provider observations or operations.

## External trust and API

An immutable `Anchor` independently pins the exact staged genesis state, bootstrap
controller and validity. Its expected SHA-256 must arrive through independently
controlled configuration, never the proposed transition. Initial trust is assumed,
not manufactured by signing one's own root.

A separately trusted `Checkpoint` pins current state hash, sequence, anchor hash,
observation time and expiry. It is not extracted from a submission. The caller is
responsible for authentic, current, durable checkpoint custody and truthful UTC
evaluation time. Replacing both the trusted checkpoint and its matching state can
restore an obsolete history even when the original anchor and anchor pin remain
unchanged. Replacing anchor/pin as well can select an entirely different root. The library cannot prove global latestness, disk durability,
ACL effectiveness, human identity, key ownership, external reviewer independence,
issuance truth, or actual revocation publication time. There is no recovery override.

`validate_transition(state, proposal, *, anchor, expected_anchor_sha256,
checkpoint, as_of)` returns a deterministic `Report`. Missing/tampered/stale state
rejects, as do malformed constructors with fixed ValueError diagnostics. Unrelated
programming errors propagate. Structural constructors detach lists and reject
incorrect primitive types; this is a typed Python API, not a general JSON parser.

`admit(package, envelope, *, state, anchor, expected_anchor_sha256, checkpoint,
as_of)` qualifies current lifecycle state, selects its embedded M3 policy, then
calls unchanged M3 verification. No submission-selected policy/pin or automatic
transition activation is accepted. Legacy M2 and standalone M3 retain their old
trust assumptions; M4 does not disable those APIs or stop a caller from invoking
them separately. Caller access to ordinary Python memory is not a sandbox boundary.

## State machine

State sequence begins at 1, increments exactly once, and binds authority identity,
effective/expiry UTC times, lifecycle controller, optional M3 policy and a sorted,
monotonically retained set of revoked PUBLIC KEY FINGERPRINTS. Fingerprint revocation
also blocks renamed aliases. Staged genesis has no active M3 policy.

Every policy entry marked REVOKED must already have its public-key fingerprint in
State.revoked. Missing inheritance rejects with `missing_revocation_inheritance`
on initial activation, every successor, and current-state admission. Validation
never silently mutates a signed successor or treats a REVOKED entry as eligible
for future activation. Revoked-entry fingerprints must match their public-key bytes;
false metadata rejects with `key_identity_mismatch`.

ACTIVATE and SUPERSEDE permit exactly the old ledger union imported REVOKED
fingerprints. ROTATE and REVOKE retain their action-specific rules and monotonic
ledger constraint, plus the same imported-revocation invariant. A policy may later
remove a retired key entry, but its fingerprint remains permanently in the ledger.
Changing key ID, issuer ID or policy version cannot make an active alias pass;
`revoked_signer` still rejects its fingerprint. Even a valid signature from a
malicious or compromised lifecycle controller cannot waive these mechanical rules.
Older inconsistent states must be rejected, not auto-repaired or grandfathered.
Any corrected state/checkpoint must be independently approved outside validation.

| Action | Required successor |
|---|---|
| BOOTSTRAP | No predecessor; exact anchor-pinned genesis, controller equals anchor, no policy/revocations, sequence 1 |
| ACTIVATE | Staged predecessor; M3 numeric policy version `1`; unchanged controller; ledger equals prior ledger plus imported REVOKED fingerprints |
| ROTATE | Active predecessor; new active evidence key and/or genuinely new controller; removed active keys and replaced controller permanently fingerprint-revoked |
| REVOKE | Strictly larger revocation set; no newly active keys; controller unchanged |
| SUPERSEDE | Active policy changes; unchanged active fingerprints/controller; ledger equals prior ledger plus imported REVOKED fingerprints |

Active policy IDs remain fixed. Changed policy versions increment exactly by one
using canonical decimal integer strings. A controller-only rotation can retain the
same policy. The currently authorized OLD controller signs every successor. New
controller or evidence keys cannot sign their own introduction. There is no
implicit emergency recovery. Revoking a shared controller/evidence key also revokes
the controller; separate keys avoid that loss of authority. A last-controller loss
requires separately approved recovery architecture, not an override in this module.

Every transition binds ID, action, exact predecessor/successor hashes, complete
successor state, anchor identity, issuance, effective and expiry times. Issuance
must occur within old authority/state validity; effective equals successor effective;
issuance <= effective <= evaluation < authorization expiry. Current checkpoint,
anchor, state, controller and active evidence-key validity are separately enforced.
State validity is an independently trusted bound; freshness is not inferred from
an arbitrary library default. The caller chooses approved checkpoint expiry.
Policies retain M3 synthetic purpose and protected-date exclusion. No actual
protected-period observations are read. Synthetic boundary fixtures test rejection.

## Cryptography and canonical identity

M4 frame: `lite.m4.lifecycle.v1`; typed record names and exact fields are bound with
the existing typed canonical primitive, without changing M1 or M3 encodings.
Transition signing frame: `lite.m4.transition-signature.v1`, domain
`LOCKEAN-LITE-SYNTHETIC-LIFECYCLE-V1\0`. All transition fields except signature are
signed, including complete successor and hashes. Ordinary M3 evidence signatures
cannot authorize lifecycle transitions. Ed25519 verification uses existing
cryptography. PyNaCl/libsodium validates public points before verification. Unsafe
points reject; UnavailableError yields a fixed rejection; other errors propagate.
Missing imports have no insecure fallback. Existing optional dependency pins remain.
M4 reuses M3 private metadata predicates; changes to those helpers need compatibility
review. All M3/M2 signing/report identities remain unchanged.

Reports contain action, stable sorted reasons, prior/next/anchor/transition hashes,
explicit evaluation time and optional M3 report hash. Hash references safely bind
public policy/key identities without including arbitrary request/error text.
Statuses: ACCEPTED for valid transitions; REJECTED for failed lifecycle checks;
M3 ADMITTED/UNKNOWN/REJECTED for qualified admission. REJECTED precedes missing M3
information, and M3 preserves REJECTED over UNKNOWN. All reports retain
SYNTHETIC_ONLY, UNVERIFIED authenticity, UNKNOWN options/profitability, NONE authority.
A hash is consistency evidence, not an issuer or real-world provenance attestation.

## Synthetic state holder

`SyntheticStore.advance(proposal, expected_state_sha256=..., as_of=...)` holds a
lock across hash comparison, validation and update. It advances its in-memory
checkpoint only after ACCEPTED and never extends the prior checkpoint deadline.
Concurrent same-predecessor updates have one winner. Duplicate/competing transitions
subsequently fail CAS or predecessor/sequence checks; IDs are bound labels, not a
global unique-ID registry. Pure validation is intentionally repeatable. Restoring
old process memory plus old trusted checkpoint is outside rollback guarantees.
No production database, persistence, ledger, signer or key export is implemented.

## Verification and independent acceptance

Ephemeral in-memory keys and generated metadata only. The test suite covers anchored
bootstrap, missing/self trust, activation, evidence/controller rotation, revocation,
obsolete policy/history replay, CAS races/conflicts, exact state hashes, sequence,
wrong domain/signatures, unsafe identity point, unavailable validator, propagated
programming errors, time limits, malformed inputs, protected date enclosure,
qualified M3 admission, pre-delegation rejection and honest custody limitations.
The initial 26-test RED predates implementation. First implementation: 24 pass / 2
fail due fixture setup (zero-length checkpoint interval and revoking a key shared
with controller). Fixtures corrected without relaxing safeguards, then 26 passed;
expanded focused coverage: 44 passed. Historical identities are verified separately.

No Windows execution or production custody claims. Transitive dependencies remain
unlocked; observed versions are recorded in the handoff. This is implementer
verification, not independent security acceptance. A non-implementer must inspect
bootstrap/pin custody, all transition invariants, old-signer selection, point checks,
CAS races, exact canonical frames, failure paths and M3 pre-delegation gate at the
published commit, and independently execute adversarial tests before merge.


## Revocation-inheritance security correction

The original state checker skipped REVOKED policy entries and activation required
an unchanged ledger. A controller could therefore import a retired key without
ledger inheritance, rotate the identical key material into an ACTIVE alias, and
obtain qualified admission. The complete chain was reproduced with key-ID-only
and issuer-plus-key-ID aliases, including SyntheticStore advances and real synthetic
approval signatures. Genuine pre-fix RED: 9 failed / 48 passed. A separate false
fingerprint regression failed before the runtime correction. Corrected focused
suite: 58 passed. Exact commands, full regressions and revision are in the external
correction handoff; no independent acceptance is claimed here.

Tests preserve imported revocations through activation, subsequent policy changes,
entry removal, retained-state CAS and obsolete-state rejection. A limitation test
also deliberately restores an old state AND its matching old checkpoint with the
same original anchor: the stateless verifier cannot detect that historical rollback.
Authentic, durable checkpoint custody and independently established current-state
freshness remain external responsibilities. The memory holder does not provide
production-grade rollback resistance, persistent freshness or external custody.
