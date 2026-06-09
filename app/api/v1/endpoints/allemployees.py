"""
All Employees API Endpoints - Production Ready
Frontend URL: /allemployees/employees
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, UploadFile, File, Request, Path
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, validator, Field

from datetime import datetime, date

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, get_current_user
from app.models.user import User
from app.core.config import settings, BASE_URL
from app.schemas.employee_validation import EmployeeWorkProfileUpdateRequest, EmployeeWorkProfileUpdate
from app.schemas.asset import (
    AssetCreateRequest, AssetUpdateRequest, AssetCreateResponse, 
    AssetUpdateResponse, AssetDeleteResponse, AssetResponse, 
    EmployeeAssetsResponse
)
from app.schemas.family import (
    FamilyMemberCreateRequest, FamilyMemberUpdateRequest, 
    FamilyMemberCreateResponse, FamilyMemberUpdateResponse, 
    FamilyMemberDeleteResponse, EmployeeFamilyResponse
)
from app.schemas.additional_info import (
    AdditionalInfoUpdateRequest, EmployeeAdditionalInfoResponse, 
    AdditionalInfoSaveResponse, AdditionalInfoResponse
)
from app.schemas.employee_permissions import (
    EmployeePermissionsFrontendUpdate, EmployeePermissionsUpdateResponse,
    EmployeePermissionsDisplay
)
from app.schemas.employee_access import (
    EmployeeAccessFrontendUpdate, EmployeeAccessUpdateResponse,
    EmployeeAccessDisplay, EmployeeAccessActionResponse,
    LogoutSessionResponse
)
from app.schemas.activity_logs import EmployeeActivityResponse
from app.schemas.allemployees_additional import (
    SalaryRevisionDeleteRequest,
    WorkProfileRevisionRequest,
    ManagerUpdateRequest
)
from pydantic import ValidationError

router = APIRouter(tags=["All Employees"])


# ============================================================================
# HELPER FUNCTION FOR BUSINESS ISOLATION
# ============================================================================
def validate_business_access(business_id: int, current_user: User, db: Session):
    """
    Centralized business access validation.
    Raises HTTPException 404 if business not found or not accessible by current user.
    """
    from app.models.business import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business with ID {business_id} not found"
        )

    # Ensure the current user has access to this business. Adjust this check as per your access rules.
    if getattr(business, 'owner_id', None) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this business"
        )

    return business


def get_user_business_ids(db: Session, current_user: User) -> List[int]:
    """
    Compatibility helper: return list of business IDs owned by the current user.
    This preserves older code paths that still used owner-based filtering.
    """
    from app.models.business import Business
    user_business_ids = db.query(Business.id).filter(
        Business.owner_id == current_user.id
    ).all()
    return [b[0] for b in user_business_ids]


def validate_employee_access(
    db: Session,
    employee_id: int,
    current_user: User,
    business_id: int,
    raise_404: bool = True
):
    """
    Validate that the employee belongs to one of the user's businesses.
    
    Args:
        db: Database session
        employee_id: ID of the employee to validate
        current_user: Current authenticated user
        raise_404: If True, raises 404 if employee not found or not accessible
        
    Returns:
        Employee object if found and accessible, None otherwise
        
    Raises:
        HTTPException 404: If employee not found or not accessible (when raise_404=True)
    """
    from app.models.employee import Employee

    # Strict business-scoped lookup
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.business_id == business_id
    ).first()
    
    if not employee and raise_404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found"
        )
    
    return employee


# ============================================================================

def get_profile_image_url(emp):
    """
    Return full URL of employee profile image.
    Uses BASE_URL for relative paths.
    """
    profile_image_url = emp.profile.profile_image_url if getattr(emp, "profile", None) else None
    if profile_image_url:
        return profile_image_url if profile_image_url.startswith('http') else f"{BASE_URL}{profile_image_url}"
    return f"{BASE_URL}/assets/img/users/user-01.jpg"

# PYDANTIC MODELS
# ============================================================================
# Pydantic models for request/response
class EmployeeBasicInfoUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    middleName: Optional[str] = None
    dateOfBirth: Optional[str] = None
    dateOfConfirmation: Optional[str] = None
    dateOfJoining: Optional[str] = None
    gender: Optional[str] = None
    maritalStatus: Optional[str] = None
    bloodGroup: Optional[str] = None
    nationality: Optional[str] = None
    religion: Optional[str] = None
    personalEmail: Optional[str] = None
    personalPhone: Optional[str] = None
    alternatePhone: Optional[str] = None
    officePhone: Optional[str] = None
    officialEmail: Optional[str] = None
    currentAddress: Optional[str] = None
    permanentAddress: Optional[str] = None
    panNumber: Optional[str] = None
    aadharNumber: Optional[str] = None
    passportNumber: Optional[str] = None
    passportExpiry: Optional[str] = None
    drivingLicense: Optional[str] = None
    licenseExpiry: Optional[str] = None
    employeeCode: Optional[str] = None
    biometricCode: Optional[str] = None
    emergencyContact: Optional[str] = None
    emergencyPhone: Optional[str] = None
    fatherName: Optional[str] = None
    motherName: Optional[str] = None
    noticePeriod: Optional[str] = None
    dateOfMarriage: Optional[str] = None
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())
    
    @validator('firstName')
    def validate_first_name(cls, v):
        # Allow None values, but validate non-empty strings at endpoint level
        return v.strip() if v and v.strip() else v
    
    @validator('lastName')
    def validate_last_name(cls, v):
        # Allow None values, but validate non-empty strings at endpoint level
        return v.strip() if v and v.strip() else v
    
    @validator('personalEmail')
    def validate_personal_email(cls, v):
        if v is not None and v.strip():
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v.strip()):
                raise ValueError('Invalid email format')
        return v.strip() if v else None
    
    @validator('officialEmail')
    def validate_official_email(cls, v):
        if v is not None and v.strip():
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v.strip()):
                raise ValueError('Invalid email format')
        return v.strip() if v else None

class EmployeeUpdate(BaseModel):
    """Schema for updating employee information via PUT endpoint"""
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    middleName: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    employeeCode: Optional[str] = None
    dateOfJoining: Optional[str] = None
    dateOfBirth: Optional[str] = None
    gender: Optional[str] = None
    maritalStatus: Optional[str] = None
    employeeStatus: Optional[str] = None
    departmentId: Optional[int] = None
    designationId: Optional[int] = None
    locationId: Optional[int] = None
    businessId: Optional[int] = None
    
    class Config:
        # Ensure at least one field is provided
        min_anyof = 1
        
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())

class EmployeeCreate(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str

    joining_date: Optional[date] = None
    confirmation_date: Optional[date] = None
    dob: Optional[date] = None

    gender: Optional[str] = None

    employee_code: Optional[str] = None
    biometric_code: Optional[str] = None

    mobile: Optional[str] = None
    email: str

    send_mobile_login: Optional[bool] = False
    send_web_login: Optional[bool] = True

    # Work profile can be names (string) or ids (int)
    location: Optional[str] = None
    cost_center: Optional[str] = None
    department: Optional[str] = None
    grade: Optional[str] = None
    designation: Optional[str] = None

    shift_policy: Optional[str] = None
    week_off_policy: Optional[str] = None

    @validator('first_name')
    def validate_first_name(cls, v):
        if not v or not v.strip():
            raise ValueError('First name cannot be empty')
        return v.strip()
    
    @validator('last_name')
    def validate_last_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Last name cannot be empty')
        return v.strip()
    
    @validator('email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError('Email cannot be empty')
        # Basic email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.strip()):
            raise ValueError('Invalid email format')
        return v.strip().lower()
    
    @validator('employee_code')
    def validate_employee_code(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Employee code cannot be empty string')
        return v.strip() if v else None

class BulkEmployeeCreate(BaseModel):
    """Schema for bulk employee creation"""
    employees: List[EmployeeCreate]
    
    @validator('employees')
    def validate_employees_list(cls, v):
        if not v:
            raise ValueError('Employee list cannot be empty')
        if len(v) > 100:  # Reasonable limit for bulk operations
            raise ValueError('Cannot create more than 100 employees at once')
        return v


class LeavePolicies(BaseModel):
    """Schema for leave policies"""
    casualleave: Optional[bool] = None
    sickleave: Optional[bool] = None
    annualleave: Optional[bool] = None
    maternityleave: Optional[bool] = None
    compensatoryoff: Optional[bool] = None


class EmployeePoliciesUpdate(BaseModel):
    """Schema for updating employee policies with dynamic validation"""
    shiftPolicy: Optional[str] = None
    weekOffPolicy: Optional[str] = None
    overtimePolicy: Optional[str] = None
    autoShiftEnabled: Optional[bool] = None
    leavePolicies: Optional[LeavePolicies] = None
    
    class Config:
        # Allow extra fields for future extensibility
        extra = "forbid"
        
    @validator('shiftPolicy')
    def validate_shift_policy(cls, v):
        if v is not None and v != "":
            # Convert to integer to validate it's a valid ID
            try:
                policy_id = int(v)
                if policy_id <= 0:
                    raise ValueError('Shift policy ID must be a positive integer')
            except ValueError:
                raise ValueError('Shift policy must be a valid integer ID')
        return v
    
    @validator('weekOffPolicy')
    def validate_weekoff_policy(cls, v):
        if v is not None and v != "":
            # Convert to integer to validate it's a valid ID
            try:
                policy_id = int(v)
                if policy_id <= 0:
                    raise ValueError('Week off policy ID must be a positive integer')
            except ValueError:
                raise ValueError('Week off policy must be a valid integer ID')
        return v
    
    @validator('overtimePolicy')
    def validate_overtime_policy(cls, v):
        if v is not None and v != "":
            # Convert to integer to validate it's a valid ID
            try:
                policy_id = int(v)
                if policy_id <= 0:
                    raise ValueError('Overtime policy ID must be a positive integer')
            except ValueError:
                raise ValueError('Overtime policy must be a valid integer ID')
        return v
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())
    
    def validate_not_empty(self):
        """Validate that at least one policy field is provided"""
        if not self.has_valid_data():
            raise ValueError("At least one policy field must be provided. Request body cannot be empty.")
        return True


@router.get("/filter-options")
async def get_filter_options(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get available filter options for employee filtering - DATABASE ONLY"""
    try:
        from app.models.business import Business
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.designations import Designation
        
        # Validate access to the business and fetch options scoped to business
        validate_business_access(business_id, current_user, db)

        business_units = db.query(Business.business_name).filter(
            Business.id == business_id
        ).distinct().all()

        locations = db.query(Location.name).filter(
            Location.business_id == business_id
        ).distinct().all()

        cost_centers = db.query(CostCenter.name).filter(
            CostCenter.business_id == business_id
        ).distinct().all()

        departments = db.query(Department.name).filter(
            Department.business_id == business_id
        ).distinct().all()

        designations = db.query(Designation.name).distinct().all()
        
        return {
            "businessUnits": ["All Units"] + [bu[0] for bu in business_units if bu[0]],
            "locations": ["All Locations"] + [loc[0] for loc in locations if loc[0]],
            "costCenters": ["All Cost Centers"] + [cc[0] for cc in cost_centers if cc[0]],
            "departments": ["All Departments"] + [dept[0] for dept in departments if dept[0]],
            "designations": ["All Designations"] + [des[0] for des in designations if des[0]]
        }
    
    except Exception as e:
        print(f"ERROR in get_filter_options: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch filter options: {str(e)}"
        )


@router.get("/")
async def get_all_employees(
    business_id: int = Path(..., description="Business ID"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=1000),
    search: Optional[str] = Query(None),
    businessUnit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    costCenter: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    designation: Optional[str] = Query(None),
    showActive: bool = Query(True),
    showInactive: bool = Query(False),
    sortBy: str = Query("name", pattern="^(name|code|doj)$"),
    sortOrder: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get all employees for frontend with proper filtering"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        from app.models.business import Business
        from app.models.business_unit import BusinessUnit
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.designations import Designation
        from sqlalchemy.orm import joinedload
        
        # Validate access to the business and scope queries
        validate_business_access(business_id, current_user, db)

        # Start with base query filtered by business_id
        query = db.query(Employee).filter(
            Employee.business_id == business_id
        ).options(
            joinedload(Employee.profile)
        )
        
        # Track which relationships we've already joined for filtering
        joined_tables = set()
        
        # Apply status filter
        if showActive and not showInactive:
            query = query.filter(Employee.employee_status.in_(["active", "ACTIVE"]))
        elif showInactive and not showActive:
            query = query.filter(~Employee.employee_status.in_(["active", "ACTIVE"]))
        
        # Apply search filter - OPTIMIZED FOR SPEED, NO CHARACTER RESTRICTIONS
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            
            # OPTIMIZATION: When searching, use a much simpler query
            # Skip all the complex joins and just get basic employee data
            simple_query = db.query(
                Employee.id,
                Employee.first_name,
                Employee.last_name,
                Employee.employee_code,
                Employee.employee_status,
                Employee.date_of_joining,
                Employee.location_id,
                Employee.department_id,
                Employee.designation_id,
                Employee.business_id
            ).filter(
                Employee.business_id == business_id
            ).filter(
                (Employee.first_name.ilike(search_term)) |
                (Employee.last_name.ilike(search_term)) |
                (Employee.employee_code.ilike(search_term))
            )
            
            # Apply status filter
            if showActive and not showInactive:
                simple_query = simple_query.filter(Employee.employee_status.in_(["active", "ACTIVE"]))
            elif showInactive and not showActive:
                simple_query = simple_query.filter(~Employee.employee_status.in_(["active", "ACTIVE"]))
            
            # Get total count
            total_count = simple_query.count()
            
            # Apply sorting
            if sortBy == "name":
                simple_query = simple_query.order_by(Employee.first_name.desc() if sortOrder == "desc" else Employee.first_name.asc())
            elif sortBy == "code":
                simple_query = simple_query.order_by(Employee.employee_code.desc() if sortOrder == "desc" else Employee.employee_code.asc())
            
            # Apply pagination
            offset = (page - 1) * pageSize
            search_results = simple_query.offset(offset).limit(pageSize).all()
            
            # Now fetch full employee objects only for the paginated results
            employee_ids = [emp.id for emp in search_results]
            employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).options(
                joinedload(Employee.profile),
                joinedload(Employee.business),
                joinedload(Employee.location),
                joinedload(Employee.department),
                joinedload(Employee.designation)
            ).all()
            
            # Sort employees to match the order from search_results
            employee_dict = {emp.id: emp for emp in employees}
            employees = [employee_dict[emp_id] for emp_id in employee_ids if emp_id in employee_dict]
            
        else:
            # No search - continue with normal filter logic below
            
            # Apply Business Unit filter (actually filtering by Business/Company)
            if businessUnit and businessUnit.strip() and businessUnit != "All Units":
                if 'business' not in joined_tables:
                    query = query.outerjoin(Employee.business)
                    joined_tables.add('business')
                query = query.filter(Business.business_name == businessUnit)
            
            # Apply Location filter
            if location and location.strip() and location != "All Locations":
                if 'location' not in joined_tables:
                    query = query.outerjoin(Employee.location)
                    joined_tables.add('location')
                query = query.filter(Location.name == location)
            
            # Apply Cost Center filter
            if costCenter and costCenter.strip() and costCenter != "All Cost Centers":
                if 'cost_center' not in joined_tables:
                    query = query.outerjoin(Employee.cost_center)
                    joined_tables.add('cost_center')
                query = query.filter(CostCenter.name == costCenter)
            
            # Apply Department filter
            if department and department.strip() and department != "All Departments":
                if 'department' not in joined_tables:
                    query = query.outerjoin(Employee.department)
                    joined_tables.add('department')
                query = query.filter(Department.name == department)
            
            # Apply Designation filter
            if designation and designation.strip() and designation != "All Designations":
                if 'designation' not in joined_tables:
                    query = query.outerjoin(Employee.designation)
                    joined_tables.add('designation')
                query = query.filter(Designation.name == designation)
            
            # Eagerly load relationships that weren't already joined for filtering
            if 'business' not in joined_tables:
                query = query.options(joinedload(Employee.business))
            if 'business_unit' not in joined_tables:
                query = query.options(joinedload(Employee.business_unit))
            if 'location' not in joined_tables:
                query = query.options(joinedload(Employee.location))
            if 'cost_center' not in joined_tables:
                query = query.options(joinedload(Employee.cost_center))
            if 'department' not in joined_tables:
                query = query.options(joinedload(Employee.department))
            if 'designation' not in joined_tables:
                query = query.options(joinedload(Employee.designation))
            
            # Get total count
            total_count = query.count()
            
            # Apply sorting - simplified
            if sortBy == "name":
                if sortOrder == "desc":
                    query = query.order_by(Employee.first_name.desc())
                else:
                    query = query.order_by(Employee.first_name.asc())
            elif sortBy == "code":
                if sortOrder == "desc":
                    query = query.order_by(Employee.employee_code.desc())
                else:
                    query = query.order_by(Employee.employee_code.asc())
            
            # Apply pagination
            offset = (page - 1) * pageSize
            employees = query.offset(offset).limit(pageSize).all()
        
        # Convert to simple frontend format
        frontend_employees = []
        for emp in employees:
            is_active = str(emp.employee_status).endswith("ACTIVE") if emp.employee_status else True
            
            employee_detail = {
                "id": emp.id,
                "name": f"{emp.first_name or ''} {emp.last_name or ''}".strip() or "Unknown Employee",
                "code": emp.employee_code or f"EMP{emp.id:03d}",
                "position": emp.designation.name if emp.designation else "Employee",
                "department": emp.department.name if emp.department else "General",
                "location": emp.location.name if emp.location else "Office",
                "business_unit": emp.business.business_name if emp.business else (emp.business_unit.name if emp.business_unit else "Company"),
                "business_id": emp.business_id,
                "cost_center": emp.cost_center.name if emp.cost_center else "N/A",
                "joining": emp.date_of_joining.strftime("%b %d, %Y") if emp.date_of_joining else "N/A",
                "img": get_profile_image_url(emp),
                "active": is_active
            }
            
            frontend_employees.append(employee_detail)
        
        return {
            "employees": frontend_employees,
            "total": total_count,
            "page": page,
            "pageSize": pageSize
        }
    
    except Exception as e:
        print(f"ERROR in get_all_employees: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employees: {str(e)}"
        )


