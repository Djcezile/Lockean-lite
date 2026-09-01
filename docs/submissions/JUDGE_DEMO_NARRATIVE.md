# Lockean Lite — Judge & Demo Narrative

## One-Sentence Pitch

**Lockean Lite is an independent execution authority that prevents an AI trading agent from executing a trade unless real market evidence, defined risk, account eligibility, proposal integrity, and cryptographic authorization all independently pass.**

---

## The Problem

AI trading agents are becoming increasingly capable of:

- analyzing markets,
- selecting instruments,
- constructing strategies,
- and recommending trades.

But there is a dangerous architectural assumption in many autonomous systems:

> The same AI that proposes the action is also trusted to execute it.

That means an AI hallucination, malformed proposal, stale observation, altered quantity, excessive risk, or compromised agent can potentially become a broker order.

Lockean Lite removes that authority from the AI.

---

## The Core Idea

The AI is a recommender.

It is not the execution authority.

```text
AI proposes
     ↓
Lockean independently verifies
     ↓
Authority decides
     ↓
Execution Gateway verifies permission
     ↓
Only then may Alpaca receive an order
```

There is no AI-to-broker shortcut.

---

# 30-Second Judge Explanation

Lockean Lite separates intelligence from authority.

The AI may recommend a defined-risk options trade, but it cannot determine whether market conditions passed, calculate trusted pricing or maximum loss, authorize itself, create execution permission, or submit a broker order.

Lockean independently evaluates real market evidence from Alpaca and Cboe, reconstructs the financially meaningful proposal from trusted data, checks risk and account eligibility, and binds the exact proposal to a short-lived cryptographically authenticated Authorization Receipt.

The Execution Gateway independently verifies that receipt immediately before broker interaction.

If anything is missing, stale, forged, altered, excessive, or unsupported, the system fails closed.

---

# Why This Is Different From AI Risk Rules

Lockean Lite is not simply:

```text
AI trading bot
+
some safety checks
```

The distinction is architectural.

The AI does not possess the capability required to bypass Lockean.

The authority to execute exists in a separate deterministic system.

That means the AI cannot simply:

- ignore a risk rule,
- rewrite a quantity,
- change an option leg,
- reuse an expired authorization,
- fabricate market-policy approval,
- or call the broker directly.

Permission must be independently earned.

---

# Trust Boundary

The system intentionally separates four responsibilities.

## 1. Market Evidence

Real external observations enter Lockean.

Current evidence sources:

```text
SPY → Alpaca
VIX → official Cboe history
```

The AI does not supply indicator conclusions.

---

## 2. AI Recommendation

The AI may recommend only structured trade intent:

```json
{
  "symbol": "SPY",
  "expiration": "2026-09-18",
  "buy_strike": 775,
  "sell_strike": 780,
  "contracts": 1
}
```

It does not control:

```text
net debit
maximum loss
market verdict
authorization
receipt
broker order
```

---

## 3. Lockean Authority

Lockean independently verifies:

```text
market-entry policy
proposal structure
trusted option pricing
defined maximum loss
configured risk policy
validated evidence
proposal fingerprint integrity
paper-account state
options eligibility
buying power
```

Only after those checks may Lockean Authority issue a short-lived Authorization Receipt.

---

## 4. Execution Gateway

The Execution Gateway independently verifies:

```text
receipt exists
receipt signature is authentic
receipt is unexpired
receipt belongs to the exact proposal fingerprint
```

Only then may broker contract resolution and order submission occur.

---

# Why Proposal Fingerprinting Matters

An Authorization Receipt does not merely say:

```text
proposal-123 may trade
```

It is bound to the exact financially meaningful proposal.

If quantity, strikes, expiration, legs, net debit, or other fingerprint-bound information changes after authorization, execution fails.

This prevents an authorized small trade from being silently transformed into a different trade before broker submission.

---

# Real Rejection Demonstration

Lockean Lite has already been exercised against real completed market evidence.

For the completed August 31, 2026 session:

```text
SPY / Alpaca: 766.87
VIX / Cboe:   14.920000
```

Lockean independently evaluated:

```text
Trend:      PASS
Momentum:   PASS
Breakout:   FAIL
Volatility: PASS
```

Final result:

```text
DECISION: REJECTED
REASON: breakout_filter_failed
```

Because the market-entry policy failed:

```text
AI Recommendation       NOT REACHED
Lockean Authority       NOT REACHED
Authorization Receipt   NOT ISSUED
Broker Order            NO ORDER
```

