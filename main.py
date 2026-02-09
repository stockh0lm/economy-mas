"""Entry point and orchestration for the Warengeld simulation.

This file intentionally stays light: it wires agent objects together and
executes a time-step scheduler.

Key spec alignment:
- **Money creation** happens only when retailers finance *goods purchases* via
  an interest-free Kontokorrent at the WarengeldBank.
- **Money extinguishing** happens when retailers repay Kontokorrent from sales
  revenues.
- The SavingsBank (Sparkasse) intermediates savings and loans without creating
  money.
- The ClearingAgent audits banks and applies reserve requirements and value
  corrections.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from config import SimulationConfig
from logger import log, setup_logger
from simulation.engine import SimulationEngine


def _format_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # NaN guard
        return "?"
    seconds_int = int(seconds)
    mins, secs = divmod(seconds_int, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours:d}h{mins:02d}m{secs:02d}s"
    if mins:
        return f"{mins:d}m{secs:02d}s"
    return f"{secs:d}s"


def _progress_bar(done: int, total: int, width: int = 30) -> str:
    if total <= 0:
        return "[" + ("?" * width) + "]"
    ratio = max(0.0, min(1.0, done / total))
    filled = int(round(ratio * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _format_compact_number(value: float) -> str:
    """Format numbers compactly for status lines (keeps terminal output short)."""

    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs_val >= 1_000:
        return f"{value / 1_000:.2f}k"
    return f"{value:.2f}"


def _ansi(text: str, code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def _progress_color(pct: float, enabled: bool) -> str:
    if not enabled:
        return ""
    # red -> yellow -> green
    if pct < 33.3:
        return "31"  # red
    if pct < 66.6:
        return "33"  # yellow
    return "32"  # green


# ---------------------------
# Config loading
# ---------------------------


def load_config(config_path: str | Path) -> SimulationConfig:
    """Load YAML config into the pydantic model."""

    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

    return SimulationConfig(**(data or {}))


def _resolve_config_from_args_or_env() -> SimulationConfig:
    """Resolve config via CLI (--config) or SIM_CONFIG env var.

    Falls back to ./config.yaml (if present) and then to an empty/default config.
    """

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=str, default=None)
    args, _ = parser.parse_known_args()

    if args.config:
        return load_config(args.config)

    env_path = os.getenv("SIM_CONFIG")
    if env_path:
        return load_config(env_path)

    if Path("config.yaml").exists():
        return load_config("config.yaml")

    # default: empty config (model defaults)
    return SimulationConfig()  # type: ignore[call-arg]


# ---------------------------
# Agent creation (kept for backwards compatibility)
# ---------------------------

from agents.bank import WarengeldBank
from agents.clearing_agent import ClearingAgent
from agents.company_agent import Company
from agents.environmental_agency import EnvironmentalAgency
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.retailer_agent import RetailerAgent
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State


def create_households(config: SimulationConfig) -> list[Household]:
    """Create households with a realistic initial age distribution.

    Notes:
    - Primary truth: doc/specs.md (macro contract). Demography details are
      driven by doc/issues.md Abschnitt 4) (growth & death behaviour).
    - Age seeding uses a deterministic RNG derived from config.time.seed or
      config.population.seed to keep CI stable.
    """

    import random

    # Deterministic local RNG (do NOT mutate global random state here).
    seed = getattr(getattr(config, "time", None), "seed", None)
    if seed is None:
        seed = getattr(getattr(config, "population", None), "seed", None)
    rng = random.Random(int(seed) if seed is not None else 0)

    days_per_year = int(getattr(getattr(config, "time", None), "days_per_year", 360) or 360)

    def _seed_age(h: Household) -> None:
        min_y = int(getattr(config.household, "initial_age_min_years", 0))
        mode_y = int(getattr(config.household, "initial_age_mode_years", 35))
        max_y = int(
            getattr(config.household, "initial_age_max_years", int(config.household.max_age))
        )
        max_y = max(min_y, min(max_y, int(config.household.max_age)))
        mode_y = max(min_y, min(mode_y, max_y))
        age_years = float(rng.triangular(min_y, max_y, mode_y))
        h.age_days = int(age_years * days_per_year)

    if config.population.num_households is not None:
        count = int(config.population.num_households)
        template = config.population.household_template
        households = [
            Household(
                unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{i}", income=template.income, config=config
            )
            for i in range(count)
        ]
        for h in households:
            _seed_age(h)
        return households

    # fall back: explicit list
    households: list[Household] = []
    for i, h in enumerate(config.INITIAL_HOUSEHOLDS):
        hh = Household(unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{i}", income=h.income, config=config)
        _seed_age(hh)
        households.append(hh)
    return households


def create_companies(config: SimulationConfig) -> list[Company]:
    if config.population.num_companies is not None:
        count = int(config.population.num_companies)
        template = config.population.company_template
        return [
            Company(
                unique_id=f"{config.COMPANY_ID_PREFIX}{i}",
                production_capacity=template.production_capacity,
                config=config,
            )
            for i in range(count)
        ]

    companies: list[Company] = []
    for i, c in enumerate(config.INITIAL_COMPANIES):
        companies.append(
            Company(
                unique_id=f"{config.COMPANY_ID_PREFIX}{i}",
                production_capacity=c.production_capacity,
                config=config,
            )
        )
    return companies


def create_retailers(config: SimulationConfig) -> list[RetailerAgent]:
    # explicit list wins if present and population not specified
    if config.population.num_retailers is not None:
        count = int(config.population.num_retailers)
        template = config.population.retailer_template
        return [
            RetailerAgent(
                unique_id=f"{config.RETAILER_ID_PREFIX}{i}",
                config=config,
                cc_limit=getattr(template, "initial_cc_limit", config.retailer.initial_cc_limit),
                target_inventory_value=getattr(
                    template, "target_inventory_value", config.retailer.target_inventory_value
                ),
            )
            for i in range(count)
        ]

    retailers: list[RetailerAgent] = []
    for i, r in enumerate(getattr(config, "INITIAL_RETAILERS", [])):
        retailers.append(
            RetailerAgent(
                unique_id=f"{config.RETAILER_ID_PREFIX}{i}",
                config=config,
                cc_limit=getattr(r, "initial_cc_limit", config.retailer.initial_cc_limit),
                target_inventory_value=getattr(
                    r, "target_inventory_value", config.retailer.target_inventory_value
                ),
            )
        )

    if retailers:
        return retailers

    # fallback heuristic: a few retailers per regionless economy
    default_count = max(1, len(config.INITIAL_COMPANIES) // 2)
    return [
        RetailerAgent(
            unique_id=f"{config.RETAILER_ID_PREFIX}{i}",
            config=config,
            cc_limit=config.retailer.initial_cc_limit,
            target_inventory_value=config.retailer.target_inventory_value,
        )
        for i in range(default_count)
    ]


@dataclass
class SimulationAgents:
    households: list[Household]
    companies: list[Company]
    retailers: list[RetailerAgent]
    state: State
    warengeld_bank: WarengeldBank
    savings_bank: SavingsBank
    clearing: ClearingAgent
    labor_market: LaborMarket
    environmental_agency: EnvironmentalAgency


def initialize_agents(config: SimulationConfig) -> dict[str, Any]:
    """Create agent instances.

    Kept for backwards compatibility with unit tests.
    """

    state = State(unique_id=str(config.STATE_ID), config=config)

    # Spatial granularity: create one house bank (+ savings bank) per region.
    num_regions = int(getattr(config.spatial, "num_regions", 1))
    region_ids = [f"region_{i}" for i in range(num_regions)]

    warengeld_banks = [
        WarengeldBank(unique_id=f"warengeld_bank_{rid}", config=config) for rid in region_ids
    ]
    savings_banks = [
        SavingsBank(unique_id=f"savings_bank_{rid}", config=config) for rid in region_ids
    ]
    for rid, bank in zip(region_ids, warengeld_banks, strict=False):
        bank.region_id = rid
    for rid, sb in zip(region_ids, savings_banks, strict=False):
        sb.region_id = rid
    clearing = ClearingAgent(unique_id=str(config.CLEARING_AGENT_ID), config=config)
    labor_market = LaborMarket(unique_id=str(config.LABOR_MARKET_ID), config=config)
    environmental_agency = EnvironmentalAgency(unique_id="environmental_agency", config=config)

    households = create_households(config)
    companies = create_companies(config)
    retailers = create_retailers(config)

    # Assign agents to regions (round-robin by id to keep deterministic seeds).
    for idx, h in enumerate(households):
        h.region_id = region_ids[idx % num_regions]
    for idx, c in enumerate(companies):
        c.region_id = region_ids[idx % num_regions]
    for idx, r in enumerate(retailers):
        r.region_id = region_ids[idx % num_regions]

    # Attach labor market to state
    state.labor_market = labor_market

    # Register retailer Kontokorrent lines at their regional banks
    banks_by_region = {rid: bank for rid, bank in zip(region_ids, warengeld_banks, strict=False)}
    savings_by_region = {rid: bank for rid, bank in zip(region_ids, savings_banks, strict=False)}
    for r in retailers:
        bank = banks_by_region.get(r.region_id, warengeld_banks[0])
        bank.register_retailer(r, cc_limit=r.cc_limit)

    # Register banks with clearing (reserve tracking)
    for bank in warengeld_banks:
        clearing.register_bank(bank)

    return {
        "households": households,
        "companies": companies,
        "retailers": retailers,
        "state": state,
        # Legacy keys (single-region code/tests)
        "warengeld_bank": warengeld_banks[0],
        "savings_bank": savings_banks[0],
        # Multi-region access
        "warengeld_banks": warengeld_banks,
        "savings_banks": savings_banks,
        "banks_by_region": banks_by_region,
        "savings_by_region": savings_by_region,
        "clearing_agent": clearing,
        "labor_market": labor_market,
        "environmental_agency": environmental_agency,
    }


# ---------------------------
# Simulation loop
# ---------------------------


def _m1_proxy(
    households: list[Household],
    companies: list[Company],
    retailers: list[RetailerAgent],
    state: State,
) -> float:
    """M1 proxy = sum of sight balances + outstanding Kontokorrent credit.

    In the Warengeld system, money is created when retailers draw on their
    Kontokorrent lines to purchase goods. This money exists in the system
    until it's extinguished when retailers repay from sales revenue.
    Therefore, the M1 proxy must include both:
    1. Sight balances (cash holdings)
    2. Outstanding Kontokorrent credit (negative CC balances)
    """

    total = 0.0
    for h in households:
        total += max(0.0, getattr(h, "sight_balance", h.checking_account))
    for c in companies:
        total += max(0.0, getattr(c, "sight_balance", getattr(c, "balance", 0.0)))
    for r in retailers:
        total += max(0.0, getattr(r, "sight_balance", 0.0))
        # Add outstanding Kontokorrent credit (money created but not yet extinguished)
        cc_balance = getattr(r, "cc_balance", 0.0)
        if cc_balance < 0:
            total += abs(cc_balance)
    total += max(0.0, getattr(state, "sight_balance", 0.0))
    return total


def _sample_household_age_days(config: SimulationConfig, *, working_age_only: bool = False) -> int:
    """Sample an initial age (in days) for newly created households.

    Used for:
    - initial population seeding (create_households)
    - turnover replacements after deaths

    The distribution is intentionally simple (triangular) and configurable via
    HouseholdConfig.initial_age_* fields.
    """

    days_per_year = int(getattr(getattr(config, "time", None), "days_per_year", 360) or 360)
    cfg = config.household

    min_y = int(getattr(cfg, "initial_age_min_years", 0))
    mode_y = int(getattr(cfg, "initial_age_mode_years", 35))
    max_y = int(getattr(cfg, "initial_age_max_years", int(getattr(cfg, "max_age", 70))))
    max_y = max(min_y, min(max_y, int(getattr(cfg, "max_age", max_y))))
    mode_y = max(min_y, min(mode_y, max_y))

    if working_age_only:
        min_y = max(min_y, int(getattr(cfg, "fertility_age_min", 18)))
        mode_y = max(min_y, mode_y)

    age_years = float(random.triangular(min_y, max_y, mode_y))
    return int(age_years * days_per_year)


def _settle_household_estate(
    *,
    deceased: Household,
    heir: Household | None,
    state: State,
    savings_bank: SavingsBank,
    config: SimulationConfig,
) -> None:
    """Settle debts and transfer remaining wealth on household death.

    Expliziter Bezug: doc/issues.md Abschnitt 4) → "Einfaches Wachstums- und
    Sterbe-Verhalten" (Generationenwechsel / Vermögensübergang).

    Rules (minimal but Warengeld-consistent):
    - Outstanding Sparkasse loan is repaid from estate if possible (sight, then
      local savings, then SavingsBank deposits).
    - Remaining estate is transferred to heir (preferred) or state.
    - No money creation: only transfers and internal netting.
    """

    did = str(getattr(deceased, "unique_id", ""))
    if not did:
        return

    # 1) Gather estate
    estate_sight = float(
        getattr(deceased, "sight_balance", getattr(deceased, "checking_account", 0.0)) or 0.0
    )
    estate_local = float(getattr(deceased, "local_savings", 0.0) or 0.0)
    estate_deposit = float(savings_bank.savings_accounts.get(did, 0.0) or 0.0)

    # 2) Settle Sparkasse loan against the estate
    outstanding = float(savings_bank.active_loans.get(did, 0.0) or 0.0)
    if outstanding > 0:
        # Repay from sight (cash returns to bank)
        pay = min(outstanding, max(0.0, estate_sight))
        if pay > 0:
            estate_sight -= pay
            outstanding -= pay
            # Note: available_funds should not be increased here as this is just netting
            # The money is moving from deceased to bank, but it's already in the system

        # Repay from local savings (cash returns to bank)
        pay = min(outstanding, max(0.0, estate_local))
        if pay > 0:
            estate_local -= pay
            outstanding -= pay
            # Note: available_funds should not be increased here as this is just netting
            # The money is moving from deceased to bank, but it's already in the system

        # Repay by netting deposits (no cash movement, just balance sheet netting)
        pay = min(outstanding, max(0.0, estate_deposit))
        if pay > 0:
            estate_deposit -= pay
            outstanding -= pay

        # Update loan ledger
        if outstanding <= 0:
            savings_bank.active_loans.pop(did, None)
        else:
            savings_bank.active_loans[did] = outstanding

    # 3) Any remaining outstanding loan is written off (risk reserve, then liquidity)
    remaining_loan = float(savings_bank.active_loans.get(did, 0.0) or 0.0)
    if remaining_loan > 0:
        reserve_cover = min(
            remaining_loan, float(getattr(savings_bank, "risk_reserve", 0.0) or 0.0)
        )
        if reserve_cover > 0:
            savings_bank.risk_reserve = float(savings_bank.risk_reserve) - reserve_cover
            remaining_loan -= reserve_cover

        if remaining_loan > 0:
            # Reduce liquidity (bank absorbs loss)
            absorb = min(
                remaining_loan, float(getattr(savings_bank, "available_funds", 0.0) or 0.0)
            )
            savings_bank.available_funds = float(savings_bank.available_funds) - absorb
            remaining_loan -= absorb

        savings_bank.active_loans.pop(did, None)

    # 4) Transfer remaining estate
    share = float(getattr(config.household, "inheritance_share_on_death", 1.0) or 1.0)
    share = max(0.0, min(1.0, share))
    receiver: Any = heir if heir is not None else state

    # Sight + local savings transfer into receiver sight.
    if estate_sight > 0:
        if receiver is state:
            # For state, we need to use tax_revenue to handle sub-budgets properly
            state.tax_revenue += estate_sight * share
            if share < 1.0:
                state.tax_revenue += estate_sight * (1.0 - share)
        else:
            receiver.sight_balance = (
                float(getattr(receiver, "sight_balance", 0.0)) + estate_sight * share
            )
            if share < 1.0:
                state.tax_revenue += estate_sight * (1.0 - share)

    if estate_local > 0:
        if receiver is state:
            # For state, we need to use tax_revenue to handle sub-budgets properly
            state.tax_revenue += estate_local * share
            if share < 1.0:
                state.tax_revenue += estate_local * (1.0 - share)
        else:
            receiver.sight_balance = (
                float(getattr(receiver, "sight_balance", 0.0)) + estate_local * share
            )
            if share < 1.0:
                state.tax_revenue += estate_local * (1.0 - share)

    # Deposits: move the savings account liability from deceased to receiver.
    if estate_deposit > 0:
        rid = str(getattr(receiver, "unique_id", "state"))
        savings_bank.savings_accounts[rid] = (
            float(savings_bank.savings_accounts.get(rid, 0.0)) + estate_deposit * share
        )
        if share < 1.0:
            # Remaining share: withdraw to state sight for simplicity
            savings_bank.savings_accounts["state"] = float(
                savings_bank.savings_accounts.get("state", 0.0)
            ) + estate_deposit * (1.0 - share)

    # Remove deceased deposit entry.
    savings_bank.savings_accounts.pop(did, None)

    # 5) Zero the deceased balances (should not matter after removal, but avoids reuse)
    if hasattr(deceased, "sight_balance"):
        deceased.sight_balance = 0.0
    if hasattr(deceased, "local_savings"):
        deceased.local_savings = 0.0


def run_simulation(config: SimulationConfig) -> dict[str, Any]:
    """Run the simulation with the given configuration.

    This function delegates to SimulationEngine.run() to execute the simulation.
    The behavior is preserved exactly as before, with the simulation loop logic
    now encapsulated in the SimulationEngine class.
    """
    engine = SimulationEngine(config)
    return engine.run()


# ---------------------------
# CLI
# ---------------------------


def main() -> None:
    cfg = _resolve_config_from_args_or_env()
    # Ensure logging is configured before any agents emit logs.
    setup_logger(
        level=cfg.logging_level,
        log_file=cfg.log_file,
        log_format=cfg.log_format,
        file_mode="w",
        config=cfg,
    )
    run_simulation(cfg)


if __name__ == "__main__":
    main()
