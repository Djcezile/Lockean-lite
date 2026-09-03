# Lockean Lite - Day 7 Hackathon Pivot
**Date:** 2026-09-02

## Pivot Decision

Late in Day 7, review of the hackathon judging model exposed a responsibility error in the Lockean Lite trading architecture.

The system had been using deterministic trend, momentum, breakout, and volatility signals as a pre-AI execution gate. When any signal failed, the autonomous cycle ended before the trading agent was allowed to evaluate the opportunity.

That behavior was safe, but it assigned trading judgment to the wrong component.

## Corrected Responsibility Boundary

The trading agent owns the trading decision.

The agent may:

- analyze trusted market evidence
- decide whether to trade
- select the supported trade structure
- choose strikes, expiration, and quantity
- explicitly choose no trade

Lockean owns execution authority.

Lockean independently determines whether a proposed action may use capital by validating evidence, proposal integrity, trusted pricing, maximum loss, account eligibility, policy compliance, authorization, and execution permission.

## What Does Not Change

The pivot does not weaken the Lockean authority boundary.

The following remain unchanged:

- AI has no broker execution authority
- defined-risk options only
- independent trusted pricing
- independent maximum-loss calculation
- maximum-loss policy ceiling
- paper-account eligibility
- proposal fingerprinting
- short-lived signed Authorization Receipts
- receipt/proposal exact-match enforcement
- Execution Gateway verification
- fail-closed behavior
- Alpaca paper trading only

## Signal Responsibility

Trend, RSI, breakout, and VIX observations remain useful market information.

They no longer possess veto authority over whether the trading agent may evaluate a market opportunity.

They become decision context for the trading agent.

## Hackathon Acceptance Goal

A successful pivot requires more than green tests.

The final acceptance criterion is a genuine autonomous Alpaca paper order produced through the full path:

market evidence
-> trading agent
-> structured proposal
-> Lockean validation
-> Lockean Authority
-> signed Authorization Receipt
-> Execution Gateway
-> Alpaca paper order

Profitability is secondary to proving real autonomous operation under independent execution authority.
