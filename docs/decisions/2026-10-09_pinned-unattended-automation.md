# Decision: Pin and Independently Reconcile Unattended Sessions

**Date:** 2026-10-09

**Status:** Accepted for paper deployment

**Scope:** Windows-local Alpaca paper automation

## Context

Day 23 completed the first verified full session launched by Windows Task
Scheduler. Its trading log, however, did not identify the source commit and did
not contain numeric signal-basis telemetry that had already been merged to
`main` on October 6. The evidence proves a full session ran; it cannot prove
which revision supplied the running Python modules. The exact reason—stale
checkout, stale editable installation, or another local deployment mismatch—is
not recoverable from the log.

The same computer also hosted the task, runner, audit, and evidence. A zero
Task Scheduler result alone was therefore insufficient to establish canonical
session completion.

## Decision

1. Unattended execution is pinned to one reviewed 40-character Git commit.
2. A worktree change or commit mismatch blocks before broker planning
   or execution.
3. Every canonical session log records commit and worktree provenance.
4. Scheduler success requires both canonical market-close and exit-code-zero
   markers plus a separate completion receipt.
5. A second Scheduled Task monitors starts, heartbeats, terminal state, runner
   exit, and completion independently from the session process.
6. Alert delivery is idempotent and uses a user-DPAPI-protected HTTPS endpoint.
7. Task replacement is gated by an exact-commit verification receipt and prior
   task definitions are backed up for rollback.
8. Neither automation component may update Git or retry a broker-capable
   session automatically.

## Consequences

The next log can establish exactly what revision ran and the watchdog can
detect several silent local failures. Deployment is more deliberate because
staging, verification, endpoint testing, and activation are separate steps.

This does not create host independence. A powered-off or logged-out computer
cannot run either local task or send an alert. It also does not improve or
validate the trading hypothesis; profitability remains a separate evidence
problem.
