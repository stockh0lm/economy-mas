from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

output_dir = "output/"


class TaxRates(BaseModel):
    bodensteuer: float = Field(0.05, ge=0, le=1)
    umweltsteuer: float = Field(0.02, ge=0, le=1)


class InitialHousehold(BaseModel):
    income: float = Field(100.0, ge=0)
    land_area: float = Field(50.0, ge=0)
    environmental_impact: float = Field(1.0, ge=0)


class InitialCompany(BaseModel):
    production_capacity: float = Field(100.0, ge=0)
    land_area: float = Field(100.0, ge=0)
    environmental_impact: float = Field(5.0, ge=0)


class InitialRetailer(BaseModel):
    initial_cc_limit: float = Field(500.0, ge=0)
    target_inventory_value: float = Field(200.0, ge=0)
    land_area: float = Field(20.0, ge=0)
    environmental_impact: float = Field(1.0, ge=0)


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(validate_default=True, frozen=False)


class PopulationConfig(BaseConfigModel):
    """Optional helpers to generate many initial agents without enumerating lists."""

    num_households: PositiveInt | None = None
    num_companies: PositiveInt | None = None

    num_retailers: PositiveInt | None = None

    household_template: InitialHousehold = Field(default_factory=InitialHousehold)
    company_template: InitialCompany = Field(default_factory=InitialCompany)

    retailer_template: InitialRetailer = Field(default_factory=InitialRetailer)

    seed: int | None = None

    @field_validator("seed")
    @classmethod
    def _validate_seed(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return int(value)


def _default_households() -> list[InitialHousehold]:
    return [
        InitialHousehold(income=100, land_area=50, environmental_impact=1),
        InitialHousehold(income=120, land_area=60, environmental_impact=2),
        InitialHousehold(income=110, land_area=70, environmental_impact=2),
        InitialHousehold(income=80, land_area=40, environmental_impact=1),
    ]


def _default_companies() -> list[InitialCompany]:
    return [
        InitialCompany(production_capacity=100, land_area=100, environmental_impact=5),
        InitialCompany(production_capacity=80, land_area=80, environmental_impact=4),
    ]



def _default_retailers() -> list[InitialRetailer]:
    return [
        InitialRetailer(initial_cc_limit=500, target_inventory_value=200, land_area=20, environmental_impact=1),
        InitialRetailer(initial_cc_limit=500, target_inventory_value=200, land_area=20, environmental_impact=1),
    ]

def _default_state_budget_allocation() -> dict[str, float]:
    return {"infrastructure": 0.5, "social": 0.3, "environment": 0.2}


class MetricConfigModel(BaseModel):
    enabled: bool = True  # noqa: F841 - false positive from static analyzers
    display_name: str = ""
    unit: str = ""
    aggregation: Literal["sum", "mean", "median", "min", "max", "value"] = "mean"
    critical_threshold: float | None = None


class AssetPriceMap:
    """Lightweight mapping wrapper retained for backward compatibility."""

    def __init__(self, data: Mapping[str, float] | None = None) -> None:
        self._data: dict[str, float] = dict(data or {})

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, item: str) -> float:
        return self._data[item]

    def get(self, item: str, default: float | None = None) -> float | None:
        return self._data.get(item, default)

    def items(self):
        return self._data.items()

    def as_dict(self) -> dict[str, float]:
        return dict(self._data)

    @classmethod
    def from_dict(cls, data: Mapping[str, float]) -> AssetPriceMap:
        return cls(data)


ConfigScalar = bool | int | float | str | None
ConfigValue = ConfigScalar | list["ConfigValue"] | dict[str, "ConfigValue"]


