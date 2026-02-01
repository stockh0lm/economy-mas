import subprocess
import sys
from pathlib import Path


def _run_legacy_scan(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "legacy_scan.py"
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def test_legacy_scan_clean() -> None:
    result = _run_legacy_scan()
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
    assert "legacy_scan: OK" in result.stdout


def test_legacy_muster_bereinigt() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → „Legacy-Muster vollständig bereinigen"""

    result = _run_legacy_scan("--cleanup", "--include-tests")
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
    assert "CLEANUP: No legacy patterns found" in result.stdout
