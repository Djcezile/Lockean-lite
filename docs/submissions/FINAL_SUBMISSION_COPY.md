# Lockean Lite — Final Hackathon Submission Copy

## Recommended Project Description

**Lockean Lite is an independent execution authority for autonomous AI trading agents.**

The AI can recommend a trade, but it cannot authorize or execute one.

Lockean independently verifies real market evidence, trusted pricing, defined maximum loss, proposal integrity, account eligibility, and policy compliance. Paper-account evidence is read independently through the official Alpaca CLI and normalized before it reaches Lockean Authority. Only then may Lockean Authority issue a short-lived cryptographically authenticated Authorization Receipt bound to the exact proposal fingerprint.

The Execution Gateway independently verifies that receipt immediately before broker interaction. A missing, forged, expired, or proposal-mismatched receipt fails closed.

For the current SPY defined-risk options vertical slice, Lockean uses real SPY data from Alpaca and official VIX history from Cboe. In a real August 31, 2026 evaluation, trend, momentum, and volatility passed while the breakout requirement failed. Lockean rejected the cycle before the AI was called, no Authority evaluation occurred, and no broker order was submitted.

A later completed September 2 evaluation also rejected honestly: SPY closed at 765.13 and VIX at 15.20; trend and momentum passed, while breakout and volatility failed. No AI recommendation, Authority decision, receipt, or broker order occurred.

We also tested a real OpenAI recommendation against real Alpaca option candidates. The AI selected a spread, but Lockean independently derived a $213 maximum loss against a $150 configured policy ceiling. The AI could recommend the trade; it could not declare itself compliant.

When a real market session legitimately qualifies, the exact production path is:

`real evidence → AI recommendation → Lockean pricing/risk → Alpaca CLI account eligibility → Lockean Authority → signed proposal-bound receipt → Execution Gateway verification → Alpaca paper order → sanitized execution proof`

There is no AI-to-broker shortcut and no demo-only bypass.

**AI proposes. Lockean verifies. Authority decides. Only then may software act.**

---

## Short Version

Lockean Lite separates AI intelligence from execution authority.

The AI may recommend a structured options trade, but it cannot approve market conditions, determine trusted pricing, calculate maximum loss, authorize itself, or submit a broker order.

A deterministic Lockean Authority independently verifies real market evidence, risk, account eligibility, and proposal integrity. If every requirement passes, it issues a short-lived cryptographically authenticated Authorization Receipt bound to the exact proposal fingerprint. The Execution Gateway independently verifies that receipt before Alpaca can receive an order.

Missing evidence, excessive risk, tampering, forged authorization, or expired permission fails closed.

---

## One-Line Pitch

**Give AI the ability to recommend consequential actions without giving it unilateral authority to execute them.**

---

## Suggested Tags

- AI Agents
- Trading
- FinTech
- Safety
- Authorization
- Alpaca
- OpenAI
- Options
- Autonomous Systems

---

## Submission Links

Replace these placeholders before final submission:

- GitHub: https://github.com/Djcezile/Lockean-lite
- Online Demo: https://djcezile.github.io/Lockean-lite/
- Demo Video: `<demo-video-url>`
- Team Page: `<team-page-url>`

---

## Final Accuracy Rule

Do not claim a successful real Alpaca paper execution until the complete production authority chain has run and Alpaca has returned a genuine broker order ID.
