# Lockean Lite — Hackathon Submission Draft

## Project Name

**Lockean Lite**

## Tagline

**Independent execution authority for autonomous AI trading agents.**

## One-Sentence Pitch

Lockean Lite lets AI recommend trades without giving the AI unilateral broker execution authority: every proposal must independently satisfy real-market evidence, defined-risk policy, account eligibility, proposal-integrity checks, and cryptographic authorization before Alpaca can receive an order.

---

## Short Description

AI trading agents are becoming increasingly capable, but capability should not automatically imply authority.

Lockean Lite separates the two.

The AI may produce a structured options recommendation, but it cannot approve market conditions, determine trusted pricing, calculate maximum loss, authorize itself, create execution permission, or submit an order.

Instead, a deterministic Lockean Authority independently verifies the proposal and, only when every requirement passes, issues a short-lived cryptographically authenticated Authorization Receipt bound to the exact proposal fingerprint.

An independent Execution Gateway verifies that receipt immediately before broker interaction.

If evidence is missing, risk is excessive, account eligibility fails, a receipt is forged or expired, or the proposal changes after authorization, the system fails closed.

---

## The Problem

Many autonomous trading architectures implicitly allow the same intelligent agent to both:

1. recommend a financial action, and
2. possess the capability to execute that action.

That creates a dangerous concentration of authority.

A hallucination, malformed proposal, stale observation, excessive risk, altered quantity, compromised agent, or unexpected model behavior can become a broker order if the AI is trusted to police itself.

Lockean Lite introduces a separate execution-authority layer.

The AI can recommend.

It cannot grant itself permission.

---

## The Solution

Lockean Lite implements a narrow defined-risk options vertical slice around a SPY bull call spread.

The control flow is:

```text
Real Market Evidence
        ↓
Deterministic Entry Policy
        ↓
Trusted Option Candidate Universe
        ↓
AI Structured Recommendation
        ↓
Lockean Proposal Construction
        ↓
Trusted Quote Pricing
        ↓
Independent Risk Calculation
        ↓
Evidence / Proposal Fingerprint Validation
        ↓
Paper Account Eligibility
        ↓
Lockean Authority
        ↓
Signed Short-Lived Authorization Receipt
        ↓
Execution Gateway
        ↓
Exact Alpaca Paper Order
        ↓
Sanitized Execution Proof
```

There is no AI-to-broker shortcut.

---

## What The AI Can Do

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

The AI does not control:

```text
market-entry verdict
trusted option prices
net debit
maximum loss
policy compliance
authorization
receipt creation
broker execution
```

---

## What Lockean Independently Verifies

Lockean independently verifies:

- real SPY market evidence from Alpaca,
- official VIX history from Cboe,
- completed-session alignment,
- deterministic trend, momentum, breakout, and volatility conditions,
- supported strategy structure,
- exact option-leg structure,
- trusted option pricing,
- maximum defined loss,
- configured risk ceiling,
- paper-account status,
- trading restrictions,
- effective options trading level,
- options buying power,
- evidence-to-proposal fingerprint integrity,
- Authorization Receipt authenticity,
- Authorization Receipt expiration,
- exact proposal match at execution time.

---

## Why Authorization Receipts Matter

A Lockean Authorization Receipt is:

- issued only by Lockean Authority,
- cryptographically authenticated,
- short-lived,
- bound to the exact proposal fingerprint.

The Execution Gateway independently verifies the receipt before any broker contract lookup or order submission.

A missing, forged, expired, or proposal-mismatched receipt fails closed.

Changing the quantity, strikes, expiration, legs, net debit, or other fingerprint-bound proposal content after authorization invalidates execution.

---

## Real Rejection Demonstration

Lockean Lite has already been exercised against real completed market data.

For the completed August 31, 2026 session:

```text
SPY / Alpaca: 766.87
VIX / Cboe:   14.920000

Trend:      PASS
Momentum:   PASS
Breakout:   FAIL
Volatility: PASS
```

Lockean returned:

```text
DECISION: REJECTED
REASON: breakout_filter_failed

AI RECOMMENDATION REACHED: NO
AUTHORITY REACHED: NO
AUTHORIZATION RECEIPT ISSUED: NO
BROKER ORDER SUBMITTED: NO
```

No threshold was changed to manufacture a successful result.

The rejection is the intended behavior.

---

## Real AI Risk Demonstration

Lockean Lite has also been exercised with real Alpaca option candidates and a real structured OpenAI recommendation.

The AI recommended:

```text
BUY  SPY 2026-09-18 775 Call
SELL SPY 2026-09-18 780 Call
1 contract
```

Using trusted Alpaca option quotes, Lockean independently derived:

```text
Net debit:    $2.13
Maximum loss: $213.00
Policy limit: $150.00
```

The AI could recommend the spread.

It could not declare itself compliant with policy.

---

## Judge-Facing Demo

A read-only real-market evaluation can be reproduced with:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31
```

A browser-viewable dashboard can be generated with:

```powershell
python -m lockean_lite.market_evidence_cli `
  --completed-through 2026-08-31 `
  --format html `
  --output .\lockean-demo.html
```

The read-only demo cannot authorize or execute trades.

The visual layer displays immutable Lockean results and does not recalculate trading conditions.

---

## Successful Execution Proof

When a real market session legitimately qualifies and the complete production chain reaches Alpaca paper trading, Lockean preserves sanitized execution proof containing:

- proposal ID,
- proposal fingerprint,
- Authorization Receipt ID,
- execution-authority verification result,
- Alpaca paper broker order ID.

The proof deliberately excludes execution-capable artifacts such as:

- the Authority signing key,
- the Authority signature,
- the complete signed Authorization Receipt,
- raw Alpaca broker objects.

