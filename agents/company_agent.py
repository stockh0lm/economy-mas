from .economic_agent import EconomicAgent
from logger import log
from config import CONFIG
from .household_agent import Household

class Company(EconomicAgent):
    def __init__(self, unique_id, production_capacity=100, resource_usage=10, land_area=100, environmental_impact=5, max_employees=10, employees=None):
        super().__init__(unique_id)
        self.production_capacity = production_capacity
        self.resource_usage = resource_usage
        self.land_area = land_area
        self.environmental_impact = environmental_impact
        self.max_employees = max_employees
        self.employees = employees if employees is not None else []
        self.inventory = 0
        self.balance = 0
        # Neue Attribute zur Steuerung der Wachstumsphase und Insolvenz
        self.growth_phase = False
        self.growth_counter = 0
        self.growth_threshold = 5           # Nach 5 Schritten (Jahren) in der Wachstumsphase erfolgt ein Spin-off
        self.growth_balance_trigger = 1000  # Überschreitet die Bilanz diesen Wert, wird die Wachstumsphase aktiviert
        self.bankruptcy_threshold = -100    # Fällt die Bilanz unter diesen Wert, gilt das Unternehmen als insolvent

    def produce(self):
        if self.max_employees == 0:
            actual_production = 0
        else:
            actual_production = self.production_capacity * (len(self.employees) / self.max_employees)
        self.inventory += actual_production
        log(f"Company {self.unique_id} produced {actual_production:.2f} units. Total inventory: {self.inventory:.2f}.", level="INFO")
        self.adjust_employees()
        return actual_production

    def adjust_employees(self):
        required_employees = int(self.production_capacity / 10)
        if required_employees > len(self.employees):
            self.hire_employees(required_employees - len(self.employees))
        elif required_employees < len(self.employees):
            self.fire_employees(len(self.employees) - required_employees)

    def hire_employees(self, number):
        for _ in range(number):
            if len(self.employees) < self.max_employees:
                # Temporärer Haushaltsagent als Mitarbeiter
                new_employee = Household("temp_employee")
                self.employees.append(new_employee)
                log(f"Company {self.unique_id} hired a new employee. Total employees: {len(self.employees)}.", level="INFO")

    def fire_employees(self, number):
        for _ in range(number):
            if self.employees:
                self.employees.pop()
                log(f"Company {self.unique_id} fired an employee. Total employees: {len(self.employees)}.", level="INFO")

    def sell_goods(self, demand=50):
        sold_quantity = min(self.inventory, demand)
        sale_price_per_unit = 10
        revenue = sold_quantity * sale_price_per_unit
        self.balance += revenue
        self.inventory -= sold_quantity
        log(f"Company {self.unique_id} sold {sold_quantity} units for {revenue}. New balance: {self.balance}. Inventory left: {self.inventory}.", level="INFO")
        return revenue

    def pay_wages(self, wage_rate=5):
        if not self.employees:
            log(f"Company {self.unique_id} has no employees to pay wages.", level="WARNING")
            return 0
        total_wages = wage_rate * len(self.employees)
        self.balance -= total_wages
        for employee in self.employees:
            employee.receive_income()
        log(f"Company {self.unique_id} paid wages totaling {total_wages}. New balance: {self.balance}.", level="INFO")
        return total_wages

    def pay_taxes(self, state):
        bodensteuer_rate = CONFIG.get("tax_rates", {}).get("bodensteuer", 0.05)
        umweltsteuer_rate = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)
        tax_due = (self.land_area * bodensteuer_rate) + (self.environmental_impact * umweltsteuer_rate)
        self.balance -= tax_due
        log(f"Company {self.unique_id} paid taxes: {tax_due:.2f}. New balance: {self.balance:.2f}.", level="INFO")
        return tax_due

    def request_funds_from_bank(self, amount):
        log(f"Company {self.unique_id} requests funds: {amount}.", level="INFO")
        self.balance += amount
        log(f"Company {self.unique_id} received funds: {amount}. New balance: {self.balance}.", level="INFO")
        return amount

    def split_company(self):
        # 50% des aktuellen Bilanzüberschusses werden für ein Spin-off genutzt.
        split_balance = self.balance * 0.5
        self.balance -= split_balance
        log(f"Company {self.unique_id} splits after growth phase. Allocating {split_balance:.2f} for a new firm. Remaining balance: {self.balance:.2f}.", level="INFO")
        new_unique_id = f"{self.unique_id}_spinoff"
        new_company = Company(new_unique_id, production_capacity=self.production_capacity, land_area=self.land_area,
                              environmental_impact=self.environmental_impact, max_employees=self.max_employees)
        new_company.balance = split_balance
        log(f"New company {new_unique_id} founded with balance: {split_balance:.2f}.", level="INFO")
        self.growth_phase = False
        self.growth_counter = 0
        return new_company

    def check_bankruptcy(self):
        if self.balance < self.bankruptcy_threshold:
            log(f"Company {self.unique_id} declared bankrupt with balance {self.balance}.", level="WARNING")
            return True
        return False

    def step(self, current_step, state=None):
        log(f"Company {self.unique_id} starting step {current_step}.", level="INFO")
        self.produce()
        self.sell_goods()
        self.pay_wages()
        if state:
            self.pay_taxes(state)
        # Aktivierung der Wachstumsphase, wenn das Bilanzniveau ausreichend ist
        if not self.growth_phase and self.balance >= self.growth_balance_trigger:
            self.growth_phase = True
            log(f"Company {self.unique_id} enters growth phase.", level="INFO")
        if self.growth_phase:
            self.growth_counter += 1
        new_company = None
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            new_company = self.split_company()
        # Überprüfe Insolvenz: Sollte das Unternehmen bankrott sein, wird es markiert.
        if self.check_bankruptcy():
            log(f"Company {self.unique_id} is removed from simulation due to bankruptcy.", level="WARNING")
            return "DEAD"  # Markierung zur Entfernung aus der Simulation
        log(f"Company {self.unique_id} completed step {current_step}.", level="INFO")
        if new_company:
            return new_company
        else:
            return None
