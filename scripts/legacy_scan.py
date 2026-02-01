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
    python scripts/legacy_scan.py                    # Normal mode (enforcement)
    python scripts/legacy_scan.py --cleanup          # Cleanup mode (shows ALL legacy patterns)
    python scripts/legacy_scan.py --cleanup --include-tests  # Cleanup mode including tests

Modes
-----
Normal mode:
- Enforces legacy-free code by flagging unauthorized legacy pattern usage
- Uses allowlists to permit legacy patterns in specific files for compatibility
- Returns exit code 1 if unauthorized legacy patterns are found

Cleanup mode (--cleanup):
- Shows ALL legacy patterns across the entire codebase
- Includes patterns that are currently allowed for legacy compatibility
- Helps identify all legacy code that needs to be cleaned up
- Always returns exit code 0 (won't break CI)
- Output is organized by file for systematic cleanup

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


def _iter_python_files(root: Path, include_tests: bool = False) -> list[Path]:
    """Yield python files under root while skipping generated/irrelevant directories."""
    skip_markers = (
        ".venv/",
        ".nox/",
        ".tox/",
        "__pycache__/",
        "output/",
        "results/",
        ".git/",
        "scripts/",
        "wirtschaft/",
        "/wirtschaft/",
        "wirtschaftssimulation.egg-info/",
    )

    # Only skip tests/ if not explicitly including them
    if not include_tests:
        skip_markers = skip_markers + ("tests/",)

    files: list[Path] = []
    for p in root.rglob("*.py"):
        posix = p.as_posix()
        if any(marker in posix for marker in skip_markers):
            continue
        files.append(p)
    return files


def _scan_files(paths: list[Path], allowlists: dict[str, set[Path]], allow_fee_rate_files: set[Path], allow_legacy_bank_methods_files: set[Path], cleanup_mode: bool = False) -> list[Finding]:
    findings: list[Finding] = []

    print_re = re.compile(r"\bprint\(")
    direct_sell_re = re.compile(r"def\s+sell_to_household\s*\(")
    balance_any_re = re.compile(r"\b\.balance\b")
    savings_attr_re = re.compile(r"\b\.savings\b")

    # M3 - Legacy-Bankpfade Deprecation (these methods should not be used)
    grant_credit_re = re.compile(r"\bgrant_credit\s*\(")
    calculate_fees_re = re.compile(r"\bcalculate_fees\s*\(")
    check_inventories_re = re.compile(r"\bcheck_inventories\s*\(")

    # M4 - Konfig-Konsistenz (fee_rate is deprecated, should use charge_account_fees parameters)
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

            # M3 - Legacy-Bankpfade Deprecation
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

            if check_inventories_re.search(line):
                is_allowed = path.resolve() in allow_legacy_bank_methods_files
                if cleanup_mode or not is_allowed:
                    message = "Legacy method `check_inventories` detected (M3 deprecated bank path)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

            # M4 - Konfig-Konsistenz (fee_rate is deprecated)
            if fee_rate_re.search(line):
                is_allowed = path.resolve() in allow_fee_rate_files
                if cleanup_mode or not is_allowed:
                    message = "Deprecated config `fee_rate` detected (M4 - use charge_account_fees parameters instead)"
                    if is_allowed:
                        message += " [ALLOWED - legacy compatibility]"
                    findings.append(Finding(path, i, message, stripped))

    return findings

def _scan_all_legacy_patterns(paths: list[Path]) -> list[Finding]:
    """Scan for ALL legacy patterns including those in allowlists - for cleanup purposes."""
    findings: list[Finding] = []

    # M3 - Legacy-Bankpfade Deprecation patterns
    grant_credit_re = re.compile(r"\bgrant_credit\s*\(")
    calculate_fees_re = re.compile(r"\bcalculate_fees\s*\(")
    check_inventories_re = re.compile(r"\bcheck_inventories\s*\(")

    # M4 - Konfig-Konsistenz patterns
    fee_rate_re = re.compile(r"\bfee_rate\b")

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()

            # Skip docstrings/comments
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Don't self-flag this tool
            if path.resolve() == Path(__file__).resolve():
                continue

            # M3 Legacy Bank Methods
            if grant_credit_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy method `grant_credit` (M3)", stripped))
            if calculate_fees_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy method `calculate_fees` (M3)", stripped))
            if check_inventories_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Legacy method `check_inventories` (M3)", stripped))

            # M4 Deprecated Config
            if fee_rate_re.search(line):
                findings.append(Finding(path, i, "CLEANUP: Deprecated config `fee_rate` (M4)", stripped))

    return findings


def main(cleanup_mode: bool = False, include_tests: bool = False) -> int:
    agents_dir = REPO_ROOT / "agents"

    # Include top-level modules too; some legacy patterns have historically lived there.
    scan_roots = [agents_dir, REPO_ROOT]

    # IMPORTANT: tests/imports still exercise the repo-root modules (mirrors of agents/*).
    # Keep allowlists in sync with both locations until the duplication is removed.

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
        # Repo-root + agents package
        (REPO_ROOT / "household_agent.py").resolve(),  # defines alias
        (REPO_ROOT / "financial_manager.py").resolve(),
        (agents_dir / "household_agent.py").resolve(),
        (agents_dir / "financial_manager.py").resolve(),
    }

    allowlists = {
        "direct_sell": allow_direct_sell_files,
        "balance_any": allow_balance_any_files,
        "savings": allow_savings_files,
    }

    # M4 fee_rate is allowed in specific legacy test files and config files
    allow_fee_rate_files = {
        # Config files that define fee_rate for legacy compatibility
        (REPO_ROOT / "config.py").resolve(),
        (agents_dir / "config_cache.py").resolve(),

        # Test files that explicitly test legacy fee_rate behavior
        (REPO_ROOT / "tests" / "test_config_consistency_deprecation.py").resolve(),
        (REPO_ROOT / "tests" / "test_bank_config.py").resolve(),
        (REPO_ROOT / "tests" / "test_bank_processes.py").resolve(),
        (REPO_ROOT / "tests" / "test_config_models.py").resolve(),

        # Bank implementation that handles legacy fee_rate with deprecation warning
        (REPO_ROOT / "agents" / "bank.py").resolve(),
        (REPO_ROOT / "bank.py").resolve(),

        # Main entry point that handles legacy fee_rate config loading with deprecation warning
        (REPO_ROOT / "main.py").resolve(),
    }

    # M3 legacy bank methods are allowed in bank.py files (they are kept for legacy tests)
    allow_legacy_bank_methods_files = {
        (REPO_ROOT / "agents" / "bank.py").resolve(),
        (REPO_ROOT / "bank.py").resolve(),
    }

    # TODO: Add detection for legacy balance sheet names
    # - Find all uses of `.checking_account` and replace with `.sight_balance`
    # - Find all uses of `.balance` on Company/Producer and replace with `.sight_balance`
    # - This will help complete the balance sheet naming consolidation
    # - Pattern: checking_account_re = re.compile(r"\b\.checking_account\b")
    # - Pattern: company_balance_re = re.compile(r"\bcompany.*\.balance\b")

    findings: list[Finding] = []
    seen: set[Path] = set()

    if cleanup_mode:
        print("CLEANUP MODE: Scanning for ALL legacy patterns (including allowed ones)...")
        for root in scan_roots:
            for p in _iter_python_files(root, include_tests=True):
                # Avoid scanning the same file twice when scanning both agents_dir and REPO_ROOT
                if p.resolve() in seen:
                    continue
                seen.add(p.resolve())
                findings.extend(_scan_all_legacy_patterns([p]))

        if findings:
            print(f"CLEANUP: Found {len(findings)} legacy pattern instances:\n")
            # Group findings by file for better organization
            findings_by_file = {}
            for f in findings:
                rel_path = f.path.relative_to(REPO_ROOT)
                findings_by_file.setdefault(rel_path, []).append(f)

            for file_path, file_findings in sorted(findings_by_file.items()):
                print(f"\n{file_path}:")
                for f in sorted(file_findings, key=lambda x: x.line_no):
                    print(f"  {f.line_no}: {f.message}")
                    print(f"    {f.line}")

            print(f"\nSummary: {len(findings)} total legacy pattern instances found across {len(findings_by_file)} files")
            return 0  # Always return 0 in cleanup mode to avoid breaking CI

        print("CLEANUP: No legacy patterns found")
        return 0
    else:
        for root in scan_roots:
            for p in _iter_python_files(root):
                # Avoid scanning the same file twice when scanning both agents_dir and REPO_ROOT
                if p.resolve() in seen:
                    continue
                seen.add(p.resolve())
                findings.extend(_scan_files([p], allowlists, allow_fee_rate_files, allow_legacy_bank_methods_files, cleanup_mode))

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
