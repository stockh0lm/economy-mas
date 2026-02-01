#!/usr/bin/env python3
"""Legacy code detector.

Goal
----
Keep the codebase aligned with the Warengeld specification and a clean balance-sheet
vocabulary by preventing re-introduction of known legacy patterns.

This script is intentionally simple (no external deps). It scans the repo for patterns
that have previously been sources of semantic drift.

Usage
-----
    python scripts/legacy_scan.py
    python scripts/legacy_scan.py --cleanup
    python scripts/legacy_scan.py --cleanup --include-tests

Modes
-----
Normal mode:
- Enforces legacy-free code by flagging unauthorized legacy pattern usage
- Uses allowlists to permit legacy patterns in specific files for compatibility
- Returns exit code 1 if unauthorized legacy patterns are found

Cleanup mode (--cleanup):
- Shows ALL legacy patterns across the entire codebase (including currently allowed ones)
- Helps identify all legacy code that needs to be cleaned up
- Always returns exit code 0 (won't break CI)

Exit codes
----------
0 = OK (no issues in normal mode, or cleanup mode completed)
1 = legacy patterns found (normal mode only)
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


def _iter_python_files(root: Path, *, include_tests: bool = False) -> list[Path]:
    """Collect python files under `root` while skipping generated/irrelevant directories.

    IMPORTANT: The implementation must be robust when the repository directory name
    happens to match a skip marker (e.g. "wirtschaft"). We therefore filter based on
    *relative* path segments (not raw substring matching on absolute paths).
    """

    skip_dirs = {
        ".venv",
        ".nox",
        ".tox",
        "__pycache__",
        "output",
        "results",
        ".git",
        "scripts",
        "wirtschaftssimulation.egg-info",
    }
    if not include_tests:
        skip_dirs.add("tests")

    files: list[Path] = []
    for p in root.rglob("*.py"):
        try:
            rel_parts = p.relative_to(root).parts
        except Exception:
            # Fallback: should not happen, but never hide files silently.
            rel_parts = p.parts

        if any(part in skip_dirs for part in rel_parts):
            continue
        files.append(p)
    return files


def _scan_files(
    paths: list[Path],
    allowlists: dict[str, set[Path]],
    allow_fee_rate_files: set[Path],
    allow_legacy_bank_methods_files: set[Path],
    cleanup_mode: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []

    print_re = re.compile(r"\bprint\(")
    direct_sell_re = re.compile(r"def\s+sell_to_household\s*\(")
    balance_any_re = re.compile(r"\b\.balance\b")
    savings_attr_re = re.compile(r"\b\.savings\b")

    # M3 - Legacy-Bankpfade (entfernte/unerwünschte APIs)
    grant_credit_re = re.compile(r"\bgrant_credit\s*\(")
    calculate_fees_re = re.compile(r"\bcalculate_fees\s*\(")

    # M3 - check_inventories(current_step=None) war ein Legacy-Mode; die moderne
    # API ist keyword-only und erwartet current_step:int.
    legacy_check_inv_re = re.compile(r"\bcheck_inventories\s*\([^\n]*current_step\s*=\s*None")

    # M4 - Konfig-Konsistenz (fee_rate ist deprecated/entfernt)
    fee_rate_re = re.compile(r"\bfee_rate\b")

    allow_direct_sell = allowlists["direct_sell"]
    allow_balance_any = allowlists["balance_any"]
    allow_savings = allowlists["savings"]

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()

            # Skip docstrings/comments: we care about actual code re-introduction.
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Don't self-flag this tool. (It prints status lines by design.)
            if path.resolve() == Path(__file__).resolve():
                continue

            if print_re.search(line):
                findings.append(Finding(path, i, "print() detected (use logger.log)", stripped))

            if direct_sell_re.search(line) and path.resolve() not in allow_direct_sell:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Direct sell_to_household detected outside RetailerAgent/allowed stubs (bypasses Warengeld goods cycle)",
                        stripped,
                    )
                )

            if balance_any_re.search(line) and path.resolve() not in allow_balance_any:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Use of `.balance` detected; prefer `sight_balance`/explicit account fields",
                        stripped,
                    )
                )

            if savings_attr_re.search(line) and path.resolve() not in allow_savings:
                findings.append(
                    Finding(
                        path,
                        i,
                        "Use of `.savings` detected; prefer `local_savings` and SavingsBank accounts",
                        stripped,
                    )
                )

            # M3 - Legacy bank methods
            if grant_credit_re.search(line):
                is_allowed = path.resolve() in allow_legacy_bank_methods_files
                if cleanup_mode or not is_allowed:
                    message = "Legacy method `grant_credit` detected (M3 deprecated bank path)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

            if calculate_fees_re.search(line):
                is_allowed = path.resolve() in allow_legacy_bank_methods_files
                if cleanup_mode or not is_allowed:
                    message = "Legacy method `calculate_fees` detected (M3 deprecated bank path)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

            if legacy_check_inv_re.search(line):
                is_allowed = path.resolve() in allow_legacy_bank_methods_files
                if cleanup_mode or not is_allowed:
                    message = "Legacy call `check_inventories(..., current_step=None)` detected (M3 deprecated bank path)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

            # M4 - Deprecated Config key
            if fee_rate_re.search(line):
                is_allowed = path.resolve() in allow_fee_rate_files
                if cleanup_mode or not is_allowed:
                    message = "Deprecated config `fee_rate` detected (M4 - use charge_account_fees parameters instead)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

    return findings


def _scan_all_legacy_patterns(paths: list[Path]) -> list[Finding]:
    """Scan for ALL legacy patterns (ignoring allowlists) - for cleanup purposes."""
    findings: list[Finding] = []

    grant_credit_re = re.compile(r"\bgrant_credit\s*\(")
    calculate_fees_re = re.compile(r"\bcalculate_fees\s*\(")
    legacy_check_inv_re = re.compile(r"\bcheck_inventories\s*\([^\n]*current_step\s*=\s*None")
    fee_rate_re = re.compile(r"\bfee_rate\b")

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()

            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if path.resolve() == Path(__file__).resolve():
                continue

            if grant_credit_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy method `grant_credit` (M3)", stripped))
            if calculate_fees_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy method `calculate_fees` (M3)", stripped))
            if legacy_check_inv_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy call `check_inventories(..., current_step=None)` (M3)", stripped))
            if fee_rate_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Deprecated config `fee_rate` (M4)", stripped))

    return findings


def main(*, cleanup_mode: bool = False, include_tests: bool = False) -> int:
    agents_dir = REPO_ROOT / "agents"

    # Include top-level modules too; some legacy patterns have historically lived there.
    scan_roots = [agents_dir, REPO_ROOT]

    allow_direct_sell_files = {
        (REPO_ROOT / "company_agent.py").resolve(),
        (REPO_ROOT / "retailer_agent.py").resolve(),
        (agents_dir / "company_agent.py").resolve(),
        (agents_dir / "retailer_agent.py").resolve(),
    }

    allow_balance_any_files = {
        # Repo-root modules
        (REPO_ROOT / "bank.py").resolve(),
        (REPO_ROOT / "clearing_agent.py").resolve(),
        (REPO_ROOT / "savings_bank_agent.py").resolve(),
        (REPO_ROOT / "state_agent.py").resolve(),
        (REPO_ROOT / "environmental_agency.py").resolve(),
        (REPO_ROOT / "company_agent.py").resolve(),
        (REPO_ROOT / "household_agent.py").resolve(),
        (REPO_ROOT / "retailer_agent.py").resolve(),
        (REPO_ROOT / "economic_agent.py").resolve(),

        # agents/ package mirrors
        (agents_dir / "bank.py").resolve(),
        (agents_dir / "clearing_agent.py").resolve(),
        (agents_dir / "savings_bank_agent.py").resolve(),
        (agents_dir / "state_agent.py").resolve(),
        (agents_dir / "environmental_agency.py").resolve(),
        (agents_dir / "company_agent.py").resolve(),
        (agents_dir / "household_agent.py").resolve(),
        (agents_dir / "retailer_agent.py").resolve(),
    }

    allow_savings_files = {
        (REPO_ROOT / "household_agent.py").resolve(),
        (REPO_ROOT / "financial_manager.py").resolve(),
        (agents_dir / "household_agent.py").resolve(),
        (agents_dir / "financial_manager.py").resolve(),
    }

    allowlists = {
        "direct_sell": allow_direct_sell_files,
        "balance_any": allow_balance_any_files,
        "savings": allow_savings_files,
    }

    # M4 fee_rate: during migration this existed in a few compatibility shims.
    # After Milestone 1 the goal is to have ZERO occurrences in code.
    allow_fee_rate_files = {
        (REPO_ROOT / "main.py").resolve(),
    }

    # M3 legacy bank methods were previously allowed in the bank implementation.
    # After Milestone 1 they must be fully removed.
    allow_legacy_bank_methods_files: set[Path] = set()

    findings: list[Finding] = []
    seen: set[Path] = set()

    if cleanup_mode:
        print("CLEANUP MODE: Scanning for ALL legacy patterns (including allowed ones)...")
        for root in scan_roots:
            for p in _iter_python_files(root, include_tests=include_tests):
                if p.resolve() in seen:
                    continue
                seen.add(p.resolve())
                findings.extend(_scan_all_legacy_patterns([p]))

        if findings:
            print(f"CLEANUP: Found {len(findings)} legacy pattern instances:\n")
            findings_by_file: dict[Path, list[Finding]] = {}
            for f in findings:
                rel_path = f.path.relative_to(REPO_ROOT)
                findings_by_file.setdefault(rel_path, []).append(f)

            for file_path, file_findings in sorted(findings_by_file.items()):
                print(f"\n{file_path}:")
                for f in sorted(file_findings, key=lambda x: x.line_no):
                    print(f"  {f.line_no}: {f.message}")
                    print(f"    {f.line}")

            print(f"\nSummary: {len(findings)} total legacy pattern instances found across {len(findings_by_file)} files")
            return 0

        print("CLEANUP: No legacy patterns found")
        return 0

    # Normal mode (enforcement)
    for root in scan_roots:
        for p in _iter_python_files(root, include_tests=False):
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            findings.extend(_scan_files([p], allowlists, allow_fee_rate_files, allow_legacy_bank_methods_files, cleanup_mode=False))

    if findings:
        print("legacy_scan: FAIL\n")
        for f in findings:
            rel = f.path.relative_to(REPO_ROOT)
            print(f"{rel}:{f.line_no}: {f.message}\n    {f.line}\n")
        return 1

    print("legacy_scan: OK")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Legacy code detector for Warengeld simulation")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Enable cleanup mode to show ALL legacy patterns (including allowed ones) for systematic removal",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in the scan (only relevant in cleanup mode)",
    )

    args = parser.parse_args()
    raise SystemExit(main(cleanup_mode=args.cleanup, include_tests=args.include_tests))
