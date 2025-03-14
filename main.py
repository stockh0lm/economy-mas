# main.py
import json
from typing import TypeAlias, Literal

from logger import setup_logger, log
from config import CONFIG

from agents.household_agent import Household
from agents.company_agent import Company
from agents.state_agent import State
from agents.bank import WarengeldBank
from agents.savings_bank_agent import SavingsBank
from agents.clearing_agent import ClearingAgent
from agents.environmental_agency import EnvironmentalAgency, RecyclingCompany
from agents.financial_market import FinancialMarket
from agents.labor_market import LaborMarket

# Type aliases
AgentResult: TypeAlias = None | Literal["DEAD"] | object
AgentDict: TypeAlias = dict[str, State | list[Household | Company] | WarengeldBank | SavingsBank | ClearingAgent |
                            EnvironmentalAgency | RecyclingCompany | FinancialMarket | LaborMarket | list[object]]

def initialize_agents() -> AgentDict:
    """Initialize all simulation agents and their relationships."""
    state: State = State(CONFIG["STATE_ID"])

    # Create initial households based on configuration
    households: list[Household] = []
    for i, params in enumerate(CONFIG["INITIAL_HOUSEHOLDS"]):
        households.append(
            Household(
                f"{CONFIG['HOUSEHOLD_ID_PREFIX']}{i+1}",
                income=params["income"],
                land_area=params["land_area"],
                environmental_impact=params["environmental_impact"]
            )
        )

    # Create initial companies based on configuration
    companies: list[Company] = []
    for i, params in enumerate(CONFIG["INITIAL_COMPANIES"]):
        companies.append(
            Company(
                f"{CONFIG['COMPANY_ID_PREFIX']}{i+1}",
                production_capacity=params["production_capacity"],
                land_area=params["land_area"],
                environmental_impact=params["environmental_impact"]
            )
        )

    warengeld_bank = WarengeldBank(CONFIG["BANK_ID"])
    savings_bank = SavingsBank(CONFIG["SAVINGS_BANK_ID"])

    clearing_agent = ClearingAgent(CONFIG["CLEARING_AGENT_ID"])
    clearing_agent.monitored_banks.append(warengeld_bank)
    clearing_agent.monitored_savings_banks.append(savings_bank)

    environmental_agency = EnvironmentalAgency(CONFIG["ENV_AGENCY_ID"])
    recycling_company = RecyclingCompany(
        CONFIG["RECYCLING_COMPANY_ID"],
        recycling_efficiency=CONFIG["recycling_efficiency"]
    )
    financial_market = FinancialMarket(CONFIG["FINANCIAL_MARKET_ID"])
    labor_market = LaborMarket(CONFIG["LABOR_MARKET_ID"])
    state.labor_market = labor_market

    # Register workers and job offers in labor market
    for hh in households:
        labor_market.register_worker(hh)
    for comp in companies:
        labor_market.register_job_offer(
            comp,
            wage=CONFIG["default_wage"],
            positions=CONFIG["INITIAL_JOB_POSITIONS_PER_COMPANY"]
        )

    all_agents: list[object] = households + companies + [state, warengeld_bank, savings_bank]

    return {
        "state": state,
        "households": households,
        "companies": companies,
        "warengeld_bank": warengeld_bank,
        "savings_bank": savings_bank,
        "clearing_agent": clearing_agent,
        "environmental_agency": environmental_agency,
        "recycling_company": recycling_company,
        "financial_market": financial_market,
        "labor_market": labor_market,
        "all_agents": all_agents
    }

def update_households(households: list[Household], step: int, state: State) -> list[Household]:
    """Update all households and manage newly created or dead households."""
    new_households: list[Household] = []
    alive_households: list[Household] = []

    for household in households:
        result: AgentResult = household.step(step, state)

        if result == "DEAD":
            log(f"Household {household.unique_id} removed (dead).", level="INFO")
            continue
        elif result is not None:
            new_households.append(result)
            alive_households.append(household)
        else:
            alive_households.append(household)

    return alive_households + new_households

