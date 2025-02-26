import json
import time

from logger import setup_logger, log
from config import CONFIG

# Importiere alle Agentenklassen
from agents.household_agent import Household
from agents.company_agent import Company
from agents.state_agent import State
from agents.bank import WarengeldBank
from agents.savings_bank_agent import SavingsBank
from agents.clearing_agent import ClearingAgent
from agents.environmental_agency import EnvironmentalAgency, RecyclingCompany
from agents.financial_market import FinancialMarket
from agents.labor_market import LaborMarket


def initialize_agents():
    """Erstellt und gibt alle benötigten Agenten zurück."""
    state = State("state_1")

    households = [
        Household("household_1", income=100, land_area=50, environment_impact=1),
        Household("household_2", income=120, land_area=60, environment_impact=2),
        Household("household_3", income=80, land_area=40, environment_impact=1)
    ]

    companies = [
        Company("company_1", production_capacity=100, land_area=100, environmental_impact=5),
        Company("company_2", production_capacity=80, land_area=80, environmental_impact=4)
    ]

    warengeld_bank = WarengeldBank("bank_1")
    savings_bank = SavingsBank("savings_bank_1")

    clearing_agent = ClearingAgent("clearing_1")
    clearing_agent.monitored_banks.append(warengeld_bank)
    clearing_agent.monitored_sparkassen.append(savings_bank)

    environmental_agency = EnvironmentalAgency("env_agency_1")
    recycling_company = RecyclingCompany("recycling_1", recycling_efficiency=0.8)
    financial_market = FinancialMarket("financial_market_1")
    labor_market = LaborMarket("labor_market_1")

    # Registriere Haushalte und Firmen beim Arbeitsmarkt
    for hh in households:
        labor_market.register_worker(hh)
    for comp in companies:
        labor_market.register_job_offer(comp, wage=10, positions=3)

    # Kombiniere relevante Agenten für übergreifende Operationen
    all_agents = households + companies + [state, warengeld_bank, savings_bank]

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


def update_households(households, step, state):
    """Führt den Simulationsschritt für Haushalte aus und aktualisiert die Liste.
       Gibt die aktualisierte Liste der lebenden Haushalte zurück."""
    new_households = []
    alive_households = []
    for hh in households:
        result = hh.step(step, state)
        if result == "DEAD":
            log(f"Household {hh.unique_id} removed (dead).", level="INFO")
            continue  # Haushalt stirbt und wird nicht weitergeführt
        elif result is not None:
            new_households.append(result)
            alive_households.append(hh)
        else:
            alive_households.append(hh)
    return alive_households + new_households


def update_companies(companies, step, state):
    """Führt den Simulationsschritt für Unternehmen aus und aktualisiert die Liste.
       Gibt die aktualisierte Liste der überlebenden Unternehmen zurück."""
    new_companies = []
    surviving_companies = []
    for comp in companies:
        result = comp.step(step, state)
        if result == "DEAD":
            log(f"Company {comp.unique_id} removed (bankrupt).", level="INFO")
            continue  # Unternehmen wird entfernt
        elif result is not None:
            new_companies.append(result)
            surviving_companies.append(comp)
        else:
            surviving_companies.append(comp)
    return surviving_companies + new_companies


def update_other_agents(step, agents_dict, state):
    """Führt die step()-Methode aller übrigen Agenten aus."""
    agents_dict["warengeld_bank"].step(step, agents_dict["companies"])
    agents_dict["savings_bank"].step(step)
    agents_dict["clearing_agent"].step(step, agents_dict["all_agents"])
    agents_dict["environmental_agency"].step(step, agents_dict["companies"] + agents_dict["households"])
    agents_dict["recycling_company"].step(step)
    agents_dict["financial_market"].step(step, agents_dict["companies"] + agents_dict["households"])
    agents_dict["labor_market"].step(step)


def update_all_agents(agents_dict):
    """Aktualisiert die all_agents-Liste basierend auf den aktuellen Haushalts- und Firmenlisten."""
    agents_dict["all_agents"] = agents_dict["households"] + agents_dict["companies"] + [agents_dict["state"],
                                                                                        agents_dict["warengeld_bank"],
                                                                                        agents_dict["savings_bank"]]
    return agents_dict


def summarize_simulation(agents_dict):
    """Erstellt eine Zusammenfassung der Simulation und speichert sie in einer JSON-Datei."""
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

    with open("simulation_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
    log("Simulation summary stored in simulation_summary.json", level="INFO")


def main():
    logger = setup_logger()
    log("Starting MAS simulation...", level="INFO")
    num_steps = CONFIG.get("simulation_steps", 10)

    agents = initialize_agents()

    for step in range(1, num_steps + 1):
        log(f"---- Simulation Step {step} ----", level="INFO")

        # Staat führt seine Schritte aus (Steuern erheben, etc.)
        agents["state"].step(agents["households"] + agents["companies"])

        # Aktualisiere Haushalte und Firmen
        agents["households"] = update_households(agents["households"], step, agents["state"])
        agents["companies"] = update_companies(agents["companies"], step, agents["state"])

        # Aktualisiere die Liste aller Agenten
        agents = update_all_agents(agents)

        # Aktualisiere übrige Agenten (Banken, Clearing, Umwelt, Recycling, Finanzmarkt, Arbeitsmarkt)
        update_other_agents(step, agents, agents["state"])

    log("Simulation complete.", level="INFO")
    summarize_simulation(agents)


if __name__ == "__main__":
    main()
