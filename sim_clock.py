"""Simulation clock / calendar utilities.

Global convention (used everywhere in this project):

- 1 simulation step == 1 day
- 30 days == 1 month
- 12 months == 1 year
- 1 year == 360 days

Monthly/quarterly/yearly processes must be triggered deterministically from the
(day_index) via this module (no ad-hoc modulo logic scattered across the code).
"""

from __future__ import annotations

from dataclasses import dataclass

from config import TimeConfig


@dataclass
class SimulationClock:
    """A small deterministic calendar.

    The clock is stateless aside from `day_index`. Use `set_day()` inside the
    simulation loop to bind it to the current step.
    """

    time: TimeConfig
    day_index: int = 0

    def set_day(self, day_index: int) -> None:
        if day_index < 0:
            raise ValueError("day_index must be >= 0")
        self.day_index = int(day_index)

    # --- Derived indices ---
    @property
    def month_index(self) -> int:
        """0-based month index since start."""
        return self.day_index // int(self.time.days_per_month)

    @property
    def year_index(self) -> int:
        """0-based year index since start."""
        return self.day_index // int(self.time.days_per_year)

    @property
    def year(self) -> int:
        return int(getattr(self.time, "start_year", 0)) + self.year_index

    # --- Period boundaries ---
    def is_month_end(self, day_index: int | None = None) -> bool:
        d = self.day_index if day_index is None else int(day_index)
        return (d + 1) % int(self.time.days_per_month) == 0

    def is_year_end(self, day_index: int | None = None) -> bool:
        d = self.day_index if day_index is None else int(day_index)
        return (d + 1) % int(self.time.days_per_year) == 0

    def is_quarter_end(self, day_index: int | None = None) -> bool:
        """Quarter end (every 90 days) based on the month grid."""
        d = self.day_index if day_index is None else int(day_index)
        if not self.is_month_end(d):
            return False
        month = (d // int(self.time.days_per_month)) % int(getattr(self.time, "months_per_year", 12))
        return month % 3 == 2

    def is_period_end(self, period_days: int, day_index: int | None = None) -> bool:
        """Generic period end helper."""
        if period_days <= 0:
            raise ValueError("period_days must be > 0")
        d = self.day_index if day_index is None else int(day_index)
        return (d + 1) % int(period_days) == 0

    # --- Rate conversion ---
    def per_day_to_per_step(self, amount_per_day: float) -> float:
        """Convert per-day amounts to per-step amounts.

        This is trivial today (1 step = 1 day), but keeping the API stable makes
        future model extensions safer.
        """

        return float(amount_per_day)
