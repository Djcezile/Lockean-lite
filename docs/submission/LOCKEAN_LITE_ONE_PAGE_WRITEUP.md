# Lockean Lite - One-Page Hackathon Write-Up

**Independent authorization for autonomous AI trading agents**  
**Alpaca AI Trading Agents Hackathon**

> **Autonomous judgment. Independent authority.**

Lockean Lite is an autonomous SPY options paper-trading agent built around one control principle: **the AI may decide what it wants to trade, but it cannot grant itself permission to risk capital.** The system separates AI judgment, deterministic authorization, broker access, and read-only portfolio telemetry into distinct responsibilities.

## AI Logic and Autonomous Session

The agent receives real completed-session SPY market data from Alpaca, official VIX history from Cboe, derived market context, and a live SPY option-candidate universe. The shared context includes bullish trend (`close > SMA50 > SMA200`), RSI(14) momentum, 20-session breakout state, and VIX relative to its 20-session average. These signals are delivered to the AI as context; they are **not** a hidden pre-AI execution veto.

The AI returns strict structured output with one of two decisions: `TRADE` or `NO_TRADE`. For `TRADE`, it may select only a defined-risk SPY bull call spread from supplied candidates. It does **not** supply trusted pricing, maximum-loss calculations, policy compliance, authorization, an Authorization Receipt, or broker instructions.

A persistent Alpaca-paper session runner now operates from one command. It reads Alpaca's market clock and linked paper portfolio, waits while the market is closed, repeatedly evaluates opportunities while the market is open, refreshes account state between cycles, and stops after the session closes. Portfolio controls cap committed exposure at **five managed spread units**, count pending MLEG orders toward that cap, constrain each new recommendation to one spread unit, and halt new entries after a configured daily-loss threshold.

## Risk Gates and Independent Authority

When the AI proposes a trade, Lockean independently reconstructs the proposal from trusted option quotes and derives financially meaningful values itself. For the defined-risk vertical slice:

`maximum loss = trusted net debit x 100 x contracts`

The per-proposal hackathon policy ceiling is **$150 maximum loss**. In controlled proof, fresh trusted pricing moved one candidate to **$164 maximum loss**. Lockean rejected the proposal even though an earlier estimate had appeared acceptable; **no broker order was submitted**.

A compliant proposal must also satisfy exact structure, quantity, leg, expiration, strike-order, account-status, options-level, buying-power, evidence-source, evidence-time, and proposal-binding requirements. Authorization is not represented by a Boolean. Lockean Authority issues a **cryptographically authenticated, short-lived Authorization Receipt bound to the exact proposal fingerprint**. Changing financially meaningful fields, presenting an expired or forged receipt, or presenting a receipt for a different proposal fails closed.

The Execution Gateway is a separate component. It has broker access but **cannot self-authorize**. Immediately before submission, it independently verifies receipt existence, signature, expiry, and exact proposal-fingerprint match.

## Alpaca Infrastructure and Live P&L

Lockean Lite integrates Alpaca at multiple independent boundaries:

- **Alpaca Market Data** for SPY completed-session evidence.
- **Alpaca Options APIs** for SPY option contracts and latest quotes.
- **Alpaca Paper Trading** for real MLEG DAY limit-order submission.
- **Alpaca Account / Positions / Orders / Clock APIs** for live equity, P&L, buying power, positions, pending orders, broker history, and market-session state.

The execution adapter resolves exact option contract symbols and preserves the authorized debit constraint with a multi-leg limit order rather than allowing unconstrained market-price drift.

In controlled proof, Lockean authorized a compliant SPY 782/785 bull call spread, the separate gateway verified `execution_authority_valid`, and Alpaca independently confirmed the resulting paper **MLEG order FILLED at a $0.89 limit price**. The same linked Alpaca paper account is then read back into Lockean's telemetry, so fills and subsequent gains or losses appear in both Alpaca and the Lockean Control Room.

**Live Control Room:** https://lockean-lite.streamlit.app/

The Control Room refreshes directly from the linked Alpaca paper account every 15 seconds and displays current equity, total P&L, day P&L, unrealized P&L, cash, buying power, options buying power, managed spreads, open option legs, recent broker orders, and the Alpaca market clock. It is deliberately read-only: it cannot authorize, mint receipts, or submit orders.

## Final Evidence

**Real autonomous run:** 41 candidates -> `NO_TRADE` -> authority not invoked -> no order  
**Independent risk proof:** $164 trusted max loss > $150 policy -> rejected  
**Authorization proof:** proposal-bound short-lived receipt -> authorized while broker still untouched  
**Execution proof:** receipt independently verified -> Alpaca paper MLEG -> **FILLED @ $0.89**  
**Live portfolio proof:** same Alpaca account -> positions, equity and P&L -> public Control Room  
**Autonomous-session proof:** market-clock-aware repeated cycles -> up to 5 committed spreads -> fail-closed recovery  
**Engineering seal:** **213 automated tests passed, 0 regressions**

**Lockean Lite is not merely an AI trading bot with risk rules attached. It is an autonomous paper-trading system in which judgment, permission, broker access, and observation remain deliberately separated so that powerful AI can trade without ever becoming its own execution authority.**
