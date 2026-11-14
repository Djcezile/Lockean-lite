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
    assert "$Session.ReadXml" in text
    assert "$Session.ReadSecurity" in text
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
    end = installer.index("$snapshots =", start)
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
$Session = [pscustomobject]@{ CurrentTime = [datetime]::new(2026, 10, 29, 6, 0, 0) }
""" + installer[start:end] + r"""
@{ daily = $dailyTrigger.StartBoundary; watchdog = $watchdogTrigger.StartBoundary } |
    ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, check=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
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


_TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
_WEEK = (
    "<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek>"
    "<Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek></ScheduleByWeek>"
)
_TRIGGER_ENABLED = "<Enabled>true</Enabled>"


@pytest.mark.parametrize(("old", "new", "accepted"), [
    pytest.param("", "", True, id="valid"),
    pytest.param("T09:20:00", "T09:20:00Z", False, id="utc-boundary"),
    pytest.param("T09:20:00", "T<Time>09:20:00</Time>", False, id="malformed-boundary"),
    pytest.param("<Friday/>", "<Saturday/>", False, id="wrong-weekdays"),
    pytest.param("<WeeksInterval>1", "<WeeksInterval>2", False, id="two-week-interval"),
    pytest.param(_WEEK, "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>",
                 False, id="daily-recurrence"),
    pytest.param(_TRIGGER_ENABLED, "<Enabled>false</Enabled>", False, id="disabled-trigger"),
    pytest.param("<Settings><Enabled>true", "<Settings><Enabled>false",
                 False, id="disabled-task"),
    pytest.param(_TRIGGER_ENABLED, "", True, id="default-trigger-enabled"),
    pytest.param("<Settings><Enabled>true</Enabled>", "<Settings>",
                 True, id="default-task-enabled"),
    pytest.param(_TRIGGER_ENABLED, "<Enabled>1</Enabled>", True, id="numeric-true"),
    pytest.param(_TRIGGER_ENABLED, "<Enabled>0</Enabled>", False, id="numeric-false"),
    pytest.param(_TRIGGER_ENABLED, "<Enabled>yes</Enabled>", False, id="malformed-enabled"),
    pytest.param(_WEEK, "", False, id="missing-recurrence"),
    pytest.param("<WeeksInterval>1</WeeksInterval>", "", False, id="missing-interval"),
    pytest.param("<WeeksInterval>1", "<WeeksInterval>one", False, id="malformed-interval"),
    pytest.param("<DaysOfWeek>", "<NotDaysOfWeek>", False, id="malformed-xml"),
    pytest.param("<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>",
                 "", False, id="missing-days"),
    pytest.param("<Friday/>", "<Thursday/>", False, id="duplicate-weekday"),
    pytest.param("<Friday/>", "<Friday>invalid</Friday>", False, id="malformed-weekday"),
    pytest.param(_WEEK, _WEEK + _WEEK, False, id="duplicate-weekly-schedule"),
    pytest.param(_WEEK, _WEEK + "<ScheduleByDay/>", False, id="mixed-recurrence"),
])
def test_installer_validates_registered_schedule_and_rolls_back(old, new, accepted):
    if old:
        actual = _run_installation_scenario("tampered-readback", {"old": old, "new": new})
        assert actual["mutationApplied"]
    else:
        actual = _run_installation_scenario("valid")
    assert bool(actual["failure"]) is (not accepted)
    if not accepted:
        assert actual["events"][-2:] == ["restore:watchdog", "restore:daily"]
    assert actual["disposed"]


def _run_installation_scenario(scenario, mutation=None):
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for offline installer tests")
    args = [
        powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "tests" / "helpers" / "windows_installer_harness.ps1"),
        "-Installer", str(OPS / "Install-LockeanLiteAutomation.ps1"),
        "-Scenario", scenario,
    ]
    if mutation is not None:
        args += ["-Mutation", json.dumps(mutation)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_ROLLBACK_PASSWORD_MARKER" not in result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("scenario", [
    "permission", "missing-credential", "incorrect-credential",
    "invalid-recovery", "running", "wrong-logon", "late-window", "imminent-enabled", "window-advanced",
])
def test_installation_preflight_rejects_before_any_task_write(scenario):
    actual = _run_installation_scenario(scenario)
    assert actual["failure"]
    assert not any(event.startswith(("write:", "restore:", "remove:")) for event in actual["events"])
    assert actual["disposed"]


