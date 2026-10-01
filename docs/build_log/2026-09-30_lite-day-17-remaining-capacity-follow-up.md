# Lockean Lite — Day 17 Remaining-Capacity Follow-up

**Decision date:** September 30, 2026

**Mode:** Alpaca paper only

## Approved Policy

The Founder selected the remaining stop-loss capacity gate exposed by Day 17.
The session stop threshold now limits both future entries and the number of
committed spread units still capable of reaching a stop.

With `--maximum-session-stop-loss-fills 2`:

| Confirmed session stop fills | Maximum committed spread units |
|---:|---:|
| 0 | 2 |
| 1 | 1 |
| 2 or more | 0; all new entries halted |

This is a non-liquidating control. A healthy open position is not forcibly
closed because another spread stopped. Instead, Lockean refuses to authorize
additional exposure when the already-committed units consume the remaining
session stop-loss capacity.

## Authority Placement

Broker-confirmed stop fills remain the source of truth. The reconstructed
loss-loop state now carries an explicit `remaining_stop_loss_capacity` value.

The capacity is enforced twice:

1. The autonomous session applies it before starting an AI proposal cycle.
2. The production runtime applies it again against a fresh portfolio snapshot
   and refreshed broker loss state immediately before deterministic proposal
   evaluation and Lockean Authority.

The second check preserves the pre-authority timing boundary: a proposal cannot
reach authorization merely because its earlier session-loop state had more
capacity.

Pending entry units and unknown-purpose pending units count as committed risk.
Pending exit units do not add new exposure.

## Exact Rejection

When committed exposure has consumed the remaining allowance, the entry path
fails closed with:

```text
session_stop_loss_capacity_reached
```

The session continues broker reconciliation and managed-position exit checks.

## Test Proof

- Zero stops preserve the two-spread configured capacity.
- One confirmed stop leaves exactly one committed unit of capacity.
- One managed spread after one stop blocks another AI proposal cycle.
- A pending entry consumes the remaining capacity.
- The pre-authority runtime rechecks capacity against refreshed broker state.
- Two confirmed stops retain the existing hard session halt.
- Directional cooldown, take-profit exclusion, duplicate-fill deduplication,
  restart reconstruction, and fail-closed behavior remain intact.

**Regression result:** 345 passed, 1 known third-party deprecation warning,
0 regressions.

## Day 18 Mission — October 1, 2026

> **Superseded before execution:** the Founder issued the permanent
> profitability-first product directive on October 1. Day 18 now runs the
> profit-first contract documented in
> `docs/decisions/2026-10-01_profitability-first-product-doctrine.md` and
> `docs/build_log/2026-10-01_lite-day-18-profit-first-pivot.md`. The
> remaining-capacity control remains active beneath the tighter one-spread,
> one-stop policy.

Day 18 is a controlled active-paper validation of the new exposure-aware rule,
not a strategy-tuning session.

The primary live acceptance case is:

1. A first confirmed stop reduces remaining capacity from two to one.
2. If one spread is already committed, a further proposal is rejected with
   `session_stop_loss_capacity_reached` even after the directional cooldown
   expires.
3. If no spread is committed, one otherwise eligible proposal may proceed.
4. A second confirmed stop activates the hard halt.
5. Reconciliation, exits, and end-of-day cleanup remain active throughout.

Run from the repository after updating `main` and activating `.venv`:

```powershell
python -m lockean_lite.session_launcher `
  --day-number 18 `
  --completed-through 2026-09-30 `
  --expiration 2026-10-02
```

The launcher writes the complete record to:

```text
C:\Users\djcez\Desktop\Lockean Lite\lockean-lite\logs\
```

Live-capital authority remains disabled. No Lockean Lite code is bulk-transferred
into Project Lockean Core.
