import subprocess
import sys
from pathlib import Path


def test_legacy_scan_clean() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "legacy_scan.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
