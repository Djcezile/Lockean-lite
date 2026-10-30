# LITE-RESEARCH-001 / M1.0 — synthetic data qualification

## Scope and authority

Founder-authorized offline implementation against main merge
`96da564f7f4a1847da21db8a933e5d4743073b96`, branch
`research/001-m1-data-qualification`. Four additions only:

- `src/lockean_lite/research/data_contracts.py`
- `src/lockean_lite/research/data_validation.py`
- `tests/test_research_data_validation.py`
- `docs/research/LITE-RESEARCH-001-M1.md`

This kernel qualifies **synthetic SPY OHLCV fixture evidence**, not provider data or
strategy profitability. It neither calls M0's evaluator nor extends M0's accepted
provider/feed. It imports no operational clients, credentials, execution components,
Authority, scheduler or production policy. No network, file reads/writes, environment
lookup, automatic collection or trading capability is provided by either new module.
Tests read the existing M0 documentation solely to verify its unchanged example.

## Public interface

```python
qualify(*, manifest, records, payload_bytes, approval, calendar, policy,
        approved_approval_sha256) -> QualificationReport
```

Callers explicitly supply immutable contracts and exact payload bytes. Wrong
constructor field types raise sanitized `ValueError` codes. Qualification violations
return REJECTED reports; missing required evidence returns UNKNOWN. Unexpected
programming errors propagate and must never be interpreted as qualification.

Inputs are frozen dataclasses containing exact strings, integers, bools, Decimals,
UTC datetimes, other frozen contracts or tuples. Calendar construction detaches
supplied lists into tuples. No arbitrary parameter mappings are accepted as contract
fields. Python frozen dataclasses prevent ordinary mutation, not malicious runtime
reflection; callers and the interpreter remain trusted.

## Identities and independent approval

`Manifest` binds schema, dataset ID/version, provider=`fixture`, feed=`synthetic`,
symbol=`SPY`, market=`XNYS`, interval=`1m` or `1d`, adjustment=`unadjusted`, requested
and delivered date ranges, optional warmup/measurement ranges, exact payload length
and SHA-256, dataset digest, calendar/policy digests, capture timestamp, source
revision and availability evidence reference. Real providers and unsupported feeds
or intervals fail constructor validation.

The single-payload dataset digest is the M1 typed-canonical hash of:

```text
{payload_schema: "lite.synthetic-spy-ohlcv.v1",
 payload_sha256: SHA256(exact payload bytes), payload_length: exact byte count}
```

This is deliberately one payload, not a multifile ingestion framework. The manifest
digest binds its complete typed contents. `Approval` pins that manifest, calendar
and policy, an approval identity, purpose=`spy_bar_research`, license evidence
reference, and whether historical options evidence is required. The caller must
provide the independently approved hash of this Approval. The kernel compares it;
it cannot itself establish the independence or authenticity of the caller's pin.
Generated tests compute their own simulation pins; they do not simulate real
Founder authorization or authenticate any external source.

Changing any pinned manifest/calendar/policy requires a new approved identity.
Hashes show byte/content consistency, not provider authenticity or license validity.
Evidence references are approval-bound attestations, not documents fetched or
verified by this kernel. Missing references remain UNKNOWN.

## Payload format and record binding

`encode_payload(tuple_of_Bar)` creates UTF-8 JSON with exactly:

```json
{"schema":"lite.synthetic-spy-ohlcv.v1","records":[]}
```

Each record has exactly `event_start`, `event_end`, `available_at`, `captured_at`,
`open`, `high`, `low`, `close`, `volume`. Times are UTC `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`;
only availability may be null. Prices are schema-typed decimal strings (finite,
at most 19 integer and 12 fractional digits); volume is an exact integer, not bool.
Floats, arbitrary fields, duplicate JSON keys and unsupported schemas reject.

Qualification hashes the original bytes, decodes this supported format itself,
then requires exact normalized Bar-sequence equality with the supplied `records`.
Equivalent Decimal spellings may normalize equally, but different original payload
bytes always have different payload identity. Invalid OHLC relationships, nonpositive
prices, negative volume, duplicates and unordered intervals reject. NaN/infinite or
unbounded Decimal inputs cannot be encoded. Caller-supplied normalized records
alone cannot establish a binding to an opaque export.

Resource bounds: one payload <=64 MiB, <=100,000 records/expected intervals,
<=1,000 explicit calendar sessions. Invalid or exhausted bounds fail closed.
No implicit retries, HTTP pagination or request budgeting exist: no transport exists.

## Calendar and temporal contract

`Calendar` binds ID/version, inclusive date coverage, evidence reference and explicit
ordered, unique Session objects with UTC open/close instants. Each boundary must
fall on that session's New York date and align to a minute. Calendar coverage must
enclose the requested dataset range. A referenced, independently approved schedule
is trusted as complete; the kernel does not independently discover NYSE sessions.
The `XNYS` identifier is a fixture convention, not calendar verification.

