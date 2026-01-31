"""Analyze a global_metrics_*.csv export without external dependencies.

This script is intentionally dependency-free (no pandas) so it can run in minimal
CI/pytest environments.

It prints head/tail excerpts and a few diagnostic aggregates:
- consumption near-zero?
- velocity collapse?
- inventory monotonic rise?
- sales non-zero?

Usage:
    python scripts/analyze_global_metrics_csv.py output/metrics/global_metrics_XXXX.csv

If no path is provided, it uses the newest global_metrics_*.csv by mtime.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from logger import log


WANTED = [
    "time_step",
    "employment_rate",
    "average_nominal_wage",
    "income",
    "household_consumption",
    "gdp",
    "m1_proxy",
    "m2_proxy",
    "velocity_proxy",
    "bankruptcy_rate",
    "inventory_value_total",
    "sales_total",
]


@dataclass
class Series:
    name: str
    values: list[float]

    def tail(self, n: int) -> list[float]:
        return self.values[-n:] if n > 0 else []


def _find_latest_global_metrics(metrics_dir: Path) -> Path:
    files = list(metrics_dir.glob("global_metrics_*.csv"))
    if not files:
        raise FileNotFoundError(f"No global_metrics_*.csv under {metrics_dir}")
    files.sort(key=lambda p: p.stat().st_mtime)
    return files[-1]


def _to_float(value: str) -> float:
    if value is None:
        return 0.0
    value = value.strip()
    if value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [row for row in reader]
    return fieldnames, rows


def extract_series(rows: list[dict[str, str]], name: str) -> Series:
    return Series(name=name, values=[_to_float(r.get(name, "")) for r in rows])


def print_excerpt(rows: list[dict[str, str]], cols: list[str], head: int = 10, tail: int = 10) -> None:
    def _fmt_row(r: dict[str, str]) -> str:
        parts = []
        for c in cols:
            parts.append(r.get(c, ""))
        return "\t".join(parts)

    log("\t".join(cols), level="INFO")
    for r in rows[:head]:
        log(_fmt_row(r), level="INFO")
    if len(rows) > head + tail:
        log("...", level="INFO")
    for r in rows[-tail:]:
        log(_fmt_row(r), level="INFO")


def diagnostics(rows: list[dict[str, str]]) -> None:
    by = {name: extract_series(rows, name) for name in WANTED if name in rows[0]}

    def _tail_stats(series: Series, n: int = 50) -> tuple[float, float, float, float]:
        tail = series.tail(n)
        if not tail:
            return 0.0, 0.0, 0.0, 0.0
        return (
            statistics.mean(tail),
            statistics.median(tail),
            min(tail),
            max(tail),
        )

    if "household_consumption" in by:
        mean_, med_, mn, mx = _tail_stats(by["household_consumption"], 50)
        log(
            f"consumption tail50: mean={mean_:.6g} median={med_:.6g} min={mn:.6g} max={mx:.6g}",
            level="INFO",
        )

    if "sales_total" in by:
        sales = by["sales_total"].values
        nonzero = sum(1 for v in sales if v > 0)
        log(f"sales_total: sum={sum(sales):.6g} nonzero_steps={nonzero}/{len(sales)}", level="INFO")

    if "velocity_proxy" in by:
        vel = by["velocity_proxy"].values
        if vel:
            log(f"velocity_proxy: first={vel[0]:.6g} mid={vel[len(vel)//2]:.6g} last={vel[-1]:.6g}", level="INFO")

    if "inventory_value_total" in by:
        inv = by["inventory_value_total"].values
        non_decreasing = True
        for i in range(1, len(inv)):
            if inv[i] + 1e-9 < inv[i - 1]:
                non_decreasing = False
                break
        pos_share = 0.0
        if len(inv) > 1:
            diffs = [inv[i] - inv[i - 1] for i in range(1, len(inv))]
            pos_share = sum(1 for d in diffs if d > 0) / len(diffs)
        if inv:
            log(
                (
                    f"inventory_value_total: first={inv[0]:.6g} last={inv[-1]:.6g} "
                    f"non_decreasing={non_decreasing} positive_diff_share={pos_share:.3f}"
                ),
                level="INFO",
            )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", default=None)
    args = parser.parse_args()

    if args.csv_path:
        path = Path(args.csv_path)
    else:
        path = _find_latest_global_metrics(Path("output/metrics"))

    fieldnames, rows = load_csv(path)
    if not rows:
        raise SystemExit(f"No rows in {path}")

    cols = [c for c in WANTED if c in fieldnames]
    missing = [c for c in WANTED if c not in fieldnames]

    log(f"file: {path}", level="INFO")
    log(f"rows: {len(rows)} cols: {len(fieldnames)}", level="INFO")
    log(f"missing: {missing}", level="INFO")
    log("EXCERPT (head/tail):", level="INFO")
    print_excerpt(rows, cols, head=12, tail=12)
    log("DIAGNOSTICS:", level="INFO")
    diagnostics(rows)


if __name__ == "__main__":
    main()
