from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError, field_validator

# config.py
output_dir = "output/"


class TaxRates(BaseModel):
    bodensteuer: float = Field(0.05, ge=0, le=1)
    umweltsteuer: float = Field(0.02, ge=0, le=1)


class AssetPriceMap(BaseModel):
    model_config = ConfigDict(extra="allow")


class InitialHousehold(BaseModel):
    income: float = Field(ge=0)
    land_area: float = Field(ge=0)
    environmental_impact: float = Field(ge=0)


class InitialCompany(BaseModel):
    production_capacity: float = Field(ge=0)
    land_area: float = Field(ge=0)
    environmental_impact: float = Field(ge=0)


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
    enabled: bool = True
    display_name: str = ""
    unit: str = ""
    aggregation: Literal["sum", "mean", "median", "min", "max", "value"] = "mean"
    critical_threshold: float | None = None


class SimulationConfig(BaseModel):
    model_config = ConfigDict(validate_default=True, frozen=False)

    simulation_steps: PositiveInt = 100
    tax_rates: TaxRates = Field(default_factory=TaxRates)
    environmental_tax_state_share: float = Field(0.5, ge=0, le=1)
    credit_interest_rate: float = Field(0.0)
    result_storage: str = Field("both")
    bank_fee_rate: float = Field(0.01, ge=0)
    inventory_check_interval: PositiveInt = 3
    initial_bank_liquidity: float = Field(1000.0, ge=0)
    inventory_coverage_threshold: float = Field(0.8, gt=0)
    hyperwealth_threshold: float = Field(1_000_000, gt=0)
    growth_threshold: PositiveInt = 5
    growth_balance_trigger: float = Field(1000, ge=0)
    growth_investment_factor: float = Field(0.1, ge=0)
    bankruptcy_threshold: float = -100
    default_wage: float = Field(10, ge=0)
    wage_rate: float = Field(5, ge=0)
    minimum_wage_floor: float = Field(8, ge=0)
    wage_unemployment_sensitivity: float = Field(0.6, ge=0)
    wage_price_index_sensitivity: float = Field(0.4, ge=0)
    target_unemployment_rate: float = Field(0.05, ge=0, le=1)
    target_inflation_rate: float = Field(0.02)
    bank_base_credit_reserve_ratio: float = Field(0.1, gt=0)
    bank_credit_unemployment_sensitivity: float = Field(0.5, ge=0)
    bank_credit_inflation_sensitivity: float = Field(0.7, ge=0)
    max_age: PositiveInt = 80
    max_generation: PositiveInt = 3
    savings_growth_trigger: float = Field(500.0, ge=0)
    household_consumption_rate_normal: float = Field(0.7, ge=0, le=1)
    household_consumption_rate_growth: float = Field(0.9, ge=0, le=1)
    rd_investment_trigger_balance: float = Field(200, ge=0)
    rd_investment_rate: float = Field(0.1, ge=0, le=1)
    innovation_production_bonus: float = Field(0.1, ge=0)
    rd_investment_decay_factor: float = Field(0.5, ge=0, le=1)
    employee_capacity_ratio: float = Field(11.0, gt=0)
    company_split_ratio: float = Field(0.5, ge=0, le=1)
    company_liquidity_buffer_ratio: float = Field(0.2, ge=0)
    min_working_capital_buffer: float = Field(0.0, ge=0)
    production_base_price: float = Field(10, ge=0)
    production_innovation_bonus_rate: float = Field(0.02, ge=0)
    demand_default: float = Field(50, ge=0)
    recycling_efficiency: float = Field(0.8, ge=0, le=1)
    desired_bank_liquidity: float = Field(1000, ge=0)
    desired_sparkassen_liquidity: float = Field(500, ge=0)
    penalty_factor_env_audit: float = Field(5, ge=0)
    speculation_limit: float = Field(10_000, ge=0)
    asset_initial_prices: AssetPriceMap = Field(default_factory=AssetPriceMap)
    asset_bid_ask_spreads: AssetPriceMap = Field(default_factory=AssetPriceMap)
    max_savings_per_account: float = Field(10_000, ge=0)
    loan_interest_rate: float = Field(0.0)
    logging_level: str = "DEBUG"
    log_file: str = output_dir + "simulation.log"
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s"
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
    SUMMARY_FILE: str = output_dir + "simulation_summary.json"
    JSON_INDENT: PositiveInt = 4
    metrics_export_path: str = output_dir + "metrics"
    price_index_base: float = Field(100.0, ge=0)
    price_index_pressure_target: float = Field(1.0, ge=0)
    price_index_sensitivity: float = Field(0.05, ge=0)
    price_index_pressure_ratio: str = "money_supply_to_gdp"
    state_budget_allocation: dict[str, float] = Field(default_factory=_default_state_budget_allocation)
    metrics_config: dict[str, MetricConfigModel] = Field(default_factory=dict)

    @property
    def initial_households(self) -> list[InitialHousehold]:
        return self.INITIAL_HOUSEHOLDS

    @property
    def initial_companies(self) -> list[InitialCompany]:
        return self.INITIAL_COMPANIES

    @field_validator("state_budget_allocation")
    @classmethod
    def _validate_budget_allocation(
        cls, value: dict[str, float]
    ) -> dict[str, float]:
        if not value:
            return value
        total = sum(value.values())
        if not 0.99 <= total <= 1.01:
            msg = "State budget allocation must sum to ~1.0"
            raise ValueError(msg)
        return value


