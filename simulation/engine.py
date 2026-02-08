from __future__ import annotations

import os
import random
import time
import sys
from dataclasses import dataclass
from typing import Any

import numpy as np

from config import SimulationConfig
from agents.bank import WarengeldBank
from agents.clearing_agent import ClearingAgent
from agents.company_agent import Company
from agents.environmental_agency import EnvironmentalAgency
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.retailer_agent import RetailerAgent
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State
from agents.config_cache import GlobalConfigCache
import agents.household_agent as household_module
import agents.household.consumption as consumption_module
from logger import log
from sim_clock import SimulationClock
from metrics import MetricsCollector


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


def _m1_proxy(
    households: list[Household],
    companies: list[Company],
    retailers: list[RetailerAgent],
    state: State,
) -> float:
    """M1 proxy = sum of sight balances + outstanding Kontokorrent credit."""
    total = 0.0
    for h in households:
        total += max(0.0, getattr(h, "sight_balance", getattr(h, "checking_account", 0.0)))
    for c in companies:
        total += max(0.0, getattr(c, "sight_balance", getattr(c, "balance", 0.0)))
    for r in retailers:
        total += max(0.0, getattr(r, "sight_balance", 0.0))
        cc_balance = getattr(r, "cc_balance", 0.0)
        if cc_balance < 0:
            total += abs(cc_balance)
    total += max(0.0, getattr(state, "sight_balance", 0.0))
    return total


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


def _sample_household_age_days(
    config: SimulationConfig, *, working_age_only: bool = False, rng: Any = random
) -> int:
    """Sample an initial age (in days) for newly created households."""

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

    if hasattr(rng, "triangular") and not isinstance(rng, type(random)):
        # numpy.random.Generator.triangular(left, mode, right)
        age_years = float(rng.triangular(min_y, mode_y, max_y))
    else:
        # random.triangular(low, high, mode)
        age_years = float(rng.triangular(min_y, max_y, mode_y))
    return int(age_years * days_per_year)


def _settle_household_estate(
    *,
    deceased: Household,
    heir: Household | None,
    state: State,
    savings_bank: SavingsBank,
    config: SimulationConfig,
) -> None:
    """Settle debts and transfer remaining wealth on household death."""

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

        # Repay from local savings (cash returns to bank)
        pay = min(outstanding, max(0.0, estate_local))
        if pay > 0:
            estate_local -= pay
            outstanding -= pay

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
            savings_bank.savings_accounts["state"] = float(
                savings_bank.savings_accounts.get("state", 0.0)
            ) + estate_deposit * (1.0 - share)

    # Remove deceased deposit entry.
    savings_bank.savings_accounts.pop(did, None)

    # 5) Zero the deceased balances
    if hasattr(deceased, "sight_balance"):
        deceased.sight_balance = 0.0
    if hasattr(deceased, "local_savings"):
        deceased.local_savings = 0.0


