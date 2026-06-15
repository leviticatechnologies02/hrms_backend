"""
Work Profile Service
Business logic layer for work profile management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.repositories.work_profile_repository import WorkProfileRepository


class WorkProfileService:
    """Service for work profile business logic"""
    
    def __init__(self, db: Session):
        self.repository = WorkProfileRepository(db)
    
    def get_employees_with_work_profiles(
        self,
        business_id: Optional[int] = None,
        business_unit: Optional[str] = None,
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        only_without_profile: bool = False,
        page: int = 1,
        size: int = 10
    ) -> List[Dict[str, Any]]:
        """Get employees with work profiles"""
        return self.repository.get_employees_with_work_profiles(
            business_id=business_id,
            business_unit=business_unit,
            location=location,
            cost_center=cost_center,
            department=department,
            search=search,
            only_without_profile=only_without_profile,
            page=page,
            size=size
        )
    
    def get_filter_options(self, business_id: Optional[int] = None) -> Dict[str, List[str]]:
        """Get filter options"""
        return self.repository.get_filter_options(business_id=business_id)
    
    def get_dropdown_options(self, business_id: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get dropdown options"""
        return self.repository.get_dropdown_options(business_id=business_id)
    
    def update_employee_work_profile(
        self,
        employee_code: str,
        location_id: Optional[int] = None,
        cost_center_id: Optional[int] = None,
        department_id: Optional[int] = None,
        grade_id: Optional[int] = None,
        designation_id: Optional[int] = None,
        shift_policy_id: Optional[int] = None,
        weekoff_policy_id: Optional[int] = None,
        reporting_manager_id: Optional[int] = None,
        business_id: Optional[int] = None,
        updated_by: int = None
    ) -> Dict[str, Any]:
        """Update employee work profile"""
        return self.repository.update_employee_work_profile(
            employee_code=employee_code,
            location_id=location_id,
            cost_center_id=cost_center_id,
            department_id=department_id,
            grade_id=grade_id,
            designation_id=designation_id,
            shift_policy_id=shift_policy_id,
            weekoff_policy_id=weekoff_policy_id,
            reporting_manager_id=reporting_manager_id,
            business_id=business_id,
            updated_by=updated_by
        )
    
    def search_employees(
        self,
        search: str,
        business_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search employees"""
        return self.repository.search_employees(
            search=search,
            business_id=business_id,
            limit=limit
        )
    
    def export_work_profiles_csv(
        self,
        business_id: Optional[int] = None,
        business_unit: Optional[str] = None,
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None
    ) -> str:
        """Export work profiles as CSV"""
        return self.repository.export_work_profiles_csv(
            business_id=business_id,
            business_unit=business_unit,
            location=location,
            cost_center=cost_center,
            department=department
        )
    
    def import_work_profiles_csv(
        self,
        csv_content: str,
        business_id: int,
        created_by: int,
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """Import work profiles from CSV"""
        return self.repository.import_work_profiles_csv(
            csv_content=csv_content,
            business_id=business_id,
            created_by=created_by,
            overwrite_existing=overwrite_existing
        )
    
    def bulk_update_work_profiles(
        self,
        updates: List[Dict[str, Any]],
        business_id: Optional[int] = None,
        updated_by: int = None
    ) -> Dict[str, Any]:
        """Bulk update work profiles"""
        return self.repository.bulk_update_work_profiles(
            updates=updates,
            business_id=business_id,
            updated_by=updated_by
        )

    def get_previous_work_profile(self, employee_id: int) -> Optional[Any]:
        """Get the previous work profile revision for an employee"""
        return self.repository.get_previous_work_profile(employee_id)

    def create_snapshot_from_employee(
        self, 
        employee: Any, 
        effective_from: Any = None, 
        is_promotion: bool = False, 
        notes: Optional[str] = None, 
        created_by: Optional[int] = None
    ) -> Any:
        """Create a history revision from the current state of an employee"""
        return self.repository.create_snapshot_from_employee(
            employee=employee,
            effective_from=effective_from,
            is_promotion=is_promotion,
            notes=notes,
            created_by=created_by
        )