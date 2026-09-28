# Lockean Lite — Day 15 Loss-Loop Follow-up

**Date:** September 28, 2026

**Mode:** Alpaca paper only

**Trigger:** Day 14 produced repeated same-direction entries after realized
stop losses. Day 15 safely closed the two inherited positions and proved that
five exit submissions can represent only two actual exits because stale orders
may be cancelled and resubmitted.

## Approved Policy

- Count broker-confirmed stop-loss spread-unit fills, not order submissions.
- After the first confirmed stop-loss fill, block proposals in that direction
  for 3,600 seconds.
- After the second confirmed stop-loss fill in the same market session, disable
  all new entries for the remainder of that session.
- Cancel any working entry order when a new cooldown or halt is observed, then
  wait for a fresh broker snapshot.
- Continue broker reconciliation and position-exit checks while entries are
  blocked.
- If stop-loss history cannot be reconstructed, fail closed for new entries.

## Architecture

Managed exit orders now carry a non-secret Lockean client-order tag identifying
stop-loss versus take-profit and call versus put direction. The session reads
the current New York market day's closed Alpaca orders on every risk cycle and
reconstructs the policy state. A process restart therefore does not erase a
cooldown or session halt. The proposal gate reads that broker history again
immediately before deterministic proposal evaluation so a stop that fills
after the session-loop check cannot pass on stale policy state.

The directional restriction is enforced deterministically against the
structured proposal before Lockean Authority evaluates it. It is not a prompt
instruction and cannot be bypassed by the AI recommendation.

## Proven Behavior

- Cancelled, expired, unfilled, and duplicate order rows do not add losses.
- A filled multi-unit stop counts each closed spread unit.
- Take-profit fills do not add losses.
- Prior-session stop fills reset at the next New York market day.
- The first call-spread stop blocks bullish proposals while allowing bearish
  proposals to continue through every other normal gate; the inverse applies
  to put spreads.
- The second stop prevents any new AI entry cycle.
- Loss-history failures prevent entries but do not suspend position-exit checks.
- Active pending entries are cancelled before stale-snapshot position actions.

**Regression result:** 338 passed, 1 known third-party deprecation warning,
0 regressions.

## Day 16 Command — September 29, 2026

Run from the Lockean Lite repository after activating `.venv`:

```powershell
$log = ".\lockean_lite_DAY16_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

python -m lockean_lite.autonomous_session `
  --completed-through 2026-09-28 `
  --expiration 2026-10-02 `
  --interval-seconds 300 `
  --risk-check-interval-seconds 30 `
  --entry-cooldown-seconds 600 `
  --maximum-open-spreads 2 `
  --maximum-same-structure-units 1 `
  --maximum-allowed-loss 150 `
  --maximum-daily-loss 300 `
  --take-profit-percent 20 `
  --stop-loss-percent 20 `
  --take-profit-price-concession 0.02 `
  --exit-order-timeout-seconds 240 `
  --entry-order-timeout-seconds 240 `
  --eod-entry-cutoff-minutes 5 `
  --loss-loop-direction-cooldown-seconds 3600 `
  --maximum-session-stop-loss-fills 2 `
  --activity-mode active_paper 2>&1 | Tee-Object -FilePath $log
```

Do not add `--risk-management-only`; Day 16 is the controlled active-paper
validation of the new entry containment. Live-capital authority remains
disabled.

## Day 16 Acceptance Criteria

- A first confirmed stop fill starts the correct 60-minute directional block.
- A same-direction proposal during that window is rejected before authority.
- An opposite-direction proposal may proceed only if every existing gate passes.
- A second confirmed stop fill disables all further entries for the session.
- Exit management, reconciliation, the end-of-day cutoff, and clean market-close
  termination remain active.
- No pending or unknown order is left unreconciled.
