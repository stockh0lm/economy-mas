# config.py
CONFIG: dict[str, int | float | str | dict | list] = {
    "simulation_steps": 100,
    "tax_rates": {
        "bodensteuer": 0.05,   # Bodensteuer (5%)
        "umweltsteuer": 0.02    # Umweltsteuer (2%)
    },
    "credit_interest_rate": 0.0,  # zinsfreie Kredite
    "result_storage": "json",  # alternativ auch "csv" möglich

    # Bank-Parameter
    "bank_fee_rate": 0.01,               # Gebührensatz der WarengeldBank (1%)
    "inventory_check_interval": 3,       # Prüfen des Warenbestands alle 3 Schritte
    "initial_bank_liquidity": 1000.0,      # Anfangsliquidität der Bank
    "inventory_coverage_threshold": 0.8,  # Minimum inventory value as percentage of outstanding credit

    # Hypervermögen & Wachstum
    "hyperwealth_threshold": 1000000,    # Schwelle für Hypervermögen (1 Mio.)
    "growth_threshold": 5,               # Anzahl an Schritten in der Wachstumsphase bis zum Splitting
    "growth_balance_trigger": 1000,      # Bilanzgrenze zum Aktivieren der Wachstumsphase
    "bankruptcy_threshold": -100,        # Bilanzgrenze für Insolvenz

    # Arbeitsmarkt / Löhne
    "default_wage": 10,
    "wage_rate": 5,                      # Standardlohn für die Gehaltszahlung

    # Haushalt-Parameter
    "max_age": 80,
    "max_generation": 3,
    "savings_growth_trigger": 500.0,     # Sparsumme, ab der der Wachstumsmodus startet
    "household_consumption_rate_normal": 0.7,
    "household_consumption_rate_growth": 0.9,

    # Unternehmensparameter
    "rd_investment_trigger_balance": 200,  # Mindestbilanz, ab der in F&E investiert wird
    "rd_investment_rate": 0.1,               # 10% des Überschusses fließen in F&E
    "innovation_production_bonus": 0.1,      # 10% Produktionsbonus bei Innovation
    "rd_investment_decay_factor": 0.5,       # Nach erfolgreicher Innovation wird der F&E-Betrag halbiert
    "employee_capacity_ratio": 11.0,         # Production capacity units per employee
    "company_split_ratio": 0.5,              # Portion of balance transferred to new company during split

    # Produktions- und Verkaufskonstanten
    "production_base_price": 10,             # Basisverkaufspreis pro Einheit
    "production_innovation_bonus_rate": 0.02,  # Preisbonus pro Innovationseinheit
    "demand_default": 50,                    # Standardverkaufsnachfrage

    # Recycling
    "recycling_efficiency": 0.8,             # Recycling-Effizienz

    # Clearing-Parameter
    "desired_bank_liquidity": 1000,
    "desired_sparkassen_liquidity": 500,
    "penalty_factor_env_audit": 5,           # Straffaktor bei Umwelt-Audits

    # Finanzmarkt
    "speculation_limit": 10000,  # Threshold for considering asset holdings as hyperwealth
    "asset_initial_prices": {    # Initial prices for financial assets
        "Aktie_A": 100.0,
        "Aktie_B": 50.0,
        "Anleihe_X": 1000.0
    },
    "asset_bid_ask_spreads": {   # Bid-ask spreads as percentage of asset price
        "Aktie_A": 0.02,
        "Aktie_B": 0.02,
        "Anleihe_X": 0.01
    },

    # Sparkassen-Parameter
    "max_savings_per_account": 10000,
    "loan_interest_rate": 0.0,

    # Logging und Debugging
    "logging_level": "DEBUG",
    "log_file": "simulation.log",
    "log_format": "%(asctime)s - %(levelname)s - %(message)s",

        # Agent identification
    "STATE_ID": "state_1",                        # Unique ID for the state agent
    "BANK_ID": "bank_1",                          # Unique ID for the Warengeld bank
    "SAVINGS_BANK_ID": "savings_bank_1",          # Unique ID for the savings bank
    "CLEARING_AGENT_ID": "clearing_1",            # Unique ID for the clearing agent
    "ENV_AGENCY_ID": "env_agency_1",              # Unique ID for the environmental agency
    "RECYCLING_COMPANY_ID": "recycling_1",        # Unique ID for the recycling company
    "FINANCIAL_MARKET_ID": "financial_market_1",  # Unique ID for the financial market
    "LABOR_MARKET_ID": "labor_market_1",          # Unique ID for the labor market
    "HOUSEHOLD_ID_PREFIX": "household_",           # Prefix for household IDs
    "COMPANY_ID_PREFIX": "company_",               # Prefix for company IDs

    # Initial agent configuration
    "INITIAL_HOUSEHOLDS": [
        {"income": 100, "land_area": 50, "environmental_impact": 1},
        {"income": 120, "land_area": 60, "environmental_impact": 2},
        {"income": 110, "land_area": 70, "environmental_impact": 2},
        {"income": 80, "land_area": 40, "environmental_impact": 1}
    ],

    "INITIAL_COMPANIES": [
        {"production_capacity": 100, "land_area": 100, "environmental_impact": 5},
        {"production_capacity": 80, "land_area": 80, "environmental_impact": 4}
    ],

    "INITIAL_JOB_POSITIONS_PER_COMPANY": 3,       # Number of job positions offered by each company

    # Output configuration
    "SUMMARY_FILE": "simulation_summary.json",    # Filename for simulation summary output
    "JSON_INDENT": 4,                             # Indentation level for JSON output files

    # State budget allocation percentages
    "state_budget_allocation": {
        "infrastructure": 0.5,  # 50% of tax revenue allocated to infrastructure
        "social": 0.3,          # 30% of tax revenue allocated to social services
        "environment": 0.2      # 20% of tax revenue allocated to environmental initiatives
    },

}
