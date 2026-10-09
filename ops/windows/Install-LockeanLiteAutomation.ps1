[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [string]$ApprovedCommit = '',
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'LockeanLite\Automation\automation-config.json'),
    [switch]$Activate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'windows_timezone_must_be_eastern_standard_time'
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }

$head = (& git -C $RepoRoot rev-parse HEAD).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') { throw 'git_head_unavailable' }
if ([string]::IsNullOrWhiteSpace($ApprovedCommit)) { $ApprovedCommit = $head }
$ApprovedCommit = $ApprovedCommit.ToLowerInvariant()
if ($ApprovedCommit -ne $head) { throw 'approved_commit_not_checked_out' }
$worktreeChanges = @(& git -C $RepoRoot status --porcelain)
if ($LASTEXITCODE -ne 0 -or $worktreeChanges.Count -gt 0) { throw 'worktree_not_clean' }

$automationRoot = Split-Path -Parent $ConfigPath
$binDir = Join-Path $automationRoot 'bin'
$stateDir = Join-Path $automationRoot 'state'
$backupDir = Join-Path $automationRoot 'backups'
foreach ($directory in @($automationRoot, $binDir, $stateDir, $backupDir, (Join-Path $automationRoot 'logs'))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    $configBackup = Join-Path $backupDir ('automation-config_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.json')
    Copy-Item -LiteralPath $ConfigPath -Destination $configBackup
}

foreach ($name in @(
    'Run-LockeanLite.ps1',
    'Watch-LockeanLite.ps1',
    'Verify-LockeanLiteAutomation.ps1',
    'Set-LockeanLiteNotification.ps1',
    'Set-LockeanLitePush.ps1',
    'Install-LockeanLiteAutomation.ps1'
)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $binDir $name) -Force
}

$config = [ordered]@{
    repo_root = $RepoRoot
    python_path = $python
    approved_commit = $ApprovedCommit
    daily_task_name = 'LockeanLite-DailyPaper'
    watchdog_task_name = 'LockeanLite-Watchdog'
    daily_start = '09:15'
    watchdog_start = '09:20'
    heartbeat_timeout_seconds = 180
    completion_grace_minutes = 15
    watchdog_poll_seconds = 120
}
$configJson = $config | ConvertTo-Json
[System.IO.File]::WriteAllText(
    $ConfigPath,
    $configJson,
    [System.Text.UTF8Encoding]::new($false)
)
$configHash = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "Staged Lockean Lite automation for commit $ApprovedCommit."

if (-not $Activate) {
    Write-Host 'Scheduled tasks were not changed. Run verification, then rerun with -Activate.'
    exit 0
}

$verificationPath = Join-Path $stateDir ('verification_' + $ApprovedCommit + '.json')
if (-not (Test-Path -LiteralPath $verificationPath -PathType Leaf)) {
    throw 'matching_verification_receipt_missing'
}
$verification = Get-Content -LiteralPath $verificationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($verification.approved_commit -ne $ApprovedCommit -or
    $verification.repo_root -ne $RepoRoot -or
    $verification.config_sha256 -ne $configHash -or
    $verification.tests_passed -ne $true -or
    $verification.dry_run_passed -ne $true -or
    $verification.notification_simulation_passed -ne $true -or
    $verification.live_notification_verified -ne $true) {
    throw 'matching_verification_receipt_invalid'
}

$notificationPath = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets\notification-endpoint.xml'
if (-not (Test-Path -LiteralPath $notificationPath -PathType Leaf)) {
    throw 'notification_destination_unavailable'
}

$dailyName = [string]$config.daily_task_name
$watchdogName = [string]$config.watchdog_task_name
$dailyBackup = $null
$watchdogBackup = $null
$existingDaily = Get-ScheduledTask -TaskName $dailyName -ErrorAction SilentlyContinue
$existingWatchdog = Get-ScheduledTask -TaskName $watchdogName -ErrorAction SilentlyContinue
if ($null -ne $existingDaily) {
    $dailyBackup = Export-ScheduledTask -TaskName $dailyName
    $dailyBackup | Set-Content -LiteralPath (Join-Path $backupDir ($dailyName + '_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.xml')) -Encoding UTF8
}
if ($null -ne $existingWatchdog) {
    $watchdogBackup = Export-ScheduledTask -TaskName $watchdogName
    $watchdogBackup | Set-Content -LiteralPath (Join-Path $backupDir ($watchdogName + '_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.xml')) -Encoding UTF8
}

$powerShellPath = (Get-Process -Id $PID).Path
$dailyScript = Join-Path $binDir 'Run-LockeanLite.ps1'
$watchdogScript = Join-Path $binDir 'Watch-LockeanLite.ps1'
$dailyAction = New-ScheduledTaskAction -Execute $powerShellPath -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $dailyScript + '" -ConfigPath "' + $ConfigPath + '"')
$watchdogAction = New-ScheduledTaskAction -Execute $powerShellPath -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $watchdogScript + '" -ConfigPath "' + $ConfigPath + '"')
$weekdays = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
$dailyTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weekdays -At $config.daily_start
$watchdogTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weekdays -At $config.watchdog_start
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 9) `
    -MultipleInstances IgnoreNew `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited

try {
    $dailyTask = New-ScheduledTask -Action $dailyAction -Trigger $dailyTrigger -Settings $settings -Principal $principal -Description ('Lockean Lite paper session; approved commit ' + $ApprovedCommit)
    Register-ScheduledTask -TaskName $dailyName -InputObject $dailyTask -Force | Out-Null
    $watchdogTask = New-ScheduledTask -Action $watchdogAction -Trigger $watchdogTrigger -Settings $settings -Principal $principal -Description ('Independent Lockean Lite session watchdog; approved commit ' + $ApprovedCommit)
    Register-ScheduledTask -TaskName $watchdogName -InputObject $watchdogTask -Force | Out-Null
    if ($null -eq (Get-ScheduledTask -TaskName $dailyName -ErrorAction Stop) -or
        $null -eq (Get-ScheduledTask -TaskName $watchdogName -ErrorAction Stop)) {
        throw 'registered_task_verification_failed'
    }
} catch {
    if ($null -ne $dailyBackup) {
        Register-ScheduledTask -TaskName $dailyName -Xml $dailyBackup -Force | Out-Null
    } else {
        Unregister-ScheduledTask -TaskName $dailyName -Confirm:$false -ErrorAction SilentlyContinue
    }
    if ($null -ne $watchdogBackup) {
        Register-ScheduledTask -TaskName $watchdogName -Xml $watchdogBackup -Force | Out-Null
    } else {
        Unregister-ScheduledTask -TaskName $watchdogName -Confirm:$false -ErrorAction SilentlyContinue
    }
    throw
}

Write-Host 'Activated and verified LockeanLite-DailyPaper plus LockeanLite-Watchdog.'
