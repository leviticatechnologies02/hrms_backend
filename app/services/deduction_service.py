"""
Deduction Service
Business logic for employee deductions management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal

from app.repositories.deduction_repository import DeductionRepository
from app.schemas.datacapture import (
    EmployeeDeductionCreate, EmployeeDeductionUpdate, EmployeeDeductionResponse
)


class DeductionService:
    """Service layer for deduction operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = DeductionRepository(db)
    
    def get_deduction_employees(
        self,
        business_id: Optional[int] = None,
        month: str = "AUG-2025",
        business_unit: Optional[str] = None,
        location: Optional[str] = None,
        department: Optional[str] = None,
        deduction_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 10,
        current_user = None
    ) -> List[Dict[str, Any]]:
        """
        Get employees with deduction data for frontend table
        
        Args:
            business_id: Business ID filter
            month: Month in format "AUG-2025"
            business_unit: Business unit filter
            location: Location filter
            department: Department filter
            deduction_type: Deduction type filter
            search: Search term for employee name/code
            page: Page number
            size: Page size
            
        Returns:
            List of employee deduction data matching frontend expectations
        """
        try:
            # Get employees with deduction data
            employees = self.repository.get_employees_with_deductions(
                business_id=business_id,
                month=month,
                business_unit=business_unit,
                location=location,
                department=department,
                deduction_type=deduction_type,
                search=search,
                page=page,
                size=size,
                current_user=current_user
            )
            
            # Format response for frontend (matching DeductionTDS.jsx expectations)
            response_data = []
            
            for i, emp_data in enumerate(employees):
                # Calculate total from all deductions
                total_amount = emp_data.get("amount", 0.0)
                
                response_data.append({
                    "id": i + 1,
                    "name": f"<b>{emp_data['name']}</b>",  # Frontend expects bold formatting
                    "clean_name": emp_data['name'],  # Clean name for testing/validation
                    "code": emp_data["employee_code"],
                    "location": emp_data["location"],
                    "dept": emp_data["department"],
                    "position": emp_data.get("position", "Software Engineer"),
                    "grosssalary": emp_data.get("gross_salary", 75000.0),
                    "calculatedexemptions": emp_data.get("calculated_exemptions", 0.0),
                    "additionalexemptions": emp_data.get("additional_exemptions", 0.0),
                    "netsalary": emp_data.get("net_salary", 75000.0),
                    "amount": emp_data.get("amount", 0.0),
                    "comments": emp_data.get("comments", ""),
                    "total": total_amount
                })
            
            return response_data
            
        except Exception as e:
            raise Exception(f"Failed to get deduction employees: {str(e)}")
    
    def get_deduction_filters(
        self,
        business_id: Optional[int] = None,
        current_user = None
    ) -> Dict[str, List[str]]:
        """
        Get filter options for deduction module
        
        Args:
            business_id: Business ID filter
            
        Returns:
            Dictionary with filter options
        """
        try:
            return self.repository.get_filter_options(business_id=business_id, current_user=current_user)
            
        except Exception as e:
            raise Exception(f"Failed to get deduction filters: {str(e)}")
    
    def update_employee_deduction(
        self,
        employee_code: str,
        month: str,
        amount: float,
        comments: str = "",
        deduction_type: str = "Voluntary PF",
        business_id: Optional[int] = None,
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update deduction for an employee
        
        Args:
            employee_code: Employee code
            month: Month in format "AUG-2025"
            amount: Deduction amount
            comments: Comments
            deduction_type: Deduction type
            business_id: Business ID
            updated_by: User ID who updated
            
        Returns:
            Update result
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Update deduction
            result = self.repository.update_employee_deduction(
                employee_code=employee_code,
                effective_date=effective_date,
                amount=Decimal(str(amount)),
                comments=comments,
                deduction_type=deduction_type,
                business_id=business_id,
                updated_by=updated_by
            )
            
            return {
                "message": f"Deduction updated for employee {result['employee_name']}",
                "employee_code": employee_code,
                "month": month,
                "amount": str(amount),
                "deduction_type": deduction_type,
                "effective_date": effective_date.isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to update deduction: {str(e)}")
    
    def copy_from_previous_period(
        self,
        source_period: str,
        target_period: str,
        deduction_type: str = "Voluntary PF",
        overwrite_existing: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Copy deductions from previous period
        
        Args:
            source_period: Source period in format "AUG-2025"
            target_period: Target period in format "SEP-2025"
            deduction_type: Deduction type to copy
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
            
            # Copy deductions
            result = self.repository.copy_deductions_from_period(
                source_date=source_date,
                target_date=target_date,
                deduction_type=deduction_type,
                overwrite_existing=overwrite_existing,
                business_id=business_id,
                created_by=created_by
            )
            
            return {
                "message": f"Deductions copied from {source_period} to {target_period}",
                "source_period": source_period,
                "target_period": target_period,
                "deduction_type": deduction_type,
                "employees_affected": result["employees_affected"],
                "records_created": result["records_created"],
                "overwrite_existing": overwrite_existing
            }
            
        except Exception as e:
            raise Exception(f"Failed to copy from previous period: {str(e)}")
    
    def export_deductions_csv(
        self,
        month: str = "AUG-2025",
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None,
        business_id: Optional[int] = None
    ) -> str:
        """
        Export deductions data as CSV
        
        Args:
            month: Month in format "AUG-2025"
            location: Location filter
            cost_center: Cost center filter
            department: Department filter
            business_id: Business ID
            
        Returns:
            CSV content as string
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Get export data
            export_data = self.repository.get_export_data(
                effective_date=effective_date,
                location=location,
                cost_center=cost_center,
                department=department,
                business_id=business_id
            )
            
            # Generate CSV content
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow([
                'SN', 'Employee Name', 'Employee Code', 'Location', 'Department',
                'Amount', 'Comments', 'Total', 'Month', 'Deduction Type'
            ])
            
            # Write data rows
            for i, row in enumerate(export_data, start=1):
                writer.writerow([
                    i,
                    row["employee_name"],
                    row["employee_code"],
                    row["location"],
                    row["department"],
                    row["amount"],
                    row["comments"],
                    row["total"],
                    month,
                    row["deduction_type"]
                ])
            
            return output.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to export deductions CSV: {str(e)}")
    
    def import_deductions_csv(
        self,
        csv_content: str,
        month: str = "AUG-2025",
        overwrite_existing: bool = False,
        consider_arrear: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Import deductions data from CSV content
        
        Args:
            csv_content: CSV content as string
            month: Month in format "AUG-2025"
            overwrite_existing: Whether to overwrite existing data
            consider_arrear: Whether to consider as arrear
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Import result
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Import CSV data
            result = self.repository.import_csv_data(
                csv_content=csv_content,
                effective_date=effective_date,
                overwrite_existing=overwrite_existing,
                consider_arrear=consider_arrear,
                business_id=business_id,
                created_by=created_by
            )
            
            return {
                "message": f"CSV import completed for {month}",
                "imported_records": result["imported_records"],
                "errors": result["errors"][:10],  # Limit errors to first 10
                "total_errors": len(result["errors"]),
                "overwrite_existing": overwrite_existing,
                "consider_arrear": consider_arrear
            }
            
        except Exception as e:
            raise Exception(f"Failed to import deductions CSV: {str(e)}")
    
    def get_employee_deduction_details(
        self,
        employee_code: str,
        month: str = "AUG-2025",
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get deduction details for an employee
        
        Args:
            employee_code: Employee code
            month: Month in format "AUG-2025"
            business_id: Business ID
            
        Returns:
            Employee deduction details
        """
        try:
            # Parse month to get effective date
            effective_date = self._parse_month_to_date(month)
            
            # Get deduction details
            details = self.repository.get_employee_deduction_details(
                employee_code=employee_code,
                effective_date=effective_date,
                business_id=business_id
            )
            
            return details
            
        except Exception as e:
            raise Exception(f"Failed to get employee deduction details: {str(e)}")
    
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