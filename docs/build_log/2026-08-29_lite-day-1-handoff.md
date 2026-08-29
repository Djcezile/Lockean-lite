# Lockean Lite — Day 1 Handoff

**Competition date:** 2026-08-29 UTC
**Project day:** Day 033 / Lockean Lite Day 1

## Verified Closing State

Commit: `dd208e3`

Tests:

`6 passed`

Regressions:

`0`

Branch:

`main`

Working tree:

`clean`

## Day 1 Architecture Earned

The AI-facing boundary is an immutable `TradeProposal`.

The AI may express trading intent, including obviously bad or malicious intent, but possesses no execution authority.

`LockeanAuthority` independently evaluates proposals and currently fails closed.

Verified rejection behavior includes:

- unsupported strategy → `unsupported_strategy`
- non-positive contract quantity → `invalid_contract_quantity`
- otherwise supported but incomplete proposal → `authorization_requirements_incomplete`

`AuthorityDecision` is immutable after creation.

## Locked Authorization Boundary

An `AUTHORIZED` decision is not execution permission.

Execution will eventually require a separate proposal-bound Authorization Receipt proving the exact proposal Lockean approved.

Changing an execution-relevant field such as quantity, option legs, expiration, or another order-relevant field must invalidate that authorization.

## Intentionally Absent

- reachable `AUTHORIZED` path
- Authorization Receipt
- proposal fingerprint
- options-leg model
- maximum-loss calculation
- risk ceiling
- receipt expiration
- Execution Gateway
- Alpaca execution client
- broker order submission
- AI integration

These are absent intentionally rather than implicitly assumed.

## Day 2 Frontier

Build one defined-risk options vertical slice.

Target sequence:

1. explicit option-leg structure
2. explicit expiration
3. deterministic maximum-loss calculation
4. risk-policy comparison
5. proposal fingerprint
6. first legitimately reachable `AUTHORIZED` decision
7. proposal-bound Authorization Receipt
8. changed proposal invalidates authorization
9. expired authorization fails closed

## Locked Principle

AI proposes.
Lockean proves.
Authority decides.
Only then may software act.