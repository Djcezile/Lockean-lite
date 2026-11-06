# M7 frozen experiment registry

The machine-readable registry contract is defined in
[src/lockean_lite/research/empirical_readiness.py](../../../src/lockean_lite/research/empirical_readiness.py).
A frozen study is identified by the SHA-256 of its typed canonical record and
the built-in versioned design. The immutable checkpoint registry maps each
synthetic ID to one digest. A redefinition requires a new independently pinned
registration. The gate derives the state. Self-declared status cannot bypass it.

| State | Meaning |
|---|---|
| DRAFT | Required evidence is missing or unverified. |
| BLOCKED | Known contradiction, unauthorized use or failed mandatory gate. |
| ELIGIBLE_FOR_REVIEW | Generated fixture satisfied the contract and can be reviewed. Independent approval may still be pending. |

## Frozen illustrative entries

Both generated entries use one synthetic security, `syn-instrument`, under
`syn-security-id`, and use `syn-study` in separate checkpoint examples. In a
shared registry those IDs must be distinct. The calendar is a generated weekday
calendar from 2021-01-01 to 2024-07-23, with 09:30–16:00 New York sessions.
It is intentionally independent of any actual exchange calendar or outcome.

| Candidate | Fold | Exact illustrative decision date (New York) | UTC decision → later execution |
|---|---|---|---|
| Trend | Development | 2021-12-29 | 15:00 → 15:15 |
| Trend | Validation | 2023-02-22 | 15:00 → 15:15 |
| Trend | Untouched holdout | 2024-04-17 | 14:00 → 14:15 |
| Earnings | Development | 2021-01-29 | 15:00 → 15:15 |
| Earnings | Validation | 2021-05-21 | 14:00 → 14:15 |
| Earnings | Untouched holdout | 2021-09-10 | 14:00 → 14:15 |

Each one-day decision fold expands to its required dependency span. Trend
uses 252 prior sessions and a 21-session horizon. Earnings uses one prior
session for the illustrative release/consensus window and a 20-session
horizon. Both use a 21-session embargo. Actual research needs a separately
approved, powered calendar and lawful independently verified data.

The examples freeze long/cash exposure, a paired incremental endpoint and
Holm correction. They require internal/commercial research, non-display,
raw and derived retention and reviewer access. Generated rights and evidence
references are `syn-license` and `syn-provenance`. Fixture retention dates,
economic bounds, synthetic reviewer and planned costs are bound in the
protocol or evidence digests. No real instruments, rights, budget or dates
are approved.

| Candidate | Canonical protocol SHA-256 | Public readiness report SHA-256 |
|---|---|---|
| Trend | `4368b30a1abc54fee248d927c9ea2e385e969541d9ab8712415195b43d6e33d5` | `640dc83c6492e6c0d235d14334c616837bf92843bfd2f4a3d662667765403774` |
| Earnings | `b24f5dca5c0e6b9156664aebd0a7f572cc8bbfe5fed1430fe3fbd55c77589921` | `9f7ed2c66d5f66e9e647b1b14bf283b03bc4a5782de7f2e37d97e04488838eda` |

See the [protocol](READINESS-PROTOCOL.md) for the frozen hypothesis and null,
universe filters, execution assumptions, benchmark and exposure controls, and
the [cost gates](COST-AND-BUDGET-GATES.md) for the decision envelope.