class MutableConfigDict(MutableMapping[str, ConfigValue]):
    """Mutable mapping providing backward-compatible dict access to the config."""

    def __init__(self, model: SimulationConfig) -> None:
        self._model = model
        self._data: dict[str, ConfigValue] = _coerce_config_dict(model.model_dump())

    def _refresh_model(self) -> None:
        try:
            refreshed = SimulationConfig(**self._data)
        except ValidationError:
            return
        self._model.__dict__.update(refreshed.__dict__)
        self._data = _coerce_config_dict(refreshed.model_dump())

    def __getitem__(self, key: str) -> ConfigValue:
        return self._data[key]

    def __setitem__(self, key: str, value: ConfigValue) -> None:
        self._data[key] = _coerce_value(value)
        self._refresh_model()

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._refresh_model()

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:  # type: ignore[override]
        self._data.clear()
        self._refresh_model()

    def pop(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None:  # type: ignore[override]
        value = self._data.pop(key, default)
        self._refresh_model()
        return value

    def popitem(self) -> tuple[str, ConfigValue]:  # type: ignore[override]
        item = self._data.popitem()
        self._refresh_model()
        return item

    def update(  # type: ignore[override]
        self,
        other: Mapping[str, ConfigValue] | None = None,
        **kwargs: ConfigValue,
    ) -> None:
        if other is not None:
            for key, value in other.items():
                self._data[key] = _coerce_value(value)
        for key, value in kwargs.items():
            self._data[key] = _coerce_value(value)
        self._refresh_model()

    def setdefault(self, key: str, default: ConfigValue | None = None) -> ConfigValue:  # type: ignore[override]
        if key not in self._data:
            self._data[key] = _coerce_value(default)
            self._refresh_model()
        return self._data[key]

    def sync_to_model(self) -> None:
        self._refresh_model()

    def copy(self) -> dict[str, ConfigValue]:  # type: ignore[override]
        return copy.deepcopy(self._data)

    def __copy__(self) -> dict[str, ConfigValue]:
        return self.copy()

    def __deepcopy__(self, memo: dict[int, object]) -> dict[str, ConfigValue]:
        return copy.deepcopy(self._data, memo)


def load_simulation_config(data: Mapping[str, ConfigValue] | None = None) -> SimulationConfig:
    if data is not None:
        coerced = _coerce_config_dict(cast(Mapping[str, object], data))
        return SimulationConfig(**coerced)
    return SimulationConfig()


CONFIG_MODEL: SimulationConfig = load_simulation_config()
CONFIG: MutableConfigDict = MutableConfigDict(CONFIG_MODEL)
