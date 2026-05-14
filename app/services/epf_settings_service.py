"""
EPF Settings Service
Business logic for EPF configuration
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.repositories.epf_settings_repository import (
    EPFSettingsRepository,
    EPFComponentMappingRepository,
    EPFRateChangeRepository,
)
from app.models.epf_settings import EPFSettings, EPFComponentMapping, EPFRateChange


class EPFSettingsService:
    def __init__(self, db: Session):
        self.db = db
        self.settings_repo = EPFSettingsRepository(db)
        self.component_repo = EPFComponentMappingRepository(db)
        self.rate_repo = EPFRateChangeRepository(db)
    
    def get_or_create_settings(self, business_id: int) -> EPFSettings:
        """Get existing settings or create default ones"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create default settings with standard components
            default_components = [
                {"component_name": "Basic Salary - Basic", "component_code": "BASIC", "component_type": "Paid Days", "is_selected": True},
                {"component_name": "House Rent Allowance - HRA", "component_code": "HRA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Special Allowance - SA", "component_code": "SA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Medical Allowance - MDA", "component_code": "MDA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Leave Encashment - Leave", "component_code": "LEAVE", "component_type": "Variable", "is_selected": False},
                {"component_name": "Bonus - Bonus", "component_code": "BONUS", "component_type": "Variable", "is_selected": False},
                {"component_name": "Conveyance Allowance - CA", "component_code": "CA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Telephone Allowance - TA", "component_code": "TA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Gratuity - Graty", "component_code": "GRATY", "component_type": "Variable", "is_selected": False},
                {"component_name": "Loan - Loan", "component_code": "LOAN", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Hours) - OT", "component_code": "OT", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Days) - OTD", "component_code": "OTD", "component_type": "System", "is_selected": False},
                {"component_name": "Retention Bonus - RTB", "component_code": "RTB", "component_type": "System", "is_selected": False},
            ]
            
            settings = self.settings_repo.create_with_relationships({
                "business_id": business_id,
                "is_enabled": True,
                "calculation_base": "Gross Salary",
                "component_mappings": [],
                "rate_changes": []
            })
        
        return settings
    
    def update_settings(self, settings_id: int, data: dict) -> EPFSettings:
        """Update EPF settings"""
        settings = self.settings_repo.get(settings_id)
        return self.settings_repo.update(settings, data)
    
    def add_component_mapping(self, settings_id: int, component_data: dict) -> EPFComponentMapping:
        """Add a new component mapping"""
        component_data["epf_settings_id"] = settings_id
        return self.component_repo.create(component_data)
    
    def update_component_mapping(self, component_id: int, data: dict) -> EPFComponentMapping:
        """Update component mapping"""
        component = self.component_repo.get(component_id)
        return self.component_repo.update(component, data)
    
    def bulk_update_components(self, component_ids: List[int], is_selected: bool) -> int:
        """Bulk update component selection"""
        return self.component_repo.bulk_update_selection(component_ids, is_selected)
    
    def add_rate_change(self, settings_id: int, rate_data: dict) -> EPFRateChange:
        """Add a new rate change"""
        rate_data["epf_settings_id"] = settings_id
        return self.rate_repo.create(rate_data)
    
    def update_rate_change(self, rate_id: int, data: dict) -> EPFRateChange:
        """Update rate change"""
        rate = self.rate_repo.get(rate_id)
        return self.rate_repo.update(rate, data)
    
    def delete_rate_change(self, rate_id: int) -> None:
        """Delete rate change"""
        self.rate_repo.delete(rate_id)
    
    def get_active_rate(self, settings_id: int, as_of_date: date = None) -> Optional[EPFRateChange]:
        """Get the currently active rate"""
        return self.rate_repo.get_active_rate(settings_id, as_of_date)
