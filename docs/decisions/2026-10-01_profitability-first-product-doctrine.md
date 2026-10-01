# Profitability-First Product Doctrine

**Date:** October 1, 2026

**Status:** Accepted

**Authority:** Founder product directive

## Decision

Lockean's primary objective is durable net profitability.

> **Profit is the proof. Everything else must earn its place.**

Every proposed capability must do at least one of four jobs:

1. **Create profit** through research, signal quality, strategy selection, or
   execution quality.
2. **Preserve profit** through sizing, exits, drawdown containment, and capital
   survival.
3. **Scale profit** through reliable automation and deployable operations.
4. **Prove profit** through broker-grounded P&L, attribution, benchmarks, and
   reproducible evidence.

Work that does none of these is not a product priority.

## Why This Changed

The hackathon implementation optimized first for authority separation,
auditability, lifecycle proof, and presentation. Those controls worked, but the
strategy did not demonstrate positive P&L. Days 16 and 17 produced five stopped
spreads in five submitted entries for a combined **-$33.50**. Day 17 alone
closed **-$23.30**.

The `active_paper` prompt explicitly preferred `TRADE` to generate lifecycle
evidence. Day 17 consequently produced fourteen bullish `TRADE` judgments and
only one `NO_TRADE` judgment even while most supplied market filters failed.
That mode served engineering validation but conflicts with the product's
permanent objective.

## Objective, Constraints, and Evidence

| Layer | Permanent rule |
|---|---|
| Objective | Maximize broker-grounded net P&L after losses and execution friction |
| Survival constraints | Avoid ruin, uncontrolled drawdown, stale authority, and unbounded exposure |
| Truth constraints | Never label a strategy profitable without sufficient out-of-sample evidence |
| Architecture | Preserve independent proposal, authorization, and execution roles |
| Presentation | Explain verified results; never substitute for them |

The authority boundary is not cosmetic. It preserves capital and makes any
eventual profit scalable without granting the AI unilateral broker power.

## First Runtime Implementation

The normal launcher now selects `profit_first` mode instead of `active_paper`.
The initial executable hypothesis is deliberately narrow:

- instrument: SPY options;
- structure: one-contract bull-call debit spread;
- completed-session evidence: trend, momentum, breakout, and volatility must
  all pass;
- intraday evidence: current-session, 15-minute, and 30-minute direction must
  all be up, and the intraday feed must be fully available;
- economics: trusted quote-derived maximum reward-to-risk must be at least
  **1.50:1** after an estimated **$0.10** round-trip cost per contract;
- exposure: one committed spread maximum;
- exits: **+30%** take-profit and **-20%** stop-loss thresholds;
- session loss loop: the first broker-confirmed stop disables all later entries;
- cadence: 15-minute evaluation, 30-minute post-submission cooldown, and no new
  entry during the final 30 minutes.

The AI may still decline a qualifying setup. It cannot override a failed
profit-first gate, determine trusted pricing, authorize itself, or reach the
broker directly.

## Profitability Scorecard

Every naturally completed session reports:

- opening equity;
- closing equity;
- net equity change;
- Alpaca broker day P&L;
- number of AI entry evaluations; and
- `POSITIVE`, `FLAT`, or `NEGATIVE` outcome.

An operationally clean negative day is still a negative result.

## Strategy Promotion Standard

The current strategy remains `EXPERIMENTAL`. It will not be described as
profitable or become eligible for live capital merely because one session wins.

Initial promotion requires all of the following:

1. positive net realized paper P&L after execution costs;
2. positive per-trade expectancy;
3. profit factor of at least **1.25**;
4. at least **100 closed paper trades** across at least **20 trading sessions**;
5. positive walk-forward or otherwise held-out results;
6. maximum peak-to-trough drawdown no greater than **5%**;
7. no single trade or trading day contributing more than **25%** of total
   profit; and
8. complete broker reconciliation with no unknown exposure.

These are minimum promotion gates, not optimization targets. Strategy research
may raise them when evidence warrants it.

## Failure Modes Addressed

- Trading for activity rather than expected value.
- Treating test count or autonomous uptime as financial success.
- Repeating correlated entries against unchanged daily evidence.
- Calling a lucky session a profitable strategy.
- Ignoring transaction friction in apparent reward-to-risk.
- Letting a presentation obscure negative P&L.

## Explicit Non-Claims

- This change does not prove that the current hypothesis is profitable.
- Signal confluence is a testable hypothesis, not established alpha.
- Paper fills do not prove identical live-market execution.
- Live-capital authority remains disabled.

