# LITE-RESEARCH-001 / M0 — integrity kernel

Research-only standard-library package, independent of production policies, broker
adapters, Authority, receipts and Gateway. No provider integration, plugin system,
broker simulator, credentials, persistence or deployment path. See issue #18.

## Input and chronology contract

Use frozen Experiment/Observation/Costs dataclasses. Specifications detach and
recursively freeze built-in dictionaries/lists; unsupported values (including
floats) fail. Timestamps must be datetime instances with timezone.utc, fold=0;
naive, offset-local, strings and ambiguous fold values are rejected explicitly.
Callers must perform explicit UTC conversion before constructing inputs.
Event <= available <= decision; observations strictly increase and cannot repeat.
Prices are finite positive Decimals, at most exponent 18 and 12 fractional digits.
Source identity, provider=fixture and feed=synthetic are mandatory. The source
SHA-256 label declares provenance; it does not authenticate an external provider.
The caller must supply an independently approved canonical input digest. A digest
computed and automatically trusted from the same untrusted input is not approval.
Synthetic fixtures in tests generate their own simulation pins, not real approval.

Inclusive partition ranges must be disjoint from October 20–December 31, 2026,
including ranges enclosing the entire protected interval. Every event, availability
and decision date is also checked in America/New_York. Only development/validation
partitions exist in M0; no protected-holdout ingestion capability is provided.
Timezone data must be available; there is no system-local fallback.

## Frozen synthetic comparison

The synthetic mark-up diagnostic selects when the last minus first already-known
mark is >= 1 price unit. Otherwise it explicitly records NO_TRADE. The comparator
always records NO_TRADE. These are retrospective differences at T, NOT hypothetical
future entries, fills, executable returns, production rule replays or strategy
candidates. The optional threshold parameter can only equal the frozen value 1;
nested parameters are descriptive metadata, not executable plugins.

Commission/spread/slippage are nonnegative, complete synthetic round-trip currency
assumptions for one unit. Gross minus their sum equals net using a fixed Decimal
context. Missing assumptions leave selected-event cost/net UNKNOWN (null). A
NO_TRADE row has zero exposure and zero gross/cost/net. Options qualification
ALWAYS remains UNKNOWN: option chains, executable quotes and fills are unsupported.
Synthetic positive net differences never establish profitability.

Canonical UTF-8 JSON sorts keys, emits UTC Z timestamps and normalized decimal
strings, and excludes runtime metadata. SHA-256 covers the complete canonical
result body; no circular embedded result digest. Reporting performs no file writes.

## Reproduction and limitations

Use the existing trusted Python 3.11+ environment with pytest, no new dependency:

```powershell
& $Python -B -m pytest -q -p no:cacheprovider tests/test_research_contracts.py tests/test_research_validation.py tests/test_research_evaluation.py
```

Test fixtures are entirely generated; no real market or protected observations
were inspected. Missing capabilities include calendar/provider validation, options
chain/quote/transaction evidence, risk/exposure accounting, trading and deployment.
Future evidence-backed study contracts require separate review; M0 supplies no
claim of predictive skill or net options expectancy.

## Representative deterministic synthetic result

Digest: `bf700dc17c42ba7bbcb02695b8c129182b9ac24ad692d1b70a6062c006dacec4`

```json
{"cost_assumptions":{"commission":"0.1","slippage":"0.3","spread":"0.2"},"cost_status":"KNOWN_SYNTHETIC_ASSUMPTIONS","decisions":[{"candidate":"synthetic_mark_up","cost":"0.6","decision":"TRADE_PROXY","gross":"1","net":"0.4","reason":"fixed_mark_difference"},{"candidate":"always_no_trade","cost":"0","decision":"NO_TRADE","gross":"0","net":"0","reason":"comparator"}],"evidence_kind":"SYNTHETIC_ONLY","input_sha256":"821636525c73e3005c55b69d92b9c3d0bde050ab0ca54cd2855c1a6721cbc7e3","inputs":[{"available_at":"2026-06-01T13:58:00Z","event_at":"2026-06-01T13:58:00Z","feed":"synthetic","price":"100","provider":"fixture","source_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},{"available_at":"2026-06-01T13:59:00Z","event_at":"2026-06-01T13:59:00Z","feed":"synthetic","price":"101","provider":"fixture","source_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],"limitations":["RETROSPECTIVE_SYNTHETIC_DIAGNOSTIC","NO_PREDICTIVE_OR_OPTIONS_PROFITABILITY","NO_DEPLOYMENT_AUTHORITY"],"measurement":"SYNTHETIC_MARK_TO_MARK_NOT_EXECUTABLE_PNL","options_missing_evidence":["option_chain","executable_quotes","fills"],"options_profit_qualification":"UNKNOWN","schema":"lite.research.m0.v1","specification":{"decision_at":"2026-06-01T14:00:00Z","name":"m0-synthetic","parameters":{}}}
```

## Engineering journal — Founder Reflection questions

- Which independent source/availability evidence should the next separately
  approved milestone validate before any historical evaluation?
- Which costs and executable option quotes are necessary for the intended claim?
- Are protected-data allocation and chronological evaluation rules approved before
  inspecting any new outcomes?

These are engineering questions for Founder review, not attributed Founder views.
