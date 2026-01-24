"""Comprehensive tests for refactored components."""

from typing import Protocol, runtime_checkable

from agents.base_agent import BaseAgent
from agents.config_cache import AgentConfigCache, ConfigCache, GlobalConfigCache
from agents.financial_manager import FinancialManager
from agents.logging_utils import AgentLogger, SimulationLogger, SystemLogger
from agents.protocols import AgentWithBalance, AgentWithImpact, HasUniqueID
from config import (
    AgentLifecycleError,
    ConfigValidationError,
    EconomicParameterError,
    InsufficientFundsError,
    SimulationConfig,
    SimulationError,
)


class MockAgent:
    """Mock agent for testing protocols."""
    def __init__(self, unique_id: str = "test_agent"):
        self.unique_id = unique_id
        self.balance = 100.0
        self.environmental_impact = 1.0

class MockHousehold:
    """Mock household for financial manager testing."""
    def __init__(self):
        self.unique_id = "test_household"
        self.income = 100.0
        self.checking_account = 50.0
        self.local_savings = 20.0
        self.growth_phase = False
        self.child_cost_covered = False
        self.child_rearing_cost = 100.0
        self.loan_repayment_rate = 0.25
        self.age = 30

    # Backwards-compat alias for older helpers
    @property
    def savings(self) -> float:
        return float(self.local_savings)

    @savings.setter
    def savings(self, value: float) -> None:
        self.local_savings = float(value)

class MockSavingsBank:
    """Mock savings bank for testing."""
    def __init__(self):
        self.savings_accounts = {}
        self.active_loans = {}

    def deposit_savings(self, agent, amount: float) -> float:
        if amount > 1000:  # Mock limit
            deposited = 1000
        else:
            deposited = amount
        self.savings_accounts[agent.unique_id] = deposited
        return deposited

    def give_household_withdrawal(self, agent, amount: float) -> float:
        available = self.savings_accounts.get(agent.unique_id, 0.0)
        return min(amount, available)

    def repayment(self, agent, amount: float) -> float:
        return amount

class TestAgentProtocols:
    """Test protocol implementations."""

    def test_agent_with_balance_protocol(self):
        """Test AgentWithBalance protocol."""
        agent = MockAgent()

        @runtime_checkable
        class TestProtocol(AgentWithBalance, Protocol):
            pass

        assert isinstance(agent, TestProtocol)
        assert hasattr(agent, 'balance')

    def test_agent_with_impact_protocol(self):
        """Test AgentWithImpact protocol."""
        agent = MockAgent()

        @runtime_checkable
        class TestProtocol(AgentWithImpact, Protocol):
            pass

        assert isinstance(agent, TestProtocol)
        assert hasattr(agent, 'environmental_impact')

    def test_has_unique_id_protocol(self):
        """Test HasUniqueID protocol."""
        agent = MockAgent()

        @runtime_checkable
        class TestProtocol(HasUniqueID, Protocol):
            pass

        assert isinstance(agent, TestProtocol)
        assert hasattr(agent, 'unique_id')

