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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agents.bank import WarengeldBank
from agents.clearing_agent import ClearingAgent
from agents.company_agent import Company
from agents.environmental_agency import EnvironmentalAgency
from agents.financial_market import FinancialMarket
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.retailer_agent import RetailerAgent
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State
from config import SimulationConfig
from logger import log, setup_logger


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
    if config.population.num_households is not None:
        count = int(config.population.num_households)
        template = config.population.household_template
        return [
            Household(unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{i}", income=template.income, config=config)
            for i in range(count)
        ]

    # fall back: explicit list
    households: list[Household] = []
    for i, h in enumerate(config.INITIAL_HOUSEHOLDS):
        households.append(Household(unique_id=f"{config.HOUSEHOLD_ID_PREFIX}{i}", income=h.income, config=config))
    return households


def create_companies(config: SimulationConfig) -> list[Company]:
    if config.population.num_companies is not None:
        count = int(config.population.num_companies)
        template = config.population.company_template
        return [
            Company(unique_id=f"{config.COMPANY_ID_PREFIX}{i}", production_capacity=template.production_capacity, config=config)
            for i in range(count)
        ]

    companies: list[Company] = []
    for i, c in enumerate(config.INITIAL_COMPANIES):
        companies.append(
            Company(unique_id=f"{config.COMPANY_ID_PREFIX}{i}", production_capacity=c.production_capacity, config=config)
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
                target_inventory_value=getattr(template, "target_inventory_value", config.retailer.target_inventory_value),
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
                target_inventory_value=getattr(r, "target_inventory_value", config.retailer.target_inventory_value),
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
    financial_market: FinancialMarket
    labor_market: LaborMarket
    environmental_agency: EnvironmentalAgency


def initialize_agents(config: SimulationConfig) -> dict[str, Any]:
    """Create agent instances.

    Kept for backwards compatibility with unit tests.
    """

    state = State(unique_id="state", config=config)
    warengeld_bank = WarengeldBank(unique_id="warengeld_bank", config=config)
    savings_bank = SavingsBank(unique_id="savings_bank", config=config)
    clearing = ClearingAgent(unique_id="clearing", config=config)
    financial_market = FinancialMarket(unique_id="financial_market", config=config)
    labor_market = LaborMarket(unique_id="labor_market", config=config)
    environmental_agency = EnvironmentalAgency(unique_id="environmental_agency", config=config)

    households = create_households(config)
    companies = create_companies(config)
    retailers = create_retailers(config)

    # Attach labor market to state
    state.labor_market = labor_market

    # Register retailer Kontokorrent lines
    for r in retailers:
        warengeld_bank.register_retailer(r, cc_limit=r.cc_limit)

    # Register bank with clearing (reserve tracking)
    clearing.register_bank(warengeld_bank)

    return {
        "households": households,
        "companies": companies,
        "retailers": retailers,
        "state": state,
        "warengeld_bank": warengeld_bank,
        "savings_bank": savings_bank,
        "clearing_agent": clearing,
        "financial_market": financial_market,
        "labor_market": labor_market,
        "environmental_agency": environmental_agency,
    }


# ---------------------------
# Simulation loop
# ---------------------------


def _m1_proxy(households: list[Household], companies: list[Company], retailers: list[RetailerAgent], state: State) -> float:
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


def run_simulation(config: SimulationConfig) -> dict[str, Any]:
    agents = initialize_agents(config)

    households: list[Household] = agents["households"]
    companies: list[Company] = agents["companies"]
    retailers: list[RetailerAgent] = agents["retailers"]

    state: State = agents["state"]
    warengeld_bank: WarengeldBank = agents["warengeld_bank"]
    savings_bank: SavingsBank = agents["savings_bank"]
    clearing: ClearingAgent = agents["clearing_agent"]
    labor_market: LaborMarket = agents["labor_market"]
    environmental_agency: EnvironmentalAgency = agents["environmental_agency"]

    steps = int(config.simulation_steps)
    month_len = int(getattr(config, "MONTH_LENGTH", 30))

    log(f"Starting simulation for {steps} steps...")

    for step in range(steps):
        # 1) Firms: production, workforce, wage payments (no Warengeld credit)
        for c in companies:
            c.step(current_step=step, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)

        # 2) Labor market matching
        labor_market.step(current_step=step)

        # 3) Retail restocking (money creation point)
        for r in retailers:
            r.restock_goods(companies=companies, bank=warengeld_bank, current_step=step)

        # 4) Households consume from retailers, then save via Sparkasse
        for h in households:
            h.step(current_step=step, savings_bank=savings_bank, retailers=retailers)

        # 5) Retail settlement (repay CC -> money extinguishing; write-downs)
        for r in retailers:
            r.settle_accounts(bank=warengeld_bank, current_step=step)

        # 6) Monthly policies
        if (step + 1) % month_len == 0:
            # Bank account fees (no interest)
            warengeld_bank.charge_account_fees([*households, *companies, *retailers, state])

            # State taxes and budgets
            state.step([*companies, *retailers])

            # Sight factor decay (excess sight balances)
            clearing.apply_sight_decay(households)

            # Savings bank bookkeeping
            savings_bank.step(current_step=step)

        # 7) Periodic clearing audits / reserve adjustments
        if (step + 1) % int(config.clearing.audit_interval) == 0:
            companies_by_id = {c.unique_id: c for c in companies}
            clearing.audit_bank(bank=warengeld_bank, retailers=retailers, companies_by_id=companies_by_id, current_step=step)
            clearing.enforce_reserve_bounds(bank=warengeld_bank)

        # 8) Environment (optional)
        environmental_agency.step(current_step=step, agents=[*companies, *retailers])

        if step % max(1, steps // 10) == 0:
            m1 = _m1_proxy(households, companies, retailers, state)
            log(f"Step {step}: M1 proxy={m1:.2f}, CC exposure={warengeld_bank.total_cc_exposure:.2f}")

    log("Simulation finished.")
    return agents


# ---------------------------
# CLI
# ---------------------------


def main() -> None:
    cfg = _resolve_config_from_args_or_env()
    # Ensure logging is configured before any agents emit logs.
    setup_logger(level=cfg.logging_level, log_file=cfg.log_file, log_format=cfg.log_format, file_mode="w")
    run_simulation(cfg)


if __name__ == "__main__":
    main()
