from agents.company_agent import Company
from config import CONFIG_MODEL


def test_split_company_moves_part_of_balance_and_resets_growth() -> None:
    original_ratio = CONFIG_MODEL.company.split_ratio
    CONFIG_MODEL.company.split_ratio = 0.5
    try:
        company = Company("C3", production_capacity=100.0)
        company.sight_balance = 1000.0
        company.generation = 1
        company.growth_phase = True
        company.growth_counter = company.growth_threshold

        new_company = company.split_company()

        assert company.sight_balance == 500.0
        assert new_company.sight_balance == 500.0
        assert new_company.generation == company.generation + 1
        assert company.growth_phase is False
        assert company.growth_counter == 0
    finally:
        CONFIG_MODEL.company.split_ratio = original_ratio


def test_check_bankruptcy_triggers_when_balance_below_threshold() -> None:
    threshold = CONFIG_MODEL.company.bankruptcy_threshold
    company = Company("C4")

    company.sight_balance = threshold - 1.0
    assert company.check_bankruptcy() is True

    company.sight_balance = threshold + 1.0
    assert company.check_bankruptcy() is False

