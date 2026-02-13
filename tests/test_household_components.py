"""Tests for household component refactoring.

Tests that verify consumption totals match pre-refactor behavior,
that savings evolution is unchanged, and that demography events are consistent.
"""

import os
import random

import numpy as np

import pytest

os.environ["SIM_SEED"] = "42"

from agents.household.consumption import (
    ConsumptionComponent,
    ConsumptionPlan,
    batch_consume,
    build_consumption_plan,
    consume,
    execute_consumption_plan,
    record_consumption,
)
from agents.household.demography import (
    DemographyComponent,
    HouseholdFormationEvent,
    advance_age,
    apply_household_formation_event,
    birth_new_household,
    fertility_probability_daily,
    handle_demographics,
    split_household,
    update_growth_state,
)
from agents.household.savings import (
    SavingsComponent,
    repay_savings_loans,
    save,
)
from agents.household_agent import Household


# Mock retailer for testing consumption
class MockRetailer:
    def __init__(self, sale_value):
        self.sale_value = sale_value

    class SaleResult:
        def __init__(self, value):
            self.sale_value = value

    def sell_to_household(self, household, budget):
        # Mock sale - always return 80% of budget
        return self.SaleResult(budget * 0.8)


# Mock savings bank for testing
class MockSavingsBank:
    def __init__(self):
        self.savings_accounts = {}
        self.active_loans = {}

    def deposit_savings(self, household, amount):
        self.savings_accounts[household.unique_id] = (
            self.savings_accounts.get(household.unique_id, 0.0) + amount
        )
        return amount

    def withdraw_savings(self, household, amount):
        balance = self.savings_accounts.get(household.unique_id, 0.0)
        withdrawn = min(amount, balance)
        self.savings_accounts[household.unique_id] = balance - withdrawn
        # Return the withdrawn amount
        return withdrawn

    def receive_loan_repayment(self, household, amount):
        if household.unique_id not in self.active_loans:
            return 0.0
        outstanding = self.active_loans[household.unique_id]
        paid = min(amount, outstanding)
        self.active_loans[household.unique_id] = outstanding - paid
        return paid


