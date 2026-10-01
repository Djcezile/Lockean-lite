# Lockean Lite — Day 18 Profitability-First Pivot

**Date:** October 1, 2026

**Mode:** Alpaca paper only

**Mission:** Replace evidence-generation trading bias with an explicit,
measurable profit-first strategy contract before the Day 18 session.

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
3. **Financial:** the strategy produced positive broker-grounded net P&L.

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
authority. The deterministic `profit_first_entry_policy` runs after trusted
proposal reconstruction and before portfolio policy, Lockean Authority, receipt
issuance, or the Execution Gateway.

The order remains:

```text
AI judgment
  -> trusted proposal reconstruction
  -> deterministic profit-first eligibility
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

**Regression result:** 363 passed, 1 known third-party deprecation warning,
0 regressions.

## Day 18 Execution

After the implementation is merged to GitHub, execute:

```powershell
python -m lockean_lite.session_launcher `
  --day-number 18 `
  --completed-through 2026-09-30 `
  --expiration 2026-10-02
```

The log is written under the repository `logs` directory. Day 18 can validate
the new runtime contract; it cannot by itself validate profitability.

Live-capital authority remains disabled. No code is bulk-transferred into
Project Lockean Core.