Daily bars represent exact approved session open-to-close intervals. Minute bars
represent each exact consecutive minute from open through close. A shortened
session therefore requires its actual supplied interval count, not 390 bars.
Closures are absent from the approved session list; weekends are not presumed to
be sessions. Empty schedules never qualify evidence: `no_expected_sessions`.
Every expected interval must exist. No interpolation, fallback to nearest records,
forward-fill, silent truncation or deletion of unexpected records is allowed.

All datetimes must be explicit `datetime` values using `timezone.utc`, fold=0.
Bar start < end <= capture; one payload has one capture timestamp, shared by every
record and its manifest. Where availability is known:

```text
bar_end <= available_at <= captured_at
available_at <= policy.decision_at
bar_end <= policy.decision_at
```

Missing availability or its evidence reference is UNKNOWN, never inferred from
capture time, bar labels or a normalized session close. A later capture can preserve
an earlier decision's evidence only through the separately attested availability.
All records must be in approved sessions and declared source coverage. Coverage,
warmup and measurement ranges must lie inside the approved requested range.

`Policy` binds version, historical decision instant and exact integer
`max_age_seconds` in [0,31536000]. Staleness concerns the latest observed bar end
relative to that decision, not every old warmup bar. Missing intervals independently
remain UNKNOWN even when the most recent bar is fresh. It is a fixture policy, not
a scientifically approved freshness threshold for any real feed.

## Protected holdout

M0's unmodified inclusive New York-date policy protects October 20-December 31,
2026. Qualification checks requested, coverage, warmup, measurement and calendar
ranges, calendar sessions, decision dates, decoded bar intervals and known
availability dates. An enclosing interval rejects despite both endpoints lying
outside the holdout. Checks operate before any coverage qualification succeeds.
End dates are checked conservatively and inclusively, including a bar ending at
the protected midnight boundary. UTC dates never replace New York dates.

Capture metadata alone is not protected market evidence: recording a capture during
the protected period does not authorize or imply reading observations from it.
No actual protected data is used by these tests; all prices and timestamps are
generated counterfactual fixtures.

## Outcomes and exact reasons

REJECTED takes precedence over UNKNOWN. Every result has evidence_kind
`SYNTHETIC_ONLY` and options_status `UNKNOWN`. QUALIFIED means only that required
fixture checks for `spy_bar_research` passed. Requiring options forces UNKNOWN;
SPY bars never establish options eligibility, fills or profitability.

| Outcome | Reasons |
|---|---|
| QUALIFIED | `all_required_checks_satisfied` |
| UNKNOWN | `no_expected_sessions`, `required_coverage_incomplete`, `calendar_unverified`, `point_in_time_availability_unverified`, `source_revision_unverified`, `license_unverified`, `historical_options_evidence_unavailable`, `observation_stale` |
| REJECTED | `invalid_manifest`, `approval_not_verified`, `identity_mismatch`, `invalid_payload`, `payload_integrity_mismatch`, `payload_record_mismatch`, `unauthorized_dataset_scope`, `invalid_calendar`, `qualification_resource_limit`, `invalid_observation`, `observation_outside_scope`, `duplicate_or_unordered_observation`, `protected_holdout_overlap` |

UNKNOWN reasons are deduplicated and sorted. REJECTED returns the first deterministic
blocking reason; diagnostics are not an exhaustive claim about all invalid inputs.
Missing intervals are exact UTC start/end pairs in schedule order. Expected and
observed counts are separate; rejected evidence can have zero counts if rejection
occurred before coverage was calculated. Reports never print exception bodies or
payload content. Returned identifiers are hashes, fixed labels and approved ranges.

## Deterministic reporting and M0 preservation

Report schema: `lite.research.data-qualification.v1`. It contains purpose, status,
reasons, manifest/approval/dataset/calendar/policy digests, requested/delivered ranges,
expected/observed counts, exact missing intervals and fixed limitations. Source
implementation identity is recorded externally by the reviewed commit and source
hashes; report schema alone does not authenticate executing code.

The new `canonical`/`digest` functions emit `lite.typed-json.v1`, a tagged JSON tree
with explicit contract, scalar and container types. Dictionary keys sort; contract
fields follow their fixed schema order. Decimal normalization uses fixed-point
formatting without dependence on ambient arithmetic context. Decimal `1`, string
`"1"`, integer `1`, bool `true` and user-authored tag-like lists remain distinct.
The complete canonical report body is SHA-256 hashed; no circular embedded hash,
runtime clock, host path or random metadata is added. This representation is not
M0's wire format and must not be interpreted by M0 consumers.

M0 reporting/evaluation/contracts/validation and all old tests/docs are unchanged.
M0's Decimal/string collision remains in `reporting.py`, non-blocking for its frozen
descriptive metadata, and must be corrected through a separately versioned contract
before typed parameters drive evaluation. M1's tagged encoder does not silently
migrate M0 or authorize parameter-driven experiments.

