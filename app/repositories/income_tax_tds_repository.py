"""
Income Tax TDS Repository
Database operations for income tax TDS management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date
from decimal import Decimal

from app.models.employee import Employee, EmployeeStatus
from app.models.department import Department
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.designations import Designation
from app.models.datacapture import IncomeTaxTDS


class IncomeTaxTDSRepository:
    """Repository for income tax TDS database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_employees_with_tds(
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
        Get employees with their TDS data
        
        Args:
            business_id: Business ID filter
            month: Month filter
            business_unit: Business unit filter
            location: Location filter
            department: Department filter
            search: Search term
            page: Page number
            size: Page size
            current_user: Current user for role-based filtering
            
        Returns:
            List of employee TDS data
        """
        try:
            # Determine business filtering based on user role
            filter_business_id = None
            if current_user:
                if current_user.role.value == "SUPERADMIN" or str(current_user.role) == "UserRole.SUPERADMIN":
                    # Superadmin sees all data - no business filtering
                    filter_business_id = None
                else:
                    # Company admin - get business_id from their owned businesses
                    if hasattr(current_user, 'businesses') and current_user.businesses:
                        # Use the first business they own
                        filter_business_id = current_user.businesses[0].id
                    else:
                        # Fallback to provided business_id or None
                        filter_business_id = business_id
            else:
                # No user context - use provided business_id
                filter_business_id = business_id
            
            print(f"🔍 Income Tax TDS Employees - User: {current_user.email if current_user else 'None'}, Role: {current_user.role if current_user else 'None'}, Business ID: {filter_business_id}, Business Unit: {business_unit}")
            
            # Base query for employees
            query = self.db.query(Employee).options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.designation),
                joinedload(Employee.business_unit)
            ).filter(Employee.employee_status == EmployeeStatus.ACTIVE)
            
            if filter_business_id:
                query = query.filter(Employee.business_id == filter_business_id)
            
            # Apply location filter
            if location and location != "All Locations":
                query = query.filter(Employee.location.has(Location.name == location))
            
            # Apply department filter
            if department and department != "All Departments":
                query = query.filter(Employee.department.has(Department.name == department))
            
            # 🎯 HYBRID APPROACH: Apply business unit filter using utility function
            if current_user and business_unit and business_unit not in ["All Business Units", "", None]:
                # Import here to avoid circular dependency
                from app.utils.business_unit_utils import apply_business_unit_filter
                query = apply_business_unit_filter(
                    query, 
                    self.db, 
                    current_user, 
                    business_unit, 
                    Employee
                )
            elif business_unit and business_unit not in ["All Business Units", "", None]:
                # Fallback to old logic if no user context
                query = query.filter(Employee.business_unit.has(BusinessUnit.name == business_unit))
            
            # Apply search filter
            if search:
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(f"%{search}%"),
                        Employee.last_name.ilike(f"%{search}%"),
                        Employee.employee_code.ilike(f"%{search}%")
                    )
                )
            
            # Apply pagination
            offset = (page - 1) * size
            employees = query.offset(offset).limit(size).all()
            
            print(f"   📊 Found {len(employees)} employees for Income Tax TDS")
            
            # Build response with TDS data
            result = []
            
            for employee in employees:
                # Get TDS for this employee and month
                tds_data = self._get_employee_tds(employee.id, month)
                
                result.append({
                    "employee_id": employee.id,
                    "name": employee.full_name,
                    "employee_code": employee.employee_code,
                    "designation": employee.designation.name if employee.designation else "Associate Software Engineer",
                    "tds_amount": tds_data.get("tds_amount", 0.0)
                })
            
            return result
            
        except Exception as e:
            print(f"Database error in get_employees_with_tds: {str(e)}")
            raise Exception(f"Database error in get_employees_with_tds: {str(e)}")
    
    def get_filter_options(
        self,
        business_id: Optional[int] = None,
        current_user = None
    ) -> Dict[str, List[str]]:
        """
        Get filter options for income tax TDS
        
        Args:
            business_id: Business ID filter
            current_user: Current user for role-based filtering
            
        Returns:
            Dictionary with filter options
        """
        try:
            # Determine business filtering based on user role
            filter_business_id = None
            if current_user:
                if current_user.role.value == "SUPERADMIN" or str(current_user.role) == "UserRole.SUPERADMIN":
                    # Superadmin sees all data - no business filtering
                    filter_business_id = None
                else:
                    # Company admin - get business_id from their owned businesses
                    if hasattr(current_user, 'businesses') and current_user.businesses:
                        # Use the first business they own
                        filter_business_id = current_user.businesses[0].id
                    else:
                        # Fallback to provided business_id or None
                        filter_business_id = business_id
            else:
                # No user context - use provided business_id
                filter_business_id = business_id
            
            print(f"🔍 Income Tax TDS Filter options - User: {current_user.email if current_user else 'None'}, Role: {current_user.role if current_user else 'None'}, Business ID: {filter_business_id}")
            
            # Get departments
            departments_query = self.db.query(Department).filter(Department.is_active == True)
            if filter_business_id:
                departments_query = departments_query.filter(Department.business_id == filter_business_id)
            department_names = [d.name for d in departments_query.all()]
            
            # Get locations
            locations_query = self.db.query(Location).filter(Location.is_active == True)
            if filter_business_id:
                locations_query = locations_query.filter(Location.business_id == filter_business_id)
            location_names = [l.name for l in locations_query.all()]
            
            # 🎯 HYBRID APPROACH: Use business unit utils for consistent behavior
            try:
                if current_user:
                    from app.utils.business_unit_utils import get_business_unit_options
                    business_unit_options = get_business_unit_options(self.db, current_user, filter_business_id)
                    business_unit_names = business_unit_options[1:]  # Remove "All Business Units"
                    print(f"   🏢 Business units found: {len(business_unit_names)}")
                else:
                    # Fallback to business units if no user context
                    from app.models.business_unit import BusinessUnit
                    business_units_query = self.db.query(BusinessUnit).filter(BusinessUnit.is_active == True)
                    if filter_business_id:
                        business_units_query = business_units_query.filter(BusinessUnit.business_id == filter_business_id)
                    business_unit_names = [bu.name for bu in business_units_query.all()]
                    print(f"   🏢 Business units found (fallback): {len(business_unit_names)}")
                
                # If no business units found, use default
                if not business_unit_names:
                    business_unit_names = ["Default Business Unit"]
            except Exception as e:
                print(f"Error fetching business units: {e}")
                business_unit_names = ["Default Business Unit"]
            
            # Business units (now from database with hybrid logic)
            business_units = ["All Business Units"] + business_unit_names
            
            return {
                "businessUnits": business_units,
                "locations": ["All Locations"] + location_names,
                "departments": ["All Departments"] + department_names
            }
            
        except Exception as e:
            raise Exception(f"Database error in get_filter_options: {str(e)}")
    
    def update_employee_tds(
        self,
        employee_code: str,
        effective_date: date,
        tds_amount: Decimal,
        business_id: Optional[int] = None,
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update TDS for an employee
        
        Args:
            employee_code: Employee code
            effective_date: Effective date
            tds_amount: TDS amount
            business_id: Business ID
            updated_by: User ID who updated
            
        Returns:
            Update result
        """
        try:
            # Find employee
            employee = self.db.query(Employee).filter(
                Employee.employee_code == employee_code,
                Employee.business_id == business_id if business_id else True
            ).first()
            
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Get financial year and quarter from effective date
            financial_year = self._get_financial_year(effective_date)
            quarter = self._get_quarter(effective_date)
            
            # Check if TDS record exists for this employee and period
            existing_tds = self.db.query(IncomeTaxTDS).filter(
                IncomeTaxTDS.business_id == (business_id or employee.business_id),
                IncomeTaxTDS.employee_id == employee.id,
                IncomeTaxTDS.financial_year == financial_year,
                IncomeTaxTDS.quarter == quarter
            ).first()
            
            if existing_tds:
                # Update existing
                existing_tds.tds_amount = tds_amount
                existing_tds.updated_at = datetime.now()
                self.db.commit()
                tds_id = existing_tds.id
            else:
                # Create new TDS record
                new_tds = IncomeTaxTDS(
                    business_id=business_id or employee.business_id,
                    employee_id=employee.id,
                    financial_year=financial_year,
                    quarter=quarter,
                    gross_salary=Decimal("50000.00"),  # Mock gross salary
                    taxable_income=Decimal("45000.00"),  # Mock taxable income
                    tds_amount=tds_amount,
                    tax_slab_rate=Decimal("20.00"),  # Mock tax rate
                    created_by=updated_by
                )
                self.db.add(new_tds)
                self.db.commit()
                self.db.refresh(new_tds)
                tds_id = new_tds.id
            
            return {
                "tds_id": tds_id,
                "employee_name": employee.full_name,
                "employee_code": employee_code,
                "tds_amount": tds_amount,
                "financial_year": financial_year,
                "quarter": quarter,
                "effective_date": effective_date
            }
            
        except ValueError as e:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in update_employee_tds: {str(e)}")
    
    def delete_employee_tds(
        self,
        employee_code: str,
        effective_date: date,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Delete TDS for an employee
        
        Args:
            employee_code: Employee code
            effective_date: Effective date
            business_id: Business ID
            
        Returns:
            Delete result
        """
        try:
            # Find employee
            employee = self.db.query(Employee).filter(
                Employee.employee_code == employee_code,
                Employee.business_id == business_id if business_id else True
            ).first()
            
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Get financial year and quarter from effective date
            financial_year = self._get_financial_year(effective_date)
            quarter = self._get_quarter(effective_date)
            
            # Find and delete TDS record
            tds_record = self.db.query(IncomeTaxTDS).filter(
                IncomeTaxTDS.business_id == (business_id or employee.business_id),
                IncomeTaxTDS.employee_id == employee.id,
                IncomeTaxTDS.financial_year == financial_year,
                IncomeTaxTDS.quarter == quarter
            ).first()
            
            if tds_record:
                self.db.delete(tds_record)
                self.db.commit()
            
            return {
                "employee_name": employee.full_name,
                "employee_code": employee_code,
                "financial_year": financial_year,
                "quarter": quarter
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in delete_employee_tds: {str(e)}")
    
    def copy_tds_from_period(
        self,
        source_date: date,
        target_date: date,
        overwrite_existing: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Copy TDS from previous period
        
        Args:
            source_date: Source date
            target_date: Target date
            overwrite_existing: Whether to overwrite existing
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Copy result
        """
        try:
            # Get financial years and quarters
            source_fy = self._get_financial_year(source_date)
            source_quarter = self._get_quarter(source_date)
            target_fy = self._get_financial_year(target_date)
            target_quarter = self._get_quarter(target_date)
            
            # Get TDS records from source period
            source_tds_records = self.db.query(IncomeTaxTDS).filter(
                IncomeTaxTDS.business_id == business_id if business_id else True,
                IncomeTaxTDS.financial_year == source_fy,
                IncomeTaxTDS.quarter == source_quarter
            ).all()
            
            records_created = 0
            
            for source_tds in source_tds_records:
                # Check if target TDS already exists
                existing_target = self.db.query(IncomeTaxTDS).filter(
                    IncomeTaxTDS.business_id == source_tds.business_id,
                    IncomeTaxTDS.employee_id == source_tds.employee_id,
                    IncomeTaxTDS.financial_year == target_fy,
                    IncomeTaxTDS.quarter == target_quarter
                ).first()
                
                if existing_target and not overwrite_existing:
                    continue
                
                if existing_target and overwrite_existing:
                    # Update existing
                    existing_target.tds_amount = source_tds.tds_amount
                    existing_target.gross_salary = source_tds.gross_salary
                    existing_target.taxable_income = source_tds.taxable_income
                    existing_target.updated_at = datetime.now()
                else:
                    # Create new TDS record
                    new_tds = IncomeTaxTDS(
                        business_id=source_tds.business_id,
                        employee_id=source_tds.employee_id,
                        financial_year=target_fy,
                        quarter=target_quarter,
                        gross_salary=source_tds.gross_salary,
                        taxable_income=source_tds.taxable_income,
                        tds_amount=source_tds.tds_amount,
                        tax_slab_rate=source_tds.tax_slab_rate,
                        exemptions=source_tds.exemptions,
                        deductions_80c=source_tds.deductions_80c,
                        other_deductions=source_tds.other_deductions,
                        created_by=created_by
                    )
                    self.db.add(new_tds)
                
                records_created += 1
            
            self.db.commit()
            
            return {
                "employees_affected": len(source_tds_records),
                "records_created": records_created
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in copy_tds_from_period: {str(e)}")
    
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
            query = self.db.query(Employee).filter(
                Employee.employee_status == EmployeeStatus.ACTIVE,
                or_(
                    Employee.first_name.ilike(f"%{search}%"),
                    Employee.last_name.ilike(f"%{search}%"),
                    Employee.employee_code.ilike(f"%{search}%")
                )
            )
            
            if business_id:
                query = query.filter(Employee.business_id == business_id)
            
            employees = query.limit(limit).all()
            
            return [
                {
                    "name": emp.full_name,
                    "employee_code": emp.employee_code
                }
                for emp in employees
            ]
            
        except Exception as e:
            raise Exception(f"Database error in search_employees: {str(e)}")
    
    def get_employee_export_data(
        self,
        employee_code: str,
        effective_date: date,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get employee TDS data for export
        
        Args:
            employee_code: Employee code
            effective_date: Effective date
            business_id: Business ID
            
        Returns:
            Employee TDS export data
        """
        try:
            # Find employee
            employee = self.db.query(Employee).options(
                joinedload(Employee.designation)
            ).filter(
                Employee.employee_code == employee_code,
                Employee.business_id == business_id if business_id else True
            ).first()
            
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Get TDS data for this employee and period
            tds_data = self._get_employee_tds(employee.id, effective_date.strftime("%b-%Y").upper())
            
            return {
                "id": employee.employee_code,
                "name": employee.full_name,
                "designation": employee.designation.name if employee.designation else "Associate Software Engineer",
                "status": "Enabled",
                "tds_amount": tds_data.get("tds_amount", 0.0)
            }
            
        except Exception as e:
            raise Exception(f"Database error in get_employee_export_data: {str(e)}")
    
    def _get_employee_tds(
        self,
        employee_id: int,
        month: str
    ) -> Dict[str, Any]:
        """
        Get TDS data for an employee
        
        Args:
            employee_id: Employee ID
            month: Month string
            
        Returns:
            TDS data
        """
        try:
            # Parse month to get financial year and quarter
            effective_date = self._parse_month_to_date(month)
            financial_year = self._get_financial_year(effective_date)
            quarter = self._get_quarter(effective_date)
            
            # Query TDS record
            tds_record = self.db.query(IncomeTaxTDS).filter(
                IncomeTaxTDS.employee_id == employee_id,
                IncomeTaxTDS.financial_year == financial_year,
                IncomeTaxTDS.quarter == quarter
            ).first()
            
            if tds_record:
                return {
                    "tds_amount": float(tds_record.tds_amount),
                    "financial_year": tds_record.financial_year,
                    "quarter": tds_record.quarter
                }
            else:
                return {
                    "tds_amount": 0.0,
                    "financial_year": financial_year,
                    "quarter": quarter
                }
            
        except Exception as e:
            return {
                "tds_amount": 0.0,
                "financial_year": "2024-25",
                "quarter": "Q3"
            }
    
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
    
    def _get_financial_year(self, effective_date: date) -> str:
        """
        Get financial year from date
        
        Args:
            effective_date: Date
            
        Returns:
            Financial year string (e.g., "2024-25")
        """
        if effective_date.month >= 4:  # April onwards
            return f"{effective_date.year}-{str(effective_date.year + 1)[-2:]}"
        else:  # January to March
            return f"{effective_date.year - 1}-{str(effective_date.year)[-2:]}"
    
    def _get_quarter(self, effective_date: date) -> str:
        """
        Get quarter from date
        
        Args:
            effective_date: Date
            
        Returns:
            Quarter string (Q1, Q2, Q3, Q4)
        """
        month = effective_date.month
        
        # Financial year quarters (April-March)
        if month in [4, 5, 6]:
            return "Q1"
        elif month in [7, 8, 9]:
            return "Q2"
        elif month in [10, 11, 12]:
            return "Q3"
        else:  # [1, 2, 3]
            return "Q4"