def test_installation_preserves_settings_and_authenticates_before_mutation():
    actual = _run_installation_scenario("valid")
    assert actual["failure"] == ""
    assert actual["preserved"]
    assert actual["disposed"]
    assert actual["events"].index("authenticate") < actual["events"].index("write:daily")
    assert actual["events"].count("validate:daily") == 2
    assert actual["events"].count("validate:watchdog") == 2
    assert "<LogonType>Password</LogonType>" in actual["definitions"]["daily"]
    assert "<LogonType>InteractiveToken</LogonType>" in actual["definitions"]["watchdog"]


@pytest.mark.parametrize("scenario", ["partial", "rollback-fails", "both-rollbacks-fail"])
def test_activation_error_survives_partial_installation_and_all_rollback_attempts(scenario):
    actual = _run_installation_scenario(scenario)
    assert "synthetic_activation_failure" in actual["failure"]
    assert actual["events"][-2:] == ["restore:watchdog", "restore:daily"]
    assert len(actual["rollback"]) == {"partial": 0, "rollback-fails": 1, "both-rollbacks-fail": 2}[scenario]
    assert actual["disposed"]


def test_new_task_is_removed_and_existing_task_restored_after_partial_failure():
    actual = _run_installation_scenario("new-task-partial")
    assert "synthetic_activation_failure" in actual["failure"]
    assert actual["events"][-2:] == ["remove:watchdog", "restore:daily"]
    assert "watchdog" not in actual["definitions"]


def test_security_descriptor_drift_causes_rollback():
    actual = _run_installation_scenario("security-drift")
    assert actual["failure"]
    assert "restore:daily" in actual["events"]


def test_native_adapter_password_registration_restoration_and_error_redaction():
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("Windows PowerShell is required for the compiled native adapter probe")
    result = subprocess.run([
        powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "tests" / "helpers" / "windows_native_adapter_probe.ps1"),
        "-NativeSource", str(OPS / "LockeanLiteSchedulerNative.cs"),
    ], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_PASSWORD_ONLY" not in result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "authenticated": True, "calls": 5, "hresult": -2147023570,
        "sanitized": True, "disposed": True, "accessChecks": True, "windowChecks": True,
    }



def test_fresh_daily_uses_password_and_authentication():
    actual = _run_installation_scenario("new-daily")
    assert actual["failure"] == ""
    assert "<LogonType>Password</LogonType>" in actual["definitions"]["daily"]
    assert actual["events"].index("authenticate") < actual["events"].index("write:daily")



@pytest.mark.parametrize("scenario", [
    "disabled-morning", "disabled-afternoon",
    "trigger-disabled-afternoon", "mixed-afternoon",
])
def test_existing_disabled_states_survive_safe_maintenance(scenario):
    from xml.etree import ElementTree

    actual = _run_installation_scenario(scenario)
    assert actual["failure"] == ""
    assert actual["preserved"]
    assert actual["rollback"] == []
    for name, xml in actual["definitions"].items():
        root = ElementTree.fromstring(xml)
        task = root.find(f"{{{_TASK_NS}}}Settings/{{{_TASK_NS}}}Enabled").text
        trigger = root.find(
            f"{{{_TASK_NS}}}Triggers/{{{_TASK_NS}}}CalendarTrigger/{{{_TASK_NS}}}Enabled"
        ).text
        assert task == ("true" if scenario == "trigger-disabled-afternoon" or
                       (scenario == "mixed-afternoon" and name == "watchdog") else "false")
        assert trigger == ("false" if scenario == "trigger-disabled-afternoon" else "true")
        boundary = root.find(
            f"{{{_TASK_NS}}}Triggers/{{{_TASK_NS}}}CalendarTrigger/{{{_TASK_NS}}}StartBoundary"
        ).text
        assert datetime.fromisoformat(boundary) > datetime(2026, 11, 13, 6 if scenario == "disabled-morning" else 15)


def test_disabled_afternoon_partial_failure_restores_both_originals():
    actual = _run_installation_scenario("disabled-partial")
    assert "synthetic_activation_failure" in actual["failure"]
    assert actual["events"][-2:] == ["restore:watchdog", "restore:daily"]
    assert actual["preserved"]
    assert actual["rollback"] == []


def test_disabled_task_cannot_be_enabled_during_readback():
    actual = _run_installation_scenario("disabled-readback-enabled")
    assert actual["failure"]
    assert actual["events"][-2:] == ["restore:watchdog", "restore:daily"]
    assert actual["preserved"]
