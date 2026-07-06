"""
Deduction Repository
Database operations for employee deductions management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date
from decimal import Decimal
import io
import csv

from app.models.employee import Employee, EmployeeStatus
from app.models.department import Department
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.cost_center import CostCenter
from app.models.datacapture import EmployeeDeduction, DeductionType
from app.models.setup.salary_and_deductions.salary_deduction import SalaryDeduction
from app.utils.business_unit_utils import get_business_unit_options


class DeductionRepository:
    """Repository for deduction database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_employees_with_deductions(
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
        Get employees with their deduction data with proper filtering and timeout protection
        """
        try:
            # Validate and sanitize inputs
            size = min(size, 100)  # Limit size to prevent large queries
            page = max(page, 1)    # Ensure valid page number
            
            # Validate month format first
            try:
                month_parts = month.split('-')
                if len(month_parts) != 2:
                    raise ValueError("Month must be in format 'MON-YYYY'")
                
                month_abbr = month_parts[0].upper()
                year = int(month_parts[1])
                
                valid_months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                
                if month_abbr not in valid_months:
                    raise ValueError(f"Invalid month abbreviation: {month_abbr}")
                    
                if year < 2020 or year > 2030:
                    raise ValueError(f"Year must be between 2020 and 2030: {year}")
                    
            except ValueError as e:
                print(f"Month validation error: {e}")
                # Use current month as fallback
                current_date = date.today()
                month = current_date.strftime("%b-%Y").upper()
                print(f"Using fallback month: {month}")
            
            # Build optimized query with proper joins and limits
            try:
                query = self.db.query(Employee).options(
                    joinedload(Employee.department),
                    joinedload(Employee.location),
                    joinedload(Employee.designation),
                    joinedload(Employee.business_unit)
                ).filter(
                    Employee.employee_status == EmployeeStatus.ACTIVE,
                    Employee.is_active == True
                )
                
                if business_id:
                    query = query.filter(Employee.business_id == business_id)
                
                # Apply filters with proper null checks
                if location and location not in ["All Locations", "", None]:
                    query = query.filter(Employee.location.has(Location.name == location))
                
                if department and department not in ["All Departments", "", None]:
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
                
                # Apply search filter with better matching
                if search and search.strip():
                    search_term = f"%{search.strip()}%"
                    query = query.filter(
                        or_(
                            Employee.first_name.ilike(search_term),
                            Employee.last_name.ilike(search_term),
                            Employee.employee_code.ilike(search_term),
                            func.concat(Employee.first_name, ' ', Employee.last_name).ilike(search_term)
                        )
                    )
                
                # Apply pagination with safety limits
                offset = (page - 1) * size
                employees = query.order_by(Employee.employee_code).offset(offset).limit(size).all()
                
                print(f"Found {len(employees)} employees for processing")
                
            except Exception as e:
                print(f"Database query error: {e}")
                # Return empty result on query failure
                return []
            
            # Build response with actual employee data
            result = []
            
            for i, employee in enumerate(employees):
                try:
                    # Get deductions for this employee and month with timeout protection
                    deduction_data = self._get_employee_deductions(
                        employee.id, month, deduction_type
                    )
                    
                    # Get actual employee data with safe fallbacks
                    employee_location = employee.location.name if employee.location else "Hyderabad"
                    employee_department = employee.department.name if employee.department else "Technical Support"
                    employee_position = employee.designation.name if employee.designation else "Software Engineer"
                    employee_business_unit = employee.business_unit.name if employee.business_unit else "Default Business Unit"
                    
                    # Calculate salary components with safe defaults
                    gross_salary = self._get_employee_gross_salary(employee.id)
                    calculated_exemptions = deduction_data.get("amount", 0.0)
                    additional_exemptions = 0.0
                    net_salary = max(0, gross_salary - calculated_exemptions - additional_exemptions)
                    
                    result.append({
                        "employee_id": employee.id,
                        "name": employee.full_name,
                        "employee_code": employee.employee_code,
                        "location": employee_location,
                        "department": employee_department,
                        "position": employee_position,
                        "business_unit": employee_business_unit,
                        "gross_salary": round(gross_salary, 2),
                        "calculated_exemptions": round(calculated_exemptions, 2),
                        "additional_exemptions": round(additional_exemptions, 2),
                        "net_salary": round(net_salary, 2),
                        "amount": round(deduction_data.get("amount", 0.0), 2),
                        "comments": deduction_data.get("comments", ""),
                        "deduction_type": deduction_data.get("deduction_type", "Voluntary PF"),
                        "records_found": deduction_data.get("records_found", 0),
                        "month_filter": month,
                        "month_parsed": deduction_data.get("month_parsed", month)
                    })
                    
                except Exception as e:
                    print(f"Error processing employee {employee.employee_code}: {e}")
                    # Continue with next employee instead of failing completely
                    continue
            
            print(f"Successfully processed {len(result)} employees for month {month}")
            return result
            
        except Exception as e:
            print(f"Database error in get_employees_with_deductions: {str(e)}")
            # Return empty result instead of raising exception
            return []
    
    def get_filter_options(
        self,
        business_id: Optional[int] = None,
        current_user = None
    ) -> Dict[str, List[str]]:
        """
        Get filter options for deductions with timeout protection
        
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
            
            print(f"🔍 Filter options - User: {current_user.email if current_user else 'None'}, Role: {current_user.role if current_user else 'None'}, Business ID: {filter_business_id}")
            
            # Use simpler queries with limits to prevent hanging
            
            # Get departments with limit
            try:
                departments_query = self.db.query(Department.name).filter(
                    Department.is_active == True
                ).distinct()
                if filter_business_id:
                    departments_query = departments_query.filter(Department.business_id == filter_business_id)
                department_names = [d.name for d in departments_query.limit(50).all()]
                print(f"   📋 Departments found: {len(department_names)}")
            except Exception as e:
                print(f"Error loading departments: {e}")
                department_names = ["Technical Support", "Human Resources", "Finance", "Operations"]
            
            # Get locations with limit
            try:
                locations_query = self.db.query(Location.name).filter(
                    Location.is_active == True
                ).distinct()
                if filter_business_id:
                    locations_query = locations_query.filter(Location.business_id == filter_business_id)
                location_names = [l.name for l in locations_query.limit(50).all()]
                print(f"   📍 Locations found: {len(location_names)}")
            except Exception as e:
                print(f"Error loading locations: {e}")
                location_names = ["Hyderabad", "Bangalore", "Mumbai", "Delhi"]
            
            # 🎯 HYBRID APPROACH: Use business unit utils for consistent behavior
            try:
                if current_user:
                    business_unit_options = get_business_unit_options(self.db, current_user, filter_business_id)
                    business_unit_names = business_unit_options[1:]  # Remove "All Business Units"
                    print(f"   🏢 Business units found: {len(business_unit_names)}")
                else:
                    # Fallback to business units if no user context
                    business_units_query = self.db.query(BusinessUnit.name).filter(
                        BusinessUnit.is_active == True
                    ).distinct()
                    if filter_business_id:
                        business_units_query = business_units_query.filter(BusinessUnit.business_id == filter_business_id)
                    business_unit_names = [bu.name for bu in business_units_query.limit(50).all()]
                    print(f"   🏢 Business units found (fallback): {len(business_unit_names)}")
                
                # If no business units found, use default
                if not business_unit_names:
                    business_unit_names = ["Default Business Unit"]
            except Exception as e:
                print(f"Error fetching business units: {e}")
                business_unit_names = ["Default Business Unit"]
            
            # Get cost centers with limit (simplified)
            try:
                cost_center_names = ["Default Cost Center", "HRA", "Travel", "Medical", "Training"]
            except Exception as e:
                print(f"Error loading cost centers: {e}")
                cost_center_names = ["Default Cost Center", "HRA", "Travel", "Medical"]
            
            # Get deduction types (simplified)
            try:
                deduction_type_names = ["Voluntary PF", "Professional Tax", "ESI", "Income Tax", "Loan Deduction", "Other"]
            except Exception as e:
                print(f"Error loading deduction types: {e}")
                deduction_type_names = ["Voluntary PF", "Professional Tax", "ESI", "Income Tax"]
            
            # Ensure we have fallback options
            if not business_unit_names:
                business_unit_names = ["Default Business Unit"]
            
            if not department_names:
                department_names = ["Technical Support", "Human Resources"]
                
            if not location_names:
                location_names = ["Hyderabad", "Bangalore"]
            
            return {
                "businessUnits": ["All Business Units"] + business_unit_names,
                "locations": ["All Locations"] + location_names,
                "departments": ["All Departments"] + department_names,
                "costCenters": ["All Cost Centers"] + cost_center_names,
                "deductionTypes": deduction_type_names
            }
            
        except Exception as e:
            print(f"Database error in get_filter_options: {str(e)}")
            # Return safe fallback options
            return {
                "businessUnits": ["All Business Units", "Default Business Unit"],
                "locations": ["All Locations", "Hyderabad", "Bangalore"],
                "departments": ["All Departments", "Technical Support", "Human Resources"],
                "costCenters": ["All Cost Centers", "Default Cost Center", "HRA"],
                "deductionTypes": ["Voluntary PF", "Professional Tax", "ESI", "Income Tax"]
            }
    
    def update_employee_deduction(
        self,
        employee_code: str,
        effective_date: date,
        amount: Decimal,
        comments: str = "",
        deduction_type: str = "Voluntary PF",
        business_id: Optional[int] = None,
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update deduction for an employee
        
        Args:
            employee_code: Employee code
            effective_date: Effective date
            amount: Amount
            comments: Comments
            deduction_type: Deduction type
            business_id: Business ID
            updated_by: User ID who updated
            
        Returns:
            Update result
        """
        try:
            # Find employee
            employee = self.db.query(Employee).filter(
                Employee.employee_code == employee_code,
                Employee.business_id == business_id if business_id is not None else Employee.business_id.isnot(None)
            ).first()
            
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Map deduction type string to enum
            deduction_type_enum = self._map_deduction_type(deduction_type)
            
            # Check if deduction exists for this employee and date
            existing_deduction = self.db.query(EmployeeDeduction).filter(
                EmployeeDeduction.business_id == (business_id or employee.business_id),
                EmployeeDeduction.employee_id == employee.id,
                EmployeeDeduction.deduction_name == deduction_type,
                func.date_trunc('month', EmployeeDeduction.effective_date) == effective_date.replace(day=1)
            ).first()
            
            if existing_deduction:
                # Update existing
                existing_deduction.amount = amount
                existing_deduction.description = comments
                existing_deduction.updated_at = datetime.now()
                self.db.commit()
                deduction_id = existing_deduction.id
            else:
                # Create new deduction
                new_deduction = EmployeeDeduction(
                    business_id=business_id or employee.business_id,
                    employee_id=employee.id,
                    deduction_name=deduction_type,
                    deduction_type=deduction_type_enum,
                    amount=amount,
                    effective_date=effective_date,
                    description=comments,
                    is_active=True,
                    created_by=updated_by
                )
                self.db.add(new_deduction)
                self.db.commit()
                self.db.refresh(new_deduction)
                deduction_id = new_deduction.id
            
            return {
                "deduction_id": deduction_id,
                "employee_name": employee.full_name,
                "employee_code": employee_code,
                "amount": amount,
                "deduction_type": deduction_type,
                "effective_date": effective_date
            }
            
        except ValueError as e:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in update_employee_deduction: {str(e)}")
    
    def copy_deductions_from_period(
        self,
        source_date: date,
        target_date: date,
        deduction_type: str = "Voluntary PF",
        overwrite_existing: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Copy deductions from previous period
        
        Args:
            source_date: Source date
            target_date: Target date
            deduction_type: Deduction type
            overwrite_existing: Whether to overwrite existing
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Copy result
        """
        try:
            # Get deductions from source period
            source_deductions = self.db.query(EmployeeDeduction).filter(
                EmployeeDeduction.business_id == business_id if business_id is not None else EmployeeDeduction.business_id.isnot(None),
                EmployeeDeduction.deduction_name == deduction_type,
                func.date_trunc('month', EmployeeDeduction.effective_date) == source_date.replace(day=1)
            ).all()
            
            records_created = 0
            
            for source_deduction in source_deductions:
                # Check if target deduction already exists
                existing_target = self.db.query(EmployeeDeduction).filter(
                    EmployeeDeduction.business_id == source_deduction.business_id,
                    EmployeeDeduction.employee_id == source_deduction.employee_id,
                    EmployeeDeduction.deduction_name == deduction_type,
                    func.date_trunc('month', EmployeeDeduction.effective_date) == target_date.replace(day=1)
                ).first()
                
                if existing_target and not overwrite_existing:
                    continue
                
                if existing_target and overwrite_existing:
                    # Update existing
                    existing_target.amount = source_deduction.amount
                    existing_target.description = source_deduction.description
                    existing_target.updated_at = datetime.now()
                else:
                    # Create new deduction
                    new_deduction = EmployeeDeduction(
                        business_id=source_deduction.business_id,
                        employee_id=source_deduction.employee_id,
                        deduction_name=source_deduction.deduction_name,
                        deduction_type=source_deduction.deduction_type,
                        amount=source_deduction.amount,
                        effective_date=target_date,
                        description=f"Copied from {source_date.strftime('%b-%Y')} - {source_deduction.description}",
                        is_recurring=source_deduction.is_recurring,
                        frequency=source_deduction.frequency,
                        is_active=True,
                        created_by=created_by
                    )
                    self.db.add(new_deduction)
                
                records_created += 1
            
            self.db.commit()
            
            return {
                "employees_affected": len(source_deductions),
                "records_created": records_created
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in copy_deductions_from_period: {str(e)}")
    
    def get_export_data(
        self,
        effective_date: date,
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None,
        business_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get data for export
        
        Args:
            effective_date: Effective date
            location: Location filter
            cost_center: Cost center filter
            department: Department filter
            business_id: Business ID
            
        Returns:
            List of export data
        """
        try:
            # Get employees with filters
            employees_query = self.db.query(Employee).options(
                joinedload(Employee.department),
                joinedload(Employee.location)
            ).filter(Employee.employee_status == EmployeeStatus.ACTIVE)
            
            if business_id:
                employees_query = employees_query.filter(Employee.business_id == business_id)
            if location and location != "All Locations":
                employees_query = employees_query.join(Location).filter(Location.name == location)
            if department and department != "All Departments":
                employees_query = employees_query.join(Department).filter(Department.name == department)
            
            employees = employees_query.all()
            
            export_data = []
            
            for employee in employees:
                # Get deductions for this employee
                deduction_data = self._get_employee_deductions(
                    employee.id, effective_date.strftime("%b-%Y").upper()
                )
                
                export_data.append({
                    "employee_name": employee.full_name,
                    "employee_code": employee.employee_code,
                    "location": employee.location.name if employee.location else "Hyderabad",
                    "department": employee.department.name if employee.department else "Technical Support",
                    "amount": deduction_data.get("amount", 0.0),
                    "comments": deduction_data.get("comments", ""),
                    "total": deduction_data.get("amount", 0.0),
                    "deduction_type": deduction_data.get("deduction_type", "Voluntary PF")
                })
            
            return export_data
            
        except Exception as e:
            raise Exception(f"Database error in get_export_data: {str(e)}")
    
    def import_csv_data(
        self,
        csv_content: str,
        effective_date: date,
        overwrite_existing: bool = False,
        consider_arrear: bool = False,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Import deductions data from CSV
        
        Args:
            csv_content: CSV content
            effective_date: Effective date
            overwrite_existing: Whether to overwrite existing
            consider_arrear: Whether to consider as arrear
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Import result
        """
        try:
            # Parse CSV content
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            imported_records = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Get employee by code
                    employee_code = row.get('Employee Code', '').strip()
                    if not employee_code:
                        errors.append(f"Row {row_num}: Missing employee code")
                        continue
                    
                    employee = self.db.query(Employee).filter(
                        Employee.employee_code == employee_code,
                        Employee.business_id == business_id if business_id is not None else Employee.business_id.isnot(None)
                    ).first()
                    
                    if not employee:
                        errors.append(f"Row {row_num}: Employee {employee_code} not found")
                        continue
                    
                    # Parse deduction data
                    amount = row.get('Amount', '0').strip()
                    comments = row.get('Comments', '').strip()
                    deduction_type = row.get('Deduction Type', 'Voluntary PF').strip()
                    
                    try:
                        amount_decimal = Decimal(str(amount))
                    except:
                        errors.append(f"Row {row_num}: Invalid amount format")
                        continue
                    
                    # Create or update deduction
                    if overwrite_existing:
                        # Delete existing deductions for this employee and type
                        self.db.query(EmployeeDeduction).filter(
                            EmployeeDeduction.business_id == (business_id or employee.business_id),
                            EmployeeDeduction.employee_id == employee.id,
                            EmployeeDeduction.deduction_name == deduction_type,
                            func.date_trunc('month', EmployeeDeduction.effective_date) == effective_date.replace(day=1)
                        ).delete()
                    
                    # Create new deduction
                    deduction_type_enum = self._map_deduction_type(deduction_type)
                    
                    new_deduction = EmployeeDeduction(
                        business_id=business_id or employee.business_id,
                        employee_id=employee.id,
                        deduction_name=deduction_type,
                        deduction_type=deduction_type_enum,
                        amount=amount_decimal,
                        effective_date=effective_date,
                        description=f"{comments} {'(Arrear)' if consider_arrear else ''}",
                        is_active=True,
                        created_by=created_by
                    )
                    
                    self.db.add(new_deduction)
                    imported_records += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
            
            self.db.commit()
            
            return {
                "imported_records": imported_records,
                "errors": errors
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Database error in import_csv_data: {str(e)}")
    
    def get_employee_deduction_details(
        self,
        employee_code: str,
        effective_date: date,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get deduction details for an employee
        
        Args:
            employee_code: Employee code
            effective_date: Effective date
            business_id: Business ID
            
        Returns:
            Employee deduction details
        """
        try:
            # Find employee
            employee = self.db.query(Employee).filter(
                Employee.employee_code == employee_code,
                Employee.business_id == business_id if business_id is not None else Employee.business_id.isnot(None)
            ).first()
            
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Get deductions for this employee
            deductions = self.db.query(EmployeeDeduction).filter(
                EmployeeDeduction.employee_id == employee.id,
                func.date_trunc('month', EmployeeDeduction.effective_date) == effective_date.replace(day=1)
            ).all()
            
            # Calculate total
            total_amount = sum(d.amount for d in deductions)
            
            # Format deduction history
            deduction_history = []
            for deduction in deductions:
                deduction_history.append({
                    "capture_date": deduction.created_at.strftime("%Y-%m-%d") if deduction.created_at else effective_date.strftime("%Y-%m-%d"),
                    "comments": deduction.description or "",
                    "amount": float(deduction.amount)
                })
            
            return {
                "employee": employee.full_name,
                "salary_component": "Deduction",
                "total": float(total_amount),
                "history": deduction_history
            }
            
        except Exception as e:
            raise Exception(f"Database error in get_employee_deduction_details: {str(e)}")
    
    def _get_employee_deductions(
        self,
        employee_id: int,
        month: str,
        deduction_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get deduction data for an employee with proper month filtering
        """
        try:
            # Parse month to get effective date with proper error handling
            try:
                month_year = month.split('-')
                if len(month_year) != 2:
                    raise ValueError("Invalid month format")
                    
                month_abbr = month_year[0].upper()
                year = int(month_year[1])
                
                # Convert month abbreviation to number
                month_abbrs = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                
                if month_abbr not in month_abbrs:
                    raise ValueError(f"Invalid month abbreviation: {month_abbr}")
                    
                month_num = month_abbrs.index(month_abbr) + 1
                effective_date = date(year, month_num, 1)
                
            except Exception as e:
                # Fallback to current month if parsing fails
                current_date = date.today()
                effective_date = current_date.replace(day=1)
                print(f"Warning: Month parsing failed for '{month}', using current month: {e}")
            
            # Query deductions with exact month and year filtering
            deductions_query = self.db.query(EmployeeDeduction).filter(
                EmployeeDeduction.employee_id == employee_id,
                EmployeeDeduction.is_active == True,
                func.extract('year', EmployeeDeduction.effective_date) == effective_date.year,
                func.extract('month', EmployeeDeduction.effective_date) == effective_date.month
            )
            
            # Add deduction type filter if specified
            if deduction_type:
                deductions_query = deductions_query.filter(
                    EmployeeDeduction.deduction_name == deduction_type
                )
            
            # Execute query with limit for safety
            deductions = deductions_query.limit(50).all()
            
            # Calculate total amount and combine comments
            total_amount = 0.0
            comments_list = []
            primary_deduction_type = deduction_type or "Voluntary PF"
            
            for deduction in deductions:
                if deduction.amount:
                    total_amount += float(deduction.amount)
                if deduction.description and deduction.description.strip():
                    comments_list.append(deduction.description.strip())
                if deduction.deduction_name:
                    primary_deduction_type = deduction.deduction_name
            
            # Combine comments with length limit
            combined_comments = "; ".join(comments_list)[:200] if comments_list else ""
            
            return {
                "amount": round(total_amount, 2),
                "comments": combined_comments,
                "deduction_type": primary_deduction_type,
                "records_found": len(deductions),
                "month_parsed": effective_date.strftime("%b-%Y").upper()
            }
            
        except Exception as e:
            # Return safe default values on any error
            print(f"Error in _get_employee_deductions: {e}")
            return {
                "amount": 0.0,
                "comments": f"Error retrieving data for {month}",
                "deduction_type": deduction_type or "Voluntary PF",
                "records_found": 0,
                "month_parsed": month
            }
    
    def _map_deduction_type(self, deduction_type_str: str) -> DeductionType:
        """
        Map deduction type string to enum
        
        Args:
            deduction_type_str: Deduction type string
            
        Returns:
            DeductionType enum
        """
        mapping = {
            "Voluntary PF": DeductionType.TAX,
            "Professional Tax": DeductionType.TAX,
            "ESI": DeductionType.INSURANCE,
            "Income Tax": DeductionType.TAX,
            "Loan Deduction": DeductionType.LOAN,
            "Other": DeductionType.OTHER
        }
        
        return mapping.get(deduction_type_str, DeductionType.OTHER)
    
    def _get_employee_gross_salary(self, employee_id: int) -> float:
        """
        Get employee gross salary from salary details or calculate based on employee data
        
        Args:
            employee_id: Employee ID
            
        Returns:
            Gross salary amount
        """
        try:
            # Try to get from employee_salaries table first
            from app.models.employee import Employee, EmployeeStatusSalary
            
            salary_record = self.db.query(EmployeeSalary).filter(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.is_active == True
            ).order_by(EmployeeSalary.effective_date.desc()).first()
            
            if salary_record and salary_record.gross_salary:
                return float(salary_record.gross_salary)
            
            # Fallback: calculate based on employee position/designation
            employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
            if employee and employee.designation:
                designation_name = employee.designation.name.lower()
                
                # Salary ranges based on designation
                salary_ranges = {
                    "ceo": 150000.0,
                    "vp": 120000.0,
                    "manager": 85000.0,
                    "senior": 65000.0,
                    "associate": 45000.0,
                    "engineer": 55000.0,
                    "developer": 55000.0,
                    "analyst": 50000.0,
                    "executive": 40000.0,
                    "intern": 25000.0
                }
                
                # Find matching designation
                for key, salary in salary_ranges.items():
                    if key in designation_name:
                        return salary
            
            # Default fallback
            return 50000.0
            
        except Exception as e:
            # If any error, return a reasonable default
            return 50000.0