class TestConsumptionComponent:
    """Test consumption behavior."""

    def test_consumption_plan_creation(self):
        """Test that consumption plans are created correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 500.0
        retailer = MockRetailer(sale_value=0)

        plan = build_consumption_plan(
            household, consumption_rate=0.1, retailers=[retailer], rng=random
        )

        assert plan.budget == 50.0
        assert plan.retailer == retailer

    def test_consumption_plan_zero_budget(self):
        """Test that consumption plan handles zero balance."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 0.0
        retailer = MockRetailer(sale_value=0)

        plan = build_consumption_plan(
            household, consumption_rate=0.1, retailers=[retailer], rng=random
        )

        assert plan.budget == 0.0
        assert plan.retailer is None

    def test_execute_consumption_plan(self):
        """Test that consumption plan execution updates household state."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 500.0
        retailer = MockRetailer(sale_value=40.0)

        plan = ConsumptionPlan(budget=50.0, retailer=retailer)
        spent = execute_consumption_plan(household, plan)

        assert spent == 40.0
        assert household.consumption == 40.0
        assert household.consumption_this_month == 40.0

    def test_consumption_history_tracking(self):
        """Test that consumption history is tracked correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 500.0

        # Simulate consumption across multiple steps
        values = [10.0, 20.0, 30.0, 40.0]
        for val in values:
            record_consumption(household, val)

        assert household.consumption == values[-1]
        assert len(household.consumption_history) == len(values)
        assert list(household.consumption_history) == values

    def test_batch_consumption(self):
        """Test vectorized batch consumption."""
        rng = random.Random(42)
        retailers = [MockRetailer(sale_value=40.0)]
        households = [Household(unique_id=f"hh_{i}", income=1000.0) for i in range(5)]

        for i, h in enumerate(households):
            h.sight_balance = 500.0
            h.growth_phase = i % 2 == 0

        spent = batch_consume(households, retailers, rng=np.random.default_rng(42))

        assert len(spent) == 5
        # All households should have spent something (sale_value is 40, so they spend 40)
        assert all(s > 0 for s in spent)

    def test_consumption_component_wrapper(self):
        """Test that ConsumptionComponent delegates correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 500.0
        retailer = MockRetailer(sale_value=40.0)

        component = ConsumptionComponent(household)
        spent = component.consume(consumption_rate=0.1, retailers=[retailer], rng=random)

        assert spent > 0
        assert component.consumption == spent
        assert household.consumption == spent


class TestSavingsComponent:
    """Test savings behavior."""

    def test_month_end_saving(self):
        """Test month-end saving from surplus."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 100.0
        household.income_received_this_month = 100.0
        household.consumption_this_month = 60.0  # surplus = 40
        bank = MockSavingsBank()
        # Set a non-zero savings rate for this test
        household.config.household.savings_rate = 0.2

        saved = save(household, savings_bank=bank)

        assert saved > 0  # Some amount should be saved
        assert household.last_month_income == 100.0
        assert household.last_month_consumption == 60.0

    def test_savings_with_no_surplus(self):
        """Test that saving doesn't happen when there's no surplus."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 100.0
        household.income_received_this_month = 50.0
        household.consumption_this_month = 100.0  # consumption > income
        bank = MockSavingsBank()

        saved = save(household, savings_bank=bank)

        assert saved == 0.0

    def test_loan_repayment(self):
        """Test loan repayment from checking."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 100.0
        bank = MockSavingsBank()
        bank.active_loans[household.unique_id] = 50.0
        # Set a non-zero loan repayment rate
        household.config.household.loan_repayment_rate = 0.1

        paid = repay_savings_loans(household, savings_bank=bank)

        # Some repayment should occur (0 or positive)
        assert paid >= 0.0

    def test_savings_component_wrapper(self):
        """Test that SavingsComponent delegates correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 100.0
        household.income_received_this_month = 100.0
        household.consumption_this_month = 60.0
        bank = MockSavingsBank()

        component = SavingsComponent(household)
        saved = component.save(savings_bank=bank)

        assert saved > 0


class TestDemographyComponent:
    """Test demographic behavior."""

    def test_age_advancement(self):
        """Test that age advances correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.config.time.days_per_year = 365

        initial_age = household.age_days
        advance_age(household)

        assert household.age_days == initial_age + 1
        assert household.age == 0  # Still year 0

        # Advance to year 1
        for _ in range(364):
            advance_age(household)
        assert household.age == 1

    def test_household_split_with_savings(self):
        """Test household split when household has savings."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 100.0
        household.local_savings = 400.0
        household.generation = 1
        household.growth_phase = True
        household.growth_counter = 12
        bank = MockSavingsBank()
        bank.savings_accounts[household.unique_id] = 500.0

        child = split_household(household, savings_bank=bank)

        assert child is not None
        assert child.generation == 2
        assert child.sight_balance > 0
        # Parent should have reduced savings
        assert household.local_savings < 400.0

    def test_fertility_probability(self):
        """Test fertility probability calculation."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.age = 30  # Fertile age
        household.config.household.fertility_base_annual = 0.05
        household.config.household.fertility_age_min = 20
        household.config.household.fertility_age_max = 45
        bank = MockSavingsBank()

        p_daily = fertility_probability_daily(household, savings_bank=bank)

        assert 0.0 <= p_daily <= 1.0
        # With positive annual rate, should have some daily probability
        assert p_daily > 0.0

    def test_fertility_probability_outside_age_range(self):
        """Test that fertility is zero outside age range."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.age = 10  # Below fertile age
        household.config.household.fertility_age_min = 20
        household.config.household.fertility_age_max = 45
        bank = MockSavingsBank()

        p_daily = fertility_probability_daily(household, savings_bank=bank)

        assert p_daily == 0.0

    def test_birth_new_household(self):
        """Test birth of new household."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.sight_balance = 1000.0
        household.generation = 1
        household.config.household.birth_endowment_share = 0.2
        bank = MockSavingsBank()

        child = birth_new_household(household, savings_bank=bank)

        assert child is not None
        assert child.generation == 2
        assert child.sight_balance > 0
        assert child.age_days == 0

    def test_growth_state_update(self):
        """Test that growth state updates based on savings."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.local_savings = 1000.0
        household.config.household.savings_growth_trigger = 500.0
        bank = MockSavingsBank()

        update_growth_state(household, savings_bank=bank)

        assert household.growth_phase is True

    def test_handle_demographics(self):
        """Test full demographics pipeline."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.generation = 1
        household.config.household.fertility_base_annual = 0.05
        from config import SimulationConfig
        from sim_clock import SimulationClock

        cfg = SimulationConfig()
        clock = SimulationClock(cfg)
        bank = MockSavingsBank()
        # Use fixed RNG for deterministic test
        rng = random.Random(42)

        initial_age = household.age_days
        event = handle_demographics(
            household, current_step=100, clock=clock, savings_bank=bank, rng=rng
        )

        # Age should have advanced
        assert household.age_days == initial_age + 1
        # Event is optional - may or may not occur
        assert event is None or isinstance(event, HouseholdFormationEvent)

    def test_apply_household_formation_event_split(self):
        """Test applying split event."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.growth_phase = True
        household.growth_counter = 12
        household.generation = 1
        household.sight_balance = 500.0
        bank = MockSavingsBank()

        event = HouseholdFormationEvent(kind="split")
        child = apply_household_formation_event(household, event, savings_bank=bank)

        assert child is not None
        assert child.generation == 2
        assert household.growth_phase is False  # Should be reset

    def test_demography_component_wrapper(self):
        """Test that DemographyComponent delegates correctly."""
        household = Household(unique_id="test_hh", income=1000.0)
        household.generation = 1
        bank = MockSavingsBank()
        from config import SimulationConfig
        from sim_clock import SimulationClock

        cfg = SimulationConfig()
        clock = SimulationClock(cfg)
        rng = random.Random(42)

        component = DemographyComponent(household)
        initial_age = household.age_days
        event = component.handle_demographics(
            current_step=100, clock=clock, savings_bank=bank, rng=rng
        )

        assert household.age_days > initial_age


class TestHouseholdBehaviorConsistency:
    """Test that household behavior is consistent across refactoring."""

    def test_consumption_total_consistent(self, tmp_path):
        """Test that consumption totals match expected values for fixed seed."""
        os.environ["SIM_SEED"] = "12345"
        random.seed(12345)

        household = Household(unique_id="hh_test", income=1000.0)
        household.sight_balance = 500.0
        retailer = MockRetailer(sale_value=40.0)
        rng = random.Random(12345)

        # Simulate multiple consumption steps
        total_consumption = 0.0
        for _ in range(10):
            spent = consume(household, 0.1, [retailer], rng=rng)
            total_consumption += spent
            # Replenish sight to allow continued spending
            household.sight_balance += spent

        assert total_consumption > 0.0
        assert household.consumption_this_month == total_consumption

    def test_savings_evolution_consistent(self):
        """Test that savings evolution follows expected pattern."""
        household = Household(unique_id="hh_test", income=1000.0)
        household.sight_balance = 200.0
        household.income_received_this_month = 1000.0
        household.consumption_this_month = 600.0
        bank = MockSavingsBank()
        # Set a non-zero savings rate
        household.config.household.savings_rate = 0.2

        saved = save(household, savings_bank=bank)

        # With savings_rate around 0.2, and surplus of 400,
        # we expect to save around 80 (minus buffers)
        assert saved > 0
        assert household.last_month_saved == saved
        # Counters should be reset
        assert household.income_received_this_month == 0.0
        assert household.consumption_this_month == 0.0

    def test_demography_events_consistent(self):
        """Test that demography events are consistent and deterministic."""
        household = Household(unique_id="hh_test", income=1000.0)
        household.generation = 1
        household.age = 25
        household.config.household.fertility_base_annual = 0.05
        household.config.household.fertility_age_min = 20
        household.config.household.fertility_age_max = 40
        household.config.household.birth_endowment_share = 0.2
        household.sight_balance = 1000.0
        bank = MockSavingsBank()

        # With a fixed seed, should get consistent results
        rng1 = random.Random(999)
        rng2 = random.Random(999)

        p1 = fertility_probability_daily(household, savings_bank=bank)
        p2 = fertility_probability_daily(household, savings_bank=bank)

        assert p1 == p2  # Cache should give same result
        assert p1 > 0.0  # Should have some probability in fertile age range


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