No threshold was weakened to manufacture a successful demo.

That rejection is the intended system behavior.

---

# What The Rejection Demo Proves

It proves that:

```text
real market data
        ↓
independent deterministic policy
        ↓
rejection
        ↓
downstream system never receives authority
```

More importantly, the demo is structurally read-only.

The judge-facing market-evidence command has no Execution Gateway or broker-order capability.

The presentation layer cannot turn a rejection into execution.

---

# Real AI Risk Demonstration

Lockean Lite has also been exercised with:

```text
real Alpaca option candidates
+
real OpenAI recommendation
```

The AI recommended:

```text
BUY  SPY 2026-09-18 775 Call
SELL SPY 2026-09-18 780 Call
1 contract
```

The AI did not supply pricing or maximum loss.

Using trusted Alpaca option quotes, Lockean independently derived:

```text
Net debit:    $2.13
Maximum loss: $213.00
Policy limit: $150.00
```

The resulting proposal exceeded Lockean's configured maximum-loss policy.

The AI could not declare itself compliant.

---

# Successful Execution Path

A successful trade must traverse the complete production path:

```text
Real qualifying market evidence
        ↓
AI structured recommendation
        ↓
Lockean trusted-quote proposal construction
        ↓
Lockean maximum-loss calculation
        ↓
Evidence bound to proposal fingerprint
        ↓
Paper-account eligibility
        ↓
Lockean Authority
        ↓
Signed short-lived Authorization Receipt
        ↓
Execution Gateway independently verifies receipt
        ↓
Exact Alpaca MLEG DAY limit order
        ↓
Alpaca paper submit_order()
        ↓
Broker order ID
        ↓
Sanitized ExecutionProof
```

There is no success-specific bypass created for the demonstration.

---

# Execution Proof

After a successful broker submission, Lockean preserves a sanitized proof record containing:

```text
proposal ID
proposal fingerprint
Authorization Receipt ID
execution-authority verification result
Alpaca paper broker order ID
```

The judge-facing proof deliberately does not expose:

```text
Authority signing key
Authority signature
complete signed Authorization Receipt
raw Alpaca broker object
```

The execution-capable artifacts remain inside the authority boundary.

---

# Why The Receipt Is Short-Lived

Authorization should represent permission for a specific decision context.

A receipt that remained valid indefinitely could be replayed after:

```text
market conditions changed
account state changed
proposal context changed
time-sensitive evidence became stale
```

Lockean therefore issues short-lived permission and the Execution Gateway checks expiration immediately before execution.

---

# Why The Broker Order Is A Limit Order

Lockean authorizes a defined debit.

Using a market order could allow the broker fill price to exceed the amount Lockean evaluated.

The execution adapter therefore constructs an Alpaca multi-leg DAY limit order so execution remains bounded by the authorized debit.

---

# Failure Philosophy

Lockean Lite follows one rule throughout the system:

> Missing trustworthy information never becomes permission.

Examples:

```text
missing market evidence
→ fail closed

mismatched evidence timestamps
→ fail closed

unsupported strategy
→ fail closed

invalid option structure
→ fail closed

risk above policy
→ fail closed

insufficient account eligibility
→ fail closed

missing receipt
→ fail closed

forged receipt
→ fail closed

expired receipt
→ fail closed

changed proposal
→ fail closed
```

---

# Transaction Truth vs Presentation Truth

Lockean also separates broker truth from presentation behavior.

If Alpaca accepts a paper order and later HTML proof generation fails:

```text
TRANSACTION RESULT:
SUBMITTED
```

remains true.

The presentation subsystem separately reports:

```text
execution_proof_output_write_failed
```

A visualization failure can never rewrite broker history.

---

# Demo Flow

## Part 1 — Show The Architecture

Explain:

> "The AI can recommend a trade, but it cannot execute one. Lockean owns the independent authority boundary."

Show:

```text
AI
↓
Lockean verification
↓
Authority Receipt
↓
Execution Gateway
↓
Alpaca
```

Target time: 20–30 seconds.

---

## Part 2 — Run The Real Rejection

Execute the read-only demo against a completed session.

