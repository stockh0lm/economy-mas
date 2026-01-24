import copy
import math
from typing import Any

from agents.company_agent import Company
from agents.household_agent import Household
from config import SimulationConfig, load_simulation_config

BASE_CONFIG = SimulationConfig().model_dump(mode="python")
DEFAULT_WAGE = SimulationConfig().labor_market.starting_wage


def build_config(overrides: dict[str, Any] | None = None) -> SimulationConfig:
    data = copy.deepcopy(BASE_CONFIG)
    if overrides:
        for path, value in overrides.items():
            cursor = data
            parts = path.split(".")
            for part in parts[:-1]:
                next_node = cursor.setdefault(part, {})
                if not isinstance(next_node, dict):
                    next_node = {}
                    cursor[part] = next_node
                cursor = next_node
            cursor[parts[-1]] = value
    return load_simulation_config(data)


class StubLaborMarket:
    def __init__(self, default_wage: float | None = None) -> None:
        self.default_wage = default_wage if default_wage is not None else DEFAULT_WAGE
        self.job_offers: list[tuple[str, float, int]] = []
        self.released_workers: list[str] = []

    def register_job_offer(self, employer: Company, wage: float, positions: int) -> None:  # type: ignore[override]
        self.job_offers.append((employer.unique_id, wage, positions))

    def release_worker(self, worker: Household) -> None:  # type: ignore[override]
        self.released_workers.append(worker.unique_id)


class StubState:
    def __init__(self, labor_market: StubLaborMarket) -> None:
        self.labor_market = labor_market


class StubWarengeldBank:
    def __init__(self) -> None:
        self.credit_lines: dict[str, float] = {}
        self.grant_calls: list[float] = []
        self.process_calls: list[float] = []

    def grant_credit(self, merchant: Company, amount: float) -> float:
        self.grant_calls.append(amount)
        merchant_id = merchant.unique_id
        self.credit_lines[merchant_id] = self.credit_lines.get(merchant_id, 0.0) + amount
        merchant.request_funds_from_bank(amount)
        return amount

    def process_repayment(self, merchant: Company, amount: float) -> float:
        merchant_id = merchant.unique_id
        outstanding = self.credit_lines.get(merchant_id, 0.0)
        repaid = min(amount, outstanding)
        self.credit_lines[merchant_id] = max(0.0, outstanding - repaid)
        self.process_calls.append(repaid)
        return repaid


class StubSavingsBank:
    def __init__(self) -> None:
        self.allocate_calls: list[float] = []

    def allocate_credit(self, borrower: Company, amount: float) -> float:
        if amount <= 0:
            return 0.0
        self.allocate_calls.append(amount)
        borrower.request_funds_from_bank(amount)
        return amount


class IntegrationState(StubState):
    def __init__(self, labor_market: StubLaborMarket) -> None:
        super().__init__(labor_market)
        self.tax_revenue = 0.0
        self.taxes_collected: list[float] = []

    def collect_taxes(self, amount: float) -> None:
        self.tax_revenue += amount
        self.taxes_collected.append(amount)


class IntegrationWarengeldBank(StubWarengeldBank):
    def __init__(self) -> None:
        super().__init__()
        self.inventory_checks: list[float] = []

    def check_inventories(self, merchants: list[Company]) -> None:
        for merchant in merchants:
            self.inventory_checks.append(merchant.finished_goods_units)


class IntegrationSavingsBank(StubSavingsBank):
    def __init__(self) -> None:
        super().__init__()
        self.repayments: list[float] = []

    def repayment(self, borrower: Company, amount: float) -> float:
        self.repayments.append(amount)
        return amount