M0 example digest remains:
`bf700dc17c42ba7bbcb02695b8c129182b9ac24ad692d1b70a6062c006dacec4`.

## Engineering journal — 2026-10-30, America/New_York (EDT)

Authorized isolated worktree: `/workspace/Lockean-lite-m1`; existing operational
Windows checkout is neither mounted here nor accessed. Python 3.12.14 on Linux.
Existing dependencies only; neither research module adds non-stdlib dependencies.
No credentials, provider data, accounts, broker calls or historical outcome analysis.

Actual commands below use `/workspace/Lockean-lite/.venv/bin/python -B -m pytest -q
-p no:cacheprovider` in that worktree. Logs are retained outside Git in
`/workspace/m1-evidence`.

| Run / command suffix | Actual result | Exit |
|---|---|---:|
| Baseline, no suffix | 450 passed, 1 known warning | 0 |
| RED, `tests/test_research_data_validation.py`, before either new module existed | 62 failed, 1 passed; actual runtime ModuleNotFoundError failures | 1 |
| First GREEN, same suffix | 63 passed | 0 |
| Review RED, same suffix after empty-calendar/missing-approval regressions | 2 failed, 74 passed | 1 |
| Final M1, same suffix | 76 passed | 0 |
| M0, `tests/test_research_contracts.py tests/test_research_validation.py tests/test_research_evaluation.py` | 41 passed | 0 |
| Safety, `tests/test_lockean_authority.py tests/test_authorization_receipt.py tests/test_execution_gateway.py tests/test_profit_first_entry_policy.py` | 57 passed, 1 known warning | 0 |
| Full, no suffix | 526 passed, 1 known warning | 0 |
| Adversarial, `tests/test_research_data_validation.py -k 'holdout or protected or enclosing'` | 15 passed, 61 deselected | 0 |

Zero skips. Known warning: existing dependency `websockets.legacy` deprecation.
The first RED's one pass was the existing M0 example verification, which does not
depend on missing M1 modules. In-scope review RED caught incorrect qualification
of an empty expected calendar and an imprecise missing-approval reason; both were
corrected before final verification. No test failures remain on Linux.

Representative generated two-minute fixture: requested June 1, 2026, approved
13:30-13:32 UTC schedule (deliberately short synthetic schedule, not a full NYSE
session); decision/capture 13:33 UTC; OHLC 100/102/99/101 and volume 5 each minute.
Result: QUALIFIED, 2 expected/2 observed, no missing intervals, options UNKNOWN.
Its exact typed canonical report was reproduced twice without running outcomes:

`933ffb7b0770b5a8f1d29c954572efe140208712fed81174f1578ab08c2f0598`

Payload SHA-256:
`bd9266a1c425760754df463e623f6c7425eb76794ffb3920aef88ba3daf24515`.

For independent reproduction, load the generated `fixture()` from the new test
module with runpy, call `qualify(**fixture())`, then `canonical(report)` and
`digest(report)`. This is synthetic qualification only, not market analysis.

## Remaining risks, review and next action

- No Windows execution is claimed. Use a separate trusted Windows checkout at the
  review commit, verify source hashes, and run the exact offline commands above.
  Do not copy into an operational checkout or activate any scheduler.
- No historical provider parser, calendar authority, publication-time archive,
  entitlement/license verification or historic options chain/quote coverage exists.
  A reference string and byte hash do not resolve these external questions.
- No actual historical data is qualified; real provider support requires a new
  reviewed adapter/scope and independent authorization, including date allocation,
  point-in-time evidence, licensing, revisions and initialization requirements.
- The approved calendar is trusted, not algorithmically authenticated. Missing
  whole sessions cannot be discovered if an independently approved schedule itself
  omits them. Calendar provenance review is essential before real research.
- Immutability is in-memory only. Durable storage, signatures, custody, artifact
  allocation and acquisition request limits are outside this four-file kernel.
- An in-memory bytes API cannot prevent a caller from reading protected inputs
  before invocation. Upstream selection must enforce authorization before access;
  the kernel refuses qualification when supplied metadata/content overlaps.

### Founder Reflection — questions, not attributed Founder statements

1. Which independent calendar and historical publication evidence would be accepted
   before a separately scoped real-data adapter is considered?
2. Which dates and context inputs may be allocated without protected-period access
   or falsely labeling development-exposed data independent validation?
3. Which license, retention rights and options quote/contract fields are necessary
   for the intended future claim, and what cost ceiling is acceptable?

HQ handoff: M1 synthetic qualification implemented and Linux-verified. Seek
independent review of the published four-file branch. Do not merge, deploy, acquire
data, evaluate strategy outcomes or authorize execution from a QUALIFIED fixture.