Example:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31
```

Explain:

> "These are real SPY observations from Alpaca and official VIX history from Cboe. Lockean independently evaluates the entry conditions."

Show:

```text
Trend PASS
Momentum PASS
Breakout FAIL
Volatility PASS
```

Then:

```text
REJECTED
breakout_filter_failed
```

Point out:

```text
AI NOT REACHED
AUTHORITY NOT REACHED
BROKER NO ORDER
```

Target time: 30–45 seconds.

---

## Part 3 — Show The Browser View

Generate:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31 `
  --format html `
  --output .\lockean-demo.html
```

Open:

```powershell
Start-Process .\lockean-demo.html
```

Explain:

> "The browser does not calculate anything. It displays the immutable decision Lockean already produced."

Target time: 20 seconds.

---

## Part 4 — Explain The AI Boundary

Show the five-field recommendation schema.

Explain:

> "The AI chooses trade intent. It does not provide trusted price, maximum loss, policy compliance, authorization, or broker instructions."

Then show the real AI recommendation that Lockean independently calculated at $213 maximum loss against a $150 policy ceiling.

Target time: 20–30 seconds.

---

## Part 5 — Show Authorization Security

Explain:

> "If Lockean authorizes a proposal, it issues a cryptographically authenticated, short-lived receipt bound to the exact proposal fingerprint."

Then:

> "The Execution Gateway recomputes that proposal fingerprint and independently verifies the receipt. Change the quantity, legs, expiration, or other financial contents and execution fails."

Target time: 20–30 seconds.

---

## Part 6 — Real Successful Execution

When real qualifying evidence is available:

Show the completed production result:

```text
SUBMITTED
paper_order_submitted
```

Then show sanitized proof:

```text
Proposal ID
Proposal Fingerprint
Authorization Receipt ID
execution_authority_valid
Alpaca Paper Broker Order ID
```

Explain:

> "This order was not submitted by the AI. It crossed the broker boundary only after Lockean independently authorized the exact proposal and the Execution Gateway independently verified that authorization."

Target time: 30–45 seconds.

---

# Three-Minute Demo Narrative

## Opening

> "AI agents are becoming capable of making increasingly consequential financial decisions. Lockean asks a different question: even if the AI is intelligent enough to recommend the action, should it also possess the authority to execute it?"

> "Our answer is no."

---

## Architecture

> "The AI in Lockean Lite can produce only structured trade intent. It cannot determine trusted pricing, calculate maximum loss, approve market conditions, issue authorization, or contact the broker."

> "Those responsibilities belong to a separate deterministic authority."

---

## Rejection

> "Here is Lockean running against real completed SPY data from Alpaca and official VIX history from Cboe."

> "Trend passed. Momentum passed. Volatility passed. The breakout requirement failed."

> "Lockean therefore rejected the cycle before the AI was even called. No Authority evaluation occurred and no broker order existed."

---

## AI Independence

> "We also tested the AI against real option candidates. It selected a spread, but Lockean independently priced it at a $213 maximum loss against a $150 policy limit."

> "The AI could recommend the trade. It could not declare itself compliant."

---

## Authorization

> "If every requirement passes, Lockean issues a short-lived cryptographically authenticated receipt bound to the exact proposal fingerprint."

> "The Execution Gateway independently verifies that receipt. Any tampering after authorization fails closed."

---

## Close

> "The core idea is not to make AI less capable."

> "It is to let powerful AI participate in consequential systems without giving it unilateral authority over the final action."

> "AI proposes. Lockean verifies. Authority decides. Only then may software act."

---

# What Judges Should Remember

If a judge remembers only three things:

### 1. The AI cannot execute.

Broker execution authority exists outside the AI.

### 2. Authorization is specific.

Permission is cryptographically authenticated, short-lived, and bound to the exact proposal fingerprint.

### 3. We prove both denial and permission.

Lockean can demonstrate:

```text
real evidence
→ real rejection
→ zero broker order
```

and, when qualifying market evidence occurs:

```text
real evidence
→ real independent authorization
→ genuine Alpaca paper order
→ genuine broker order ID
```

---

# Current Verified Engineering State

```text
163 tests passed
0 regressions
1 known third-party dependency warning
```

Real external integrations already verified include:

```text
Alpaca paper account
Alpaca SPY market data
Alpaca option-contract discovery
Alpaca option quotes
OpenAI structured recommendation
official Cboe VIX history
real broker-facing MLEG order construction
```

The remaining real-market acceptance criterion is:

```text
first genuine qualifying evidence-backed
Alpaca paper order
through the complete Lockean authority chain
```

Lockean will not weaken its policy merely to manufacture that result.

---

# Closing Line

> **Intelligence may recommend the action. Authority must still be earned.**
