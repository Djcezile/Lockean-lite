param(
    [guid]$AcceptanceId = [guid]::NewGuid(),
    [switch]$ExecuteDisposableDrill,
    [switch]$ApproveCredentialEntry,
    [string]$ApprovalReference,
    [string]$RecoveryDirectory,
    [ValidateSet('None','PartialWrite','RollbackFailure')][string]$Fault = 'None'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# These switches record separate operator authorization; they do not grant it.
# Default invocation compiles only, connects to no service, and opens no credential UI.
try {
    if ($ExecuteDisposableDrill -and (-not $ApproveCredentialEntry -or
        [string]::IsNullOrWhiteSpace($ApprovalReference) -or
        [string]::IsNullOrWhiteSpace($RecoveryDirectory))) { throw 'separate_execution_and_credential_approval_and_recovery_path_required' }
    Add-Type -Path @(
        (Join-Path $PSScriptRoot 'LockeanLiteSchedulerNative.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteAcceptance.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteScheduleReader.cs')
    ) -ReferencedAssemblies System,System.Core,System.Xml,Microsoft.CSharp
    $policy = [LockeanAcceptance.TaskPolicy]::new($AcceptanceId)
    if (-not $ExecuteDisposableDrill) {
        [pscustomobject]@{Status='PREPARED'; Daily=$policy.Daily; Watchdog=$policy.Watchdog; NativeOperations=$false} | ConvertTo-Json -Compress
        return
    }
    $session = [LockeanAcceptance.GuardedSession]::CreateNative($policy,$true,$true)
    try {
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        # Narrow fixture ACL: owner/group administrator; only SYSTEM, admins and operator.
        $sddl = 'O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;' + $sid + ')'
        $script:recoveryPins = $null
        $capture = [Action]{ $script:recoveryPins = [LockeanAcceptance.RecoverySet]::Save($session,$RecoveryDirectory) }
        $result = [LockeanAcceptance.Drill]::Run($session,$sid,$sddl,[LockeanAcceptance.DrillFault]::$Fault,$capture)
        [pscustomobject]@{Result=$result; Daily=$policy.Daily; Watchdog=$policy.Watchdog; RecoveryPins=$script:recoveryPins} | ConvertTo-Json -Depth 5 -Compress
        if ($result.Status -ne 'PASS') { exit 1 }
    } finally { $session.Dispose() }
} catch {
    # No provider messages, PS error records, account IDs or credential-bearing objects.
    [pscustomobject]@{Status='BLOCKED'; HResult=$_.Exception.GetBaseException().HResult} | ConvertTo-Json -Compress
    exit 1
}