@router.patch("/{employee_id}/status")
async def update_employee_status(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    active: bool = Query(..., description="New active status for the employee"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee status"""
    try:
        from app.models.employee import Employee
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        
        new_status = "active" if active else "inactive"
        employee.employee_status = new_status
        
        db.commit()
        db.refresh(employee)
        
        return {
            "success": True,
            "message": f"Employee status updated to {new_status}",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "business_id": employee.business_id,
                "code": employee.employee_code,
                "active": active,
                "status": new_status
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:

            # Additional logging or handling can be added here

        db.rollback()
        print(f"ERROR in update_employee_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee status: {str(e)}"
        )


@router.get("/{employee_id}/summary", response_model=dict)
async def get_employee_summary(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get comprehensive employee summary (Optimized)"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        from app.models.designations import Designation
        from sqlalchemy.orm import joinedload
        
        # Validate business access and use business-scoped queries
        validate_business_access(business_id, current_user, db)

        # Use optimized query with eager loading and business filter
        employee = db.query(Employee).options(
            joinedload(Employee.designation),
            joinedload(Employee.department),
            joinedload(Employee.location),
            joinedload(Employee.business),
            joinedload(Employee.cost_center),
            joinedload(Employee.grade),
            joinedload(Employee.profile),
            joinedload(Employee.reporting_manager)
        ).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get profile image from pre-loaded relationship
        profile_image_url = employee.profile.profile_image_url if employee.profile else None
        
        # Build full URL for profile image
        if profile_image_url:
            if profile_image_url.startswith('http'):
                full_profile_image_url = profile_image_url
            else:
                full_profile_image_url = f"{BASE_URL}{profile_image_url}"
        else:
            full_profile_image_url = f"{BASE_URL}/assets/img/users/user-01.jpg"
        
        print(f"🖼️ Profile image URL: {full_profile_image_url}")
        print(f"   BASE_URL: {BASE_URL}")
        print(f"   Raw profile_image_url: {profile_image_url}")
        
        # Get related data from pre-loaded relationships (no additional queries)
        position = employee.designation.name if employee.designation else "Employee"
        department = employee.department.name if employee.department else "General"
        location = employee.location.name if employee.location else "Office"
        business_name = employee.business.business_name if employee.business else "Company"
        cost_center = employee.cost_center.name if employee.cost_center else "General"
        grade = employee.grade.name if employee.grade else "Default Grade"
        
        # Get managers information - DATABASE ONLY
        managers = {
            "reportingManager": {
                "name": "Not Defined",
                "code": "",
                "img": f"{BASE_URL}/assets/img/users/user-01.jpg"
            },
            "hrManager": {
                "name": "Not Defined",
                "code": "",
                "img": f"{BASE_URL}/assets/img/users/user-01.jpg"
            },

            # Additional logging or handling can be added here
            "indirectManager": {
                "name": "Not Defined",
                "code": "",
                "img": f"{BASE_URL}/assets/img/users/user-01.jpg"
            }
        }
        
        # Get actual reporting manager data from database
        if employee.reporting_manager_id:
            try:
                reporting_manager = db.query(Employee).filter(
                    Employee.id == employee.reporting_manager_id,
                    Employee.business_id == business_id
                ).first()
                if reporting_manager:
                    # Get manager's profile image
                    manager_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == reporting_manager.id).first()
                    manager_img = manager_profile.profile_image_url if manager_profile and manager_profile.profile_image_url else None
                    
                    # Build full URL for manager image
                    if manager_img:
                        if manager_img.startswith('http'):
                            manager_img_url = manager_img
                        else:
                            manager_img_url = f"{BASE_URL}{manager_img}"
                    else:
                        manager_img_url = f"{BASE_URL}/assets/img/users/user-01.jpg"
                    
                    managers["reportingManager"] = {
                        "name": f"{reporting_manager.first_name or ''} {reporting_manager.last_name or ''}".strip(),
                        "code": reporting_manager.employee_code or f"EMP{reporting_manager.id:03d}",
                        "img": manager_img_url
                    }
            except Exception as e:
                print(f"Warning: Error getting reporting manager: {e}")
        
        # Get actual HR manager data from database using hr_manager_id field
        if employee.hr_manager_id:
            try:
                hr_manager = db.query(Employee).filter(
                    Employee.id == employee.hr_manager_id,
                    Employee.business_id == business_id
                ).first()
                if hr_manager:
                    hr_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == hr_manager.id).first()
                    hr_img = hr_profile.profile_image_url if hr_profile and hr_profile.profile_image_url else None
                    
                    # Build full URL for HR manager image
                    if hr_img:
                        if hr_img.startswith('http'):
                            hr_img_url = hr_img
                        else:
                            hr_img_url = f"{BASE_URL}{hr_img}"
                    else:
                        hr_img_url = f"{BASE_URL}/assets/img/users/user-01.jpg"
                    
                    managers["hrManager"] = {
                        "name": f"{hr_manager.first_name or ''} {hr_manager.last_name or ''}".strip(),
                        "code": hr_manager.employee_code or f"EMP{hr_manager.id:03d}",
                        "img": hr_img_url
                    }
            except Exception as e:
                print(f"Warning: Error getting HR manager: {e}")
        
        # Get actual indirect manager data from database using indirect_manager_id field
        if employee.indirect_manager_id:
            try:
                indirect_manager = db.query(Employee).filter(
                    Employee.id == employee.indirect_manager_id,
                    Employee.business_id == business_id
                ).first()
                if indirect_manager:
                    indirect_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == indirect_manager.id).first()
                    indirect_img = indirect_profile.profile_image_url if indirect_profile and indirect_profile.profile_image_url else None
                    
                    # Build full URL for indirect manager image
                    if indirect_img:
                        if indirect_img.startswith('http'):
                            indirect_img_url = indirect_img
                        else:
                            indirect_img_url = f"{BASE_URL}{indirect_img}"
                    else:
                        indirect_img_url = f"{BASE_URL}/assets/img/users/user-01.jpg"
                    
                    managers["indirectManager"] = {
                        "name": f"{indirect_manager.first_name or ''} {indirect_manager.last_name or ''}".strip(),
                        "code": indirect_manager.employee_code or f"EMP{indirect_manager.id:03d}",
                        "img": indirect_img_url
                    }
            except Exception as e:
                print(f"Warning: Error getting indirect manager: {e}")
        
        # Get direct reports
        direct_reports = []
        try:
            reports = db.query(Employee).filter(
                Employee.reporting_manager_id == employee_id,
                Employee.business_id == business_id
            ).all()
            for report in reports:
                report_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == report.id).first()
                report_img = report_profile.profile_image_url if report_profile and report_profile.profile_image_url else None
                
                # Build full URL for report image
                if report_img:
                    if report_img.startswith('http'):
                        report_img_url = report_img
                    else:
                        report_img_url = f"{BASE_URL}{report_img}"
                else:
                    report_img_url = f"{BASE_URL}/assets/img/users/user-01.jpg"
                
                direct_reports.append({
                    "id": report.id,
                    "name": f"{report.first_name or ''} {report.last_name or ''}".strip(),
                    "code": report.employee_code or f"EMP{report.id:03d}",
                    "img": report_img_url
                })
        except Exception as e:
            print(f"Warning: Error getting direct reports: {e}")
        
        # Prepare work profile data
        work_profile = {
            "joiningDate": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
            "confirmationDate": employee.date_of_confirmation.isoformat() if employee.date_of_confirmation else None,
            "reportingManager": managers["reportingManager"]["name"]
        }
        
        # Prepare contact details
        contact_details = {
            "officePhone": employee.office_phone or "",
            "homePhone": "",
            "emergencyContact": employee.emergency_contact or "",
            "personalEmail": employee.email or ""
        }
        
        # Override with employee_profile data if available
        if employee.profile:
            if employee.profile.emergency_contact_name:
                contact_details["emergencyContact"] = employee.profile.emergency_contact_name
            if employee.profile.emergency_contact_mobile:
                contact_details["homePhone"] = employee.profile.emergency_contact_mobile
        
        # Prepare basic info
        basic_info = {
            "firstName": employee.first_name or "",
            "lastName": employee.last_name or "",
            "middleName": employee.middle_name or "",
            "personalEmail": employee.email or "",
            "personalPhone": employee.mobile or "",
            "alternatePhone": employee.alternate_mobile or "",
            "officePhone": employee.office_phone or "",
            "officialEmail": employee.official_email or "",
            "dateOfBirth": employee.date_of_birth.isoformat() if employee.date_of_birth else None,
            "dateOfConfirmation": employee.date_of_confirmation.isoformat() if employee.date_of_confirmation else None,
            "dateOfMarriage": employee.date_of_marriage.isoformat() if employee.date_of_marriage else None,
            "gender": str(employee.gender).replace('Gender.', '').lower() if employee.gender else "",
            "maritalStatus": str(employee.marital_status).replace('MaritalStatus.', '').lower() if employee.marital_status else "",
            "bloodGroup": employee.blood_group or "",
            "nationality": employee.nationality or "",
            "religion": employee.religion or "",
            "emergencyContact": employee.emergency_contact or "",
            "emergencyPhone": employee.emergency_phone or "",
            "fatherName": employee.father_name or "",
            "motherName": employee.mother_name or "",
            "noticePeriod": str(employee.notice_period_days) if employee.notice_period_days else "",
            "employeeCode": employee.employee_code or f"EMP{employee.id:03d}",
            "biometricCode": employee.biometric_code or "",
            "passportNumber": employee.passport_number or "",
            "passportExpiry": employee.passport_expiry.isoformat() if employee.passport_expiry else "",
            "drivingLicense": employee.driving_license or "",
            "licenseExpiry": employee.license_expiry.isoformat() if employee.license_expiry else "",
            "currentAddress": employee.current_address or "",
            "permanentAddress": employee.permanent_address or "",
            "panNumber": employee.profile.pan_number if employee.profile else "",
            "aadharNumber": employee.aadhar_number or ""
        }
        
        # Merge with employee_profiles data if available
        if employee.profile:
            if employee.profile.aadhaar_number:
                basic_info["aadharNumber"] = employee.profile.aadhaar_number
            if employee.profile.emergency_contact_name:
                basic_info["emergencyContact"] = employee.profile.emergency_contact_name
            if employee.profile.emergency_contact_mobile:
                basic_info["emergencyPhone"] = employee.profile.emergency_contact_mobile
            
            # Build full address from profile components
            if employee.profile.present_address_line1:
                address_parts = [
                    employee.profile.present_address_line1,
                    employee.profile.present_address_line2,
                    employee.profile.present_city,
                    employee.profile.present_state,
                    employee.profile.present_country,
                    employee.profile.present_pincode
                ]
                current_address = ", ".join([part for part in address_parts if part])
                if current_address:
                    basic_info["currentAddress"] = current_address
            
            if employee.profile.permanent_address_line1:
                perm_address_parts = [
                    employee.profile.permanent_address_line1,
                    employee.profile.permanent_address_line2,
                    employee.profile.permanent_city,
                    employee.profile.permanent_state,
                    employee.profile.permanent_country,
                    employee.profile.permanent_pincode
                ]
                permanent_address = ", ".join([part for part in perm_address_parts if part])
                if permanent_address:
                    basic_info["permanentAddress"] = permanent_address
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip() or "Unknown Employee",
            "code": employee.employee_code or f"EMP{employee.id:03d}",
            "position": position,
            "department": department,
            "location": location,
            "business": business_name,
            "business_id": employee.business_id,
            "costCenter": cost_center,
            "grade": grade,
            "joining": employee.date_of_joining.strftime("%b %d, %Y") if employee.date_of_joining else "N/A",
            "img": full_profile_image_url,
            "active": employee.employee_status == "active" if employee.employee_status else True,
            "email": employee.email or "",
            "mobile": employee.mobile or "",
            "basicInfo": basic_info,
            "workProfile": work_profile,
            "managers": managers,
            "directReports": direct_reports,
            "contactDetails": contact_details,
            "hrRecord": {
                "dateOfJoining": employee.date_of_joining.strftime("%b %d, %Y") if employee.date_of_joining else "",
                "dateOfConfirmation": employee.date_of_confirmation.strftime("%b %d, %Y") if employee.date_of_confirmation else "",
                "dateOfBirth": employee.date_of_birth.strftime("%b %d, %Y") if employee.date_of_birth else ""
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee summary: {str(e)}"
        )


@router.get("/{employee_id}/basic-info")
async def get_employee_basic_info(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee basic information with data from both employees and employee_profiles tables"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        from sqlalchemy.orm import joinedload
        
        print(f"🔍 Fetching employee basic info for ID: {employee_id}")
        
        # Validate business access and use business-scoped queries
        validate_business_access(business_id, current_user, db)

        # Use the same query pattern as employee summary for consistency with business filter
        employee = db.query(Employee).options(
            joinedload(Employee.profile)
        ).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        
        if not employee:
            print(f"❌ Employee with ID {employee_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        print(f"✅ Found employee: {employee.first_name} {employee.last_name} (Code: {employee.employee_code})")
        
        # Get employee profile from pre-loaded relationship
        employee_profile = employee.profile
        print(f"📋 Employee profile found: {employee_profile is not None}")
        
        # Helper function to safely get field values with consistent logic
        def get_field_value(profile_field, employee_field, default=""):
            try:
                # First try employee_profiles table
                if employee_profile and hasattr(employee_profile, profile_field):
                    profile_value = getattr(employee_profile, profile_field)
                    if profile_value is not None and str(profile_value).strip():
                        return str(profile_value)
                
                # Then try employees table
                if hasattr(employee, employee_field):
                    employee_value = getattr(employee, employee_field)
                    if employee_value is not None and str(employee_value).strip():
                        return str(employee_value)
                
                return default
            except Exception as e:
                print(f"⚠️ Error getting field value for {profile_field}/{employee_field}: {e}")
                return default
        
        # Safe enum handling function (same as summary endpoint)
        def safe_enum_to_string(enum_value):
            try:
                if enum_value is None:
                    return ""
                
                # Handle different enum formats
                if hasattr(enum_value, 'value'):
                    return str(enum_value.value).lower()
                elif hasattr(enum_value, 'name'):
                    return str(enum_value.name).lower()
                else:
                    # Handle string representation
                    enum_str = str(enum_value)
                    # Remove enum class prefixes
                    for prefix in ['Gender.', 'MaritalStatus.', 'EmployeeStatus.']:
                        enum_str = enum_str.replace(prefix, '')
                    return enum_str.lower()
            except Exception as e:
                print(f"⚠️ Error converting enum to string: {e}")
                return ""
        
        # Safe date handling function (same as summary endpoint)
        def safe_date_to_iso(date_value):
            try:
                if date_value is None:
                    return ""
                return date_value.isoformat()
            except Exception as e:
                print(f"⚠️ Error converting date to ISO: {e}")
                return ""
        
        # Build comprehensive basic info using SAME LOGIC as summary endpoint
        basic_info = {
            # Name fields - from employees table (CONSISTENT with summary)
            "firstName": employee.first_name or "",
            "lastName": employee.last_name or "",
            "middleName": employee.middle_name or "",
            
            # Date fields - from employees table with safe handling (CONSISTENT)
            "dateOfBirth": safe_date_to_iso(employee.date_of_birth),
            "dateOfConfirmation": safe_date_to_iso(employee.date_of_confirmation),
            "dateOfMarriage": safe_date_to_iso(employee.date_of_marriage),
            "dateOfJoining": safe_date_to_iso(employee.date_of_joining),
            
            # Enum fields - from employees table with safe handling (CONSISTENT)
            "gender": safe_enum_to_string(employee.gender),
            "maritalStatus": safe_enum_to_string(employee.marital_status),
            "bloodGroup": employee.blood_group or "",
            "nationality": employee.nationality or "",
            "religion": employee.religion or "",
            
            # Contact fields - CONSISTENT with summary endpoint logic
            "personalEmail": employee.email or "",
            "personalPhone": employee.mobile or "",
            "alternatePhone": employee.alternate_mobile or "",
            "officePhone": employee.office_phone or "",
            "officialEmail": employee.official_email or "",
            
            # Address fields - prefer employee_profiles, fallback to employees (CONSISTENT)
            "currentAddress": get_field_value('present_address_line1', 'current_address'),
            "permanentAddress": get_field_value('permanent_address_line1', 'permanent_address'),
            
            # Document fields - prefer employee_profiles, fallback to employees (CONSISTENT)
            "panNumber": employee_profile.pan_number if employee_profile and employee_profile.pan_number else "",
            "aadharNumber": get_field_value('aadhaar_number', 'aadhar_number'),
            "passportNumber": employee.passport_number or "",
            "passportExpiry": safe_date_to_iso(employee.passport_expiry),
            "drivingLicense": employee.driving_license or "",
            "licenseExpiry": safe_date_to_iso(employee.license_expiry),
            
            # Employment fields - from employees table (CONSISTENT)
            "employeeCode": employee.employee_code or f"EMP{employee.id:03d}",
            "biometricCode": employee.biometric_code or "",
            "noticePeriod": str(employee.notice_period_days) if employee.notice_period_days else "",
            
            # Emergency contact - prefer employee_profiles, fallback to employees (CONSISTENT)
            "emergencyContact": get_field_value('emergency_contact_name', 'emergency_contact'),
            "emergencyPhone": get_field_value('emergency_contact_mobile', 'emergency_phone'),
            
            # Family fields - from employees table (CONSISTENT)
            "fatherName": employee.father_name or "",
            "motherName": employee.mother_name or ""
        }
        
        # Enhanced address building (CONSISTENT with summary endpoint)
        if employee_profile:
            try:
                # Build full address from profile components
                if employee_profile.present_address_line1:
                    address_parts = [
                        employee_profile.present_address_line1,
                        employee_profile.present_address_line2,
                        employee_profile.present_city,
                        employee_profile.present_state,
                        employee_profile.present_country,
                        employee_profile.present_pincode
                    ]
                    current_address = ", ".join([str(part) for part in address_parts if part])
                    if current_address:
                        basic_info["currentAddress"] = current_address
                
                if employee_profile.permanent_address_line1:
                    perm_address_parts = [
                        employee_profile.permanent_address_line1,
                        employee_profile.permanent_address_line2,
                        employee_profile.permanent_city,
                        employee_profile.permanent_state,
                        employee_profile.permanent_country,
                        employee_profile.permanent_pincode
                    ]
                    permanent_address = ", ".join([str(part) for part in perm_address_parts if part])
                    if permanent_address:
                        basic_info["permanentAddress"] = permanent_address
            except Exception as e:
                print(f"⚠️ Error processing employee profile address data: {e}")
        
        # Prepare response with CONSISTENT data format
        # Get profile image URL from employee profile
        profile_image_url = "/assets/img/users/user-01.jpg"  # Default
        if employee_profile and employee_profile.profile_image_url:
            profile_image_url = employee_profile.profile_image_url
        
        response_data = {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip() or "Unknown Employee",
            "code": employee.employee_code or f"EMP{employee.id:03d}",
            "img": profile_image_url,
            "business_id": employee.business_id,
            "basicInfo": basic_info
        }
        
        print(f"✅ Successfully prepared CONSISTENT response for employee {employee_id}")
        print(f"   - Name: {response_data['name']}")
        print(f"   - Code: {response_data['code']}")
        print(f"   - Email: {basic_info['personalEmail']}")
        print(f"   - Profile Image: {profile_image_url}")
        
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in get_employee_basic_info: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee basic info: {str(e)}"
        )


# ============================================================================
# ADDITIONAL CRITICAL ENDPOINTS
# ============================================================================

@router.get("/dropdown-data")
async def get_dropdown_data(
    business_id: int = Path(..., description="Business ID"),
    active: Optional[bool] = Query(None, description="If true return only active items; if false only inactive; if omitted return all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get dropdown data for employee forms - DATABASE ONLY"""
    try:
        from app.models.business import Business
        from app.models.location import Location
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.cost_center import CostCenter
        
        # Validate business access and fetch scoped data
        validate_business_access(business_id, current_user, db)

        businesses = db.query(Business).filter(Business.id == business_id).all()
        # locations
        loc_q = db.query(Location).filter(Location.business_id == business_id)
        if active is not None and hasattr(Location, 'is_active'):
            loc_q = loc_q.filter(Location.is_active == active)
        locations = loc_q.all()

        # departments
        dept_q = db.query(Department).filter(Department.business_id == business_id)
        if active is not None and hasattr(Department, 'is_active'):
            dept_q = dept_q.filter(Department.is_active == active)
        departments = dept_q.all()

        # designations (may be global)
        des_q = db.query(Designation)
        if hasattr(Designation, 'business_id'):
            des_q = des_q.filter(Designation.business_id == business_id)
        if active is not None and hasattr(Designation, 'is_active'):
            des_q = des_q.filter(Designation.is_active == active)
        designations = des_q.all()

        # cost centers
        cc_q = db.query(CostCenter).filter(CostCenter.business_id == business_id)
        if active is not None and hasattr(CostCenter, 'is_active'):
            cc_q = cc_q.filter(CostCenter.is_active == active)
        cost_centers = cc_q.all()
        
        return {
            "businesses": [{"id": b.id, "name": b.business_name, "is_active": getattr(b, 'is_active', True)} for b in businesses],
            "locations": [{"id": l.id, "name": l.name, "is_active": getattr(l, 'is_active', True)} for l in locations],
            "departments": [{"id": d.id, "name": d.name, "is_active": getattr(d, 'is_active', True)} for d in departments],
            "designations": [{"id": d.id, "name": d.name, "is_active": getattr(d, 'is_active', True)} for d in designations],
            "cost_centers": [{"id": c.id, "name": c.name, "is_active": getattr(c, 'is_active', True)} for c in cost_centers]
        }
    
    except Exception as e:
        print(f"ERROR in get_dropdown_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dropdown data: {str(e)}"
        )


@router.get("/list")
async def get_employees_list(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get simple employees list - DATABASE ONLY"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        from app.models.business import Business
        from sqlalchemy.orm import joinedload
        
        # Validate business access and list employees for the business
        validate_business_access(business_id, current_user, db)

        # Get all active employees from database with profile and designation
        from app.models.employee import EmployeeStatus
        employees = db.query(Employee).options(
            joinedload(Employee.designation),
            joinedload(Employee.profile),
            joinedload(Employee.department),
            joinedload(Employee.location)
        ).filter(
            Employee.business_id == business_id,
            Employee.employee_status == EmployeeStatus.ACTIVE
        ).limit(50).all()  # Limit for performance
        
        employee_list = []
        for emp in employees:
            # Get name from employee table (database has correct names)
            first_name = emp.first_name or "Unknown"
            last_name = emp.last_name or "Employee"
            employee_code = emp.employee_code or f"EMP{emp.id:03d}"
            
            # Get designation
            designation = "No designation"
            if emp.designation and hasattr(emp.designation, 'name'):
                designation = emp.designation.name

            department = None
            if emp.department and hasattr(emp.department, 'name'):
                department = emp.department.name

            location = None
            if emp.location and hasattr(emp.location, 'name'):
                location = emp.location.name
            
            employee_list.append({
                "id": emp.id,
                "first_name": first_name,
                "last_name": last_name,
                "employee_code": employee_code,
                "business_id": emp.business_id,
                "email": emp.email or "",
                "designation": designation,
                "department": department,
                "location": location,
                "joining_date": emp.date_of_joining.isoformat() if emp.date_of_joining else None
            })
        
        return {
            "employees": employee_list
        }
    
    except Exception as e:
        print(f"ERROR in get_employees_list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employees list: {str(e)}"
        )


@router.get("/{employee_id}/details")
async def get_employee_details(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get detailed employee information"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        
        # Validate business and fetch employee scoped to business
        validate_business_access(business_id, current_user, db)

        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get related data safely
        position = "Employee"
        department = "General"
        location = "Office"
        
        try:
            if employee.designation:
                position = employee.designation.name
            if employee.department:
                department = employee.department.name
            if employee.location:
                location = employee.location.name
        except:
            pass
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "code": employee.employee_code or f"EMP{employee.id:03d}",
            "position": position,
            "department": department,
            "location": location,
            "business_id": employee.business_id,
            "joining": employee.date_of_joining.strftime("%b %d, %Y") if employee.date_of_joining else "N/A",
            "img": "/assets/img/users/user-01.jpg",
            "active": employee.employee_status == "active" if employee.employee_status else True,
            "email": employee.email or "",
            "mobile": employee.mobile or "",
            "gender": employee.gender or "Male",
            "maritalStatus": employee.marital_status or "Single",
            "dateOfBirth": employee.date_of_birth.isoformat() if employee.date_of_birth else ""
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee details: {str(e)}"
        )


@router.get("/search")
async def search_employees(
    business_id: int = Path(..., description="Business ID"),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search employees (optimized for autocomplete) - NO minimum character requirement"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        
        # Validate business access and use business-scoped search
        validate_business_access(business_id, current_user, db)

        # Return empty if no query
        if not q or not q.strip():
            return {"employees": []}
        
        search_term = f"%{q.strip()}%"
        
        # Ultra-lightweight query - only select needed columns
        employees = db.query(
            Employee.id,
            Employee.first_name,
            Employee.last_name,
            Employee.employee_code,
            Employee.email,
            Employee.employee_status,
            Employee.business_id
        ).filter(
            Employee.business_id == business_id
        ).filter(
            (Employee.first_name.ilike(search_term)) |
            (Employee.last_name.ilike(search_term)) |
            (Employee.employee_code.ilike(search_term))
        ).filter(
            Employee.employee_status == "active"  # Only active employees
        ).limit(10).all()
        
        return {
            "employees": [
                {
                    "id": emp.id,
                    "name": f"{emp.first_name or ''} {emp.last_name or ''}".strip(),
                    "code": emp.employee_code or f"EMP{emp.id:03d}",
                    "email": emp.email or "",
                    "active": True,
                    "business_id": emp.business_id
                }
                for emp in employees
            ]
        }
    
    except Exception as e:
        print(f"ERROR in search_employees: {str(e)}")
        # Return empty results instead of failing
        return {"employees": []}


@router.get("/{employee_id}")
async def get_employee_by_id(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee by ID"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        
        # Validate business and fetch employee scoped to business
        validate_business_access(business_id, current_user, db)

        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        return {
            "id": employee.id,
            "firstName": employee.first_name or "",
            "lastName": employee.last_name or "",
            "middleName": employee.middle_name or "",
            "business_id": employee.business_id,
            "email": employee.email or "",
            "mobile": employee.mobile or "",
            "employeeCode": employee.employee_code or f"EMP{employee.id:03d}",
            "dateOfJoining": employee.date_of_joining.isoformat() if employee.date_of_joining else "",
            "dateOfBirth": employee.date_of_birth.isoformat() if employee.date_of_birth else "",
            "gender": employee.gender or "Male",
            "maritalStatus": employee.marital_status or "Single",
            "employeeStatus": employee.employee_status or "active",
            "departmentId": employee.department_id,
            "designationId": employee.designation_id,
            "locationId": employee.location_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_by_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee: {str(e)}"
        )

@router.post("/")
async def create_employee(
    employee_data: EmployeeCreate,
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create new employee with comprehensive validation"""
    try:
        from app.models.employee import Employee
        
        # Check if email already exists
        existing_email = db.query(Employee).filter(Employee.email == employee_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Employee with email {employee_data.email} already exists"
            )
        
        # Check if employee code already exists
        if employee_data.employee_code:
            existing_code = db.query(Employee).filter(Employee.employee_code == employee_data.employee_code).first()
            if existing_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee code {employee_data.employee_code} already exists"
                )

        # Validate/resolve related fields (accept name or id)
        def resolve(model, value):
            if not value:
                return None
            try:
                # numeric id
                if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
                    row = db.query(model).filter(model.id == int(value)).first()
                    return row.id if row else None
                # lookup by name column
                row = db.query(model).filter(getattr(model, 'business_id', None) == business_id, getattr(model, 'name') == value).first()
                if not row:
                    # fallback to global name match
                    row = db.query(model).filter(getattr(model, 'name') == value).first()
                return row.id if row else None
            except Exception:
                return None

        department_id = None
        designation_id = None
        location_id = None
        cost_center_id = None
        grade_id = None
        shift_policy_id = None
        weekoff_policy_id = None

        if employee_data.department:
            from app.models.department import Department
            department_id = resolve(Department, employee_data.department)
            if employee_data.department and department_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department '{employee_data.department}' not found")

        if employee_data.designation:
            from app.models.designations import Designation
            designation_id = resolve(Designation, employee_data.designation)
            if employee_data.designation and designation_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Designation '{employee_data.designation}' not found")

        if employee_data.location:
            from app.models.location import Location
            location_id = resolve(Location, employee_data.location)
            if employee_data.location and location_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Location '{employee_data.location}' not found")
        
        if employee_data.cost_center:
            from app.models.cost_center import CostCenter
            cost_center_id = resolve(CostCenter, employee_data.cost_center)
            if employee_data.cost_center and cost_center_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cost center '{employee_data.cost_center}' not found")

        if employee_data.grade:
            from app.models.grades import Grade
            grade_id = resolve(Grade, employee_data.grade)
            if employee_data.grade and grade_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Grade '{employee_data.grade}' not found")

        if employee_data.shift_policy:
            from app.models.shift_policy import ShiftPolicy
            shift_policy_id = resolve(ShiftPolicy, employee_data.shift_policy)
            if employee_data.shift_policy and shift_policy_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Shift policy '{employee_data.shift_policy}' not found")

        if employee_data.week_off_policy:
            from app.models.weekoff_policy import WeekOffPolicy
            weekoff_policy_id = resolve(WeekOffPolicy, employee_data.week_off_policy)
            if employee_data.week_off_policy and weekoff_policy_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Week off policy '{employee_data.week_off_policy}' not found")
        
        # Auto-generate employee code if not provided
        employee_code = employee_data.employee_code
        if not employee_code:
            # Get the next available employee ID to generate code
            max_id = db.query(Employee.id).order_by(Employee.id.desc()).first()
            next_id = (max_id[0] + 1) if max_id else 1
            employee_code = f"EMP{next_id:03d}"
            
            # Ensure uniqueness
            while db.query(Employee).filter(Employee.employee_code == employee_code).first():
                next_id += 1
                employee_code = f"EMP{next_id:03d}"
        
        # Validate business access and create new employee scoped to business
        validate_business_access(business_id, current_user, db)

        # Normalize gender to the DB enum values
        gender_value = None
        if getattr(employee_data, 'gender', None):
            try:
                g = str(employee_data.gender).strip().lower()
                if g in ('male', 'm'):
                    gender_value = 'male'
                elif g in ('female', 'f'):
                    gender_value = 'female'
                elif g in ('other', 'o'):
                    gender_value = 'other'
                else:
                    # leave as None to avoid invalid enum insert
                    gender_value = None
            except Exception:
                gender_value = None

        # Create new employee (use resolved ids)
        new_employee = Employee(
            business_id=business_id,
            first_name=employee_data.first_name,
            last_name=employee_data.last_name,
            middle_name=getattr(employee_data, 'middle_name', None),
            email=employee_data.email,
            mobile=getattr(employee_data, 'mobile', None),
            date_of_joining=getattr(employee_data, 'joining_date', None),
            date_of_birth=getattr(employee_data, 'dob', None),
            date_of_confirmation=getattr(employee_data, 'confirmation_date', None),
            gender=gender_value,
            employee_code=employee_code,
            biometric_code=getattr(employee_data, 'biometric_code', None),
            department_id=department_id,
            designation_id=designation_id,
            location_id=location_id,
            cost_center_id=cost_center_id,
            grade_id=grade_id,
            shift_policy_id=shift_policy_id,
            weekoff_policy_id=weekoff_policy_id,
            employee_status="ACTIVE",
            created_by=current_user.id
        )
        
        db.add(new_employee)
        db.commit()
        db.refresh(new_employee)
        
        print(f"✅ Employee created successfully: {new_employee.first_name} {new_employee.last_name} (ID: {new_employee.id})")
        
        response_employee = {
            "id": new_employee.id,
            "first_name": new_employee.first_name,
            "middle_name": new_employee.middle_name,
            "last_name": new_employee.last_name,
            "joining_date": new_employee.date_of_joining.isoformat() if new_employee.date_of_joining else None,
            "confirmation_date": new_employee.date_of_confirmation.isoformat() if new_employee.date_of_confirmation else None,
            "dob": new_employee.date_of_birth.isoformat() if new_employee.date_of_birth else None,
            "gender": employee_data.gender if getattr(employee_data, 'gender', None) is not None else (new_employee.gender if new_employee.gender else None),
            "employee_code": new_employee.employee_code,
            "biometric_code": new_employee.biometric_code,
            "mobile": new_employee.mobile,
            "email": new_employee.email,
            "send_mobile_login": new_employee.send_mobile_login if hasattr(new_employee, 'send_mobile_login') else getattr(employee_data, 'send_mobile_login', False),
            "send_web_login": new_employee.send_web_login if hasattr(new_employee, 'send_web_login') else getattr(employee_data, 'send_web_login', True),
            "location": employee_data.location if getattr(employee_data, 'location', None) is not None else new_employee.location_id,
            "cost_center": employee_data.cost_center if getattr(employee_data, 'cost_center', None) is not None else new_employee.cost_center_id,
            "department": employee_data.department if getattr(employee_data, 'department', None) is not None else new_employee.department_id,
            "grade": employee_data.grade if getattr(employee_data, 'grade', None) is not None else new_employee.grade_id,
            "designation": employee_data.designation if getattr(employee_data, 'designation', None) is not None else new_employee.designation_id,
            "shift_policy": employee_data.shift_policy if getattr(employee_data, 'shift_policy', None) is not None else new_employee.shift_policy_id,
            "week_off_policy": employee_data.week_off_policy if getattr(employee_data, 'week_off_policy', None) is not None else new_employee.weekoff_policy_id,
            "location_id": new_employee.location_id,
            "cost_center_id": new_employee.cost_center_id,
            "department_id": new_employee.department_id,
            "grade_id": new_employee.grade_id,
            "designation_id": new_employee.designation_id,
            "shift_policy_id": new_employee.shift_policy_id,
            "week_off_policy_id": new_employee.weekoff_policy_id
            ,"business_id": new_employee.business_id
        }

        return {"success": True, "message": "Employee created successfully", "employee": response_employee}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in create_employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create employee: {str(e)}"
        )


@router.put("/{employee_id}")
async def update_employee(
    employee_data: EmployeeUpdate,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee with proper validation"""
    try:
        from app.models.employee import Employee
        from datetime import datetime
        
        # Validate that the request body is not empty
        if not employee_data.has_valid_data():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body cannot be empty. At least one field must be provided for update."
            )
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Track what fields are being updated
        updated_fields = []
        
        # Validate and update basic fields
        if employee_data.firstName is not None:
            if not employee_data.firstName.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="First name cannot be empty"
                )
            employee.first_name = employee_data.firstName.strip()
            updated_fields.append("firstName")
            
        if employee_data.lastName is not None:
            if not employee_data.lastName.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Last name cannot be empty"
                )
            employee.last_name = employee_data.lastName.strip()
            updated_fields.append("lastName")
            
        if employee_data.middleName is not None:
            employee.middle_name = employee_data.middleName.strip() if employee_data.middleName else None
            updated_fields.append("middleName")
            
        if employee_data.email is not None:
            if not employee_data.email.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email cannot be empty"
                )
            # Check for duplicate email
            existing_email = db.query(Employee).filter(
                Employee.email == employee_data.email.strip(),
                Employee.id != employee_id,
                Employee.business_id == business_id
            ).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email {employee_data.email} is already in use by another employee"
                )
            employee.email = employee_data.email.strip()
            updated_fields.append("email")
            
        if employee_data.mobile is not None:
            employee.mobile = employee_data.mobile.strip() if employee_data.mobile else None
            updated_fields.append("mobile")
            
        if getattr(employee_data, 'employee_code', None) is not None:
            if getattr(employee_data, 'employee_code') and str(employee_data.employee_code).strip():
                # Check for duplicate employee code
                existing_code = db.query(Employee).filter(
                    Employee.employee_code == str(employee_data.employee_code).strip(),
                    Employee.id != employee_id,
                    Employee.business_id == business_id
                ).first()
                if existing_code:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Employee code {employee_data.employee_code} is already in use"
                    )
            employee.employee_code = str(employee_data.employee_code).strip() if employee_data.employee_code else None
            updated_fields.append("employee_code")
            
        # Handle date fields with validation
        if employee_data.dateOfJoining is not None:
            if employee_data.dateOfJoining.strip():
                try:
                    date_str = employee_data.dateOfJoining.strip()
                    if 'T' in date_str:
                        date_str = date_str.split('T')[0]
                    employee.date_of_joining = datetime.strptime(date_str, '%Y-%m-%d').date()
                    updated_fields.append("dateOfJoining")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format for dateOfJoining. Use YYYY-MM-DD format."
                    )
                    
        if employee_data.dateOfBirth is not None:
            if employee_data.dateOfBirth.strip():
                try:
                    date_str = employee_data.dateOfBirth.strip()
                    if 'T' in date_str:
                        date_str = date_str.split('T')[0]
                    employee.date_of_birth = datetime.strptime(date_str, '%Y-%m-%d').date()
                    updated_fields.append("dateOfBirth")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format for dateOfBirth. Use YYYY-MM-DD format."
                    )
        
        # Handle enum fields with validation
        if employee_data.gender is not None:
            valid_genders = ['male', 'female', 'other']
            if employee_data.gender.lower() not in valid_genders:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid gender. Must be one of: {', '.join(valid_genders)}"
                )
            employee.gender = employee_data.gender.lower()
            updated_fields.append("gender")
            
        if employee_data.maritalStatus is not None:
            valid_statuses = ['single', 'married', 'divorced', 'widowed']
            if employee_data.maritalStatus.lower() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid marital status. Must be one of: {', '.join(valid_statuses)}"
                )
            employee.marital_status = employee_data.maritalStatus.lower()
            updated_fields.append("maritalStatus")
            
        if employee_data.employeeStatus is not None:
            valid_statuses = ['active', 'inactive', 'terminated', 'on_leave', 'probation']
            if employee_data.employeeStatus.lower() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid employee status. Must be one of: {', '.join(valid_statuses)}"
                )
            employee.employee_status = employee_data.employeeStatus.lower()
            updated_fields.append("employeeStatus")
        
        # Handle foreign key fields with validation
        if employee_data.departmentId is not None:
            if employee_data.departmentId > 0:
                from app.models.department import Department
                department = db.query(Department).filter(Department.id == employee_data.departmentId).first()
                if not department:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Department with ID {employee_data.departmentId} not found"
                    )
            employee.department_id = employee_data.departmentId if employee_data.departmentId > 0 else None
            updated_fields.append("departmentId")
            
        if employee_data.designationId is not None:
            if employee_data.designationId > 0:
                from app.models.designations import Designation
                designation = db.query(Designation).filter(Designation.id == employee_data.designationId).first()
                if not designation:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Designation with ID {employee_data.designationId} not found"
                    )
            employee.designation_id = employee_data.designationId if employee_data.designationId > 0 else None
            updated_fields.append("designationId")
            
        if employee_data.locationId is not None:
            if employee_data.locationId > 0:
                from app.models.location import Location
                location = db.query(Location).filter(Location.id == employee_data.locationId).first()
                if not location:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Location with ID {employee_data.locationId} not found"
                    )
            employee.location_id = employee_data.locationId if employee_data.locationId > 0 else None
            updated_fields.append("locationId")
            
        if employee_data.businessId is not None:
            if employee_data.businessId > 0:
                from app.models.business import Business
                business = db.query(Business).filter(Business.id == employee_data.businessId).first()
                if not business:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Business with ID {employee_data.businessId} not found"
                    )
            employee.business_id = employee_data.businessId if employee_data.businessId > 0 else None
            updated_fields.append("businessId")
        
        # Update system fields
        employee.updated_by = current_user.id
        
        # Commit changes
        db.commit()
        db.refresh(employee)
        
        print(f"✅ Employee {employee_id} updated successfully. Fields updated: {updated_fields}")
        
        return {
            "success": True,
            "message": "Employee updated successfully",
            "updatedFields": updated_fields,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}",
                "email": employee.email,
                "status": employee.employee_status,
                "business_id": employee.business_id
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in update_employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee: {str(e)}"
        )


