"""
Professional Tax Service
Business logic for Professional Tax configuration
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.repositories.professional_tax_repository import (
    ProfessionalTaxSettingsRepository,
    PTComponentMappingRepository,
    ProfessionalTaxRateRepository
)
from app.models.professional_tax import ProfessionalTaxSettings, PTComponentMapping, ProfessionalTaxRate


class ProfessionalTaxService:
    def __init__(self, db: Session):
        self.db = db
        self.settings_repo = ProfessionalTaxSettingsRepository(db)
        self.component_repo = PTComponentMappingRepository(db)
        self.rate_repo = ProfessionalTaxRateRepository(db)
    
    def get_or_create_settings(self, business_id: int) -> ProfessionalTaxSettings:
        """Get existing settings or create default ones"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create empty default settings (no pre-populated components)
            settings = self.settings_repo.create_with_relationships({
                "business_id": business_id,
                "is_enabled": True,
                "calculation_base": "Gross Salary",
                "component_mappings": [],
                "tax_rates": []
            })
        
        return settings
    
    def update_settings(self, settings_id: int, data: dict) -> ProfessionalTaxSettings:
        """Update Professional Tax settings"""
        settings = self.settings_repo.get(settings_id)
        return self.settings_repo.update(settings, data)
    
    def add_component_mapping(self, settings_id: int, component_data: dict) -> PTComponentMapping:
        """Add a new component mapping"""
        component_data["pt_settings_id"] = settings_id
        return self.component_repo.create(component_data)
    
    def update_component_mapping(self, component_id: int, data: dict) -> PTComponentMapping:
        """Update component mapping"""
        component = self.component_repo.get(component_id)
        return self.component_repo.update(component, data)
    
    def bulk_update_components(self, component_ids: List[int], is_selected: bool) -> int:
        """Bulk update component selection"""
        return self.component_repo.bulk_update_selection(component_ids, is_selected)
    
    def add_tax_rate(self, settings_id: int, rate_data: dict) -> ProfessionalTaxRate:
        """Add a new tax rate"""
        rate_data["pt_settings_id"] = settings_id
        return self.rate_repo.create(rate_data)
    
    def update_tax_rate(self, rate_id: int, data: dict) -> ProfessionalTaxRate:
        """Update tax rate"""
        rate = self.rate_repo.get(rate_id)
        return self.rate_repo.update(rate, data)
    
    def delete_tax_rate(self, rate_id: int) -> None:
        """Delete tax rate"""
        self.rate_repo.delete(rate_id)
    
    def get_rates_by_state(self, settings_id: int, state: str) -> List[ProfessionalTaxRate]:
        """Get all tax rates for a specific state"""
        return self.rate_repo.get_by_state(settings_id, state)
    
    def calculate_tax(
        self,
        settings_id: int,
        state: str,
        salary: float,
        month: str = "All Months",
        gender: str = "All Genders",
        as_of_date: date = None
    ) -> float:
        """Calculate professional tax for given parameters"""
        rate = self.rate_repo.get_applicable_rate(
            settings_id, state, salary, month, gender, as_of_date
        )
        return rate.tax_amount if rate else 0.0