def update_companies(companies: list[Company], step: int, state: State) -> list[Company]:
    """Update all companies and manage newly created or bankrupt companies."""
    new_companies: list[Company] = []
    surviving_companies: list[Company] = []

    for company in companies:
        result: AgentResult = company.step(step, state)

        if result == "DEAD":
            log(f"Company {company.unique_id} removed (bankrupt).", level="INFO")
            continue
        elif result is not None:
            new_companies.append(result)
            surviving_companies.append(company)
        else:
            surviving_companies.append(company)

    return surviving_companies + new_companies

def update_other_agents(step: int, agents_dict: AgentDict, state: State) -> None:
    """Update all auxiliary agents in the simulation."""
    warengeld_bank: WarengeldBank = agents_dict["warengeld_bank"]
    savings_bank: SavingsBank = agents_dict["savings_bank"]
    clearing_agent: ClearingAgent = agents_dict["clearing_agent"]
    environmental_agency: EnvironmentalAgency = agents_dict["environmental_agency"]
    recycling_company: RecyclingCompany = agents_dict["recycling_company"]
    financial_market: FinancialMarket = agents_dict["financial_market"]
    labor_market: LaborMarket = agents_dict["labor_market"]
    companies: list[Company] = agents_dict["companies"]
    households: list[Household] = agents_dict["households"]
    all_agents: list[object] = agents_dict["all_agents"]

    warengeld_bank.step(step, companies)
    savings_bank.step(step)
    clearing_agent.step(step, all_agents)
    environmental_agency.step(step, companies + households)
    recycling_company.step(step)
    financial_market.step(step, companies + households)
    labor_market.step(step)

def update_all_agents(agents_dict: AgentDict) -> AgentDict:
    """Update the combined agents list after individual agent updates."""
    agents_dict["all_agents"] = (
        agents_dict["households"] +
        agents_dict["companies"] +
        [agents_dict["state"], agents_dict["warengeld_bank"], agents_dict["savings_bank"]]
    )
    return agents_dict

def summarize_simulation(agents_dict: AgentDict) -> None:
    """Generate and save simulation summary to a JSON file."""
    summary = {
        "State": {
            "infrastructure_budget": agents_dict["state"].infrastructure_budget,
            "social_budget": agents_dict["state"].social_budget,
            "environment_budget": agents_dict["state"].environment_budget
        },
        "Households": {
            hh.unique_id: {
                "balance": hh.balance,
                "checking_account": hh.checking_account,
                "savings": hh.savings,
                "age": hh.age,
                "generation": hh.generation
            } for hh in agents_dict["households"]
        },
        "Companies": {
            comp.unique_id: {
                "balance": comp.balance,
                "inventory": comp.inventory
            } for comp in agents_dict["companies"]
        },
        "WarengeldBank": {
            "collected_fees": agents_dict["warengeld_bank"].collected_fees,
            "liquidity": agents_dict["warengeld_bank"].liquidity
        },
        "SavingsBank": {
            "total_savings": agents_dict["savings_bank"].total_savings,
            "liquidity": agents_dict["savings_bank"].liquidity
        },
        "ClearingAgent": {
            "excess_wealth_collected": agents_dict["clearing_agent"].excess_wealth_collected
        },
        "EnvironmentalAgency": {
            "collected_env_tax": agents_dict["environmental_agency"].collected_env_tax
        },
        "RecyclingCompany": {
            "processed_materials": agents_dict["recycling_company"].processed_materials
        }
    }

    with open(CONFIG["SUMMARY_FILE"], "w") as f:
        json.dump(summary, f, indent=CONFIG["JSON_INDENT"])

    log(f"Simulation summary stored in {CONFIG['SUMMARY_FILE']}", level="INFO")

def main() -> None:
    """Main simulation execution function."""
    logger = setup_logger()
    log("Starting MAS simulation...", level="INFO")
    num_steps: int = CONFIG["simulation_steps"]

    agents: AgentDict = initialize_agents()

    for step in range(1, num_steps + 1):
        log(f"---- Simulation Step {step} ----", level="INFO")
        agents["state"].step(agents["households"] + agents["companies"])
        agents["households"] = update_households(agents["households"], step, agents["state"])
        agents["companies"] = update_companies(agents["companies"], step, agents["state"])
        agents = update_all_agents(agents)
        update_other_agents(step, agents, agents["state"])

    log("Simulation complete.", level="INFO")
    summarize_simulation(agents)

if __name__ == "__main__":
    main()