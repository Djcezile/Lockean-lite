from datetime import date, datetime
from functools import cache
import json
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

import pytest


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops" / "windows"


def test_windows_automation_assets_are_version_controlled_and_secret_free():
    expected = {
        "Run-LockeanLite.ps1",
        "Watch-LockeanLite.ps1",
        "Install-LockeanLiteAutomation.ps1",
        "Verify-LockeanLiteAutomation.ps1",
        "Set-LockeanLiteNotification.ps1",
        "Set-LockeanLitePush.ps1",
        "automation-config.example.json",
    }
    assert expected <= {path.name for path in OPS.iterdir()}

    config = json.loads(
        (OPS / "automation-config.example.json").read_text(encoding="utf-8")
    )
    assert config["approved_commit"] == "REPLACE_WITH_40_CHARACTER_GIT_COMMIT"
    assert "webhook" not in json.dumps(config).lower()
    assert "secret" not in json.dumps(config).lower()


def test_daily_wrapper_pins_source_and_reconciles_canonical_log():
    text = (OPS / "Run-LockeanLite.ps1").read_text(encoding="utf-8")
    assert "lockean_lite.automation.session_plan" in text
    assert "--approved-commit" in text
    assert "source_revision_unapproved" in text
    assert "MARKET CLOSED: autonomous session complete" in text
    assert "SESSION RUN RESULT: COMPLETE | exit_code=0" in text
    assert "completed_" in text
    assert "git pull" not in text.lower()


def test_installer_requires_same_commit_verification_before_activation():
    text = (OPS / "Install-LockeanLiteAutomation.ps1").read_text(
        encoding="utf-8"
    )
    assert "verification_" in text
    assert "live_notification_verified" in text
    assert "config_sha256" in text
    assert "Export-ScheduledTask" in text
    assert "WakeToRun" in text
    assert "IgnoreNew" in text
    assert "LockeanLite-Watchdog" in text
    assert "Eastern Standard Time" in text


def test_watchdog_wrapper_uses_dpapi_secret_and_independent_module():
    text = (OPS / "Watch-LockeanLite.ps1").read_text(encoding="utf-8")
    assert "Import-Clixml" in text
    assert "LOCKEAN_NOTIFICATION_WEBHOOK" in text
    assert "lockean_lite.automation.session_watchdog" in text


def test_push_setup_generates_private_ntfy_topic_and_uses_dpapi():
    text = (OPS / "Set-LockeanLitePush.ps1").read_text(encoding="utf-8")
    assert "RandomNumberGenerator" in text
    assert "New-Object byte[] 16" in text
    assert "https://ntfy.sh/" in text
    assert "Export-Clixml" in text
    assert "Set-Clipboard" in text
    assert "notification-endpoint.xml" in text


@cache
def _installer_trigger_boundaries():
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for offline installer fragment tests")
    installer = (OPS / "Install-LockeanLiteAutomation.ps1").read_text(encoding="utf-8")
    # Execute just the trigger construction with a mock for the native cmdlet.
    # The mock reproduces the observed Windows cmdlet's UTC serialization.
    start = installer.index("$weekdays = ")
    end = installer.index("$settings =", start)
    script = r"""
$ErrorActionPreference = 'Stop'
function New-ScheduledTaskTrigger {
    param([switch]$Weekly, [int]$WeeksInterval, [string[]]$DaysOfWeek, [datetime]$At)
    if (-not $Weekly -or $WeeksInterval -ne 1 -or
        ($DaysOfWeek -join ',') -ne 'Monday,Tuesday,Wednesday,Thursday,Friday') {
        throw 'unexpected trigger cadence'
    }
    $local = [datetime]::new(2026, 10, 29, $At.Hour, $At.Minute, 0)
    $utc = [datetimeoffset]::new($local, [timespan]::FromHours(-4)).UtcDateTime
    [pscustomobject]@{ StartBoundary = $utc.ToString('s') + 'Z' }
}
$config = @{ daily_start = '09:15'; watchdog_start = '09:20' }
""" + installer[start:end] + r"""
@{ daily = $dailyTrigger.StartBoundary; watchdog = $watchdogTrigger.StartBoundary } |
    ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(("name", "expected"), [("daily", "09:15"), ("watchdog", "09:20")])
@pytest.mark.parametrize(("before", "after"), [
    (date(2026, 3, 6), date(2026, 3, 9)),
    (date(2026, 10, 30), date(2026, 11, 2)),
])
def test_weekly_triggers_preserve_new_york_wall_clock(name, expected, before, after):
    boundary = datetime.fromisoformat(_installer_trigger_boundaries()[name])
    eastern = ZoneInfo("America/New_York")

    def local_clock(day):
        occurrence = datetime.combine(day, boundary.timetz())
        if occurrence.tzinfo is not None:
            occurrence = occurrence.astimezone(eastern)
        return occurrence.strftime("%H:%M")

    assert (local_clock(before), local_clock(after)) == (expected, expected)
    assert boundary.tzinfo is None