class TestBaseAgent:
    """Test enhanced base agent functionality."""

    def test_base_agent_initialization(self):
        """Test base agent initialization."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        assert agent.unique_id == "test_agent"
        assert agent.config == config
        assert agent.active is True
        assert agent.created_at_step is None
        assert agent.last_updated_step is None

    def test_base_agent_step(self):
        """Test base agent step method."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        agent.step(1)

        assert agent.created_at_step == 1
        assert agent.last_updated_step == 1

    def test_base_agent_metrics(self):
        """Test base agent metrics functionality."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        agent.log_metric("test_metric", 42)
        agent.log_metric("perf_metric", 1.5, category="performance")

        metrics = agent.get_metrics()

        assert metrics["basic"]["test_metric"] == 42
        assert metrics["performance"]["perf_metric"] == 1.5
        assert metrics["state"]["active"] is True

    def test_base_agent_activation(self):
        """Test agent activation/deactivation."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        assert agent.active is True

        agent.deactivate()
        assert agent.active is False

        agent.activate()
        assert agent.active is True

    def test_base_agent_config_access(self):
        """Test base agent configuration access."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        # Test existing config path
        value = agent.get_config_value("simulation_steps")
        assert value == 100

        # Test non-existing config path with default
        value = agent.get_config_value("nonexistent.path", default=42)
        assert value == 42

class TestConfigCache:
    """Test configuration caching system."""

    def test_config_cache_basic(self):
        """Test basic config cache functionality."""
        cache = ConfigCache(max_size=5)

        call_count = 0
        def getter():
            nonlocal call_count
            call_count += 1
            return 42

        # First call should compute
        value = cache.get("test_key", getter)
        assert value == 42
        assert call_count == 1

        # Second call should use cache
        value = cache.get("test_key", getter)
        assert value == 42
        assert call_count == 1  # Should not have called getter again

    def test_config_cache_stats(self):
        """Test config cache statistics."""
        cache = ConfigCache(max_size=3)

        def getter():
            return "test_value"

        # Add some items
        cache.get("key1", getter)
        cache.get("key2", getter)
        cache.get("key3", getter)

        stats = cache.get_stats()
        assert stats["cache_size"] == 3
        assert stats["hit_rate"] == 0  # All were misses initially

        # Access cached items
        cache.get("key1", getter)
        cache.get("key2", getter)

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 3

    def test_agent_config_cache(self):
        """Test agent-specific config cache."""
        config = SimulationConfig()
        agent_cache = AgentConfigCache(config)

        # Test basic caching
        value = agent_cache.get_config_value("simulation_steps")
        assert value == 100

        # Test section cache
        company_cache = agent_cache.get_section_cache("company")
        assert isinstance(company_cache, ConfigCache)

    def test_global_config_cache(self):
        """Test global config cache singleton."""
        config = SimulationConfig()
        cache1 = GlobalConfigCache(config)
        cache2 = GlobalConfigCache()

        assert cache1 is cache2  # Should be same instance

        value = cache1.get_config_value("simulation_steps")
        assert value == 100

class TestFinancialManager:
    """Test financial manager functionality."""

    def test_financial_manager_initialization(self):
        """Test financial manager initialization."""
        household = MockHousehold()
        fm = FinancialManager(household)

        assert fm.household is household
        assert fm._financial_history == []

    def test_financial_manager_income(self):
        """Test income processing."""
        household = MockHousehold()
        fm = FinancialManager(household)

        amount = fm.process_income()
        assert amount == 100.0
        assert household.checking_account == 150.0  # 50 + 100

        # Test specific amount
        amount = fm.process_income(50.0)
        assert amount == 50.0
        assert household.checking_account == 200.0

    def test_financial_manager_consumption(self):
        """Test consumption management."""
        household = MockHousehold()
        fm = FinancialManager(household)

        # Test legacy consumption
        amount = fm.manage_consumption(0.5)  # 50% of checking account
        assert amount == 25.0  # 50 * 0.5
        assert household.checking_account == 25.0

    def test_financial_manager_savings(self):
        """Test savings optimization."""
        household = MockHousehold()
        fm = FinancialManager(household)

        # Test without bank
        amount = fm.optimize_savings()
        assert amount == 50.0
        assert household.checking_account == 0.0
        assert household.local_savings == 70.0  # 20 + 50

        # Reset for bank test
        household.checking_account = 50.0
        household.local_savings = 20.0

        # Test with bank
        bank = MockSavingsBank()
        amount = fm.optimize_savings(bank)
        assert amount == 50.0
        assert household.checking_account == 0.0
        assert household.local_savings == 20.0  # Local savings unchanged, all went to bank
        assert bank.savings_accounts[household.unique_id] == 50.0

    def test_financial_manager_childrearing(self):
        """Test childrearing cost handling."""
        household = MockHousehold()
        household.growth_phase = True
        fm = FinancialManager(household)

        # Test without bank - household has savings, so it should withdraw
        amount = fm.handle_childrearing_costs(None)
        assert amount == 20.0  # Withdrew all available savings (20)
        assert household.local_savings == 0.0  # 20 - 20 used for childrearing
        assert household.checking_account == 70.0  # 50 + 20 withdrawn
        assert household.child_cost_covered is False  # Still needs 80 more

        # Add more savings and test completion
        household.local_savings = 150.0
        amount = fm.handle_childrearing_costs(None)
        assert amount == 100.0  # Remaining child rearing cost needed (80 + 20 from previous withdrawal)
        assert household.local_savings == 50.0  # 150 - 100 used
        assert household.checking_account == 170.0  # 70 + 100 withdrawn
        assert household.child_cost_covered is True

    def test_financial_manager_loan_repayment(self):
        """Test loan repayment."""
        household = MockHousehold()
        household.checking_account = 100.0
        fm = FinancialManager(household)

        bank = MockSavingsBank()
        bank.active_loans[household.unique_id] = 50.0

        amount = fm.repay_savings_loans(bank)
        assert amount == 25.0  # 100 * 0.25
        assert household.checking_account == 75.0

    def test_financial_manager_health_score(self):
        """Test financial health score calculation."""
        household = MockHousehold()
        fm = FinancialManager(household)

        # Test with default values
        score = fm.get_financial_health_score()
        assert 0 <= score <= 1

        # Test with higher assets
        household.checking_account = 1000.0
        household.local_savings = 500.0
        score = fm.get_financial_health_score()
        assert score > 0.5

class TestLoggingUtils:
    """Test logging utilities."""

    def test_simulation_logger_initialization(self):
        """Test simulation logger initialization."""
        logger = SimulationLogger("TestComponent", "test_agent")

        assert logger.component_name == "TestComponent"
        assert logger.agent_id == "test_agent"
        assert logger._log_count == 0

    def test_simulation_logger_methods(self):
        """Test simulation logger methods."""
        logger = SimulationLogger("TestComponent", "test_agent")

        # Test all log levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        assert logger._log_count == 5

    def test_agent_logger(self):
        """Test agent-specific logger."""
        logger = AgentLogger("test_agent", "Household")

        logger.log_state_change("idle", "active", "simulation started")
        logger.log_financial_transaction("income", 100.0, 150.0)

        stats = logger.get_log_stats()
        assert stats["log_count"] == 2
        assert stats["component"] == "Household"

    def test_system_logger(self):
        """Test system logger."""
        logger = SystemLogger("TestSystem")

        logger.log_system_metric("agents_created", 100, "count")
        logger.log_system_metric("simulation_time", 1.5, "seconds")

        stats = logger.get_log_stats()
        assert stats["log_count"] == 2

class TestConfigurationValidation:
    """Test configuration validation."""

    def test_config_validation_error(self):
        """Test configuration validation error."""
        try:
            raise ConfigValidationError("Test validation error", ["error1", "error2"])
        except ConfigValidationError as e:
            assert str(e) == "Test validation error\nErrors: error1, error2"
            assert e.config_errors == ["error1", "error2"]

    def test_simulation_error(self):
        """Test simulation error."""
        try:
            raise SimulationError("Test simulation error", "agent_1")
        except SimulationError as e:
            assert str(e) == "Agent agent_1: Test simulation error"
            assert e.agent_id == "agent_1"

    def test_insufficient_funds_error(self):
        """Test insufficient funds error."""
        try:
            raise InsufficientFundsError("Test funds error", "agent_1", 100.0, 50.0)
        except InsufficientFundsError as e:
            assert "Required: 100.00, Available: 50.00" in str(e)
            assert e.required == 100.0
            assert e.available == 50.0

    def test_agent_lifecycle_error(self):
        """Test agent lifecycle error."""
        try:
            raise AgentLifecycleError("Test lifecycle error", "agent_1")
        except AgentLifecycleError as e:
            assert "Agent agent_1: Test lifecycle error" == str(e)

    def test_economic_parameter_error(self):
        """Test economic parameter error."""
        try:
            raise EconomicParameterError("Test parameter error")
        except EconomicParameterError as e:
            assert "Test parameter error" == str(e)
            assert e.agent_id is None

class TestIntegration:
    """Integration tests for refactored components."""

    def test_base_agent_with_protocols(self):
        """Test base agent with protocol compliance."""
        config = SimulationConfig()
        agent = BaseAgent("test_agent", config)

        # Test HasUniqueID protocol compliance
        assert hasattr(agent, 'unique_id')
        assert agent.unique_id == "test_agent"

        # Test metrics functionality
        agent.log_metric("test", 42)
        metrics = agent.get_metrics()
        assert "test" in metrics["basic"]

    def test_financial_manager_with_household(self):
        """Test financial manager integration with household."""
        household = MockHousehold()
        fm = FinancialManager(household)

        # Process income
        fm.process_income()

        # Manage consumption
        fm.manage_consumption(0.3)

        # Optimize savings
        fm.optimize_savings()

        # Check final state
        assert household.checking_account >= 0
        assert household.local_savings >= 20.0

    def test_config_cache_performance(self):
        """Test config cache performance characteristics."""
        cache = ConfigCache(max_size=10)

        call_count = 0
        def expensive_getter():
            nonlocal call_count
            call_count += 1
            import time
            time.sleep(0.001)  # Simulate expensive operation
            return "expensive_result"

        # First call should be slow
        import time
        start = time.time()
        result1 = cache.get("expensive_key", expensive_getter)
        time1 = time.time() - start

        # Second call should be fast (cached)
        start = time.time()
        result2 = cache.get("expensive_key", expensive_getter)
        time2 = time.time() - start

        assert result1 == result2 == "expensive_result"
        assert time2 < time1  # Cached call should be faster
        assert call_count == 1  # Getter only called once