def test_company_step_handles_credit_growth_and_split() -> None:
    overrides = {
        "company.liquidity_buffer_ratio": 0.2,
        "company.investment_threshold": 1.0,
        "company.growth_threshold": 1,
        "company.min_working_capital_buffer": 0.0,
        "company.growth_investment_factor": 0.1,
        "labor_market.starting_wage": 5.0,
    }
    cfg = build_config(overrides)
    company = Company("company_step_regress", production_capacity=110.0, max_employees=10, config=cfg)
    employees = [Household("emp_a", config=cfg), Household("emp_b", config=cfg)]
    default_wage = cfg.labor_market.starting_wage
    for employee in employees:
        employee.current_wage = default_wage
        employee.employed = True
    initial_balance = 10.0
    company.employees = employees
    company.sight_balance = initial_balance
    initial_employee_count = len(employees)
    labor_market = StubLaborMarket(cfg.labor_market.starting_wage)
    state = StubState(labor_market)
    warengeld_bank = StubWarengeldBank()
    savings_bank = StubSavingsBank()

    new_company = company.step(
        current_step=1,
        state=state,
        warengeld_bank=warengeld_bank,
        savings_bank=savings_bank,
    )

    assert isinstance(new_company, Company)
    assert new_company.unique_id == "company_step_regress_g1"

    employee_capacity_ratio = cfg.company.employee_capacity_ratio
    required_employees = int(company.production_capacity / employee_capacity_ratio)
    expected_positions = min(
        max(0, required_employees - initial_employee_count),
        company.max_employees - initial_employee_count,
    )
    
    # Original company registers job offers
    expected_offers = [(company.unique_id, labor_market.default_wage, expected_positions)]
    # New spinoff company also registers initial job offers (default positions)
    initial_positions = cfg.INITIAL_JOB_POSITIONS_PER_COMPANY
    expected_offers.append((new_company.unique_id, labor_market.default_wage, initial_positions))

    # Sort both lists to ensure consistent comparison regardless of order
    assert sorted(labor_market.job_offers) == sorted(expected_offers)

    planned_wage_bill = sum(getattr(worker, "current_wage", default_wage) for worker in employees)
    buffer_ratio = cfg.company.liquidity_buffer_ratio
    target_liquidity = planned_wage_bill * (1 + buffer_ratio)
    expected_credit = max(0.0, target_liquidity - initial_balance)

    assert len(warengeld_bank.grant_calls) == 1
    assert math.isclose(warengeld_bank.grant_calls[0], expected_credit, rel_tol=1e-9)

    assert len(warengeld_bank.process_calls) == 1
    assert math.isclose(
        warengeld_bank.process_calls[0],
        warengeld_bank.grant_calls[0],
        rel_tol=1e-9,
    )
    assert math.isclose(warengeld_bank.credit_lines[company.unique_id], 0.0, rel_tol=1e-9)

    assert len(savings_bank.allocate_calls) == 1
    expected_growth_credit = company.production_capacity * cfg.company.growth_investment_factor
    assert math.isclose(savings_bank.allocate_calls[0], expected_growth_credit, rel_tol=1e-9)

    assert company.growth_phase is False
    assert company.growth_counter == 0


def test_company_step_without_employees_skips_credit_and_production() -> None:
    cfg = build_config(
        {
            "company.rd_investment_trigger_balance": 500.0,
            "company.investment_threshold": 10_000.0,
        }
    )
    company = Company("company_no_workers", production_capacity=80.0, max_employees=5, config=cfg)
    company.employees = []
    company.sight_balance = 50.0

    class PassiveWarengeldBank(StubWarengeldBank):
        def grant_credit(self, merchant: Company, amount: float) -> float:  # type: ignore[override]
            super().grant_credit(merchant, amount)
            return 0.0

    warengeld_bank = PassiveWarengeldBank()
    new_company = company.step(current_step=2, state=None, warengeld_bank=warengeld_bank)

    assert new_company is None
    assert warengeld_bank.grant_calls == []
    assert math.isclose(company.finished_goods_units, 0.0)


def test_company_step_returns_dead_when_bankrupt() -> None:
    cfg = build_config({"company.bankruptcy_threshold": -5.0})
    company = Company("company_bankrupt", production_capacity=50.0, config=cfg)
    company.sight_balance = -10.0

    result = company.step(current_step=3)

    assert result == "DEAD"


def test_company_step_handles_credit_denial_gracefully() -> None:
    cfg = build_config(
        {
            "company.liquidity_buffer_ratio": 0.3,
            "company.investment_threshold": 10_000.0,
            "labor_market.starting_wage": 5.0,
        }
    )
    company = Company("company_credit_denied", production_capacity=90.0, max_employees=10, config=cfg)
    employees = [Household("emp_x", config=cfg), Household("emp_y", config=cfg)]
    wage = cfg.labor_market.starting_wage
    for worker in employees:
        worker.current_wage = wage
        worker.employed = True
    company.employees = employees
    company.sight_balance = 0.0

    class DenyingWarengeldBank(StubWarengeldBank):
        def grant_credit(self, merchant: Company, amount: float) -> float:  # type: ignore[override]
            self.grant_calls.append(amount)
            return 0.0

    labor_market = StubLaborMarket(cfg.labor_market.starting_wage)
    state = StubState(labor_market)
    warengeld_bank = DenyingWarengeldBank()

    new_company = company.step(4, state=state, warengeld_bank=warengeld_bank)

    assert new_company is None
    assert warengeld_bank.credit_lines == {}
    assert len(warengeld_bank.grant_calls) == 1
    assert company.sight_balance <= 0.0


