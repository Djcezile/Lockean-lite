# Lockean Lite — 3-Minute Demo Video Script

## Goal

Show one thing clearly:

**The AI may recommend a trade, but it cannot execute unless Lockean independently verifies and authorizes the exact proposal.**

Target runtime: **2:45–3:15**

---

## 0:00–0:20 — Opening Hook

### On screen
Show the Lockean Lite README title or the browser dashboard header.

### Say
> "AI trading agents are getting better at making financial decisions. But intelligence and authority are not the same thing."

> "Lockean Lite is an independent execution authority for autonomous AI trading agents."

> "The AI can recommend a trade. It cannot authorize or execute one."

---

## 0:20–0:45 — Architecture

### On screen
Show the architecture diagram from the README.

### Say
> "Every action moves through a separate deterministic control plane."

> "Real market evidence enters first. If the market qualifies, the AI may produce only structured trade intent."

> "Lockean then independently reconstructs the proposal from trusted prices, calculates maximum loss, verifies account eligibility, and binds the exact proposal to a short-lived cryptographically authenticated Authorization Receipt."

> "The Execution Gateway verifies that receipt before Alpaca can receive an order."

---

## 0:45–1:20 — Real Rejection Demo

### On screen
Run:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31
```

Then show the output.

### Say
> "This is a real completed market session."

> "SPY evidence comes from Alpaca. VIX history comes from official Cboe data."

> "Trend passed. Momentum passed. Volatility passed. The breakout requirement failed."

> "So Lockean rejected the cycle before the AI was even called."

Point to:

```text
DECISION: REJECTED
REASON: breakout_filter_failed

AI RECOMMENDATION REACHED: NO
AUTHORITY REACHED: NO
AUTHORIZATION RECEIPT ISSUED: NO
BROKER ORDER SUBMITTED: NO
```

### Say
> "No threshold was changed to force a trade. Missing permission means no broker order."

---

## 1:20–1:40 — Browser Proof

### On screen
Generate the dashboard:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31 `
  --format html `
  --output .\lockean-demo.html

Start-Process .\lockean-demo.html
```

Show the rendered rejection dashboard.

### Say
> "This browser view is intentionally read-only."

> "It does not recalculate the policy, authorize anything, or possess execution capability."

> "Lockean decides. The interface only displays."

---

## 1:40–2:05 — AI Does Not Own Risk

### On screen
Show the real AI recommendation example:

```text
BUY  SPY 2026-09-18 775 Call
SELL SPY 2026-09-18 780 Call
1 contract
```

Then show:

```text
Net debit:    $2.13
Maximum loss: $213.00
Policy limit: $150.00
```

### Say
> "We also tested the AI against real Alpaca option candidates."

> "The AI selected this spread, but it did not supply the trusted price or maximum loss."

> "Lockean independently derived a $213 maximum loss against a $150 policy ceiling."

> "The AI could recommend the trade. It could not declare itself compliant."

---

## 2:05–2:35 — Authorization and Execution Proof

### On screen
Show this flow:

```text
TradeProposal
    ↓
Lockean Authority
    ↓
Signed Authorization Receipt
    ↓
Execution Gateway verifies exact receipt + proposal
    ↓
Alpaca paper submit_order()
    ↓
Sanitized ExecutionProof
```

If a genuine successful paper execution has already occurred by recording time, replace this section with the actual success proof page and show:

```text
SUBMITTED
paper_order_submitted

Proposal ID
Proposal Fingerprint
Authorization Receipt ID
execution_authority_valid
Alpaca Paper Broker Order ID
```

### Say
> "If every requirement passes, Lockean issues a short-lived receipt bound to the exact proposal fingerprint."

> "The Execution Gateway independently verifies that receipt. Change the quantity, strikes, expiration, legs, or other fingerprint-bound contents and execution fails."

If real success exists:

> "This Alpaca paper order ID is the broker-side proof that the exact authorized proposal crossed the real paper-trading boundary."

If real success does not yet exist:

> "The production path is complete, but we will not weaken the market policy simply to manufacture a successful order. A genuine paper execution remains dependent on qualifying real market evidence."

---

## 2:35–3:00 — Closing

### On screen
Return to the Lockean title / architecture.

### Say
> "Lockean Lite is not an AI trading bot with safety rules attached."

> "It separates intelligence from authority."

> "The AI can be creative and probabilistic. Execution permission remains deterministic, specific, short-lived, and independently verified."

> "AI proposes. Lockean verifies. Authority decides. Only then may software act."

---

# Recording Checklist

- Hide all API keys, secrets, terminal history containing credentials, and environment-variable values.
- Use the real August 31 rejection demo.
- Keep the browser dashboard visible long enough to read the rejection and downstream status.
- Show the architecture diagram once.
- Show the AI risk example once.
- If a genuine Alpaca paper order exists before recording, show the sanitized proof only — never the signed receipt or signing key.
- Keep the final video near three minutes.
- Avoid narrating implementation details that do not support the central thesis.
- Record at 1080p if possible.
- Use a large terminal font and browser zoom so judges can read the output.
- Verify audio levels before recording the final take.

---

# Final Recording Rule

The video must never imply a real successful paper execution occurred unless Lockean actually traversed the complete production authority chain and Alpaca returned a genuine paper broker order ID.
