"""cProfile helper for Milestone 2 (Household performance).

Referenz: doc/issues.md Abschnitt 5 → "Performance-Optimierung nach Profiling-Analyse".

Run:
    python scripts/profile_household_m2.py

The output is intended to be copied into `doc/profile_household_m2.txt`.
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys

# Ensure repo root is on sys.path when executed as a plain script.
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import SimulationConfig
from sim_clock import SimulationClock


def profile_household_step(n_households: int = 120, n_steps: int = 360) -> str:
    cfg = SimulationConfig()
    sb = SavingsBank(unique_id="sb", config=cfg)
    clock = SimulationClock(cfg.time)

    households: list[Household] = []
    for i in range(n_households):
        h = Household(unique_id=f"h{i}", config=cfg, income=cfg.household.base_income)
        h.sight_balance = 1_000.0
        households.append(h)

    prof = cProfile.Profile()
    prof.enable()
    for step in range(n_steps):
        month_end = clock.is_month_end(step)
        for h in households:
            h.step(
                current_step=step,
                clock=clock,
                savings_bank=sb,
                retailers=[],
                is_month_end=month_end,
            )
    prof.disable()

    buf = io.StringIO()
    stats = pstats.Stats(prof, stream=buf)
    stats.sort_stats("cumtime").print_stats(25)
    return buf.getvalue()


if __name__ == "__main__":
    print(profile_household_step())
