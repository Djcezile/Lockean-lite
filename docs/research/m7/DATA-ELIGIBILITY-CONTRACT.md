# M7 synthetic data eligibility contract

`qualify(study, dataset, *, raw_bytes, checkpoint, expected_checkpoint_sha256,
as_of, intended_purpose)` is a pure offline gate. The caller supplies the
current expected checkpoint pin, time and purpose independently of the
submission. The checkpoint represents independently selected **synthetic**
evidence for registry entries, dataset claims, license terms, cost estimates
and review records. The expected pin binds the exact checkpoint bytes.
M7 consumes no external provider statements, signatures or real approvals.
M5 synthetic qualification cannot establish real-world provenance.

## Records and bounded inputs

- `Study` binds a synthetic candidate and universe, calendar, three ordered
  folds, exact decisions and later execution instants, embargo, purpose,
  required scopes, raw/derived retention dates, reviewer and provenance/license
  references, cost ceilings, effect, capacity and drawdown assumptions.
  Its identity incorporates the versioned candidate design and fixed parameters.
- `Dataset` binds source, product, version, evidence reference, raw digest,
  calendar identity, instrument reference and scheme, listing/delisting and
  coverage dates, historical eligibility, and synthetic attestations for
  point-in-time constituents, delistings, actions, distributions and revisions.
  A `Sample` supplies observation, publication, selected revision, provider
  receipt, local receipt, action and benchmark availability, and decision times.
  Earnings additionally binds original release, actual and consensus versions,
  comparable fiscal period/basis and consensus creation and receipt.
- `Rights` binds an issuer, agreement version, data identity, purpose, scopes,
  reviewer and effective and retention intervals. Costs bind the exact protocol
  and independent dataset digests and a quote expiry. `Review` is optional and
  binds both digests, the separately named reviewer and review time.
- Inputs are exact immutable records. Instants are UTC and unambiguous. Dates
  and times are bounded to years 1900–2200. Synthetic identifiers are restricted
  to the fixture namespace. There are at most 32 instruments, 2,048 sessions,
  512 decisions per fold, 4,096 samples and 128 registered study IDs. Raw
  synthetic bytes are bounded to 8 MiB. Type/schema tags, ordered tuples, explicit
  dates, and sorted JSON keys determine canonical identities in
  `lite.research.m7.v1`. Historical encoders and schemas are unchanged.

## Checks and precedence

Detect malformed input, incorrect purpose, mismatched/stale checkpoint,
duplicate registration, revoked authority/rights/provenance/study, and study
IDs marked replayed. A pinned registry must contain the exact study digest
before checkpoint evidence is associated with it. For that exact registration,
a revoked study provenance reference blocks even if both dataset records are
absent. A partially initialized input record, including a nested record with
an absent declared field, is malformed and blocks before canonicalization. Compare submitted and pinned
dataset claims. Check raw bytes directly against both available digests, even
if the submission omits its digest. Missing raw bytes do not invent a mismatch.

The pinned calendar fixes ordered New York sessions. A decision and its strictly
later execution must occur within the same eligible session. Trend requires
the previous completed close and at most one decision per month. The supported
earnings window begins at the prior session open and ends before the execution
session opens. An eligible consensus vintage must have been received before
the original publication. Reject lookback or horizon shortfalls and coverage
outside the calendar. Each instrument attests continuous coverage over its inclusive coverage span.
It must cover every declared calendar-backed fold in full, including time before
the first or after the last decision, and all required decision dependencies.
Coverage shortfalls within a declared fold produce `fold_coverage_incomplete`.
The synthetic span does not independently prove there are no missing source rows. Trend requires a sample for every decision/instrument
pair. Earnings requires at least one witness per decision. Covered spans include
the declared fold plus required prior sessions and later label sessions.
A dependency overlap or too few intervening embargo sessions blocks progression.
The calendar and applicable spans may neither intersect nor straddle October 20
through December 31, 2026, inclusive, in America/New_York.

Check requested rights, including non-display, commercial use if requested,
separate raw/derived retention, reviewer access and redistribution if requested.
Rights must cover checkpoint observation and evaluation. A quote exceeding
any known component or the aggregate cap blocks even if another component is
unknown. A synthetic review cannot predate frozen coverage or follow checkpoint
observation, and must bind the exact study, dataset and reviewer.

- `BLOCKED` takes precedence for a detected contradiction, prohibited span or
  failed gate. Missing evidence is still listed.
- `DRAFT` withholds eligibility for missing evidence without a known violation.
- `ELIGIBLE_FOR_REVIEW` means complete synthetic checks. `PENDING` review is
  allowed and is the default. A synthetic review record adds no empirical
  or operational authority.

The report contains deterministic digests, time, reason codes and limitations.
It excludes raw bytes, submitted provider text, credentials and private
diagnostics. The gate does not inspect market observations, verify the truth
or completeness of calendar/coverage attestations, or prove that a label or
feature was computed correctly. The caller must provide authentic custody,
currentness and replay state outside the fixture boundary. This pure gate
does not consume registrations or detect replay across unrelated checkpoints.
Authenticity remains UNVERIFIED, profitability UNKNOWN, empirical and trading
authority NONE.
