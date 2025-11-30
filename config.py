from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
)

output_dir = "output/"


class TaxRates(BaseModel):
    bodensteuer: float = Field(0.05, ge=0, le=1)
    umweltsteuer: float = Field(0.02, ge=0, le=1)


class InitialHousehold(BaseModel):
    income: float = Field(ge=0)
    land_area: float = Field(ge=0)
    environmental_impact: float = Field(ge=0)


class InitialCompany(BaseModel):
    production_capacity: float = Field(ge=0)
    land_area: float = Field(ge=0)
    environmental_impact: float = Field(ge=0)


def _default_households() -> list[dict[str, float]]:
    return [
        {"income": 100, "land_area": 50, "environmental_impact": 1},
        {"income": 120, "land_area": 60, "environmental_impact": 2},
        {"income": 110, "land_area": 70, "environmental_impact": 2},
        {"income": 80, "land_area": 40, "environmental_impact": 1},
    ]


def _default_companies() -> list[dict[str, float]]:
    return [
        {"production_capacity": 100, "land_area": 100, "environmental_impact": 5},
        {"production_capacity": 80, "land_area": 80, "environmental_impact": 4},
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

    def items(self) -> Mapping[str, float].items:
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


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(validate_default=True, frozen=False)


class HouseholdConfig(BaseConfigModel):
    max_age: PositiveInt = 80
    max_generation: PositiveInt = 3
    base_income: float = Field(100.0, ge=0)
    growth_threshold: PositiveInt = 5
    consumption_rate_normal: float = Field(0.7, ge=0, le=1)
    consumption_rate_growth: float = Field(0.9, ge=0, le=1)
    savings_growth_trigger: float = Field(500.0, ge=0)
    loan_repayment_rate: float = Field(0.25, ge=0, le=1)
    child_rearing_cost: float = Field(200.0, ge=0)


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


class BankConfig(BaseConfigModel):
    fee_rate: float = Field(0.01, ge=0)
    inventory_check_interval: PositiveInt = 3
    inventory_coverage_threshold: float = Field(0.8, gt=0)
    base_credit_reserve_ratio: float = Field(0.1, gt=0)
    credit_unemployment_sensitivity: float = Field(0.5, ge=0)
    credit_inflation_sensitivity: float = Field(0.7, ge=0)
    credit_interest_rate: float = 0.0
    initial_liquidity: float = Field(1000.0, ge=0)


class SavingsBankConfig(BaseConfigModel):
    max_savings_per_account: float = Field(10_000.0, ge=0)
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


class SimulationConfig(BaseConfigModel):
    simulation_steps: PositiveInt = 100
    result_storage: str = Field("both")
    tax_rates: TaxRates = Field(default_factory=TaxRates)
    household: HouseholdConfig = Field(default_factory=HouseholdConfig)
    company: CompanyConfig = Field(default_factory=CompanyConfig)
    bank: BankConfig = Field(default_factory=BankConfig)
    savings_bank: SavingsBankConfig = Field(default_factory=SavingsBankConfig)
    labor_market: LaborMarketConfig = Field(default_factory=LaborMarketConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    environmental: EnvironmentalConfig = Field(default_factory=EnvironmentalConfig)
    clearing: ClearingConfig = Field(default_factory=ClearingConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    logging_level: str = "DEBUG"
    log_file: str = output_dir + "simulation.log"
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s"
    SUMMARY_FILE: str = output_dir + "simulation_summary.json"
    JSON_INDENT: PositiveInt = 4
    metrics_export_path: str = output_dir + "metrics"
    metrics_config: dict[str, MetricConfigModel] = Field(default_factory=dict)
    STATE_ID: str = "state_1"
    BANK_ID: str = "bank_1"
    SAVINGS_BANK_ID: str = "savings_bank_1"
    CLEARING_AGENT_ID: str = "clearing_1"
    ENV_AGENCY_ID: str = "env_agency_1"
    RECYCLING_COMPANY_ID: str = "recycling_1"
    FINANCIAL_MARKET_ID: str = "financial_market_1"
    LABOR_MARKET_ID: str = "labor_market_1"
    HOUSEHOLD_ID_PREFIX: str = "household_"
    COMPANY_ID_PREFIX: str = "company_"
    INITIAL_HOUSEHOLDS: list[InitialHousehold] = Field(default_factory=_default_households)
    INITIAL_COMPANIES: list[InitialCompany] = Field(default_factory=_default_companies)
    INITIAL_JOB_POSITIONS_PER_COMPANY: PositiveInt = 3
    state_budget_allocation: dict[str, float] = Field(default_factory=_default_state_budget_allocation)

    @property
    def initial_households(self) -> list[InitialHousehold]:
        return self.INITIAL_HOUSEHOLDS

    @property
    def initial_companies(self) -> list[InitialCompany]:
        return self.INITIAL_COMPANIES

    @property
    def summary_file(self) -> str:
        return self.SUMMARY_FILE

    @property
    def json_indent(self) -> PositiveInt:
        return self.JSON_INDENT


def load_simulation_config(data: Mapping[str, ConfigValue] | None = None) -> SimulationConfig:
    if data is not None:
        coerced = _coerce_config_dict(cast(Mapping[str, object], data))
        return SimulationConfig(**coerced)
    return SimulationConfig()


CONFIG_MODEL: SimulationConfig = load_simulation_config()
