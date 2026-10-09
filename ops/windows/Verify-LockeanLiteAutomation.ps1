[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'automation-config.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'windows_timezone_must_be_eastern_standard_time'
}
$automationRoot = Split-Path -Parent $ConfigPath
$stateDir = Join-Path $automationRoot 'state'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw 'configuration_missing' }
$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$repo = [string]$config.repo_root
$python = [string]$config.python_path
$approvedCommit = ([string]$config.approved_commit).ToLowerInvariant()
$configHash = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash.ToLowerInvariant()
$dailyScript = Join-Path $PSScriptRoot 'Run-LockeanLite.ps1'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }
$head = (& git -C $repo rev-parse HEAD).Trim().ToLowerInvariant()
$worktreeChanges = @(& git -C $repo status --porcelain)
if ($LASTEXITCODE -ne 0 -or $head -ne $approvedCommit -or $worktreeChanges.Count -gt 0) {
    throw 'source_revision_unapproved'
}

Set-Location -LiteralPath $repo
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'regression_tests_failed' }

$powerShellPath = (Get-Process -Id $PID).Path
& $powerShellPath -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $dailyScript -DryRun -ConfigPath $ConfigPath
if ($LASTEXITCODE -ne 0) { throw 'scheduled_wrapper_dry_run_failed' }

& $python -m lockean_lite.automation.session_watchdog `
    --repo-root $repo `
    --automation-root $automationRoot `
    --simulate-event task_not_started
if ($LASTEXITCODE -ne 0) { throw 'notification_simulation_failed' }

$notificationPath = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets\notification-endpoint.xml'
if (-not (Test-Path -LiteralPath $notificationPath -PathType Leaf)) {
    throw 'notification_destination_unavailable'
}
$secureEndpoint = Import-Clixml -LiteralPath $notificationPath
if (-not ($secureEndpoint -is [System.Security.SecureString]) -or $secureEndpoint.Length -eq 0) {
    throw 'notification_destination_unavailable'
}
$endpointCredential = [System.Net.NetworkCredential]::new('Lockean', $secureEndpoint)
$env:LOCKEAN_NOTIFICATION_WEBHOOK = $endpointCredential.Password
Remove-Variable endpointCredential, secureEndpoint
try {
    & $python -m lockean_lite.automation.notification --test --market-date (Get-Date -Format yyyy-MM-dd)
    if ($LASTEXITCODE -ne 0) { throw 'live_notification_test_failed' }
} finally {
    Remove-Item Env:LOCKEAN_NOTIFICATION_WEBHOOK -ErrorAction SilentlyContinue
}

$receipt = @{
    approved_commit = $approvedCommit
    repo_root = $repo
    config_sha256 = $configHash
    verified_at = (Get-Date -Format o)
    tests_passed = $true
    dry_run_passed = $true
    notification_simulation_passed = $true
    live_notification_verified = $true
} | ConvertTo-Json
$receiptPath = Join-Path $stateDir ('verification_' + $approvedCommit + '.json')
$temporaryPath = $receiptPath + '.tmp'
[System.IO.File]::WriteAllText(
    $temporaryPath,
    $receipt,
    [System.Text.UTF8Encoding]::new($false)
)
Move-Item -LiteralPath $temporaryPath -Destination $receiptPath -Force
Write-Host "Automation verified for commit $approvedCommit."
