import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops" / "windows"


def test_windows_automation_assets_are_version_controlled_and_secret_free():
    expected = {
        "Run-LockeanLite.ps1",
        "Watch-LockeanLite.ps1",
        "Install-LockeanLiteAutomation.ps1",
        "Verify-LockeanLiteAutomation.ps1",
        "Set-LockeanLiteNotification.ps1",
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
