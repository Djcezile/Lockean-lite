"""Offline-only acceptance qualification. No native task mutation or credential UI."""
from functools import cache
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops" / "windows"


@cache
def probe():
    shell = shutil.which("powershell.exe")
    if shell is None:
        pytest.skip("Windows PowerShell 5.1 required for native offline tooling probe")
    evidence = Path(os.environ.get("LOCKEAN_CAPTURE_EVIDENCE_ROOT") or tempfile.mkdtemp(prefix="lockean-capture-evidence-"))
    evidence.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "LOCKEAN_CAPTURE_EVIDENCE_ROOT": str(evidence)}
    result = subprocess.run([
        shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "tests/helpers/windows_acceptance_probe.ps1"), "-Ops", str(OPS),
    ], capture_output=True, text=True, timeout=60, check=False, env=env)
    inventory = [{"path": str(path.relative_to(evidence)), "directory": path.is_dir(),
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}
                 for path in sorted(evidence.rglob("*"))]
    (evidence / "ARTIFACT-INVENTORY.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    # Never forward arbitrary subprocess diagnostics to pytest assertion output.
    assert result.returncode == 0, "offline acceptance probe failed; inspect sanitized probe status"
    assert "SYNTHETIC_SECRET_MARKER" not in result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("operation", ["ReadXml", "ReadSecurity", "RequireIdle", "Authenticate", "Validate", "Write", "Remove", "SecurityMatches"])
def test_every_adapter_operation_rejects_production_and_alias_names(operation):
    assert probe()["isolation_" + operation]
    assert probe()["native_isolation_" + operation]


@pytest.mark.parametrize("case", [
    "approval_before_native_connection", "credential_approval", "unsafe_action", "extra_action",
    "enabled_fixture", "catchup", "registration_trigger", "wrong_logon", "principal_drift",
    "settings_drift", "security_drift", "running", "missing_auth", "secret_redaction",
    "partial_rollback", "rollback_failure_primary", "success_preservation", "cleanup_guard",
    "backup_hash", "backup_path", "backup_disabled", "backup_missing", "native_serialization",
    "no_mutation_approval", "backup_valid", "native_adapter_private", "xml_external_entity",
    "recovery_pins", "recovery_valid", "recovery_auth", "recovery_drift", "recovery_all_attempted",
    "backup_unc", "permission_failure", "existing_fixture", "native_normalization_guard", "no_public_backend_injection",
])
def test_acceptance_and_recovery_contracts(case):
    assert probe()[case]


@pytest.mark.parametrize("scenario", [
    "failure", "partial_directory", "partial_file", "cleanup_failure", "both_cleanup_fail",
    "running_guard", "enabled_guard", "action_guard", "cleanup_no_effect", "readback_failure",
    "success", "success_then_rollback",
])
def test_recovery_capture_failure_cleans_only_guarded_fixtures_and_retains_evidence(scenario):
    assert probe()["capture_" + scenario]


@pytest.mark.parametrize("case", [
    "dst_spring_daily", "dst_fall_daily", "dst_spring_watchdog", "dst_fall_watchdog",
    "dst_missing", "dst_hresult", "dst_mismatch", "dst_weekend", "dst_offset",
    "dst_daily_recurrence", "dst_disabled", "dst_truncated", "dst_exact_allowlist",
    "dst_readonly_surface", "dst_abi",
])
def test_readonly_schedule_client_contracts(case):
    assert probe()[case]


def test_entrypoints_require_explicit_mutation_and_credential_approval():
    text = (OPS / "Test-LockeanLiteIsolatedAcceptance.ps1").read_text()
    assert "ExecuteDisposableDrill" in text and "ApproveCredentialEntry" in text
    assert "CreateNative" in text and "Get-Credential" not in text
    readonly = (OPS / "Test-LockeanLiteScheduleDST.ps1").read_text()
    assert "ScheduleClient" in readonly
    assert not any(word in readonly for word in ("Register-ScheduledTask", "Enable-ScheduledTask", "Start-ScheduledTask"))


def test_default_entrypoint_performs_no_native_task_operations():
    shell = shutil.which("powershell.exe")
    if shell is None:
        pytest.skip("Windows PowerShell required")
    result = subprocess.run([
        shell, "-NoProfile", "-NonInteractive", "-File",
        str(OPS / "Test-LockeanLiteIsolatedAcceptance.ps1"),
    ], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, "compile-only entrypoint failed"
    assert json.loads(result.stdout)["NativeOperations"] is False


def test_readonly_entrypoint_rejects_task_alias_without_provider_diagnostics():
    shell = shutil.which("powershell.exe")
    if shell is None:
        pytest.skip("Windows PowerShell required")
    result = subprocess.run([
        shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
        str(OPS / "Test-LockeanLiteScheduleDST.ps1"), "-PermittedTask", r"\LockeanLite-DailyPaper",
    ], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 1
    assert "BLOCKED" in result.stdout and result.stderr == ""
