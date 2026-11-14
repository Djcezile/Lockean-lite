param(
    [Parameter(Mandatory=$true)][guid]$AcceptanceId,
    [Parameter(Mandatory=$true)][string]$RecoveryDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$DailyXmlSHA256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$DailySecuritySHA256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$WatchdogXmlSHA256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$WatchdogSecuritySHA256,
    [switch]$ExecuteRecovery,
    [switch]$ApproveCredentialEntry,
    [string]$ApprovalReference
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    Add-Type -Path @(
        (Join-Path $PSScriptRoot 'LockeanLiteSchedulerNative.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteAcceptance.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteScheduleReader.cs')
    ) -ReferencedAssemblies System,System.Core,System.Xml,Microsoft.CSharp
    $policy = [LockeanAcceptance.TaskPolicy]::new($AcceptanceId)
    $pins = [Collections.Generic.Dictionary[string,string]]::new()
    $pins[$policy.Daily+'.xml']=$DailyXmlSHA256
    $pins[$policy.Daily+'.sddl']=$DailySecuritySHA256
    $pins[$policy.Watchdog+'.xml']=$WatchdogXmlSHA256
    $pins[$policy.Watchdog+'.sddl']=$WatchdogSecuritySHA256
    # Pins must come from independently preserved operator evidence, not the backup itself.
    $recovery = [LockeanAcceptance.RecoverySet]::Load($policy,$RecoveryDirectory,$pins)
    if (-not $ExecuteRecovery) { [pscustomobject]@{Status='VALIDATED_OFFLINE'; NativeOperations=$false} | ConvertTo-Json -Compress; return }
    if (-not $ApproveCredentialEntry -or [string]::IsNullOrWhiteSpace($ApprovalReference)) {
        throw 'separate_recovery_and_credential_approval_required'
    }
    $session = [LockeanAcceptance.GuardedSession]::CreateNative($policy,$true,$true)
    try {
        $failures=$recovery.Restore($session)
        [pscustomobject]@{Status=$(if($failures.Count){'BLOCKED'}else{'PASS'}); Failures=$failures} | ConvertTo-Json -Depth 4 -Compress
        if ($failures.Count) { exit 1 }
    } finally { $session.Dispose() }
} catch {
    [pscustomobject]@{Status='BLOCKED'; HResult=$_.Exception.GetBaseException().HResult} | ConvertTo-Json -Compress
    exit 1
}
