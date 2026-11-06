# M5.0 Offline Research Evidence Provenance and Economic-Readiness Gate

LITE-RESEARCH-001 at baseline `9c3bcbee922cd351e39990ba52a6d64c1f8833d1`.

## Ownership and acceptance

M5 owns `src/lockean_lite/research/provenance_qualification.py`,
`tests/test_research_provenance_qualification.py`, and this protocol. The
consolidated journal and evidence manifest live outside Git. M0–M4, operational
code, configuration, dependencies and canonical historical artifacts are protected.
The Founder authorized one isolated branch and draft PR for independent review.

The pure gate takes a bounded frozen package, raw synthetic bytes, a separately
provided current synthetic checkpoint and its independently selected SHA-256 pin,
and explicit evaluation time. The checkpoint binds source and product, instrument,
custody and lineage, historical availability, agreement and issuer, and approval
to the intended use. Submitted declarations cannot supply the current-state pin.
A pin authenticates an exact synthetic snapshot under the caller's trust assumption.
There is no signature ingestion, external lookup, or real-world authentication.

Missing supporting evidence yields UNKNOWN. Malformed inputs, contradictions,
policy mismatch or staleness, supersession or replay, unavailable observations,
holdout overlap and prohibited uses yield REJECTED. Rejections take precedence.
Positive qualification is explicitly SYNTHETIC_ONLY. Real-world authenticity
remains UNVERIFIED, profitability UNKNOWN, and downstream authority NONE.

Acceptance requires genuine RED, focused GREEN, historical identities and full
regression checks. Work uses generated synthetic documents, with protected dates
used only in generated boundary fixtures. No market-data or execution access.

## Inputs and trust boundary

`qualify(package, *, raw_bytes, checkpoint, expected_checkpoint_sha256,
as_of, intended_use)` has no implicit clock, I/O, discovery or state mutation.
`Package` carries `Facts`, an optional declared `Grant`, the requested
`Intent`, and policy and approval references. `None` in a supported field
explicitly marks missing evidence. The caller supplies the intended use separately.
The package intent must match it, including the decision time and any retention
deadline. Callers must enumerate all requested uses.

`Checkpoint` represents a separately selected, current synthetic registry.
The independent pin binds its policy reference, sequence, validity window,
entries, issuer, transformer and signer rosters, revocations and replay records.
Each entry binds the exact source/product and instrument/scheme, raw reference
and byte digest, observation series and revision, publication and custody
times, ordered transformation links, agreement and approval. An approval
binds the typed facts, grant and intent digests. Its issuance must follow
collection and be evidenced by the checkpoint observation time.

The caller must obtain the expected current pin outside submission control,
keep the checkpoint current and provide an independently selected clock and
intent. A matching SHA-256 authenticates the registry bytes under that trust
assumption. A digest by itself supplies no independent custody, authorship,
availability, licensing or external truth. The signer roster models which
identities the synthetic registry accepts. This gate consumes no signatures or
keys and does not invoke M3/M4. There is no fallback to self-supplied pins,
provider names, local timestamps or license assertions. A caller that selects
its own replacement root can make an alternate synthetic registry appear current.
Currentness, registry issuance and persistence are caller responsibilities.

Synthetic identifiers use the bounded `syn-` namespace. This namespace is a
protocol convention and cannot establish the origin of bytes. Callers must
provide generated fixtures only. Records are frozen, variable collections are
bounded to 128 entries, and raw bytes are bounded to 8 MiB. A lineage tuple
binds successive digest links and an authorized actor per step. An empty tuple
means no transformation. The gate does not execute a transform or attest
output bytes beyond the digests covered by the registry.

## Rights and point-in-time policy

