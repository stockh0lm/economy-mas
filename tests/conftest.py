"""conftest.py - Pytest configuration and fixtures.

Resets class-level mutable state between test runs to ensure test isolation.
"""

import sys
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PROJECT_ROOT / "agents"

for path in (PROJECT_ROOT, AGENTS_DIR):
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def pytest_runtest_setup(item):
    """Reset class-level mutable state before each test."""
    company_module = sys.modules.get("agents.company_agent")
    if company_module is not None:
        company_module.Company._lineage_counters.clear()

    household_module = sys.modules.get("agents.household_agent")
    if household_module is not None:
        household_module._DEFAULT_NP_RNG = None


def pytest_runtest_setup(item):
    """Reset class-level mutable state before each test.

    Ensures test isolation by clearing any class-level mutable dictionaries
    that might have been modified by previous tests.
    """
    # Reset Company._lineage_counters to prevent pollution from test_m5
    # which forces company splits and modifies this global counter.
    import importlib

    company_module = sys.modules.get("agents.company_agent")
    if company_module is not None:
        company_module.Company._lineage_counters.clear()
    # Also initialize Houseoloading counters if they exist
    from agents.company_agent import Company

    # Force reset even if empty
    Company._lineage_counters = {}

    # Reset household agent's numpy RNG which is a cached global
    household_module = sys.modules.get("agents.household_agent")
    if household_module is not None:
        household_module._DEFAULT_NP_RNG = None