The execution-capable artifacts remain inside the Lockean authority boundary.

---

## Current Real-Market Status

The complete production execution path is implemented.

The remaining real-market acceptance criterion is the first genuine qualifying evidence-backed Alpaca paper order through the full Lockean authority chain.

Lockean will not weaken its deterministic market policy merely to manufacture a successful demo.

If the current completed session does not qualify, the system remains rejected by design.

---

## Why This Is Novel

The core idea is not simply to add risk rules to an AI trading bot.

The architectural distinction is that the AI does not possess the capability required to authorize or execute its own recommendation.

The execution authority exists independently.

That pattern can generalize beyond trading to any consequential AI action where intelligence and authority should be separated.

Examples include:

- financial transfers,
- infrastructure control,
- privileged security actions,
- healthcare workflows,
- enterprise approvals,
- autonomous operational systems.

---

## Why Alpaca

Alpaca provides the market-data, options, paper-account, option-contract, and paper-execution capabilities needed to demonstrate the complete authority boundary against a realistic brokerage environment.

Lockean Lite uses Alpaca for:

- SPY historical market evidence,
- option-contract discovery,
- option quote retrieval,
- paper-account state,
- options eligibility,
- broker-facing multi-leg order construction,
- paper-order submission.

The broker is the final execution destination, not the source of Lockean's policy decisions.

---

## Why OpenAI

OpenAI is used for structured recommendation generation only.

The AI receives a controlled candidate universe and may select trade intent within a strict schema.

Lockean independently owns:

- trusted market facts,
- pricing,
- maximum loss,
- policy compliance,
- authorization,
- execution.

This preserves a clean division between probabilistic intelligence and deterministic authority.

---

## Defined-Risk Vertical Slice

Lockean Lite intentionally implements one narrow strategy:

**SPY bull call spread**

A valid proposal requires:

- strategy `defined_risk_option`,
- exactly two call legs,
- one buy leg,
- one sell leg,
- matching expiration,
- buy strike below sell strike,
- positive net debit,
- positive contract quantity.

Lockean independently derives:

```text
maximum loss = net debit × 100 × contracts
```

Current configured maximum allowed loss:

```text
$150
```

The AI may know this limit as planning context, but it cannot determine compliance.

---

## Safety Invariants

Lockean Lite is built around these non-negotiable properties:

1. The AI cannot submit broker orders.
2. The AI cannot authorize its own recommendation.
3. Market evidence must come from supported external sources.
4. Lockean independently calculates financially meaningful values.
5. Authorization is bound to the exact proposal fingerprint.
6. Authorization expires.
7. Tampering after authorization fails closed.
8. The Execution Gateway independently verifies authority.
9. Invalid authority prevents downstream broker interaction.
10. Presentation layers cannot authorize or execute.
11. A later presentation failure cannot rewrite broker transaction truth.
12. Policy is never weakened merely to manufacture a successful demonstration.

---

## Testing

Current verified engineering state:

```text
163 tests passed
0 regressions
1 known third-party dependency warning
```

The remaining warning comes from the external `websockets.legacy` dependency and does not fail the suite.

The tests cover, among other things:

- proposal integrity,
- risk calculation,
- deterministic market policy,
- evidence validation,
- account eligibility,
- Authorization Receipt issuance,
- signature verification,
- expiration,
- tampering,
- Execution Gateway behavior,
- zero broker interaction under invalid authority,
- exact authorized paper-order construction,
- AI schema boundaries,
- autonomous-cycle short-circuiting,
- visual read-only reporting,
- sanitized execution-proof propagation,
- transaction truth vs presentation failure.

---

## Technology Stack

- Python
- Alpaca Paper Trading
- Alpaca Market Data
- Alpaca Options APIs
- OpenAI Responses API
- Official Cboe VIX history
- HMAC-SHA256 Authorization Receipts
- SHA-256 proposal fingerprints
- pytest

---

## Demo Narrative

The demo is designed around two complementary proofs.

### Proof 1 — Denial

```text
real market evidence
→ deterministic Lockean rejection
→ AI not reached
→ Authority not reached
→ zero broker orders
```

### Proof 2 — Permission

When real market evidence legitimately qualifies:

```text
real market evidence
→ AI recommendation
→ independent Lockean verification
→ signed proposal-bound authorization
→ Gateway verification
→ genuine Alpaca paper order
→ genuine broker order ID
```

The successful branch uses the exact same production authority chain.

There is no demo-only bypass.

---

## What We Want Judges To Remember

**1. The AI cannot execute.**

Execution authority exists outside the model.

**2. Authorization is specific.**

Permission is cryptographically authenticated, short-lived, and bound to the exact proposal fingerprint.

**3. Lockean proves both denial and permission.**

It can stop a real trade before the AI is even reached, and it can permit a real trade only after independent authorization.

---

## Closing Statement

**Intelligence may recommend the action. Authority must still be earned.**

---

## Submission Links

Fill these in before final submission:

- **GitHub Repository:** `<repository-url>`
- **Demo Video:** `<demo-video-url>`
- **Team / Hackathon Page:** `<team-page-url>`
- **Additional Demo Artifact:** `<optional-url>`

---

## Final Status Checklist

Before submission:

- [ ] Repository public and accessible
- [ ] README current
- [ ] Setup instructions smoke-tested
- [ ] Secrets absent from repository
- [ ] Full test suite green
- [ ] Real rejection demo reproduced
- [ ] Browser dashboard screenshot captured
- [ ] Successful paper execution captured if qualifying market evidence occurs
- [ ] Genuine Alpaca order ID captured if submitted
- [ ] Demo video recorded
- [ ] Submission description finalized
- [ ] Team/hackathon links verified
