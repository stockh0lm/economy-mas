"""Household behavior components.

This package contains extracted components for Household agent behavior:
- ConsumptionComponent: consumption decision and purchase logic
- SavingsComponent: savings rate, portfolio, deposits
- DemographyComponent: births, deaths, household split logic
"""

from .consumption import ConsumptionComponent, ConsumptionPlan
from .demography import DemographyComponent, HouseholdFormationEvent
from .savings import SavingsComponent

__all__ = [
    "ConsumptionComponent",
    "ConsumptionPlan",
    "DemographyComponent",
    "HouseholdFormationEvent",
    "SavingsComponent",
]