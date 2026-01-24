#!/usr/bin/env python3
"""Legacy code detector.

Goal
----
Keep the codebase aligned with the Warengeld specification and a clean balance-sheet
vocabulary by preventing re-introduction of known legacy patterns.

This script is intentionally simple (no external deps). It scans the repo for patterns
that have previously been sources of semantic drift, e.g.:
- "print(...)" in agents (side effects; bypasses logging)
- producer selling directly to households (bypassing retailer/Warengeld primitives)
- "EconomicAgent" dummy patterns

Usage
-----
    python scripts/legacy_scan.py

Exit codes
----------
0 = OK
1 = legacy patterns found
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Finding:
    path: Path
    line_no: int
    message: str
    line: str


def _iter_python_files(root: Path) -> list[Path]:
    """Yield python files under root while skipping generated/irrelevant directories."""
    skip_markers = (
        "/.venv/",
        "/__pycache__/",
        "/output/",
        "/results/",
        "/.git/",
        "/tests/",
    )
    files: list[Path] = []
    for p in root.rglob("*.py"):
        posix = p.as_posix()
        if any(marker in posix for marker in skip_markers):
            continue
        files.append(p)
    return files


def _scan_files(paths: list[Path], allowlists: dict[str, set[Path]]) -> list[Finding]:
    findings: list[Finding] = []

    print_re = re.compile(r"\bprint\(")
    direct_sell_re = re.compile(r"def\s+sell_to_household\s*\(")
    balance_any_re = re.compile(r"\b\.balance\b")
    savings_attr_re = re.compile(r"\b\.savings\b")

    allow_direct_sell = allowlists["direct_sell"]
    allow_balance_any = allowlists["balance_any"]
    allow_savings = allowlists["savings"]

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if print_re.search(line):
                findings.append(Finding(path, i, "print() detected (use logger.log)", line.strip()))

            if direct_sell_re.search(line) and path.resolve() not in allow_direct_sell:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Direct sell_to_household detected outside RetailerAgent/allowed stubs (bypasses Warengeld goods cycle)",
                        line.strip(),
                    )
                )

            if balance_any_re.search(line) and path.resolve() not in allow_balance_any:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Use of `.balance` detected; prefer `sight_balance`/explicit account fields",
                        line.strip(),
                    )
                )

            if savings_attr_re.search(line) and path.resolve() not in allow_savings:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Use of `.savings` detected; prefer `local_savings` and SavingsBank accounts",
                        line.strip(),
                    )
                )

    return findings


def main() -> int:
    agents_dir = REPO_ROOT / "agents"

    # Include top-level modules too; some legacy patterns have historically lived there.
    scan_roots = [agents_dir, REPO_ROOT]

    allow_direct_sell_files = {
        (agents_dir / "company_agent.py").resolve(),
        (agents_dir / "retailer_agent.py").resolve(),
    }

    allow_balance_any_files = {
        # Protocol-driven/transitional modules that may receive arbitrary BalanceSheet-ish agents
        (agents_dir / "bank.py").resolve(),
        (agents_dir / "clearing_agent.py").resolve(),
        (agents_dir / "savings_bank_agent.py").resolve(),
        (agents_dir / "state_agent.py").resolve(),
        (agents_dir / "environmental_agency.py").resolve(),

        # Transitional compatibility properties
        (agents_dir / "company_agent.py").resolve(),
        (agents_dir / "household_agent.py").resolve(),
        (agents_dir / "retailer_agent.py").resolve(),
    }

    allow_savings_files = {
        (agents_dir / "household_agent.py").resolve(),  # defines alias
    }

    allowlists = {
        "direct_sell": allow_direct_sell_files,
        "balance_any": allow_balance_any_files,
        "savings": allow_savings_files,
    }

    findings: list[Finding] = []
    seen: set[Path] = set()
    for root in scan_roots:
        for p in _iter_python_files(root):
            # Avoid scanning the same file twice when scanning both agents_dir and REPO_ROOT
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            findings.extend(_scan_files([p], allowlists))

    if findings:
        print("legacy_scan: FAIL\n")
        for f in findings:
            rel = f.path.relative_to(REPO_ROOT)
            print(f"{rel}:{f.line_no}: {f.message}\n    {f.line}\n")
        return 1

    print("legacy_scan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