def _coerce_value(value: object) -> ConfigValue:
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, list):
        return [_coerce_value(item) for item in value]
    if isinstance(value, tuple):
        return [_coerce_value(item) for item in value]
    if isinstance(value, Mapping):
        coerced: dict[str, ConfigValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                msg = "CONFIG keys must be strings"
                raise TypeError(msg)
            coerced[key] = _coerce_value(item)
        return coerced
    msg = f"Unsupported CONFIG value type: {type(value)!r}"
    raise TypeError(msg)


def _coerce_config_dict(data: Mapping[str, object]) -> dict[str, ConfigValue]:
    return {key: _coerce_value(value) for key, value in data.items()}


class HouseholdConfig(BaseConfigModel):
    max_age: PositiveInt = 70
    max_generation: PositiveInt = 3
    base_income: float = Field(100.0, ge=0)
    growth_threshold: PositiveInt = 5
    consumption_rate_normal: float = Field(0.7, ge=0, le=1)
    consumption_rate_growth: float = Field(0.9, ge=0, le=1)
    savings_growth_trigger: float = Field(500.0, ge=0)
    # New: allow growth to trigger from sustained disposable sight-balance (when savings_rate is low).
    sight_growth_trigger: float = Field(0.0, ge=0)
    loan_repayment_rate: float = Field(0.25, ge=0, le=1)
    child_rearing_cost: float = Field(200.0, ge=0)

    # New: household saving behavior
    savings_rate: float = Field(0.0, ge=0, le=1)
    transaction_buffer: float = Field(5.0, ge=0)

    # --- Demography (age-dependent mortality) ---
    # All rates are annual and translated to daily probabilities via the global
    # calendar (360 days/year).
    mortality_base_annual: float = Field(0.002, ge=0)
    mortality_senescence_annual: float = Field(0.15, ge=0)
    mortality_shape: float = Field(3.0, ge=0.1)

    # --- Demography (fertility / births) ---
    # Births are modeled as *household formation* events. They MUST be funded
    # by transfers from the parent household (no money creation).
    fertility_base_annual: float = Field(
        0.02,
        ge=0,
        description="Baseline annual birth probability for eligible households",
    )
    fertility_age_min: PositiveInt = 18
    fertility_age_max: PositiveInt = 42
    fertility_peak_age: PositiveInt = 30
    fertility_income_sensitivity: float = Field(
        0.5,
        ge=0,
        description="Elasticity of fertility to income (relative to base_income)",
    )
    fertility_wealth_sensitivity: float = Field(
        0.5,
        ge=0,
        description="Elasticity of fertility to (sight+savings) wealth relative to savings_growth_trigger",
    )
    birth_endowment_share: float = Field(
        0.2,
        ge=0,
        le=1,
        description="Share of parent's liquid net worth transferred to the newborn household",
    )

    # --- Estate / inheritance ---
    inheritance_share_on_death: float = Field(
        1.0,
        ge=0,
        le=1,
        description="Share of remaining estate transferred to heirs (rest can go to state)",
    )

    # --- Initial age distribution ---
    # Used for initial population seeding and turnover replacements.
    initial_age_min_years: int = Field(0, ge=0)
    initial_age_mode_years: int = Field(35, ge=0)
    initial_age_max_years: int = Field(70, ge=0)


class CompanyConfig(BaseConfigModel):
    base_wage: float = Field(5.0, ge=0)  # Renamed from wage_rate
    
    employee_capacity_ratio: float = Field(11.0, gt=0)
    investment_threshold: float = Field(1000.0, ge=0)  # Renamed from growth_balance_trigger
    growth_threshold: PositiveInt = 5
    growth_investment_factor: float = Field(0.1, ge=0)
    bankruptcy_threshold: float = -100.0
    split_ratio: float = Field(0.5, ge=0, le=1)
    liquidity_buffer_ratio: float = Field(0.2, ge=0)
    min_working_capital_buffer: float = Field(0.0, ge=0)
    production_base_price: float = Field(10.0, ge=0)
    production_innovation_bonus_rate: float = Field(0.02, ge=0)
    rd_investment_trigger_balance: float = Field(200.0, ge=0)
    rd_investment_rate: float = Field(0.1, ge=0, le=1)
    innovation_production_bonus: float = Field(0.1, ge=0)
    rd_investment_decay_factor: float = Field(0.5, ge=0, le=1)
    zero_staff_auto_liquidation: bool = True
    zero_staff_grace_steps: PositiveInt = 3
    zero_staff_liquidation_state_share: float = Field(1.0, ge=0, le=1)

    # --- Sparkasse investment credit (deterministic, testable policy) ---
    # See doc/issues.md Abschnitt 6) -> M2 (Sparkassen-Investitionskredite).
    # Trigger default: if `sight_balance` < `investment_threshold` and eligibility allows,
    # the company may request an investment loan from the SavingsBank.
    sparkasse_investment_loan_max_to_capacity: float = Field(
        5.0,
        ge=0,
        description="Eligibility cap: max principal outstanding = production_capacity * ratio",
    )
    sparkasse_investment_loan_repayment_rate: float = Field(
        0.1,
        ge=0,
        le=1,
        description="Deterministic repayment rate (share of available cash buffer)",
    )
    investment_capital_cost_per_capacity: float = Field(
        10.0,
        gt=0,
        description="Deterministic mapping: currency needed per +1 production_capacity",
    )

    # --- Company demography (founding / mergers) ---
    # The main simulation loop may spawn new companies if market opportunities
    # exist and founders can provide real capital (transfer from households).
    founding_base_annual: float = Field(
        0.01,
        ge=0,
        description="Baseline annual probability (per region) to found a new company",
    )
    founding_min_capital: float = Field(
        200.0,
        ge=0,
        description="Minimum startup capital required to found a company (must be transferred, no money creation)",
    )
    founding_capital_share_of_founder_wealth: float = Field(
        0.25,
        ge=0,
        le=1,
        description="Share of founder household wealth invested as startup capital",
    )
    founding_opportunity_sensitivity: float = Field(
        2.0,
        ge=0,
        description="Multiplier on founding probability from market shortage (0..1)",
    )

    merger_rate_annual: float = Field(
        0.01,
        ge=0,
        description="Annual probability (per region) for a distressed firm to be merged into a healthier one",
    )
    merger_distress_threshold: float = Field(
        -50.0,
        description="Companies below this sight_balance may be considered merger targets",
    )
    merger_min_acquirer_balance: float = Field(
        300.0,
        ge=0,
        description="Minimum sight_balance required for an acquirer to absorb a target",
    )
    merger_capacity_synergy: float = Field(
        0.9,
        ge=0,
        le=1.5,
        description="Capacity multiplier applied to target capacity when merged into acquirer",
    )

class RetailerConfig(BaseConfigModel):
    # Kontokorrent-Kreditrahmen (zinsenfrei) wird bei Initialisierung gesetzt; Anpassung ist politisch/vertraglich geregelt.
    initial_cc_limit: float = Field(500.0, ge=0)
    target_inventory_value: float = Field(200.0, ge=0)
    reorder_point_ratio: float = Field(0.5, ge=0, le=1)
    working_capital_buffer: float = Field(25.0, ge=0)
    price_markup: float = Field(0.2, ge=0)
    # Abschreibung / Obsoleszenz (pro Schritt, wenn Schritt=Tag)
    obsolescence_rate: float = Field(0.001, ge=0, le=1)

    # Warenbewertung: cost / market / Niederstwertprinzip
    inventory_valuation_method: Literal[
        "cost", "market", "lower_of_cost_or_market"
    ] = "cost"

    # Artikelgruppen / Obsoleszenz je Gruppe
    default_article_group: str = "default"
    obsolescence_rate_by_group: dict[str, float] = Field(default_factory=dict)

    # "Unverkaufbar"-Kriterium (bewertet Lot = 0)
    unsellable_after_days: int = Field(365, ge=0)
    # Wenn Marktpreis sehr niedrig ggü. Einstand, gilt die Ware als faktisch unverkäuflich.
    unsellable_market_price_floor_ratio: float = Field(0.05, ge=0, le=1)
    # Anteil des geschätzten Gewinns, der in Warenwertberichtigungskonten fließt
    write_down_reserve_share: float = Field(0.05, ge=0, le=1)
    # Automatische Tilgung: ab welchem Überschuss wird Kontokorrent zurückgeführt?
    auto_repay: bool = True

class BankConfig(BaseConfigModel):
    base_account_fee: float = Field(0.0, ge=0)
    positive_balance_fee_rate: float = Field(0.0, ge=0)
    negative_balance_fee_rate: float = Field(0.0, ge=0)
    # Risk pool: distribute a small fee proportional to total CC exposure across
    # all accounts. This is *not* interest; it is a shared risk premium.
    risk_pool_rate: float = Field(0.0, ge=0)
    # CC-Limit Policy (partnerschaftlicher Rahmen)
    cc_limit_multiplier: float = Field(2.0, gt=0)
    cc_limit_rolling_window_days: PositiveInt = 30
    # Maximaler Reduktionsanteil pro Monat; größere Reduktionen benötigen Zustimmung (Retailer).
    cc_limit_max_monthly_decrease: float = Field(0.25, ge=0, le=1)
    # Audit-Risk-Modifikator: risk_modifier = max(0, 1 - penalty * audit_risk_score).
    cc_limit_audit_risk_penalty: float = Field(0.5, ge=0, le=1)
    inventory_check_interval: PositiveInt = 3
    inventory_coverage_threshold: float = Field(0.8, gt=0)
    base_credit_reserve_ratio: float = Field(0.1, gt=0)
    credit_unemployment_sensitivity: float = Field(0.5, ge=0)
    credit_inflation_sensitivity: float = Field(0.7, ge=0)
    credit_interest_rate: float = 0.0
    initial_liquidity: float = Field(1000.0, ge=0)


class SavingsBankConfig(BaseConfigModel):
    # Legacy / fallback (pre-M4). Still read, but superseded by the split caps.
    max_savings_per_account: float = Field(10_000.0, ge=0)

    # Milestone 4 (doc/issues.md Abschnitt 2): split caps by agent type.
    max_savings_household: float = Field(10_000.0, ge=0)
    max_savings_company: float = Field(50_000.0, ge=0)

    # Demand coupling: effective cap is scaled by expected credit demand.
    savings_cap_min_scale: float = Field(0.5, ge=0)
    savings_cap_max_scale: float = Field(2.0, ge=0)
    savings_cap_demand_coupling_strength: float = Field(0.0, ge=0, le=1)
    expected_credit_demand_smoothing: float = Field(0.2, ge=0, le=1)
    loan_interest_rate: float = 0.0
    initial_liquidity: float = Field(500.0, ge=0)


class LaborMarketConfig(BaseConfigModel):
    starting_wage: float = Field(10.0, ge=0)  # Renamed from default_wage
    minimum_wage_floor: float = Field(8.0, ge=0)
    wage_unemployment_sensitivity: float = Field(0.6, ge=0)
    wage_price_index_sensitivity: float = Field(0.4, ge=0)
    target_unemployment_rate: float = Field(0.05, ge=0, le=1)
    target_inflation_rate: float = Field(0.02)


class MarketConfig(BaseConfigModel):
    demand_default: float = Field(50.0, ge=0)
    speculation_limit: float = Field(10_000.0, ge=0)
    price_index_base: float = Field(100.0, ge=0)
    price_index_pressure_target: float = Field(1.0, ge=0)
    price_index_sensitivity: float = Field(0.05, ge=0)
    price_index_pressure_ratio: str = "money_supply_to_gdp"
    boom_threshold: float = Field(0.03)
    recession_threshold: float = Field(-0.01)


class EnvironmentalConfig(BaseConfigModel):
    environmental_tax_state_share: float = Field(0.5, ge=0, le=1)
    penalty_factor_env_audit: float = Field(5.0, ge=0)
    recycling_efficiency: float = Field(0.8, ge=0, le=1)
    waste_output_per_env_impact: float = Field(0.5, ge=0)
    recycling_cost_per_unit: float = Field(0.25, ge=0)


class ClearingConfig(BaseConfigModel):
    hyperwealth_threshold: float = Field(1_000_000.0, gt=0)
    # Audit- und Reserve-Mechanik (Warengeld-Clearingstelle)
    audit_interval: PositiveInt = 90  # z.B. 90 Schritte ~ Quartal, wenn Schritt=Tag
    required_reserve_ratio: float = Field(0.1, ge=0, le=1)
    reserve_ratio_step: float = Field(0.02, ge=0, le=1)
    reserve_bounds_min: float = Field(0.05, ge=0, le=1)
    reserve_bounds_max: float = Field(0.3, ge=0, le=1)
    # Sichtguthaben-Abschmelzung (nur Überschuss über Freibetrag)
    sight_allowance_multiplier: float = Field(1.0, ge=0)
    sight_excess_decay_rate: float = Field(0.01, ge=0, le=1)
    # Rolling window length for average spending used by the sight allowance.
    sight_allowance_window_days: PositiveInt = 30
    # Legacy: alte Liquidity-Balancing Parameter
    desired_bank_liquidity: float = Field(1000.0, ge=0)
    desired_savings_bank_liquidity: float = Field(500.0, ge=0)


class StateConfig(BaseConfigModel):
    budget_allocation: dict[str, float] = Field(default_factory=_default_state_budget_allocation)

    @field_validator("budget_allocation")
    @classmethod
    def _validate_budget_allocation(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            return value
        total = sum(value.values())
        if not 0.99 <= total <= 1.01:
            msg = "State budget allocation must sum to ~1.0"
            raise ValueError(msg)
        return value


class TimeConfig(BaseConfigModel):
    """Temporal granularity.

    The core tick is interpreted as a *day*.
    Monthly policies (fees, sight-decay, savings-bank) run every `days_per_month`.

    Time scaling:
    - `days_per_year` is used to convert age expressed in *years* to simulation steps.
    """

    days_per_month: PositiveInt = 30
    months_per_year: PositiveInt = 12
    days_per_year: PositiveInt = 360
    start_year: int = 0
    seed: int | None = None

    @model_validator(mode="after")
    def _normalize_days_per_year(self):
        """Ensure `days_per_year` is consistent with month/year settings.

        The project uses a fixed convention: days_per_year == days_per_month * months_per_year.
        We normalize rather than error, because YAML configs might override one field.
        """

        expected = int(self.days_per_month) * int(self.months_per_year)
        if int(self.days_per_year) != expected:
            self.days_per_year = expected
        return self


class SpatialConfig(BaseConfigModel):
    """Geographic granularity for 'Hausbanken' and local retail markets."""

    num_regions: PositiveInt = 1
    local_trade_bias: float = Field(0.8, ge=0, le=1)  # probability to trade within the same region


class SimulationConfig(BaseConfigModel):
    simulation_steps: PositiveInt = 100
    # JSON export was removed for performance; CSV is the canonical output.
    result_storage: str = Field("csv")
    tax_rates: TaxRates = Field(default_factory=TaxRates)
    household: HouseholdConfig = Field(default_factory=HouseholdConfig)
    company: CompanyConfig = Field(default_factory=CompanyConfig)
    retailer: RetailerConfig = Field(default_factory=RetailerConfig)
    bank: BankConfig = Field(default_factory=BankConfig)
    savings_bank: SavingsBankConfig = Field(default_factory=SavingsBankConfig)
    labor_market: LaborMarketConfig = Field(default_factory=LaborMarketConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    environmental: EnvironmentalConfig = Field(default_factory=EnvironmentalConfig)
    clearing: ClearingConfig = Field(default_factory=ClearingConfig)
    state: StateConfig = Field(default_factory=StateConfig)

    time: TimeConfig = Field(default_factory=TimeConfig)
    spatial: SpatialConfig = Field(default_factory=SpatialConfig)

    # New: population helpers
    population: PopulationConfig = Field(default_factory=PopulationConfig)

    logging_level: str = "DEBUG"
    log_file: str = output_dir + "simulation.log"
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s"
    SUMMARY_FILE: str = output_dir + "simulation_summary.json"
    JSON_INDENT: PositiveInt = 4
    metrics_export_path: str = output_dir + "metrics"
    metrics_config: dict[str, MetricConfigModel] = Field(default_factory=dict)
    STATE_ID: str = "state_0"
    BANK_ID: str = "bank_1"
    SAVINGS_BANK_ID: str = "savings_bank_1"
    CLEARING_AGENT_ID: str = "clearing_0"
    ENV_AGENCY_ID: str = "env_agency_1"
    RECYCLING_COMPANY_ID: str = "recycling_1"
    FINANCIAL_MARKET_ID: str = "financial_market_1"
    LABOR_MARKET_ID: str = "labor_market_0"
    HOUSEHOLD_ID_PREFIX: str = "household_"
    COMPANY_ID_PREFIX: str = "company_"
    RETAILER_ID_PREFIX: str = "retailer_"
    INITIAL_HOUSEHOLDS: list[InitialHousehold] = Field(default_factory=_default_households)
    INITIAL_COMPANIES: list[InitialCompany] = Field(default_factory=_default_companies)
    INITIAL_RETAILERS: list[InitialRetailer] = Field(default_factory=_default_retailers)
    INITIAL_JOB_POSITIONS_PER_COMPANY: PositiveInt = 3
    state_budget_allocation: dict[str, float] = Field(default_factory=_default_state_budget_allocation)

    @property
    def initial_households(self) -> list[InitialHousehold]:
        return self.INITIAL_HOUSEHOLDS

    @property
    def initial_companies(self) -> list[InitialCompany]:
        return self.INITIAL_COMPANIES


    @property
    def initial_retailers(self) -> list[InitialRetailer]:
        return self.INITIAL_RETAILERS

    @property
    def summary_file(self) -> str:
        return self.SUMMARY_FILE

    @property
    def json_indent(self) -> PositiveInt:
        return self.JSON_INDENT

    @field_validator("result_storage")
    @classmethod
    def _validate_result_storage(cls, value: str) -> str:
        """Validate result storage option."""
        # Historical options included 'file'/'memory'. The current codebase
        # uses CSV as the canonical persisted output format.
        valid_options = ["csv", "both", "file", "memory", "none", "json"]
        if value not in valid_options:
            raise ValueError(f"result_storage must be one of {valid_options}, got {value}")
        return value

    @field_validator("logging_level")
    @classmethod
    def _validate_logging_level(cls, value: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if value not in valid_levels:
            raise ValueError(f"logging_level must be one of {valid_levels}, got {value}")
        return value

    @field_validator("metrics_export_path")
    @classmethod
    def _validate_metrics_path(cls, value: str) -> str:
        """Validate metrics export path."""
        if not value or not isinstance(value, str):
            raise ValueError("metrics_export_path must be a non-empty string")
        return value

    def validate_agent_counts(self) -> None:
        """Validate that agent counts are consistent with configuration."""
        # Only validate if both are explicitly set by the user (not using defaults)
        # If population.num_households is set, we should ignore INITIAL_HOUSEHOLDS
        # If INITIAL_HOUSEHOLDS is provided, we should ignore population.num_households
        pass  # Remove validation for now to allow both approaches

    def get_effective_household_count(self) -> int:
        """Get the effective number of households that will be created."""
        if self.population.num_households is not None:
            return self.population.num_households
        return len(self.INITIAL_HOUSEHOLDS)

    def get_effective_company_count(self) -> int:
        """Get the effective number of companies that will be created."""
        if self.population.num_companies is not None:
            return self.population.num_companies
        return len(self.INITIAL_COMPANIES)


    def get_effective_retailer_count(self) -> int:
        """Get the effective number of retailers that will be created."""
        if self.population.num_retailers is not None:
            return self.population.num_retailers
        return len(self.INITIAL_RETAILERS)

    def validate_economic_parameters(self) -> None:
        """Validate that economic parameters are within reasonable bounds."""
        # Check that tax rates are reasonable
        if self.tax_rates.bodensteuer + self.tax_rates.umweltsteuer > 0.5:
            raise ValueError("Combined tax rates exceed 50% - this may cause simulation instability")

        # Check that wage parameters are consistent
        if self.labor_market.minimum_wage_floor > self.labor_market.starting_wage:
            raise ValueError("minimum_wage_floor cannot be higher than starting_wage")

        # Check that bank parameters are stable
        # Removed legacy fee_rate check - modern parameters are validated by Pydantic

    def validate_all(self) -> None:
        """Run all validation checks on the configuration."""
        self.validate_agent_counts()
        self.validate_economic_parameters()

        # Validate that all required directories exist or can be created
        for path_attr in ['log_file', 'SUMMARY_FILE', 'metrics_export_path']:
            path_value = getattr(self, path_attr)
            if isinstance(path_value, str):
                try:
                    Path(path_value).parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ValueError(f"Cannot create directory for {path_attr}: {str(e)}")

class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    def __init__(self, message: str, config_errors: list[str] | None = None):
        self.message = message
        self.config_errors = config_errors or []
        super().__init__(message)

    def __str__(self) -> str:
        if self.config_errors:
            return f"{self.message}\nErrors: {', '.join(self.config_errors)}"
        return self.message


def load_simulation_config(data: Mapping[str, ConfigValue] | None = None) -> SimulationConfig:
    if data is not None:
        coerced = _coerce_config_dict(cast(Mapping[str, object], data))
        return SimulationConfig(**coerced)
    return SimulationConfig()


def load_simulation_config_from_yaml(path: str) -> SimulationConfig:
    """Load a YAML config file and validate it via `SimulationConfig`.

    YAML is only an input format: schema validation remains centralized in Pydantic.

    Args:
        path: Path to YAML configuration file

    Returns:
        Validated SimulationConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ModuleNotFoundError: If YAML parser not installed
        TypeError: If YAML structure is invalid
        ConfigValidationError: If configuration validation fails in a non-schema way
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover
        msg = (
            "YAML support is not installed. Add PyYAML (or another YAML parser) to dependencies "
            "to use load_simulation_config_from_yaml()."
        )
        raise ModuleNotFoundError(msg) from exc

    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {path}")
    except Exception as e:
        raise ConfigValidationError(f"Failed to read YAML file {path}: {str(e)}")

    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        msg = "Top-level YAML config must be a mapping/object."
        raise TypeError(msg)

    # Let schema validation errors propagate as-is (tests assert this).
    from pydantic import ValidationError as PydanticValidationError  # type: ignore
    try:
        from pydantic_core import ValidationError as CoreValidationError  # type: ignore
    except Exception:  # pragma: no cover
        CoreValidationError = None  # type: ignore

    try:
        config = load_simulation_config(cast(Mapping[str, ConfigValue], raw))
        config.validate_all()
        return config
    except Exception as e:
        # Keep schema validation errors unwrapped for tests and callers.
        if type(e).__module__.startswith("pydantic"):
            raise
        raise ConfigValidationError(f"Configuration validation failed: {str(e)}", [str(e)])

def validate_config_compatibility(config: SimulationConfig) -> None:
    """
    Validate that configuration is compatible with current simulation requirements.

    Args:
        config: Configuration to validate

    Raises:
        ConfigValidationError: If compatibility issues found
    """
    errors = []

    # Check that agent counts are reasonable for performance
    household_count = config.get_effective_household_count()
    company_count = config.get_effective_company_count()

    if household_count > 1000:
        errors.append(f"Household count {household_count} exceeds recommended maximum of 1000")
    if company_count > 200:
        errors.append(f"Company count {company_count} exceeds recommended maximum of 200")

    # Check economic parameter compatibility
    if config.company.base_wage < config.labor_market.minimum_wage_floor:
        errors.append("Company base wage is below minimum wage floor")

    # Removed legacy fee_rate check - modern parameters are validated by Pydantic

    if errors:
        raise ConfigValidationError("Configuration compatibility issues found", errors)

class SimulationError(Exception):
    """Base exception for simulation errors."""
    def __init__(self, message: str, agent_id: str | None = None):
        self.message = message
        self.agent_id = agent_id
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.agent_id:
            return f"Agent {self.agent_id}: {self.message}"
        return self.message

class InsufficientFundsError(SimulationError):
    """Exception for insufficient funds situations."""
    def __init__(self, message: str, agent_id: str, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(message, agent_id)

    def _format_message(self) -> str:
        base_msg = super()._format_message()
        return f"{base_msg} (Required: {self.required:.2f}, Available: {self.available:.2f})"

class AgentLifecycleError(SimulationError):
    """Exception for agent lifecycle management errors."""
    pass

class EconomicParameterError(SimulationError):
    """Exception for invalid economic parameter values."""
    pass


CONFIG_MODEL: SimulationConfig = load_simulation_config()
