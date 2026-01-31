# warengeld_accounting.py
"""
Structural architectural solution for Warengeld money system.
Implements double-entry accounting and proper money conservation.
"""

from typing import Dict, List, Optional
from agents.clearing_agent import ClearingAgent
from logger import log

class DoubleEntryAccounting:
    """Double-entry accounting system that prevents money creation by design."""

    def __init__(self):
        self.ledger: Dict[str, Dict[str, float]] = {}
        self.transaction_history: List[Dict] = []
        self.total_money_supply = 0.0

    def record_transaction(self, debit_account: str, credit_account: str, amount: float, purpose: str, step: int):
        """
        Record a transaction with proper debits and credits.

        Args:
            debit_account: Account to debit (money leaves)
            credit_account: Account to credit (money enters)
            amount: Transaction amount (must be positive)
            purpose: Purpose of transaction
            step: Simulation step

        Raises:
            ValueError: If transaction would violate money conservation
        """
        if amount <= 0:
            raise ValueError(f"Amount must be positive, got {amount}")

        # Initialize accounts if needed
        for account in [debit_account, credit_account]:
            if account not in self.ledger:
                self.ledger[account] = {'debits': 0.0, 'credits': 0.0}

        # Record the transaction
        self.ledger[debit_account]['debits'] += amount
        self.ledger[credit_account]['credits'] += amount

        # Log the transaction
        transaction = {
            'step': step,
            'debit': debit_account,
            'credit': credit_account,
            'amount': amount,
            'purpose': purpose
        }
        self.transaction_history.append(transaction)

        # Verify money supply conservation
        self._verify_conservation()

        log(
            f"Accounting: {debit_account} → {credit_account}: {amount:.2f} "
            f"for {purpose} (step {step})",
            level="INFO"
        )

    def _verify_conservation(self):
        """Verify that total debits equal total credits (money conservation)."""
        total_debits = sum(account['debits'] for account in self.ledger.values())
        total_credits = sum(account['credits'] for account in self.ledger.values())

        if abs(total_debits - total_credits) > 0.01:
            raise ValueError(
                f"Money supply violation: Debits ({total_debits:.2f}) ≠ Credits ({total_credits:.2f})"
            )

    def get_balance(self, account: str) -> float:
        """Get account balance (credits - debits)."""
        if account not in self.ledger:
            return 0.0
        return self.ledger[account]['credits'] - self.ledger[account]['debits']

    def get_total_money_supply(self) -> float:
        """Get total money supply (should equal total credits - total debits)."""
        total_credits = sum(account['credits'] for account in self.ledger.values())
        total_debits = sum(account['debits'] for account in self.ledger.values())
        return total_credits - total_debits

    def get_transaction_history(self, limit: int = 100) -> List[Dict]:
        """Get recent transaction history."""
        return self.transaction_history[-limit:] if self.transaction_history else []

class MoneyTransactionPipeline:
    """Transaction pipeline that enforces proper money flows."""

    def __init__(self, accounting: DoubleEntryAccounting, clearing_agent: Optional[ClearingAgent] = None):
        self.accounting = accounting
        self.clearing_agent = clearing_agent

    def transfer(self, from_account: str, to_account: str, amount: float, purpose: str, step: int):
        """
        Transfer money between accounts (no money creation).

        Args:
            from_account: Source account
            to_account: Destination account
            amount: Amount to transfer
            purpose: Purpose of transfer
            step: Simulation step

        Returns:
            True if successful, False if failed
        """
        try:
            self.accounting.record_transaction(from_account, to_account, amount, purpose, step)
            return True
        except ValueError as e:
            log(f"Transfer failed: {e}", level="ERROR")
            return False

    def create_retail_credit(self, retailer_account: str, producer_account: str, amount: float, step: int):
        """
        Create money through retail credit (proper money creation with offset).

        Args:
            retailer_account: Retailer taking on debt
            producer_account: Producer receiving payment
            amount: Amount to create
            step: Simulation step

        Returns:
            True if successful, False if failed
        """
        try:
            # This creates money: retailer gets negative balance, producer gets positive
            self.accounting.record_transaction(retailer_account, producer_account, amount, "retail_credit", step)
            return True
        except ValueError as e:
            log(f"Retail credit failed: {e}", level="ERROR")
            return False

    def repay_credit(self, debtor_account: str, creditor_account: str, amount: float, step: int):
        """
        Repay credit (money destruction).

        Args:
            debtor_account: Account repaying debt
            creditor_account: Account receiving repayment
            amount: Amount to repay
            step: Simulation step

        Returns:
            True if successful, False if failed
        """
        try:
            # This destroys money: debtor reduces debt, creditor receives payment
            self.accounting.record_transaction(debtor_account, creditor_account, amount, "credit_repayment", step)
            return True
        except ValueError as e:
            log(f"Repayment failed: {e}", level="ERROR")
            return False

    def get_balance(self, account: str) -> float:
        """Get account balance."""
        return self.accounting.get_balance(account)

class MoneySupplyGuardian:
    """Actively monitors and guards money supply integrity."""

    def __init__(self, accounting: DoubleEntryAccounting, clearing_agent: Optional[ClearingAgent] = None):
        self.accounting = accounting
        self.clearing_agent = clearing_agent
        self.initial_supply = 0.0

    def initialize(self, agents: List[object]):
        """Initialize with current money supply."""
        self.initial_supply = self.accounting.get_total_money_supply()

    def check_anomalies(self) -> List[Dict]:
        """Check for money supply anomalies."""
        anomalies = []

        # Check for large changes
        current_supply = self.accounting.get_total_money_supply()
        change = current_supply - self.initial_supply
        pct_change = (change / self.initial_supply * 100) if self.initial_supply > 0 else 0

        if abs(pct_change) > 1:  # More than 1% change
            anomalies.append({
                'type': 'supply_change',
                'initial': self.initial_supply,
                'current': current_supply,
                'change': change,
                'pct_change': pct_change
            })

        # Check individual account anomalies
        for account, data in self.accounting.ledger.items():
            balance = data['credits'] - data['debits']
            if abs(balance) > 10000:  # Large balance
                anomalies.append({
                    'type': 'large_balance',
                    'account': account,
                    'balance': balance,
                    'credits': data['credits'],
                    'debits': data['debits']
                })

        return anomalies

def create_warengeld_accounting_system(clearing_agent: Optional[ClearingAgent] = None):
    """Create the complete Warengeld accounting system."""
    accounting = DoubleEntryAccounting()
    pipeline = MoneyTransactionPipeline(accounting, clearing_agent)
    guardian = MoneySupplyGuardian(accounting, clearing_agent)

    return {
        'accounting': accounting,
        'pipeline': pipeline,
        'guardian': guardian
    }
