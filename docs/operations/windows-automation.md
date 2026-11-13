# Windows Scheduled Paper Operations

This runbook installs the version-controlled Lockean Lite daily paper task and
its separate watchdog. It is intentionally a two-phase deployment: staging
copies files and writes configuration without changing a scheduled task;
activation is refused until the exact Git commit has passed the full test
suite, a read-only broker-planning dry run, a simulated alert, and a real test
delivery to the configured notification destination.

The automation does not modify the trading hypothesis. It invokes the same
paper-only, one-spread, `$150` maximum-loss, `profit_first` launcher described
in the README.

## System boundary

| Component | Role | Can submit an order? |
|---|---|---:|
| `Run-LockeanLite.ps1` | Validate source, plan the date, enforce duplicate/start guards, invoke the approved runner, reconcile completion | Indirectly, through the existing guarded paper pipeline only |
| `session_plan.py` | Read Alpaca PAPER calendar/contracts and derive the next day, evidence date, and expiration | No |
| `session_launcher.py` | Create the canonical repository log, record source provenance, invoke the approved policy | Through the existing paper pipeline |
| `Watch-LockeanLite.ps1` | Start a separate lifecycle monitor and load its protected endpoint | No |
| `session_watchdog.py` | Detect missing starts/logs/heartbeats/completion, planner failures, terminal failures, and source mismatch | No |
| `notification.py` | Send a small sanitized HTTPS webhook or ntfy mobile-push message | No |

The watchdog is process- and task-independent from the session runner, but it
is not host-independent: if the Windows computer is powered off, cannot log in,
or has no network, neither local task can deliver an alert. A cloud-hosted
external heartbeat monitor is deliberately deferred until the paper strategy
has evidence of profitability.

## Durable locations

| Evidence | Location |
|---|---|
| Full trading logs | `<repo>\logs\lockean_lite_DAY<N>_<timestamp>.log` |
| Scheduler/watchdog audits | `%LOCALAPPDATA%\LockeanLite\Automation\logs` |
| Start, completion, alert, verification receipts | `%LOCALAPPDATA%\LockeanLite\Automation\state` |
| Staged PowerShell scripts | `%LOCALAPPDATA%\LockeanLite\Automation\bin` |
| Task/config backups | `%LOCALAPPDATA%\LockeanLite\Automation\backups` |
| Authorization signing key | `%LOCALAPPDATA%\LockeanLite\Secrets\authorization-key.xml` |
| Notification destination | `%LOCALAPPDATA%\LockeanLite\Secrets\notification-endpoint.xml` |

The launcher always creates and writes the `logs` subfolder inside the actual
Lockean Lite repository. Logs remain ignored by Git because they can contain
account telemetry.

## Prerequisites

1. Windows is set to `Eastern Standard Time` (the Windows identifier for New
   York time). Installation and verification fail closed otherwise.
2. The repository is on the reviewed commit with a clean worktree. Git-ignored
   runtime logs, the virtual environment, and local environment files do not
   count as changes.
3. The repository virtual environment exists at `.venv\Scripts\python.exe`.
4. Alpaca paper and OpenAI credentials are stored as Windows *User*
   environment variables.
5. The authorization key and notification endpoint are stored with
   user-scoped Windows DPAPI. For mobile push, install the ntfy app on the
   destination phone before verification.
6. The Windows user remains logged in. The tasks use interactive-user logon so
   that the same user environment and DPAPI scope are available.

## Restore credentials after a reboot or environment reset

Run this in a fresh PowerShell window. Input is hidden and the values are
stored for the current Windows user; do not paste secrets into source files,
Git, screenshots, or chat.

```powershell
function Set-LockeanUserSecret([string]$Name) {
    $secure = Read-Host "Enter $Name" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plain = $null
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        [Environment]::SetEnvironmentVariable($Name, $plain, 'User')
    }
    finally {
        if ($null -ne $plain) { $plain = $null }
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

Set-LockeanUserSecret ALPACA_API_KEY
Set-LockeanUserSecret ALPACA_SECRET_KEY
Set-LockeanUserSecret OPENAI_API_KEY
Remove-Item Function:Set-LockeanUserSecret
```

If the authorization key itself is missing, recreate its protected file:

```powershell
$keyDirectory = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets'
New-Item -ItemType Directory -Path $keyDirectory -Force | Out-Null
$authorizationKey = Read-Host 'Enter LOCKEAN_AUTHORIZATION_SIGNING_KEY' -AsSecureString
$authorizationKey | Export-Clixml -LiteralPath (Join-Path $keyDirectory 'authorization-key.xml') -Force
Remove-Variable authorizationKey
```

Close that PowerShell window and open a new one before verification so the
fresh user-level environment is loaded normally.

## Stage, verify, and activate

From the repository root in the new PowerShell window:

```powershell
git pull --ff-only
$repo = (Get-Location).Path

.\ops\windows\Install-LockeanLiteAutomation.ps1 -RepoRoot $repo
```

That command stages files and configuration only. It prints that scheduled
tasks were not changed.

For mobile push without Slack or Google Workspace, install the
[ntfy app](https://docs.ntfy.sh/subscribe/phone/) on the phone, then run:

```powershell
& "$env:LOCALAPPDATA\LockeanLite\Automation\bin\Set-LockeanLitePush.ps1"
```

The script generates a 128-bit random private topic, saves only its HTTPS
endpoint as a user-DPAPI-protected `SecureString`, displays the topic, and
copies it to the Windows clipboard. In the ntfy app, tap `+` and subscribe to
that exact topic on the default `https://ntfy.sh` server. Do this before the
verification command because verification sends a real labelled test alert.

The topic is a bearer secret. ntfy topics are created on demand and anyone who
knows a topic can subscribe or publish, so never put it in Git, chat, a
screenshot, a public note, or an ordinary log. The 128-bit generated suffix
makes accidental guessing impractical. The notifier also refuses weak or
ambiguous `ntfy.sh` URLs.

To use some other HTTPS webhook instead, retain the generic hidden-input setup:

```powershell
& "$env:LOCALAPPDATA\LockeanLite\Automation\bin\Set-LockeanLiteNotification.ps1"
```

SMS is not configured in this release. Direct SMS would add a paid provider,
phone-number handling, and another credential; ntfy supplies the requested
phone alert without those dependencies.

Verify the exact staged commit:

```powershell
$config = "$env:LOCALAPPDATA\LockeanLite\Automation\automation-config.json"
& "$env:LOCALAPPDATA\LockeanLite\Automation\bin\Verify-LockeanLiteAutomation.ps1" `
  -ConfigPath $config
```

Verification performs four gates:

1. the complete Python regression suite;
2. an exact-commit, read-only `Run-LockeanLite.ps1 -DryRun` (it may query the
   Alpaca PAPER calendar/contracts but cannot invoke the session runner);
3. a locally rendered simulated `task_not_started` notification; and
4. a real, explicitly labelled `watchdog_test` delivery to the configured
   endpoint.

Only after all four pass does it write
`state\verification_<40-character-commit>.json`. Activate with the same commit:

```powershell
.\ops\windows\Install-LockeanLiteAutomation.ps1 `
  -RepoRoot $repo `
  -Activate -OperatorCredentialEntry
```

Activation backs up any existing task XML, registers
`LockeanLite-DailyPaper` at 09:15 ET and `LockeanLite-Watchdog` at 09:20 ET,
then checks the registered calendar triggers. Both use weekday local
wall-clock boundaries without a UTC offset, so Task Scheduler follows the
host's Eastern daylight-saving changes. If registration or the boundary
check fails, the installer restores the prior task definitions (or removes
only a newly created task).
The receipt also binds the repository path and SHA-256 of the staged
configuration, so a receipt cannot authorize a silently changed target.

## Protected operator credential entry

Activation requires Windows PowerShell 5.1 in an elevated local operator
console and the explicit `-OperatorCredentialEntry` switch. Run it only
after independent review and separate deployment approval. Use an idle
maintenance window. The installer chooses the next future weekday boundary
for each corrected time, skipping elapsed starts and weekends. This permits
afternoon maintenance without introducing a missed-start catch-up.

An effectively enabled task (both task and trigger enabled) must have its
planned first run more than 30 minutes away. This guard runs before
credential entry and again immediately before each write. Windows service
next-run state separately blocks an imminent or overdue enabled execution.
Running, queued, and unknown task states always block installation,
including when a task is otherwise disabled.

Existing tasks keep their principal, logon type, actions, settings, and
security descriptor. Daily uses Password logon and watchdog uses
Interactive logon. A different existing logon policy fails preflight.
Only each calendar trigger's start boundary changes. Fresh definitions
use the same approved logon policy and the existing automation protections.
Existing task and trigger enabled states are captured and compared after
registration. Disabled tasks stay disabled, and registration explicitly
uses the Windows disable flag for those definitions. Disabled, idle tasks
can be corrected during afternoon maintenance. Enablement remains a
separately approved operational step that must reassess future run risk.

The adapter requires an administrative token and checks the effective
token against the root folder and task security descriptors. Task snapshots
include owner, group, DACL, and audit SACL. Reading auditing metadata requires
the corresponding Windows security privilege; the installer fails closed
if the operator context cannot read it and does not enable privileges or
change system policy. An existing SACL also requires audit-security access
for restoration. It backs up
both original XML definitions and security descriptors before entering
credentials or mutating tasks. It refuses running tasks and tasks with
an imminent existing run. All changes require the genuine verification
receipt for the exact source and configuration.

The operator enters the Windows password directly into the Windows
secure-desktop credential dialog. Password input is never a PowerShell
parameter, environment variable, command-line argument, repository file,
or diagnostic payload. Do not enter it into chat, recorded terminal input,
or a screen-sharing session. Cancellation, a different account, an empty
password, or failed batch authentication blocks installation. Windows
Hello or certificate credentials that cannot supply the required
Password-logon secret also fail closed.

`LockeanLiteSchedulerNative.cs` is compiled from the pinned, clean source.
It keeps the password in a private SecureString for the transaction.
It checks the entered account SID and authenticates a batch logon before
validating both the recovery XML and replacement XML with Task Scheduler's
validation-only mode. Validation-only mode checks the definition; the
batch logon supplies the authentication check. These prerequisites reduce
recovery risk but cannot guarantee recovery during a service outage,
permission change, credential revocation, or concurrent operator action.

Windows APIs require transient plaintext. The adapter clears the
credential-provider blob, unmanaged password buffers, and the pinned
temporary managed string used for COM marshaling. It disposes cached
SecureStrings after success or failure. Runtime, COM, OS, provider, and
crash-dump copies remain a security limitation; buffer clearing is not
proof that every copy was erased. Use a trusted local host.

Registration and restoration use the same authenticated credential cache.
Updates preserve the original security descriptor and suppress
registration-trigger execution. Failed or partial writes are recovered in
reverse order, including the failing write. Both restoration and removal
are read back. Recovery continues if one rollback fails. The original
sanitized activation error is rethrown with separate RollbackFailures
metadata and a BLOCKED warning. Provider exception messages and inner
exceptions are excluded; HRESULT and any Win32 error metadata are retained.
A rollback failure requires operator intervention using the original
backups. Do not blindly retry or clear historical run receipts.

Engineering tests use synthetic credentials and a fake registration
target. They compile the native adapter and check synthetic Windows access
descriptors without entering real credentials. Tests should run with
inherited credential variables removed and pytest 9.2.0 or later to avoid
the known Windows oversized-test-name diagnostic failure. Secure-desktop
entry, actual account authentication, persisted registration, and recovery
still require separately authorized Windows acceptance.

[Windows credential UI](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw),
[task registration](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertask),
and [task access rights](https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks)
define the native contracts.

## Verify the activated tasks

```powershell
Get-ScheduledTask -TaskName 'LockeanLite-DailyPaper','LockeanLite-Watchdog' |
  Select-Object TaskName, State

Get-ScheduledTaskInfo -TaskName 'LockeanLite-DailyPaper' |
  Select-Object LastRunTime, LastTaskResult, NextRunTime

Get-ScheduledTaskInfo -TaskName 'LockeanLite-Watchdog' |
  Select-Object LastRunTime, LastTaskResult, NextRunTime
```

Confirm that the host uses Eastern time with automatic daylight-saving
adjustment enabled. In each `Export-ScheduledTask` result, check the
`CalendarTrigger` weekday schedule and its `StartBoundary`. The daily
boundary must end in `T09:15:00` and the watchdog boundary in `T09:20:00`,
with no UTC designator or numeric offset. Compare the next-run times above
in the host's local time.

The tasks use `WakeToRun`, `StartWhenAvailable`, a nine-hour execution limit,
and `IgnoreNew` overlap behavior. `StartWhenAvailable` does not weaken the
09:00–10:00 start guard. A computer that becomes available after 10:00 ET is
recorded as blocked; it does not launch a late trading cycle.

## Daily behavior

The 09:15 task:

1. requires the configured 40-character commit to equal repository `HEAD` and
   requires a clean worktree;
2. imports credentials from current-user storage and the signing key from
   DPAPI;
3. uses Alpaca PAPER read-only calls with bounded retry to verify that today is
   a market day, preserve any early close, choose the previous completed market
   date, and verify the strictly future Friday SPY expiration;
4. derives the next day only from logs containing both the market-close marker
   and exit-code-zero terminal marker;
5. enforces the time, mutex, existing-process, and one-attempt-per-market-date
   guards;
6. launches the existing approved paper session while preventing sleep;
7. requires the canonical log under `<repo>\logs` to contain both success
   markers; and
8. writes a completion receipt only after scheduler and runner evidence agree.

There is no automatic Git pull and no automatic retry of a broker-capable
session. Read-only planning is the only operation with bounded retries.

## Watchdog events

Notifications contain an event code, market date, and fixed explanation—never
credentials, webhook URLs, broker responses, balances, positions, or raw
exceptions.

| Event | Meaning |
|---|---|
| `task_not_started` | No start receipt by five minutes before market open |
| `planner_failure` | Read-only session planning exhausted or failed deterministically |
| `startup_blocked` | A runner startup guard blocked the task |
| `source_revision_mismatch` | Available source differs from the approved clean commit |
| `session_log_missing` | A start receipt exists but no canonical repository log appeared |
| `heartbeat_missing` / `heartbeat_stale` | A live session has no advancing heartbeat |
| `unexpected_terminal` | Session ended blocked, failed, interrupted, or aborted |
| `runner_nonzero` | Scheduler observed a nonzero runner exit code |
| `completion_record_missing` | Canonical log completed but scheduler receipt is absent |
| `session_incomplete_after_close` | Successful reconciled completion is absent after broker close plus grace |
| `watchdog_calendar_unavailable` | Independent PAPER-calendar reads failed |

Delivered events are keyed by market date and event code in
`alert-ledger.json`. A failed delivery is not marked delivered, so the next
watchdog pass retries it. Alpaca calendar hours determine holidays and early
closes; the monitor does not assume every weekday closes at 16:00.

## Failure and restart semantics

| Condition | Result |
|---|---|
| Network is not ready after wake | PAPER planning retries up to seven times over about three minutes, then blocks and alerts |
| Planner returns an unverified expiration or missing completed log | Deterministic failure; no retry and no session |
| Session already runs | Mutex/process guard blocks the duplicate |
| Start receipt already exists | No second broker-capable attempt that market date |
| Host restarts during a session | The abrupt log lacks completion; the one-attempt receipt prevents blind resubmission |
| Host sleeps | Runner requests continuous system availability; task is also configured to wake the computer where hardware permits |
| Source/worktree changes after verification | Daily runner blocks before planning or trading |
| Notification delivery fails | Local watchdog audit records failure; ledger leaves the event retryable |
| Market holiday/weekend | Alpaca calendar returns closed and both operations skip |

## Rollback

First disable both new tasks so no additional launch can occur:

```powershell
Disable-ScheduledTask -TaskName 'LockeanLite-DailyPaper'
Disable-ScheduledTask -TaskName 'LockeanLite-Watchdog'
```

The installer leaves timestamped prior task XML and configuration under
`%LOCALAPPDATA%\LockeanLite\Automation\backups`. Inspect the exact backup, then
restore it explicitly:

```powershell
$backup = 'C:\exact\reviewed\backup.xml'
Register-ScheduledTask -TaskName 'LockeanLite-DailyPaper' `
  -Xml (Get-Content -LiteralPath $backup -Raw) `
  -Force
```

Do not delete start/completion receipts or session logs to force a rerun. A
failed market-date attempt needs explicit diagnosis, not a blind second order
opportunity.

## Known limitations

- The installer has synthetic Windows test and unregistered serialization
  evidence. Real credential entry, Password authentication, persisted
  registration, and rollback acceptance remain pending.
- Both tasks depend on the same computer, current-user login, network, Alpaca,
  and Task Scheduler. The watchdog is not an external uptime service.
- Operating costs and all-in net P&L remain unmeasured.
- Scheduling reliability is supported by one verified unattended full session,
  not a statistically meaningful reliability history.
- No claim of strategy profitability follows from a flat, no-trade day.