class SimulationEngine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.reset()

    def reset(self) -> None:
        """Reset the simulation to its initial state."""

        # 1) Clear global caches and ClassVar states before re-initializing agents.
        GlobalConfigCache().initialize(self.config)
        if hasattr(Company, "_lineage_counters"):
            Company._lineage_counters.clear()
        household_module._DEFAULT_NP_RNG = None
        consumption_module._DEFAULT_NP_RNG = None

        # 2) Deterministic seeding.
        # Seeding MUST happen before initialize_agents to ensure deterministic agent creation if they use global RNG.
        seed_val: int | None = None
        env_seed = os.getenv("SIM_SEED")
        if env_seed is not None and env_seed != "":
            seed_val = int(env_seed)
        elif os.getenv("SIM_SEED_FROM_CONFIG") == "1":
            seed = getattr(getattr(self.config, "time", None), "seed", None)
            if seed is None:
                seed = getattr(getattr(self.config, "population", None), "seed", None)
            if seed is not None:
                seed_val = int(seed)

        if seed_val is not None:
            random.seed(seed_val)
            np.random.seed(seed_val)
            self.np_rng = np.random.default_rng(seed_val)
        else:
            self.np_rng = np.random.default_rng()

        self.agents_dict = initialize_agents(self.config)
        self.households: list[Household] = self.agents_dict["households"]
        self.companies: list[Company] = self.agents_dict["companies"]
        self.retailers: list[RetailerAgent] = self.agents_dict["retailers"]
        self.state: State = self.agents_dict["state"]
        self.warengeld_banks: list[WarengeldBank] = self.agents_dict.get(
            "warengeld_banks", [self.agents_dict["warengeld_bank"]]
        )
        self.savings_banks: list[SavingsBank] = self.agents_dict.get(
            "savings_banks", [self.agents_dict["savings_bank"]]
        )
        self.banks_by_region: dict[str, WarengeldBank] = self.agents_dict.get(
            "banks_by_region", {"region_0": self.warengeld_banks[0]}
        )
        self.savings_by_region: dict[str, SavingsBank] = self.agents_dict.get(
            "savings_by_region", {"region_0": self.savings_banks[0]}
        )
        self.clearing: ClearingAgent = self.agents_dict["clearing_agent"]
        self.labor_market: LaborMarket = self.agents_dict["labor_market"]
        self.environmental_agency: EnvironmentalAgency = self.agents_dict["environmental_agency"]

        for h in self.households:
            self.labor_market.register_worker(h)

        self.steps = int(self.config.simulation_steps)
        self.clock = SimulationClock(self.config.time)
        self.current_step = 0

        self.collector = MetricsCollector(config=self.config)
        for h in self.households:
            self.collector.register_household(h)
        for c in self.companies:
            self.collector.register_company(c)
        for b in self.warengeld_banks:
            self.collector.register_bank(b)
        for sb in self.savings_banks:
            self.collector.register_bank(sb)

        # Progress tracking state
        self.progress_enabled = os.getenv("SIM_PROGRESS", "1") not in {"0", "false", "False"}
        self.progress_use_ansi = self.progress_enabled and (os.getenv("NO_COLOR") is None)
        self.start_ts = time.time()
        self.last_progress_ts = self.start_ts
        self.progress_every_steps = max(1, self.steps // 200)
        self.progress_every_seconds = 2.0

        # Lifecycle state
        configured_initial = int(
            getattr(getattr(self.config, "population", None), "num_households", 0) or 0
        )
        self.next_household_idx = (
            configured_initial if configured_initial > 0 else len(self.households)
        )
        try:
            existing_suffixes = [
                int(str(h.unique_id).replace(str(self.config.HOUSEHOLD_ID_PREFIX), ""))
                for h in self.households
                if str(h.unique_id).startswith(str(self.config.HOUSEHOLD_ID_PREFIX))
            ]
            if existing_suffixes:
                self.next_household_idx = max(self.next_household_idx, max(existing_suffixes) + 1)
        except Exception:
            pass

        configured_companies = int(
            getattr(getattr(self.config, "population", None), "num_companies", 0) or 0
        )
        self.next_company_idx = (
            configured_companies if configured_companies > 0 else len(self.companies)
        )
        prefix = str(self.config.COMPANY_ID_PREFIX)
        numeric_suffixes: list[int] = []
        for c in self.companies:
            uid = str(getattr(c, "unique_id", ""))
            if uid.startswith(prefix):
                tail = uid[len(prefix) :]
                if tail.isdigit():
                    numeric_suffixes.append(int(tail))
        if numeric_suffixes:
            self.next_company_idx = max(self.next_company_idx, max(numeric_suffixes) + 1)

    def step(self) -> None:
        """Execute a single time step of the simulation."""
        step = self.current_step
        self.clock.day_index = step

        # Reset per-step retailer flow counters
        for r in self.retailers:
            r.sales_total = 0.0
            r.purchases_total = 0.0
            r.write_downs_total = 0.0
            if hasattr(r, "repaid_total"):
                r.repaid_total = 0.0
            if hasattr(r, "inventory_write_down_extinguished_total"):
                r.inventory_write_down_extinguished_total = 0.0

        for c in self.companies:
            if hasattr(c, "service_sales_total"):
                c.service_sales_total = 0.0

        # 0) Demography pass
        alive_households: list[Household] = []
        deaths_this_step = 0
        births_this_step = 0
        company_births_this_step = 0
        company_deaths_this_step = 0
        companies_by_id = {c.unique_id: c for c in self.companies}
        days_per_year = int(getattr(self.config.time, "days_per_year", 360))
        base_annual = float(getattr(self.config.household, "mortality_base_annual", 0.0) or 0.0)
        senesce_annual = float(
            getattr(self.config.household, "mortality_senescence_annual", 0.0) or 0.0
        )
        shape = float(getattr(self.config.household, "mortality_shape", 3.0) or 3.0)

        for h in self.households:
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
                region_id = getattr(h, "region_id", "region_0")
                h_savings_bank = self.savings_by_region.get(region_id, self.savings_banks[0])
                heir_candidates = [
                    hh
                    for hh in self.households
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
                    state=self.state,
                    savings_bank=h_savings_bank,
                    config=self.config,
                )
                self.labor_market.deregister_worker(h)
                employer_id = getattr(h, "employer_id", None)
                if employer_id:
                    employer = companies_by_id.get(str(employer_id))
                    if employer is not None and h in getattr(employer, "employees", []):
                        employer.employees = [e for e in employer.employees if e is not h]

                replacement = Household(
                    unique_id=f"{self.config.HOUSEHOLD_ID_PREFIX}{self.next_household_idx}",
                    config=self.config,
                )
                replacement.region_id = getattr(h, "region_id", "region_0")
                replacement.age_days = _sample_household_age_days(
                    self.config, working_age_only=True
                )
                replacement.age = replacement.age_days // max(1, days_per_year)
                self.next_household_idx += 1
                self.collector.register_household(replacement)
                self.labor_market.register_worker(replacement)
                alive_households.append(replacement)
                births_this_step += 1
                continue
            alive_households.append(h)

        if not alive_households:
            seed_household = Household(
                unique_id=f"{self.config.HOUSEHOLD_ID_PREFIX}{self.next_household_idx}",
                config=self.config,
            )
            seed_household.region_id = "region_0"
            seed_household.age_days = _sample_household_age_days(self.config, working_age_only=True)
            seed_household.age = seed_household.age_days // max(1, days_per_year)
            self.labor_market.register_worker(seed_household)
            self.collector.register_household(seed_household)
            self.next_household_idx += 1
            alive_households.append(seed_household)

        self.households = alive_households
        self.agents_dict["households"] = self.households

        # 0b) Company population dynamics
        opportunity_by_region: dict[str, float] = {}
        for r in self.retailers:
            target = float(
                getattr(
                    r,
                    "target_inventory_value",
                    getattr(self.config.retailer, "target_inventory_value", 0.0),
                )
                or 0.0
            )
            current = float(getattr(r, "inventory_value", 0.0) or 0.0)
            shortage = max(0.0, target - current)
            rid = getattr(r, "region_id", "region_0")
            opportunity_by_region.setdefault(rid, 0.0)
            opportunity_by_region[rid] += shortage

        target_by_region: dict[str, float] = {}
        for r in self.retailers:
            rid = getattr(r, "region_id", "region_0")
            target_by_region[rid] = target_by_region.get(rid, 0.0) + float(
                getattr(r, "target_inventory_value", 0.0) or 0.0
            )

        for rid, shortage in list(opportunity_by_region.items()):
            denom = max(1e-9, float(target_by_region.get(rid, 0.0) or 0.0))
            opportunity_by_region[rid] = max(0.0, min(1.0, shortage / denom))

        found_base = float(getattr(self.config.company, "founding_base_annual", 0.0) or 0.0)
        found_sens = float(
            getattr(self.config.company, "founding_opportunity_sensitivity", 0.0) or 0.0
        )
        min_capital = float(getattr(self.config.company, "founding_min_capital", 0.0) or 0.0)
        share_capital = float(
            getattr(self.config.company, "founding_capital_share_of_founder_wealth", 0.0) or 0.0
        )

        for region_id in list(self.banks_by_region.keys()):
            opportunity = float(opportunity_by_region.get(region_id, 0.0) or 0.0)
            p_found = (found_base / float(max(1, days_per_year))) * (1.0 + found_sens * opportunity)
            if p_found > 0 and random.random() < min(1.0, p_found):
                sb = self.savings_by_region.get(region_id, self.savings_banks[0])
                region_households = [
                    h for h in self.households if getattr(h, "region_id", "region_0") == region_id
                ]
                if region_households:

                    def _wealth(hh: Household) -> float:
                        return (
                            float(getattr(hh, "sight_balance", 0.0) or 0.0)
                            + float(getattr(hh, "local_savings", 0.0) or 0.0)
                            + float(sb.savings_accounts.get(hh.unique_id, 0.0) or 0.0)
                        )

                    founder = max(region_households, key=_wealth)
                    founder_wealth = _wealth(founder)
                    buffer = float(getattr(self.config.household, "transaction_buffer", 0.0) or 0.0)
                    available = max(0.0, founder_wealth - buffer)
                    desired = max(min_capital, founder_wealth * share_capital)
                    invest = min(desired, available)
                    if invest >= min_capital and invest > 0:
                        remaining = invest
                        disposable_sight = max(0.0, float(founder.sight_balance) - buffer)
                        from_sight = min(disposable_sight, remaining)
                        if from_sight > 0:
                            founder.sight_balance -= from_sight
                            remaining -= from_sight
                        from_local = min(max(0.0, float(founder.local_savings)), remaining)
                        if from_local > 0:
                            founder.local_savings -= from_local
                            remaining -= from_local
                        if remaining > 0:
                            withdrawn = sb.withdraw_savings(founder, remaining)
                            if withdrawn > 0:
                                founder.sight_balance -= withdrawn
                                remaining -= withdrawn
                        transferred = invest - max(0.0, remaining)
                        if transferred >= min_capital and transferred > 0:
                            template = self.config.population.company_template
                            new_company = Company(
                                unique_id=f"{self.config.COMPANY_ID_PREFIX}{self.next_company_idx}",
                                production_capacity=template.production_capacity,
                                config=self.config,
                            )
                            new_company.region_id = region_id
                            new_company.sight_balance = float(transferred)
                            self.next_company_idx += 1
                            self.companies.append(new_company)
                            self.collector.register_company(new_company)
                            company_births_this_step += 1

        merge_base = float(getattr(self.config.company, "merger_rate_annual", 0.0) or 0.0)
        distress = float(getattr(self.config.company, "merger_distress_threshold", 0.0) or 0.0)
        min_acq = float(getattr(self.config.company, "merger_min_acquirer_balance", 0.0) or 0.0)
        synergy = float(getattr(self.config.company, "merger_capacity_synergy", 1.0) or 1.0)
        if merge_base > 0:
            p_merge = min(1.0, merge_base / float(max(1, days_per_year)))
            if random.random() < p_merge:
                regions = [rid for rid in self.banks_by_region.keys() if rid]
                if regions:
                    region_id = random.choice(regions)
                    region_companies = [
                        c
                        for c in self.companies
                        if getattr(c, "region_id", "region_0") == region_id
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
                            self.companies = [c for c in self.companies if c is not target]
                            company_deaths_this_step += 1

        # 1) Firms: post labor demand
        alive_companies: list[Company] = []
        for c in self.companies:
            c.adjust_employees(self.labor_market)
            alive_companies.append(c)
        self.companies = alive_companies
        self.agents_dict["companies"] = self.companies

        # 2) Labor market matching
        if step > 0:
            last_price_index = float(
                self.collector.latest_global_metrics.get(
                    "price_index", self.config.market.price_index_base
                )
            )
        else:
            last_price_index = float(self.config.market.price_index_base)
        self.labor_market.step(current_step=step, price_index=last_price_index)

        # 3) Firms: operations + lifecycle
        new_companies = []
        alive_companies = []
        for c in self.companies:
            result = c.step(
                current_step=step,
                state=self.state,
                savings_bank=self.savings_by_region.get(c.region_id, self.savings_banks[0]),
            )
            if isinstance(result, Company):
                company_births_this_step += 1
                result.unique_id = f"{self.config.COMPANY_ID_PREFIX}{self.next_company_idx}"
                self.next_company_idx += 1
                new_companies.append(result)
                self.collector.register_company(result)
                alive_companies.append(c)
            elif result in ("DEAD", "LIQUIDATED"):
                company_deaths_this_step += 1
                continue
            else:
                alive_companies.append(c)
        if new_companies:
            alive_companies.extend(new_companies)
        self.companies = alive_companies
        self.agents_dict["companies"] = self.companies

        # 4) Retail restocking
        local_trade_bias = float(self.config.spatial.local_trade_bias)
        for r in self.retailers:
            bank = self.banks_by_region.get(r.region_id, self.warengeld_banks[0])
            if random.random() < local_trade_bias:
                producer_pool = [
                    c for c in self.companies if c.region_id == r.region_id
                ] or self.companies
            else:
                producer_pool = self.companies
            r.restock_goods(companies=producer_pool, bank=bank, current_step=step)

        # 5) Households consume
        retailers_by_region: dict[str, list[RetailerAgent]] = {}
        for r in self.retailers:
            retailers_by_region.setdefault(r.region_id, []).append(r)
        alive_households = []
        newborns: list[Household] = []
        households_by_region: dict[str, list[Household]] = {}
        for h in self.households:
            households_by_region.setdefault(h.region_id, []).append(h)
        for region_id, region_households in households_by_region.items():
            h_retailers = retailers_by_region.get(region_id, self.retailers)
            h_savings_bank = self.savings_by_region.get(region_id, self.savings_banks[0])
            for h in region_households:
                h._savings_bank_ref = h_savings_bank
            region_newborns = Household.batch_step(
                region_households,
                current_step=step,
                clock=self.clock,
                savings_bank=h_savings_bank,
                retailers=h_retailers,
            )
            alive_households.extend(region_households)
            for maybe_new in region_newborns:
                births_this_step += 1
                old_id = str(getattr(maybe_new, "unique_id", ""))
                new_id = f"{self.config.HOUSEHOLD_ID_PREFIX}{self.next_household_idx}"
                if h_savings_bank is not None and hasattr(h_savings_bank, "rename_agent_id"):
                    h_savings_bank.rename_agent_id(old_id, new_id)
                maybe_new.unique_id = new_id
                self.next_household_idx += 1
                self.collector.register_household(maybe_new)
                maybe_new.employed = False
                maybe_new.current_wage = None
                self.labor_market.register_worker(maybe_new)
                newborns.append(maybe_new)
        if newborns:
            alive_households.extend(newborns)
        self.households = alive_households
        self.agents_dict["households"] = self.households

        # 6) Retail settlement
        for r in self.retailers:
            bank = self.banks_by_region.get(r.region_id, self.warengeld_banks[0])
            r.settle_accounts(bank=bank, current_step=step)
        for r in self.retailers:
            if hasattr(r, "push_cogs_history"):
                r.push_cogs_history(window_days=int(self.config.bank.cc_limit_rolling_window_days))

        # 7) Monthly policies
        if self.clock.is_month_end(step):
            for rid, bank in self.banks_by_region.items():
                region_retailers = [r for r in self.retailers if r.region_id == rid]
                bank.recompute_cc_limits(region_retailers, current_step=step)
                bank_accounts: list[Any] = [a for a in self.households if a.region_id == rid]
                bank_accounts += [a for a in self.companies if a.region_id == rid]
                bank_accounts += [a for a in self.retailers if a.region_id == rid]
                bank.charge_account_fees(bank_accounts)
            self.state.step([*self.companies, *self.retailers])
            self.state.spend_budgets(self.households, self.companies, self.retailers)
            self.clearing.apply_sight_decay(
                [*self.households, *self.companies, *self.retailers, self.state]
            )
            for region_id, sb in self.savings_by_region.items():
                region_companies = [
                    c
                    for c in self.companies
                    if str(getattr(c, "region_id", "region_0")) == str(region_id)
                ]
                sb.step(current_step=step, companies=region_companies)

        # 8) Periodic clearing audits
        if self.clock.is_period_end(int(self.config.clearing.audit_interval), step):
            companies_by_id = {c.unique_id: c for c in self.companies}
            for bank in self.warengeld_banks:
                local_retailers = [
                    r
                    for r in self.retailers
                    if r.region_id == getattr(bank, "region_id", "region_0")
                ]
                if not local_retailers:
                    local_retailers = self.retailers
                self.clearing.audit_bank(
                    bank=bank,
                    retailers=local_retailers,
                    companies_by_id=companies_by_id,
                    current_step=step,
                )
                self.clearing.enforce_reserve_bounds(bank=bank)

        # 9) Environment
        if self.clock.is_month_end(step):
            self.environmental_agency.step(
                current_step=step, agents=[*self.companies, *self.retailers], state=self.state
            )

        # Collect metrics
        self.collector.collect_household_metrics(self.households, step)
        self.collector.collect_company_metrics(self.companies, step)
        self.collector.collect_retailer_metrics(self.retailers, step)
        self.collector.collect_bank_metrics(self.warengeld_banks, step)
        self.collector.collect_bank_metrics(self.savings_banks, step)
        self.collector.collect_state_metrics(
            "state", self.state, self.households, self.companies, step
        )
        self.collector.collect_market_metrics(self.labor_market, step)
        self.collector.calculate_global_metrics(step)

        if step in self.collector.global_metrics:
            self.collector.global_metrics[step].update(
                {
                    "total_households": len(self.households),
                    "total_companies": len(self.companies),
                    "total_retailers": len(self.retailers),
                    "deaths": deaths_this_step,
                    "births": births_this_step,
                    "company_births": company_births_this_step,
                    "company_deaths": company_deaths_this_step,
                }
            )

        # Progress update
        if self.progress_enabled:
            is_last = (step + 1) == self.steps
            now = time.time()
            if is_last or (
                (step + 1) % self.progress_every_steps == 0
                and (now - self.last_progress_ts) >= self.progress_every_seconds
            ):
                elapsed = now - self.start_ts
                done = step + 1
                rate = done / elapsed if elapsed > 0 else 0.0
                remaining = (self.steps - done) / rate if rate > 0 else float("nan")
                pct = (done / self.steps * 100.0) if self.steps > 0 else 100.0
                bar = _progress_bar(done, self.steps, width=22)
                m1 = _m1_proxy(self.households, self.companies, self.retailers, self.state)
                status = f"{bar} {pct:6.2f}%  step {done}/{self.steps}  HH {len(self.households):5d}  CO {len(self.companies):5d}  M1 {_format_compact_number(m1):>8}  elapsed {_format_duration(elapsed)}  eta {_format_duration(remaining)}"
                color = _progress_color(pct, self.progress_use_ansi)
                status = _ansi(status, color, self.progress_use_ansi)
                sys.stdout.write("\r" + status)
                sys.stdout.flush()
                if is_last:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                self.last_progress_ts = now

        if step % max(1, self.steps // 10) == 0:
            m1 = _m1_proxy(self.households, self.companies, self.retailers, self.state)
            total_cc = sum(b.total_cc_exposure for b in self.warengeld_banks)
            log(f"Step {step}: M1 proxy={m1:.2f}, CC exposure={total_cc:.2f}")

        self.current_step += 1

    def run(self) -> dict[str, Any]:
        """Run the full simulation."""
        log(f"Starting simulation for {self.steps} steps...")
        for _ in range(self.steps):
            self.step()

        log("Simulation finished.")
        self.collector.export_metrics()
        self.agents_dict["metrics_collector"] = self.collector
        return self.agents_dict
