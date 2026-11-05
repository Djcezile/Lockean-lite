# M3.0 — Signed Synthetic Approvals and Trusted-Context Custody

## Scope and ownership

Founder-authorized baseline: 6a8ad96e8fb67f6a419918f92e4c24aa9af80e1b.
Branch: research/001-m3-signed-approvals. Governing root AGENTS.md unchanged.

New component: src/lockean_lite/research/signed_approvals.py, its test module,
and this document. One essential dependency-manifest edit: pyproject.toml adds
the optional research-crypto extra, cryptography==50.0.2. The dev extra pins the
same library so the existing README dev-install/full-test workflow remains usable.
Both extras also pin PyNaCl==1.6.2 for mandatory vetted public-point validation;
Ed25519 signing/verification remains cryptography, not a replacement algorithm.
These additions do not change base operational dependencies. M0/M1/M2 source,
serializers, schemas, historical evidence and operational components are unchanged.

This is a pure, offline, synthetic API. It does not provision real approval
issuers, discover roots, load private keys, contact providers or operate a broker.
Only tests generate ephemeral Ed25519 private keys, in memory. No private key
export, storage or signing service exists. Signing is capability possession,
not an independent human approval workflow.

## Dependency and environment

The baseline environment had no cryptography package. The configured public
package index advertised 50.0.2; that exact version was selected and its Ed25519
generate/sign/verify/from_public_bytes APIs inspected and probed. No primitive,
fallback algorithm or network key service was implemented.

Actual isolated installation: /workspace/m3-crypto; shared venv not modified.
Observed: cryptography 50.0.2, cffi 2.1.1, pycparser 3.12, bundled OpenSSL 4.0.3.
Cryptography metadata declares Apache-2.0 OR BSD-3-Clause. These are observed
versions, not a claim of a comprehensive dependency vulnerability or license audit.
No pre-existing lockfile was found; no new lock framework was added. Only the
direct research dependency is pinned; transitive versions are recorded in evidence,
not promised immutable by that pin. Base project dependencies remain unchanged.

For a fresh approved engineering environment, install the project with its dev
and research-crypto extras. This does not authorize installation on Windows
production or activation of a service. Existing test runs used the inherited
trusted Python with PYTHONPATH=/workspace/m3-crypto; pytest adds src via pyproject.

## Public contracts and identity

- PublicKey: issuer ID, globally unique key ID, 32-byte public key as lowercase
  hex, SHA-256 fingerprint of those exact bytes, ACTIVE/REVOKED status, signing
  purpose, and UTC validity bounds.
- TrustPolicy: lite.signing-policy.v1, policy ID/version, public keys, reviewer
  allowlist, research purpose, NY date range, UTC validity, maximum approval
  lifetime in exact integer seconds. Collections detach into immutable tuples
  and are bounded to 128; duplicated key IDs/reviewer IDs reject.
- ApprovalMessage: lite.signed-approval-message.v1, artifact type
  synthetic-evidence-approval, policy ID/version, issuer/key/fingerprint,
  selected approval ID, issuance time and the entire immutable M2 TrustContext.
  Therefore the signature binds exact package identity, purpose, dates, evidence
  references/digests and review identities/dispositions. Exactly one approval
  is supported in a signed context. Duplicate context identities reject.
- SignedEnvelope: lite.signed-approval-envelope.v1, fixed Ed25519 algorithm,
  message and 64-byte signature represented as lowercase hex.
- SignedAdmissionReport: lite.research.signed-admission.v1, safe identities,
  explicit evaluation time, signature status, admission status/reasons, optional
  M2 result hash and fixed synthetic limitations.

Caller supplies the policy and expected policy SHA-256 separately from the
untrusted package/envelope. The envelope cannot select a replacement public root.
Actual public-key bytes come ONLY from that matching trusted policy. Issuer,
key, fingerprint, signing purpose and policy ID/version must agree. Unknown,
revoked, invalid/expired, substituted or obsolete policy/key identities reject.

The expected hash must come from independently approved CURRENT configuration.
A caller who replaces both policy and expected hash can choose another authority;
this library does not defeat control of its own trusted inputs or prove custody.
A valid signature proves possession of the registered signing key under supplied
policy, not legal issuer identity, factual evidence, actual signing-clock time or
independent human approval. Public-root onboarding and authentic distribution are
external responsibilities. Policy roots are not automatically fetched or refreshed.

## Canonical signing and report bytes