def test_company_step_repayment_respects_working_capital_buffer() -> None:
    cfg = build_config(
        {
            "company.min_working_capital_buffer": 10.0,
            "company.investment_threshold": 10_000.0,
            "company.rd_investment_trigger_balance": 500.0,
        }
    )
    company = Company("company_repay_buffer", production_capacity=60.0, config=cfg)
    company.employees = []
    company.sight_balance = 40.0

    warengeld_bank = StubWarengeldBank()
    warengeld_bank.credit_lines[company.unique_id] = 30.0

    company.step(current_step=5, warengeld_bank=warengeld_bank)

    assert warengeld_bank.process_calls == [30.0]
    assert math.isclose(company.sight_balance, cfg.company.min_working_capital_buffer)
    assert math.isclose(warengeld_bank.credit_lines[company.unique_id], 0.0)


def test_company_step_growth_persists_and_releases_workers() -> None:
    cfg = build_config(
        {
            "company.investment_threshold": 50.0,
            "company.growth_threshold": 5,
            "company.employee_capacity_ratio": 15.0,
            "labor_market.starting_wage": 5.0,
        }
    )
    company = Company("company_multi_step", production_capacity=30.0, max_employees=10, config=cfg)
    employees = [Household("emp_multi_1", config=cfg), Household("emp_multi_2", config=cfg), Household("emp_multi_3", config=cfg)]
    for worker in employees:
        worker.current_wage = cfg.labor_market.starting_wage
        worker.employed = True
    company.employees = employees.copy()
    company.sight_balance = 200.0

    class TrackingLaborMarket(StubLaborMarket):
        def __init__(self, default_wage: float) -> None:
            super().__init__(default_wage)
            self.release_calls: list[str] = []

        def release_worker(self, worker: Household) -> None:  # type: ignore[override]
            self.release_calls.append(worker.unique_id)
            super().release_worker(worker)

    labor_market = TrackingLaborMarket(cfg.labor_market.starting_wage)
    state = StubState(labor_market)

    results = []
    for step in (1, 2):
        outcome = company.step(current_step=step, state=state)
        results.append(outcome)

    assert all(res is None for res in results)
    assert company.growth_phase is True
    assert company.growth_counter == 2
    assert labor_market.release_calls
    assert len(company.employees) == int(company.production_capacity / cfg.company.employee_capacity_ratio)


def test_company_state_bank_integration_multi_step() -> None:
    cfg = build_config(
        {
            "company.investment_threshold": 200.0,
            "company.liquidity_buffer_ratio": 0.1,
            "company.growth_threshold": 3,
            "company.min_working_capital_buffer": 5.0,
            "labor_market.starting_wage": 5.0,
            "company.growth_investment_factor": 0.1,
        }
    )
    labor_market = StubLaborMarket(cfg.labor_market.starting_wage)
    state = IntegrationState(labor_market)
    warengeld_bank = IntegrationWarengeldBank()
    savings_bank = IntegrationSavingsBank()

    company = Company("company_integration", production_capacity=60.0, max_employees=5, config=cfg)
    company.sight_balance = 5.0
    employees = [Household("emp_int_1", config=cfg), Household("emp_int_2", config=cfg), Household("emp_int_3", config=cfg)]
    for worker in employees:
        worker.current_wage = cfg.labor_market.starting_wage
        worker.employed = True
    company.employees = employees

    company.step(1, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
    assert warengeld_bank.grant_calls
    assert state.tax_revenue >= 0.0

    warengeld_bank.check_inventories([company])
    assert warengeld_bank.inventory_checks

    company.sight_balance = 100.0
    warengeld_bank.credit_lines[company.unique_id] = 20.0
    Company.step(company, 2, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
    assert math.isclose(warengeld_bank.credit_lines[company.unique_id], 0.0)
    assert company.sight_balance >= cfg.company.min_working_capital_buffer

    company.sight_balance = 250.0
    result = company.step(3, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
    assert result is None or isinstance(result, Company)
    assert company.growth_counter >= 1


def test_company_auto_liquidates_when_staffless() -> None:
    cfg = build_config(
        {
            "company.zero_staff_auto_liquidation": True,
            "company.zero_staff_grace_steps": 2,
            "company.zero_staff_liquidation_state_share": 0.5,
        }
    )
    company = Company("company_staffless", production_capacity=50.0, config=cfg)
    company.sight_balance = 100.0
    company.employees = []

    class StubStateWithRevenue(StubState):
        def __init__(self) -> None:
            super().__init__(labor_market=StubLaborMarket(cfg.labor_market.starting_wage))
            self.tax_revenue = 0.0

    state = StubStateWithRevenue()

    company.step(1, state=state)
    assert company._zero_staff_steps == 1
    result = company.step(2, state=state)
    assert result == "LIQUIDATED"
    assert company.sight_balance == 0.0
    assert state.tax_revenue == 50.0
