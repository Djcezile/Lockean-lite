# M2.0 — synthetic Evidence Admission

## Scope and authority

Founder-authorized baseline: `58ba3da44236a0419e0b6d37a276b3115ee80241`.
Governing instruction: root AGENTS.md at that baseline. Implementation branch:
`research/001-m2-evidence-admission`. Component ownership is new admission code,
associated tests/generated fixtures and research documentation only.

Files:
- src/lockean_lite/research/evidence_admission.py
- tests/test_research_evidence_admission.py
- docs/research/LITE-RESEARCH-001-M2-evidence-admission.md

No existing code, tests, instructions, schemas or sealed evidence are modified.
This is a pure, in-memory synthetic metadata gate, not a provider connector,
signature service, dataset qualifier, strategy evaluator or trading system.

## Inputs and explicit trust boundary

```python
admit(package, approval_id, *, trusted_context, expected_context_sha256, as_of)
```

The untrusted submission is a `Package` plus an approval identifier. A Package has
no approval object, trust context, or trusted-anchor field. The separate TrustContext
and expected hash must be obtained by the trusted caller outside the submitted
package. No environment, filesystem, network or default anchor discovery exists.

The caller and interpreter are trusted. **Replacing both the context and its
expected pin can produce a new internally consistent synthetic ADMITTED report.**
The API cannot authenticate who supplied those arguments or establish independent
issuance/custody itself. Tests demonstrate that a forged package/context with new
matching hashes cannot satisfy the original independently retained context pin.
Do not call a self-generated context hash independent authorization.

No actual Founder approval or provider authentication is created by test helpers.
Their simulated issuer/reviewer identifiers and review dispositions are generated
fixtures only. Before any real use, independent issuance, delivery, reviewer identity
and custody require a separately reviewed, enforceable integration boundary.

## Immutable versioned contracts

- Package: `lite.admission-package.v1`; package ID/version, purpose, inclusive NY
  dates, event interval, availability/capture timestamps and typed evidence.
  Provider must be `fixture`, feed `synthetic`, purpose must be
  `synthetic_metadata_research` for admission.
- Evidence: kind, safe opaque reference and synthetic artifact SHA-256. Required
  kinds: provenance, availability, licensing and retention. No documents are opened.
- Approval: `lite.admission-approval.v1`; approval/issuer identities, exact package
  identity, purpose/dates, UTC validity window and independent evidence reviews.
- Review: required kind, exact Evidence identity, reviewer identity and disposition
  VERIFIED, UNVERIFIED or DENIED. These are trusted-context attestations, not facts
  inferred from strings or hashes. Rights DENIED means incompatibility, not absence.
- TrustContext: `lite.admission-context.v1`; context ID/version, allowed issuers,
  allowed reviewers and issued approvals. The entire context has a pinned identity.

Contracts are frozen dataclasses. Input collections detach into tuples; IDs, exact
types, schemas, hashes and UTC timestamps are checked. Collection bounds are 128
entries each. Duplicate evidence/review kinds, approval IDs and authority identities
reject; they are not silently deduplicated. Unsupported constructor inputs raise
fixed ValueError codes (unknown Python constructor fields fail with TypeError).
Frozen dataclasses are not protection against malicious interpreter reflection.

Identity hashes use unchanged M1 typed canonical encoding over explicitly named
record fields/types. Package identity binds every reference, artifact hash, time,
date, purpose and source field. Approval identity binds reviews and reviewer IDs;
context identity binds issuer/reviewer allowlists and every approval. Order in these
tuples remains identity-significant. No M0 encoder migration or hash reinterpretation.

## Chronology, dates and validity

All timestamps require exact timezone.utc, fold=0. `as_of` is mandatory and explicit;
the gate does not read the wall clock. It represents administrative evaluation time,
not authorization to evaluate historical signals.

```text
event_start < event_end <= captured_at <= as_of
event_end <= available_at <= captured_at  (when available_at is supplied)
approval.valid_from <= as_of < approval.valid_until
```

Missing availability stays UNKNOWN even if its review disposition says VERIFIED.
Contradictory event/availability/capture chronology rejects. Event dates must lie
within the package's declared NY date range; approval dates must match exactly.

Existing M0 partition validation excludes inclusive October 20-December 31, 2026
NY ranges, including enclosing ranges. It checks package and selected approval
dates, event interval and supplied availability date. Event/capture metadata are
generated fixtures; no actual protected observations are read. Capture, evaluation
and administrative validity timestamps alone are not market observations, and are
not classified as protected data merely because their dates fall in that period.

No prices, OHLCV records, calendars, trade candidates, fills or historical outcomes
are ingested. Admission cannot assert their completeness or availability.

## Outcomes and failure modes

Report schema: `lite.research.evidence-admission.v1`.

| Status | Meaning |
|---|---|
| ADMITTED | All required synthetic checks passed against the pinned trusted context |
| UNKNOWN | Essential evidence or trusted context is missing/unverified; no admission |
| REJECTED | Invalid, altered, contradictory, unauthorized or untrusted metadata |

The gate accumulates fixed reasons; REJECTED takes precedence over UNKNOWN, then
ADMITTED. Reports sort and deduplicate reason codes. Only the winning severity's
reasons appear. A trusted approval is selected only after the context matches its
pin; a context mismatch never supplies approval authority.