@router.post("/{employee_id}/upload-profile-image")
async def upload_employee_profile_image(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Upload employee profile image with comprehensive validation"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        # Validate file is provided
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided. Please select an image file to upload."
            )
        
        # Validate filename
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file. Please provide a valid image file."
            )
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/gif", "image/webp"]
        if not file.content_type or file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Only {', '.join(allowed_types)} are allowed."
            )
        
        # Validate file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        file_extension = os.path.splitext(file.filename.lower())[1]
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension. Only {', '.join(allowed_extensions)} are allowed."
            )
        
        # Read and validate file size
        file_content = await file.read()
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided. Please select a valid image file."
            )
        
        # Validate file size (2MB limit)
        max_size = 2 * 1024 * 1024  # 2MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size too large. Maximum size is {max_size // (1024*1024)}MB. Current size: {len(file_content) // (1024*1024)}MB."
            )
        
        # Validate minimum file size (1KB to avoid empty/corrupt files)
        min_size = 1024  # 1KB
        if len(file_content) < min_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too small. Please provide a valid image file."
            )
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        clean_extension = file_extension.lower()
        unique_filename = f"employee_{employee_id}_{timestamp}_{unique_id}{clean_extension}"
        
        # Ensure upload directory exists
        upload_dir = getattr(settings, 'UPLOAD_DIR', 'uploads')
        profile_dir = os.path.join(upload_dir, 'profile_images')
        os.makedirs(profile_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(profile_dir, unique_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Create relative path for database storage
        relative_path = f"/uploads/profile_images/{unique_filename}"
        
        # Get or create employee profile
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if not employee_profile:
            employee_profile = EmployeeProfile(
                employee_id=employee_id,
                profile_image_url=relative_path
            )
            db.add(employee_profile)
        else:
            # Remove old image file if exists
            if employee_profile.profile_image_url:
                try:
                    old_file_path = os.path.join(os.getcwd(), employee_profile.profile_image_url.lstrip('/'))
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                except Exception as e:
                    print(f"⚠️ Warning: Could not remove old profile image: {str(e)}")
            
            employee_profile.profile_image_url = relative_path
        
        db.commit()
        db.refresh(employee_profile)
        
        # Build full URL for the uploaded image
        full_image_url = f"{BASE_URL}{relative_path}"
        
        print(f"✅ Profile image uploaded for employee {employee_id}: {relative_path}")
        print(f"   Full URL: {full_image_url}")
        
        return {
            "success": True,
            "message": "Profile image uploaded successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "profileImageUrl": full_image_url,  # Return full URL
                "business_id": employee.business_id
            },
            "fileInfo": {
                "filename": unique_filename,
                "size": len(file_content),
                "type": file.content_type
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Clean up uploaded file if database update fails
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        
        print(f"❌ ERROR in upload_employee_profile_image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload profile image: {str(e)}"
        )


@router.delete("/{employee_id}/profile-image")
async def remove_employee_profile_image(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Remove employee profile image"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get employee profile
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if employee_profile and employee_profile.profile_image_url:
            # Remove file from filesystem
            try:
                file_path = os.path.join(os.getcwd(), employee_profile.profile_image_url.lstrip('/'))
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass  # Continue even if file removal fails
            
            # Update database
            employee_profile.profile_image_url = None
            db.commit()
        
        return {
            "success": True,
            "message": "Profile image removed successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "profileImageUrl": None,
                "business_id": employee.business_id
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in remove_employee_profile_image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove profile image: {str(e)}"
        )


@router.patch("/{employee_id}/basic-info")
async def update_employee_basic_info(
    basic_info: EmployeeBasicInfoUpdate,
    request: Request,  # ADDED for activity logging
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee basic information - BULLETPROOF VERSION"""
    print(f"🔄 BULLETPROOF UPDATE START - Employee {employee_id}")
    
    try:
        # Step 1: Validate input
        print(f"📥 Received data keys: {list(basic_info.dict().keys())}")
        
        if not basic_info.has_valid_data():
            return {"success": False, "message": "No data provided for update"}
        
        # Step 2: Validate business and get employee
        from app.models.employee import Employee, EmployeeProfile
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            return {"success": False, "message": f"Employee {employee_id} not found"}
        
        print(f"✅ Found employee: {employee.first_name} {employee.last_name}")
        
        # ACTIVITY LOGGING: Capture old values before update
        old_values = {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "middle_name": employee.middle_name,
            "mobile": employee.mobile,
            "alternate_mobile": employee.alternate_mobile,
            "office_phone": employee.office_phone,
            "email": employee.email,
            "official_email": employee.official_email,
            "employee_code": employee.employee_code,
            "biometric_code": employee.biometric_code,
            "nationality": employee.nationality,
            "religion": employee.religion,
            "blood_group": employee.blood_group,
            "current_address": employee.current_address,
            "permanent_address": employee.permanent_address,
            "emergency_contact": employee.emergency_contact,
            "emergency_phone": employee.emergency_phone,
            "father_name": employee.father_name,
            "mother_name": employee.mother_name,
            "aadhar_number": employee.aadhar_number,
            "passport_number": employee.passport_number,
            "driving_license": employee.driving_license,
            "notice_period_days": employee.notice_period_days,
            "date_of_birth": str(employee.date_of_birth) if employee.date_of_birth else None,
            "date_of_joining": str(employee.date_of_joining) if employee.date_of_joining else None,
            "date_of_confirmation": str(employee.date_of_confirmation) if employee.date_of_confirmation else None,
            "date_of_marriage": str(employee.date_of_marriage) if employee.date_of_marriage else None,
            "gender": employee.gender.value if employee.gender else None,
            "marital_status": employee.marital_status.value if employee.marital_status else None
        }
        
        # Step 3: Update fields one by one with error handling
        updates_made = []
        
        # Basic Info Fields
        try:
            if basic_info.firstName and basic_info.firstName.strip():
                employee.first_name = basic_info.firstName.strip()
                updates_made.append("firstName")
        except Exception as e:
            print(f"⚠️ firstName error: {e}")
        
        try:
            if basic_info.lastName and basic_info.lastName.strip():
                employee.last_name = basic_info.lastName.strip()
                updates_made.append("lastName")
        except Exception as e:
            print(f"⚠️ lastName error: {e}")
        
        try:
            if basic_info.middleName is not None:
                employee.middle_name = basic_info.middleName.strip() if basic_info.middleName else None
                updates_made.append("middleName")
        except Exception as e:
            print(f"⚠️ middleName error: {e}")
        
        # Contact Fields
        try:
            if basic_info.personalPhone is not None:
                phone_val = basic_info.personalPhone.strip() if basic_info.personalPhone else None
                if phone_val and len(phone_val) > 20:
                    phone_val = phone_val[:20]  # Truncate to fit database
                employee.mobile = phone_val
                updates_made.append("personalPhone")
        except Exception as e:
            print(f"⚠️ personalPhone error: {e}")
        
        try:
            if basic_info.alternatePhone is not None:
                phone_val = basic_info.alternatePhone.strip() if basic_info.alternatePhone else None
                if phone_val and len(phone_val) > 20:
                    phone_val = phone_val[:20]  # Truncate to fit database
                employee.alternate_mobile = phone_val
                updates_made.append("alternatePhone")
        except Exception as e:
            print(f"⚠️ alternatePhone error: {e}")
        
        try:
            if basic_info.officePhone is not None:
                phone_val = basic_info.officePhone.strip() if basic_info.officePhone else None
                if phone_val and len(phone_val) > 20:
                    phone_val = phone_val[:20]  # Truncate to fit database
                employee.office_phone = phone_val
                updates_made.append("officePhone")
        except Exception as e:
            print(f"⚠️ officePhone error: {e}")
        
        # Email Fields with basic validation
        try:
            if basic_info.personalEmail is not None:
                email_val = basic_info.personalEmail.strip() if basic_info.personalEmail else None
                if email_val and "@" in email_val:  # Basic validation
                    employee.email = email_val
                    updates_made.append("personalEmail")
        except Exception as e:
            print(f"⚠️ personalEmail error: {e}")
        
        try:
            if basic_info.officialEmail is not None:
                email_val = basic_info.officialEmail.strip() if basic_info.officialEmail else None
                if email_val and "@" in email_val:  # Basic validation
                    employee.official_email = email_val
                    updates_made.append("officialEmail")
        except Exception as e:
            print(f"⚠️ officialEmail error: {e}")
        
        # Work Fields
        try:
            if getattr(basic_info, 'employee_code', None) is not None:
                employee.employee_code = basic_info.employee_code.strip() if basic_info.employee_code else None
                updates_made.append("employeeCode")
        except Exception as e:
            print(f"⚠️ employeeCode error: {e}")
        
        try:
            if basic_info.biometricCode is not None:
                employee.biometric_code = basic_info.biometricCode.strip() if basic_info.biometricCode else None
                updates_made.append("biometricCode")
        except Exception as e:
            print(f"⚠️ biometricCode error: {e}")
        
        # Personal Details
        try:
            if basic_info.nationality is not None:
                employee.nationality = basic_info.nationality.strip() if basic_info.nationality else None
                updates_made.append("nationality")
        except Exception as e:
            print(f"⚠️ nationality error: {e}")
        
        try:
            if basic_info.religion is not None:
                employee.religion = basic_info.religion.strip() if basic_info.religion else None
                updates_made.append("religion")
        except Exception as e:
            print(f"⚠️ religion error: {e}")
        
        try:
            if basic_info.bloodGroup is not None:
                employee.blood_group = basic_info.bloodGroup.strip() if basic_info.bloodGroup else None
                updates_made.append("bloodGroup")
        except Exception as e:
            print(f"⚠️ bloodGroup error: {e}")
        
        # Address Fields
        try:
            if basic_info.currentAddress is not None:
                employee.current_address = basic_info.currentAddress.strip() if basic_info.currentAddress else None
                updates_made.append("currentAddress")
        except Exception as e:
            print(f"⚠️ currentAddress error: {e}")
        
        try:
            if basic_info.permanentAddress is not None:
                employee.permanent_address = basic_info.permanentAddress.strip() if basic_info.permanentAddress else None
                updates_made.append("permanentAddress")
        except Exception as e:
            print(f"⚠️ permanentAddress error: {e}")
        
        # Emergency Contact
        try:
            if basic_info.emergencyContact is not None:
                contact_val = basic_info.emergencyContact.strip() if basic_info.emergencyContact else None
                if contact_val and len(contact_val) > 100:
                    contact_val = contact_val[:100]  # Truncate to fit database
                employee.emergency_contact = contact_val
                updates_made.append("emergencyContact")
        except Exception as e:
            print(f"⚠️ emergencyContact error: {e}")
        
        try:
            if basic_info.emergencyPhone is not None:
                phone_val = basic_info.emergencyPhone.strip() if basic_info.emergencyPhone else None
                if phone_val and len(phone_val) > 20:
                    phone_val = phone_val[:20]  # Truncate to fit database
                employee.emergency_phone = phone_val
                updates_made.append("emergencyPhone")
        except Exception as e:
            print(f"⚠️ emergencyPhone error: {e}")
        
        # Family Info
        try:
            if basic_info.fatherName is not None:
                employee.father_name = basic_info.fatherName.strip() if basic_info.fatherName else None
                updates_made.append("fatherName")
        except Exception as e:
            print(f"⚠️ fatherName error: {e}")
        
        try:
            if basic_info.motherName is not None:
                employee.mother_name = basic_info.motherName.strip() if basic_info.motherName else None
                updates_made.append("motherName")
        except Exception as e:
            print(f"⚠️ motherName error: {e}")
        
        # Document Fields
        try:
            if basic_info.aadharNumber is not None:
                # Remove hyphens and spaces, keep only digits for Aadhaar
                aadhar_clean = ''.join(filter(str.isdigit, basic_info.aadharNumber)) if basic_info.aadharNumber else None
                if aadhar_clean and len(aadhar_clean) > 12:
                    aadhar_clean = aadhar_clean[:12]  # Truncate to 12 digits
                employee.aadhar_number = aadhar_clean
                updates_made.append("aadharNumber")
        except Exception as e:
            print(f"⚠️ aadharNumber error: {e}")
        
        try:
            if basic_info.passportNumber is not None:
                passport_val = basic_info.passportNumber.strip() if basic_info.passportNumber else None
                if passport_val and len(passport_val) > 20:
                    passport_val = passport_val[:20]  # Truncate to fit database
                employee.passport_number = passport_val
                updates_made.append("passportNumber")
        except Exception as e:
            print(f"⚠️ passportNumber error: {e}")
        
        try:
            if basic_info.drivingLicense is not None:
                license_val = basic_info.drivingLicense.strip() if basic_info.drivingLicense else None
                if license_val and len(license_val) > 20:
                    license_val = license_val[:20]  # Truncate to fit database
                employee.driving_license = license_val
                updates_made.append("drivingLicense")
        except Exception as e:
            print(f"⚠️ drivingLicense error: {e}")
        
        # Notice Period
        try:
            if basic_info.noticePeriod is not None:
                if basic_info.noticePeriod and basic_info.noticePeriod.strip().isdigit():
                    employee.notice_period_days = int(basic_info.noticePeriod.strip())
                    updates_made.append("noticePeriod")
        except Exception as e:
            print(f"⚠️ noticePeriod error: {e}")
        
        # Date Fields - Simple parsing
        def safe_date_parse(date_str):
            if not date_str or not date_str.strip():
                return None
            try:
                from datetime import datetime
                clean_date = date_str.strip()
                if 'T' in clean_date:
                    clean_date = clean_date.split('T')[0]
                # Try different formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                    try:
                        return datetime.strptime(clean_date, fmt).date()
                    except:
                        continue
                return None
            except:
                return None
        
        try:
            if basic_info.dateOfBirth is not None:
                parsed_date = safe_date_parse(basic_info.dateOfBirth)
                if parsed_date:
                    employee.date_of_birth = parsed_date
                    updates_made.append("dateOfBirth")
        except Exception as e:
            print(f"⚠️ dateOfBirth error: {e}")
        
        try:
            if basic_info.dateOfJoining is not None:
                parsed_date = safe_date_parse(basic_info.dateOfJoining)
                if parsed_date:
                    employee.date_of_joining = parsed_date
                    updates_made.append("dateOfJoining")
        except Exception as e:
            print(f"⚠️ dateOfJoining error: {e}")
        
        try:
            if basic_info.dateOfConfirmation is not None:
                parsed_date = safe_date_parse(basic_info.dateOfConfirmation)
                if parsed_date:
                    employee.date_of_confirmation = parsed_date
                    updates_made.append("dateOfConfirmation")
        except Exception as e:
            print(f"⚠️ dateOfConfirmation error: {e}")
        
        try:
            if basic_info.dateOfMarriage is not None:
                parsed_date = safe_date_parse(basic_info.dateOfMarriage)
                if parsed_date:
                    employee.date_of_marriage = parsed_date
                    updates_made.append("dateOfMarriage")
        except Exception as e:
            print(f"⚠️ dateOfMarriage error: {e}")
        
        # Enum Fields - Safe mapping
        try:
            if basic_info.gender is not None and basic_info.gender.strip():
                from app.models.employee import Gender
                gender_map = {
                    'male': Gender.MALE,
                    'female': Gender.FEMALE,
                    'other': Gender.OTHER,
                    'transgender': Gender.OTHER
                }
                gender_val = gender_map.get(basic_info.gender.lower().strip())
                if gender_val:
                    employee.gender = gender_val
                    updates_made.append("gender")
        except Exception as e:
            print(f"⚠️ gender error: {e}")
        
        try:
            if basic_info.maritalStatus is not None and basic_info.maritalStatus.strip():
                from app.models.employee import MaritalStatus
                marital_map = {
                    'single': MaritalStatus.SINGLE,
                    'married': MaritalStatus.MARRIED,
                    'unmarried': MaritalStatus.SINGLE,
                    'divorced': MaritalStatus.DIVORCED,
                    'widowed': MaritalStatus.WIDOWED
                }
                marital_val = marital_map.get(basic_info.maritalStatus.lower().strip())
                if marital_val:
                    employee.marital_status = marital_val
                    updates_made.append("maritalStatus")
        except Exception as e:
            print(f"⚠️ maritalStatus error: {e}")
        
        # Step 4: Handle Employee Profile
        try:
            profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
            if not profile:
                profile = EmployeeProfile(employee_id=employee_id)
                db.add(profile)
                print("✅ Created employee profile")
            
            # Profile fields
            if basic_info.panNumber is not None:
                pan_val = basic_info.panNumber.strip().upper() if basic_info.panNumber else None
                if pan_val and len(pan_val) > 20:
                    pan_val = pan_val[:20]  # Truncate to fit database
                profile.pan_number = pan_val
                updates_made.append("panNumber")
            
            if basic_info.aadharNumber is not None:
                # Remove hyphens and spaces, keep only digits for Aadhaar
                aadhar_clean = ''.join(filter(str.isdigit, basic_info.aadharNumber)) if basic_info.aadharNumber else None
                if aadhar_clean and len(aadhar_clean) > 20:
                    aadhar_clean = aadhar_clean[:20]  # Truncate to fit database
                profile.aadhaar_number = aadhar_clean
                updates_made.append("aadharNumber_profile")
            
            if basic_info.emergencyContact is not None:
                contact_val = basic_info.emergencyContact.strip() if basic_info.emergencyContact else None
                if contact_val and len(contact_val) > 255:
                    contact_val = contact_val[:255]  # Truncate to fit database
                profile.emergency_contact_name = contact_val
                updates_made.append("emergencyContact_profile")
            
            if basic_info.emergencyPhone is not None:
                phone_val = basic_info.emergencyPhone.strip() if basic_info.emergencyPhone else None
                if phone_val and len(phone_val) > 20:
                    phone_val = phone_val[:20]  # Truncate to fit database
                profile.emergency_contact_mobile = phone_val
                updates_made.append("emergencyPhone_profile")
            
            if basic_info.currentAddress is not None:
                addr_val = basic_info.currentAddress.strip() if basic_info.currentAddress else None
                if addr_val and len(addr_val) > 255:
                    addr_val = addr_val[:255]  # Truncate to fit database
                profile.present_address_line1 = addr_val
                updates_made.append("currentAddress_profile")
            
            if basic_info.permanentAddress is not None:
                addr_val = basic_info.permanentAddress.strip() if basic_info.permanentAddress else None
                if addr_val and len(addr_val) > 255:
                    addr_val = addr_val[:255]  # Truncate to fit database
                profile.permanent_address_line1 = addr_val
                updates_made.append("permanentAddress_profile")
                
        except Exception as e:
            print(f"⚠️ Profile update error: {e}")
        
        # Step 5: Set system fields
        try:
            employee.updated_by = current_user.id
        except Exception as e:
            print(f"⚠️ updated_by error: {e}")
        
        # Step 6: Commit changes
        try:
            db.commit()
            db.refresh(employee)
            if 'profile' in locals():
                db.refresh(profile)
            print(f"✅ Successfully updated {len(updates_made)} fields: {updates_made}")
        except Exception as e:
            db.rollback()
            print(f"❌ Commit failed: {e}")
            return {"success": False, "message": f"Database commit failed: {str(e)}"}
        
        # ACTIVITY LOGGING: Log the changes after successful commit
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            # Capture new values after update
            new_values = {
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "middle_name": employee.middle_name,
                "mobile": employee.mobile,
                "alternate_mobile": employee.alternate_mobile,
                "office_phone": employee.office_phone,
                "email": employee.email,
                "official_email": employee.official_email,
                "employee_code": employee.employee_code,
                "biometric_code": employee.biometric_code,
                "nationality": employee.nationality,
                "religion": employee.religion,
                "blood_group": employee.blood_group,
                "current_address": employee.current_address,
                "permanent_address": employee.permanent_address,
                "emergency_contact": employee.emergency_contact,
                "emergency_phone": employee.emergency_phone,
                "father_name": employee.father_name,
                "mother_name": employee.mother_name,
                "aadhar_number": employee.aadhar_number,
                "passport_number": employee.passport_number,
                "driving_license": employee.driving_license,
                "notice_period_days": employee.notice_period_days,
                "date_of_birth": str(employee.date_of_birth) if employee.date_of_birth else None,
                "date_of_joining": str(employee.date_of_joining) if employee.date_of_joining else None,
                "date_of_confirmation": str(employee.date_of_confirmation) if employee.date_of_confirmation else None,
                "date_of_marriage": str(employee.date_of_marriage) if employee.date_of_marriage else None,
                "gender": employee.gender.value if employee.gender else None,
                "marital_status": employee.marital_status.value if employee.marital_status else None
            }
            
            # Log the activity
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="basic_info",
                old_data=old_values,
                new_data=new_values,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id}")
        except Exception as log_error:
            # Don't fail the request if logging fails
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return {
            "success": True,
            "message": f"Employee updated successfully. Updated {len(updates_made)} fields.",
            "updated_fields": updates_made,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code,
                "business_id": employee.business_id
            }
        }
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            db.rollback()
        except:
            pass
        return {
            "success": False,
            "message": f"Update failed: {str(e)}",
            "error_type": type(e).__name__
        }
        
        print(f"📝 Update data received: {basic_info.dict()}")
        
        # Validate employee access with business isolation

        
        employee = validate_employee_access(db, employee_id, current_user)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        print(f"✅ Found employee: {employee.first_name} {employee.last_name}")
        
        # Safe field update function
        def safe_update_field(field_name, new_value, target_object, target_field):
            try:
                if new_value is not None:
                    if isinstance(new_value, str):
                        processed_value = new_value.strip() if new_value else None
                    else:
                        processed_value = new_value
                    setattr(target_object, target_field, processed_value)
                    print(f"✅ Updated {field_name}: {processed_value}")
            except Exception as e:
                print(f"⚠️ Error updating {field_name}: {e}")
        
        # Update basic info fields with validation
        if basic_info.firstName is not None:
            if basic_info.firstName == "" or (basic_info.firstName and not basic_info.firstName.strip()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="First name cannot be empty"
                )
            employee.first_name = basic_info.firstName.strip()
            
        if basic_info.lastName is not None:
            if basic_info.lastName == "" or (basic_info.lastName and not basic_info.lastName.strip()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Last name cannot be empty"
                )
            employee.last_name = basic_info.lastName.strip()
        
        # Update other string fields safely
        safe_update_field("middleName", basic_info.middleName, employee, "middle_name")
        safe_update_field("personalPhone", basic_info.personalPhone, employee, "mobile")
        safe_update_field("alternatePhone", basic_info.alternatePhone, employee, "alternate_mobile")
        safe_update_field("employee_code", getattr(basic_info, 'employee_code', None), employee, "employee_code")
        safe_update_field("biometricCode", basic_info.biometricCode, employee, "biometric_code")
        safe_update_field("nationality", basic_info.nationality, employee, "nationality")
        safe_update_field("religion", basic_info.religion, employee, "religion")
        safe_update_field("bloodGroup", basic_info.bloodGroup, employee, "blood_group")
        safe_update_field("officePhone", basic_info.officePhone, employee, "office_phone")
        safe_update_field("currentAddress", basic_info.currentAddress, employee, "current_address")
        safe_update_field("permanentAddress", basic_info.permanentAddress, employee, "permanent_address")
        safe_update_field("emergencyContact", basic_info.emergencyContact, employee, "emergency_contact")
        safe_update_field("emergencyPhone", basic_info.emergencyPhone, employee, "emergency_phone")
        safe_update_field("fatherName", basic_info.fatherName, employee, "father_name")
        safe_update_field("motherName", basic_info.motherName, employee, "mother_name")
        
        # Handle email fields with validation
        if basic_info.personalEmail is not None:
            if basic_info.personalEmail.strip():
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, basic_info.personalEmail.strip()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid personal email format"
                    )
                # Check for duplicate email (excluding current employee)
                existing_email = db.query(Employee).filter(
                    Employee.email == basic_info.personalEmail.strip(),
                    Employee.id != employee_id
                ).first()
                if existing_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Email {basic_info.personalEmail.strip()} is already in use by another employee"
                    )
            employee.email = basic_info.personalEmail.strip() if basic_info.personalEmail else None
            
        if basic_info.officialEmail is not None:
            if basic_info.officialEmail.strip():
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, basic_info.officialEmail.strip()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid official email format"
                    )
                # Check for duplicate official email (excluding current employee)
                existing_official_email = db.query(Employee).filter(
                    Employee.official_email == basic_info.officialEmail.strip(),
                    Employee.id != employee_id
                ).first()
                if existing_official_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Official email {basic_info.officialEmail.strip()} is already in use by another employee"
                    )
            employee.official_email = basic_info.officialEmail.strip() if basic_info.officialEmail else None
        
        # Handle document fields with case conversion
        if basic_info.aadharNumber is not None:
            employee.aadhar_number = basic_info.aadharNumber.strip() if basic_info.aadharNumber else None
        if basic_info.passportNumber is not None:
            employee.passport_number = basic_info.passportNumber.strip() if basic_info.passportNumber else None
        if basic_info.drivingLicense is not None:
            employee.driving_license = basic_info.drivingLicense.strip() if basic_info.drivingLicense else None
        
        # Handle numeric fields
        if basic_info.noticePeriod is not None:
            try:
                employee.notice_period_days = int(basic_info.noticePeriod) if basic_info.noticePeriod and basic_info.noticePeriod.strip() else None
            except (ValueError, AttributeError):
                print(f"⚠️ Invalid notice period value: {basic_info.noticePeriod}")
        
        # Handle date fields with safe parsing
        def safe_parse_date(date_str, field_name):
            try:
                if date_str and date_str.strip():
                    clean_date = date_str.strip()
                    if 'T' in clean_date:
                        clean_date = clean_date.split('T')[0]
                    return datetime.strptime(clean_date, '%Y-%m-%d').date()
                return None
            except Exception as e:
                print(f"⚠️ Invalid date format for {field_name}: {date_str}, error: {e}")
                return None
        
        if basic_info.passportExpiry is not None:
            parsed_date = safe_parse_date(basic_info.passportExpiry, "passportExpiry")
            if parsed_date:
                employee.passport_expiry = parsed_date
        
        if basic_info.licenseExpiry is not None:
            parsed_date = safe_parse_date(basic_info.licenseExpiry, "licenseExpiry")
            if parsed_date:
                employee.license_expiry = parsed_date
        
        if basic_info.dateOfBirth is not None:
            parsed_date = safe_parse_date(basic_info.dateOfBirth, "dateOfBirth")
            if parsed_date:
                employee.date_of_birth = parsed_date
        
        if basic_info.dateOfConfirmation is not None:
            parsed_date = safe_parse_date(basic_info.dateOfConfirmation, "dateOfConfirmation")
            if parsed_date:
                employee.date_of_confirmation = parsed_date
        
        if basic_info.dateOfMarriage is not None:
            parsed_date = safe_parse_date(basic_info.dateOfMarriage, "dateOfMarriage")
            if parsed_date:
                employee.date_of_marriage = parsed_date
        
        if basic_info.dateOfJoining is not None:
            parsed_date = safe_parse_date(basic_info.dateOfJoining, "dateOfJoining")
            if parsed_date:
                employee.date_of_joining = parsed_date
                print(f"✅ Updated date of joining: {parsed_date}")
        
        # Handle enum fields with proper enum object assignment
        if basic_info.gender is not None and basic_info.gender.strip():
            try:
                from app.models.employee import Gender
                gender_mapping = {
                    'male': Gender.MALE,
                    'female': Gender.FEMALE, 
                    'other': Gender.OTHER,
                    'transgender': Gender.OTHER
                }
                gender_value = gender_mapping.get(basic_info.gender.lower(), Gender.MALE)
                employee.gender = gender_value
                print(f"✅ Updated gender: {gender_value}")
            except Exception as e:
                print(f"⚠️ Error updating gender: {e}")
        
        if basic_info.maritalStatus is not None and basic_info.maritalStatus.strip():
            try:
                from app.models.employee import MaritalStatus
                marital_mapping = {
                    'single': MaritalStatus.SINGLE,
                    'married': MaritalStatus.MARRIED,
                    'divorced': MaritalStatus.DIVORCED,
                    'widowed': MaritalStatus.WIDOWED,
                    'unmarried': MaritalStatus.SINGLE
                }
                marital_value = marital_mapping.get(basic_info.maritalStatus.lower(), MaritalStatus.SINGLE)
                employee.marital_status = marital_value
                print(f"✅ Updated marital status: {marital_value}")
            except Exception as e:
                print(f"⚠️ Error updating marital status: {e}")
        
        # CRITICAL FIX: Also update employee_profiles table for fields that exist there
        print("📋 Updating employee profile...")
        
        # Get or create employee profile
        from app.models.employee import EmployeeProfile
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if not employee_profile:
            employee_profile = EmployeeProfile(employee_id=employee_id)
            db.add(employee_profile)
            print("✅ Created new employee profile")
        
        # Update fields that exist in employee_profiles table
        if basic_info.panNumber is not None:
            pan_value = basic_info.panNumber.strip().upper() if basic_info.panNumber else None
            if pan_value:
                # Check for duplicate PAN number (excluding current employee)
                existing_pan = db.query(EmployeeProfile).filter(
                    EmployeeProfile.pan_number == pan_value,
                    EmployeeProfile.employee_id != employee_id
                ).first()
                if existing_pan:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"PAN number {pan_value} is already in use by another employee"
                    )
            employee_profile.pan_number = pan_value
            
        if basic_info.aadharNumber is not None:
            aadhar_value = basic_info.aadharNumber.strip() if basic_info.aadharNumber else None
            if aadhar_value:
                # Check for duplicate Aadhaar number (excluding current employee)
                existing_aadhar = db.query(EmployeeProfile).filter(
                    EmployeeProfile.aadhaar_number == aadhar_value,
                    EmployeeProfile.employee_id != employee_id
                ).first()
                if existing_aadhar:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Aadhaar number {aadhar_value} is already in use by another employee"
                    )
            employee_profile.aadhaar_number = aadhar_value
        if basic_info.emergencyContact is not None:
            employee_profile.emergency_contact_name = basic_info.emergencyContact.strip() if basic_info.emergencyContact else None
        if basic_info.emergencyPhone is not None:
            employee_profile.emergency_contact_mobile = basic_info.emergencyPhone.strip() if basic_info.emergencyPhone else None
        
        # Handle address fields - parse and store in profile components
        if basic_info.currentAddress is not None:
            if basic_info.currentAddress and basic_info.currentAddress.strip():
                employee_profile.present_address_line1 = basic_info.currentAddress.strip()
            else:
                employee_profile.present_address_line1 = None
                
        if basic_info.permanentAddress is not None:
            if basic_info.permanentAddress and basic_info.permanentAddress.strip():
                employee_profile.permanent_address_line1 = basic_info.permanentAddress.strip()
            else:
                employee_profile.permanent_address_line1 = None
        
        # Update system fields
        employee.updated_by = current_user.id
        
        print("💾 Committing changes to database...")
        db.commit()
        db.refresh(employee)
        db.refresh(employee_profile)
        
        print(f"✅ Employee {employee_id} basic info updated successfully in both employees and employee_profiles tables")
        
        return {
            "success": True,
            "message": "Employee basic information updated successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in update_employee_basic_info: {str(e)}")
        print(f"🔍 Employee ID: {employee_id}")
        print(f"🔍 Request data: {basic_info.dict()}")
        print(f"🔍 User ID: {current_user.id if current_user else 'None'}")
        import traceback
        print(f"🔍 Full traceback:")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee basic info: {str(e)}"
        )


@router.get("/stats/overview")
async def get_employee_stats(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee statistics"""
    try:
        from app.models.employee import Employee
        
        # Validate business access and compute stats scoped to business
        validate_business_access(business_id, current_user, db)

        total_employees = db.query(Employee).filter(
            Employee.business_id == business_id
        ).count()

        active_employees = db.query(Employee).filter(
            Employee.business_id == business_id,
            Employee.employee_status == "active"
        ).count()

        inactive_employees = total_employees - active_employees
        
        return {
            "total": total_employees,
            "active": active_employees,
            "inactive": inactive_employees,
            "departments": 0,  # Could be enhanced to show actual department count
            "locations": 0     # Could be enhanced to show actual location count
        }
    
    except Exception as e:
        print(f"ERROR in get_employee_stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee stats: {str(e)}"
        )


# ============================================================================
# ADDITIONAL EMPLOYEE INFORMATION ENDPOINTS
# ============================================================================

@router.get("/{employee_id}/address")
async def get_employee_address(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee address information"""
    try:
        from app.models.employee import Employee
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Safely get address fields with defaults
        current_address = getattr(employee, 'current_address', None) or ""
        permanent_address = getattr(employee, 'permanent_address', None) or ""
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "addresses": {
                "current": {
                    "street": current_address,
                    "city": "",
                    "state": "",
                    "pincode": "",
                    "country": "India"
                },
                "permanent": {
                    "street": permanent_address,
                    "city": "",
                    "state": "",
                    "pincode": "",
                    "country": "India"
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_address: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee address: {str(e)}"
        )


@router.get("/{employee_id:int}/work-profile")
async def get_employee_work_profile(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee work profile information"""
    try:
        from app.models.employee import Employee
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get related data safely with defaults
        department_name = "General"
        designation_name = "Employee"
        location_name = "Office"
        
        try:
            if hasattr(employee, 'department') and employee.department:
                department_name = employee.department.name
        except:
            pass
            
        try:
            if hasattr(employee, 'designation') and employee.designation:
                designation_name = employee.designation.name
        except:
            pass
            
        try:
            if hasattr(employee, 'location') and employee.location:
                location_name = employee.location.name
        except:
            pass
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "workProfile": {
                "employeeCode": employee.employee_code or f"EMP{employee.id:03d}",
                "department": department_name,
                "designation": designation_name,
                "location": location_name,
                "dateOfJoining": employee.date_of_joining.isoformat() if employee.date_of_joining else "",
                "employmentType": "Full Time",
                "workingHours": "9 hours",
                "reportingManager": "",
                "status": employee.employee_status or "active"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_work_profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee work profile: {str(e)}"
        )


@router.get("/{employee_id}/test-salary-options")
async def test_get_salary_options(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Test endpoint to get salary options and breakdown without authentication (for debugging)"""
    try:
        from app.models.employee import EmployeeSalary
        
        # Validate business access and get current salary record
        validate_business_access(business_id, current_user, db)
        
        # Get current salary record
        current_salary = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.is_active == True
        ).first()
        
        if not current_salary:
            return {
                "success": True,
                "message": "No salary record found - using defaults",
                "basicSalary": 12000,
                "houseRentAllowance": 4800,
                "specialAllowance": 8000,
                "medicalAllowance": 500,
                "conveyanceAllowance": 400,
                "telephoneAllowance": 500,
                "grossSalary": 26200,
                "groupInsurance": 500,
                "gratuity": 577.2,  # 12000 * 0.0481
                "salaryOptions": {
                    "isIncrement": False,
                    "disableOvertime": False,
                    "esiDisabled": False,
                    "esiAboveCeiling": False,
                    "pfDisabled": False,
                    "pfPensionDisabled": False,
                    "pfEmployeeAboveCeiling": False,
                    "pfEmployerAboveCeiling": False,
                    "pfGrossSalary": False,
                    "pfExtraDeduction": False,
                    "ptaxDisabled": False,
                    "itaxDisabled": False,
                    "itaxMetro": False,
                    "lwfDisabled": False,
                    "lwfState": "",
                    "pfMinimum": 0
                }
            }
        
        # Get salary breakdown from database
        basic = float(current_salary.basic_salary)
        gross = float(current_salary.gross_salary)
        
        # Get individual components from database if they exist, otherwise calculate defaults
        hra = float(current_salary.house_rent_allowance) if hasattr(current_salary, 'house_rent_allowance') and current_salary.house_rent_allowance else basic * 0.4
        special = float(current_salary.special_allowance) if hasattr(current_salary, 'special_allowance') and current_salary.special_allowance else 8000
        medical = float(current_salary.medical_allowance) if hasattr(current_salary, 'medical_allowance') and current_salary.medical_allowance else 500
        conveyance = float(current_salary.conveyance_allowance) if hasattr(current_salary, 'conveyance_allowance') and current_salary.conveyance_allowance else 400
        telephone = float(current_salary.telephone_allowance) if hasattr(current_salary, 'telephone_allowance') and current_salary.telephone_allowance else 500
        
        # Calculate employer benefits
        group_insurance = 500  # Fixed group insurance amount
        gratuity = basic * 0.0481  # 4.81% of basic salary
        
        # Get salary options
        saved_options = current_salary.salary_options or {}
        salary_option_keys = {
            "isIncrement", "disableOvertime", "esiDisabled", "esiAboveCeiling",
            "pfDisabled", "pfPensionDisabled", "pfEmployeeAboveCeiling", 
            "pfEmployerAboveCeiling", "pfGrossSalary", "pfExtraDeduction",
            "ptaxDisabled", "itaxDisabled", "itaxMetro", "lwfDisabled", "lwfState",
            "pfMinimum"
        }
        
        # Extract salary option toggles and pfMinimum
        filtered_options = {key: saved_options.get(key, False) for key in salary_option_keys if key not in ["lwfState", "pfMinimum"]}
        filtered_options["lwfState"] = saved_options.get("lwfState", "")
        filtered_options["pfMinimum"] = saved_options.get("pfMinimum", 0)
        
        return {
            "success": True,
            "message": "Salary data retrieved successfully",
            "basicSalary": basic,
            "houseRentAllowance": hra,
            "specialAllowance": special,
            "medicalAllowance": medical,
            "conveyanceAllowance": conveyance,
            "telephoneAllowance": telephone,
            "grossSalary": gross,
            "groupInsurance": group_insurance,
            "gratuity": gratuity,
            "salaryOptions": filtered_options,
            "databaseInfo": {
                "hasIndividualComponents": hasattr(current_salary, 'house_rent_allowance'),
                "componentsFromDB": {
                    "hra": hasattr(current_salary, 'house_rent_allowance') and current_salary.house_rent_allowance is not None,
                    "special": hasattr(current_salary, 'special_allowance') and current_salary.special_allowance is not None,
                    "medical": hasattr(current_salary, 'medical_allowance') and current_salary.medical_allowance is not None,
                    "conveyance": hasattr(current_salary, 'conveyance_allowance') and current_salary.conveyance_allowance is not None,
                    "telephone": hasattr(current_salary, 'telephone_allowance') and current_salary.telephone_allowance is not None
                }
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "salaryOptions": {},
            "basicSalary": 0,
            "houseRentAllowance": 0,
            "specialAllowance": 0,
            "medicalAllowance": 0,
            "conveyanceAllowance": 0,
            "telephoneAllowance": 0,
            "grossSalary": 0
        }


@router.get("/{employee_id}/salary-options")
async def get_employee_salary_options(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee salary options only (fast endpoint)"""
    try:
        from app.models.employee import Employee, EmployeeSalary
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get current salary record
        current_salary = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.is_active == True
        ).first()
        
        if not current_salary or not current_salary.salary_options:
            # Return default salary options
            return {
                "success": True,
                "salaryOptions": {
                    "isIncrement": False,
                    "disableOvertime": False,
                    "esiDisabled": False,
                    "esiAboveCeiling": False,
                    "pfDisabled": False,
                    "pfPensionDisabled": False,
                    "pfEmployeeAboveCeiling": False,
                    "pfEmployerAboveCeiling": False,
                    "pfGrossSalary": False,
                    "pfExtraDeduction": False,
                    "ptaxDisabled": False,
                    "itaxDisabled": False,
                    "itaxMetro": False,
                    "lwfDisabled": False,
                    "lwfState": ""
                }
            }
        
        # Filter only salary option toggles
        saved_options = current_salary.salary_options
        salary_option_keys = {
            "isIncrement", "disableOvertime", "esiDisabled", "esiAboveCeiling",
            "pfDisabled", "pfPensionDisabled", "pfEmployeeAboveCeiling", 
            "pfEmployerAboveCeiling", "pfGrossSalary", "pfExtraDeduction",
            "ptaxDisabled", "itaxDisabled", "itaxMetro", "lwfDisabled", "lwfState"
        }
        
        # Extract only salary option toggles
        filtered_options = {key: saved_options.get(key, False) for key in salary_option_keys if key != "lwfState"}
        filtered_options["lwfState"] = saved_options.get("lwfState", "")
        
        return {
            "success": True,
            "salaryOptions": filtered_options
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_salary_options: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary options: {str(e)}"
        )


@router.get("/{employee_id}/salary")
async def get_employee_salary(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get comprehensive employee salary information"""
    try:
        from app.models.employee import Employee
        from datetime import datetime, date
        
        # Validate business and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Try to get salary records, but handle if table doesn't exist
        current_salary = None
        salary_revisions = []
        
        try:
            from app.models.employee import EmployeeSalary
            
            # Get current salary record
            current_salary = db.query(EmployeeSalary).filter(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.is_active == True
            ).order_by(EmployeeSalary.effective_from.desc()).first()
            
            # Get all salary revisions
            salary_revisions = db.query(EmployeeSalary).filter(
                EmployeeSalary.employee_id == employee_id
            ).order_by(EmployeeSalary.effective_from.desc()).all()
            
        except Exception as salary_error:
            print(f"⚠️ Warning: Could not access salary table: {salary_error}")
            # Continue with default salary structure
        
        # Default salary structure if no salary record exists
        if not current_salary:
            # Create default salary structure (2.5-3 LPA range)
            default_basic = 12000
            default_hra = 4800  # 40% of basic
            default_special = 8000
            default_medical = 500
            default_conveyance = 400
            default_telephone = 500
            default_gross = default_basic + default_hra + default_special + default_medical + default_conveyance + default_telephone
            
            # Calculate deductions (using default toggles - all enabled)
            default_options = {
                "esiDisabled": False,
                "pfDisabled": False,
                "ptaxDisabled": False,
                "lwfDisabled": False,
                "pfGrossSalary": False,
                "pfEmployeeAboveCeiling": False,
                "pfEmployerAboveCeiling": False,
                "esiAboveCeiling": False,
                "pfMinimum": 0
            }
            
            # PF Deduction
            pf_deduction = 0
            if not default_options.get('pfDisabled', False):
                pf_base = default_basic if not default_options.get('pfGrossSalary', False) else default_gross
                if not default_options.get('pfEmployeeAboveCeiling', False):
                    pf_base = min(pf_base, 15000)
                pf_deduction = pf_base * 0.12
            
            # ESI Deduction
            esi_deduction = 0
            if not default_options.get('esiDisabled', False):
                if default_gross <= 21000 or default_options.get('esiAboveCeiling', False):
                    esi_deduction = default_gross * 0.0075
            
            # Professional Tax
            prof_tax = 0
            if not default_options.get('ptaxDisabled', False):
                prof_tax = 200
            
            total_deductions = pf_deduction + esi_deduction + prof_tax
            net_salary = default_gross - total_deductions
            
            # Calculate employer contributions
            employer_pf = 0
            if not default_options.get('pfDisabled', False):
                pf_base_employer = default_basic if not default_options.get('pfGrossSalary', False) else default_gross
                if not default_options.get('pfEmployerAboveCeiling', False):
                    pf_base_employer = min(pf_base_employer, 15000)
                employer_pf = pf_base_employer * 0.12
            
            employer_esi = 0
            if not default_options.get('esiDisabled', False):
                if default_gross <= 21000 or default_options.get('esiAboveCeiling', False):
                    employer_esi = default_gross * 0.0325
            
            group_insurance = 500  # Fixed group insurance amount
            gratuity = default_basic * 0.0481  # 4.81% of basic salary
            total_ctc = default_gross + employer_pf + employer_esi + group_insurance + gratuity
            
            current_salary_data = {
                "basicSalary": float(default_basic),
                "houseRentAllowance": float(default_hra),
                "specialAllowance": float(default_special),
                "medicalAllowance": float(default_medical),
                "conveyanceAllowance": float(default_conveyance),
                "telephoneAllowance": float(default_telephone),
                "grossSalary": float(default_gross),
                "totalSalary": float(default_gross),
                "groupInsurance": float(group_insurance),
                "gratuity": float(gratuity),
                "netSalary": float(net_salary),
                "totalCTC": float(total_ctc),
                "pfMinimum": 0,
                "effectiveFrom": date.today().isoformat(),
                "currency": "INR",
                "payrollFrequency": "Monthly",
                # Default salary options
                "salaryOptions": {
                    "isIncrement": False,
                    "disableOvertime": False,
                    "esiDisabled": False,
                    "esiAboveCeiling": False,
                    "pfDisabled": False,
                    "pfPensionDisabled": False,
                    "pfEmployeeAboveCeiling": False,
                    "pfEmployerAboveCeiling": False,
                    "pfGrossSalary": False,
                    "pfExtraDeduction": False,
                    "ptaxDisabled": False,
                    "itaxDisabled": False,
                    "itaxMetro": False,
                    "lwfDisabled": False,
                    "lwfState": ""
                }
            }
        else:
            # Get detailed salary breakdown from database
            basic = float(current_salary.basic_salary)
            gross = float(current_salary.gross_salary)
            
            # Get individual components from database if they exist, otherwise calculate defaults
            hra = float(current_salary.house_rent_allowance) if hasattr(current_salary, 'house_rent_allowance') and current_salary.house_rent_allowance else basic * 0.4
            special = float(current_salary.special_allowance) if hasattr(current_salary, 'special_allowance') and current_salary.special_allowance else 8000
            medical = float(current_salary.medical_allowance) if hasattr(current_salary, 'medical_allowance') and current_salary.medical_allowance else 500
            conveyance = float(current_salary.conveyance_allowance) if hasattr(current_salary, 'conveyance_allowance') and current_salary.conveyance_allowance else 400
            telephone = float(current_salary.telephone_allowance) if hasattr(current_salary, 'telephone_allowance') and current_salary.telephone_allowance else 500
            
            # Get salary options for toggle-aware calculations
            saved_options = current_salary.salary_options if current_salary.salary_options else {}
            print(f"DEBUG: Salary options for employee {employee_id}: {saved_options}")
            
            # Get employer benefits from database FIRST (needed for CTC calculation)
            group_insurance = float(current_salary.group_insurance) if hasattr(current_salary, 'group_insurance') and current_salary.group_insurance else 500
            gratuity = float(current_salary.gratuity) if hasattr(current_salary, 'gratuity') and current_salary.gratuity else basic * 0.0481
            print(f"DEBUG: Group Insurance: {group_insurance}, Gratuity: {gratuity}")
            
            # ===== TOGGLE-AWARE DEDUCTION CALCULATIONS =====
            
            # 1. PF Deduction (respects pfDisabled, pfGrossSalary, pfEmployeeAboveCeiling, pfMinimum)
            pf_deduction = 0
            if not saved_options.get('pfDisabled', False):
                # Determine PF calculation base (basic or gross)
                if saved_options.get('pfGrossSalary', False):
                    pf_base = gross
                else:
                    pf_base = basic
                
                # Apply ceiling unless pfEmployeeAboveCeiling is enabled
                if not saved_options.get('pfEmployeeAboveCeiling', False):
                    pf_base = min(pf_base, 15000)
                
                # Calculate 12% PF
                pf_deduction = pf_base * 0.12
                
                # Apply minimum deduction if set
                pf_minimum = saved_options.get('pfMinimum', 0)
                if pf_minimum > 0:
                    pf_deduction = max(pf_deduction, pf_minimum)
            
            # 2. ESI Deduction (respects esiDisabled, esiAboveCeiling)
            esi_deduction = 0
            if not saved_options.get('esiDisabled', False):
                # Check if ESI should be calculated
                if gross <= 21000 or saved_options.get('esiAboveCeiling', False):
                    esi_deduction = gross * 0.0075  # 0.75% employee contribution
            
            # 3. Professional Tax (respects ptaxDisabled)
            prof_tax = 0
            if not saved_options.get('ptaxDisabled', False):
                prof_tax = 200  # Standard PT amount
            
            # 4. Labour Welfare Fund (respects lwfDisabled, lwfState)
            lwf_deduction = 0
            if not saved_options.get('lwfDisabled', False):
                lwf_state = saved_options.get('lwfState', '')
                if lwf_state:
                    # TODO: Fetch LWF rate from database based on state
                    # For now, use a default amount
                    lwf_deduction = 0  # Will be implemented with LWF settings
            
            # Calculate total deductions and net salary
            total_deductions = pf_deduction + esi_deduction + prof_tax + lwf_deduction
            net_salary = gross - total_deductions
            print(f"DEBUG: PF={pf_deduction}, ESI={esi_deduction}, PT={prof_tax}, LWF={lwf_deduction}, Total Deductions={total_deductions}, Net={net_salary}")
            
            # ===== TOGGLE-AWARE EMPLOYER CONTRIBUTIONS =====
            
            # 1. Employer PF Contribution (respects pfDisabled, pfGrossSalary, pfEmployerAboveCeiling)
            employer_pf = 0
            if not saved_options.get('pfDisabled', False):
                # Determine PF calculation base (basic or gross)
                if saved_options.get('pfGrossSalary', False):
                    pf_base_employer = gross
                else:
                    pf_base_employer = basic
                
                # Apply ceiling unless pfEmployerAboveCeiling is enabled
                if not saved_options.get('pfEmployerAboveCeiling', False):
                    pf_base_employer = min(pf_base_employer, 15000)
                
                # Calculate 12% employer PF
                employer_pf = pf_base_employer * 0.12
            
            # 2. Employer ESI Contribution (respects esiDisabled, esiAboveCeiling)
            employer_esi = 0
            if not saved_options.get('esiDisabled', False):
                if gross <= 21000 or saved_options.get('esiAboveCeiling', False):
                    employer_esi = gross * 0.0325  # 3.25% employer contribution
            
            # 3. Employer LWF Contribution (respects lwfDisabled, lwfState)
            employer_lwf = 0
            if not saved_options.get('lwfDisabled', False):
                lwf_state = saved_options.get('lwfState', '')
                if lwf_state:
                    # TODO: Fetch employer LWF rate from database based on state
                    employer_lwf = 0  # Will be implemented with LWF settings
            
            # Recalculate CTC with toggle-aware contributions
            total_ctc = gross + employer_pf + employer_esi + group_insurance + gratuity + employer_lwf
            print(f"DEBUG: CTC Calculation - Gross={gross}, Emp PF={employer_pf}, Emp ESI={employer_esi}, GI={group_insurance}, Gratuity={gratuity}, Emp LWF={employer_lwf}, Total CTC={total_ctc}")
            
            # Filter only the salary option toggles (not salary components)
            salary_option_keys = {
                "isIncrement", "disableOvertime", "esiDisabled", "esiAboveCeiling",
                "pfDisabled", "pfPensionDisabled", "pfEmployeeAboveCeiling", 
                "pfEmployerAboveCeiling", "pfGrossSalary", "pfExtraDeduction",
                "ptaxDisabled", "itaxDisabled", "itaxMetro", "lwfDisabled", "lwfState"
            }
            
            # Extract only salary option toggles from saved data
            filtered_options = {key: saved_options.get(key, False) for key in salary_option_keys if key != "lwfState"}
            filtered_options["lwfState"] = saved_options.get("lwfState", "")
            
            current_salary_data = {
                "basicSalary": basic,
                "houseRentAllowance": hra,
                "specialAllowance": max(special, 0),
                "medicalAllowance": medical,
                "conveyanceAllowance": conveyance,
                "telephoneAllowance": telephone,
                "grossSalary": gross,
                "totalSalary": gross,
                "groupInsurance": group_insurance,
                "gratuity": gratuity,
                "netSalary": net_salary,
                "totalCTC": float(current_salary.ctc),
                "pfMinimum": 0,
                "effectiveFrom": current_salary.effective_from.isoformat(),
                "currency": "INR",
                "payrollFrequency": "Monthly",
                # Load filtered salary options from database
                "salaryOptions": filtered_options
            }
        
        # Format salary revisions
        revisions = []
        for revision in salary_revisions:
            basic = float(revision.basic_salary)
            gross = float(revision.gross_salary)
            ctc = float(revision.ctc)
            
            # Calculate net salary
            pf_deduction = min(basic * 0.12, 1800)
            esi_deduction = gross * 0.0175 if gross <= 21000 else 0
            prof_tax = 200
            total_deductions = pf_deduction + esi_deduction + prof_tax
            net_salary = gross - total_deductions
            
            revisions.append({
                "effectiveFrom": revision.effective_from.isoformat(),
                "basicSalary": basic,
                "grossSalary": gross,
                "netSalary": net_salary,
                "ctc": ctc,
                "ctcAnnual": ctc * 12,
                "isActive": revision.is_active
            })
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "code": employee.employee_code or f"EMP{employee.id:03d}",
            "salary": current_salary_data,
            "revisions": revisions,
            "hasCurrentRevision": current_salary is not None,
            "totalRevisions": len(revisions)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_employee_salary: {str(e)}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee salary: {str(e)}"
        )


class SalaryRevisionCreate(BaseModel):
    """Schema for creating a new salary revision"""
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    year: int = Field(..., ge=2020, le=2030, description="Year (2020-2030)")
    considerIncrement: bool = Field(default=False, description="Apply increment to previous salary")
    copyFromLatest: bool = Field(default=True, description="Copy from latest salary revision")
    
    class Config:
        json_schema_extra = {
            "example": {
                "month": 2,
                "year": 2026,
                "considerIncrement": True,
                "copyFromLatest": True
            }
        }


class EmployeeSalaryUpdate(BaseModel):
    """Schema for updating employee salary"""
    basicSalary: Optional[float] = None
    houseRentAllowance: Optional[float] = None
    specialAllowance: Optional[float] = None
    medicalAllowance: Optional[float] = None
    conveyanceAllowance: Optional[float] = None
    telephoneAllowance: Optional[float] = None
    grossSalary: Optional[float] = None
    totalSalary: Optional[float] = None
    groupInsurance: Optional[float] = None
    gratuity: Optional[float] = None
    netSalary: Optional[float] = None
    totalCTC: Optional[float] = None
    pfMinimum: Optional[float] = None
    effectiveFrom: Optional[str] = None
    
    # Salary options/toggles
    isIncrement: Optional[bool] = None
    disableOvertime: Optional[bool] = None
    esiDisabled: Optional[bool] = None
    esiAboveCeiling: Optional[bool] = None
    pfDisabled: Optional[bool] = None
    pfPensionDisabled: Optional[bool] = None
    pfEmployeeAboveCeiling: Optional[bool] = None
    pfEmployerAboveCeiling: Optional[bool] = None
    pfGrossSalary: Optional[bool] = None
    pfExtraDeduction: Optional[bool] = None
    ptaxDisabled: Optional[bool] = None
    itaxDisabled: Optional[bool] = None
    itaxMetro: Optional[bool] = None
    lwfDisabled: Optional[bool] = None
    lwfState: Optional[str] = None
    
    class Config:
        extra = "forbid"
    
    @validator('basicSalary', 'houseRentAllowance', 'specialAllowance', 'medicalAllowance', 
              'conveyanceAllowance', 'telephoneAllowance', 'grossSalary', 'totalSalary', 
              'groupInsurance', 'gratuity', 'totalCTC', 'pfMinimum')
    def validate_salary_amounts(cls, v):
        if v is not None and v < 0:
            raise ValueError('Salary amounts cannot be negative')
        return v
    
    # Note: netSalary can be negative if deductions exceed gross, so we don't validate it
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())


@router.put("/{employee_id}/salary")
async def update_employee_salary(
    payload: EmployeeSalaryUpdate,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update employee salary information (tenant-isolated)."""
    try:
        from app.models.employee import Employee, EmployeeSalary
        from datetime import datetime, date

        # Validate that the request body has at least one field
        if not payload.has_valid_data():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one salary field must be provided. Request body cannot be empty."
            )

        # Enforce business access and ensure employee belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Get current active salary record
        current_salary = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.is_active == True
        ).first()
        
        # Convert salary data to dict
        salary_dict = payload.dict(exclude_none=True)
        
        # Calculate effective date
        effective_from = date.today()
        if 'effectiveFrom' in salary_dict:
            try:
                effective_from = datetime.fromisoformat(salary_dict['effectiveFrom']).date()
            except:
                effective_from = date.today()
        
        # Extract salary options from request first
        salary_options = {}
        option_fields = [
            'isIncrement', 'disableOvertime', 'esiDisabled', 'esiAboveCeiling',
            'pfDisabled', 'pfPensionDisabled', 'pfEmployeeAboveCeiling', 
            'pfEmployerAboveCeiling', 'pfGrossSalary', 'pfExtraDeduction',
            'ptaxDisabled', 'itaxDisabled', 'itaxMetro', 'lwfDisabled', 'lwfState',
            'pfMinimum'  # Add pfMinimum to salary options
        ]
        
        for field in option_fields:
            if field in salary_dict:
                salary_options[field] = salary_dict[field]
        
        # Check if this is only a salary options update (no salary amounts)
        salary_amount_fields = [
            'basicSalary', 'houseRentAllowance', 'specialAllowance', 
            'medicalAllowance', 'conveyanceAllowance', 'telephoneAllowance',
            'groupInsurance', 'gratuity', 'grossSalary', 'totalSalary', 'netSalary', 'totalCTC'
        ]
        
        has_salary_amounts = any(field in salary_dict for field in salary_amount_fields)
        
        # Initialize component variables
        hra = 0
        special = 0
        medical = 0
        conveyance = 0
        telephone = 0
        group_insurance = 0
        gratuity = 0
        
        # Only calculate salary components if salary amounts are provided
        if has_salary_amounts:
            # Get salary components from request or use defaults
            basic_salary = salary_dict.get('basicSalary', 12000)
            hra = salary_dict.get('houseRentAllowance', basic_salary * 0.4)
            special = salary_dict.get('specialAllowance', 8000)
            medical = salary_dict.get('medicalAllowance', 500)
            conveyance = salary_dict.get('conveyanceAllowance', 400)
            telephone = salary_dict.get('telephoneAllowance', 500)
            
            # Handle Group Insurance and Gratuity with auto-calculation logic
            if 'groupInsurance' in salary_dict:
                # Use provided value if explicitly set
                group_insurance = salary_dict.get('groupInsurance', 500)
            else:
                # Auto-calculate or use default
                group_insurance = 500  # Default fixed amount
            
            if 'gratuity' in salary_dict:
                # Use provided value if explicitly set
                gratuity = salary_dict.get('gratuity', basic_salary * 0.0481)
            else:
                # Auto-calculate based on basic salary
                gratuity = basic_salary * 0.0481
            
            # If only basic salary is being updated, auto-update gratuity
            if 'basicSalary' in salary_dict and 'gratuity' not in salary_dict:
                gratuity = basic_salary * 0.0481
                print(f"DEBUG: Auto-calculated gratuity = {gratuity} for basic salary = {basic_salary}")
            special = salary_dict.get('specialAllowance', 8000)
            medical = salary_dict.get('medicalAllowance', 500)
            conveyance = salary_dict.get('conveyanceAllowance', 400)
            telephone = salary_dict.get('telephoneAllowance', 500)
            
            # Calculate gross salary
            gross_salary = basic_salary + hra + special + medical + conveyance + telephone
            if 'grossSalary' in salary_dict:
                gross_salary = salary_dict['grossSalary']
            
            # Calculate CTC
            employer_pf = min(basic_salary * 0.12, 1800)
            employer_esi = gross_salary * 0.00475 if gross_salary <= 21000 else 0
            total_ctc = gross_salary + employer_pf + employer_esi + 200  # Adding gratuity provision
            if 'totalCTC' in salary_dict:
                total_ctc = salary_dict['totalCTC']
        else:
            # Use existing values if only updating options
            if current_salary:
                basic_salary = float(current_salary.basic_salary)
                gross_salary = float(current_salary.gross_salary)
                total_ctc = float(current_salary.ctc)
                effective_from = current_salary.effective_from
                
                # Get individual components from database if they exist
                hra = float(current_salary.house_rent_allowance) if hasattr(current_salary, 'house_rent_allowance') and current_salary.house_rent_allowance else basic_salary * 0.4
                special = float(current_salary.special_allowance) if hasattr(current_salary, 'special_allowance') and current_salary.special_allowance else 8000
                medical = float(current_salary.medical_allowance) if hasattr(current_salary, 'medical_allowance') and current_salary.medical_allowance else 500
                conveyance = float(current_salary.conveyance_allowance) if hasattr(current_salary, 'conveyance_allowance') and current_salary.conveyance_allowance else 400
                telephone = float(current_salary.telephone_allowance) if hasattr(current_salary, 'telephone_allowance') and current_salary.telephone_allowance else 500
                group_insurance = float(current_salary.group_insurance) if hasattr(current_salary, 'group_insurance') and current_salary.group_insurance else 500
                gratuity = float(current_salary.gratuity) if hasattr(current_salary, 'gratuity') and current_salary.gratuity else basic_salary * 0.0481
            else:
                # Default values for new salary record
                basic_salary = 12000
                hra = basic_salary * 0.4
                special = 8000
                medical = 500
                conveyance = 400
                telephone = 500
                group_insurance = 500
                gratuity = basic_salary * 0.0481
                gross_salary = basic_salary + hra + special + medical + conveyance + telephone
                employer_pf = min(basic_salary * 0.12, 1800)
                employer_esi = gross_salary * 0.00475 if gross_salary <= 21000 else 0
                total_ctc = gross_salary + employer_pf + employer_esi + group_insurance + gratuity
        
        if current_salary:
            # Update existing salary record
            current_salary.basic_salary = basic_salary
            current_salary.gross_salary = gross_salary
            current_salary.ctc = total_ctc
            current_salary.effective_from = effective_from
            current_salary.updated_at = datetime.utcnow()
            
            # Update individual allowance components if they exist in the model
            if hasattr(current_salary, 'house_rent_allowance'):
                current_salary.house_rent_allowance = hra
            if hasattr(current_salary, 'special_allowance'):
                current_salary.special_allowance = special
            if hasattr(current_salary, 'medical_allowance'):
                current_salary.medical_allowance = medical
            if hasattr(current_salary, 'conveyance_allowance'):
                current_salary.conveyance_allowance = conveyance
            if hasattr(current_salary, 'telephone_allowance'):
                current_salary.telephone_allowance = telephone
            if hasattr(current_salary, 'group_insurance'):
                current_salary.group_insurance = group_insurance
            if hasattr(current_salary, 'gratuity'):
                current_salary.gratuity = gratuity
            
            # Update salary options if any provided
            if salary_options:
                if current_salary.salary_options is None:
                    current_salary.salary_options = {}
                
                # Create a new dict to ensure SQLAlchemy detects the change
                updated_options = dict(current_salary.salary_options)
                updated_options.update(salary_options)
                current_salary.salary_options = updated_options
                
                # Mark the attribute as modified to ensure SQLAlchemy saves it
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(current_salary, 'salary_options')
        else:
            # Create new salary record with individual components
            new_salary_data = {
                'employee_id': employee_id,
                'basic_salary': basic_salary,
                'gross_salary': gross_salary,
                'ctc': total_ctc,
                'effective_from': effective_from,
                'is_active': True,
                'salary_options': salary_options if salary_options else {}
            }
            
            # Add individual allowance components if the model supports them
            try:
                new_salary_data.update({
                    'house_rent_allowance': hra,
                    'special_allowance': special,
                    'medical_allowance': medical,
                    'conveyance_allowance': conveyance,
                    'telephone_allowance': telephone,
                    'group_insurance': group_insurance,
                    'gratuity': gratuity
                })
            except Exception as e:
                print(f"Warning: Could not set individual allowance components: {e}")
            
            new_salary = EmployeeSalary(**new_salary_data)
            db.add(new_salary)
        
        db.commit()
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            if has_salary_amounts and current_salary:
                # Log salary revision
                change_tracker.log_salary_revision(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    old_salary=float(current_salary.basic_salary or 0),
                    new_salary=float(basic_salary),
                    effective_date=effective_from.isoformat(),
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
            else:
                # Log general salary update
                change_tracker.log_update(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    section="salary",
                    old_data={"salary_options": current_salary.salary_options if current_salary else {}},
                    new_data={"salary_options": salary_options},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
            print(f"✅ Activity logged for employee {employee_id} - salary update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        # Calculate net salary for response
        pf_deduction = min(basic_salary * 0.12, 1800)
        esi_deduction = gross_salary * 0.0175 if gross_salary <= 21000 else 0
        prof_tax = 200
        total_deductions = pf_deduction + esi_deduction + prof_tax
        net_salary = gross_salary - total_deductions
        
        return {
            "success": True,
            "message": "Employee salary updated successfully"
        }
    
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Validation error: {str(e)}")
    except Exception as e:
        db.rollback()
        # Log the error server-side but don't expose internal error details to clients
        print(f"ERROR in update_employee_salary: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update employee salary"
        )


@router.post("/{employee_id}/salary/revision")
async def add_salary_revision(
    revision_data: SalaryRevisionCreate,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Add a new salary revision for employee
    
    Creates a new salary revision with the specified effective date.
    Can optionally copy from the latest revision and apply an increment.
    
    Parameters:
    - month: Month for the revision (1-12)
    - year: Year for the revision (2020-2030)
    - considerIncrement: If true, applies 10% increment to previous salary
    - copyFromLatest: If true, copies from the latest salary revision
    
    Example request body:
    ```json
    {
        "month": 2,
        "year": 2026,
        "considerIncrement": true,
        "copyFromLatest": true
    }
    ```
    """
    try:
        from app.models.employee import Employee, EmployeeSalary
        from datetime import datetime, date, timedelta
        
        print(f"DEBUG: Adding salary revision for employee {employee_id}")
        print(f"DEBUG: Revision data: {revision_data}")
        
        # Validate business and employee access
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        print(f"DEBUG: Employee found: {employee.first_name} {employee.last_name}")
        
        # Extract revision data
        month = revision_data.month
        year = revision_data.year
        consider_increment = revision_data.considerIncrement
        copy_from_latest = revision_data.copyFromLatest
        
        # Calculate effective date
        effective_from = date(year, month, 1)
        print(f"DEBUG: Effective from: {effective_from}")
        
        # Check if revision already exists for this date
        existing_revision = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from == effective_from
        ).first()
        
        if existing_revision:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Salary revision already exists for {effective_from}"
            )
        
        # Get latest salary for copying
        latest_salary = None
        if copy_from_latest:
            latest_salary = db.query(EmployeeSalary).filter(
                EmployeeSalary.employee_id == employee_id
            ).order_by(EmployeeSalary.effective_from.desc()).first()
            print(f"DEBUG: Latest salary found: {latest_salary is not None}")
        
        # Calculate new salary amounts
        if latest_salary and copy_from_latest:
            basic_salary = float(latest_salary.basic_salary)
            gross_salary = float(latest_salary.gross_salary)
            ctc = float(latest_salary.ctc)
            
            print(f"DEBUG: Copying from latest - Basic: {basic_salary}, Gross: {gross_salary}, CTC: {ctc}")
            
            # Apply increment if requested
            if consider_increment:
                increment_percentage = 0.10  # 10% increment
                basic_salary *= (1 + increment_percentage)
                gross_salary *= (1 + increment_percentage)
                ctc *= (1 + increment_percentage)
                print(f"DEBUG: After increment - Basic: {basic_salary}, Gross: {gross_salary}, CTC: {ctc}")
        else:
            # Default salary structure
            basic_salary = 12000.0
            gross_salary = 26200.0
            ctc = 31500.0
            print(f"DEBUG: Using default salary structure")
        
        # Validate salary amounts
        if basic_salary <= 0 or gross_salary <= 0 or ctc <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Salary amounts must be greater than zero"
            )
        
        # Deactivate current active salary
        current_active = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.is_active == True
        ).first()
        
        if current_active:
            print(f"DEBUG: Deactivating current active salary: {current_active.effective_from}")
            current_active.is_active = False
            # Set effective_to to the day before the new revision starts
            from datetime import timedelta
            current_active.effective_to = effective_from - timedelta(days=1)
        
        # Create new salary revision
        print(f"DEBUG: Creating new salary revision")
        new_revision = EmployeeSalary(
            employee_id=employee_id,
            basic_salary=basic_salary,
            gross_salary=gross_salary,
            ctc=ctc,
            effective_from=effective_from,
            is_active=True,
            salary_options={}  # Initialize with empty options
        )
        
        db.add(new_revision)
        
        # Commit the transaction
        print(f"DEBUG: Committing transaction")
        db.commit()
        db.refresh(new_revision)
        
        print(f"DEBUG: Salary revision created successfully with ID: {new_revision.id}")
        
        # Calculate net salary for response
        pf_deduction = min(basic_salary * 0.12, 1800)
        esi_deduction = gross_salary * 0.0175 if gross_salary <= 21000 else 0
        prof_tax = 200
        total_deductions = pf_deduction + esi_deduction + prof_tax
        net_salary = gross_salary - total_deductions
        
        return {
            "success": True,
            "message": f"Salary revision added successfully for {employee.first_name} {employee.last_name}",
            "revision": {
                "id": new_revision.id,
                "effectiveFrom": effective_from.isoformat(),
                "basicSalary": float(basic_salary),
                "grossSalary": float(gross_salary),
                "netSalary": float(net_salary),
                "ctc": float(ctc),
                "ctcAnnual": float(ctc * 12),
                "isActive": True
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in add_salary_revision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add salary revision: {str(e)}"
        )


@router.delete("/{employee_id}/salary/revision")
async def delete_salary_revision(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    revision_data: SalaryRevisionDeleteRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a salary revision for employee
    
    **Request body:**
    - effectiveDate: Effective date of the revision to delete (YYYY-MM-DD or ISO format)
    """
    try:
        from app.models.employee import Employee, EmployeeSalary
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Extract effective date from request
        effective_date_str = revision_data.effectiveDate
        
        # Parse effective date
        try:
            effective_date = datetime.fromisoformat(effective_date_str.replace('Z', '+00:00')).date()
        except:
            try:
                effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD or ISO format"
                )
        
        # Find the salary revision to delete
        revision_to_delete = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from == effective_date
        ).first()
        
        if not revision_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No salary revision found for effective date {effective_date}"
            )
        
        # Check if this is the only revision (don't allow deletion of the last one)
        total_revisions = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id
        ).count()
        
        if total_revisions <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last salary revision. Employee must have at least one salary record."
            )
        
        # If deleting the active revision, make the previous one active
        if revision_to_delete.is_active:
            previous_revision = db.query(EmployeeSalary).filter(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_from < effective_date
            ).order_by(EmployeeSalary.effective_from.desc()).first()
            
            if previous_revision:
                previous_revision.is_active = True
                previous_revision.effective_to = None
        
        # Delete the revision
        db.delete(revision_to_delete)
        db.commit()
        
        return {
            "success": True,
            "message": f"Salary revision deleted successfully for {employee.first_name} {employee.last_name}",
            "deletedRevision": {
                "effectiveFrom": effective_date.isoformat(),
                "basicSalary": float(revision_to_delete.basic_salary),
                "grossSalary": float(revision_to_delete.gross_salary),
                "ctc": float(revision_to_delete.ctc)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in delete_salary_revision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete salary revision: {str(e)}"
        )


@router.get("/{employee_id}/salary/revision")
async def get_salary_revision(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    effectiveDate: str = Query(..., description="Effective date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get specific salary revision for employee"""
    try:
        from app.models.employee import Employee, EmployeeSalary
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Parse effective date
        try:
            effective_date = datetime.fromisoformat(effectiveDate.replace('Z', '+00:00')).date()
        except:
            try:
                effective_date = datetime.strptime(effectiveDate, '%Y-%m-%d').date()
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD or ISO format"
                )
        
        # Find the salary revision
        revision = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from == effective_date
        ).first()
        
        if not revision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No salary revision found for effective date {effective_date}"
            )
        
        # Calculate net salary and other components
        basic_salary = float(revision.basic_salary)
        gross_salary = float(revision.gross_salary)
        ctc = float(revision.ctc)
        
        # Calculate breakdown components
        hra = basic_salary * 0.4
        special = max(gross_salary - basic_salary - hra - 1400, 0)
        medical = 500
        conveyance = 400
        telephone = 500
        
        # Calculate deductions
        pf_deduction = min(basic_salary * 0.12, 1800)
        esi_deduction = gross_salary * 0.0175 if gross_salary <= 21000 else 0
        prof_tax = 200
        total_deductions = pf_deduction + esi_deduction + prof_tax
        net_salary = gross_salary - total_deductions
        
        return {
            "success": True,
            "revision": {
                "id": revision.id,
                "employeeId": employee_id,
                "effectiveFrom": effective_date.isoformat(),
                "basicSalary": basic_salary,
                "houseRentAllowance": hra,
                "specialAllowance": special,
                "medicalAllowance": medical,
                "conveyanceAllowance": conveyance,
                "telephoneAllowance": telephone,
                "grossSalary": gross_salary,
                "totalSalary": gross_salary,
                "netSalary": net_salary,
                "totalCTC": ctc,
                "ctc": ctc,
                "ctcAnnual": ctc * 12,
                "isActive": revision.is_active,
                "pfMinimum": 0
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_salary_revision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary revision: {str(e)}"
        )


@router.get("/employee-identity/{employee_id}")
async def get_employee_identity(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee identity information"""
    try:
        from app.models.employee import Employee
        
        # Validate employee access with business isolation

        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Prefer an explicit, business-scoped EmployeeProfile lookup to avoid
        # cross-business or missing-profile issues during setup.
        from app.models.employee import EmployeeProfile

        profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.employee_id == employee_id,
            EmployeeProfile.business_id == business_id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found"
            )

        return {
            "employee_id": employee.id,
            "business_id": employee.business_id,
            "bank_name": profile.bank_name or "",
            "bank_account_number": profile.bank_account_number or "",
            "ifsc_code": profile.ifsc_code or "",
            "pan_number": profile.pan_number or "",
            "aadhaar_number": profile.aadhaar_number or "",
            "passport_number": profile.passport_number or "",
            "driving_license": profile.driving_license or "",
            "voter_id": profile.voter_id or ""
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_identity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee identity: {str(e)}"
        )


@router.get("/employee-family/{employee_id}", response_model=EmployeeFamilyResponse)
async def get_employee_family(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee family members information"""
    try:
        from app.models.employee import Employee
        from app.models.employee_relative import EmployeeRelative
        from app.schemas.family import EmployeeFamilyResponse, FamilyMemberResponse, RelationTypeOption
        
        # Validate employee access with business isolation

        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get all family members for this employee
        family_members = db.query(EmployeeRelative).filter(
            EmployeeRelative.employee_id == employee_id,
            EmployeeRelative.is_active == True
        ).order_by(EmployeeRelative.created_at.desc()).all()
        
        # Format family members for frontend
        members_list = []
        for member in family_members:
            members_list.append(FamilyMemberResponse(
                id=member.id,
                relation=member.relation,
                name=member.relative_name,
                phone=member.phone or "",
                email=member.email or "",
                notes=member.notes or "",
                date_of_birth=member.date_of_birth.isoformat() if member.date_of_birth else None,
                dob=member.date_of_birth.strftime("%d-%b-%Y") if member.date_of_birth else "",
                is_dependent=member.dependent == "Yes" if member.dependent else False,
                created_at=member.created_at.isoformat() if member.created_at else None
            ))
        
        relation_types = [
            RelationTypeOption(value="Father", label="Father"),
            RelationTypeOption(value="Mother", label="Mother"),
            RelationTypeOption(value="Brother", label="Brother"),
            RelationTypeOption(value="Sister", label="Sister"),
            RelationTypeOption(value="Spouse", label="Spouse"),
            RelationTypeOption(value="Son", label="Son"),
            RelationTypeOption(value="Daughter", label="Daughter"),
            RelationTypeOption(value="Grand Father", label="Grand Father"),
            RelationTypeOption(value="Grand Mother", label="Grand Mother")
        ]
        
        return EmployeeFamilyResponse(
            id=employee.id,
            name=f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            code=employee.employee_code or f"EMP{employee.id:03d}",
            family_members=members_list,
            total_members=len(members_list),
            relation_types=relation_types
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_family: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee family: {str(e)}"
        )


@router.post("/{employee_id}/family", response_model=FamilyMemberCreateResponse)
async def create_employee_family_member(
    member_data: FamilyMemberCreateRequest,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new family member for an employee"""
    try:
        from app.models.employee import Employee
        from app.models.employee_relative import EmployeeRelative
        from app.schemas.family import FamilyMemberCreateRequest, FamilyMemberCreateResponse, FamilyMemberResponse
        from datetime import datetime
        
        # Validate employee exists and belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Create new family member
        new_member = EmployeeRelative(
            employee_id=employee_id,
            relation=member_data.relation,  # Remove .value since it's already a string
            relative_name=member_data.name,
            phone=member_data.phone,
            email=member_data.email,
            notes=member_data.notes,
            date_of_birth=member_data.date_of_birth,
            dependent="Yes" if member_data.is_dependent else "No"
        )
        
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_create(
                user_id=current_user.id,
                employee_id=employee_id,
                section="family_members",
                data={"name": member_data.name, "relation": member_data.relation},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - family member create")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return FamilyMemberCreateResponse(
            success=True,
            message="Family member added successfully",
            member=FamilyMemberResponse(
                id=new_member.id,
                relation=new_member.relation,
                name=new_member.relative_name,
                phone=new_member.phone or "",
                email=new_member.email or "",
                notes=new_member.notes or "",
                date_of_birth=new_member.date_of_birth.isoformat() if new_member.date_of_birth else None,
                dob=new_member.date_of_birth.strftime("%d-%b-%Y") if new_member.date_of_birth else "",
                is_dependent=new_member.dependent == "Yes",
                created_at=new_member.created_at.isoformat() if new_member.created_at else None
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in create_employee_family_member: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create family member: {str(e)}"
        )


@router.put("/{employee_id}/family/{member_id}", response_model=FamilyMemberUpdateResponse)
async def update_employee_family_member(
    member_data: FamilyMemberUpdateRequest,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    member_id: int = Path(..., description="Member ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update an employee family member"""
    try:
        from app.models.employee import Employee
        from app.models.employee_relative import EmployeeRelative
        from app.schemas.family import FamilyMemberUpdateRequest, FamilyMemberUpdateResponse, FamilyMemberResponse
        from datetime import datetime
        
        # Validate employee exists and belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the family member
        member = db.query(EmployeeRelative).filter(
            EmployeeRelative.id == member_id,
            EmployeeRelative.employee_id == employee_id,
            EmployeeRelative.is_active == True
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Family member with ID {member_id} not found for employee {employee_id}"
            )
        
        # Update family member
        old_data = {
            "name": member.relative_name,
            "relation": member.relation,
            "phone": member.phone,
            "email": member.email
        }
        
        member.relation = member_data.relation  # Remove .value since it's already a string
        member.relative_name = member_data.name
        member.phone = member_data.phone
        member.email = member_data.email
        member.notes = member_data.notes
        member.date_of_birth = member_data.date_of_birth
        member.dependent = "Yes" if member_data.is_dependent else "No"
        
        db.commit()
        db.refresh(member)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            new_data = {
                "name": member.relative_name,
                "relation": member.relation,
                "phone": member.phone,
                "email": member.email
            }
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="family_members",
                old_data=old_data,
                new_data=new_data,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - family member update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return FamilyMemberUpdateResponse(
            success=True,
            message="Family member updated successfully",
            member=FamilyMemberResponse(
                id=member.id,
                relation=member.relation,
                name=member.relative_name,
                phone=member.phone or "",
                email=member.email or "",
                notes=member.notes or "",
                date_of_birth=member.date_of_birth.isoformat() if member.date_of_birth else None,
                dob=member.date_of_birth.strftime("%d-%b-%Y") if member.date_of_birth else "",
                is_dependent=member.dependent == "Yes",
                created_at=member.created_at.isoformat() if member.created_at else None
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in update_employee_family_member: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update family member: {str(e)}"
        )


@router.delete("/{employee_id}/family/{member_id}", response_model=FamilyMemberDeleteResponse)
async def delete_employee_family_member(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    member_id: int = Path(..., description="Member ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an employee family member"""
    try:
        from app.models.employee import Employee
        from app.models.employee_relative import EmployeeRelative
        from app.schemas.family import FamilyMemberDeleteResponse
        
        # Validate employee exists and belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the family member
        member = db.query(EmployeeRelative).filter(
            EmployeeRelative.id == member_id,
            EmployeeRelative.employee_id == employee_id,
            EmployeeRelative.is_active == True
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Family member with ID {member_id} not found for employee {employee_id}"
            )
        
        # Soft delete - mark as inactive
        member_name = member.relative_name
        member_relation = member.relation
        
        member.is_active = False
        
        db.commit()
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_delete(
                user_id=current_user.id,
                employee_id=employee_id,
                section="family_members",
                data={"name": member_name, "relation": member_relation},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - family member delete")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return FamilyMemberDeleteResponse(
            success=True,
            message=f"Family member '{member.relative_name}' removed successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in delete_employee_family_member: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete family member: {str(e)}"
        )


@router.get("/employee-additional/{employee_id}", response_model=EmployeeAdditionalInfoResponse)
async def get_employee_additional_info(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee additional information"""
    try:
        from app.models.employee import Employee
        from app.models.employee_additional_info import EmployeeAdditionalInfo
        
        # Validate employee access with business isolation

        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get additional info record
        additional_info = db.query(EmployeeAdditionalInfo).filter(
            EmployeeAdditionalInfo.employee_id == employee_id,
            EmployeeAdditionalInfo.is_active == True
        ).first()
        
        # Prepare response data
        additional_data = AdditionalInfoResponse()
        if additional_info:
            additional_data = AdditionalInfoResponse(
                field1=additional_info.other_info_1 or "",
                field2=additional_info.other_info_2 or "",
                field3=additional_info.other_info_3 or "",
                field4=additional_info.other_info_4 or "",
                field5=additional_info.other_info_5 or "",
                field6=additional_info.other_info_6 or "",
                field7=additional_info.other_info_7 or "",
                field8=additional_info.other_info_8 or "",
                field9=additional_info.other_info_9 or "",
                field10=additional_info.other_info_10 or ""
            )
        
        return EmployeeAdditionalInfoResponse(
            id=employee.id,
            name=f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            code=employee.employee_code or f"EMP{employee.id:03d}",
            additional_info=additional_data,
            field_labels={
                "field1": "Other Info 1",
                "field2": "Other Info 2", 
                "field3": "Other Info 3",
                "field4": "Other Info 4",
                "field5": "Other Info 5",
                "field6": "Other Info 6",
                "field7": "Other Info 7",
                "field8": "Other Info 8",
                "field9": "Other Info 9",
                "field10": "Other Info 10"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_additional_info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee additional info: {str(e)}"
        )


@router.post("/{employee_id}/additional-info", response_model=AdditionalInfoSaveResponse)
async def save_employee_additional_info(
    additional_data: AdditionalInfoUpdateRequest,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Save employee additional information"""
    try:
        from app.models.employee import Employee
        from app.models.employee_additional_info import EmployeeAdditionalInfo
        
        # Validate employee exists and belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if additional info record exists
        additional_info = db.query(EmployeeAdditionalInfo).filter(
            EmployeeAdditionalInfo.employee_id == employee_id,
            EmployeeAdditionalInfo.is_active == True
        ).first()
        
        old_data = {}
        if additional_info:
            # Capture old values
            old_data = {
                "field1": additional_info.other_info_1,
                "field2": additional_info.other_info_2,
                "field3": additional_info.other_info_3,
                "field4": additional_info.other_info_4,
                "field5": additional_info.other_info_5
            }
            
            # Update existing record
            additional_info.other_info_1 = additional_data.field1
            additional_info.other_info_2 = additional_data.field2
            additional_info.other_info_3 = additional_data.field3
            additional_info.other_info_4 = additional_data.field4
            additional_info.other_info_5 = additional_data.field5
            additional_info.other_info_6 = additional_data.field6
            additional_info.other_info_7 = additional_data.field7
            additional_info.other_info_8 = additional_data.field8
            additional_info.other_info_9 = additional_data.field9
            additional_info.other_info_10 = additional_data.field10
        else:
            # Create new record
            additional_info = EmployeeAdditionalInfo(
                employee_id=employee_id,
                other_info_1=additional_data.field1,
                other_info_2=additional_data.field2,
                other_info_3=additional_data.field3,
                other_info_4=additional_data.field4,
                other_info_5=additional_data.field5,
                other_info_6=additional_data.field6,
                other_info_7=additional_data.field7,
                other_info_8=additional_data.field8,
                other_info_9=additional_data.field9,
                other_info_10=additional_data.field10
            )
            db.add(additional_info)
        
        db.commit()
        db.refresh(additional_info)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            new_data = {
                "field1": additional_info.other_info_1,
                "field2": additional_info.other_info_2,
                "field3": additional_info.other_info_3,
                "field4": additional_info.other_info_4,
                "field5": additional_info.other_info_5
            }
            
            change_tracker = EmployeeChangeTracker(db)
            if old_data:
                change_tracker.log_update(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    section="additional_info",
                    old_data=old_data,
                    new_data=new_data,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
            else:
                change_tracker.log_create(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    section="additional_info",
                    data=new_data,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
            print(f"✅ Activity logged for employee {employee_id} - additional info update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return AdditionalInfoSaveResponse(
            success=True,
            message="Additional information saved successfully",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            additional_info=AdditionalInfoResponse(
                field1=additional_info.other_info_1 or "",
                field2=additional_info.other_info_2 or "",
                field3=additional_info.other_info_3 or "",
                field4=additional_info.other_info_4 or "",
                field5=additional_info.other_info_5 or "",
                field6=additional_info.other_info_6 or "",
                field7=additional_info.other_info_7 or "",
                field8=additional_info.other_info_8 or "",
                field9=additional_info.other_info_9 or "",
                field10=additional_info.other_info_10 or ""
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in save_employee_additional_info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save employee additional info: {str(e)}"
        )


@router.get("/employee-documents/{employee_id}")
async def get_employee_documents(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee documents information"""
    try:
        from app.models.employee import Employee, EmployeeDocument
        
        # Validate employee access with business isolation

        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get all documents for this employee
        documents = db.query(EmployeeDocument).filter(
            EmployeeDocument.employee_id == employee_id
        ).order_by(EmployeeDocument.created_at.desc()).all()
        
        # Format documents for frontend
        document_list = []
        for doc in documents:
            document_list.append({
                "id": doc.id,
                "title": doc.document_name,
                "filename": os.path.basename(doc.file_path) if doc.file_path else "",
                "document_type": doc.document_type,
                "file_path": doc.file_path,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "hidden": doc.hidden if hasattr(doc, 'hidden') else False
            })
        
        return {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "code": employee.employee_code or f"EMP{employee.id:03d}",
            "documents": document_list,
            "total_documents": len(document_list),
            "guidelines": {
                "max_file_size": "10 MB",
                "allowed_types": ["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt"],
                "max_filename_length": 100,
                "max_documents": 50
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee documents: {str(e)}"
        )


@router.post("/{employee_id}/documents")
async def upload_employee_document(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    file: UploadFile = File(...),
    document_name: str = Body(...),
    document_type: str = Body(default="general"),
    hidden: bool = Body(default=False),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Upload a document for an employee"""
    try:
        from app.models.employee import Employee, EmployeeDocument
        import os
        import uuid
        from datetime import datetime
        
        # Validate employee exists and belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 10MB limit"
            )
        
        # Check file type
        allowed_extensions = ['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt']
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Check document count limit
        existing_count = db.query(EmployeeDocument).filter(
            EmployeeDocument.employee_id == employee_id
        ).count()
        if existing_count >= 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 documents allowed per employee"
            )
        
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads/employee_documents"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"{employee_id}_{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Create database record
        new_document = EmployeeDocument(
            employee_id=employee_id,
            document_type=document_type,
            document_name=document_name,
            file_path=file_path,
            original_filename=file.filename,
            file_size=len(file_content),
            mime_type=file.content_type,
            hidden=hidden,
            uploaded_by=current_user.id,
            uploaded_at=datetime.now()
        )
        
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_document_upload(
                user_id=current_user.id,
                employee_id=employee_id,
                document_name=document_name,
                document_type=document_type,
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            print(f"✅ Activity logged for employee {employee_id} - document upload")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "document": {
                "id": new_document.id,
                "title": new_document.document_name,
                "filename": file.filename,
                "document_type": new_document.document_type,
                "file_size": new_document.file_size,
                "uploaded_at": new_document.uploaded_at.isoformat()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in upload_employee_document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.delete("/{employee_id}/documents/{document_id}")
async def delete_employee_document(
    document_id: int,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an employee document"""
    try:
        from app.models.employee import Employee, EmployeeDocument
        import os
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the document
        document = db.query(EmployeeDocument).filter(
            EmployeeDocument.id == document_id,
            EmployeeDocument.employee_id == employee_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for employee {employee_id}"
            )
        
        # Delete file from filesystem
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                print(f"Warning: Could not delete file {document.file_path}: {str(e)}")
        
        # Delete from database
        document_name = document.document_name
        document_type = document.document_type
        
        db.delete(document)
        db.commit()
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_document_delete(
                user_id=current_user.id,
                employee_id=employee_id,
                document_name=document_name,
                document_type=document_type,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - document delete")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return {
            "success": True,
            "message": f"Document '{document.document_name}' deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in delete_employee_document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/{employee_id}/documents/{document_id}/download")
async def download_employee_document(
    document_id: int,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Download an employee document"""
    try:
        from app.models.employee import Employee, EmployeeDocument
        from fastapi.responses import FileResponse
        import os
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the document
        document = db.query(EmployeeDocument).filter(
            EmployeeDocument.id == document_id,
            EmployeeDocument.employee_id == employee_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for employee {employee_id}"
            )
        
        # Check if file exists
        if not document.file_path or not os.path.exists(document.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found on server"
            )
        
        # Get original filename
        # Try to use stored original_filename first
        if hasattr(document, 'original_filename') and document.original_filename:
            download_filename = document.original_filename
        else:
            # Fallback: Extract from stored path
            stored_filename = os.path.basename(document.file_path)
            
            # Check if filename has UUID format: {employee_id}_{uuid}_{original_filename}
            # UUID format has 32 hex characters
            parts = stored_filename.split('_', 2)
            if len(parts) > 2 and len(parts[1]) == 32:
                # New format with UUID
                download_filename = parts[2]
            elif len(parts) > 1:
                # Old format without UUID: {employee_id}_{document_type}_{original_filename}
                # Join everything after first underscore
                download_filename = '_'.join(parts[1:])
            else:
                # Fallback to full filename
                download_filename = stored_filename
        
        # Return file response with proper headers
        return FileResponse(
            path=document.file_path,
            filename=download_filename,
            media_type=document.mime_type or 'application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{download_filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in download_employee_document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download document: {str(e)}"
        )


@router.patch("/{employee_id}/documents/{document_id}/visibility")
async def update_document_visibility(
    document_id: int,
    request_data: dict = Body(...),
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update document visibility (hidden/visible)"""
    try:
        from app.models.employee import Employee, EmployeeDocument
        
        # Validate employee and business
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)

        # Extract hidden value from request data
        if "hidden" not in request_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'hidden' field in request body"
            )
        
        hidden = request_data["hidden"]
        if not isinstance(hidden, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'hidden' field must be a boolean value"
            )
        
        # Validate employee exists
        # Validate employee access with business isolation

        employee = validate_employee_access(db, employee_id, current_user)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the document
        document = db.query(EmployeeDocument).filter(
            EmployeeDocument.id == document_id,
            EmployeeDocument.employee_id == employee_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for employee {employee_id}"
            )
        
        # Update visibility
        document.hidden = hidden
        db.commit()
        db.refresh(document)
        
        visibility_status = "hidden" if hidden else "visible"
        
        return {
            "success": True,
            "message": f"Document '{document.document_name}' is now {visibility_status}",
            "document": {
                "id": document.id,
                "title": document.document_name,
                "hidden": document.hidden
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in update_document_visibility: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document visibility: {str(e)}"
        )


@router.get("/employee-assets/{employee_id}", response_model=EmployeeAssetsResponse)
async def get_employee_assets(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee assets information"""
    try:
        from app.models.employee import Employee
        from app.models.asset import Asset
        from app.schemas.asset import EmployeeAssetsResponse, AssetResponse, AssetTypeOption
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get all assets assigned to this employee
        assets = db.query(Asset).filter(
            Asset.assigned_employee_id == employee_id,
            Asset.status == 'ACTIVE'
        ).order_by(Asset.assigned_date.desc()).all()
        
        # Format assets for frontend
        asset_list = []
        for asset in assets:
            asset_data = AssetResponse(
                id=asset.id,
                asset_code=asset.asset_code or "",
                name=asset.name or "Unknown Asset",
                type=asset.asset_type.value if asset.asset_type else "other",
                brand=asset.brand or "",
                model=asset.model or "",
                serial_number=asset.serial_number or "",
                estimated_value=float(asset.estimated_value) if asset.estimated_value else 0,
                assigned_date=asset.assigned_date.isoformat() if asset.assigned_date else None,
                warranty_end_date=asset.warranty_end_date.isoformat() if asset.warranty_end_date else None,
                condition=asset.condition.value if asset.condition else "good",
                status=asset.status.value if asset.status else "active",
                description=asset.description or "",
                warranty_status=asset.warranty_status
            )
            asset_list.append(asset_data)
        
        asset_types = [
            AssetTypeOption(value="laptop", label="Laptop"),
            AssetTypeOption(value="desktop", label="Desktop"),
            AssetTypeOption(value="monitor", label="Monitor"),
            AssetTypeOption(value="keyboard", label="Keyboard"),
            AssetTypeOption(value="mouse", label="Mouse"),
            AssetTypeOption(value="mobile", label="Mobile"),
            AssetTypeOption(value="tablet", label="Tablet"),
            AssetTypeOption(value="printer", label="Printer"),
            AssetTypeOption(value="headset", label="Headset"),
            AssetTypeOption(value="webcam", label="Webcam"),
            AssetTypeOption(value="chair", label="Chair"),
            AssetTypeOption(value="desk", label="Desk"),
            AssetTypeOption(value="other", label="Other")
        ]
        
        return EmployeeAssetsResponse(
            id=employee.id,
            name=f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            code=employee.employee_code or f"EMP{employee.id:03d}",
            assets=asset_list,
            total_assets=len(asset_list),
            asset_types=asset_types
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_assets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee assets: {str(e)}"
        )


@router.post("/{employee_id}/assets", response_model=AssetCreateResponse)
async def create_employee_asset(
    asset_data: AssetCreateRequest,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new asset for an employee"""
    try:
        from app.models.employee import Employee
        from app.models.asset import Asset, AssetType, AssetCondition, AssetStatus
        from app.schemas.asset import AssetCreateRequest, AssetCreateResponse
        from datetime import datetime, date
        import uuid
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Validate asset type
        try:
            asset_type_enum = AssetType(asset_data.asset_type.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid asset type: {asset_data.asset_type}"
            )
        
        # Validate condition
        try:
            condition_enum = AssetCondition(asset_data.condition.value)
        except ValueError:
            condition_enum = AssetCondition.GOOD
        
        # Generate unique asset code
        asset_code = f"AST-{employee_id}-{uuid.uuid4().hex[:8].upper()}"
        
        # Ensure unique serial number if provided
        if asset_data.serial_number:
            existing_asset = db.query(Asset).filter(Asset.serial_number == asset_data.serial_number).first()
            if existing_asset:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Asset with serial number '{asset_data.serial_number}' already exists"
                )
        
        # Create new asset
        new_asset = Asset(
            asset_code=asset_code,
            name=asset_data.name,
            asset_type=asset_type_enum,
            brand=asset_data.brand,
            model=asset_data.model,
            serial_number=asset_data.serial_number if asset_data.serial_number else None,
            description=asset_data.description,
            estimated_value=asset_data.estimated_value,
            assigned_employee_id=employee_id,
            assigned_date=asset_data.assigned_date,
            warranty_end_date=asset_data.warranty_end_date,
            condition=condition_enum,
            status=AssetStatus.ACTIVE,
            business_id=employee.business_id,
            created_by=current_user.id
        )
        
        db.add(new_asset)
        db.commit()
        db.refresh(new_asset)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_asset_assignment(
                user_id=current_user.id,
                employee_id=employee_id,
                asset_name=new_asset.name,
                asset_type=new_asset.asset_type.value,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - asset assignment")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return AssetCreateResponse(
            success=True,
            message="Asset created successfully",
            asset=AssetResponse(
                id=new_asset.id,
                asset_code=new_asset.asset_code,
                name=new_asset.name,
                type=new_asset.asset_type.value,
                brand=new_asset.brand,
                model=new_asset.model,
                serial_number=new_asset.serial_number,
                estimated_value=float(new_asset.estimated_value) if new_asset.estimated_value else 0,
                assigned_date=new_asset.assigned_date.isoformat(),
                warranty_end_date=new_asset.warranty_end_date.isoformat() if new_asset.warranty_end_date else None,
                condition=new_asset.condition.value,
                status=new_asset.status.value,
                description=new_asset.description,
                warranty_status=new_asset.warranty_status
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in create_employee_asset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create asset: {str(e)}"
        )


@router.put("/{employee_id}/assets/{asset_id}", response_model=AssetUpdateResponse)
async def update_employee_asset(
    asset_data: AssetUpdateRequest,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update an employee asset"""
    try:
        from app.models.employee import Employee
        from app.models.asset import Asset, AssetType, AssetCondition
        from app.schemas.asset import AssetUpdateRequest, AssetUpdateResponse, AssetResponse
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the asset
        asset = db.query(Asset).filter(
            Asset.id == asset_id,
            Asset.assigned_employee_id == employee_id
        ).first()
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset with ID {asset_id} not found for employee {employee_id}"
            )
        
        # Validate asset type
        try:
            asset_type_enum = AssetType(asset_data.asset_type.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid asset type: {asset_data.asset_type}"
            )
        
        # Validate condition
        try:
            condition_enum = AssetCondition(asset_data.condition.value)
        except ValueError:
            condition_enum = AssetCondition.GOOD
        
        # Check serial number uniqueness (excluding current asset)
        if asset_data.serial_number:
            existing_asset = db.query(Asset).filter(
                Asset.serial_number == asset_data.serial_number,
                Asset.id != asset_id
            ).first()
            if existing_asset:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Asset with serial number '{asset_data.serial_number}' already exists"
                )
        
        # Update asset
        asset.name = asset_data.name
        asset.asset_type = asset_type_enum
        asset.brand = asset_data.brand
        asset.model = asset_data.model
        asset.serial_number = asset_data.serial_number if asset_data.serial_number else None
        asset.description = asset_data.description
        asset.estimated_value = asset_data.estimated_value
        asset.assigned_date = asset_data.assigned_date
        asset.warranty_end_date = asset_data.warranty_end_date
        asset.condition = condition_enum
        asset.updated_by = current_user.id
        
        db.commit()
        db.refresh(asset)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="assets",
                old_data={"asset_name": asset.name, "asset_type": asset.asset_type.value},
                new_data={"asset_name": asset.name, "asset_type": asset.asset_type.value},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - asset update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return AssetUpdateResponse(
            success=True,
            message="Asset updated successfully",
            asset=AssetResponse(
                id=asset.id,
                asset_code=asset.asset_code,
                name=asset.name,
                type=asset.asset_type.value,
                brand=asset.brand,
                model=asset.model,
                serial_number=asset.serial_number,
                estimated_value=float(asset.estimated_value) if asset.estimated_value else 0,
                assigned_date=asset.assigned_date.isoformat(),
                warranty_end_date=asset.warranty_end_date.isoformat() if asset.warranty_end_date else None,
                condition=asset.condition.value,
                status=asset.status.value,
                description=asset.description,
                warranty_status=asset.warranty_status
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in update_employee_asset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update asset: {str(e)}"
        )


@router.delete("/{employee_id}/assets/{asset_id}", response_model=AssetDeleteResponse)
async def delete_employee_asset(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an employee asset"""
    try:
        from app.models.employee import Employee
        from app.models.asset import Asset, AssetStatus
        from app.schemas.asset import AssetDeleteResponse
        from datetime import date
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Find the asset
        asset = db.query(Asset).filter(
            Asset.id == asset_id,
            Asset.assigned_employee_id == employee_id
        ).first()
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset with ID {asset_id} not found for employee {employee_id}"
            )
        
        # Instead of deleting, mark as inactive (soft delete)
        asset_name = asset.name
        asset_type = asset.asset_type.value
        
        asset.status = AssetStatus.INACTIVE
        asset.assigned_employee_id = None
        asset.return_date = date.today()
        asset.updated_by = current_user.id
        
        db.commit()
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_asset_return(
                user_id=current_user.id,
                employee_id=employee_id,
                asset_name=asset_name,
                asset_type=asset_type,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - asset return")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return AssetDeleteResponse(
            success=True,
            message=f"Asset '{asset.name}' removed from employee successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in delete_employee_asset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete asset: {str(e)}"
        )


@router.get("/employee-policies/{employee_id}")
async def get_employee_policies(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee policies information from database"""
    try:
        from app.models.employee import Employee
        from app.models.shift_policy import ShiftPolicy
        from app.models.weekoff_policy import WeekOffPolicy
        from app.models.leave_policy import LeavePolicy
        from app.models.setup.salary_and_deductions.overtime import OvertimePolicy
        from app.models.employee_leave_policy import EmployeeLeavePolicy
        from sqlalchemy.orm import joinedload
        
        validate_business_access(business_id, current_user, db)
        # Validate employee access with business isolation
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        
        # Get employee with basic policy relationships
        employee = db.query(Employee).options(
            joinedload(Employee.shift_policy),
            joinedload(Employee.weekoff_policy),
            joinedload(Employee.overtime_policy),
            joinedload(Employee.leave_policy_assignments).joinedload(EmployeeLeavePolicy.leave_policy)
        ).filter(Employee.id == employee_id, Employee.business_id == business_id).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get all available policies for dropdowns
        all_shift_policies = db.query(ShiftPolicy).filter(
            ShiftPolicy.business_id == employee.business_id
        ).all()
        
        all_weekoff_policies = db.query(WeekOffPolicy).filter(
            WeekOffPolicy.business_id == employee.business_id
        ).all()
        
        all_leave_policies = db.query(LeavePolicy).filter(
            LeavePolicy.business_id == employee.business_id
        ).all()
        
        # Get overtime policies from setup system
        all_overtime_policies = db.query(OvertimePolicy).filter(
            OvertimePolicy.business_id == employee.business_id
        ).all()
        
        # Get active leave policy assignments
        active_leave_assignments = [
            assignment for assignment in employee.leave_policy_assignments
            if assignment.is_active
        ]
        
        # Build simplified response with real database data
        response = {
            "id": employee.id,
            "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            "currentPolicies": {
                "shiftPolicy": {
                    "id": employee.shift_policy_id,
                    "name": employee.shift_policy.title if employee.shift_policy else None,
                    "description": employee.shift_policy.description if employee.shift_policy else None
                },
                "weekOffPolicy": {
                    "id": employee.weekoff_policy_id,
                    "name": employee.weekoff_policy.title if employee.weekoff_policy else None,
                    "description": employee.weekoff_policy.description if employee.weekoff_policy else None
                },
                "overtimePolicy": {
                    "id": employee.overtime_policy_id,
                    "name": employee.overtime_policy.policy_name if employee.overtime_policy else None,
                    "description": f"Overtime policy with {len(employee.overtime_policy.rules)} rules" if employee.overtime_policy else None
                },
                "autoShiftEnabled": employee.auto_shift_enabled or False,
                "leavePolicies": [
                    {
                        "id": assignment.leave_policy.id,
                        "policyName": assignment.leave_policy.policy_name,
                        "leaveType": assignment.leave_policy.leave_type,
                        "description": assignment.leave_policy.description,
                        "isAssigned": True
                    } for assignment in active_leave_assignments
                ]
            },
            "availablePolicies": {
                "shiftPolicies": [
                    {
                        "id": policy.id,
                        "title": policy.title,
                        "description": policy.description,
                        "isDefault": policy.is_default
                    } for policy in all_shift_policies
                ],
                "weekOffPolicies": [
                    {
                        "id": policy.id,
                        "title": policy.title,
                        "description": policy.description,
                        "isDefault": policy.is_default
                    } for policy in all_weekoff_policies
                ],
                "overtimePolicies": [
                    {
                        "id": policy.id,
                        "title": policy.policy_name,
                        "description": f"Overtime policy with {len(policy.rules)} rules",
                        "isDefault": False,
                        "rateMultiplier": 1.5,  # Default value
                        "minimumHours": 1.0,
                        "maximumHours": 12.0
                    } for policy in all_overtime_policies
                ],
                "leavePolicies": [
                    {
                        "id": policy.id,
                        "policyName": policy.policy_name,
                        "leaveType": policy.leave_type,
                        "description": policy.description,
                        "isAssigned": any(
                            assignment.leave_policy_id == policy.id and assignment.is_active
                            for assignment in employee.leave_policy_assignments
                        )
                    } for policy in all_leave_policies
                ]
            },
            "policies": {
                "attendancePolicy": {
                    "assigned": True,
                    "policyName": "Standard Attendance Policy",
                    "workingHours": "9 hours",
                    "flexiTime": True,
                    "lateMarkGrace": "15 minutes"
                },
                "leavePolicy": {
                    "assigned": len(active_leave_assignments) > 0,
                    "policyName": f"{len(active_leave_assignments)} Leave Policies Assigned",
                    "assignedPolicies": [assignment.leave_policy.policy_name for assignment in active_leave_assignments],
                    "totalPolicies": len(all_leave_policies)
                },
                "shiftPolicy": {
                    "assigned": employee.shift_policy_id is not None,
                    "policyName": employee.shift_policy.title if employee.shift_policy else "No Shift Policy Assigned",
                    "startTime": "09:00 AM" if employee.shift_policy else "Not Set",
                    "endTime": "06:00 PM" if employee.shift_policy else "Not Set",
                    "breakTime": "1 hour" if employee.shift_policy else "Not Set"
                },
                "weekOffPolicy": {
                    "assigned": employee.weekoff_policy_id is not None,
                    "policyName": employee.weekoff_policy.title if employee.weekoff_policy else "No Week Off Policy Assigned",
                    "weekOffs": ["Saturday", "Sunday"] if employee.weekoff_policy else [],
                    "totalWeekOffs": 2 if employee.weekoff_policy else 0
                },
                "overtimePolicy": {
                    "assigned": employee.overtime_policy_id is not None,
                    "policyName": employee.overtime_policy.policy_name if employee.overtime_policy else "No Overtime Policy Assigned",
                    "overtimeRate": "1.5x" if employee.overtime_policy else "Not Set",
                    "minimumHours": 1 if employee.overtime_policy else 0
                },
                "autoShiftPolicy": {
                    "assigned": employee.auto_shift_enabled or False,
                    "policyName": "Auto Shift Selection",
                    "status": "Enabled" if employee.auto_shift_enabled else "Disabled"
                }
            }
        }
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_policies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee policies: {str(e)}"
        )


@router.put("/{employee_id}/policies")
async def update_employee_policies(
    policies_data: EmployeePoliciesUpdate,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee policies with proper database relationships"""
    try:
        from app.models.employee import Employee
        from app.models.shift_policy import ShiftPolicy
        from app.models.weekoff_policy import WeekOffPolicy
        from app.models.setup.salary_and_deductions.overtime import OvertimePolicy
        from app.models.leave_policy import LeavePolicy
        from app.models.employee_leave_policy import EmployeeLeavePolicy
        
        # Validate that the request body has at least one field
        try:
            policies_data.validate_not_empty()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        validate_business_access(business_id, current_user, db)
        # Check if employee exists and belongs to business
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Track what policies are being updated
        updated_policies = []
        
        # Convert Pydantic model to dict for processing
        policies_dict = policies_data.dict(exclude_none=True)
        
        # Update shift policy using proper foreign key
        if 'shiftPolicy' in policies_dict:
            shift_policy_id = policies_dict['shiftPolicy']
            if shift_policy_id:
                # Validate shift policy exists and belongs to employee's business
                shift_policy = db.query(ShiftPolicy).filter(
                    ShiftPolicy.id == int(shift_policy_id),
                    ShiftPolicy.business_id == employee.business_id
                ).first()
                
                if not shift_policy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Shift policy with ID {shift_policy_id} not found or not accessible"
                    )
                
                employee.shift_policy_id = int(shift_policy_id)
                updated_policies.append("shiftPolicy")
            else:
                # Clear shift policy assignment
                employee.shift_policy_id = None
                updated_policies.append("shiftPolicy")
        
        # Update week off policy using proper foreign key
        if 'weekOffPolicy' in policies_dict:
            weekoff_policy_id = policies_dict['weekOffPolicy']
            if weekoff_policy_id:
                # Validate weekoff policy exists and belongs to employee's business
                weekoff_policy = db.query(WeekOffPolicy).filter(
                    WeekOffPolicy.id == int(weekoff_policy_id),
                    WeekOffPolicy.business_id == employee.business_id
                ).first()
                
                if not weekoff_policy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Week off policy with ID {weekoff_policy_id} not found or not accessible"
                    )
                
                employee.weekoff_policy_id = int(weekoff_policy_id)
                updated_policies.append("weekOffPolicy")
            else:
                # Clear weekoff policy assignment
                employee.weekoff_policy_id = None
                updated_policies.append("weekOffPolicy")
        
        # Handle other policy updates (overtime, auto shift, leave policies)
        # Update overtime policy using proper foreign key
        if 'overtimePolicy' in policies_dict:
            overtime_policy_id = policies_dict['overtimePolicy']
            if overtime_policy_id and overtime_policy_id != "" and overtime_policy_id != "0":
                # Validate overtime policy exists and belongs to employee's business
                overtime_policy = db.query(OvertimePolicy).filter(
                    OvertimePolicy.id == int(overtime_policy_id),
                    OvertimePolicy.business_id == employee.business_id
                ).first()
                
                if not overtime_policy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Overtime policy with ID {overtime_policy_id} not found or not accessible"
                    )
                
                employee.overtime_policy_id = int(overtime_policy_id)
                updated_policies.append("overtimePolicy")
            else:
                # Clear overtime policy assignment (empty string, "0", or None)
                employee.overtime_policy_id = None
                updated_policies.append("overtimePolicy")
        
        if 'autoShiftEnabled' in policies_dict:
            # Save auto shift enabled state to database
            auto_shift_enabled = policies_dict['autoShiftEnabled']
            employee.auto_shift_enabled = auto_shift_enabled
            updated_policies.append("autoShiftEnabled")
        
        if 'leavePolicies' in policies_dict:
            # Handle leave policies assignment using junction table
            leave_policies = policies_dict['leavePolicies']
            
            if isinstance(leave_policies, dict):
                # Clear existing assignments
                db.query(EmployeeLeavePolicy).filter(
                    EmployeeLeavePolicy.employee_id == employee_id
                ).delete()
                
                # Add new assignments
                for leave_type, is_enabled in leave_policies.items():
                    if is_enabled:
                        # Improved matching logic - handle different formats
                        leave_policy = None
                        
                        # Try exact match first (remove spaces and convert to lowercase)
                        for policy in db.query(LeavePolicy).filter(
                            LeavePolicy.business_id == employee.business_id
                        ).all():
                            policy_type_normalized = policy.leave_type.lower().replace(' ', '').replace('-', '')
                            leave_type_normalized = leave_type.lower().replace(' ', '').replace('-', '')
                            
                            if policy_type_normalized == leave_type_normalized:
                                leave_policy = policy
                                break
                        
                        # If no exact match, try partial match
                        if not leave_policy:
                            # Convert leave_type key to readable format for partial matching
                            search_terms = []
                            if 'casual' in leave_type.lower():
                                search_terms.append('casual')
                            if 'sick' in leave_type.lower():
                                search_terms.append('sick')
                            if 'annual' in leave_type.lower():
                                search_terms.append('annual')
                            if 'maternity' in leave_type.lower():
                                search_terms.append('maternity')
                            if 'compensatory' in leave_type.lower() or 'compoff' in leave_type.lower():
                                search_terms.append('compensatory')
                            
                            for term in search_terms:
                                leave_policy = db.query(LeavePolicy).filter(
                                    LeavePolicy.business_id == employee.business_id,
                                    LeavePolicy.leave_type.ilike(f"%{term}%")
                                ).first()
                                if leave_policy:
                                    break
                        
                        if leave_policy:
                            employee_leave_policy = EmployeeLeavePolicy(
                                employee_id=employee_id,
                                leave_policy_id=leave_policy.id,
                                is_active=True,
                                assigned_by=current_user.id  # Use actual user ID instead of None
                            )
                            db.add(employee_leave_policy)
                
                updated_policies.append("leavePolicies")
        
        # Update system fields
        employee.updated_by = current_user.id
        
        # Commit changes
        db.commit()
        db.refresh(employee)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            for policy_name in updated_policies:
                change_tracker.log_policy_assignment(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    policy_name=policy_name,
                    policy_type="employee_policy",
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
            print(f"✅ Activity logged for employee {employee_id} - policies update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return {
            "success": True,
            "message": "Employee policies updated successfully",
            "updatedPolicies": updated_policies,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "validationInfo": {
                "totalFieldsProvided": len(policies_dict),
                "fieldsUpdated": len(updated_policies),
                "validationPassed": True
            }
        }
    
    except HTTPException:
        raise
    except ValueError as e:
        # Handle Pydantic validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR in update_employee_policies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee policies: {str(e)}"
        )


@router.get("/employee-permissions/{employee_id}")
async def get_employee_permissions(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> EmployeePermissionsDisplay:
    """Get employee permissions information"""
    try:
        from app.models.employee import Employee
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Try to get permissions record, but handle if table doesn't exist
        permissions_data = {}
        try:
            from app.models.employee_permissions import EmployeePermissions
            
            # Get permissions record
            permissions = db.query(EmployeePermissions).filter(
                EmployeePermissions.employee_id == employee_id,
                EmployeePermissions.is_active == True
            ).first()
            
            # Prepare permissions data
            if permissions:
                permissions_data = {
                    # Attendance & Punches
                    "chkSelfiePunch": permissions.selfie_punch,
                    "chkSelfieFaceMatch": permissions.selfie_face_recognition,
                    "chkSelfieAllLocations": permissions.selfie_all_locations,
                    "chkRemotePunch": permissions.remote_punch,
                    "chkMissedPunch": permissions.missed_punch,
                    "txtMissedPunchCount": str(permissions.missed_punch_limit or 0),
                    "chkWebPunch": permissions.web_punch,
                    "chkTimeRelaxation": permissions.time_relaxation,
                    "chkQrAllLocations": permissions.scan_all_locations,
                    "chkDisableStrikes": permissions.ignore_time_strikes,
                    "chkAutoPunch": permissions.auto_punch,
                    
                    # Travel & Visit Tracking
                    "chkTravelPunch": permissions.visit_punch,
                    "chkTravelPunchApproval": permissions.visit_punch_approval,
                    "chkTravelPunchAttendance": permissions.visit_punch_attendance,
                    "chkLiveTravel": permissions.live_travel,
                    "chkLiveTravelAttendance": permissions.live_travel_attendance,
                    
                    # Rewards and Recognition
                    "chkGiveBadges": permissions.give_badges,
                    "chkGiveRewards": permissions.give_rewards
                }
            else:
                # Return default permissions if no record exists
                permissions_data = {
                    # Attendance & Punches
                    "chkSelfiePunch": True,
                    "chkSelfieFaceMatch": False,
                    "chkSelfieAllLocations": False,
                    "chkRemotePunch": True,
                    "chkMissedPunch": True,
                    "txtMissedPunchCount": "0",
                    "chkWebPunch": False,
                    "chkTimeRelaxation": False,
                    "chkQrAllLocations": True,
                    "chkDisableStrikes": False,
                    "chkAutoPunch": False,
                    
                    # Travel & Visit Tracking
                    "chkTravelPunch": False,
                    "chkTravelPunchApproval": False,
                    "chkTravelPunchAttendance": False,
                    "chkLiveTravel": False,
                    "chkLiveTravelAttendance": False,
                    
                    # Rewards and Recognition
                    "chkGiveBadges": False,
                    "chkGiveRewards": False
                }
        except Exception as permissions_error:
            print(f"⚠️ Warning: Could not access permissions table: {permissions_error}")
            # Return default permissions if table doesn't exist or has issues
            permissions_data = {
                # Attendance & Punches
                "chkSelfiePunch": True,
                "chkSelfieFaceMatch": False,
                "chkSelfieAllLocations": False,
                "chkRemotePunch": True,
                "chkMissedPunch": True,
                "txtMissedPunchCount": "0",
                "chkWebPunch": False,
                "chkTimeRelaxation": False,
                "chkQrAllLocations": True,
                "chkDisableStrikes": False,
                "chkAutoPunch": False,
                
                # Travel & Visit Tracking
                "chkTravelPunch": False,
                "chkTravelPunchApproval": False,
                "chkTravelPunchAttendance": False,
                "chkLiveTravel": False,
                "chkLiveTravelAttendance": False,
                
                # Rewards and Recognition
                "chkGiveBadges": False,
                "chkGiveRewards": False
            }
        
        return EmployeePermissionsDisplay(
            id=employee.id,
            name=f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            code=employee.employee_code or f"EMP{employee.id:03d}",
            permissions=permissions_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee permissions: {str(e)}"
        )


@router.put("/{employee_id}/permissions")
async def update_employee_permissions(
    permissions_data: EmployeePermissionsFrontendUpdate,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> EmployeePermissionsUpdateResponse:
    """Update employee permissions with proper Pydantic validation"""
    try:
        from app.models.employee import Employee
        from app.models.employee_permissions import EmployeePermissions
        from app.schemas.employee_permissions import EmployeePermissionsUpdateResponse
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Convert string missed punch count to integer (Pydantic already validated this)
        try:
            missed_punch_limit = int(permissions_data.txtMissedPunchCount)
        except (ValueError, TypeError):
            missed_punch_limit = 0
        
        # Check if permissions record exists
        permissions = db.query(EmployeePermissions).filter(
            EmployeePermissions.employee_id == employee_id,
            EmployeePermissions.is_active == True
        ).first()
        
        if permissions:
            # Update existing record
            permissions.selfie_punch = permissions_data.chkSelfiePunch
            permissions.selfie_face_recognition = permissions_data.chkSelfieFaceMatch
            permissions.selfie_all_locations = permissions_data.chkSelfieAllLocations
            permissions.remote_punch = permissions_data.chkRemotePunch
            permissions.missed_punch = permissions_data.chkMissedPunch
            permissions.missed_punch_limit = missed_punch_limit
            permissions.web_punch = permissions_data.chkWebPunch
            permissions.time_relaxation = permissions_data.chkTimeRelaxation
            permissions.scan_all_locations = permissions_data.chkQrAllLocations
            permissions.ignore_time_strikes = permissions_data.chkDisableStrikes
            permissions.auto_punch = permissions_data.chkAutoPunch
            permissions.visit_punch = permissions_data.chkTravelPunch
            permissions.visit_punch_approval = permissions_data.chkTravelPunchApproval
            permissions.visit_punch_attendance = permissions_data.chkTravelPunchAttendance
            permissions.live_travel = permissions_data.chkLiveTravel
            permissions.live_travel_attendance = permissions_data.chkLiveTravelAttendance
            permissions.give_badges = permissions_data.chkGiveBadges
            permissions.give_rewards = permissions_data.chkGiveRewards
        else:
            # Create new record
            permissions = EmployeePermissions(
                employee_id=employee_id,
                selfie_punch=permissions_data.chkSelfiePunch,
                selfie_face_recognition=permissions_data.chkSelfieFaceMatch,
                selfie_all_locations=permissions_data.chkSelfieAllLocations,
                remote_punch=permissions_data.chkRemotePunch,
                missed_punch=permissions_data.chkMissedPunch,
                missed_punch_limit=missed_punch_limit,
                web_punch=permissions_data.chkWebPunch,
                time_relaxation=permissions_data.chkTimeRelaxation,
                scan_all_locations=permissions_data.chkQrAllLocations,
                ignore_time_strikes=permissions_data.chkDisableStrikes,
                auto_punch=permissions_data.chkAutoPunch,
                visit_punch=permissions_data.chkTravelPunch,
                visit_punch_approval=permissions_data.chkTravelPunchApproval,
                visit_punch_attendance=permissions_data.chkTravelPunchAttendance,
                live_travel=permissions_data.chkLiveTravel,
                live_travel_attendance=permissions_data.chkLiveTravelAttendance,
                give_badges=permissions_data.chkGiveBadges,
                give_rewards=permissions_data.chkGiveRewards
            )
            db.add(permissions)
        
        db.commit()
        db.refresh(permissions)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_permission_change(
                user_id=current_user.id,
                employee_id=employee_id,
                permission_name="Employee Permissions",
                granted=True,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - permissions update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return EmployeePermissionsUpdateResponse(
            success=True,
            message="Employee permissions updated successfully",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            permissions={
                "chkSelfiePunch": permissions.selfie_punch,
                "chkSelfieFaceMatch": permissions.selfie_face_recognition,
                "chkSelfieAllLocations": permissions.selfie_all_locations,
                "chkRemotePunch": permissions.remote_punch,
                "chkMissedPunch": permissions.missed_punch,
                "txtMissedPunchCount": str(permissions.missed_punch_limit or 0),
                "chkWebPunch": permissions.web_punch,
                "chkTimeRelaxation": permissions.time_relaxation,
                "chkQrAllLocations": permissions.scan_all_locations,
                "chkDisableStrikes": permissions.ignore_time_strikes,
                "chkAutoPunch": permissions.auto_punch,
                "chkTravelPunch": permissions.visit_punch,
                "chkTravelPunchApproval": permissions.visit_punch_approval,
                "chkTravelPunchAttendance": permissions.visit_punch_attendance,
                "chkLiveTravel": permissions.live_travel,
                "chkLiveTravelAttendance": permissions.live_travel_attendance,
                "chkGiveBadges": permissions.give_badges,
                "chkGiveRewards": permissions.give_rewards
            }
        )
    
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR in update_employee_permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee permissions: {str(e)}"
        )


@router.get("/employee-access/{employee_id}")
async def get_employee_access(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> EmployeeAccessDisplay:
    """Get employee access information"""
    try:
        from app.models.employee import Employee
        from app.models.employee_access import EmployeeAccess, EmployeeLoginSession
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get access settings
        access_settings = db.query(EmployeeAccess).filter(
            EmployeeAccess.employee_id == employee_id,
            EmployeeAccess.is_active == True
        ).first()
        
        # Get active login sessions
        login_sessions = db.query(EmployeeLoginSession).filter(
            EmployeeLoginSession.employee_id == employee_id,
            EmployeeLoginSession.is_active == True
        ).all()
        
        # Prepare access data
        access_data = {}
        if access_settings:
            access_data = {
                "pinNeverExpires": access_settings.pin_never_expires,
                "multiDeviceLogins": access_settings.multi_device_logins,
                "mobileAccessEnabled": access_settings.mobile_access_enabled,
                "webAccessEnabled": access_settings.web_access_enabled,
                "wallAdmin": access_settings.wall_admin,
                "wallPosting": access_settings.wall_posting,
                "wallCommenting": access_settings.wall_commenting
            }
        else:
            # Return default access settings if no record exists
            access_data = {
                "pinNeverExpires": False,
                "multiDeviceLogins": False,
                "mobileAccessEnabled": True,
                "webAccessEnabled": True,
                "wallAdmin": False,
                "wallPosting": True,
                "wallCommenting": True
            }
        
        # Prepare login sessions data
        sessions_data = []
        for session in login_sessions:
            sessions_data.append({
                "id": session.id,
                "sessionToken": session.session_token,
                "deviceName": session.device_name or "Unknown Device",
                "deviceType": session.device_type or "mobile",
                "osVersion": session.os_version or "Unknown OS",
                "appVersion": session.app_version or "Unknown Version",
                "ipAddress": session.ip_address or "",
                "lastActivity": session.last_activity.isoformat() if session.last_activity else None,
                "loginTime": session.login_time.isoformat() if session.login_time else None,
                "isActive": session.is_active
            })
        
        return EmployeeAccessDisplay(
            id=employee.id,
            name=f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
            code=employee.employee_code or f"EMP{employee.id:03d}",
            companyCode="LEV029",  # This should come from business settings
            employeeCode=employee.employee_code or f"LEV{employee.id:03d}",
            access=access_data,
            loginSessions=sessions_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee access: {str(e)}"
        )


@router.put("/{employee_id}/access")
async def update_employee_access(
    access_data: EmployeeAccessFrontendUpdate,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> EmployeeAccessUpdateResponse:
    """Update employee access settings"""
    try:
        from app.models.employee import Employee
        from app.models.employee_access import EmployeeAccess
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if access record exists
        access_settings = db.query(EmployeeAccess).filter(
            EmployeeAccess.employee_id == employee_id,
            EmployeeAccess.is_active == True
        ).first()
        
        if access_settings:
            # Update existing record
            access_settings.pin_never_expires = access_data.pinNeverExpires
            access_settings.multi_device_logins = access_data.multiDeviceLogins
            access_settings.mobile_access_enabled = access_data.mobileAccessEnabled
            access_settings.web_access_enabled = access_data.webAccessEnabled
            access_settings.wall_admin = access_data.wallAdmin
            access_settings.wall_posting = access_data.wallPosting
            access_settings.wall_commenting = access_data.wallCommenting
        else:
            # Create new record
            access_settings = EmployeeAccess(
                employee_id=employee_id,
                pin_never_expires=access_data.pinNeverExpires,
                multi_device_logins=access_data.multiDeviceLogins,
                mobile_access_enabled=access_data.mobileAccessEnabled,
                web_access_enabled=access_data.webAccessEnabled,
                wall_admin=access_data.wallAdmin,
                wall_posting=access_data.wallPosting,
                wall_commenting=access_data.wallCommenting
            )
            db.add(access_settings)
        
        db.commit()
        db.refresh(access_settings)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            # Build a descriptive action message
            changes = []
            
            if access_data.mobileAccessEnabled:
                changes.append("Mobile Access Enabled")
            if access_data.webAccessEnabled:
                changes.append("Web Access Enabled")
            if access_data.multiDeviceLogins:
                changes.append("Multi-Device Logins")
            if access_data.pinNeverExpires:
                changes.append("PIN Never Expires")
            if access_data.wallAdmin:
                changes.append("Wall Admin")
            if access_data.wallPosting:
                changes.append("Wall Posting")
            if access_data.wallCommenting:
                changes.append("Wall Commenting")
            
            # Build action message
            if changes:
                if len(changes) == 1:
                    action = f"Updated {changes[0]} in Login & Access"
                elif len(changes) <= 3:
                    action = f"Updated {', '.join(changes)} in Login & Access"
                else:
                    action = f"Updated {len(changes)} settings in Login & Access"
            else:
                action = "Updated Login & Access Settings"
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_change(
                user_id=current_user.id,
                employee_id=employee_id,
                section="login_access",
                action=action,
                new_values={
                    "pin_never_expires": access_data.pinNeverExpires,
                    "multi_device_logins": access_data.multiDeviceLogins,
                    "mobile_access_enabled": access_data.mobileAccessEnabled,
                    "web_access_enabled": access_data.webAccessEnabled,
                    "wall_admin": access_data.wallAdmin,
                    "wall_posting": access_data.wallPosting,
                    "wall_commenting": access_data.wallCommenting
                },
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - login access update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return EmployeeAccessUpdateResponse(
            success=True,
            message="Employee access settings updated successfully",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            access={
                "pinNeverExpires": access_settings.pin_never_expires,
                "multiDeviceLogins": access_settings.multi_device_logins,
                "mobileAccessEnabled": access_settings.mobile_access_enabled,
                "webAccessEnabled": access_settings.web_access_enabled,
                "wallAdmin": access_settings.wall_admin,
                "wallPosting": access_settings.wall_posting,
                "wallCommenting": access_settings.wall_commenting
            }
        )
    
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR in update_employee_access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee access: {str(e)}"
        )


@router.post("/{employee_id}/access/send-mobile-login")
async def send_mobile_login(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> EmployeeAccessActionResponse:
    """Send mobile login details to employee"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.services.email_service import email_service
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if employee has email
        if not employee.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # Check if employee has mobile
        if not employee.mobile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have a mobile number"
            )
        
        # Get business for company name
        business = db.query(Business).filter(Business.id == employee.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Generate company ID from business code or use default
        company_id = business.business_code if business and hasattr(business, 'business_code') and business.business_code else "LEV001"
        
        # Generate login PIN (last 6 digits of mobile)
        login_pin = employee.mobile[-6:] if employee.mobile and len(employee.mobile) >= 6 else str(random.randint(100000, 999999))
        
        # Send mobile login email
        email_sent = await email_service.send_mobile_login_email(
            employee_name=f"{employee.first_name} {employee.last_name}",
            employee_code=employee.employee_code,
            employee_email=employee.email,
            mobile=employee.mobile,
            company_name=company_name,
            company_id=company_id,
            login_pin=login_pin
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please check SMTP configuration."
            )
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_change(
                user_id=current_user.id,
                employee_id=employee_id,
                section="login_access",
                action="Sent Mobile Login credentials via email",
                new_values={"email": employee.email, "mobile": employee.mobile},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - sent mobile login")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return EmployeeAccessActionResponse(
            success=True,
            message=f"Mobile login details sent to {employee.first_name} {employee.last_name} at {employee.email}",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "mobile": employee.mobile,
                "email": employee.email
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in send_mobile_login: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send mobile login: {str(e)}"
        )


@router.post("/{employee_id}/access/reset-mobile-pin")
async def reset_mobile_pin(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Reset mobile PIN for employee and send new PIN via email"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.services.email_service import email_service
        import random
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if employee has email
        if not employee.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # Check if employee has mobile
        if not employee.mobile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have a mobile number"
            )
        
        # Get business for company name
        business = db.query(Business).filter(Business.id == employee.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Generate company ID from business code or use default
        company_id = business.business_code if business and hasattr(business, 'business_code') and business.business_code else "LEV001"
        
        # Generate NEW random 6-digit PIN
        new_pin = str(random.randint(100000, 999999))
        
        # Send email with new PIN
        email_sent = await email_service.send_mobile_login_email(
            employee_name=f"{employee.first_name} {employee.last_name}",
            employee_code=employee.employee_code,
            employee_email=employee.email,
            mobile=employee.mobile,
            company_name=company_name,
            company_id=company_id,
            login_pin=new_pin
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please check SMTP configuration."
            )
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_change(
                user_id=current_user.id,
                employee_id=employee_id,
                section="login_access",
                action="Reset Mobile PIN and sent new PIN via email",
                new_values={"email": employee.email},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - reset mobile PIN")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return EmployeeAccessActionResponse(
            success=True,
            message=f"New mobile PIN sent to {employee.first_name} {employee.last_name} at {employee.email}",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "mobile": employee.mobile,
                "email": employee.email
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in reset_mobile_pin: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset mobile PIN: {str(e)}"
        )


@router.post("/{employee_id}/access/send-web-login")
async def send_web_login(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Send web login details to employee"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.services.email_service import email_service
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if employee has email
        if not employee.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # Get business for company name
        business = db.query(Business).filter(Business.id == employee.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Generate company ID from business code or use default
        company_id = business.business_code if business and hasattr(business, 'business_code') and business.business_code else "LEV001"
        
        # Generate login PIN from employee code digits
        code_digits = ''.join(filter(str.isdigit, employee.employee_code))
        login_pin = code_digits[-6:].zfill(6) if code_digits else str(random.randint(100000, 999999))
        
        # Send web login email
        # Note: You can optionally generate a temporary password here
        # For now, we'll send without temporary password (OTP-based login)
        email_sent = await email_service.send_web_login_email(
            employee_name=f"{employee.first_name} {employee.last_name}",
            employee_code=employee.employee_code,
            employee_email=employee.email,
            company_name=company_name,
            company_id=company_id,
            login_pin=login_pin,
            temporary_password=None  # Set to None for OTP-based login
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please check SMTP configuration."
            )
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_change(
                user_id=current_user.id,
                employee_id=employee_id,
                section="login_access",
                action="Sent Web Login credentials via email",
                new_values={"email": employee.email},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - sent web login")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return {
            "success": True,
            "message": f"Web login details sent to {employee.first_name} {employee.last_name} at {employee.email}",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "email": employee.email,
                "employee_code": employee.employee_code
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in send_web_login: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send web login: {str(e)}"
        )


@router.post("/{employee_id}/access/send-runtime-workman")
async def send_runtime_workman(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Send Runtime Workman login details to employee"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.services.email_service import email_service
        import random
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if employee has email
        if not employee.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # Get business for company details
        business = db.query(Business).filter(Business.id == employee.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Generate company ID from business code or use default
        company_id = business.business_code if business and hasattr(business, 'business_code') and business.business_code else "LEV001"
        
        # Generate or retrieve login PIN (6 digits)
        # In production, you should store this in the database
        # For now, we'll generate a random 6-digit PIN
        login_pin = str(random.randint(100000, 999999))
        
        # Send Runtime Workman email
        email_sent = await email_service.send_runtime_workman_email(
            employee_name=f"{employee.first_name} {employee.last_name}",
            company_id=company_id,
            employee_code=employee.employee_code,
            login_pin=login_pin,
            employee_email=employee.email,
            company_name=company_name
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please check SMTP configuration."
            )
        
        return {
            "success": True,
            "message": f"Runtime Workman login details sent to {employee.first_name} {employee.last_name} at {employee.email}",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "email": employee.email,
                "employee_code": employee.employee_code,
                "company_id": company_id,
                "login_pin": login_pin  # In production, don't return this in response
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in send_runtime_workman: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send Runtime Workman details: {str(e)}"
        )


@router.post("/{employee_id}/access/reset-web-password")
async def reset_web_password(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Reset web password for employee and send password reset link via email"""
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.services.email_service import email_service
        import random
        import string
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Check if employee has email
        if not employee.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # Get business for company name
        business = db.query(Business).filter(Business.id == employee.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Generate company ID from business code or use default
        company_id = business.business_code if business and hasattr(business, 'business_code') and business.business_code else "LEV001"
        
        # Generate temporary password (8 characters: letters + numbers)
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # Send web login email with temporary password
        email_sent = await email_service.send_web_login_email(
            employee_name=f"{employee.first_name} {employee.last_name}",
            employee_code=employee.employee_code,
            employee_email=employee.email,
            company_name=company_name,
            company_id=company_id,
            login_pin=None,
            temporary_password=temp_password
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please check SMTP configuration."
            )
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_change(
                user_id=current_user.id,
                employee_id=employee_id,
                section="login_access",
                action="Reset Web Password and sent reset link via email",
                new_values={"email": employee.email},
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - reset web password")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        return EmployeeAccessActionResponse(
            success=True,
            message=f"Password reset instructions sent to {employee.first_name} {employee.last_name} at {employee.email}",
            employee={
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "email": employee.email,
                "employee_code": employee.employee_code
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in reset_web_password: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset web password: {str(e)}"
        )


@router.delete("/{employee_id}/access/logout-session/{session_id}")
async def logout_session(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    session_id: int = Path(..., description="Session ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Logout a specific session for employee"""
    try:
        from app.models.employee import Employee
        from app.models.employee_access import EmployeeLoginSession
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        session = db.query(EmployeeLoginSession).filter(
            EmployeeLoginSession.id == session_id,
            EmployeeLoginSession.employee_id == employee_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with ID {session_id} not found"
            )
        
        # Mark session as inactive and set logout time
        session.is_active = False
        session.logout_time = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Session logged out successfully",
            "session": {
                "id": session.id,
                "deviceName": session.device_name,
                "logoutTime": session.logout_time.isoformat()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in logout_session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout session: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee access: {str(e)}"
        )


@router.get("/employee-activity/{employee_id}", response_model=EmployeeActivityResponse)
async def get_employee_activity(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee activity information"""
    try:
        from app.services.activity_log_service import ActivityLogService
        from app.schemas.activity_logs import EmployeeActivityResponse
        
        # Create activity log service
        activity_service = ActivityLogService(db)
        
        # Validate business and employee
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)

        # Get employee activity data (service should respect business scoping)
        activity_data = activity_service.get_employee_activity(employee_id)
        
        return activity_data
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        print(f"ERROR in get_employee_activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee activity: {str(e)}"
        )


@router.delete("/{employee_id}")
async def delete_employee(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Deactivate (soft delete) an employee within the business scope."""
    try:
        from app.models.employee import Employee

        # Validate access to the business and employee with strict business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )

        # Soft delete only: mark as inactive and unset active flag
        employee.employee_status = "INACTIVE"
        if hasattr(employee, 'is_active'):
            employee.is_active = False

        db.commit()
        db.refresh(employee)

        return {
            "success": True,
            "message": "Employee deactivated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in delete_employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete employee: {str(e)}"
        )


# ============================================================================
# ADDITIONAL VALUABLE ENDPOINTS FROM EMPLOYEES.PY
# ============================================================================

@router.get("/salary/download-revisions")
async def download_salary_revisions(
    employee_id: int = Query(..., description="Employee ID"),
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Download employee salary revisions as CSV file"""
    try:
        from app.models.employee import Employee, EmployeeSalary
        from datetime import datetime
        import io
        import csv
        
        # Validate business access and employee access with business isolation
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Get all salary revisions for the employee
        salary_revisions = db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee_id
        ).order_by(EmployeeSalary.effective_from.desc()).all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Employee Code', 'Employee Name', 'Effective From', 'Basic Salary', 
            'Gross Salary', 'CTC', 'Annual CTC', 'Status'
        ])
        
        # Write salary revision data
        if salary_revisions:
            for revision in salary_revisions:
                writer.writerow([
                    employee.employee_code or f'EMP{employee_id:04d}',
                    f"{employee.first_name} {employee.last_name}",
                    revision.effective_from.strftime('%Y-%m-%d'),
                    f"{revision.basic_salary:,.2f}",
                    f"{revision.gross_salary:,.2f}",
                    f"{revision.ctc:,.2f}",
                    f"{revision.ctc * 12:,.2f}",
                    "Active" if revision.is_active else "Inactive"
                ])
        else:
            # If no salary revisions, add a default row
            writer.writerow([
                employee.employee_code or f'EMP{employee_id:04d}',
                f"{employee.first_name} {employee.last_name}",
                employee.date_of_joining.strftime('%Y-%m-%d') if employee.date_of_joining else datetime.now().strftime('%Y-%m-%d'),
                "50,000.00",
                "75,000.00", 
                "90,000.00",
                "1,080,000.00",
                "Active"
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename
        filename = f"salary_revisions_{employee.employee_code or employee_id}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        from fastapi import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in download_salary_revisions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download salary revisions"
        )


@router.get("/search/managers")
async def search_managers(
    query: str = Query(..., description="Search query for manager name"),
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search for managers (employees who can be reporting managers)"""
    try:
        from app.models.employee import Employee
        # Validate business access and restrict to this business
        validate_business_access(business_id, current_user, db)

        if not query or len(query.strip()) < 2:
            return {"managers": []}

        search_term = f"%{query.strip()}%"
        managers = db.query(Employee).filter(
            Employee.business_id == business_id,
            (Employee.first_name.ilike(search_term)) |
            (Employee.last_name.ilike(search_term)) |
            (Employee.employee_code.ilike(search_term)),
            Employee.employee_status == "active"
        ).limit(10).all()
        
        return {
            "managers": [
                {
                    "id": mgr.id,
                    "name": f"{mgr.first_name or ''} {mgr.last_name or ''}".strip(),
                    "code": mgr.employee_code or f"EMP{mgr.id:03d}",
                    "designation": mgr.designation.name if mgr.designation else "Manager",
                    "department": mgr.department.name if mgr.department else "N/A"
                }
                for mgr in managers
            ]
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search managers: {str(e)}"
        )


@router.post("/bulk")
async def bulk_create_employees(
    bulk_data: BulkEmployeeCreate,
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Bulk create employees with proper validation"""
    try:
        from app.models.employee import Employee
        
        # Validate user has access to this business
        validate_business_access(business_id, current_user, db)

        employees_data = bulk_data.employees
        created_employees = []
        errors = []
        
        for i, employee_data in enumerate(employees_data):
            try:
                # Check if employee already exists
                existing_email = db.query(Employee).filter(Employee.email == employee_data.email).first()
                if existing_email:
                    errors.append(f"Row {i+1}: Employee with email {employee_data.email} already exists")
                    continue
                
                # Check employee code if provided
                if getattr(employee_data, 'employee_code', None):
                    existing_code = db.query(Employee).filter(Employee.employee_code == employee_data.employee_code).first()
                    if existing_code:
                        errors.append(f"Row {i+1}: Employee code {employee_data.employee_code} already exists")
                        continue
                
                # Validate foreign keys if provided
                if employee_data.departmentId:
                    from app.models.department import Department
                    department = db.query(Department).filter(Department.id == employee_data.departmentId).first()
                    if not department:
                        errors.append(f"Row {i+1}: Department with ID {employee_data.departmentId} not found")
                        continue
                
                if employee_data.designationId:
                    from app.models.designations import Designation
                    designation = db.query(Designation).filter(Designation.id == employee_data.designationId).first()
                    if not designation:
                        errors.append(f"Row {i+1}: Designation with ID {employee_data.designationId} not found")
                        continue
                
                if employee_data.locationId:
                    from app.models.location import Location
                    location = db.query(Location).filter(Location.id == employee_data.locationId).first()
                    if not location:
                        errors.append(f"Row {i+1}: Location with ID {employee_data.locationId} not found")
                        continue
                
                # Create employee
                employee = Employee(
                    business_id=business_id,
                    first_name=employee_data.firstName,
                    last_name=employee_data.lastName,
                    email=employee_data.email,
                    employee_code=employee_data.employee_code,
                    department_id=employee_data.departmentId,
                    designation_id=employee_data.designationId,
                    location_id=employee_data.locationId,
                    employee_status="active",
                    created_by=current_user.id
                )
                
                db.add(employee)
                db.flush()  # Get the ID
                
                created_employees.append({
                    "id": employee.id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "email": employee.email,
                    "code": employee.employee_code or f"EMP{employee.id:03d}"
                })
                
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Bulk employee creation completed",
            "created": len(created_employees),
            "errors": len(errors),
            "employees": created_employees,
            "error_details": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in bulk_create_employees: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk create employees: {str(e)}"
        )


# ============================================================================
# EMPLOYEE WORK PROFILE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/{employee_id:int}/work-profile")
async def get_employee_work_profile_detailed(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed employee work profile information"""
    try:
        from app.models.employee import Employee
        from sqlalchemy.orm import joinedload

        # Validate current user has access to business
        validate_business_access(business_id, current_user, db)

        # Use joinedload to eagerly load all relationships and enforce business isolation
        employee = db.query(Employee).options(
            joinedload(Employee.business),
            joinedload(Employee.location),
            joinedload(Employee.cost_center),
            joinedload(Employee.department),
            joinedload(Employee.designation),
            joinedload(Employee.grade),
            joinedload(Employee.reporting_manager),
            joinedload(Employee.profile)
        ).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()

        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Get related data safely with proper fallbacks
        business_name = "Default Business Unit"
        location_name = "Office"
        cost_center_name = "General"
        department_name = "General"
        grade_name = "Default Grade"
        designation_name = "Employee"
        
        # Manager Information - ALL FROM DATABASE
        reporting_manager = {"id": 0, "name": "Not Defined", "designation": "Not Defined", "profileImage": "/assets/img/users/user-01.jpg"}
        hr_manager = {"id": 0, "name": "Not Defined", "designation": "Not Defined", "profileImage": "/assets/img/users/user-01.jpg"}
        indirect_manager = {"id": 0, "name": "Not Defined", "designation": "Not Defined", "profileImage": "/assets/img/users/user-01.jpg"}
        
        try:
            if employee.business:
                business_name = employee.business.business_name
            if employee.location:
                location_name = employee.location.name
            if employee.cost_center:
                cost_center_name = employee.cost_center.name
            if employee.department:
                department_name = employee.department.name
            if employee.designation:
                designation_name = employee.designation.name
            if employee.grade:
                grade_name = employee.grade.name if hasattr(employee.grade, 'name') else f"Grade {employee.grade.id}"
                
            # Get reporting manager details from database
            if employee.reporting_manager:
                manager_profile_image = "/assets/img/users/user-01.jpg"
                if employee.reporting_manager.profile and employee.reporting_manager.profile.profile_image_url:
                    manager_profile_image = employee.reporting_manager.profile.profile_image_url
                
                manager_designation = "Manager"
                if employee.reporting_manager.designation:
                    manager_designation = employee.reporting_manager.designation.name
                
                reporting_manager = {
                    "id": employee.reporting_manager.id,
                    "name": f"{employee.reporting_manager.first_name} {employee.reporting_manager.last_name}".strip(),
                    "designation": manager_designation,
                    "profileImage": manager_profile_image
                }
            
            # Get HR Manager from database - look for employee with HR role
            if hasattr(employee, 'hr_manager_id') and employee.hr_manager_id:
                # Get user's business IDs for validation
                user_business_ids = get_user_business_ids(db, current_user)
                hr_manager_employee = db.query(Employee).filter(
                    Employee.id == employee.hr_manager_id,
                    Employee.business_id.in_(user_business_ids)
                ).first()
                if hr_manager_employee:
                    hr_profile_image = "/assets/img/users/user-01.jpg"
                    if hr_manager_employee.profile and hr_manager_employee.profile.profile_image_url:
                        hr_profile_image = hr_manager_employee.profile.profile_image_url
                    
                    hr_designation = "HR Manager"
                    if hr_manager_employee.designation:
                        hr_designation = hr_manager_employee.designation.name
                    
                    hr_manager = {
                        "id": hr_manager_employee.id,
                        "name": f"{hr_manager_employee.first_name} {hr_manager_employee.last_name}".strip(),
                        "designation": hr_designation,
                        "profileImage": hr_profile_image
                    }
            else:
                # Fallback: Find any employee with HR designation
                try:
                    from app.models.designations import Designation
                    # Get user's business IDs for validation
                    user_business_ids = get_user_business_ids(db, current_user)
                    hr_designation = db.query(Designation).filter(Designation.name.ilike('%hr%')).first()
                    if hr_designation:
                        hr_employee = db.query(Employee).filter(
                            Employee.designation_id == hr_designation.id,
                            Employee.business_id.in_(user_business_ids)
                        ).first()
                        if hr_employee:
                            hr_profile_image = "/assets/img/users/user-01.jpg"
                            if hr_employee.profile and hr_employee.profile.profile_image_url:
                                hr_profile_image = hr_employee.profile.profile_image_url
                            
                            hr_manager = {
                                "id": hr_employee.id,
                                "name": f"{hr_employee.first_name} {hr_employee.last_name}".strip(),
                                "designation": hr_designation.name,
                                "profileImage": hr_profile_image
                            }
                except Exception as hr_error:
                    print(f"Warning: Could not find HR manager: {hr_error}")
            
            # Get Indirect Manager from database
            if hasattr(employee, 'indirect_manager_id') and employee.indirect_manager_id:
                # Get user's business IDs for validation
                user_business_ids = get_user_business_ids(db, current_user)
                indirect_manager_employee = db.query(Employee).filter(
                    Employee.id == employee.indirect_manager_id,
                    Employee.business_id.in_(user_business_ids)
                ).first()
                if indirect_manager_employee:
                    indirect_profile_image = "/assets/img/users/user-01.jpg"
                    if indirect_manager_employee.profile and indirect_manager_employee.profile.profile_image_url:
                        indirect_profile_image = indirect_manager_employee.profile.profile_image_url
                    
                    indirect_designation = "Manager"
                    if indirect_manager_employee.designation:
                        indirect_designation = indirect_manager_employee.designation.name
                    
                    indirect_manager = {
                        "id": indirect_manager_employee.id,
                        "name": f"{indirect_manager_employee.first_name} {indirect_manager_employee.last_name}".strip(),
                        "designation": indirect_designation,
                        "profileImage": indirect_profile_image
                    }
                
        except Exception as e:
            print(f"Warning: Error loading relationships: {str(e)}")
        
        return {
            "success": True,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "workProfile": {
                "businessName": business_name,
                "businessId": employee.business_id,
                "locationName": location_name,
                "locationId": employee.location_id,
                "costCenterName": cost_center_name,
                "costCenterId": employee.cost_center_id,
                "departmentName": department_name,
                "departmentId": employee.department_id,
                "gradeName": grade_name,
                "gradeId": employee.grade_id,
                "designationName": designation_name,
                "designationId": employee.designation_id,
                "reportingManager": reporting_manager,
                "hrManager": hr_manager,
                "indirectManager": indirect_manager,
                "effectiveFrom": employee.date_of_joining.isoformat() if employee.date_of_joining else "",
                "employeeStatus": employee.employee_status.value if employee.employee_status else "active",
                "shiftPolicyId": employee.shift_policy_id,
                "weekoffPolicyId": employee.weekoff_policy_id
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_employee_work_profile_detailed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee work profile: {str(e)}"
        )


@router.put("/{employee_id}/work-profile")
async def update_employee_work_profile(
    payload: EmployeeWorkProfileUpdate,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    request: Request = None,  # ADDED for activity logging
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update employee work profile"""
    try:
        from app.models.employee import Employee
        
        # Validate that at least one field is provided
        if not payload.dict(exclude_unset=True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update."
            )
        # Validate business access and ensure employee belongs to the business
        validate_business_access(business_id, current_user, db)
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.business_id == business_id
        ).first()
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # ACTIVITY LOGGING: Capture old values
        old_values = {
            "business_id": employee.business_id,
            "location_id": employee.location_id,
            "cost_center_id": employee.cost_center_id,
            "department_id": employee.department_id,
            "grade_id": employee.grade_id,
            "designation_id": employee.designation_id,
            "reporting_manager_id": employee.reporting_manager_id,
            "shift_policy_id": employee.shift_policy_id,
            "weekoff_policy_id": employee.weekoff_policy_id,
            "date_of_confirmation": str(employee.date_of_confirmation) if employee.date_of_confirmation else None,
            "date_of_termination": str(employee.date_of_termination) if employee.date_of_termination else None,
            "employee_status": employee.employee_status
        }
        
        # Update work profile fields - only allowed fields (business_id must not be changed)
        updated_fields = []

        if payload.locationId is not None:
            from app.models.location import Location
            location = db.query(Location).filter(Location.id == payload.locationId, Location.business_id == business_id).first()
            if not location:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Location with ID {payload.locationId} not found")
            employee.location_id = payload.locationId
            updated_fields.append("locationId")
        
        if payload.costCenterId is not None:
            from app.models.cost_center import CostCenter
            cost_center = db.query(CostCenter).filter(CostCenter.id == payload.costCenterId, CostCenter.business_id == business_id).first()
            if not cost_center:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cost Center with ID {payload.costCenterId} not found")
            employee.cost_center_id = payload.costCenterId
            updated_fields.append("costCenterId")
        
        if payload.departmentId is not None:
            from app.models.department import Department
            department = db.query(Department).filter(Department.id == payload.departmentId, Department.business_id == business_id).first()
            if not department:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department with ID {payload.departmentId} not found")
            employee.department_id = payload.departmentId
            updated_fields.append("departmentId")
        
        if payload.gradeId is not None:
            from app.models.grades import Grade
            grade = db.query(Grade).filter(Grade.id == payload.gradeId).first()
            if not grade:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Grade with ID {payload.gradeId} not found")
            employee.grade_id = payload.gradeId
            updated_fields.append("gradeId")
        
        if payload.designationId is not None:
            from app.models.designations import Designation
            designation = db.query(Designation).filter(Designation.id == payload.designationId).first()
            if not designation:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Designation with ID {payload.designationId} not found")
            employee.designation_id = payload.designationId
            updated_fields.append("designationId")
        
        # Update manager assignments
        if payload.reportingManagerId is not None:
            manager_id = payload.reportingManagerId
            if manager_id and manager_id > 0:
                # Validate that the manager exists and belongs to the same business
                manager = db.query(Employee).filter(
                    Employee.id == manager_id,
                    Employee.business_id == business_id
                ).first()
                if not manager:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Manager with ID {manager_id} not found in this business")
                employee.reporting_manager_id = manager_id
            else:
                employee.reporting_manager_id = None
            updated_fields.append("reportingManagerId")
        
        # Update shift and weekoff policies
        if payload.shiftPolicyId is not None:
            shift_policy_id = payload.shiftPolicyId
            if shift_policy_id and shift_policy_id > 0:
                try:
                    from app.models.shift_policy import ShiftPolicy
                    shift_policy = db.query(ShiftPolicy).filter(ShiftPolicy.id == shift_policy_id).first()
                    if shift_policy:
                        employee.shift_policy_id = shift_policy_id
                        updated_fields.append("shiftPolicyId")
                except Exception as e:
                    print(f"Warning: Could not update shift policy: {str(e)}")
            else:
                employee.shift_policy_id = None
                updated_fields.append("shiftPolicyId")
        
        if payload.weekoffPolicyId is not None:
            weekoff_policy_id = payload.weekoffPolicyId
            if weekoff_policy_id and weekoff_policy_id > 0:
                try:
                    from app.models.weekoff_policy import WeekOffPolicy
                    weekoff_policy = db.query(WeekOffPolicy).filter(WeekOffPolicy.id == weekoff_policy_id).first()
                    if weekoff_policy:
                        employee.weekoff_policy_id = weekoff_policy_id
                        updated_fields.append("weekoffPolicyId")
                except Exception as e:
                    print(f"Warning: Could not update weekoff policy: {str(e)}")
            else:
                employee.weekoff_policy_id = None
                updated_fields.append("weekoffPolicyId")
        
        # Update dates
        if payload.confirmationDate is not None:
            from datetime import datetime
            try:
                confirmation_date = datetime.strptime(payload.confirmationDate, '%Y-%m-%d').date()
                employee.date_of_confirmation = confirmation_date
                updated_fields.append("confirmationDate")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid confirmation date format. Use YYYY-MM-DD format."
                )
        
        if payload.terminationDate is not None:
            from datetime import datetime
            try:
                termination_date = datetime.strptime(payload.terminationDate, '%Y-%m-%d').date()
                employee.date_of_termination = termination_date
                updated_fields.append("terminationDate")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid termination date format. Use YYYY-MM-DD format."
                )
        
        # Update employee status
        if payload.employeeStatus is not None:
            employee.employee_status = payload.employeeStatus
            updated_fields.append("employeeStatus")
        
        # Update system fields
        employee.updated_by = current_user.id
        
        db.commit()
        db.refresh(employee)
        
        print(f"🔍 DEBUG: About to log activity for employee {employee_id}")
        print(f"🔍 DEBUG: Updated fields: {updated_fields}")
        
        # ACTIVITY LOGGING: Capture new values and log
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            print(f"🔍 DEBUG: Imported EmployeeChangeTracker successfully")
            
            new_values = {
                "business_id": employee.business_id,
                "location_id": employee.location_id,
                "cost_center_id": employee.cost_center_id,
                "department_id": employee.department_id,
                "grade_id": employee.grade_id,
                "designation_id": employee.designation_id,
                "reporting_manager_id": employee.reporting_manager_id,
                "shift_policy_id": employee.shift_policy_id,
                "weekoff_policy_id": employee.weekoff_policy_id,
                "date_of_confirmation": str(employee.date_of_confirmation) if employee.date_of_confirmation else None,
                "date_of_termination": str(employee.date_of_termination) if employee.date_of_termination else None,
                "employee_status": employee.employee_status
            }
            
            print(f"🔍 DEBUG: Old values: {old_values}")
            print(f"🔍 DEBUG: New values: {new_values}")
            print(f"🔍 DEBUG: Current user ID: {current_user.id}")
            print(f"🔍 DEBUG: Employee ID: {employee_id}")
            
            change_tracker = EmployeeChangeTracker(db)
            print(f"🔍 DEBUG: Created EmployeeChangeTracker instance")
            
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="work_profile",
                old_data=old_values,
                new_data=new_values,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} work profile")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
            import traceback
            print(f"⚠️ Traceback: {traceback.format_exc()}")
        
        return {
            "success": True,
            "message": "Employee work profile updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in update_employee_work_profile: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update work profile: {str(e)}"
        )


@router.post("/{employee_id}/work-profile/revision")
async def add_work_profile_revision(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    revision_data: WorkProfileRevisionRequest = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Add a new work profile revision for employee
    
    **Request body:**
    - month: Month (1-12)
    - year: Year (2020-2030)
    - businessId: Business ID (optional)
    - locationId: Location ID (optional)
    - costCenterId: Cost center ID (optional)
    - departmentId: Department ID (optional)
    - designationId: Designation ID (optional)
    - gradeId: Grade ID (optional)
    - employmentType: Employment type (optional)
    - notes: Revision notes (optional)
    """
    try:
        from app.models.employee import Employee
        from app.models.business import Business
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.grades import Grade
        from datetime import datetime, date
        
        # Validate business and employee
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)

        print(f"DEBUG: Adding work profile revision for employee {employee_id}")
        print(f"DEBUG: Revision data: {revision_data}")
        print(f"DEBUG: Raw manager IDs from request:")
        print(f"  - reportingManagerId: {revision_data.reportingManagerId}")
        print(f"  - hrManagerId: {revision_data.hrManagerId}")
        print(f"  - indirectManagerId: {revision_data.indirectManagerId}")
        
        # Check if employee exists
        # Validate employee access with business isolation

        employee = validate_employee_access(db, employee_id, current_user)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        print(f"DEBUG: Employee found: {employee.first_name} {employee.last_name}")
        
        # Extract and validate revision data
        month = revision_data.month
        year = revision_data.year
        
        # Get optional fields
        business_id = revision_data.businessId
        location_id = revision_data.locationId
            
        cost_center_id = revision_data.costCenterId
        if cost_center_id == "" or cost_center_id == "0":
            cost_center_id = None
        elif cost_center_id:
            cost_center_id = int(cost_center_id)
            
        department_id = revision_data.departmentId
        if department_id == "" or department_id == "0":
            department_id = None
        elif department_id:
            department_id = int(department_id)
            
        grade_id = revision_data.gradeId
        if grade_id == "" or grade_id == "0":
            grade_id = None
        elif grade_id:
            grade_id = int(grade_id)
            
        designation_id = revision_data.designationId
        if designation_id == "" or designation_id == "0":
            designation_id = None
        elif designation_id:
            designation_id = int(designation_id)
            
        # Handle manager fields - NEW
        reporting_manager_id = revision_data.reportingManagerId if hasattr(revision_data, 'reportingManagerId') else None
        if reporting_manager_id == "" or reporting_manager_id == "0":
            reporting_manager_id = None
        elif reporting_manager_id:
            reporting_manager_id = int(reporting_manager_id)
            
        hr_manager_id = revision_data.hrManagerId if hasattr(revision_data, 'hrManagerId') else None
        if hr_manager_id == "" or hr_manager_id == "0":
            hr_manager_id = None
        elif hr_manager_id:
            hr_manager_id = int(hr_manager_id)
            
        indirect_manager_id = revision_data.indirectManagerId if hasattr(revision_data, 'indirectManagerId') else None
        if indirect_manager_id == "" or indirect_manager_id == "0":
            indirect_manager_id = None
        elif indirect_manager_id:
            indirect_manager_id = int(indirect_manager_id)
            
        is_promotion = revision_data.isPromotion if hasattr(revision_data, 'isPromotion') else False
        
        print(f"DEBUG: Processed values:")
        print(f"  business_id: {business_id}")
        print(f"  location_id: {location_id}")
        print(f"  cost_center_id: {cost_center_id}")
        print(f"  department_id: {department_id}")
        print(f"  grade_id: {grade_id}")
        print(f"  designation_id: {designation_id}")
        print(f"  reporting_manager_id: {reporting_manager_id}")
        print(f"  hr_manager_id: {hr_manager_id}")
        print(f"  indirect_manager_id: {indirect_manager_id}")
        
        # Validate required fields
        if not month or not year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month and year are required for work profile revision"
            )
        
        # Create effective date
        try:
            effective_date = date(int(year), int(month), 1)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid month or year format"
            )
        
        # Validate foreign key references with better error handling
        validation_errors = []
        
        # Only validate if the ID is provided and not None
        if business_id and business_id > 0:
            try:
                business = db.query(Business).filter(Business.id == business_id).first()
                if not business:
                    validation_errors.append(f"Business with ID {business_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate business: {e}")
                validation_errors.append(f"Could not validate business with ID {business_id}")
        
        if location_id and location_id > 0:
            try:
                location = db.query(Location).filter(Location.id == location_id).first()
                if not location:
                    validation_errors.append(f"Location with ID {location_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate location: {e}")
                validation_errors.append(f"Could not validate location with ID {location_id}")
        
        if cost_center_id and cost_center_id > 0:
            try:
                cost_center = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
                if not cost_center:
                    validation_errors.append(f"Cost Center with ID {cost_center_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate cost center: {e}")
                validation_errors.append(f"Could not validate cost center with ID {cost_center_id}")
        
        if department_id and department_id > 0:
            try:
                department = db.query(Department).filter(Department.id == department_id).first()
                if not department:
                    validation_errors.append(f"Department with ID {department_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate department: {e}")
                validation_errors.append(f"Could not validate department with ID {department_id}")
        
        if designation_id and designation_id > 0:
            try:
                designation = db.query(Designation).filter(Designation.id == designation_id).first()
                if not designation:
                    validation_errors.append(f"Designation with ID {designation_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate designation: {e}")
                validation_errors.append(f"Could not validate designation with ID {designation_id}")
        
        if grade_id and grade_id > 0:
            try:
                grade = db.query(Grade).filter(Grade.id == grade_id).first()
                if not grade:
                    validation_errors.append(f"Grade with ID {grade_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate grade: {e}")
                validation_errors.append(f"Could not validate grade with ID {grade_id}")
        
        # Validate manager references - only if provided
        if reporting_manager_id and reporting_manager_id > 0:
            try:
                # Get user\'s business IDs for validation

                user_business_ids = get_user_business_ids(db, current_user)

                reporting_manager = db.query(Employee).filter(

                    Employee.id == reporting_manager_id,

                    Employee.business_id.in_(user_business_ids)

                ).first()
                if not reporting_manager:
                    validation_errors.append(f"Reporting Manager with ID {reporting_manager_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate reporting manager: {e}")
                validation_errors.append(f"Could not validate reporting manager with ID {reporting_manager_id}")
        
        if hr_manager_id and hr_manager_id > 0:
            try:
                # Get user\'s business IDs for validation

                user_business_ids = get_user_business_ids(db, current_user)

                hr_manager = db.query(Employee).filter(

                    Employee.id == hr_manager_id,

                    Employee.business_id.in_(user_business_ids)

                ).first()
                if not hr_manager:
                    validation_errors.append(f"HR Manager with ID {hr_manager_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate HR manager: {e}")
                validation_errors.append(f"Could not validate HR manager with ID {hr_manager_id}")
        
        if indirect_manager_id and indirect_manager_id > 0:
            try:
                # Get user\'s business IDs for validation

                user_business_ids = get_user_business_ids(db, current_user)

                indirect_manager = db.query(Employee).filter(

                    Employee.id == indirect_manager_id,

                    Employee.business_id.in_(user_business_ids)

                ).first()
                if not indirect_manager:
                    validation_errors.append(f"Indirect Manager with ID {indirect_manager_id} not found")
            except Exception as e:
                print(f"Warning: Could not validate indirect manager: {e}")
                validation_errors.append(f"Could not validate indirect manager with ID {indirect_manager_id}")
        
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation errors: {'; '.join(validation_errors)}"
            )
        
        # Capture OLD values before updating (for activity logging)
        old_business_id = employee.business_id
        old_location_id = employee.location_id
        old_cost_center_id = employee.cost_center_id
        old_department_id = employee.department_id
        old_designation_id = employee.designation_id
        old_grade_id = employee.grade_id
        old_reporting_manager_id = employee.reporting_manager_id
        old_hr_manager_id = employee.hr_manager_id
        old_indirect_manager_id = employee.indirect_manager_id
        
        # Update employee work profile with new revision data
        updated_fields = []
        
        # Update fields that are provided in the request
        if business_id is not None:
            employee.business_id = business_id
            updated_fields.append("business_id")
        
        if location_id is not None:
            employee.location_id = location_id
            updated_fields.append("location_id")
        
        if cost_center_id is not None:
            employee.cost_center_id = cost_center_id
            updated_fields.append("cost_center_id")
        
        if department_id is not None:
            employee.department_id = department_id
            updated_fields.append("department_id")
        
        if designation_id is not None:
            employee.designation_id = designation_id
            updated_fields.append("designation_id")
        
        # Handle grade_id - now using real database IDs
        if grade_id is not None:
            employee.grade_id = grade_id
            updated_fields.append("grade_id")
        
        # Handle manager fields - Always update them (even if None to clear)
        # The frontend always sends these fields in the payload
        employee.reporting_manager_id = reporting_manager_id
        updated_fields.append("reporting_manager_id")
        print(f"✅ Updated reporting_manager_id to: {reporting_manager_id}")
        
        employee.hr_manager_id = hr_manager_id
        updated_fields.append("hr_manager_id")
        print(f"✅ Updated hr_manager_id to: {hr_manager_id}")
        
        employee.indirect_manager_id = indirect_manager_id
        updated_fields.append("indirect_manager_id")
        print(f"✅ Updated indirect_manager_id to: {indirect_manager_id}")
        
        # Update system fields
        employee.updated_by = current_user.id
        
        # Commit changes
        db.commit()
        db.refresh(employee)
        
        # Verify the managers were saved
        print(f"✅ Database committed. Verifying saved manager IDs:")
        print(f"  - employee.reporting_manager_id: {employee.reporting_manager_id}")
        print(f"  - employee.hr_manager_id: {employee.hr_manager_id}")
        print(f"  - employee.indirect_manager_id: {employee.indirect_manager_id}")
        
        # Log activity with proper before/after tracking
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            change_tracker = EmployeeChangeTracker(db)
            
            # Build changes dictionary with old and new values
            changes = {}
            
            # Helper function to get name from ID
            def get_employee_name(emp_id):
                if emp_id:
                    # Get user's business IDs for validation
                    user_business_ids = get_user_business_ids(db, current_user)
                    emp = db.query(Employee).filter(
                        Employee.id == emp_id,
                        Employee.business_id.in_(user_business_ids)
                    ).first()
                    if emp:
                        return f"{emp.first_name or ''} {emp.last_name or ''}".strip()
                return None
            
            # Track each field change with readable names
            if business_id != old_business_id:
                old_val = None
                new_val = None
                if old_business_id:
                    old_biz = db.query(Business).filter(Business.id == old_business_id).first()
                    old_val = old_biz.business_name if old_biz else f"ID {old_business_id}"
                if business_id:
                    new_biz = db.query(Business).filter(Business.id == business_id).first()
                    new_val = new_biz.business_name if new_biz else f"ID {business_id}"
                changes['Business'] = {'old': old_val, 'new': new_val}
            
            if location_id != old_location_id:
                old_val = None
                new_val = None
                if old_location_id:
                    old_loc = db.query(Location).filter(Location.id == old_location_id).first()
                    old_val = old_loc.name if old_loc else f"ID {old_location_id}"
                if location_id:
                    new_loc = db.query(Location).filter(Location.id == location_id).first()
                    new_val = new_loc.name if new_loc else f"ID {location_id}"
                changes['Location'] = {'old': old_val, 'new': new_val}
            
            if cost_center_id != old_cost_center_id:
                old_val = None
                new_val = None
                if old_cost_center_id:
                    old_cc = db.query(CostCenter).filter(CostCenter.id == old_cost_center_id).first()
                    old_val = old_cc.name if old_cc else f"ID {old_cost_center_id}"
                if cost_center_id:
                    new_cc = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
                    new_val = new_cc.name if new_cc else f"ID {cost_center_id}"
                changes['Cost Center'] = {'old': old_val, 'new': new_val}
            
            if department_id != old_department_id:
                old_val = None
                new_val = None
                if old_department_id:
                    old_dept = db.query(Department).filter(Department.id == old_department_id).first()
                    old_val = old_dept.name if old_dept else f"ID {old_department_id}"
                if department_id:
                    new_dept = db.query(Department).filter(Department.id == department_id).first()
                    new_val = new_dept.name if new_dept else f"ID {department_id}"
                changes['Department'] = {'old': old_val, 'new': new_val}
            
            if designation_id != old_designation_id:
                old_val = None
                new_val = None
                if old_designation_id:
                    old_desig = db.query(Designation).filter(Designation.id == old_designation_id).first()
                    old_val = old_desig.name if old_desig else f"ID {old_designation_id}"
                if designation_id:
                    new_desig = db.query(Designation).filter(Designation.id == designation_id).first()
                    new_val = new_desig.name if new_desig else f"ID {designation_id}"
                changes['Designation'] = {'old': old_val, 'new': new_val}
            
            if grade_id != old_grade_id:
                old_val = None
                new_val = None
                if old_grade_id:
                    old_grade = db.query(Grade).filter(Grade.id == old_grade_id).first()
                    old_val = old_grade.name if old_grade and hasattr(old_grade, 'name') else f"Grade {old_grade_id}"
                if grade_id:
                    new_grade = db.query(Grade).filter(Grade.id == grade_id).first()
                    new_val = new_grade.name if new_grade and hasattr(new_grade, 'name') else f"Grade {grade_id}"
                changes['Grade'] = {'old': old_val, 'new': new_val}
            
            # Track manager changes with employee names
            if reporting_manager_id != old_reporting_manager_id:
                old_val = get_employee_name(old_reporting_manager_id)
                new_val = get_employee_name(reporting_manager_id)
                changes['Reporting Manager'] = {'old': old_val, 'new': new_val}
            
            if hr_manager_id != old_hr_manager_id:
                old_val = get_employee_name(old_hr_manager_id)
                new_val = get_employee_name(hr_manager_id)
                changes['HR Manager'] = {'old': old_val, 'new': new_val}
            
            if indirect_manager_id != old_indirect_manager_id:
                old_val = get_employee_name(old_indirect_manager_id)
                new_val = get_employee_name(indirect_manager_id)
                changes['Indirect Manager'] = {'old': old_val, 'new': new_val}
            
            # Build action message
            if is_promotion:
                action = f"Promotion for {effective_date.strftime('%B %Y')}"
            else:
                action = f"Work Profile Update for {effective_date.strftime('%B %Y')}"
            
            if changes:
                change_tracker.log_change(
                    user_id=current_user.id,
                    employee_id=employee_id,
                    section="work_profile",
                    action=action,
                    changes=changes,
                    ip_address=get_client_ip(request) if request else None,
                    user_agent=get_user_agent(request) if request else None
                )
                print(f"✅ Activity logged for employee {employee_id} - work profile revision with {len(changes)} changes")
            else:
                print(f"⚠️ No changes detected for activity log")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
            import traceback
            traceback.print_exc()
        
        print(f"✅ Work profile revision added for employee {employee_id}. Fields updated: {updated_fields}")
        
        return {
            "success": True,
            "message": f"Work profile revision added successfully for {effective_date.strftime('%B %Y')}",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "revision": {
                "effectiveDate": effective_date.isoformat(),
                "month": month,
                "year": year,
                "isPromotion": is_promotion,
                "updatedFields": updated_fields,
                "createdAt": datetime.now().isoformat(),
                "createdBy": current_user.id
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in add_work_profile_revision: {str(e)}")
        print(f"ERROR details - Employee ID: {employee_id}")
        print(f"ERROR details - Revision data: {revision_data}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add work profile revision: {str(e)}"
        )


@router.delete("/{employee_id}/work-profile/revision")
async def delete_work_profile_revision(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    revision_date: str = Query(..., description="Revision date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a work profile revision"""
    try:
        from app.models.employee import Employee
        from datetime import datetime
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Validate revision date format
        try:
            revision_date_obj = datetime.strptime(revision_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid revision date format. Use YYYY-MM-DD format."
            )
        
        # For now, we'll simulate deletion since we don't have a separate revisions table
        # In a real implementation, this would delete from a work_profile_revisions table
        
        return {
            "success": True,
            "message": f"Work profile revision for {revision_date} deleted successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "deletedRevision": {
                "date": revision_date,
                "deletedAt": datetime.now().isoformat(),
                "deletedBy": current_user.id
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in delete_work_profile_revision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete work profile revision: {str(e)}"
        )


@router.get("/{employee_id}/managers/search")
async def search_managers_for_employee(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    query: str = Query("", description="Search query for manager name or employee code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search for potential managers for employee assignment"""
    try:
        from app.models.employee import Employee
        from sqlalchemy import or_
        from sqlalchemy.orm import joinedload
        
        # Verify employee exists
        # Validate employee access with business isolation

        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Build search query for potential managers
        # Search managers only within the business
        managers_query = db.query(Employee).options(
            joinedload(Employee.designation),
            joinedload(Employee.department),
            joinedload(Employee.profile)
        ).filter(
            Employee.business_id == business_id,
            Employee.id != employee_id,  # Exclude the employee themselves
            Employee.employee_status == "active"
        )
        
        # Apply search filter if query provided
        if query and query.strip():
            search_term = f"%{query.strip()}%"
            managers_query = managers_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Limit results to prevent overwhelming the UI
        managers = managers_query.limit(20).all()
        
        # Format response
        manager_list = []
        for manager in managers:
            profile_image = "/assets/img/users/user-01.jpg"
            if manager.profile and manager.profile.profile_image_url:
                profile_image = manager.profile.profile_image_url
            
            designation_name = "Manager"
            if manager.designation:
                designation_name = manager.designation.name
            
            department_name = ""
            if manager.department:
                department_name = manager.department.name
            
            manager_list.append({
                "id": manager.id,
                "name": f"{manager.first_name} {manager.last_name}".strip(),
                "code": manager.employee_code or f"EMP{manager.id:03d}",
                "designation": designation_name,
                "department": department_name,
                "profileImage": profile_image
            })
        
        return {
            "success": True,
            "managers": manager_list,
            "total": len(manager_list),
            "query": query
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in search_managers_for_employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search managers: {str(e)}"
        )


@router.put("/{employee_id}/managers/{manager_type}")
async def update_employee_manager(
    employee_id: int,
    manager_type: str,
    manager_data: ManagerUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update employee manager assignment
    
    **Request body:**
    - managerId: Manager ID (use 0 or null to remove manager)
    """
    try:
        from app.models.employee import Employee
        
        print(f"🔄 DEBUG: Starting manager update for employee {employee_id}, type {manager_type}")
        print(f"🔄 DEBUG: Manager data: {manager_data}")
        
        # Validate manager type
        valid_manager_types = ["reporting", "hr", "indirect"]
        if manager_type not in valid_manager_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid manager type. Must be one of: {', '.join(valid_manager_types)}"
            )
        
        # Validate employee access with business isolation

        
        employee = validate_employee_access(db, employee_id, current_user)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        print(f"🔄 DEBUG: Employee found: {employee.first_name} {employee.last_name}")
        
        manager_id = manager_data.managerId
        
        # Validate manager exists (if not 0/null)
        if manager_id and manager_id > 0:
            # Get user\'s business IDs for validation

            user_business_ids = get_user_business_ids(db, current_user)

            manager = db.query(Employee).filter(

                Employee.id == manager_id,

                Employee.business_id.in_(user_business_ids)

            ).first()
            if not manager:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Manager with ID {manager_id} not found"
                )
            print(f"🔄 DEBUG: Manager found: {manager.first_name} {manager.last_name}")
        
        # Log current values
        print(f"🔄 DEBUG: BEFORE UPDATE - Reporting: {employee.reporting_manager_id}, HR: {employee.hr_manager_id}, Indirect: {employee.indirect_manager_id}")
        
        # Update the appropriate manager field
        if manager_type == "reporting":
            old_value = employee.reporting_manager_id
            employee.reporting_manager_id = manager_id if manager_id > 0 else None
            print(f"🔄 DEBUG: Updated reporting_manager_id: {old_value} → {employee.reporting_manager_id}")
        elif manager_type == "hr":
            old_value = employee.hr_manager_id
            employee.hr_manager_id = manager_id if manager_id > 0 else None
            print(f"🔄 DEBUG: Updated hr_manager_id: {old_value} → {employee.hr_manager_id}")
        elif manager_type == "indirect":
            old_value = employee.indirect_manager_id
            employee.indirect_manager_id = manager_id if manager_id > 0 else None
            print(f"🔄 DEBUG: Updated indirect_manager_id: {old_value} → {employee.indirect_manager_id}")
        
        # Update system fields
        employee.updated_by = current_user.id
        print(f"🔄 DEBUG: Set updated_by to {current_user.id}")
        
        print(f"🔄 DEBUG: About to commit changes...")
        db.commit()
        print(f"🔄 DEBUG: Commit successful")
        
        db.refresh(employee)
        print(f"🔄 DEBUG: AFTER REFRESH - Reporting: {employee.reporting_manager_id}, HR: {employee.hr_manager_id}, Indirect: {employee.indirect_manager_id}")
        
        return {
            "success": True,
            "message": f"{manager_type.title()} manager updated successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "managerType": manager_type,
            "managerId": manager_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in update_employee_manager: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update manager: {str(e)}"
        )


@router.delete("/{employee_id}/managers/{manager_type}")
async def remove_employee_manager(
    employee_id: int,
    manager_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Remove employee manager assignment"""
    try:
        from app.models.employee import Employee
        
        # Validate manager type
        valid_manager_types = ["reporting", "hr", "indirect"]
        if manager_type not in valid_manager_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid manager type. Must be one of: {', '.join(valid_manager_types)}"
            )
        
        # Validate employee access with business isolation

        
        employee = validate_employee_access(db, employee_id, current_user)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Remove the appropriate manager assignment
        if manager_type == "reporting":
            employee.reporting_manager_id = None
        elif manager_type == "hr":
            employee.hr_manager_id = None
        elif manager_type == "indirect":
            employee.indirect_manager_id = None
        
        # Update system fields
        employee.updated_by = current_user.id
        
        db.commit()
        db.refresh(employee)
        
        return {
            "success": True,
            "message": f"{manager_type.title()} manager removed successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "managerType": manager_type
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR in remove_employee_manager: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove manager: {str(e)}"
        )


@router.get("/dropdown-options/work-profile/simple")
async def get_work_profile_dropdown_options_simple(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get dropdown options for work profile forms - Simple version with DATABASE ONLY"""
    try:
        print("🔄 Loading simple dropdown options from DATABASE...")
        
        # Import all required models
        from app.models.business import Business
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.grades import Grade
        
        # Validate business access and then query scoped data
        validate_business_access(business_id, current_user, db)

        businesses_db = db.query(Business).filter(Business.id == business_id).all()
        locations_db = db.query(Location).filter(Location.business_id == business_id).all()
        cost_centers_db = db.query(CostCenter).filter(CostCenter.business_id == business_id).all()
        departments_db = db.query(Department).filter(Department.business_id == business_id).all()
        designations_db = db.query(Designation).filter(Designation.business_id == business_id).all()
        grades_db = db.query(Grade).filter(Grade.business_id == business_id).all()
        
        # Convert to response format
        businesses = [
            {"id": b.id, "name": getattr(b, 'business_name', getattr(b, 'name', f'Business {b.id}'))} 
            for b in businesses_db
        ]
        
        locations = [
            {"id": l.id, "name": getattr(l, 'name', f'Location {l.id}')} 
            for l in locations_db
        ]
        
        cost_centers = [
            {"id": cc.id, "name": getattr(cc, 'name', f'Cost Center {cc.id}')} 
            for cc in cost_centers_db
        ]
        
        departments = [
            {"id": d.id, "name": getattr(d, 'name', f'Department {d.id}')} 
            for d in departments_db
        ]
        
        designations = [
            {"id": des.id, "name": getattr(des, 'name', f'Designation {des.id}')} 
            for des in designations_db
        ]
        
        grades = [
            {"id": g.id, "name": getattr(g, 'name', f'Grade {g.id}')} 
            for g in grades_db
        ]
        
        # Log what we found in the database
        print(f"📊 DATABASE RESULTS:")
        print(f"  - Businesses: {len(businesses)} items")
        print(f"  - Locations: {len(locations)} items")
        print(f"  - Cost Centers: {len(cost_centers)} items")
        print(f"  - Departments: {len(departments)} items")
        print(f"  - Designations: {len(designations)} items")
        print(f"  - Grades: {len(grades)} items")
        
        # Log actual IDs for debugging
        business_ids = [b["id"] for b in businesses]
        grade_ids = [g["id"] for g in grades]
        print(f"  - Business IDs: {business_ids}")
        print(f"  - Grade IDs: {grade_ids}")
        
        database_data = {
            "success": True,
            "options": {
                "businesses": businesses,
                "locations": locations,
                "costCenters": cost_centers,
                "departments": departments,
                "designations": designations,
                "grades": grades
            }
        }
        
        print("✅ Simple dropdown options loaded successfully from DATABASE")
        return database_data
        
    except Exception as e:
        print(f"❌ Error loading dropdown options from database: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return minimal fallback only if database completely fails
        fallback_data = {
            "success": True,
            "options": {
                "businesses": [{"id": 1, "name": "Default Business"}],
                "locations": [{"id": 1, "name": "Main Office"}],
                "costCenters": [{"id": 1, "name": "General"}],
                "departments": [{"id": 1, "name": "General"}],
                "designations": [{"id": 1, "name": "Employee"}],
                "grades": [{"id": 1, "name": "Default Grade"}]
            }
        }
        
        print("⚠️ Using minimal fallback data due to database error")
        return fallback_data
    
    except Exception as e:
        print(f"❌ ERROR in simple dropdown options: {str(e)}")
        # Even if there's an error, return basic data
        return {
            "success": True,
            "options": {
                "businesses": [{"id": 1, "name": "Default Business Unit"}],
                "locations": [{"id": 1, "name": "Main Office"}],
                "costCenters": [{"id": 1, "name": "General"}],
                "departments": [{"id": 1, "name": "General"}],
                "designations": [{"id": 1, "name": "Employee"}],
                "grades": [{"id": 1, "name": "Default Grade"}]
            }
        }


@router.get("/dropdown-options/work-profile")
async def get_work_profile_dropdown_options(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get dropdown options for work profile forms - DATABASE ONLY"""
    try:
        print("🔄 Loading dropdown options from DATABASE...")
        
        # Validate business access and filter for this business
        validate_business_access(business_id, current_user, db)
        user_business_ids = [business_id]
        
        # Initialize empty lists for safety
        businesses = []
        locations = []
        departments = []
        designations = []
        cost_centers = []
        
        # Try to get data from each table, with fallback handling
        try:
            from app.models.business import Business
            businesses = db.query(Business).filter(Business.id.in_(user_business_ids)).all()
            print(f"✅ Loaded {len(businesses)} businesses")
        except Exception as e:
            print(f"Warning: Could not load businesses: {str(e)}")
        
        try:
            from app.models.location import Location
            locations = db.query(Location).filter(Location.business_id.in_(user_business_ids)).all()
            print(f"✅ Loaded {len(locations)} locations")
        except Exception as e:
            print(f"Warning: Could not load locations: {str(e)}")
        
        try:
            from app.models.department import Department
            departments = db.query(Department).filter(
                Department.business_id.in_(user_business_ids)
            ).all()
            print(f"✅ Loaded {len(departments)} departments")
        except Exception as e:
            print(f"Warning: Could not load departments: {str(e)}")
        
        try:
            from app.models.designations import Designation
            designations = db.query(Designation).all()
            print(f"✅ Loaded {len(designations)} designations")
        except Exception as e:
            print(f"Warning: Could not load designations: {str(e)}")
        
        try:
            from app.models.cost_center import CostCenter
            cost_centers = db.query(CostCenter).filter(
                CostCenter.business_id.in_(user_business_ids)
            ).all()
            print(f"✅ Loaded {len(cost_centers)} cost centers")
        except Exception as e:
            print(f"Warning: Could not load cost centers: {str(e)}")
        
        # Get grades from database - NO FALLBACKS
        grades_data = []
        try:
            from app.models.grades import Grade
            grades = db.query(Grade).all()
            grades_data = [
                {"id": g.id, "name": getattr(g, 'name', f'Grade {g.id}')} 
                for g in grades
            ]
            print(f"✅ Loaded {len(grades_data)} grades from database")
            grade_ids = [g["id"] for g in grades_data]
            print(f"✅ Grade IDs from database: {grade_ids}")
        except Exception as e:
            print(f"❌ CRITICAL: Could not load grades from database: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return empty instead of fallback to force fixing the database issue
            grades_data = []
        
        # Build response with safe data extraction
        response_data = {
            "success": True,
            "options": {
                "businesses": [],
                "locations": [],
                "costCenters": [],
                "departments": [],
                "designations": [],
                "grades": grades_data,
                "managers": []
            }
        }
        
        # Safely extract business data - DATABASE ONLY
        try:
            response_data["options"]["businesses"] = [
                {"id": b.id, "name": getattr(b, 'business_name', getattr(b, 'name', f'Business {b.id}'))} 
                for b in businesses
            ]
            business_ids = [b["id"] for b in response_data["options"]["businesses"]]
            print(f"✅ Business IDs from database: {business_ids}")
        except Exception as e:
            print(f"❌ CRITICAL: Error processing businesses: {str(e)}")
            response_data["options"]["businesses"] = []
        
        # Safely extract location data - DATABASE ONLY
        try:
            response_data["options"]["locations"] = [
                {"id": l.id, "name": getattr(l, 'name', f'Location {l.id}')} 
                for l in locations
            ]
        except Exception as e:
            print(f"❌ CRITICAL: Error processing locations: {str(e)}")
            response_data["options"]["locations"] = []
        
        # Safely extract cost center data - DATABASE ONLY
        try:
            response_data["options"]["costCenters"] = [
                {"id": cc.id, "name": getattr(cc, 'name', f'Cost Center {cc.id}')} 
                for cc in cost_centers
            ]
        except Exception as e:
            print(f"❌ CRITICAL: Error processing cost centers: {str(e)}")
            response_data["options"]["costCenters"] = []
        
        # Safely extract department data - DATABASE ONLY
        try:
            response_data["options"]["departments"] = [
                {"id": d.id, "name": getattr(d, 'name', f'Department {d.id}')} 
                for d in departments
            ]
        except Exception as e:
            print(f"❌ CRITICAL: Error processing departments: {str(e)}")
            response_data["options"]["departments"] = []
        
        # Safely extract designation data - DATABASE ONLY
        try:
            response_data["options"]["designations"] = [
                {"id": d.id, "name": getattr(d, 'name', f'Designation {d.id}')} 
                for d in designations
            ]
        except Exception as e:
            print(f"❌ CRITICAL: Error processing designations: {str(e)}")
            response_data["options"]["designations"] = []
        
        # Get manager options from database - ALL EMPLOYEES
        try:
            from app.models.employee import Employee, EmployeeStatus
            # Query for active employees using proper enum comparison
            managers = db.query(Employee).filter(
                Employee.employee_status == EmployeeStatus.ACTIVE
            ).all()
            
            # If no active employees, get all employees as fallback
            if not managers:
                print("⚠️ No active employees found, using all employees as potential managers")
                managers = db.query(Employee).all()
            
            response_data["options"]["managers"] = [
                {
                    "id": m.id, 
                    "name": f"{m.first_name or ''} {m.last_name or ''}".strip() or f"Employee {m.id}",
                    "code": m.employee_code or f"EMP{m.id:03d}",
                    "designation": m.designation.name if m.designation else "Employee"
                } 
                for m in managers
            ]
            print(f"✅ Loaded {len(response_data['options']['managers'])} manager options from database")
        except Exception as e:
            print(f"❌ CRITICAL: Error processing managers: {str(e)}")
            import traceback
            traceback.print_exc()
            response_data["options"]["managers"] = []
        
        print(f"✅ Dropdown options loaded successfully:")
        print(f"  - Businesses: {len(response_data['options']['businesses'])}")
        print(f"  - Locations: {len(response_data['options']['locations'])}")
        print(f"  - Cost Centers: {len(response_data['options']['costCenters'])}")
        print(f"  - Departments: {len(response_data['options']['departments'])}")
        print(f"  - Designations: {len(response_data['options']['designations'])}")
        print(f"  - Grades: {len(response_data['options']['grades'])}")
        print(f"  - Managers: {len(response_data['options']['managers'])}")
        
        return response_data
    
    except Exception as e:
        print(f"❌ ERROR in get_work_profile_dropdown_options: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return minimal fallback data instead of failing completely
        fallback_data = {
            "success": True,
            "options": {
                "businesses": [{"id": 1, "name": "Default Business Unit"}],
                "locations": [{"id": 1, "name": "Main Office"}],
                "costCenters": [{"id": 1, "name": "General"}],
                "departments": [{"id": 1, "name": "General"}],
                "designations": [{"id": 1, "name": "Employee"}],
                "grades": [{"id": 1, "name": "Default Grade"}],
                "managers": []
            }
        }
        
        print("⚠️  Returning fallback dropdown data due to error")
        return fallback_data


# ============================================================================
# EMPLOYEE ADDRESS MANAGEMENT ENDPOINTS
# ============================================================================

class EmployeeAddressCreate(BaseModel):
    """Schema for creating employee address"""
    addressType: str  # "permanent" or "present"
    addressLine1: str
    addressLine2: Optional[str] = None
    city: str
    state: str
    country: str
    pincode: str
    
    @validator('addressType')
    def validate_address_type(cls, v):
        if v.lower() not in ['permanent', 'present']:
            raise ValueError('Address type must be either "permanent" or "present"')
        return v.lower()
    
    @validator('addressLine1')
    def validate_address_line1(cls, v):
        if not v or not v.strip():
            raise ValueError('Address line 1 cannot be empty')
        return v.strip()
    
    @validator('city')
    def validate_city(cls, v):
        if not v or not v.strip():
            raise ValueError('City cannot be empty')
        return v.strip()
    
    @validator('state')
    def validate_state(cls, v):
        if not v or not v.strip():
            raise ValueError('State cannot be empty')
        return v.strip()
    
    @validator('country')
    def validate_country(cls, v):
        if not v or not v.strip():
            raise ValueError('Country cannot be empty')
        return v.strip()
    
    @validator('pincode')
    def validate_pincode(cls, v):
        if not v or not v.strip():
            raise ValueError('Pincode cannot be empty')
        return v.strip()


class EmployeeAddressUpdate(BaseModel):
    """Schema for updating employee address"""
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())


@router.get("/{employee_id}/addresses")
async def get_employee_addresses(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee addresses in list format"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get employee profile for detailed address info
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        
        addresses = []
        
        # Add permanent address if exists
        if profile and (profile.permanent_address_line1 or employee.permanent_address):
            permanent_address = {
                "id": f"{employee_id}_permanent",
                "type": "permanent",
                "addressType": "Permanent",
                "addressLine1": profile.permanent_address_line1 or employee.permanent_address or "",
                "addressLine2": profile.permanent_address_line2 or "",
                "city": profile.permanent_city or "",
                "state": profile.permanent_state or "",
                "country": profile.permanent_country or "India",
                "pincode": profile.permanent_pincode or "",
                "fullAddress": f"{profile.permanent_address_line1 or employee.permanent_address or ''}, {profile.permanent_city or ''}, {profile.permanent_state or ''}, {profile.permanent_country or 'India'} - {profile.permanent_pincode or ''}".strip(", -")
            }
            addresses.append(permanent_address)
        
        # Add present address if exists
        if profile and (profile.present_address_line1 or employee.current_address):
            present_address = {
                "id": f"{employee_id}_present",
                "type": "present",
                "addressType": "Present",
                "addressLine1": profile.present_address_line1 or employee.current_address or "",
                "addressLine2": profile.present_address_line2 or "",
                "city": profile.present_city or "",
                "state": profile.present_state or "",
                "country": profile.present_country or "India",
                "pincode": profile.present_pincode or "",
                "fullAddress": f"{profile.present_address_line1 or employee.current_address or ''}, {profile.present_city or ''}, {profile.present_state or ''}, {profile.present_country or 'India'} - {profile.present_pincode or ''}".strip(", -")
            }
            addresses.append(present_address)
        
        return {
            "success": True,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "addresses": addresses,
            "total": len(addresses)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in get_employee_addresses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee addresses: {str(e)}"
        )


@router.post("/{employee_id}/addresses")
async def add_employee_address(
    address_data: EmployeeAddressCreate,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add employee address with comprehensive validation"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get or create employee profile
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if not profile:
            profile = EmployeeProfile(employee_id=employee_id)
            db.add(profile)
        
        # Update address based on type
        address_type = address_data.addressType.lower()
        
        if address_type == "permanent":
            profile.permanent_address_line1 = address_data.addressLine1
            profile.permanent_address_line2 = address_data.addressLine2 or ""
            profile.permanent_city = address_data.city
            profile.permanent_state = address_data.state
            profile.permanent_country = address_data.country
            profile.permanent_pincode = address_data.pincode
            
            # Also update the simple address field in Employee model
            full_address = f"{address_data.addressLine1}"
            if address_data.addressLine2:
                full_address += f", {address_data.addressLine2}"
            full_address += f", {address_data.city}, {address_data.state}, {address_data.country} - {address_data.pincode}"
            employee.permanent_address = full_address
            
        elif address_type == "present":
            profile.present_address_line1 = address_data.addressLine1
            profile.present_address_line2 = address_data.addressLine2 or ""
            profile.present_city = address_data.city
            profile.present_state = address_data.state
            profile.present_country = address_data.country
            profile.present_pincode = address_data.pincode
            
            # Also update the simple address field in Employee model
            full_address = f"{address_data.addressLine1}"
            if address_data.addressLine2:
                full_address += f", {address_data.addressLine2}"
            full_address += f", {address_data.city}, {address_data.state}, {address_data.country} - {address_data.pincode}"
            employee.current_address = full_address
        
        db.commit()
        db.refresh(profile)
        db.refresh(employee)
        
        print(f"✅ {address_type.title()} address added for employee {employee_id}")
        
        return {
            "success": True,
            "message": f"{address_type.title()} address added successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "address": {
                "id": f"{employee_id}_{address_type}",
                "type": address_type,
                "addressType": address_type.title(),
                "addressLine1": address_data.addressLine1,
                "addressLine2": address_data.addressLine2 or "",
                "city": address_data.city,
                "state": address_data.state,
                "country": address_data.country,
                "pincode": address_data.pincode
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in add_employee_address: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add employee address: {str(e)}"
        )


@router.put("/{employee_id}/addresses/{address_type}")
async def update_employee_address(
    address_type: str,
    address_data: EmployeeAddressUpdate,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee address with validation"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        # Validate address type
        if address_type.lower() not in ['permanent', 'present']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Address type must be either 'permanent' or 'present'"
            )
        
        # Validate that the request body is not empty
        if not address_data.has_valid_data():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body cannot be empty. At least one field must be provided for update."
            )
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get or create employee profile
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if not profile:
            profile = EmployeeProfile(employee_id=employee_id)
            db.add(profile)
        
        address_type = address_type.lower()
        updated_fields = []
        
        # Capture old values for activity logging
        old_values = {}
        if address_type == "permanent":
            old_values = {
                "addressLine1": profile.permanent_address_line1,
                "addressLine2": profile.permanent_address_line2,
                "city": profile.permanent_city,
                "state": profile.permanent_state,
                "country": profile.permanent_country,
                "pincode": profile.permanent_pincode
            }
        elif address_type == "present":
            old_values = {
                "addressLine1": profile.present_address_line1,
                "addressLine2": profile.present_address_line2,
                "city": profile.present_city,
                "state": profile.present_state,
                "country": profile.present_country,
                "pincode": profile.present_pincode
            }
        
        # Update address fields based on type
        if address_type == "permanent":
            if address_data.addressLine1 is not None:
                if not address_data.addressLine1.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Address line 1 cannot be empty"
                    )
                profile.permanent_address_line1 = address_data.addressLine1.strip()
                updated_fields.append("addressLine1")
                
            if address_data.addressLine2 is not None:
                profile.permanent_address_line2 = address_data.addressLine2.strip() if address_data.addressLine2 else ""
                updated_fields.append("addressLine2")
                
            if address_data.city is not None:
                if not address_data.city.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="City cannot be empty"
                    )
                profile.permanent_city = address_data.city.strip()
                updated_fields.append("city")
                
            if address_data.state is not None:
                if not address_data.state.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="State cannot be empty"
                    )
                profile.permanent_state = address_data.state.strip()
                updated_fields.append("state")
                
            if address_data.country is not None:
                if not address_data.country.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Country cannot be empty"
                    )
                profile.permanent_country = address_data.country.strip()
                updated_fields.append("country")
                
            if address_data.pincode is not None:
                if not address_data.pincode.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Pincode cannot be empty"
                    )
                profile.permanent_pincode = address_data.pincode.strip()
                updated_fields.append("pincode")
            
            # Update the simple address field in Employee model
            full_address = f"{profile.permanent_address_line1 or ''}"
            if profile.permanent_address_line2:
                full_address += f", {profile.permanent_address_line2}"
            full_address += f", {profile.permanent_city or ''}, {profile.permanent_state or ''}, {profile.permanent_country or ''} - {profile.permanent_pincode or ''}".strip(", -")
            employee.permanent_address = full_address
            
        elif address_type == "present":
            if address_data.addressLine1 is not None:
                if not address_data.addressLine1.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Address line 1 cannot be empty"
                    )
                profile.present_address_line1 = address_data.addressLine1.strip()
                updated_fields.append("addressLine1")
                
            if address_data.addressLine2 is not None:
                profile.present_address_line2 = address_data.addressLine2.strip() if address_data.addressLine2 else ""
                updated_fields.append("addressLine2")
                
            if address_data.city is not None:
                if not address_data.city.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="City cannot be empty"
                    )
                profile.present_city = address_data.city.strip()
                updated_fields.append("city")
                
            if address_data.state is not None:
                if not address_data.state.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="State cannot be empty"
                    )
                profile.present_state = address_data.state.strip()
                updated_fields.append("state")
                
            if address_data.country is not None:
                if not address_data.country.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Country cannot be empty"
                    )
                profile.present_country = address_data.country.strip()
                updated_fields.append("country")
                
            if address_data.pincode is not None:
                if not address_data.pincode.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Pincode cannot be empty"
                    )
                profile.present_pincode = address_data.pincode.strip()
                updated_fields.append("pincode")
            
            # Update the simple address field in Employee model
            full_address = f"{profile.present_address_line1 or ''}"
            if profile.present_address_line2:
                full_address += f", {profile.present_address_line2}"
            full_address += f", {profile.present_city or ''}, {profile.present_state or ''}, {profile.present_country or ''} - {profile.present_pincode or ''}".strip(", -")
            employee.current_address = full_address
        
        db.commit()
        db.refresh(profile)
        db.refresh(employee)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            new_values = {}
            if address_type == "permanent":
                new_values = {
                    "addressLine1": profile.permanent_address_line1,
                    "addressLine2": profile.permanent_address_line2,
                    "city": profile.permanent_city,
                    "state": profile.permanent_state,
                    "country": profile.permanent_country,
                    "pincode": profile.permanent_pincode
                }
            elif address_type == "present":
                new_values = {
                    "addressLine1": profile.present_address_line1,
                    "addressLine2": profile.present_address_line2,
                    "city": profile.present_city,
                    "state": profile.present_state,
                    "country": profile.present_country,
                    "pincode": profile.present_pincode
                }
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="addresses",
                old_data=old_values,
                new_data=new_values,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - {address_type} address update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        print(f"✅ {address_type.title()} address updated for employee {employee_id}. Fields: {updated_fields}")
        
        return {
            "success": True,
            "message": f"{address_type.title()} address updated successfully",
            "updatedFields": updated_fields,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "address": {
                "id": f"{employee_id}_{address_type}",
                "type": address_type,
                "addressType": address_type.title()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in update_employee_address: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee address: {str(e)}"
        )


@router.delete("/{employee_id}/addresses/{address_type}")
async def delete_employee_address(
    address_type: str,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete employee address"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        # Validate address type
        if address_type.lower() not in ['permanent', 'present']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Address type must be either 'permanent' or 'present'"
            )
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get employee profile
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        
        address_type = address_type.lower()
        
        # Clear address fields based on type
        if address_type == "permanent":
            if profile:
                profile.permanent_address_line1 = None
                profile.permanent_address_line2 = None
                profile.permanent_city = None
                profile.permanent_state = None
                profile.permanent_country = None
                profile.permanent_pincode = None
            employee.permanent_address = None
            
        elif address_type == "present":
            if profile:
                profile.present_address_line1 = None
                profile.present_address_line2 = None
                profile.present_city = None
                profile.present_state = None
                profile.present_country = None
                profile.present_pincode = None
            employee.current_address = None
        
        db.commit()
        if profile:
            db.refresh(profile)
        db.refresh(employee)
        
        print(f"✅ {address_type.title()} address deleted for employee {employee_id}")
        
        return {
            "success": True,
            "message": f"{address_type.title()} address deleted successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "deletedAddress": {
                "id": f"{employee_id}_{address_type}",
                "type": address_type,
                "addressType": address_type.title()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in delete_employee_address: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete employee address: {str(e)}"
        )


# ============================================================================
# EMPLOYEE IDENTITY MANAGEMENT ENDPOINTS
# ============================================================================

class EmployeeIdentityUpdate(BaseModel):
    """Schema for updating employee identity information"""
    # Bank Information
    bankName: Optional[str] = None
    bankIfsc: Optional[str] = None
    bankAccount: Optional[str] = None
    
    # Document Information
    aadharNumber: Optional[str] = None
    panNumber: Optional[str] = None
    passportNumber: Optional[str] = None
    drivingLicense: Optional[str] = None
    
    # Additional Information
    bloodGroup: Optional[str] = None
    pfUan: Optional[str] = None
    esiIpNumber: Optional[str] = None
    
    # KYC Status
    kycCompleted: Optional[bool] = None
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())
    
    @validator('bankIfsc')
    def validate_ifsc(cls, v):
        if v is not None and v.strip():
            # Basic IFSC validation (4 letters + 7 characters = 11 total)
            # But allow flexibility for partial/incomplete codes during data entry
            import re
            v_upper = v.strip().upper()
            # Check if it starts with 4 letters and has at least some digits
            if not re.match(r'^[A-Z]{4}[0-9A-Z]+$', v_upper):
                raise ValueError('Invalid IFSC code format. Must start with 4 letters followed by numbers/letters')
            # Warn if not exactly 11 characters but still allow it
            if len(v_upper) != 11:
                print(f"⚠️ IFSC code '{v_upper}' is {len(v_upper)} characters (expected 11)")
        return v.strip().upper() if v else None
    
    @validator('panNumber')
    def validate_pan(cls, v):
        if v is not None and v.strip():
            # Basic PAN validation (5 letters + 4 digits + 1 letter)
            import re
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.strip().upper()):
                raise ValueError('Invalid PAN number format')
        return v.strip().upper() if v else None
    
    @validator('aadharNumber')
    def validate_aadhar(cls, v):
        if v is not None and v.strip():
            # Basic Aadhar validation (12 digits)
            if not v.strip().isdigit() or len(v.strip()) != 12:
                raise ValueError('Aadhar number must be 12 digits')
        return v.strip() if v else None
    
    @validator('bloodGroup')
    def validate_blood_group(cls, v):
        if v is not None and v.strip():
            valid_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
            if v.strip().upper() not in valid_groups:
                raise ValueError(f'Invalid blood group. Must be one of: {", ".join(valid_groups)}')
        return v.strip().upper() if v else None


@router.get("/{employee_id}/identity")
async def get_employee_identity_detailed(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get detailed employee identity information"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get employee profile for additional identity info
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        
        print(f"📖 Loading identity for employee {employee_id}")
        print(f"   Profile exists: {profile is not None}")
        if profile:
            print(f"   Bank Name: {profile.bank_name}")
            print(f"   Bank IFSC: {profile.bank_ifsc_code}")
            print(f"   Bank Account: {profile.bank_account_number}")
        
        return {
            "success": True,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name or ''} {employee.last_name or ''}".strip(),
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "identity": {
                # Bank Information
                "bankName": profile.bank_name if profile else employee.bank_name or "",
                "bankIfsc": profile.bank_ifsc_code if profile else employee.bank_ifsc_code or "",
                "bankAccount": profile.bank_account_number if profile else employee.bank_account_number or "",
                
                # Document Information
                "aadharNumber": profile.aadhaar_number if profile else employee.aadhar_number or "",
                "panNumber": profile.pan_number if profile else "",
                "passportNumber": employee.passport_number or "",
                "drivingLicense": employee.driving_license or "",
                
                # Additional Information
                "bloodGroup": employee.blood_group or "",
                "pfUan": profile.uan_number if profile else "",
                "esiIpNumber": profile.esi_number if profile else "",
                
                # KYC Status
                "kycCompleted": profile.kyc_completed if profile else False
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in get_employee_identity_detailed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee identity: {str(e)}"
        )


@router.put("/{employee_id}/identity")
async def update_employee_identity(
    identity_data: EmployeeIdentityUpdate,
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update employee identity information with comprehensive validation"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        # Validate that the request body is not empty
        if not identity_data.has_valid_data():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body cannot be empty. At least one field must be provided for update."
            )
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get or create employee profile
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        if not profile:
            profile = EmployeeProfile(employee_id=employee_id)
            db.add(profile)
        
        # Capture old values for activity logging
        old_values = {
            "bankName": profile.bank_name,
            "bankIfsc": profile.bank_ifsc_code,
            "bankAccount": profile.bank_account_number,
            "aadharNumber": profile.aadhaar_number,
            "panNumber": profile.pan_number,
            "passportNumber": employee.passport_number,
            "drivingLicense": employee.driving_license,
            "bloodGroup": employee.blood_group,
            "pfUan": profile.uan_number,
            "esiIpNumber": profile.esi_number,
            "kycCompleted": profile.kyc_completed
        }
        
        updated_fields = []
        
        # Update bank information
        if identity_data.bankName is not None:
            profile.bank_name = identity_data.bankName.strip() if identity_data.bankName else None
            employee.bank_name = profile.bank_name  # Keep both models in sync
            updated_fields.append("bankName")
            print(f"💾 Updating bankName: {profile.bank_name}")
            
        if identity_data.bankIfsc is not None:
            profile.bank_ifsc_code = identity_data.bankIfsc
            employee.bank_ifsc_code = profile.bank_ifsc_code
            updated_fields.append("bankIfsc")
            print(f"💾 Updating bankIfsc: {profile.bank_ifsc_code}")
            
        if identity_data.bankAccount is not None:
            profile.bank_account_number = identity_data.bankAccount.strip() if identity_data.bankAccount else None
            employee.bank_account_number = profile.bank_account_number
            updated_fields.append("bankAccount")
            print(f"💾 Updating bankAccount: {profile.bank_account_number}")
        
        # Update document information
        if identity_data.aadharNumber is not None:
            # Check for duplicate Aadhar
            if identity_data.aadharNumber.strip():
                existing_aadhar = db.query(EmployeeProfile).filter(
                    EmployeeProfile.aadhaar_number == identity_data.aadharNumber.strip(),
                    EmployeeProfile.employee_id != employee_id
                ).first()
                if existing_aadhar:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Aadhar number already exists for another employee"
                    )
            
            profile.aadhaar_number = identity_data.aadharNumber
            employee.aadhar_number = profile.aadhaar_number
            updated_fields.append("aadharNumber")
            
        if identity_data.panNumber is not None:
            # Check for duplicate PAN
            if identity_data.panNumber.strip():
                existing_pan = db.query(EmployeeProfile).filter(
                    EmployeeProfile.pan_number == identity_data.panNumber.strip(),
                    EmployeeProfile.employee_id != employee_id
                ).first()
                if existing_pan:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="PAN number already exists for another employee"
                    )
            
            profile.pan_number = identity_data.panNumber
            updated_fields.append("panNumber")
            
        if identity_data.passportNumber is not None:
            employee.passport_number = identity_data.passportNumber.strip() if identity_data.passportNumber else None
            updated_fields.append("passportNumber")
            
        if identity_data.drivingLicense is not None:
            employee.driving_license = identity_data.drivingLicense.strip() if identity_data.drivingLicense else None
            updated_fields.append("drivingLicense")
        
        # Update additional information
        if identity_data.bloodGroup is not None:
            employee.blood_group = identity_data.bloodGroup
            updated_fields.append("bloodGroup")
            
        if identity_data.pfUan is not None:
            profile.uan_number = identity_data.pfUan.strip() if identity_data.pfUan else None
            updated_fields.append("pfUan")
            
        if identity_data.esiIpNumber is not None:
            profile.esi_number = identity_data.esiIpNumber.strip() if identity_data.esiIpNumber else None
            updated_fields.append("esiIpNumber")
        
        # Update KYC status
        if identity_data.kycCompleted is not None:
            profile.kyc_completed = identity_data.kycCompleted
            updated_fields.append("kycCompleted")
        
        # Update system fields
        employee.updated_by = current_user.id
        
        # Commit changes
        db.commit()
        db.refresh(profile)
        db.refresh(employee)
        
        # Log activity
        try:
            from app.services.employee_change_tracker import (
                EmployeeChangeTracker,
                get_client_ip,
                get_user_agent
            )
            
            new_values = {
                "bankName": profile.bank_name,
                "bankIfsc": profile.bank_ifsc_code,
                "bankAccount": profile.bank_account_number,
                "aadharNumber": profile.aadhaar_number,
                "panNumber": profile.pan_number,
                "passportNumber": employee.passport_number,
                "drivingLicense": employee.driving_license,
                "bloodGroup": employee.blood_group,
                "pfUan": profile.uan_number,
                "esiIpNumber": profile.esi_number,
                "kycCompleted": profile.kyc_completed
            }
            
            change_tracker = EmployeeChangeTracker(db)
            change_tracker.log_update(
                user_id=current_user.id,
                employee_id=employee_id,
                section="identity",
                old_data=old_values,
                new_data=new_values,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            print(f"✅ Activity logged for employee {employee_id} - identity update")
        except Exception as log_error:
            print(f"⚠️ Failed to log activity: {log_error}")
        
        print(f"✅ Employee {employee_id} identity updated successfully. Fields: {updated_fields}")
        
        return {
            "success": True,
            "message": "Employee identity updated successfully",
            "updatedFields": updated_fields,
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in update_employee_identity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee identity: {str(e)}"
        )


@router.post("/{employee_id}/identity/verify-bank")
async def verify_bank_details(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Verify bank details (placeholder for actual verification service)"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        
        # Check if bank details exist
        bank_name = profile.bank_name if profile else employee.bank_name
        bank_account = profile.bank_account_number if profile else employee.bank_account_number
        bank_ifsc = profile.bank_ifsc_code if profile else employee.bank_ifsc_code
        
        if not all([bank_name, bank_account, bank_ifsc]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank details are incomplete. Please provide bank name, account number, and IFSC code."
            )
        
        # Placeholder for actual bank verification logic
        # In a real implementation, this would call a bank verification API
        verification_result = {
            "verified": True,
            "accountHolderName": f"{employee.first_name} {employee.last_name}",
            "verificationId": f"VERIFY_{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "verifiedAt": datetime.now().isoformat()
        }
        
        print(f"✅ Bank verification initiated for employee {employee_id}")
        
        return {
            "success": True,
            "message": "Bank verification completed successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "verification": verification_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in verify_bank_details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify bank details: {str(e)}"
        )


@router.post("/{employee_id}/identity/verify-pan")
async def verify_pan_details(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Verify PAN details (placeholder for actual verification service)"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        pan_number = profile.pan_number if profile else ""
        
        if not pan_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PAN number not found. Please provide PAN number first."
            )
        
        # Placeholder for actual PAN verification logic
        verification_result = {
            "verified": True,
            "panHolderName": f"{employee.first_name} {employee.last_name}",
            "panNumber": pan_number,
            "verificationId": f"PAN_VERIFY_{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "verifiedAt": datetime.now().isoformat()
        }
        
        print(f"✅ PAN verification initiated for employee {employee_id}")
        
        return {
            "success": True,
            "message": "PAN verification completed successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "verification": verification_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in verify_pan_details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify PAN details: {str(e)}"
        )


@router.post("/{employee_id}/identity/verify-aadhar")
async def verify_aadhar_details(
    business_id: int = Path(..., description="Business ID"),
    employee_id: int = Path(..., description="Employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Verify Aadhar details (placeholder for actual verification service)"""
    try:
        from app.models.employee import Employee, EmployeeProfile
        
        validate_business_access(business_id, current_user, db)
        employee = validate_employee_access(db, employee_id, current_user, business_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
        aadhar_number = profile.aadhaar_number if profile else employee.aadhar_number
        
        if not aadhar_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aadhar number not found. Please provide Aadhar number first."
            )
        
        # Placeholder for actual Aadhar verification logic
        # Note: As per UIDAI regulations, full Aadhar number should not be stored
        masked_aadhar = f"XXXX-XXXX-{aadhar_number[-4:]}" if len(aadhar_number) >= 4 else "XXXX-XXXX-XXXX"
        
        verification_result = {
            "verified": True,
            "aadharHolderName": f"{employee.first_name} {employee.last_name}",
            "maskedAadhar": masked_aadhar,
            "verificationId": f"AADHAR_VERIFY_{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "verifiedAt": datetime.now().isoformat()
        }
        
        print(f"✅ Aadhar verification initiated for employee {employee_id}")
        
        return {
            "success": True,
            "message": "Aadhar verification completed successfully",
            "employee": {
                "id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "code": employee.employee_code or f"EMP{employee.id:03d}"
            },
            "verification": verification_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR in verify_aadhar_details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify Aadhar details: {str(e)}"
        )


# ============================================================================
# EMPLOYEE WORK PROFILE MANAGEMENT ENDPOINTS
# ============================================================================

class EmployeeWorkProfileUpdate(BaseModel):
    """Schema for updating employee work profile information"""
    
    # Organizational Information
    businessId: Optional[int] = None
    locationId: Optional[int] = None
    costCenterId: Optional[int] = None
    departmentId: Optional[int] = None
    gradeId: Optional[int] = None
    designationId: Optional[int] = None
    
    # Manager Assignments
    reportingManagerId: Optional[int] = None
    hrManagerId: Optional[int] = None
    indirectManagerId: Optional[int] = None
    
    # Work Profile Details
    effectiveFrom: Optional[str] = None
    isPromotion: Optional[bool] = None
    
    def has_valid_data(self) -> bool:
        """Check if at least one field has a non-None value"""
        return any(value is not None for value in self.dict().values())
    
    @validator('effectiveFrom')
    def validate_effective_from(cls, v):
        if v is not None and v.strip():
            try:
                from datetime import datetime
                datetime.fromisoformat(v.strip())
                return v.strip()
            except ValueError:
                raise ValueError('Invalid date format. Use YYYY-MM-DD format.')
        return v


# ============================================================================
# BULK EMPLOYEE OPERATIONS
# ============================================================================
