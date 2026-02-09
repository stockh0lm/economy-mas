"""Savings and financial operations for households.

This module handles:
- Saving at month-end
- Loan repayments to savings bank
- Child-rearing costs
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from logger import log

if TYPE_CHECKING:
    from agents.household_agent import Household
    from agents.savings_bank_agent import SavingsBank


def save(household: Household, savings_bank: SavingsBank | None) -> float:
    """Move part of monthly surplus into savings.

    We interpret saving as allocating a fraction of the *monthly surplus*
    (income received during the month minus consumption during the month)
    into SavingsBank deposits at month-end.

    The scheduler controls *when* this method is allowed to save (month-end).
    """
    save_rate = float(household.config.household.savings_rate)
    save_rate = max(0.0, min(1.0, save_rate))

    income = float(household.income_received_this_month)
    consumption = float(household.consumption_this_month)

    # Month-end snapshot (kept after we reset the counters)
    household.last_month_income = income
    household.last_month_consumption = consumption

    # Monthly surplus = income received - consumption during month.
    surplus = max(0.0, income - consumption)

    # Reset counters for the next month.
    household.income_received_this_month = 0.0
    household.consumption_this_month = 0.0
    household.last_income_received = 0.0
    household.last_consumption = 0.0

    if save_rate <= 0 or surplus <= 0:
        household.last_month_saved = 0.0
        return 0.0

    # Keep a small liquid buffer.
    buffer = float(household.config.household.transaction_buffer)
    max_affordable = max(0.0, float(household.sight_balance) - buffer)
    if max_affordable <= 0:
        household.last_month_saved = 0.0
        return 0.0

    saved_amount = min(max_affordable, surplus * save_rate)
    if saved_amount <= 0:
        household.last_month_saved = 0.0
        return 0.0

    deposited: float
    if savings_bank is None:
        # Cash-at-home savings.
        household.sight_balance -= saved_amount
        household.local_savings += saved_amount
        deposited = float(saved_amount)
    else:
        # Banked savings: cap may bind, so only deduct what was actually booked.
        deposited = float(savings_bank.deposit_savings(household, saved_amount))
        household.sight_balance -= deposited

    household.last_month_saved = float(deposited)
    log(f"Household {household.unique_id}: Saved {deposited:.2f}.", level="INFO")
    return float(deposited)


def repay_savings_loans(household: Household, savings_bank: SavingsBank | None) -> float:
    """Repay part of outstanding savings-bank loans from checking."""
    if savings_bank is None:
        return 0.0

    if household.unique_id not in savings_bank.active_loans:
        return 0.0
    outstanding = float(savings_bank.active_loans.get(household.unique_id, 0.0))
    if outstanding <= 0:
        return 0.0

    repay_budget = max(0.0, household.sight_balance) * float(
        household.config.household.loan_repayment_rate
    )
    paid = savings_bank.receive_loan_repayment(household, repay_budget)
    if paid > 0:
        log(f"Household {household.unique_id}: Repaid {paid:.2f}.", level="INFO")
    return paid


def handle_childrearing_costs(household: Household, savings_bank: SavingsBank | None) -> float:
    """Withdraw savings to cover a one-off child cost during growth.

    Preference order:
    1) SavingsBank (if provided)
    2) local savings (`household.local_savings`)
    """
    if not household.growth_phase or household.child_cost_covered:
        return 0.0

    cost = float(household.config.household.child_rearing_cost)
    if household.sight_balance >= cost:
        household.sight_balance -= cost
        household.child_cost_covered = True
        return 0.0

    need = cost - household.sight_balance
    withdrawn = 0.0
    if savings_bank is not None:
        withdrawn = savings_bank.withdraw_savings(household, need)
    else:
        withdrawn = min(need, max(0.0, household.local_savings))
        household.local_savings -= withdrawn
        household.sight_balance += withdrawn

    # If bank withdrawal happened, SavingsBank already credited checking via withdraw_savings()
    if household.sight_balance >= cost:
        household.sight_balance -= cost
        household.child_cost_covered = True

    return withdrawn


def handle_finances(
    household: Household,
    current_step: int,
    savings_bank: SavingsBank | None,
    stage: str,
    is_month_end: bool | None = None,
    clock=None,
) -> None:
    """Finance pipeline: repayments + month-end saving."""
    if stage == "pre":
        repay_savings_loans(household, savings_bank)
        return

    if stage == "post":
        month_end = is_month_end
        if month_end is None:
            month_end = clock.is_month_end(current_step) if clock is not None else False
        if month_end:
            save(household, savings_bank)
        return

    raise ValueError(f"Unknown stage for handle_finances: {stage!r}")


# ---------------------------------------------------------------------------
# Class-based wrapper (used by household_agent.py component delegation)
# ---------------------------------------------------------------------------


class SavingsComponent:
    """Wraps the function-based savings logic as a component attached to a Household."""

    __slots__ = ("_household",)

    def __init__(self, household: Household) -> None:
        self._household = household

    @property
    def savings(self) -> float:
        """Backwards-compatible 'savings' metric."""
        sb = getattr(self._household, "_savings_bank_ref", None)
        bank_deposits = 0.0
        if sb is not None:
            bank_deposits = float(sb.savings_accounts.get(self._household.unique_id, 0.0))
        return float(self._household.local_savings) + bank_deposits

    @savings.setter
    def savings(self, value: float) -> None:
        self._household.local_savings = float(value)

    @property
    def savings_balance(self) -> float:
        """Local cash savings buffer (not bank deposits)."""
        return float(self._household.local_savings)

    def save(self, savings_bank: SavingsBank | None) -> float:
        return save(self._household, savings_bank)

    def _repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        return repay_savings_loans(self._household, savings_bank)

    def _handle_childrearing_costs(self, savings_bank: SavingsBank | None) -> float:
        return handle_childrearing_costs(self._household, savings_bank)

    def handle_finances(
        self,
        current_step: int,
        *,
        clock=None,
        savings_bank: SavingsBank | None = None,
        stage: str,
        is_month_end: bool | None = None,
    ) -> None:
        return handle_finances(
            self._household,
            current_step,
            savings_bank,
            stage,
            is_month_end=is_month_end,
            clock=clock,
        )
