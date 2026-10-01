# Lockean Lite — Day 18 Profitability-First Pivot

**Date:** October 1, 2026

**Mode:** Alpaca paper only

**Mission:** Replace evidence-generation trading bias with an explicit,
measurable profit-first strategy contract and judge the first completed session
strictly by its financial evidence.

## Final Verdict

Day 18 completed automatically with **$0.00 Alpaca day P&L**, unchanged equity,
no position, no order, and no runtime error. That is a successful capital-
preservation day and an operationally clean session. It is **not evidence of a
profitable strategy**. No trade qualified, no proposal reached the deterministic
economics gate, and no entry or exit lifecycle ran.

The session also found two profit-accounting defects in the new contract:

1. Lockean made 24 external AI inference requests after the immutable
   completed-session filters had already made every entry ineligible.
2. The end-of-day scorecard called the broker result `FLAT` without saying that
   model and infrastructure costs were excluded.

Both defects are corrected after this session. A deterministic market preflight
now runs before option discovery and AI inference, and the scorecard now labels
its scope as broker-only while all-in operating costs remain untracked.

## Problem

Days 16 and 17 proved that the autonomous lifecycle and loss-loop controls
worked, but the trading logic lost **$33.50** across five submitted spreads.
The previous `active_paper` mode intentionally preferred activity because its
goal was exercising the lifecycle. That goal is now retired for normal
sessions.

## Responsibility

Lockean must distinguish three claims:

1. **Operational:** the autonomous system ran correctly.
2. **Strategic:** an entry hypothesis met its stated rules.
3. **Financial:** the strategy produced positive broker P&L and positive all-in
   net P&L after operating costs.

Only the third is business success. The first two are necessary evidence, not
the product objective.

## Contract

The approved launcher now:

- uses `profit_first` rather than `active_paper`;
- never asks the AI to trade for lifecycle activity;
- permits only the currently explicit bullish-confluence hypothesis;
- rejects trusted spread economics below 1.50:1 maximum reward-to-risk after
  estimated round-trip cost;
- caps exposure at one spread and daily new-entry loss at $150;
- uses +30% / -20% exit thresholds;
- halts new entries after one confirmed stop;
- evaluates entries every 15 minutes with a 30-minute post-fill cooldown;
- blocks new entries during the final 30 minutes; and
- prints a broker-grounded profitability scorecard at normal session close.

## Architecture Placement

The AI receives the profit objective as judgment context but receives no new
authority. After Day 18, the deterministic market-only portion of
`profit_first_entry_policy` runs before option discovery or AI inference. Only
an eligible market reaches AI judgment. The full structure and quote-economics
policy still runs after trusted proposal reconstruction and before portfolio
policy, Lockean Authority, receipt issuance, or the Execution Gateway.

The order remains:

```text
deterministic market preflight
  -> option discovery and AI judgment
  -> trusted proposal reconstruction
  -> deterministic structure and economics eligibility
  -> portfolio and loss-loop policy
  -> Lockean Authority
  -> proposal-bound receipt
  -> Execution Gateway
  -> Alpaca paper broker
```

## Files

- `src/lockean_lite/profit_first_entry_policy.py`
- `src/lockean_lite/profitability_scorecard.py`
- `src/lockean_lite/ai_recommendation_provider.py`
- `src/lockean_lite/production_runtime.py`
- `src/lockean_lite/autonomous_session.py`
- `src/lockean_lite/session_launcher.py`
- `tests/test_profit_first_entry_policy.py`
- `tests/test_profit_first_mode.py`
- `tests/test_profitability_scorecard.py`
- `tests/test_production_runtime.py`
- `tests/test_session_launcher.py`
- `tests/test_autonomous_session.py`

## Test Contract

- Profit-first prompts contain no `Prefer decision=TRADE` activity bias.
- `NO_TRADE` is preferred when a credible net edge is absent.
- Failed daily confluence blocks the proposal.
- Incomplete or misaligned intraday evidence blocks the proposal.
- Bearish structures remain blocked until a symmetric bearish hypothesis is
  researched and validated.
- Weak reward-to-risk after costs blocks the proposal.
- The gate cannot authorize or execute.
- The launcher cannot silently revert to activity mode or the former exposure
  budget.
- A completed session labels broker P&L as positive, flat, or negative.

**Regression result after the Day 18 correction:** 369 passed, 1 known
third-party deprecation warning, 0 regressions.

## Day 18 Execution Record

The launcher created this file on the operator's computer:

`lockean-lite/logs/lockean_lite_DAY18_20261001_093604.log`

The filename records a **09:36:04 ET** launch, **6 minutes 4 seconds after** the
09:30 market open. The first completed intraday bar was 09:35 ET. This lateness
did not omit a policy-qualified entry: all four completed-session requirements
failed for every evaluation, and the 15- and 30-minute evidence required by the
strategy was not complete at the open.