Signing bytes are exactly the constant prefix
LOCKEAN-LITE-SYNTHETIC-APPROVAL-V1 followed by a zero byte and the unchanged M1
typed canonical encoding of a lite.m3.signing-frame.v1 wrapper containing the full
public ApprovalMessage snapshot. Record-type names, field values, UTC instants
and tuple order are bound. This is a separately versioned M3 format, not an M0
migration. Strict contract types prevent bool/int/string ambiguity.

Envelope schema, algorithm and artifact type are checked against fixed values.
No signature intended for another domain, schema, purpose or approval selection
is accepted. Policy ID/version and key fingerprint are signed; the exact current
policy contents/hash are separately trusted and enforced at verification. Status
and allowlist updates can change that policy snapshot while retaining its logical
version; the caller must supply its current approved hash. An intentionally changed
policy version invalidates messages naming the previous version.

Ed25519 signing is deterministic for identical message and key. Tests generate
new ephemeral keys, so independently generated scenarios have different public
inputs and hashes. Determinism means identical explicit inputs produce identical
bytes/outcomes; it does not mean unrelated random keys have the same identity.

Report bytes use a separate lite.m3.identity.v1 wrapper. A report hash covers all
canonical bytes and is stored separately. No runtime metadata, private key or
arbitrary input body is included. Names/references are represented by safe hashes.

## Mandatory verification order

1. Validate package/policy/envelope types, explicit UTC evaluation time and expected
   policy hash. No policy discovery, unsigned acceptance or default trust root.
2. Validate supported schemas/domain/algorithm, policy identity/purpose, duplicate
   keys/reviewers, issuer/key selection, fingerprint, ACTIVE status and key/policy
   validity. These failures do not invoke M2.
3. Verify Ed25519 against the policy's public key. InvalidSignature yields REJECTED.
   No broad exception catch or insecure fallback; unrelated programming errors
   propagate. No M2 result exists for signature failure.
4. Validate the authenticated context, issuer, reviewers, approval purpose/dates,
   policy limits and issuance chronology. No extra signed approval is silently ignored.
5. Only after all these checks, call unchanged M2 admission with the signed context
   and its computed consistency pin. This derived pin is safe only because the M3
   signature/root gate has already authenticated that context. The old M2 API itself
   remains caller-trusting and does NOT gain cryptographic authentication.

M3 never invokes M1 qualification, strategy evaluation, Authority or Gateway.

## Time, revocation and replay

All times are caller-supplied timezone.utc datetimes, fold=0. No clock discovery.
Validity begins inclusively and ends exclusively, at issuance and evaluation:

- policy and key must be valid at message issuance and current evaluation;
- issued_at <= approval.valid_from <= evaluation < approval.valid_until;
- approval.valid_until must not exceed key/policy expiration;
- approval duration must not exceed policy.max_approval_seconds.

Current policy REVOKED status rejects even a previously valid signature.
Rotation is demonstrated with a genuinely new ephemeral key; old signatures fail
under current revoked-key policy, new authorized-key signatures pass.
Old policy snapshots cannot satisfy the current expected policy hash, but an
offline verifier cannot independently establish that a caller supplied the latest
configuration. Revocation freshness remains external.

Package/approval exact identity and purpose prevent inappropriate cross-package
reuse. Identical valid stateless verification may be repeated successfully: no
one-time consumption, replay registry or exactly-once guarantee is implemented.
Such persistence would need separate authorization.

Protected October 20-December 31, 2026 NY date exclusion remains mandatory.
Policy/approval date ranges are checked; validly signed packages still undergo M2
event/availability/holdout and extreme-date checks. A signature never authorizes
protected research observations. Timestamp tests use generated counterfactuals only.

## Outcomes and limitations

REJECTED takes precedence over UNKNOWN; mandatory signature/policy failure always
rejects. Once the authenticated context passes M3, M2 missing/unverified factual
evidence stays UNKNOWN and known DENIED evidence rejects. ADMITTED means only all
required synthetic checks passed. signature_status records whether cryptographic
verification actually completed; VERIFIED can coexist with later REJECTED or UNKNOWN.

Every report retains SYNTHETIC_ONLY, UNVERIFIED real-world authenticity, UNKNOWN
options eligibility/profitability and NONE downstream authority. Signatures do
not prove historical observations, publication availability, license or retention
rights. Real trust-root ownership, issuer provisioning and human review remain
outside this fixture-only kernel. No merge, deployment or real-data authority follows.

## Actual engineering evidence and independent review

