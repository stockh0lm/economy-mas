import json

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


def main():
    # Logger initialisieren
    logger = setup_logger()
    log("Starting MAS simulation...", level="INFO")

    num_steps = CONFIG.get("simulation_steps", 10)

    # Agenten-Instanziierung
    state = State("state_1")

    # Haushalte: Drei Beispiele mit unterschiedlichen Parametern
    households = [
        Household("household_1", income=100, land_area=50, environment_impact=1),
        Household("household_2", income=120, land_area=60, environment_impact=2),
        Household("household_3", income=80, land_area=40, environment_impact=1)
    ]

    # Unternehmen: Zwei Beispiele
    companies = [
        Company("company_1", production_capacity=100, land_area=100, environmental_impact=5),
        Company("company_2", production_capacity=80, land_area=80, environmental_impact=4)
    ]

    # WarengeldBank und Sparkasse
    warengeld_bank = WarengeldBank("bank_1")
    savings_bank = SavingsBank("savings_bank_1")

    # Clearingstelle
    clearing_agent = ClearingAgent("clearing_1")
    # Registrierung der Banken/Sparkassen zur Überwachung
    clearing_agent.monitored_banks.append(warengeld_bank)
    clearing_agent.monitored_sparkassen.append(savings_bank)

    # Umweltagentur und Recyclingunternehmen
    environmental_agency = EnvironmentalAgency("env_agency_1")
    recycling_company = RecyclingCompany("recycling_1", recycling_efficiency=0.8)

    # Finanzmarkt
    financial_market = FinancialMarket("financial_market_1")

    # Arbeitsmarkt: Registrierung von arbeitssuchenden Haushalten und Jobangeboten der Unternehmen
    labor_market = LaborMarket("labor_market_1")
    for hh in households:
        labor_market.register_worker(hh)
    for comp in companies:
        labor_market.register_job_offer(comp, wage=10, positions=3)

    # Für Clearing und weitere übergreifende Operationen kombinieren wir relevante Agenten
    all_agents = households + companies + [state, warengeld_bank, savings_bank]

    # Hauptsimulationsschleife
    for step in range(1, num_steps + 1):
        log(f"---- Simulation Step {step} ----", level="INFO")

        # Staat: Steuern erheben, Hypervermögen überwachen und Mittel verteilen

        state.step(households + companies)
        new_households = []
        alive_households = []
        for hh in households:
            result = hh.step(step, state)
            if result == "DEAD":
                # Haushalt stirbt und wird nicht weitergeführt
                continue
            elif result is not None:
                # Splitting: Der neue Haushalt wird hinzugefügt, während der Elternhaushalt weiterlebt
                new_households.append(result)
                alive_households.append(hh)
            else:
                alive_households.append(hh)
        households = alive_households + new_households

        new_companies = []
        surviving_companies = []
        for comp in companies:
            result = comp.step(step, state)
            if result == "DEAD":
                continue  # Unternehmen wird entfernt
            elif result is not None:
                new_companies.append(result)
                surviving_companies.append(comp)
            else:
                surviving_companies.append(comp)
        companies = surviving_companies + new_companies

        # WarengeldBank: Überprüfung der Lagerbestände und Einziehen von Kontoführungsgebühren
        warengeld_bank.step(step, companies)

        # Sparkasse: Überprüfung der Spareinlagen (Spargrenzen etc.)
        savings_bank.step(step)

        # Clearingstelle: Liquiditätsausgleich und Kontrolle von Hypervermögen (auf Basis aller relevanten Agenten)
        clearing_agent.step(step, all_agents)

        # Umweltagentur: Erhebt Umweltsteuern und auditiert Unternehmen/Haushalte
        environmental_agency.step(step, companies + households)

        # Recyclingunternehmen: Verarbeitet gesammelten Abfall
        recycling_company.step(step)

        # Finanzmarkt: Simuliert (prototypisch) Handelsvorgänge und prüft spekulative Assetbestände
        financial_market.step(step, companies + households)

        # Arbeitsmarkt: Matching zwischen registrierten Arbeitssuchenden und Jobangeboten
        labor_market.step(step)

    log("Simulation complete.", level="INFO")

    # Zusammenfassende Ausgabe: z. B. Endbudgets, eingesammelte Gebühren, etc.
    summary = {
        "State": {
            "infrastructure_budget": state.infrastructure_budget,
            "social_budget": state.social_budget,
            "environment_budget": state.environment_budget
        },
        "Households": {
            hh.unique_id: {
                "balance": hh.balance,
                "checking_account": hh.checking_account,
                "savings": hh.savings
            } for hh in households
        },
        "Companies": {
            comp.unique_id: {
                "balance": comp.balance,
                "inventory": comp.inventory
            } for comp in companies
        },
        "WarengeldBank": {
            "collected_fees": warengeld_bank.collected_fees,
            "liquidity": warengeld_bank.liquidity
        },
        "SavingsBank": {
            "total_savings": savings_bank.total_savings,
            "liquidity": savings_bank.liquidity
        },
        "ClearingAgent": {
            "excess_wealth_collected": clearing_agent.excess_wealth_collected
        },
        "EnvironmentalAgency": {
            "collected_env_tax": environmental_agency.collected_env_tax
        },
        "RecyclingCompany": {
            "processed_materials": recycling_company.processed_materials
        }
    }

    with open("simulation_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
    log("Simulation summary stored in simulation_summary.json", level="INFO")


if __name__ == "__main__":
    main()
