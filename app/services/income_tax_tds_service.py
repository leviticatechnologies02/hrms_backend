"""
Income Tax TDS Service
Business logic for income tax TDS management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal

from app.repositories.income_tax_tds_repository import IncomeTaxTDSRepository
from app.schemas.datacapture import (
    IncomeTaxTDSCreate, IncomeTaxTDSResponse
)


class IncomeTaxTDSService:
    """Service layer for income tax TDS operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = IncomeTaxTDSRepository(db)
    
    def get_incometaxtds_employees(
        self,
        business_id: Optional[int] = None,
        month: str = "AUG-2025",
        business_unit: Optional[str] = None,
        location: Optional[str] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 5,
        current_user = None
    ) -> List[Dict[str, Any]]:
        """
        Get employees with income tax TDS data for frontend table
        
        Args:
            business_id: Business ID filter
            month: Month in format "AUG-2025"
            business_unit: Business unit filter
            location: Location filter
            department: Department filter
            search: Search term for employee name
            page: Page number
            size: Page size
            
        Returns:
            List of employee TDS data
        """
        try:
            # Get employees with TDS data
            employees = self.repository.get_employees_with_tds(
                business_id=business_id,
                month=month,
                business_unit=business_unit,
                location=location,
                department=department,
                search=search,
                page=page,
                size=size,
                current_user=current_user
            )
            
            # Format response for frontend
            response_data = []
            
            for emp_data in employees:
                response_data.append({
                    "id": emp_data["employee_code"],
                    "name": emp_data["name"],
                    "designation": emp_data["designation"],
                    "status": "Enabled",
                    "tds_amount": emp_data.get("tds_amount", 0.0)
                })
            
            return response_data
            
        except Exception as e:
            raise Exception(f"Failed to get income tax TDS employees: {str(e)}")
    
    def get_incometaxtds_filters(
        self,
        business_id: Optional[int] = None,
        current_user = None
    ) -> Dict[str, List[str]]:
        """
        Get filter options for income tax TDS module
        
        Args:
            business_id: Business ID filter
            current_user: Current user for role-based filtering
            
        Returns:
            Dictionary with filter options
        """
        try:
            return self.repository.get_filter_options(business_id=business_id, current_user=current_user)
            
        except Exception as e:
            raise Exception(f"Failed to get income tax TDS filters: {str(e)}")
    
    def update_employee_tds(
        self,
        employee_code: str,
        month: str,
        tds_amount: float,
        business_id: Optional[int] = None,
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update income tax TDS for an employee
        
        Args:
            employee_code: Employee code
            month: Month in format "AUG-2025"
            tds_amount: TDS amount
            business_id: Business ID
            updated_by: User ID who updated
            
        Returns:
            Update result
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Update TDS
            result = self.repository.update_employee_tds(
                employee_code=employee_code,
                effective_date=effective_date,
                tds_amount=Decimal(str(tds_amount)),
                business_id=business_id,
                updated_by=updated_by
            )
            
            return {
                "message": f"Income tax TDS updated for employee {result['employee_name']}",
                "employee_code": employee_code,
                "month": month,
                "tds_amount": str(tds_amount),
                "effective_date": effective_date.isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to update income tax TDS: {str(e)}")
    
    def delete_employee_tds(
        self,
        employee_code: str,
        month: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Delete income tax TDS for an employee
        
        Args:
            employee_code: Employee code
            month: Month in format "AUG-2025"
            business_id: Business ID
            
        Returns:
            Delete result
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Delete TDS
            result = self.repository.delete_employee_tds(
                employee_code=employee_code,
                effective_date=effective_date,
                business_id=business_id
            )
            
            return {
                "message": f"Income tax TDS deleted for employee {result['employee_name']}",
                "employee_code": employee_code,
                "month": month,
                "deleted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to delete income tax TDS: {str(e)}")
    
    def copy_from_previous_period(
        self,
        source_period: str,
        target_period: str,
        overwrite_existing: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Copy TDS from previous period
        
        Args:
            source_period: Source period in format "AUG-2025"
            target_period: Target period in format "SEP-2025"
            overwrite_existing: Whether to overwrite existing data
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Copy result
        """
        try:
            # Parse periods to get effective dates
            source_date = self._parse_month_to_date(source_period)
            target_date = self._parse_month_to_date(target_period)
            
            # Copy TDS records
            result = self.repository.copy_tds_from_period(
                source_date=source_date,
                target_date=target_date,
                overwrite_existing=overwrite_existing,
                business_id=business_id,
                created_by=created_by
            )
            
            return {
                "message": f"Income tax TDS copied from {source_period} to {target_period}",
                "source_period": source_period,
                "target_period": target_period,
                "employees_affected": result["employees_affected"],
                "records_created": result["records_created"],
                "overwrite_existing": overwrite_existing
            }
            
        except Exception as e:
            raise Exception(f"Failed to copy from previous period: {str(e)}")
    
    def search_employees(
        self,
        search: str,
        limit: int = 5,
        business_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search employees for autocomplete
        
        Args:
            search: Search term
            limit: Maximum results
            business_id: Business ID
            
        Returns:
            List of matching employees
        """
        try:
            employees = self.repository.search_employees(
                search=search,
                limit=limit,
                business_id=business_id
            )
            
            return [{"name": emp["name"], "code": emp["employee_code"]} for emp in employees]
            
        except Exception as e:
            raise Exception(f"Failed to search employees: {str(e)}")
    
    def export_employee_data(
        self,
        employee_code: str,
        month: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export employee TDS data
        
        Args:
            employee_code: Employee code
            month: Month in format "AUG-2025"
            business_id: Business ID
            
        Returns:
            Employee TDS export data
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Get employee TDS data
            export_data = self.repository.get_employee_export_data(
                employee_code=employee_code,
                effective_date=effective_date,
                business_id=business_id
            )
            
            return export_data
            
        except Exception as e:
            raise Exception(f"Failed to export employee data: {str(e)}")
    
    def _parse_month_to_date(self, month: str) -> date:
        """
        Parse month string to date
        
        Args:
            month: Month in format "AUG-2025"
            
        Returns:
            Date object for first day of month
        """
        try:
            month_year = month.split('-')
            month_abbr = month_year[0]
            year = int(month_year[1])
            
            # Convert month abbreviation to number
            month_abbrs = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            month_num = month_abbrs.index(month_abbr) + 1
            
            return date(year, month_num, 1)
        except:
            return date.today().replace(day=1)