Python 3.12.14, Linux. Original baseline: 617 passed, one known dependency warning.
Genuine RED: 50 failed, exit 1, before the new module existed.
First implementation: 48 passed, 2 failed (early-expiry diagnostics and static test's
handling of a relative ImportFrom). Added explicit validity reasons and corrected
the AST inspection without removing the forbidden-import check. Next GREEN: 50.
Expanded runs: 65 focused / 682 full passes. Final added package-key injection
regression: 66 focused / 683 full passes. M0/M1: 121; M2/M2.1: 87; safety: 57.
All final gates exit 0; no skips; one existing websockets.legacy warning.
Pip check: no broken requirements; pip also reports its non-writable cache warning.

Adversarial cases include valid signatures, RFC 8032 section 7.1 public verification
vector, message/package/key/reference/review tampering, untrusted roots and issuer
IDs, malformed signatures, domain/algorithm substitutions, key rotation/revocation,
obsolete policy, duplicate identities, expiry/issuance boundaries, protected/enclosing
dates, extreme times, UNKNOWN precedence, stateless repeats, sanitization and no
unsigned M2 fallback. Test private keys are generated ephemerally; the RFC vector
imports only its public key and signature, never private material.

Artifacts outside Git in /workspace/m3-evidence include a PUBLIC generated scenario,
canonical signing/report identities and a replay script. It reconstructs public
contracts only and proves repeatability, not independent root issuance. The recorded
scenario report hash is in synthetic-identities.json; future fresh keys change it.
The old M2 admitted-report hash remains
8dceca7227bc6bad9846a2954ed98eeef6fc5efb053bcee78abc15d013c93adf.

Independent non-implementer cryptographic review must inspect the actual diff,
trust-root custody assumptions, signing domain/canonical bytes, expiry/revocation
policy and critical adversarial tests; independently replay the PUBLIC fixture and
probe for unsigned bypass. Implementer self-review is preliminary evidence only.
Windows and deployment verification are unperformed. No protected components or
real-world evidence were used or modified. No next milestone is authorized.

## Required security correction — unsafe public-key encodings

Independent local reproduction showed cryptography 50.0.2 / OpenSSL 4.0.3 accepts
the identity-point public key (01 then 31 zero bytes) with signature R=identity,
S=zero (01 then 63 zero bytes), for distinct messages. With that key in an approved
synthetic root, uncorrected M3 returned ADMITTED/VERIFIED without a private key.
The constructor's 32-byte length check and verification alone were insufficient.

M3 now applies PyNaCl's maintained libsodium primitive
`crypto_core_ed25519_is_valid_point` to the selected trusted-policy public key
before OpenSSL verification. The primitive requires canonical representation,
curve membership, main-subgroup membership and absence of small order. This is
not an identity blacklist or hand-written subgroup/curve algorithm. Signing and
signature verification still use the pinned cryptography Ed25519 implementation.

Pinned API contract:
https://github.com/pyca/pynacl/blob/1.6.2/src/nacl/bindings/crypto_core.py

Upstream implementation:
https://github.com/jedisct1/libsodium/blob/1.0.20-RELEASE/src/libsodium/crypto_core/ed25519/core_ed25519.c

The exact PyNaCl 1.6.2 source distribution was downloaded, its published SHA-256
checked, and its vendored 1.0.20 configure/source and validator checks inspected.
Source hashes are retained in the correction evidence. The installed wheel's
supported binding docstring matches these guarantees; it exposes no runtime
libsodium-version query, so the vendored source version is not misrepresented as
a runtime measurement of the wheel. PyNaCl reuses existing cffi; base operational
dependencies and shared environments remain unchanged.

False validity returns REJECTED/unsafe_public_key; a minimal build raising
UnavailableError returns REJECTED/public_key_validation_unavailable. There is no
fallback if validation is absent. Other programming errors propagate. This checks
the selected key, not every unused policy entry or the authenticity of policy
custody. It does not authenticate an issuer's facts, authorize a root, prove true
availability/licensing, or supply replay consumption. External root/pin custody
remains mandatory. Existing signing bytes, schemas and valid report bytes are unchanged.

Genuine correction RED: 9 failed, 68 passed, exit 1. The identity forgery produced
ADMITTED instead of required REJECTED. GREEN: 77 M3, 208 existing M0/M1/M2 research,
57 safety and 694 full-suite passes, exits 0. No skips; one existing websockets.legacy
warning. Vectors exercise identity, low order, noncanonical, off-curve encodings,
and a mixed-order point constructed using maintained library addition in a test
fixture only. No custom elliptic-curve arithmetic was introduced. Ordinary keys,
rotation, revocation and previous signature substitutions remain covered. The
recorded public fixture report still hashes to
1b354e92ae925a07ca7daa294f3437d517bb13fc0162d2172ffd647e35fa70bd.

These are implementer results, not independent security acceptance. The new exact
commit and validator/dependency choice require independent review before merge.
