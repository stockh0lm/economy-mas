import math

from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG


class StubLaborMarket:
    def __init__(self) -> None:
        self.default_wage = CONFIG.get("default_wage", 5)
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
            self.inventory_checks.append(merchant.inventory)


class IntegrationSavingsBank(StubSavingsBank):
    def __init__(self) -> None:
        super().__init__()
        self.repayments: list[float] = []

    def repayment(self, borrower: Company, amount: float) -> float:
        self.repayments.append(amount)
        return amount


def test_company_step_handles_credit_growth_and_split() -> None:
    overrides: dict[str, float | int] = {
        "company_liquidity_buffer_ratio": 0.2,
        "growth_balance_trigger": 1.0,
        "growth_threshold": 1,
        "min_working_capital_buffer": 0.0,
        "growth_investment_factor": 0.1,
        "default_wage": 5,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_step_regress", production_capacity=110.0, max_employees=10)
        employees = [Household("emp_a"), Household("emp_b")]
        default_wage = CONFIG.get("default_wage", 5)
        for employee in employees:
            employee.current_wage = default_wage
            employee.employed = True
        initial_balance = 10.0
        company.employees = employees
        company.balance = initial_balance
        initial_employee_count = len(employees)
        labor_market = StubLaborMarket()
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

        employee_capacity_ratio = CONFIG.get("employee_capacity_ratio", 10.0)
        required_employees = int(company.production_capacity / employee_capacity_ratio)
        expected_positions = min(
            max(0, required_employees - initial_employee_count),
            company.max_employees - initial_employee_count,
        )
        assert labor_market.job_offers == [
            (company.unique_id, labor_market.default_wage, expected_positions),
        ]

        planned_wage_bill = sum(
            getattr(worker, "current_wage", default_wage) for worker in employees
        )
        buffer_ratio = CONFIG["company_liquidity_buffer_ratio"]
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
        expected_growth_credit = company.production_capacity * CONFIG["growth_investment_factor"]
        assert math.isclose(savings_bank.allocate_calls[0], expected_growth_credit, rel_tol=1e-9)

        assert company.growth_phase is False
        assert company.growth_counter == 0
    finally:
        CONFIG.update(originals)


def test_company_step_without_employees_skips_credit_and_production() -> None:
    overrides = {
        "rd_investment_trigger_balance": 500.0,
        "growth_balance_trigger": 10_000.0,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_no_workers", production_capacity=80.0, max_employees=5)
        company.employees = []
        company.balance = 50.0

        class PassiveWarengeldBank(StubWarengeldBank):
            def grant_credit(self, merchant: Company, amount: float) -> float:  # type: ignore[override]
                super().grant_credit(merchant, amount)
                return 0.0

        warengeld_bank = PassiveWarengeldBank()
        new_company = company.step(current_step=2, state=None, warengeld_bank=warengeld_bank)

        assert new_company is None
        assert warengeld_bank.grant_calls == []
        assert math.isclose(company.inventory, 0.0)
    finally:
        CONFIG.update(originals)


def test_company_step_returns_dead_when_bankrupt() -> None:
    overrides = {
        "bankruptcy_threshold": -5.0,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_bankrupt", production_capacity=50.0)
        company.balance = -10.0

        result = company.step(current_step=3)

        assert result == "DEAD"
    finally:
        CONFIG.update(originals)


def test_company_step_handles_credit_denial_gracefully() -> None:
    overrides = {
        "company_liquidity_buffer_ratio": 0.3,
        "growth_balance_trigger": 10_000.0,
        "default_wage": 5,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_credit_denied", production_capacity=90.0, max_employees=10)
        employees = [Household("emp_x"), Household("emp_y")]
        wage = CONFIG["default_wage"]
        for worker in employees:
            worker.current_wage = wage
            worker.employed = True
        company.employees = employees
        company.balance = 0.0

        class DenyingWarengeldBank(StubWarengeldBank):
            def grant_credit(self, merchant: Company, amount: float) -> float:  # type: ignore[override]
                self.grant_calls.append(amount)
                return 0.0

        labor_market = StubLaborMarket()
        state = StubState(labor_market)
        warengeld_bank = DenyingWarengeldBank()

        new_company = company.step(4, state=state, warengeld_bank=warengeld_bank)

        assert new_company is None
        assert warengeld_bank.credit_lines == {}
        assert len(warengeld_bank.grant_calls) == 1
        assert company.balance <= 0.0  # wages paid without external credit
    finally:
        CONFIG.update(originals)


def test_company_step_repayment_respects_working_capital_buffer() -> None:
    overrides = {
        "min_working_capital_buffer": 10.0,
        "growth_balance_trigger": 10_000.0,
        "rd_investment_trigger_balance": 500.0,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_repay_buffer", production_capacity=60.0)
        company.employees = []
        company.balance = 40.0

        warengeld_bank = StubWarengeldBank()
        warengeld_bank.credit_lines[company.unique_id] = 30.0

        company.step(current_step=5, warengeld_bank=warengeld_bank)

        assert warengeld_bank.process_calls == [30.0]
        assert math.isclose(company.balance, CONFIG["min_working_capital_buffer"])
        assert math.isclose(warengeld_bank.credit_lines[company.unique_id], 0.0)
    finally:
        CONFIG.update(originals)


def test_company_step_growth_persists_and_releases_workers() -> None:
    overrides: dict[str, float | int] = {
        "growth_balance_trigger": 50.0,
        "growth_threshold": 5,
        "employee_capacity_ratio": 15.0,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        company = Company("company_multi_step", production_capacity=30.0, max_employees=10)
        employees = [Household("emp_multi_1"), Household("emp_multi_2"), Household("emp_multi_3")]
        for worker in employees:
            worker.current_wage = CONFIG.get("default_wage", 5)
            worker.employed = True
        company.employees = employees.copy()
        company.balance = 200.0

        class TrackingLaborMarket(StubLaborMarket):
            def __init__(self) -> None:
                super().__init__()
                self.release_calls: list[str] = []

            def release_worker(self, worker: Household) -> None:  # type: ignore[override]
                self.release_calls.append(worker.unique_id)
                super().release_worker(worker)

        labor_market = TrackingLaborMarket()
        state = StubState(labor_market)

        results = []
        for step in (1, 2):
            outcome = company.step(current_step=step, state=state)
            results.append(outcome)

        assert all(res is None for res in results)
        assert company.growth_phase is True
        assert company.growth_counter == 2
        assert labor_market.release_calls  # at least one worker was released when downsizing
        assert len(company.employees) == int(company.production_capacity / CONFIG["employee_capacity_ratio"])
    finally:
        CONFIG.update(originals)


def test_company_state_bank_integration_multi_step() -> None:
    overrides = {
        "growth_balance_trigger": 200.0,
        "company_liquidity_buffer_ratio": 0.1,
        "growth_threshold": 3,
        "min_working_capital_buffer": 5.0,
        "default_wage": 5,
        "growth_investment_factor": 0.1,
    }
    originals = {key: CONFIG.get(key) for key in overrides}
    CONFIG.update(overrides)
    try:
        labor_market = StubLaborMarket()
        state = IntegrationState(labor_market)
        warengeld_bank = IntegrationWarengeldBank()
        savings_bank = IntegrationSavingsBank()

        company = Company("company_integration", production_capacity=60.0, max_employees=5)
        company.balance = 5.0
        employees = [Household("emp_int_1"), Household("emp_int_2"), Household("emp_int_3")]
        for worker in employees:
            worker.current_wage = CONFIG["default_wage"]
            worker.employed = True
        company.employees = employees

        # Step 1: company pays wages, uses credit, and state collects taxes indirectly
        company.step(1, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
        assert warengeld_bank.grant_calls  # credit requested
        assert state.tax_revenue >= 0.0  # placeholder for state interactions

        # Simulate inventory check between steps
        warengeld_bank.check_inventories([company])
        assert warengeld_bank.inventory_checks  # recorded inventory snapshot

        # Step 2: ensure credit repayment honors working capital buffer
        company.balance = 100.0
        warengeld_bank.credit_lines[company.unique_id] = 20.0
        Company.step(company, 2, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
        assert math.isclose(warengeld_bank.credit_lines[company.unique_id], 0.0)
        assert company.balance >= CONFIG["min_working_capital_buffer"]

        # Step 3: growth progression and potential savings-bank interactions
        company.balance = 250.0
        result = company.step(3, state=state, warengeld_bank=warengeld_bank, savings_bank=savings_bank)
        assert result is None or isinstance(result, Company)
        assert company.growth_counter >= 1
    finally:
        CONFIG.update(originals)