## Sanitized Evidence

| Observation | Result |
|---|---:|
| Portfolio snapshots | 759 |
| Open-market snapshots | 758 |
| Market-close snapshots | 1 |
| Entry evaluations | 24 |
| AI `NO_TRADE` decisions | 24 |
| AI `TRADE` decisions | 0 |
| Deterministic proposal-gate evaluations | 0 |
| Entry orders submitted | 0 |
| Exit orders submitted | 0 |
| Managed-position checks reporting none | 758 |
| End-of-day cleanup/cutoff cycles | 58 |
| Recoverable or fatal errors | 0 |
| Opening equity | $99,399.75 |
| Closing equity | $99,399.75 |
| Alpaca day P&L | $0.00 |
| Total P&L from $100,000 baseline | -$600.25 |
| Closing positions | 0 |
| Closing pending entry, exit, or unknown orders | 0 |

Day 17's documented closing equity was $99,400.07, while Day 18 opened at
$99,399.75, an inter-session difference of **-$0.32**. The Day 18 log cannot
attribute that adjustment, and Alpaca reported $0.00 Day 18 P&L throughout. It
is retained as an unresolved reconciliation item rather than silently folded
into the Day 18 result.

## Market and Decision Evidence

The completed-session vector was unchanged across all 24 evaluations:

```text
trend=FAIL; momentum=FAIL; breakout=FAIL; volatility=FAIL
```

Intraday evidence warmed normally: the first evaluation was `WARMING_UP`, and
the other 23 were `AVAILABLE`. Sampled SPY session return ranged from -0.376%
to +0.308%. Five evaluations eventually had session, 15-minute, and 30-minute
directions all `UP`, but the immutable daily requirements still failed. The AI
therefore returned `NO_TRADE` every time.

This means the prompt-level behavior changed exactly as intended relative to
Day 17: it did not trade merely to create activity. It also means the full
post-proposal gate—bull-call structure, trusted debit, after-cost reward-to-risk,
portfolio capacity, authority, and execution—was never exercised live.

## What Day 18 Proved

- The approved launcher used `profit_first` with the one-spread, $150 loss,
  +30% take-profit, -20% stop, one-stop halt, 15-minute entry, 30-second risk,
  and 30-minute end-of-day contracts.
- The launcher stored the complete log under the repository's `logs` folder.
- Removing the activity-generation bias worked: 24 ambiguous or ineligible
  observations produced 24 `NO_TRADE` decisions and zero orders.
- Capital was preserved inside the broker account for the session.
- Reconciliation, market-clock handling, loss-loop reading, end-of-day cleanup,
  scorecard output, and automatic shutdown completed without an error.

## What Day 18 Did Not Prove

- It did not produce profit, a winning trade, positive expectancy, profit
  factor, or any evidence toward the 100-trade promotion sample.
- It did not prove the 1.50:1 economics gate against a live proposal.
- It did not exercise an entry fill, take-profit, stop-loss, cooldown, first-stop
  session halt, or pending-order cancellation.
- It did not measure all-in net P&L because AI and infrastructure costs were not
  captured.
- One flat broker day cannot validate the bullish-confluence hypothesis.

## Evidence-Driven Correction

The immutable daily failures made the session ineligible before option quotes
or AI judgment were useful. The corrected runtime now:

1. builds the market context;
2. runs `evaluate_profit_first_market_context`;
3. returns deterministic `NO_TRADE` with `agent_decision=SKIPPED` when a hard
   prerequisite fails;
4. discovers option candidates and calls the AI only after market eligibility;
5. still reconstructs trusted pricing and applies the full post-proposal
   structure/economics gate before any authority decision; and
6. prints `SCOPE: BROKER ACCOUNT ONLY`, `OPERATING COSTS: NOT TRACKED`, and
   `ALL-IN NET P&L: UNKNOWN` at close.

This preserves the strategy rules while removing inference work that could not
possibly produce an authorized trade.

## Day 19 Decision

Day 19 is a repeat of the same experimental hypothesis, not a parameter-tuning
session. The only routine calendar roll is the option expiration from October 2
to October 9 so the next session does not silently become a zero-day-to-
expiration experiment.

Run on the next trading day, October 2, 2026, from the repository after pulling
the merged correction and activating `.venv`:

```powershell
python -m lockean_lite.session_launcher `
  --day-number 19 `
  --completed-through 2026-10-01 `
  --expiration 2026-10-09
```

Day 19 must be judged in this order: all-in accounting completeness, broker net
P&L, expectancy evidence, drawdown, and only then operational behavior. A clean
flat day remains non-profitable evidence, not a win.

Live-capital authority remains disabled. No code is bulk-transferred into
Project Lockean Core.
