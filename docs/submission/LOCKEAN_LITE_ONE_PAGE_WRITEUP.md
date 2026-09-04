# Lockean Lite - One-Page Hackathon Write-Up

**Independent authorization for autonomous AI trading agents**  
**Alpaca AI Trading Agents Hackathon**

> **Autonomous judgment. Independent authority.**

Lockean Lite is a narrow, evidence-backed SPY options trading prototype built around one control principle: **the AI may decide what it wants to trade, but it cannot grant itself permission to risk capital.** The system separates AI judgment, deterministic authorization, and broker access into distinct responsibilities.

## AI Logic

The autonomous agent receives real completed-session SPY market data from Alpaca, official VIX history from Cboe, derived market context, and a real SPY option-candidate universe. The shared context includes bullish trend (`close > SMA50 > SMA200`), RSI(14) momentum, 20-session breakout state, and VIX relative to its 20-session average. These signals are delivered to the AI as context; they are **not** a hidden pre-AI execution veto.

The AI returns strict structured output with one of two decisions: `TRADE` or `NO_TRADE`. For `TRADE`, it may select only a defined-risk SPY bull call spread from the supplied candidates. It does **not** supply trusted pricing, maximum-loss calculations, policy compliance, authorization, an Authorization Receipt, or broker instructions. A real September 2 run delivered 41 option candidates and mixed market context to the agent; it independently chose `NO_TRADE`, and no authority or broker layer was invoked.

## Risk Gates and Independent Authority

When the AI proposes a trade, Lockean independently reconstructs the proposal from trusted option quotes and derives financially meaningful values itself. For the defined-risk vertical slice:

`maximum loss = trusted net debit x 100 x contracts`

The hackathon policy ceiling is **$150 maximum loss**. In controlled proof, fresh trusted pricing moved one candidate to **$164 maximum loss**. Lockean rejected the proposal even though an earlier estimate had appeared acceptable; **no broker order was submitted**.

A compliant proposal must also satisfy exact structure, quantity, leg, expiration, strike-order, account-status, options-level, buying-power, evidence-source, evidence-time, and proposal-binding requirements. Authorization is not represented by a Boolean. Lockean Authority issues a **cryptographically authenticated, short-lived Authorization Receipt bound to the exact proposal fingerprint**. Changing financially meaningful fields, presenting an expired or forged receipt, or presenting a receipt for a different proposal fails closed.

The Execution Gateway is a separate component. It has broker access but **cannot self-authorize**. Immediately before submission, it independently verifies receipt existence, signature, expiry, and exact proposal-fingerprint match.

## Alpaca Infrastructure

Lockean Lite integrates Alpaca at multiple independent boundaries:

- **Alpaca Market Data** for SPY completed-session evidence.
- **Alpaca Options APIs** for SPY option contracts and latest quotes.
- **Alpaca CLI** for strict read-only paper-account evidence (`GET /v2/account`).
- **Alpaca Paper Trading** for the final MLEG DAY limit-order submission.

The execution adapter resolves the exact option contract symbols and preserves the authorized debit constraint with a multi-leg limit order rather than allowing unconstrained market-price drift.

In final controlled proof, Lockean authorized a compliant SPY 782/785 bull call spread, the separate gateway verified `execution_authority_valid`, and Alpaca independently confirmed the resulting paper **MLEG order FILLED at a $0.89 limit price**.

## Final Evidence

**Real autonomous run:** 41 candidates -> `NO_TRADE` -> authority not invoked -> no order  
**Independent risk proof:** $164 trusted max loss > $150 policy -> rejected  
**Authorization proof:** proposal-bound short-lived receipt -> authorized while broker still untouched  
**Execution proof:** receipt independently verified -> Alpaca paper MLEG -> **FILLED @ $0.89**  
**Engineering seal:** **197 automated tests passed, 0 regressions**

**Lockean Lite is not primarily an AI trading bot with risk rules attached. It is a separate authorization system that allows powerful AI to make autonomous financial judgments without ever becoming its own execution authority.**
