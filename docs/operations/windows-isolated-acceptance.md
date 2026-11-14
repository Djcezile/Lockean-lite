# M11.2 isolated Windows acceptance tools

These tools prepare a separately approved Windows operator acceptance. Engineering
qualification uses synthetic backends and unregistered definitions. It does not
authorize task creation, credential entry, authentication, cleanup, production
installation or enablement. Independent security review must bind to the exact
tooling commit before operator use. The existing production installer and native
credential adapter are unchanged.

Use a fresh Windows PowerShell **5.1** process. The tools compile the reviewed C#
sources together; PowerShell 7 framework-reference behavior is not qualified.
Capture JSON output, native exit codes and source hashes without transcripts,
debug traces, screenshots of credential UI, or dumps of exception/provider objects.

## Disposable-task boundary

`Test-LockeanLiteIsolatedAcceptance.ps1` defaults to compile-only preparation:

```powershell
& .\ops\windows\Test-LockeanLiteIsolatedAcceptance.ps1
```

It generates two identities of the form
`LockeanLite-Acceptance-<canonical-lowercase-GUID>-Daily` and `-Watchdog`.
The exact pair is immutable for a session. A different GUID, path alias, suffix,
case variation or either production name is rejected. Checks occur both in every
named session operation and in the private native backend before forwarding to
the existing adapter. That backend is never returned to PowerShell. Normalization,
authentication, validation, readback, restoration and removal obey the same name
boundary. This protects the tool's supported API; it is not a sandbox against an
administrator deliberately bypassing it with reflection, modified source or
unrelated Task Scheduler clients.

Fixtures contain one weekday calendar trigger, task Enabled=false, no missed-run
catch-up, IgnoreNew, no demand start, least privilege and one exact action:
the Windows system directory's `cmd.exe` with `/d /c exit 0`. Alternate executables,
arguments, working-directory elements, extra actions, registration triggers,
unexpected logon types and enabled fixtures are rejected. The `/d` switch prevents
the command processor's AutoRun hooks. No fixture invokes Lockean code. The daily
fixture uses Password and the watchdog InteractiveToken for the operator's SID.
Initial fixture boundaries are in January 2027; refresh this reviewed contract if
acceptance is delayed beyond its applicable schedule period.

## Future operator drill — separate approval required

Do not run this step under engineering-only authorization. The operator must
first bind approval to the source SHA, GUID, account, local recovery directory,
maintenance window, injected fault and later cleanup. Approval switches record
that decision; possession of a switch is not evidence of authorization.

The future command interface is:

```powershell
& .\ops\windows\Test-LockeanLiteIsolatedAcceptance.ps1 `
    -AcceptanceId $approvedGuid -ExecuteDisposableDrill -ApproveCredentialEntry `
    -ApprovalReference $approvalReference -RecoveryDirectory $newPrivateLocalDirectory `
    -Fault RollbackFailure
```

Only a new canonical local directory is accepted for recovery capture. The tool
creates it with a protected ACL for the operator, SYSTEM and Administrators;
existing artifacts are never replaced. UNC/device paths and reparse ancestors
are denied. Preserve its independently captured four SHA-256 pins outside the
backup directory in protected operator evidence. These hashes are consistency
anchors; they do not establish who approved a restore.

The native session checks administrative/root permissions, authenticates the
daily SID through the existing secure-desktop Windows dialog and batch logon,
and validates both original definitions before any fixture write. No PowerShell
password variable or password parameter exists. The reviewed native adapter uses
a private SecureString and brief native/managed plaintext representations required
for Windows marshaling, clears its owned buffers and disposes its cache. Runtime
or COM-owned copies and privileged process inspection cannot be ruled out. Do not
use real credentials during engineering tests.

The drill refuses existing GUID tasks, creates only disabled harmless fixtures,
verifies them, captures their XML/full security descriptors, then advances their
boundaries without changing their other metadata. Native readback separately
checks actual disabled state and zero active instances. XML normalization uses an
unregistered definition; actual principal/action/settings and full descriptor
equality are checked after writes.

`None` restores the initial pair after successful candidate verification.
`PartialWrite` throws a labelled synthetic exception after the second successful
candidate write and verifies reverse restoration. `RollbackFailure` also injects
a pre-write restoration failure for the watchdog while continuing daily recovery.
The original activation HRESULT stays primary; restoration errors are separate.
An injected failure intentionally reports BLOCKED and exits 1. The watchdog may
retain its disabled candidate definition; identify it and recover before cleanup.
This exercises a chosen failure path, not every Windows provider failure.

Stop on permission/authentication failure, cancellation, existing names, descriptor
or principal drift, unexpected enabled/running state, secret-bearing diagnostics,
missing recovery evidence or any production-name access. Never retry credentials
blindly. Recovery rights and an authorized containment operator must exist before
starting; these tools do not grant permission to disable an unexpectedly enabled
task. Initial partial creation attempts are cleaned up only through the same
allowlisted, harmless-definition/disabled-idle checks. Unrecoverable cleanup stays
BLOCKED and names the affected disposable task.

Recovery-capture or normalized-snapshot read-back failure after fixture creation
also returns BLOCKED. The primary ActivationError field contains the sanitized
capture HRESULT with a `capture_` label. The tool attempts guarded removal of both
known fixtures in reverse order and checks that each removal persisted.
RollbackFailures entries labelled `cleanup_` identify unresolved or uncertain
fixture identities independently of the capture error. Retain the configured
RecoveryDirectory and all partially written files, including an empty directory;
record its path alongside the result. Do not treat partial files as a usable
recovery set, delete them automatically, or retry into the same evidence directory.

## Disposable recovery and cleanup

`Restore-LockeanLiteAcceptanceFixtures.ps1` validates all four exact files before
connecting or authenticating. Supply the original GUID, canonical recovery path,
and independently preserved daily/watchdog XML/security digests. With no execution
switch it performs file-only validation and outputs `VALIDATED_OFFLINE`:

```powershell
& .\ops\windows\Restore-LockeanLiteAcceptanceFixtures.ps1 `
    -AcceptanceId $approvedGuid -RecoveryDirectory $privateRecoveryDirectory `
    -DailyXmlSHA256 $dailyXmlPin -DailySecuritySHA256 $dailySecurityPin `
    -WatchdogXmlSHA256 $watchdogXmlPin -WatchdogSecuritySHA256 $watchdogSecurityPin
```

