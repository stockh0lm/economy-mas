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

import yaml

from agents.bank import WarengeldBank
from agents.clearing_agent import ClearingAgent
from agents.company_agent import Company
from agents.environmental_agency import EnvironmentalAgency
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.retailer_agent import RetailerAgent
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State
from config import SimulationConfig
from logger import log, setup_logger
from sim_clock import SimulationClock


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
    return SimulationConfig()


# ---------------------------
# Agent creation
# ---------------------------


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
    for rid, bank in zip(region_ids, warengeld_banks):
        bank.region_id = rid
    for rid, sb in zip(region_ids, savings_banks):
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
    banks_by_region = {rid: bank for rid, bank in zip(region_ids, warengeld_banks)}
    savings_by_region = {rid: bank for rid, bank in zip(region_ids, savings_banks)}
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
    """M1 proxy = sum of sight balances."""

    total = 0.0
    for h in households:
        total += max(0.0, getattr(h, "sight_balance", h.checking_account))
    for c in companies:
        total += max(0.0, getattr(c, "sight_balance", getattr(c, "balance", 0.0)))
    for r in retailers:
        total += max(0.0, getattr(r, "sight_balance", 0.0))
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
    agents = initialize_agents(config)

    households: list[Household] = agents["households"]
    companies: list[Company] = agents["companies"]
    retailers: list[RetailerAgent] = agents["retailers"]

    state: State = agents["state"]
    warengeld_banks: list[WarengeldBank] = agents.get("warengeld_banks", [agents["warengeld_bank"]])
    savings_banks: list[SavingsBank] = agents.get("savings_banks", [agents["savings_bank"]])
    banks_by_region: dict[str, WarengeldBank] = agents.get(
        "banks_by_region", {"region_0": warengeld_banks[0]}
    )
    savings_by_region: dict[str, SavingsBank] = agents.get(
        "savings_by_region", {"region_0": savings_banks[0]}
    )
    clearing: ClearingAgent = agents["clearing_agent"]
    labor_market: LaborMarket = agents["labor_market"]
    environmental_agency: EnvironmentalAgency = agents["environmental_agency"]

    # Households must be known to the labor market for matching to work.
    for h in households:
        labor_market.register_worker(h)

    steps = int(config.simulation_steps)
    clock = SimulationClock(config.time)

    # Reproducibility in CI/tests should be explicit.
    # - If SIM_SEED is set, seed immediately.
    # - If SIM_SEED_FROM_CONFIG=1, also seed from config.population.seed when present.
    env_seed = os.getenv("SIM_SEED")
    if env_seed is not None and env_seed != "":
        random.seed(int(env_seed))
    elif os.getenv("SIM_SEED_FROM_CONFIG") == "1":
        seed = getattr(getattr(config, "time", None), "seed", None)
        if seed is None:
            seed = getattr(getattr(config, "population", None), "seed", None)
        if seed is not None:
            random.seed(int(seed))

    # Metrics
    from metrics import MetricsCollector

    collector = MetricsCollector(config=config)
    for h in households:
        collector.register_household(h)
    for c in companies:
        collector.register_company(c)
    for b in warengeld_banks:
        collector.register_bank(b)
    for sb in savings_banks:
        collector.register_bank(sb)
    # Retailer metrics are registered lazily inside the collector (if present).

    log(f"Starting simulation for {steps} steps...")

    # Minimal liveness/progress output for long runs.
    # Enabled by default; disable with SIM_PROGRESS=0.
    progress_enabled = os.getenv("SIM_PROGRESS", "1") not in {"0", "false", "False"}
    progress_use_ansi = progress_enabled and (os.getenv("NO_COLOR") is None)
    start_ts = time.time()
    last_progress_ts = start_ts
    progress_every_steps = max(1, steps // 200)  # ~0.5% increments (cap at 200 updates)
    progress_every_seconds = 2.0  # but at most once every 2 seconds

    # Helpers for lifecycle dynamics
    # Newborn IDs must be globally unique and should start at the initially configured
    # population size (not just len(households), which can differ depending on config paths).
    configured_initial = int(getattr(getattr(config, "population", None), "num_households", 0) or 0)
    next_household_idx = configured_initial if configured_initial > 0 else len(households)

    # Ensure we never reuse an existing suffix even if initial agents were created from explicit lists.
    try:
        existing_suffixes = [
            int(str(h.unique_id).replace(str(config.HOUSEHOLD_ID_PREFIX), ""))
            for h in households
            if str(h.unique_id).startswith(str(config.HOUSEHOLD_ID_PREFIX))
        ]
        if existing_suffixes:
            next_household_idx = max(next_household_idx, max(existing_suffixes) + 1)
    except Exception:
        # Safe fallback: keep computed next_household_idx.
        pass

    # Companies: keep numeric IDs for newly founded firms (Milestone 1);
    # Milestone 5 tightens this to *all* company births incl. splits.
    configured_companies = int(
        getattr(getattr(config, "population", None), "num_companies", 0) or 0
    )
    next_company_idx = configured_companies if configured_companies > 0 else len(companies)
    prefix = str(config.COMPANY_ID_PREFIX)
    numeric_suffixes: list[int] = []
    for c in companies:
        uid = str(getattr(c, "unique_id", ""))
        if uid.startswith(prefix):
            tail = uid[len(prefix) :]
            if tail.isdigit():
                numeric_suffixes.append(int(tail))
    if numeric_suffixes:
        next_company_idx = max(next_company_idx, max(numeric_suffixes) + 1)

    for step in range(steps):
        clock.day_index = step
        # Reset per-step retailer flow counters (used by metrics exports).
        for r in retailers:
            r.sales_total = 0.0
            r.purchases_total = 0.0
            r.write_downs_total = 0.0
            # Money-destruction flow counters (explicit for metrics)
            if hasattr(r, "repaid_total"):
                r.repaid_total = 0.0
            if hasattr(r, "inventory_write_down_extinguished_total"):
                r.inventory_write_down_extinguished_total = 0.0

        # Reset per-step company service flow counters.
        for c in companies:
            if hasattr(c, "service_sales_total"):
                c.service_sales_total = 0.0

        # 0) Demography pass: households can die (shrink) and households can split (grow).
        # We apply death before labor matching to avoid a full-step delay.
        alive_households: list[Household] = []
        deaths_this_step = 0
        births_this_step = 0
        company_births_this_step = 0
        company_deaths_this_step = 0
        companies_by_id = {c.unique_id: c for c in companies}
        days_per_year = int(getattr(config.time, "days_per_year", 360))
        base_annual = float(getattr(config.household, "mortality_base_annual", 0.0) or 0.0)
        senesce_annual = float(getattr(config.household, "mortality_senescence_annual", 0.0) or 0.0)
        shape = float(getattr(config.household, "mortality_shape", 3.0) or 3.0)

        for h in households:
            age_days = int(getattr(h, "age_days", 0) or 0)
            max_age_days = int(getattr(h, "max_age_days", getattr(h, "max_age", 0) or 0) or 0)

            age_years = age_days / float(days_per_year)
            max_age_years = max(1e-9, max_age_days / float(days_per_year))
            age_frac = min(1.0, max(0.0, age_years / max_age_years))

            annual_hazard = base_annual + senesce_annual * (age_frac**shape)
            daily_p = min(1.0, max(0.0, annual_hazard) / float(days_per_year))

            death_now = age_days >= max_age_days or (daily_p > 0 and random.random() < daily_p)

            if death_now:
                deaths_this_step += 1
                # Estate settlement & wealth transition (doc/issues.md Abschnitt 4)
                region_id = getattr(h, "region_id", "region_0")
                h_savings_bank = savings_by_region.get(region_id, savings_banks[0])
                heir_candidates = [
                    hh
                    for hh in households
                    if hh is not h and getattr(hh, "region_id", "region_0") == region_id
                ]
                younger = [
                    hh for hh in heir_candidates if int(getattr(hh, "age_days", 0) or 0) < age_days
                ]
                if younger:
                    heir_candidates = younger
                heir = random.choice(heir_candidates) if heir_candidates else None
                _settle_household_estate(
                    deceased=h,
                    heir=heir,
                    state=state,
                    savings_bank=h_savings_bank,
                    config=config,
                )

                labor_market.deregister_worker(h)
                # Also remove from its current employer (if any).
                employer_id = getattr(h, "employer_id", None)
                if employer_id:
                    employer = companies_by_id.get(str(employer_id))
                    if employer is not None and h in getattr(employer, "employees", []):
                        employer.employees = [e for e in employer.employees if e is not h]
                log(
                    f"death: household {h.unique_id} age_days={age_days} at step={step}",
                    level="INFO",
                )

                # Immediate replacement keeps the system from silently collapsing
                # and makes turnover observable even in short runs.
                replacement = Household(
                    unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{next_household_idx}",
                    config=config,
                )
                replacement.region_id = getattr(h, "region_id", "region_0")
                replacement.age_days = _sample_household_age_days(config, working_age_only=True)
                replacement.age = replacement.age_days // max(1, days_per_year)
                next_household_idx += 1
                collector.register_household(replacement)
                labor_market.register_worker(replacement)
                alive_households.append(replacement)
                births_this_step += 1
                log(
                    f"birth: household {replacement.unique_id} (replacement for {h.unique_id}) at step={step}",
                    level="INFO",
                )
                continue

            alive_households.append(h)

        # Ensure simulation doesn't end up with an empty labor force.
        if not alive_households:
            seed_household = Household(
                unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{next_household_idx}",
                config=config,
            )
            seed_household.region_id = "region_0"
            seed_household.age_days = _sample_household_age_days(config, working_age_only=True)
            seed_household.age = seed_household.age_days // max(1, days_per_year)
            labor_market.register_worker(seed_household)
            collector.register_household(seed_household)
            next_household_idx += 1
            alive_households.append(seed_household)

        households = alive_households
        agents["households"] = households

        # 0b) Company population dynamics: founding & mergers
        # Expliziter Bezug: doc/issues.md Abschnitt 4) → Wachstums- und Sterbe-Verhalten (Unternehmen).
        # Assumption: founding is transfer-funded by a household in the same region (no money creation).
        opportunity_by_region: dict[str, float] = {}
        for r in retailers:
            target = float(
                getattr(
                    r,
                    "target_inventory_value",
                    getattr(config.retailer, "target_inventory_value", 0.0),
                )
                or 0.0
            )
            current = float(getattr(r, "inventory_value", 0.0) or 0.0)
            shortage = max(0.0, target - current)
            rid = getattr(r, "region_id", "region_0")
            opportunity_by_region.setdefault(rid, 0.0)
            # accumulate shortage ratio numerator; denominator handled below
            opportunity_by_region[rid] += shortage

        # normalize by total target per region
        target_by_region: dict[str, float] = {}
        for r in retailers:
            rid = getattr(r, "region_id", "region_0")
            target_by_region[rid] = target_by_region.get(rid, 0.0) + float(
                getattr(r, "target_inventory_value", 0.0) or 0.0
            )

        for rid, shortage in list(opportunity_by_region.items()):
            denom = max(1e-9, float(target_by_region.get(rid, 0.0) or 0.0))
            opportunity_by_region[rid] = max(0.0, min(1.0, shortage / denom))

        # Founding
        found_base = float(getattr(config.company, "founding_base_annual", 0.0) or 0.0)
        found_sens = float(getattr(config.company, "founding_opportunity_sensitivity", 0.0) or 0.0)
        min_capital = float(getattr(config.company, "founding_min_capital", 0.0) or 0.0)
        share_capital = float(
            getattr(config.company, "founding_capital_share_of_founder_wealth", 0.0) or 0.0
        )

        for region_id in list(banks_by_region.keys()):
            opportunity = float(opportunity_by_region.get(region_id, 0.0) or 0.0)
            p_found = (found_base / float(max(1, days_per_year))) * (1.0 + found_sens * opportunity)
            if p_found > 0 and random.random() < min(1.0, p_found):
                sb = savings_by_region.get(region_id, savings_banks[0])
                region_households = [
                    h for h in households if getattr(h, "region_id", "region_0") == region_id
                ]
                if region_households:
                    # Choose the wealthiest founder to reduce random collapse.
                    def _wealth(hh: Household) -> float:
                        return (
                            float(getattr(hh, "sight_balance", 0.0) or 0.0)
                            + float(getattr(hh, "local_savings", 0.0) or 0.0)
                            + float(sb.savings_accounts.get(hh.unique_id, 0.0) or 0.0)
                        )

                    founder = max(region_households, key=_wealth)
                    founder_wealth = _wealth(founder)
                    buffer = float(getattr(config.household, "transaction_buffer", 0.0) or 0.0)
                    available = max(0.0, founder_wealth - buffer)
                    desired = max(min_capital, founder_wealth * share_capital)
                    invest = min(desired, available)

                    if invest >= min_capital and invest > 0:
                        remaining = invest
                        # Take from disposable sight
                        disposable_sight = max(0.0, float(founder.sight_balance) - buffer)
                        from_sight = min(disposable_sight, remaining)
                        if from_sight > 0:
                            founder.sight_balance -= from_sight
                            remaining -= from_sight

                        # Take from local savings
                        from_local = min(max(0.0, float(founder.local_savings)), remaining)
                        if from_local > 0:
                            founder.local_savings -= from_local
                            remaining -= from_local

                        # Withdraw from Sparkasse deposits as needed
                        if remaining > 0:
                            withdrawn = sb.withdraw_savings(founder, remaining)
                            if withdrawn > 0:
                                founder.sight_balance -= withdrawn
                                remaining -= withdrawn

                        transferred = invest - max(0.0, remaining)
                        if transferred >= min_capital and transferred > 0:
                            template = config.population.company_template
                            new_company = Company(
                                unique_id=f"{config.COMPANY_ID_PREFIX}{next_company_idx}",
                                production_capacity=template.production_capacity,
                                config=config,
                            )
                            new_company.region_id = region_id
                            new_company.sight_balance = float(transferred)
                            next_company_idx += 1
                            companies.append(new_company)
                            collector.register_company(new_company)
                            company_births_this_step += 1
                            log(
                                f"founding: company {new_company.unique_id} founded by {founder.unique_id} capital={transferred:.2f} at step={step}",
                                level="INFO",
                            )

        # Mergers (distressed -> absorbed)
        merge_base = float(getattr(config.company, "merger_rate_annual", 0.0) or 0.0)
        distress = float(getattr(config.company, "merger_distress_threshold", 0.0) or 0.0)
        min_acq = float(getattr(config.company, "merger_min_acquirer_balance", 0.0) or 0.0)
        synergy = float(getattr(config.company, "merger_capacity_synergy", 1.0) or 1.0)

        if merge_base > 0:
            p_merge = min(1.0, merge_base / float(max(1, days_per_year)))
            if random.random() < p_merge:
                # Select one region event per day for simplicity.
                regions = [rid for rid in banks_by_region.keys() if rid]
                if regions:
                    region_id = random.choice(regions)
                    region_companies = [
                        c for c in companies if getattr(c, "region_id", "region_0") == region_id
                    ]
                    targets = [
                        c
                        for c in region_companies
                        if float(getattr(c, "sight_balance", 0.0) or 0.0) < distress
                    ]
                    acquirers = [
                        c
                        for c in region_companies
                        if float(getattr(c, "sight_balance", 0.0) or 0.0) >= min_acq
                    ]

                    if targets and acquirers:
                        target = min(
                            targets, key=lambda c: float(getattr(c, "sight_balance", 0.0) or 0.0)
                        )
                        acquirer = max(
                            acquirers, key=lambda c: float(getattr(c, "sight_balance", 0.0) or 0.0)
                        )
                        if target is not acquirer:
                            # Transfer employees and assets
                            for e in list(getattr(target, "employees", [])):
                                if e not in acquirer.employees:
                                    acquirer.employees.append(e)
                                e.employer_id = acquirer.unique_id
                                e.employed = True

                            acquirer.sight_balance = float(
                                getattr(acquirer, "sight_balance", 0.0) or 0.0
                            ) + float(getattr(target, "sight_balance", 0.0) or 0.0)
                            acquirer.finished_goods_units = float(
                                getattr(acquirer, "finished_goods_units", 0.0) or 0.0
                            ) + float(getattr(target, "finished_goods_units", 0.0) or 0.0)
                            acquirer.production_capacity = (
                                float(getattr(acquirer, "production_capacity", 0.0) or 0.0)
                                + float(getattr(target, "production_capacity", 0.0) or 0.0)
                                * synergy
                            )

                            companies = [c for c in companies if c is not target]
                            company_deaths_this_step += 1
                            log(
                                f"merger: target={target.unique_id} absorbed_by={acquirer.unique_id} at step={step}",
                                level="INFO",
                            )

        # 1) Firms: post labor demand (but don't liquidate for missing staff yet)
        new_companies: list[Company] = []
        alive_companies: list[Company] = []
        for c in companies:
            # Post labor demand NOW so matching can happen this same step.
            c.adjust_employees(labor_market)
            alive_companies.append(c)

        companies = alive_companies
        agents["companies"] = companies

        # 2) Labor market matching (same-step)
        #
        # IMPORTANT: Pass the latest known price index into the labor market so
        # wage adjustment is consistent with the macro price dynamics tracked by
        # the MetricsCollector (doc/specs.md: real wages vs. price level).
        #
        # We use the previous step's price index because global metrics for the
        # current step are computed later in the pipeline.
        if step > 0:
            last_price_index = float(
                collector.latest_global_metrics.get("price_index", config.market.price_index_base)
            )
        else:
            last_price_index = float(config.market.price_index_base)
        labor_market.step(current_step=step, price_index=last_price_index)

        # 3) Firms: now run operations + lifecycle using the updated employee lists
        new_companies = []
        alive_companies = []
        for c in companies:
            # Run the remainder of company.step but skip the already-done parts.
            # We call the existing step for maintainability, but temporarily disable
            # the zero-staff grace triggering before matching.
            result = c.step(
                current_step=step,
                state=state,
                savings_bank=savings_by_region.get(c.region_id, savings_banks[0]),
            )

            if isinstance(result, Company):
                company_births_this_step += 1
                # Milestone 5 (doc/issues.md Abschnitt 5): enforce numeric ID
                # convention for *all* company births (including splits).
                result.unique_id = f"{config.COMPANY_ID_PREFIX}{next_company_idx}"
                next_company_idx += 1
                log(
                    f"growth: company split parent={c.unique_id} child={result.unique_id} at step={step}",
                    level="INFO",
                )
                new_companies.append(result)
                collector.register_company(result)
                alive_companies.append(c)
            elif result in ("DEAD", "LIQUIDATED"):
                company_deaths_this_step += 1
                log(
                    f"bankruptcy: company {c.unique_id} removed (status={result}) at step={step}",
                    level="WARNING",
                )
                continue
            else:
                alive_companies.append(c)

        if new_companies:
            alive_companies.extend(new_companies)

        companies = alive_companies
        agents["companies"] = companies

        # 4) Retail restocking (money creation point)
        # Milestone 1: avoid repeated getattr() in the hot loop.
        local_trade_bias = float(config.spatial.local_trade_bias)
        for r in retailers:
            bank = banks_by_region.get(r.region_id, warengeld_banks[0])
            # Preference for local producers, but allow cross-region trade.
            if random.random() < local_trade_bias:
                producer_pool = [c for c in companies if c.region_id == r.region_id] or companies
            else:
                producer_pool = companies
            r.restock_goods(companies=producer_pool, bank=bank, current_step=step)

        # 5) Households consume from retailers, then save via Sparkasse
        retailers_by_region: dict[str, list[RetailerAgent]] = {}
        for r in retailers:
            retailers_by_region.setdefault(r.region_id, []).append(r)

        alive_households = []
        newborns: list[Household] = []
        # Performance: process households per region to enable batch consumption.
        # Referenz: doc/issues.md Abschnitt 5 → "Performance-Optimierung nach Profiling-Analyse"
        households_by_region: dict[str, list[Household]] = {}
        for h in households:
            households_by_region.setdefault(h.region_id, []).append(h)

        for region_id, region_households in households_by_region.items():
            h_retailers = retailers_by_region.get(region_id, retailers)
            h_savings_bank = savings_by_region.get(region_id, savings_banks[0])

            # Attach for metrics: households report savings as local + bank deposits.
            for h in region_households:
                h._savings_bank_ref = h_savings_bank

            region_newborns = Household.batch_step(
                region_households,
                current_step=step,
                clock=clock,
                savings_bank=h_savings_bank,
                retailers=h_retailers,
            )

            alive_households.extend(region_households)

            for maybe_new in region_newborns:
                births_this_step += 1
                # Ensure unique IDs for newborns in the global simulation namespace.
                old_id = str(getattr(maybe_new, "unique_id", ""))
                new_id = f"{config.HOUSEHOLD_ID_PREFIX}{next_household_idx}"
                # Milestone 5 (doc/issues.md Abschnitt 5): renaming must migrate
                # any pre-created Sparkasse ledger entries (e.g. split-household
                # savings transfers) to avoid orphaned accounts.
                if h_savings_bank is not None and hasattr(h_savings_bank, "rename_agent_id"):
                    h_savings_bank.rename_agent_id(old_id, new_id)
                maybe_new.unique_id = new_id
                next_household_idx += 1
                collector.register_household(maybe_new)
                # New households must participate in labor matching.
                maybe_new.employed = False
                maybe_new.current_wage = None
                labor_market.register_worker(maybe_new)
                newborns.append(maybe_new)
                log(
                    f"birth: household {maybe_new.unique_id} parent={old_id} at step={step}",
                    level="INFO",
                )

        if newborns:
            alive_households.extend(newborns)

        households = alive_households
        agents["households"] = households

        # 6) Retail settlement (repay CC -> money extinguishing; write-downs)
        for r in retailers:
            bank = banks_by_region.get(r.region_id, warengeld_banks[0])
            r.settle_accounts(bank=bank, current_step=step)

        # Update rolling COGS history for cc_limit policy (must happen before month-end recomputation).
        for r in retailers:
            if hasattr(r, "push_cogs_history"):
                r.push_cogs_history(window_days=int(config.bank.cc_limit_rolling_window_days))

        # 7) Monthly policies
        if clock.is_month_end(step):
            # Bank account fees (no interest) ... by region.
            for rid, bank in banks_by_region.items():
                region_retailers = [r for r in retailers if r.region_id == rid]
                bank.recompute_cc_limits(region_retailers, current_step=step)
                bank_accounts: list[Any] = [a for a in households if a.region_id == rid]
                bank_accounts += [a for a in companies if a.region_id == rid]
                bank_accounts += [a for a in retailers if a.region_id == rid]
                bank.charge_account_fees(bank_accounts)

            # State taxes and budgets
            state.step([*companies, *retailers])
            # Spend state budgets back into the economy to keep circulation alive.
            state.spend_budgets(households, companies, retailers)

            # Sight factor decay (excess sight balances)
            clearing.apply_sight_decay([*households, *companies, *retailers, state])

            # Savings bank bookkeeping
            for region_id, sb in savings_by_region.items():
                region_companies = [
                    c
                    for c in companies
                    if str(getattr(c, "region_id", "region_0")) == str(region_id)
                ]
                sb.step(current_step=step, companies=region_companies)

        # 8) Periodic clearing audits / reserve adjustments
        if clock.is_period_end(int(config.clearing.audit_interval), step):
            companies_by_id = {c.unique_id: c for c in companies}
            for bank in warengeld_banks:
                local_retailers = [
                    r for r in retailers if r.region_id == getattr(bank, "region_id", "region_0")
                ]
                # Bank IDs are suffixed with region_id; use string match.
                if not local_retailers:
                    # fallback: audit all
                    local_retailers = retailers
                clearing.audit_bank(
                    bank=bank,
                    retailers=local_retailers,
                    companies_by_id=companies_by_id,
                    current_step=step,
                )
                clearing.enforce_reserve_bounds(bank=bank)

        # 9) Environment (optional) - run monthly to match the global calendar.
        if clock.is_month_end(step):
            environmental_agency.step(
                current_step=step, agents=[*companies, *retailers], state=state
            )

        # Collect metrics
        collector.collect_household_metrics(households, step)
        collector.collect_company_metrics(companies, step)
        collector.collect_retailer_metrics(retailers, step)
        collector.collect_bank_metrics(warengeld_banks, step)
        collector.collect_bank_metrics(savings_banks, step)
        collector.collect_state_metrics("state", state, households, companies, step)
        collector.collect_market_metrics(labor_market, step)
        collector.calculate_global_metrics(step)

        # Inject live counts + lifecycle events into macro metrics.
        if step in collector.global_metrics:
            collector.global_metrics[step].update(
                {
                    "total_households": len(households),
                    "total_companies": len(companies),
                    "total_retailers": len(retailers),
                    "deaths": deaths_this_step,
                    "births": births_this_step,
                    "company_births": company_births_this_step,
                    "company_deaths": company_deaths_this_step,
                }
            )

        # Minimal progress update (single line, overwritten).
        if progress_enabled:
            is_last = (step + 1) == steps
            now = time.time()
            if is_last or (
                (step + 1) % progress_every_steps == 0
                and (now - last_progress_ts) >= progress_every_seconds
            ):
                elapsed = now - start_ts
                done = step + 1
                rate = done / elapsed if elapsed > 0 else 0.0
                remaining = (steps - done) / rate if rate > 0 else float("nan")
                pct = (done / steps * 100.0) if steps > 0 else 100.0
                bar = _progress_bar(done, steps, width=22)

                m1 = _m1_proxy(households, companies, retailers, state)
                status = (
                    f"{bar} {pct:6.2f}%  step {done}/{steps}  "
                    f"HH {len(households):5d}  CO {len(companies):5d}  "
                    f"M1 {_format_compact_number(m1):>8}  "
                    f"elapsed {_format_duration(elapsed)}  eta {_format_duration(remaining)}"
                )

                color = _progress_color(pct, progress_use_ansi)
                status = _ansi(status, color, progress_use_ansi)

                # Carriage return to overwrite the previous status line.
                # Flush immediately so it stays live even when stdout is buffered.
                sys.stdout.write("\r" + status)
                sys.stdout.flush()

                # Ensure final state ends with a newline.
                if is_last:
                    sys.stdout.write("\n")
                    sys.stdout.flush()

                last_progress_ts = now

        if step % max(1, steps // 10) == 0:
            m1 = _m1_proxy(households, companies, retailers, state)
            total_cc = sum(b.total_cc_exposure for b in warengeld_banks)
            log(f"Step {step}: M1 proxy={m1:.2f}, CC exposure={total_cc:.2f}")

    log("Simulation finished.")
    collector.export_metrics()
    # Expose for validation/analysis scripts.
    agents["metrics_collector"] = collector
    return agents


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
