import subprocess
import sys
from pathlib import Path


def test_compare_posthoc_smoke_real_export(tmp_path: Path) -> None:
    """Referenz: doc/issues.md Abschnitt 5 → Implement Option A (Smoke-Test)"""

    repo_root = Path(__file__).resolve().parents[1]
    metrics_dir = repo_root / "output" / "metrics"
    assert metrics_dir.exists(), "repo should ship a small output/metrics sample for smoke tests"

    candidates = sorted(metrics_dir.glob("global_metrics_*.csv"))
    assert candidates, "no global_metrics export files found for smoke test"

    # Use latest available export in repo (mtime sort is deterministic within the checkout).
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    run_id = latest.stem.split("global_metrics_")[-1]

    script = repo_root / "scripts" / "compare_posthoc.py"
    plots_dir = tmp_path / "plots"

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run-id",
            run_id,
            "--metrics-dir",
            str(metrics_dir),
            "--plots-dir",
            str(plots_dir),
            "--assume-services-in-gdp",
            "--output-prefix",
            "pytest",
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr

    out_dir = plots_dir / run_id / "posthoc"
    assert (out_dir / "price_index.png").exists()
    assert (out_dir / "inflation_rate.png").exists()
    assert (out_dir / f"pytest_differences_{run_id}.csv").exists()
    assert (out_dir / f"pytest_summary_{run_id}.md").exists()
