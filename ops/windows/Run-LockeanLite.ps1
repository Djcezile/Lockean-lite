[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'automation-config.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$automationRoot = Split-Path -Parent $ConfigPath
$logsDir = Join-Path $automationRoot 'logs'
$stateDir = Join-Path $automationRoot 'state'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$audit = Join-Path $logsDir ('scheduler_' + (Get-Date -Format yyyyMMdd) + '.log')
$mutex = $null
$hasMutex = $false
$keepAwake = $false
$stage = 'initializing'

function Write-Audit([string]$Message) {
    $line = (Get-Date -Format o) + ' ' + $Message
    Add-Content -LiteralPath $audit -Value $line -Encoding UTF8
    Write-Host $Message
}

function Read-Config {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw 'configuration_missing'
    }
    return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

try {
    $config = Read-Config
    $repo = [string]$config.repo_root
    $python = [string]$config.python_path
    $approvedCommit = ([string]$config.approved_commit).ToLowerInvariant()

    $stage = 'file_checks'
    if (-not (Test-Path -LiteralPath $repo -PathType Container)) { throw 'repo_missing' }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }
    if ($approvedCommit -notmatch '^[0-9a-f]{40}$') { throw 'approved_commit_invalid' }
    if (-not (Test-Path -LiteralPath (Join-Path $repo 'src\lockean_lite\session_launcher.py'))) {
        throw 'session_launcher_missing'
    }

    $stage = 'source_revision'
    $head = (& git -C $repo rev-parse HEAD).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $head -ne $approvedCommit) {
        Write-Audit 'SOURCE REVISION BLOCKED: approved commit does not match repository HEAD.'
        throw 'source_revision_unapproved'
    }
    $worktreeChanges = @(& git -C $repo status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $worktreeChanges.Count -gt 0) {
        Write-Audit 'SOURCE REVISION BLOCKED: worktree is not clean.'
        throw 'source_revision_unapproved'
    }
    Write-Audit ("SOURCE REVISION: commit=$approvedCommit | worktree=clean")
    Set-Location -LiteralPath $repo

    $stage = 'credentials'
    foreach ($name in @('ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'OPENAI_API_KEY')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
        if ([string]::IsNullOrWhiteSpace($value)) { throw 'user_credential_missing' }
        Set-Item -Path ('Env:' + $name) -Value $value
    }
    $keyPath = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets\authorization-key.xml'
    $key = Import-Clixml -LiteralPath $keyPath
    if (-not ($key -is [System.Security.SecureString]) -or $key.Length -eq 0) {
        throw 'signing_key_unavailable'
    }
    $credential = [System.Net.NetworkCredential]::new('Lockean', $key)
    $env:LOCKEAN_AUTHORIZATION_SIGNING_KEY = $credential.Password
    Remove-Variable credential, key

    $stage = 'broker_planning'
    $planOutput = @(& $python -m lockean_lite.automation.session_plan --repo-root $repo)
    $planExit = $LASTEXITCODE
    try { $plan = ($planOutput -join "`n") | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'planner_response_invalid' }

    if ($planExit -ne 0) {
        $reason = [string]$plan.reason
        if ($reason -notmatch '^[a-z][a-z0-9_]{0,63}$') { $reason = 'unclassified' }
        $attemptCount = 0
        if ($plan.PSObject.Properties.Name -contains 'planning_attempts') {
            $attemptCount = [int]$plan.planning_attempts
        }
        Write-Audit ("PLANNER FAILURE: reason=$reason | read_only_attempts=$attemptCount | exit_code=$planExit")
        throw 'planner_blocked'
    }
    if ($plan.PSObject.Properties.Name -contains 'planning_attempts' -and
        [int]$plan.planning_attempts -gt 1) {
        Write-Audit ("PLANNER RECOVERED: read_only_attempts=$($plan.planning_attempts)")
    }
    if ($plan.status -eq 'SKIP') {
        Write-Audit ('SKIP: ' + $plan.reason + ' ' + $plan.market_date)
        exit 0
    }
    if ($plan.status -ne 'READY' -or $plan.paper_only -ne $true) { throw 'plan_unverified' }
    Write-Audit ("PLAN: Day $($plan.day_number) | completed-through $($plan.completed_through) | expiration $($plan.expiration) | close $($plan.market_close)")

    if ($DryRun) {
        Write-Audit 'DRY RUN PASSED: No autonomous trading module invoked.'
        exit 0
    }

    $stage = 'time_guard'
    $time = (Get-Date).TimeOfDay
    if ($time -lt [TimeSpan]::Parse('09:00:00') -or
        $time -gt [TimeSpan]::Parse('10:00:00')) { throw 'outside_approved_start_window' }

    $stage = 'duplicate_guard'
    $mutex = [System.Threading.Mutex]::new($false, 'Local\LockeanLiteScheduledSession')
    $hasMutex = $mutex.WaitOne(0)
    if (-not $hasMutex) { throw 'another_scheduled_session_running' }

    $stage = 'manual_session_guard'
    $runningSessions = @(Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and
        $_.CommandLine -match 'lockean_lite\.(session_launcher|autonomous_session)'
    })
    if ($runningSessions.Count -gt 0) { throw 'manual_session_already_running' }

    $legacyMarker = Join-Path $logsDir ('started_' + $plan.market_date + '.txt')
    $marker = Join-Path $stateDir ('started_' + $plan.market_date + '.json')
    if (Test-Path -LiteralPath $legacyMarker) { throw 'market_date_already_attempted' }
    $file = [System.IO.File]::Open(
        $marker,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $startRecord = @{
            market_date = [string]$plan.market_date
            day_number = [int]$plan.day_number
            started_at = (Get-Date -Format o)
            approved_commit = $approvedCommit
        } | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($startRecord)
        $file.Write($bytes, 0, $bytes.Length)
    } finally { $file.Dispose() }

    $stage = 'keep_awake'
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LockeanSystemAwake {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
    if ([LockeanSystemAwake]::SetThreadExecutionState([uint32]2147483649) -eq 0) {
        throw 'cannot_hold_system_awake'
    }
    $keepAwake = $true

    $stage = 'trading_session'
    $runnerStarted = Get-Date
    Write-Audit 'START: Launching approved Alpaca PAPER-only session runner.'
    & $python -m lockean_lite.session_launcher `
        --day-number ([int]$plan.day_number) `
        --completed-through ([string]$plan.completed_through) `
        --expiration ([string]$plan.expiration) `
        --approved-commit $approvedCommit
    $runExit = $LASTEXITCODE
    Write-Audit ("RUNNER_EXIT_CODE: $runExit")
    if ($runExit -ne 0) { throw 'trading_session_failed' }

    $stage = 'completion_reconciliation'
    $compactDate = ([string]$plan.market_date).Replace('-', '')
    $pattern = 'lockean_lite_DAY' + [string]$plan.day_number + '_' + $compactDate + '_*.log'
    $sessionLog = Get-ChildItem -LiteralPath (Join-Path $repo 'logs') -Filter $pattern -File |
        Where-Object { $_.LastWriteTime -ge $runnerStarted.AddMinutes(-1) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $sessionLog) { throw 'canonical_session_log_missing' }
    $sessionText = Get-Content -LiteralPath $sessionLog.FullName -Raw -Encoding UTF8
    if (-not $sessionText.Contains('MARKET CLOSED: autonomous session complete') -or
        -not $sessionText.Contains('SESSION RUN RESULT: COMPLETE | exit_code=0')) {
        throw 'canonical_session_log_incomplete'
    }

    $completionPath = Join-Path $stateDir ('completed_' + $plan.market_date + '.json')
    $temporaryPath = $completionPath + '.tmp'
    $completionRecord = @{
        market_date = [string]$plan.market_date
        day_number = [int]$plan.day_number
        completed_at = (Get-Date -Format o)
        approved_commit = $approvedCommit
        runner_exit_code = 0
        session_log = $sessionLog.FullName
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText(
        $temporaryPath,
        $completionRecord,
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $completionPath -Force
    Write-Audit ("COMPLETE: reconciled canonical log " + $sessionLog.Name)
    exit 0
}
catch {
    Write-Audit ("BLOCKED: $stage | inspect local logs; no automatic retry")
    exit 1
}
finally {
    if ($keepAwake) {
        [void][LockeanSystemAwake]::SetThreadExecutionState([uint32]2147483648)
    }
    if ($hasMutex) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
    foreach ($name in @(
        'LOCKEAN_AUTHORIZATION_SIGNING_KEY',
        'ALPACA_API_KEY',
        'ALPACA_SECRET_KEY',
        'OPENAI_API_KEY'
    )) {
        Remove-Item -Path ('Env:' + $name) -ErrorAction SilentlyContinue
    }
}