Rejection reasons: invalid_package, unsupported_purpose, invalid_evaluation_time,
invalid_chronology, event_outside_declared_dates, protected_holdout_overlap,
invalid_trust_anchor, invalid_trust_context, trust_anchor_mismatch,
invalid_approval_identity, approval_not_found, untrusted_issuer, untrusted_reviewer,
package_identity_mismatch, approval_purpose_mismatch, unauthorized_dates,
approval_not_yet_valid, approval_expired, duplicate_metadata; plus
`<kind>_evidence_mismatch` and `<kind>_review_denied` for the four fixed kinds.

UNKNOWN reasons: trust_context_unverified, historical_availability_unverified;
plus `<kind>_evidence_missing`, `<kind>_review_missing`, `<kind>_review_unverified`.
ADMITTED reason: all_required_synthetic_checks_satisfied.

All reports explicitly retain:
- evidence_kind = SYNTHETIC_ONLY
- data_authenticity = UNVERIFIED
- options_eligibility = UNKNOWN
- profitability = UNKNOWN
- downstream_authority = NONE

Reports contain safe hashes, explicit evaluation time and fixed codes/labels, not
raw IDs, evidence references, payload contents, documents or exception text. No
secrets, confidential provider material or credentials are required or discovered.
Canonical report bytes and their SHA-256 are separate; no circular embedded hash.
Source implementation identity remains external in the reviewed commit/source pins.

## Reproduction, verification and limitations

Representative generated fixture: June 1, 2026 NY dates, event 13:58-13:59Z,
availability 13:59Z, capture/evaluation 14:00Z; four generated evidence references,
one synthetic issuer, one synthetic reviewer, all four dispositions VERIFIED.
Its report is ADMITTED, with all authenticity/options/profitability limitations above.

Report SHA-256:
`8dceca7227bc6bad9846a2954ed98eeef6fc5efb053bcee78abc15d013c93adf`.

Tests generate all metadata locally. Reproduce by loading `fixture()` from the test
module with runpy, then `admit(**fixture())`, `report_bytes(report)` and
`identity(report)`. No real approval, data collection or market research is implied.

Baseline full suite: 530 passed, one known warning, exit 0.
Initial genuine RED before module existed: 60 failed, exit 1.
First implementation: 58 passed, 2 failed; overly restrictive list lengths prevented
duplicate-metadata fixtures reaching admission. Bounds were made uniformly 128;
duplicate rejection remains mandatory. Next focused run: 60 passed, exit 0.
Expanded verification: 71 focused and 601 full tests passed. In-scope review then
added regressions for malformed contexts with missing pins: 3 failed, 72 passed,
exit 1. The gate now rejects malformed context types before missing-pin UNKNOWN.
Final results: 75 focused, 121 existing M0/M1 research, 57 safety and 605 full tests
passed; exits 0. Separate 121/57 runs preceded the final M2-only correction; the
final full 605 run included those same unchanged tests. No skips. Known warning:
existing websockets.legacy dependency deprecation. No Windows execution claimed.

Actual commands, sanitized outputs, exit ledger, report bytes, source hashes and
one consolidated journal/manifest are retained outside Git in /workspace/m2-evidence.

Independent Sentinel review must inspect the actual diff, trusted-caller/anchor
boundary, self-issued-hash attacks, expiry and rejection precedence, and reproduce
critical tests at the exact commit. Implementer verification is not independent
acceptance. No merge or deployment is authorized.

Real-data provenance, publication-time truth, legal rights, independent approval
issuance and context custody are not solved by this pure synthetic gate. They
require separate verified evidence and explicit scope. M0's canonical collision
remains deferred before typed parameters drive evaluation. Protected observations,
brokers, production systems and private Original Lockean remain out of scope.

## M2.1 — defensive timestamp hardening

Constructor-valid extreme UTC instants can fall outside Python's representable
datetime range when projected into New York local dates. All such projections in
the admission gate now use one helper that catches only `OverflowError`, records
REJECTED reason `timestamp_out_of_range`, and withholds date-dependent checks for
that unrepresentable instant. Rejection remains mandatory and takes precedence
over UNKNOWN; no date is clamped, timezone substituted or observation admitted.
Unrelated programming failures propagate. Existing holdout and chronology checks
remain unchanged for representable instants.

Generated regressions cover minimum UTC event/availability values, the first
representable New York local boundary and one microsecond before it, maximum UTC
values, combined missing/malformed trust evidence, and unrelated projection errors.
Context substitution still cannot satisfy the original trusted pin. Deliberately
replacing BOTH context and pin remains outside the library's authentication
boundary; no approval issuance or custody guarantee was added.

Actual M2.1 baseline: 605 passed, one known warning, exit 0. Genuine RED: 8 failed,
79 passed, exit 1, reproducing uncaught timezone-projection OverflowError. GREEN:
87 focused M2, 121 existing M0/M1 research, 57 safety and 617 full-suite tests passed,
exits 0; no skips, one existing websockets.legacy dependency warning. These runs
are distinct from the historical M2.0 results above. The valid report was manually
reconstructed without test fixture helpers and remained byte-for-byte identical
with the SHA-256 above. All synthetic-only limitations and output labels remain.
