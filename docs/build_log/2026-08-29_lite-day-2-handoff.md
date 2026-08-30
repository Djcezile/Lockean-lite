# Lockean Lite — Day 2 Handoff

**Competition date:** 2026-08-29 UTC
**Project day:** Day 034 / Lockean Lite Day 2

## Verified Closing State

Commit: `fe8229e`

Tests: `21 passed`

Collected: `21`

Regressions: `0`

Branch: `main`

Working tree: `clean`

## Day 2 Architecture Earned

Lockean Lite now supports one intentionally narrow defined-risk options vertical slice: a bull call debit spread.

The AI may propose trading intent, but Lockean independently determines whether that intent satisfies the supported structure.

Verified deterministic rejection behavior includes:

- unsupported strategy → `unsupported_strategy`
- non-positive contract quantity → `invalid_contract_quantity`
- invalid option-leg count → `invalid_leg_count`
- non-call option leg → `unsupported_option_type`
- invalid buy/sell relationship → `invalid_leg_sides`
- mismatched expiration → `expiration_mismatch`
- invalid strike relationship → `invalid_strike_order`
- missing proposed spread debit → `missing_net_debit`
- non-positive proposed spread debit → `invalid_net_debit`
- derived maximum loss above Lockean policy → `max_loss_exceeds_limit`

## Independent Risk Calculation

For the supported bull call debit spread, Lockean independently derives maximum loss from:

`net debit × 100 × contract quantity`

The AI does not establish the authoritative maximum-loss value.

The maximum permitted loss is owned by `LockeanAuthority`, not by the AI proposal.

Passing the loss ceiling is necessary but is not sufficient for authorization.

## Proposal Identity

Lockean Lite now generates a versioned canonical SHA-256 fingerprint for a `TradeProposal`.

The fingerprint includes execution-relevant proposal information.

Incidental option-leg tuple ordering does not alter identity when the explicitly declared financial action is unchanged.

Changing a meaningful execution field, including contract quantity, changes the fingerprint.

This creates the deterministic foundation required for proposal-bound authorization and later tamper detection.

## Locked Authorization Boundary

`AUTHORIZED` remains intentionally unreachable.

Lockean will not issue an authorization decision until that decision can be tied to the exact proposal it evaluated and the remaining required authorization evidence exists.

An `AUTHORIZED` decision will still not constitute execution permission by itself.

Execution will require a separate proposal-bound Authorization Receipt.

## Intentionally Absent

- reachable `AUTHORIZED` path
- validated evidence contract
- Authorization Receipt
- receipt expiration
- Execution Gateway
- Alpaca order submission
- AI model integration
- autonomous trading loop

These are absent intentionally rather than implicitly trusted.

## Day 3 Frontier

Begin integrating Alpaca competition infrastructure behind the existing Lockean authority boundary without granting execution permission.

Preserve the following invariant:

AI may propose.
Lockean independently validates and proves.
A broker path may eventually exist.
No broker order may execute without explicit proposal-bound authority.

The next authorization work must preserve exact proposal identity and fail closed if required evidence or authorization is absent.