Actual recovery additionally requires `-ExecuteRecovery -ApproveCredentialEntry
-ApprovalReference $approvalReference`. It checks permissions, authenticates the
Password principal, validates both originals, attempts both reverse restorations
independently and checks XML/full descriptor and native disabled-idle state.
Any failure exits 1 and stays BLOCKED. Missing tasks are not silently recreated.
Hashes are verified and contents consumed through a single read handle. Existing
root/path ACLs and custody must be rechecked by the operator; administrator-level
filesystem interference is outside this protection.

Leave fixtures disabled for inspection. Separately approved cleanup can use a new
`GuardedSession.CreateNative(policy, true, false)` after compilation and permission
checks, then ReadXml/Remove for the exact two GUID identities in reverse order.
Remove validates the harmless fixture and actual disabled-idle state first. Do
not use wildcard task enumeration/deletion or raw production installer activation.
A different ConfigPath does not isolate the production installer, which retains
its real task names.

This helper **cannot restore production tasks**. The earlier manual production
recovery skeleton lacks enforced backup pins/path custody and is not qualified by
these disposable tests. Production recovery still needs independently reviewed
operator steps using fresh disabled originals, full descriptors, independently
pinned paths/digests and protected authentication. Do not promote a disposable
fixture backup into a production rollback set.

## Read-only native DST client

```powershell
& .\ops\windows\Test-LockeanLiteScheduleDST.ps1 `
    -PermittedTask 'LockeanLite-DailyPaper','LockeanLite-Watchdog' -Year 2027
```

Only explicitly supplied exact production/GUID task identities can be queried.
The C# read-only IRegisteredTask projection follows the SDK GUID/vtable order,
uses a 16-byte SYSTEMTIME and DWORD count, checks HRESULT/truncation, and frees the
returned array with CoTaskMemFree. Mutation slots remain unused ABI placeholders;
no operation to run/enable/modify a task or time setting is exposed by this client.
Service connection/folder acquisition are local and read-only.

It admits only one enabled weekly Monday–Friday calendar trigger, interval one,
and offset-free 09:15/09:20 boundaries. Task-level disabled state is retained.
It requires the Eastern Windows timezone, a future year and installed timezone
rules matching the expected US transitions. It queries the Friday and Monday
around both transitions, checks the returned local clock/date, and records local
and corresponding UTC times. Host clock/timezone settings are never changed.
Prediction evidence does not establish that a task is enabled or has executed.

Exit 0 means matching queried predictions; exit 1 means a confirmed schedule
failure or a blocked invocation; exit 2 means unavailable/incomplete predictions.
JSON distinguishes FAIL, BLOCKED and INCONCLUSIVE. A zero prediction count, access
failure or S_FALSE is not a pass. Actual HRESULTs/counts are preserved. The separate
Inspect method reads native enabled/state/next-run metadata; RequireDisabled also
checks active instances. It exposes no task arguments, account details or XML.

Read-only validation of existing definitions and unregistered XML serialization
cannot prove persisted corrected definitions, Password authentication or real
rollback. Those gates remain pending until separately approved native acceptance.

Windows interface references: [IRegisteredTask::GetRunTimes](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-iregisteredtask-getruntimes),
[ITrigger start-boundary semantics](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-itrigger-get_startboundary),
[SDK ABI declarations](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/taskschd.h).
