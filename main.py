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
from pathlib import Path
from typing import Any

import yaml

from config import SimulationConfig
from logger import setup_logger
from simulation.engine import (
    SimulationEngine,
    initialize_agents,
    _sample_household_age_days,
    _settle_household_estate,
    create_households,
    create_companies,
    create_retailers,
    SimulationAgents,
    _m1_proxy,
)


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


def run_simulation(config: SimulationConfig) -> dict[str, Any]:
    """Orchestrate the simulation run using the SimulationEngine."""
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