The independently pinned grant identifies its issuer, agreement/version,
source/product, permitted purposes, permitted scopes and effective interval.
The grant must cover both decision and evaluation time. Scopes are
`internal_research`, `commercial_research`, `model_development`,
`retain_data`, `store_derived_features`, `redistribute` and
`external_reporting`. Access conveys no scope by default. Raw retention
and derived-feature storage require an explicit requested deadline and an
authenticated grant deadline. Revocations take precedence. The fixture grant
models permitted use inside the synthetic protocol. Legal authorization
requires independent real-world evidence in a separate milestone.

Required sequence is event ≤ first publication ≤ selected revision publication
≤ provider receipt ≤ local collection ≤ research decision ≤ evaluation.
Earlier event timestamps cannot establish availability. A revision requires a
predecessor reference and a release later than first publication. A revision
published after decision cannot stand in for the original. The current registry
must identify the accepted revision and can flag replayed references. The gate
rejects duplicate current records and known alternate references for an
existing observation. Repeating the same pure evaluation reproduces its report.
Stateful replay prevention requires caller-maintained replay state.

Times accept fixed offsets and normalize to UTC. Naive, ambiguous or
unrepresentable timestamps fail closed. The New York date span enclosing all
known evidence times and the decision must avoid October 20 through December 31,
2026, inclusive. This also rejects spans that straddle the protected period.
Evaluation and rights metadata are administrative timestamps outside that
observation-span test. Boundary tests use only generated timestamps.

## Audit and outcome

The versioned report records sorted reason codes, a separate missing-evidence
list, a typed package digest, accepted checkpoint digest, policy reference and
sequence, matched synthetic source and product identities, scope and purpose
from the caller's intent, intent digest, source, rights and chronology decisions,
and explicit evaluation time. Local subdecisions describe their respective
checks. Only the overall status determines synthetic qualification.

- `QUALIFIED_SYNTHETIC_ONLY` means the supplied synthetic evidence satisfies the
  contract against the pinned registry.
- `UNKNOWN` withholds qualification for missing or unverified evidence.
- `REJECTED` withholds qualification for any known mandatory failure, including
  when evidence is also missing. Reason codes describe both categories.

Evidence basis is `PINNED_SYNTHETIC_SNAPSHOT`, `METADATA_UNVERIFIED`, or
`REJECTED_EVIDENCE` according to that outcome. Real-world authenticity remains
`UNVERIFIED`, profitability `UNKNOWN`, and downstream authority `NONE`.
Missing, mismatched and invalid inputs are distinguished by stable codes.
Malformed records are excluded from hashing. Unknown/unmatched synthetic labels,
raw bytes, agreement details, lineage, credentials and key material are excluded
from reports. Matched identities and policy labels must be public synthetic
identifiers selected by the trusted fixture author.

`identity` and `report_bytes` use a versioned, record-type-tagged envelope and
the existing canonical JSON serializer. Tuple order is part of identity,
including declared scope order. Fixed offsets for the same instant serialize
identically. Same inputs and explicit evaluation time yield identical report
bytes. This schema leaves M0–M4 serializers and report identities intact.

## Economic readiness for a separately authorized empirical study

Establish independently evidenced point-in-time data provenance and legal rights
for each product, instrument, revision and planned use. Pin datasets, data
versions, decision-time availability, calendar and code. Define chronological
training and validation, accounting for overlapping labels and observations.
Lock the experiment, candidate family, comparison baseline and acceptance
criteria before evaluating a previously unseen holdout. The protected 2026
period requires separate Founder authorization and a reviewed allocation
protocol. Document candidate selection, multiple testing and reporting of
unsuccessful trials.

Model realistic fees and commissions, bid/ask spread and slippage, liquidity,
market impact, fill probability and partial fills. Include borrowing or financing
where relevant, market-data and infrastructure expenses, operational maintenance,
capital usage and drawdown. Reconcile broker P&L against all-in profitability,
including costs booked outside the broker. Require reproducible data, code,
inputs and outputs, sensitivity checks, and independent acceptance against the
locked protocol. M5 produces no empirical strategy metrics or optimization.
