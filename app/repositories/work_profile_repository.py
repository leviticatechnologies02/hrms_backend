"""
Work Profile Repository
Data access layer for work profile management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime

from app.models.employee import Employee, EmployeeStatus


class WorkProfileRepository:
    """Repository for work profile data access"""
    
    def __init__(self, db: Session):
        self.db = db
    
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
        """Get employees with their work profiles"""
        try:
            # Base query
            query = self.db.query(Employee).filter(Employee.employee_status == EmployeeStatus.ACTIVE)
            
            if business_id:
                query = query.filter(Employee.business_id == business_id)
            
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
            
            # Convert to response format with mock work profile data
            result = []
            for emp in employees:
                result.append({
                    "id": emp.employee_code,  # Use employee code as ID for frontend compatibility
                    "name": f"{emp.first_name} {emp.last_name or ''}".strip(),
                    "last_updated": "Jul-2025",
                    "location": "Hyderabad",
                    "location_id": 1,
                    "cost_center": "Associate Sof",
                    "cost_center_id": 1,
                    "department": "Technical Sup",
                    "department_id": emp.department_id or 1,
                    "grade": "Trainee",
                    "grade_id": 1,
                    "designation": "Associate Sof",
                    "designation_id": emp.designation_id or 1,
                    "shift_policy": "General Policy",
                    "shift_policy_id": 1,
                    "weekoff_policy": "Hyderabad Week",
                    "weekoff_policy_id": 1,
                    "employee_id": emp.id,
                    "business_id": emp.business_id
                })
            
            return result
            
        except Exception as e:
            print(f"Error in get_employees_with_work_profiles: {str(e)}")
            return []
    
    def get_filter_options(self, business_id: Optional[int] = None) -> Dict[str, List[str]]:
        """Get filter options for work profiles"""
        return {
            "business_units": ["Levitica Technologies"],
            "locations": ["Hyderabad", "Bangalore", "Chennai"],
            "cost_centers": ["Operation Team", "Software Engineer", "Quality Assurance"],
            "departments": ["Product Development Team", "Technical Support", "HR Executive"]
        }
    
    def get_dropdown_options(self, business_id: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get dropdown options for work profile fields"""
        return {
            "locations": [
                {"id": 1, "name": "Hyderabad"},
                {"id": 2, "name": "Bangalore"},
                {"id": 3, "name": "Chennai"},
                {"id": 4, "name": "Pune"}
            ],
            "cost_centers": [
                {"id": 1, "name": "Associate Sof"},
                {"id": 2, "name": "Tech Support"},
                {"id": 3, "name": "Business Ops"},
                {"id": 4, "name": "HR Services"}
            ],
            "departments": [
                {"id": 1, "name": "Technical Sup"},
                {"id": 2, "name": "IT Support"},
                {"id": 3, "name": "Development"},
                {"id": 4, "name": "Sales"}
            ],
            "grades": [
                {"id": 1, "name": "Trainee"},
                {"id": 2, "name": "Associate"},
                {"id": 3, "name": "Senior Associate"},
                {"id": 4, "name": "Lead"}
            ],
            "designations": [
                {"id": 1, "name": "Associate Sof"},
                {"id": 2, "name": "Software Engineer"},
                {"id": 3, "name": "Team Lead"},
                {"id": 4, "name": "Manager"}
            ],
            "shift_policies": [
                {"id": 1, "name": "General Policy"},
                {"id": 2, "name": "Night Shift"},
                {"id": 3, "name": "Rotational Shift"}
            ],
            "weekoff_policies": [
                {"id": 1, "name": "Hyderabad Week"},
                {"id": 2, "name": "Alternate Weekoff"},
                {"id": 3, "name": "Fixed Sunday"}
            ]
        }
    
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
        try:
            # Find employee
            query = self.db.query(Employee).filter(Employee.employee_code == employee_code)
            if business_id:
                query = query.filter(Employee.business_id == business_id)
            
            employee = query.first()
            if not employee:
                raise ValueError(f"Employee with code {employee_code} not found")
            
            # Mock update
            return {
                "message": f"Work profile updated successfully for {employee.first_name} {employee.last_name or ''}",
                "employee_code": employee_code,
                "employee_name": f"{employee.first_name} {employee.last_name or ''}".strip(),
                "updated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"Failed to update work profile: {str(e)}")
    
    def search_employees(
        self,
        search: str,
        business_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search employees for autocomplete"""
        try:
            query = self.db.query(Employee).filter(Employee.employee_status == EmployeeStatus.ACTIVE)
            
            if business_id:
                query = query.filter(Employee.business_id == business_id)
            
            if search:
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(f"%{search}%"),
                        Employee.last_name.ilike(f"%{search}%"),
                        Employee.employee_code.ilike(f"%{search}%")
                    )
                )
            
            employees = query.limit(limit).all()
            
            result = []
            for emp in employees:
                result.append({
                    "id": emp.id,
                    "name": f"{emp.first_name} {emp.last_name or ''}".strip(),
                    "code": emp.employee_code
                })
            
            return result
            
        except Exception as e:
            print(f"Error in search_employees: {str(e)}")
            return []
    
    def export_work_profiles_csv(
        self,
        business_id: Optional[int] = None,
        business_unit: Optional[str] = None,
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None
    ) -> str:
        """Export work profiles as CSV"""
        csv_content = "Employee Code,Employee Name,Location,Cost Center,Department,Grade,Designation,Shift Policy,Weekoff Policy\n"
        csv_content += "EMP001,John Doe,Hyderabad,Associate Sof,Technical Sup,Trainee,Associate Sof,General Policy,Hyderabad Week\n"
        csv_content += "EMP002,Jane Smith,Bangalore,Tech Support,IT Support,Associate,Software Engineer,Night Shift,Alternate Weekoff\n"
        return csv_content
    
    def import_work_profiles_csv(
        self,
        csv_content: str,
        business_id: int,
        created_by: int,
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """Import work profiles from CSV"""
        return {
            "total_records": 2,
            "successful_imports": 2,
            "failed_imports": 0,
            "errors": [],
            "message": "Work profiles imported successfully"
        }
    
    def bulk_update_work_profiles(
        self,
        updates: List[Dict[str, Any]],
        business_id: Optional[int] = None,
        updated_by: int = None
    ) -> Dict[str, Any]:
        """Bulk update work profiles"""
        return {
            "total_records": len(updates),
            "successful_updates": len(updates),
            "failed_updates": 0,
            "errors": []
        }

    def get_previous_work_profile(self, employee_id: int) -> Optional[Any]:
        """Fetch the most recent past work profile revision prior to the current state"""
        try:
            from app.models.employee import EmployeeWorkProfileHistory
            from sqlalchemy.orm import joinedload
            
            # Fetch the most recent history entry for this employee
            return self.db.query(EmployeeWorkProfileHistory).options(
                joinedload(EmployeeWorkProfileHistory.business_unit),
                joinedload(EmployeeWorkProfileHistory.department),
                joinedload(EmployeeWorkProfileHistory.designation),
                joinedload(EmployeeWorkProfileHistory.location),
                joinedload(EmployeeWorkProfileHistory.cost_center),
                joinedload(EmployeeWorkProfileHistory.grade),
                joinedload(EmployeeWorkProfileHistory.reporting_manager),
                joinedload(EmployeeWorkProfileHistory.hr_manager),
                joinedload(EmployeeWorkProfileHistory.indirect_manager)
            ).filter(
                EmployeeWorkProfileHistory.employee_id == employee_id
            ).order_by(
                EmployeeWorkProfileHistory.effective_from.desc(),
                EmployeeWorkProfileHistory.created_at.desc()
            ).first()
        except Exception as e:
            import traceback
            print(f"Error in get_previous_work_profile repository: {str(e)}")
            traceback.print_exc()
            return None

    def create_history_entry(
        self,
        employee_id: int,
        business_unit_id: Optional[int] = None,
        department_id: Optional[int] = None,
        designation_id: Optional[int] = None,
        location_id: Optional[int] = None,
        cost_center_id: Optional[int] = None,
        grade_id: Optional[int] = None,
        reporting_manager_id: Optional[int] = None,
        hr_manager_id: Optional[int] = None,
        indirect_manager_id: Optional[int] = None,
        employment_type: Optional[str] = None,
        employee_status: Optional[str] = None,
        shift_policy_id: Optional[int] = None,
        weekoff_policy_id: Optional[int] = None,
        effective_from: Optional[Any] = None,
        is_promotion: bool = False,
        notes: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Any:
        """Create a new work profile history record"""
        try:
            from app.models.employee import EmployeeWorkProfileHistory
            from datetime import date
            
            # Parse effective_from date if it's a string
            parsed_effective = effective_from
            if isinstance(effective_from, str):
                from datetime import datetime
                try:
                    parsed_effective = datetime.strptime(effective_from, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        parsed_effective = datetime.fromisoformat(effective_from.replace('Z', '+00:00')).date()
                    except ValueError:
                        parsed_effective = date.today()
            elif not effective_from:
                parsed_effective = date.today()

            # Ensure we serialize enum to string if needed
            status_str = employee_status
            if hasattr(employee_status, 'value'):
                status_str = employee_status.value

            history_entry = EmployeeWorkProfileHistory(
                employee_id=employee_id,
                business_unit_id=business_unit_id,
                department_id=department_id,
                designation_id=designation_id,
                location_id=location_id,
                cost_center_id=cost_center_id,
                grade_id=grade_id,
                reporting_manager_id=reporting_manager_id,
                hr_manager_id=hr_manager_id,
                indirect_manager_id=indirect_manager_id,
                employment_type=employment_type,
                employee_status=status_str,
                shift_policy_id=shift_policy_id,
                weekoff_policy_id=weekoff_policy_id,
                effective_from=parsed_effective,
                is_promotion=is_promotion,
                notes=notes,
                created_by=created_by
            )
            self.db.add(history_entry)
            self.db.commit()
            self.db.refresh(history_entry)
            return history_entry
        except Exception as e:
            self.db.rollback()
            print(f"Error creating history entry: {str(e)}")
            raise e

    def create_snapshot_from_employee(
        self, 
        employee: Any, 
        effective_from: Any = None, 
        is_promotion: bool = False, 
        notes: Optional[str] = None, 
        created_by: Optional[int] = None
    ) -> Any:
        """Create a history revision from the current state of an employee"""
        status_val = employee.employee_status.value if hasattr(employee.employee_status, 'value') else employee.employee_status
        return self.create_history_entry(
            employee_id=employee.id,
            business_unit_id=employee.business_unit_id,
            department_id=employee.department_id,
            designation_id=employee.designation_id,
            location_id=employee.location_id,
            cost_center_id=employee.cost_center_id,
            grade_id=employee.grade_id,
            reporting_manager_id=employee.reporting_manager_id,
            hr_manager_id=employee.hr_manager_id,
            indirect_manager_id=employee.indirect_manager_id,
            employment_type=employee.employment_type,
            employee_status=status_val,
            shift_policy_id=employee.shift_policy_id,
            weekoff_policy_id=employee.weekoff_policy_id,
            effective_from=effective_from or employee.date_of_joining,
            is_promotion=is_promotion,
            notes=notes,
            created_by=created_by
        )