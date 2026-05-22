"""
Data Capture API Endpoints
Complete data capture and management API

REORGANIZED: 2026-02-23 10:46:27
============================================================================
FILE ORGANIZATION - MATCHES FRONTEND MENU SEQUENCE:

1. SALARY VARIABLE      ✓ Frontend Position #1
2. SALARY UNITS         ✓ Frontend Position #2
3. DEDUCTION            ✓ Frontend Position #3
4. INCOME TAX (TDS)     ✓ Frontend Position #4
5. EXTRA DAYS           ✓ Frontend Position #5
6. EXTRA HOURS          ✓ Frontend Position #6
7. LOANS                ✓ Frontend Position #7
8. IT DECLARATION       ✓ Frontend Position #8
9. IT EXEMPTIONS        ✓ Frontend Position #9 (Part of IT Declaration)
10. TDS CHALLANS        ✓ Frontend Position #10
11. TDS RETURNS         ✓ Frontend Position #11

All sections are now in the exact order shown in the frontend menu.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.core.database import get_db
from app.api.v1.deps import get_current_user, get_current_admin
from app.utils.tenant import validate_business
from app.models.user import User
from app.models.employee import Employee
from app.models.department import Department
from app.models.location import Location
from app.models.datacapture import ExtraDay
from app.schemas.datacapture import (
    ExtraDaysEmployeeResponse, ExtraDaysUpdateRequest, ExtraDaysFiltersResponse,
    ExtraDaysSearchResponse, ExtraDaysExportResponse, ExtraDaysExportAllResponse,
    ExtraDaysImportResponse, ExtraDayCreate, ExtraDayUpdate, ExtraDayResponse,
    SalaryVariableCreate, SalaryVariableUpdate, SalaryVariableResponse,
    SalaryVariableEmployeeResponse, SalaryVariableEmployeesResponse, SalaryVariableUpdateRequest,
    AddNonCashSalaryRequest, SalaryVariableFiltersResponse,
    SalaryUnitsEmployeeResponse, SalaryUnitsUpdateRequest, SalaryUnitsFiltersResponse,
    ImportTravelKmsRequest,
    ExtraHoursEmployeeResponse, ExtraHoursFiltersResponse, ExtraHoursSearchResponse,
    ExtraHoursCreateRequest, ExtraHoursCreateResponse, ExtraHoursImportRequest, ExtraHoursImportResponse,
    TDSChallanSaveRequest, TDSChallanMonthResponse, TDSChallanYearResponse, TDSChallanSummaryResponse,
    TDSReturnSaveRequest, TDSReturnRequest
)
from app.schemas.datacapture_additional import TravelKmsImportRequest
from app.services.salary_variable_service import SalaryVariableService
from app.services.salary_units_service import SalaryUnitsService
from app.services.deduction_service import DeductionService
from app.services.income_tax_tds_service import IncomeTaxTDSService
from app.services.tds_challan_service import TDSChallanService
from app.services.tds_return_service import TDSReturnService
from pydantic import BaseModel, Field

router = APIRouter()


# Centralized business access validation helper
def validate_business_access(business_id: int, current_user: User, db: Session):
    from app.models.business import Business
    from app.utils.business_unit_utils import is_superadmin

    # Ensure business exists (simple tenant validation)
    business = validate_business(business_id, db)

    # Additional access control: owner or superadmin only
    if getattr(business, 'owner_id', None) != current_user.id and not is_superadmin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this business"
        )

    return business


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_business_ids(current_user: User, db: Session) -> list:
    """
    Get list of business IDs owned by the current user.
    Returns empty list if user owns no businesses.
    """
    from app.models.business import Business
    user_business_ids = db.query(Business.id).filter(
        Business.owner_id == current_user.id
    ).all()
    return [b[0] for b in user_business_ids]


def get_user_business_id(current_user: User, db: Session) -> int:
    """
    Get the first business ID owned by the current user.
    Raises 404 if user owns no businesses.
    """
    business_ids = get_user_business_ids(current_user, db)
    if not business_ids:
        raise HTTPException(
            status_code=404,
            detail="No business found for current user"
        )
    return business_ids[0]


# ============================================================================
# PYDANTIC MODELS
# ============================================================================
class DataCaptureDashboardResponse(BaseModel):
    """Data capture dashboard response"""
    statistics: Dict[str, int]
    recent_activities: List[Dict[str, Any]]
    available_templates: List[Dict[str, str]]


class BulkImportRequest(BaseModel):
    """Bulk import request"""
    import_type: str
    file_name: str
    total_records: int


class BulkImportResponse(BaseModel):
    """Bulk import response"""
    import_id: str
    status: str
    total_records: int
    processed_records: int
    successful_records: int
    failed_records: int
    errors: List[str]
    started_at: str


class SalaryVariableResponse(BaseModel):
    """Salary variable response"""
    id: int
    employee_id: int
    employee_name: str
    variable_name: str
    variable_amount: Decimal
    effective_date: date
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class SalaryUnitsResponse(BaseModel):
    """Salary units response"""
    id: int
    unit_name: str
    unit_type: str
    calculation_method: str
    base_amount: Optional[Decimal] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeductionResponse(BaseModel):
    """Deduction response"""
    id: int
    employee_id: int
    employee_name: str
    deduction_type: str
    deduction_amount: Decimal
    deduction_date: date
    reason: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class IncomeTaxTDSResponse(BaseModel):
    """Income tax TDS response"""
    id: int
    employee_id: int
    employee_name: str
    financial_year: str
    tds_amount: Decimal
    tax_period: str
    challan_number: Optional[str] = None
    payment_date: Optional[date] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExtraDaysResponse(BaseModel):
    """Extra days response"""
    id: int
    employee_id: int
    employee_name: str
    extra_date: date
    hours_worked: Decimal
    reason: str
    approved_by: Optional[int] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExtraHoursResponse(BaseModel):
    """Extra hours response"""
    id: int
    employee_id: int
    employee_name: str
    work_date: date
    extra_hours: Decimal
    hourly_rate: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    reason: str
    approved_by: Optional[int] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class LoansResponse(BaseModel):
    """Loans response"""
    id: int
    employee_id: int
    employee_name: str
    loan_type: str
    loan_amount: Decimal
    outstanding_amount: Decimal
    monthly_deduction: Decimal
    start_date: date
    end_date: Optional[date] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ITDeclarationsResponse(BaseModel):
    """IT declarations response"""
    id: int
    employee_id: int
    employee_name: str
    financial_year: str
    declaration_type: str
    declared_amount: Decimal
    supporting_documents: Optional[str] = None
    status: str
    submitted_at: datetime
    
    class Config:
        from_attributes = True


class DeductionTDSResponse(BaseModel):
    """Deduction TDS response"""
    id: int
    employee_id: int
    employee_name: str
    deduction_type: str
    tds_amount: Decimal
    deduction_month: str
    challan_reference: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TDSChallansResponse(BaseModel):
    """TDS challans response"""
    id: int
    challan_number: str
    payment_date: date
    total_amount: Decimal
    bank_name: str
    branch_code: Optional[str] = None
    employees_count: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TDSReturnsResponse(BaseModel):
    """TDS returns response"""
    id: int
    return_type: str
    financial_year: str
    quarter: str
    total_tds_amount: Decimal
    filing_date: Optional[date] = None
    acknowledgment_number: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  1. SALARY VARIABLE                                                           ║
# ║  Frontend Menu Position: #1                                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝



@router.get("/salary-variable", response_model=List[SalaryVariableResponse])
async def get_salary_variables(
    business_id: int,
    employee_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get salary variables for employees
    
    **Returns:**
    - List of salary variables
    - Employee details
    - Variable amounts and dates
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        variables = service.get_salary_variables(
            business_id=business_id,
            employee_id=employee_id,
            page=page,
            size=size
        )
        
        # Convert to response format
        response_data = []
        for var in variables:
            response_data.append(SalaryVariableResponse(
                id=var["id"],
                employee_id=var["employee_id"],
                employee_name=var["employee_name"],
                variable_name=var["variable_name"],
                variable_amount=var["variable_amount"],
                effective_date=var["effective_date"],
                status=var["status"],
                created_at=var["created_at"],
                business_id=var["business_id"],
                is_active=var["is_active"],
                updated_at=var["updated_at"],
                created_by=var["created_by"]
            ))
        
        return response_data
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary variables: {str(e)}"
        )


class SalaryVariableRequest(BaseModel):
    """Salary variable create/update request"""
    employee_id: int
    variable_name: str
    variable_amount: float
    effective_date: date
    description: Optional[str] = None
    is_recurring: bool = False


@router.post("/salary-variable", response_model=SalaryVariableResponse)
async def create_salary_variable(
    business_id: int,
    variable_data: SalaryVariableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create new salary variable
    
    **Creates:**
    - New salary variable for employee
    - Variable amount and effective date
    - Recurring or one-time variable
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.create_salary_variable(
            variable_data=variable_data,
            business_id=business_id,
            created_by=current_user.id
        )
        
        # Convert to response format
        return SalaryVariableResponse(
            id=result["id"],
            employee_id=result["employee_id"],
            employee_name=result["employee_name"],
            variable_name=result["variable_name"],
            variable_amount=result["variable_amount"],
            effective_date=result["effective_date"],
            status=result["status"],
            created_at=result["created_at"],
            business_id=result["business_id"],
            is_active=result["is_active"],
            updated_at=result["updated_at"],
            created_by=result["created_by"]
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create salary variable: {str(e)}"
        )


@router.put("/salary-variable/{variable_id}", response_model=SalaryVariableResponse)
async def update_salary_variable(
    business_id: int,
    variable_id: int,
    variable_data: SalaryVariableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update salary variable
    
    **Updates:**
    - Salary variable details
    - Amount and effective date
    - Variable configuration
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.update_salary_variable(
            variable_id=variable_id,
            variable_data=variable_data,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        # Convert to response format
        return SalaryVariableResponse(
            id=result["id"],
            employee_id=result["employee_id"],
            employee_name=result["employee_name"],
            variable_name=result["variable_name"],
            variable_amount=result["variable_amount"],
            effective_date=result["effective_date"],
            status=result["status"],
            created_at=result["created_at"],
            business_id=result["business_id"],
            is_active=result["is_active"],
            updated_at=result["updated_at"],
            created_by=result["created_by"]
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update salary variable: {str(e)}"
        )


@router.delete("/salary-variable/{variable_id}", response_model=Dict[str, str])
async def delete_salary_variable(
    business_id: int,
    variable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete salary variable
    
    **Deletes:**
    - Salary variable record
    - Maintains audit trail
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.delete_salary_variable(
            variable_id=variable_id,
            business_id=business_id
        )
        
        return {
            "message": result["message"],
            "variable_id": result["variable_id"],
            "deleted_by": current_user.email,
            "deleted_at": result["deleted_at"]
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete salary variable: {str(e)}"
        )


@router.get("/salary-variable/export-csv")
async def export_salary_variables_csv(
    business_id: int,
    employee_id: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    cost_center: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    business_unit: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export salary variables as CSV with filtering options
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        csv_content = service.export_salary_variables_csv(
            business_id=business_id,
            employee_id=employee_id,
            month=month,
            location=location,
            cost_center=cost_center,
            department=department,
            business_unit=business_unit
        )

        # Safely build filename even when `month` is None
        if month:
            filename_month = month.replace(' ', '_')
        else:
            filename_month = datetime.now().strftime('%Y%m%d')

        # Ensure csv_content is a string
        if csv_content is None:
            csv_content = ""

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=salary_variables_{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export CSV: {str(e)}"
        )


@router.post("/salary-variable/import-csv")
async def import_salary_variable_csv(
    business_id: int,
    csv_data: str = Body(..., media_type="text/plain"),
    overwrite_existing: bool = Query(False),
    consider_arrear: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import salary variables from CSV content
    
    **Accepts:**
    - CSV content as text/plain body
    - overwrite_existing: Whether to overwrite existing records
    - consider_arrear: Whether to treat as arrear payments
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.import_salary_variables_csv(
            csv_content=csv_data,
            business_id=business_id,
            created_by=current_user.id,
            overwrite_existing=overwrite_existing,
            consider_arrear=consider_arrear
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import CSV: {str(e)}"
        )


# ============================================================================
# MISSING SALARY VARIABLE ENDPOINTS - Frontend Compatible
# ============================================================================

@router.get("/salary-variable-employees", response_model=SalaryVariableEmployeesResponse)
async def get_salary_variable_employees(
    business_id: int,
    month: str = Query("January 2026", description="Month in format 'January 2026'"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    leave_option: Optional[str] = Query(None),
    arrear: bool = Query(False),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with salary variable data for frontend table
    
    **Frontend URL:** /datacapture/salary-variable
    
    **Returns:**
    - Employee list with salary variable information
    - Supports filtering by business unit, location, department
    - Supports search by employee name or code
    - Supports pagination
    """
    try:
        from app.services.salary_variable_service import SalaryVariableService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.get_salary_variable_employees(
            business_id=business_id,
            month=month,
            business_unit=business_unit,
            location=location,
            department=department,
            leave_option=leave_option,
            arrear=arrear,
            search=search,
            page=page,
            size=size,
            current_user=current_user
        )
        
        return SalaryVariableEmployeesResponse(
            employees=result.get("employees", []),
            total_pages=result.get("total_pages", 1),
            current_page=page,
            total_employees=result.get("total_employees", 0)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary variable employees: {str(e)}"
        )


@router.get("/salary-variable-filters", response_model=SalaryVariableFiltersResponse)
async def get_salary_variable_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for salary variable module
    
    **Returns:**
    - Business units, locations, departments
    - Leave options for dropdown filters
    - Used for dropdown filters in salary variable frontend
    """
    try:
        from app.services.salary_variable_service import SalaryVariableService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        filters = service.get_salary_variable_filters(
            business_id=business_id,
            current_user=current_user
        )
        
        return SalaryVariableFiltersResponse(
            business_units=filters.get("business_units", ["All Business Units"]),
            locations=filters.get("locations", ["All Locations"]),
            departments=filters.get("departments", ["All Departments"]),
            cost_centers=filters.get("cost_centers", ["All Cost Centers"]),
            leave_options=filters.get("leave_options", ["Leave Encashment"])
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary variable filters: {str(e)}"
        )


@router.post("/salary-variable-update", response_model=Dict[str, str])
async def update_salary_variable_employee(
    business_id: int,
    update_data: SalaryVariableUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update salary variable for an employee
    
    **Updates:**
    - Employee salary variable amount
    - Comments and variable type
    - Month-specific data
    """
    try:
        from app.services.salary_variable_service import SalaryVariableService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.update_salary_variable_employee(
            update_data=update_data,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update salary variable: {str(e)}"
        )


@router.post("/salary-variable-add-non-cash", response_model=Dict[str, Any])
async def add_non_cash_salary_component(
    business_id: int,
    request_data: AddNonCashSalaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Add non-cash salary components for employees
    
    **Creates:**
    - Non-cash salary components
    - For multiple employees
    - With date range and component mapping
    """
    try:
        from app.services.salary_variable_service import SalaryVariableService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryVariableService(db)
        result = service.add_non_cash_salary(
            request_data=request_data,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add non-cash salary components: {str(e)}"
        )




# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  2. SALARY UNITS                                                              ║
# ║  Frontend Menu Position: #2                                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝



@router.get("/salary-units", response_model=List[SalaryUnitsResponse])
async def get_salary_units(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get salary units configuration
    
    **Returns:**
    - List of salary calculation units
    - Unit types and methods
    - Base amounts
    """
    try:
        # Validate business access (even for mock data)
        validate_business_access(business_id, current_user, db)
        # Mock data for salary units
        mock_units = [
            SalaryUnitsResponse(
                id=1,
                unit_name="Basic Salary",
                unit_type="fixed",
                calculation_method="monthly",
                base_amount=Decimal("25000.00"),
                is_active=True,
                created_at=datetime.now()
            ),
            SalaryUnitsResponse(
                id=2,
                unit_name="HRA",
                unit_type="percentage",
                calculation_method="percentage_of_basic",
                base_amount=Decimal("40.00"),
                is_active=True,
                created_at=datetime.now()
            ),
            SalaryUnitsResponse(
                id=3,
                unit_name="Transport Allowance",
                unit_type="fixed",
                calculation_method="monthly",
                base_amount=Decimal("2000.00"),
                is_active=True,
                created_at=datetime.now()
            )
        ]
        
        return mock_units
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary units: {str(e)}"
        )


@router.get("/salary-units-employees", response_model=List[SalaryUnitsEmployeeResponse])
async def get_salary_units_employees(
    business_id: int,
    month: str = Query("January 2026", description="Month in format 'January 2026'"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    component: Optional[str] = Query(None),
    arrear: bool = Query(False),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with salary units data for frontend table
    
    **Frontend URL:** /datacapture/salary-units
    
    **Returns:**
    - Employee list with salary units information
    - Supports filtering by business unit, location, department, component
    - Supports search by employee name or code
    - Supports pagination
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryUnitsService(db)
        employees = service.get_salary_units_employees(
            business_id=business_id,
            month=month,
            business_unit=business_unit,
            location=location,
            department=department,
            component=component,
            arrear=arrear,
            search=search,
            page=page,
            size=size,
            current_user=current_user
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary units employees: {str(e)}"
        )


@router.get("/salary-units-filters", response_model=SalaryUnitsFiltersResponse)
async def get_salary_units_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for salary units module
    
    **Returns:**
    - Business units, locations, departments, components
    - Used for dropdown filters in salary units frontend
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryUnitsService(db)
        filters = service.get_salary_units_filters(
            business_id=business_id,
            current_user=current_user
        )
        
        return SalaryUnitsFiltersResponse(
            businessUnits=filters.get("businessUnits", ["All Business Units"]),
            locations=filters.get("locations", ["All Locations"]),
            departments=filters.get("departments", ["All Departments"]),
            components=filters.get("components", ["Component"])
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary units filters: {str(e)}"
        )


@router.post("/salary-units-update", response_model=Dict[str, str])
async def update_salary_units_employee(
    business_id: int,
    update_data: SalaryUnitsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update salary units for an employee
    
    **Updates:**
    - Employee salary units amount
    - Comments and component type
    - Month-specific data
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryUnitsService(db)
        result = service.update_salary_units_employee(
            employee_code=update_data.employee_code,
            month=update_data.month,
            amount=update_data.amount,
            comments=update_data.comments,
            component=update_data.component,
            arrear=update_data.arrear,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update salary units: {str(e)}"
        )


@router.post("/salary-units-import-travel", response_model=Dict[str, str])
async def import_travel_kms_to_salary_units(
    business_id: int,
    import_data: TravelKmsImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import travel kilometers data to salary units
    
    **Request body:**
    - period: Period for salary units (e.g., 'JAN-2026')
    - location: Location filter for employees
    - department: Department filter for employees
    - component: Salary component name
    - distance_type: Type of distance calculation (Calculated/Manual)
    - comments: Additional comments for the import
    - overwrite_existing: Whether to overwrite existing salary units
    
    **Creates:**
    - Salary units based on travel data
    - For employees matching location/department filters
    - With calculated amounts based on distance
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        
        # Validate business path and access
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = SalaryUnitsService(db)
        result = service.import_travel_kms(
            period=import_data.period,
            location=import_data.location,
            department=import_data.department,
            component=import_data.component,
            distance_type=import_data.distance_type,
            comments=import_data.comments,
            overwrite_existing=import_data.overwrite_existing,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import travel KMS: {str(e)}"
        )


@router.get("/salary-units-export")
async def export_salary_units_csv(
    business_id: int,
    month: str = Query("January 2026", description="Month in format 'January 2026'"),
    location: Optional[str] = Query(None),
    cost_center: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export salary units data as CSV
    
    **Returns:**
    - CSV file with salary units data
    - Filtered by location, cost center, department
    - For specified month
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        from fastapi.responses import StreamingResponse
        import io
        
        # Validate business from path and access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryUnitsService(db)
        csv_content = service.export_salary_units_csv(
            month=month,
            location=location,
            cost_center=cost_center,
            department=department,
            business_id=business_id
        )
        
        # Create streaming response
        csv_buffer = io.StringIO(csv_content)
        
        # Safely build filename
        filename_month = month.replace(' ', '-') if month else datetime.now().strftime('%Y%m%d')
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=salary-units-{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export salary units: {str(e)}"
        )


@router.post("/salary-units-import", response_model=Dict[str, Any])
async def import_salary_units_csv(
    business_id: int,
    request: Request,
    month: str = Query("January 2026", description="Month in format 'January 2026'"),
    overwrite_existing: bool = Query(False),
    consider_arrear: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import salary units data from CSV
    
    **Creates:**
    - Salary units from CSV data
    - For specified month
    - With optional arrear consideration
    """
    try:
        from app.services.salary_units_service import SalaryUnitsService
        
        # Read CSV content from request body
        csv_content = await request.body()
        csv_content = csv_content.decode('utf-8')
        
        # Validate business path and access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = SalaryUnitsService(db)
        result = service.import_salary_units_csv(
            csv_content=csv_content,
            month=month,
            overwrite_existing=overwrite_existing,
            consider_arrear=consider_arrear,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import salary units: {str(e)}"
        )


@router.get("/salary-units/{unit_id}")
async def get_salary_unit_by_id(
    business_id: int,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get a specific salary unit by ID
    
    **Returns:**
    - Salary unit details
    - Employee information
    - Amount and dates
    """
    try:
        from app.models.datacapture import EmployeeSalaryUnit
        
        validate_business_access(business_id, current_user, db)
        # Query salary unit
        query = db.query(EmployeeSalaryUnit).filter(
            EmployeeSalaryUnit.id == unit_id,
            EmployeeSalaryUnit.is_active == True
        )
        
        if business_id:
            query = query.filter(EmployeeSalaryUnit.business_id == business_id)
        
        salary_unit = query.first()
        
        if not salary_unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salary unit with ID {unit_id} not found"
            )
        
        # Get employee details
        employee = db.query(Employee).filter(Employee.id == salary_unit.employee_id).first()
        
        return {
            "id": salary_unit.id,
            "employee_id": salary_unit.employee_id,
            "employee_name": employee.full_name if employee else "Unknown",
            "employee_code": employee.employee_code if employee else "N/A",
            "unit_name": salary_unit.unit_name,
            "unit_type": salary_unit.unit_type,
            "amount": float(salary_unit.amount),
            "effective_date": salary_unit.effective_date.isoformat(),
            "end_date": salary_unit.end_date.isoformat() if salary_unit.end_date else None,
            "comments": salary_unit.comments,
            "is_arrear": salary_unit.is_arrear,
            "is_active": salary_unit.is_active,
            "created_at": salary_unit.created_at.isoformat() if salary_unit.created_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary unit: {str(e)}"
        )


@router.put("/salary-units/{unit_id}")
async def update_salary_unit_by_id(
    business_id: int,
    unit_id: int,
    amount: float = Body(...),
    comments: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update a specific salary unit by ID
    
    **Updates:**
    - Salary unit amount
    - Comments
    """
    try:
        from app.models.datacapture import EmployeeSalaryUnit
        
        validate_business_access(business_id, current_user, db)
        # Query salary unit
        query = db.query(EmployeeSalaryUnit).filter(
            EmployeeSalaryUnit.id == unit_id,
            EmployeeSalaryUnit.is_active == True
        )
        
        if business_id:
            query = query.filter(EmployeeSalaryUnit.business_id == business_id)
        
        salary_unit = query.first()
        
        if not salary_unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salary unit with ID {unit_id} not found"
            )
        
        # Update fields
        salary_unit.amount = Decimal(str(amount))
        if comments is not None:
            salary_unit.comments = comments
        salary_unit.updated_by = current_user.id
        salary_unit.updated_at = datetime.now()
        
        db.commit()
        db.refresh(salary_unit)
        
        return {
            "message": f"Salary unit {unit_id} updated successfully",
            "unit_id": unit_id,
            "amount": float(salary_unit.amount),
            "comments": salary_unit.comments,
            "updated_at": salary_unit.updated_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update salary unit: {str(e)}"
        )


@router.delete("/salary-units/{unit_id}")
async def delete_salary_unit_by_id(
    business_id: int,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a specific salary unit by ID (soft delete)
    
    **Deletes:**
    - Marks salary unit as inactive
    """
    try:
        from app.models.datacapture import EmployeeSalaryUnit
        
        validate_business_access(business_id, current_user, db)
        # Query salary unit
        query = db.query(EmployeeSalaryUnit).filter(
            EmployeeSalaryUnit.id == unit_id,
            EmployeeSalaryUnit.is_active == True
        )
        
        if business_id:
            query = query.filter(EmployeeSalaryUnit.business_id == business_id)
        
        salary_unit = query.first()
        
        if not salary_unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salary unit with ID {unit_id} not found"
            )
        
        # Soft delete
        salary_unit.is_active = False
        salary_unit.updated_by = current_user.id
        salary_unit.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "message": f"Salary unit {unit_id} deleted successfully",
            "unit_id": unit_id,
            "deleted_at": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete salary unit: {str(e)}"
        )



# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  3. DEDUCTION                                                                 ║
# ║  Frontend Menu Position: #3                                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝



@router.get("/deduction", response_model=List[DeductionResponse])
async def get_deductions(
    business_id: int,
    employee_id: Optional[int] = Query(None),
    deduction_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employee deductions
    
    **Returns:**
    - List of deductions
    - Employee details
    - Deduction amounts and types
    """
    try:
        # Validate business access for path business_id
        validate_business_access(business_id, current_user, db)
        # Mock data for deductions
        mock_deductions = []
        
        # Get employees for mock data
        employee_query = db.query(Employee).filter(Employee.employee_status == "active")
        if business_id:
            employee_query = employee_query.filter(Employee.business_id == business_id)
        if employee_id:
            employee_query = employee_query.filter(Employee.id == employee_id)
        
        employees = employee_query.limit(size).all()
        
        deduction_types = ["PF", "ESI", "Professional Tax", "Income Tax"]
        
        for i, employee in enumerate(employees):
            deduction_type_selected = deduction_types[i % len(deduction_types)]
            mock_deductions.append(DeductionResponse(
                id=i + 1,
                employee_id=employee.id,
                employee_name=employee.full_name,
                deduction_type=deduction_type_selected,
                deduction_amount=Decimal("1800.00") if deduction_type_selected == "PF" else Decimal("500.00"),
                deduction_date=date.today(),
                reason=f"Monthly {deduction_type_selected} deduction",
                status="processed",
                created_at=datetime.now()
            ))
        
        return mock_deductions
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deductions: {str(e)}"
        )


# ============================================================================
# DEDUCTION APIs - Frontend Compatible
# ============================================================================

class DeductionEmployeeResponse(BaseModel):
    """Deduction employee response matching frontend expectations"""
    id: int
    name: str  # Employee name with bold formatting
    code: str  # Employee code
    location: str
    dept: str  # Department
    position: str = "Software Engineer"  # Employee position/designation
    grosssalary: float = 75000.0  # Gross salary
    calculatedexemptions: float = 0.0  # Calculated exemptions (deductions)
    additionalexemptions: float = 0.0  # Additional exemptions (user input)
    netsalary: float = 75000.0  # Net salary after deductions
    amount: float = 0.0  # Deduction amount
    comments: str = ""  # Comments
    total: float = 0.0  # Total deductions


class DeductionUpdateRequest(BaseModel):
    """Deduction update request"""
    employee_code: str
    month: str  # Format: "AUG-2025"
    amount: float
    comments: str = ""
    deduction_type: str = "Voluntary PF"


class CopyFromPreviousPeriodRequest(BaseModel):
    """Copy from previous period request"""
    source_period: str  # Format: "AUG-2025"
    target_period: str  # Format: "SEP-2025"
    deduction_type: str = "Voluntary PF"
    overwrite_existing: bool = False


@router.get("/deduction-employees", response_model=List[DeductionEmployeeResponse], operation_id="get_deduction_employees_v1")
async def get_deduction_employees(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    deduction_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with deduction data for frontend table
    
    **Frontend Compatible:**
    - Returns employee data with deduction amounts
    - Supports filtering by business unit, location, department
    - Includes gross salary, exemptions, and net salary calculations
    """
    try:
        # Validate business from path and access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer for real database integration
        service = DeductionService(db)
        employees = service.get_deduction_employees(
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
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deduction employees: {str(e)}"
        )


@router.get("/deductionTDS", response_model=List[DeductionEmployeeResponse])
async def get_deduction_tds_employees(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025' or 'YYYY-YYYY' for financial year"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    deduction_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with deduction TDS data for frontend table
    
    **Frontend Compatible:**
    - Returns employee data with deduction amounts
    - Supports both month format (AUG-2025) and financial year format (2025-2026)
    - Includes gross salary, exemptions, and net salary calculations
    """
    try:
        # Handle financial year format (e.g., "2025-2026") - convert to current month
        if '-' in month and len(month.split('-')[0]) == 4:
            # Financial year format detected, use current month
            from datetime import datetime
            current_month = datetime.now().strftime("%b-%Y").upper()
            month = current_month
        
        # Validate business from path and access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer for real database integration
        service = DeductionService(db)
        employees = service.get_deduction_employees(
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
        
        return employees
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deduction TDS employees: {str(e)}"
        )


@router.get("/deductionTDS-filters", response_model=Dict[str, List[str]])
async def get_deduction_tds_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for deduction TDS module
    
    **Returns:**
    - Business units, locations, departments for dropdown filters
    - Used for dropdown filters in deduction TDS frontend
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = DeductionService(db)
        filters = service.get_deduction_filters(business_id=business_id, current_user=current_user)
        
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deduction TDS filters: {str(e)}"
        )


@router.post("/deductionTDS-update", response_model=Dict[str, str])
async def update_deduction_tds_employee(
    business_id: int,
    update_data: DeductionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update deduction TDS for an employee
    
    **Updates:**
    - Employee deduction amount for TDS calculation
    - Comments and deduction type
    - Month-specific data
    """
    try:
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = DeductionService(db)
        result = service.update_employee_deduction(
            employee_code=update_data.employee_code,
            month=update_data.month,
            amount=update_data.amount,
            comments=update_data.comments,
            deduction_type=update_data.deduction_type,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deduction TDS: {str(e)}"
        )


@router.get("/deductionTDS-export")
async def export_deduction_tds_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    location: Optional[str] = Query(None),
    cost_center: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export deduction TDS data as CSV
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = DeductionService(db)
        csv_content = service.export_deductions_csv(
            month=month,
            location=location,
            cost_center=cost_center,
            department=department,
            business_id=business_id
        )
        
        # Return as streaming response
        filename_month = month.replace('-', '_') if month else datetime.now().strftime('%Y%m%d')
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=deduction_tds_{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export deduction TDS CSV: {str(e)}"
        )


@router.get("/deduction-filters", response_model=Dict[str, List[str]], operation_id="get_deduction_filters_v1")
async def get_deduction_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for deduction module
    
    **Returns:**
    - Business units, locations, departments
    - Deduction types for dropdown filters
    - Used for dropdown filters in deduction frontend
    """
    try:
        # Validate business path and access
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = DeductionService(db)
        filters = service.get_deduction_filters(business_id=business_id, current_user=current_user)
        
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deduction filters: {str(e)}"
        )


@router.post("/deduction-update", response_model=Dict[str, str], operation_id="update_deduction_employee_v1")
async def update_deduction_employee(
    business_id: int,
    update_data: DeductionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update deduction for an employee
    
    **Updates:**
    - Employee deduction amount
    - Comments and deduction type
    - Month-specific data
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = DeductionService(db)
        result = service.update_employee_deduction(
            employee_code=update_data.employee_code,
            month=update_data.month,
            amount=update_data.amount,
            comments=update_data.comments,
            deduction_type=update_data.deduction_type,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deduction: {str(e)}"
        )


@router.post("/deduction-copy-previous", response_model=Dict[str, Any])
async def copy_deductions_from_previous_period(
    business_id: int,
    copy_data: CopyFromPreviousPeriodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Copy deductions from previous period
    
    **Creates:**
    - Deduction records for target period
    - Based on source period data
    - Supports overwrite existing option
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = DeductionService(db)
        result = service.copy_from_previous_period(
            source_period=copy_data.source_period,
            target_period=copy_data.target_period,
            deduction_type=copy_data.deduction_type,
            overwrite_existing=copy_data.overwrite_existing,
            current_user=current_user,
            created_by=current_user.id,
            business_id=business_id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to copy from previous period: {str(e)}"
        )


@router.get("/deduction-export", operation_id="export_deduction_data_v1")
async def export_deduction_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    location: Optional[str] = Query(None),
    cost_center: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export deduction data as CSV
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = DeductionService(db)
        csv_content = service.export_deductions_csv(
            month=month,
            location=location,
            cost_center=cost_center,
            department=department,
            business_id=business_id
        )

        filename_month = month.replace('-', '_') if month else datetime.now().strftime('%Y%m%d')
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=deductions_{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export deduction data: {str(e)}"
        )


@router.post("/deduction-import", operation_id="import_deduction_data_v1")
async def import_deduction_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    overwrite_existing: bool = Query(False),
    consider_arrear: bool = Query(False),
    csv_data: str = Body(..., media_type="text/plain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import deduction data from CSV content
    
    **Accepts:**
    - CSV content as string
    - Expected columns: Employee Code, Amount, Comments, Deduction Type
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = DeductionService(db)
        result = service.import_deductions_csv(
            csv_content=csv_data,
            month=month,
            overwrite_existing=overwrite_existing,
            consider_arrear=consider_arrear,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import deduction data: {str(e)}"
        )


@router.get("/deduction-details/{employee_code}")
async def get_employee_deduction_details(
    business_id: int,
    employee_code: str,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get deduction details for an employee
    
    **Returns:**
    - Employee deduction details
    - Deduction history for the month
    - Total deduction amount
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = DeductionService(db)
        details = service.get_employee_deduction_details(
            employee_code=employee_code,
            month=month,
            business_id=business_id
        )
        
        return details
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get employee deduction details: {str(e)}"
        )




# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  4. INCOME TAX (TDS)                                                          ║
# ║  Frontend Menu Position: #4                                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝



@router.get("/incometaxtds", response_model=List[IncomeTaxTDSResponse])
async def get_income_tax_tds(
    business_id: int,
    employee_id: Optional[int] = Query(None),
    financial_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get income tax TDS records
    
    **Returns:**
    - List of TDS records
    - Employee details
    - Tax amounts and periods
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Mock data for income tax TDS
        mock_tds = []
        
        # Get employees for mock data
        employee_query = db.query(Employee).filter(Employee.employee_status == "active")
        if business_id:
            employee_query = employee_query.filter(Employee.business_id == business_id)
        if employee_id:
            employee_query = employee_query.filter(Employee.id == employee_id)
        
        employees = employee_query.limit(10).all()
        
        for i, employee in enumerate(employees):
            mock_tds.append(IncomeTaxTDSResponse(
                id=i + 1,
                employee_id=employee.id,
                employee_name=employee.full_name,
                financial_year="2024-25",
                tds_amount=Decimal("2500.00"),
                tax_period="December 2024",
                challan_number=f"TDS{1000 + i}",
                payment_date=date.today(),
                status="paid",
                created_at=datetime.now()
            ))
        
        return mock_tds
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch income tax TDS: {str(e)}"
        )


# ============================================================================
# EXTRA HOURS ENDPOINTS - Frontend Compatible
# ============================================================================

@router.get("/extrahours-employees", response_model=List[ExtraHoursEmployeeResponse])
async def get_extrahours_employees(
    business_id: int,
    month: str = Query("AUG-2025", pattern=r"^[A-Z]{3}-\d{4}$", description="Month in format 'AUG-2025'"),
    business_unit: Optional[str] = Query(None, max_length=100),
    location: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(None, max_length=100),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1, le=1000),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with extra hours data for frontend table
    
    **Returns:**
    - Employee list with extra hours information
    - Supports filtering by business unit, location, department
    - Supports search by employee name or code
    - Supports pagination
    """
    try:
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = ExtraHoursService(db)
        employees = service.get_employees_with_extra_hours(
            month=month,
            business_unit=business_unit,
            location=location,
            department=department,
            search=search,
            page=page,
            size=size,
            current_user=current_user
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch extra hours employees: {str(e)}"
        )


@router.get("/extrahours-filters", response_model=ExtraHoursFiltersResponse)
async def get_extrahours_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for extra hours module
    
    **Returns:**
    - Business units, locations, departments
    - Used for dropdown filters in extra hours frontend
    """
    try:
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraHoursService(db)
        filters = service.get_filter_options(current_user=current_user)
        
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch extra hours filters: {str(e)}"
        )


@router.get("/extrahours-search", response_model=List[ExtraHoursSearchResponse])
async def search_extrahours_employees(
    business_id: int,
    search: str = Query(..., min_length=1, max_length=100, description="Search term for employee name"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Search employees for autocomplete in extra hours module
    
    **Returns:**
    - List of employee names matching search term
    - Used for autocomplete dropdown
    """
    try:
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = ExtraHoursService(db)
        employees = service.search_employees(search, current_user=current_user, limit=limit)
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search extra hours employees: {str(e)}"
        )


@router.post("/extrahours-create", response_model=ExtraHoursCreateResponse)
async def create_extrahours_record(
    business_id: int,
    request: ExtraHoursCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create extra hours record for an employee
    
    **Creates:**
    - New extra hours record
    - Hours worked and hourly rate
    - Total amount calculation
    """
    try:
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = ExtraHoursService(db)
        result = service.create_extra_hours_record(
            employee_code=request.employee_code,
            work_date=request.work_date,
            extra_hours=request.extra_hours,
            hourly_rate=request.hourly_rate,
            reason=request.reason,
            current_user=current_user,
            created_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create extra hours record: {str(e)}"
        )


@router.get("/extrahours-export")
async def export_extrahours_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export extra hours data as CSV
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)

        # Use service layer
        service = ExtraHoursService(db)
        csv_content = service.generate_csv_export(
            month=month,
            location=location,
            department=department,
            current_user=current_user
        )

        filename_month = month.replace('-', '_') if month else datetime.now().strftime('%Y%m%d')
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=extra_hours_{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export extra hours data: {str(e)}"
        )


@router.post("/extrahours-import", response_model=ExtraHoursImportResponse)
async def import_extrahours_data(
    business_id: int,
    request: ExtraHoursImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import extra hours data from CSV content
    
    **Accepts:**
    - CSV content as string
    - Expected columns: Employee Code, Extra Hours, Hourly Rate, Reason
    """
    try:
        from app.services.extra_hours_service import ExtraHoursService
        
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = ExtraHoursService(db)
        result = service.import_csv_data(
            csv_content=request.csv_data,
            month=request.month,
            overwrite_existing=request.overwrite_existing,
            current_user=current_user,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import extra hours data: {str(e)}"
        )


@router.put("/extrahours/{extra_hours_id}")
async def update_extra_hours(
    business_id: int,
    extra_hours_id: int,
    extra_hours_data: ExtraHoursCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update extra hours record
    
    **Updates:**
    - Extra hours details
    - Hours worked and hourly rate
    - Total amount calculation
    - Approval status
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)

        # Verify the extra hours record exists and belongs to user's business
        from app.models.datacapture import ExtraHour
        extra_hours_record = db.query(ExtraHour).filter(
            ExtraHour.id == extra_hours_id
        ).first()
        
        if not extra_hours_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extra hours record {extra_hours_id} not found"
            )
        
        # Verify business ownership
        if extra_hours_record.business_id != business_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extra hours record {extra_hours_id} not found"
            )
        
        # Update the record using service
        from app.services.extra_hours_service import ExtraHoursService
        service = ExtraHoursService(db)
        result = service.create_extra_hours_record(
            employee_code=extra_hours_data.employee_code,
            work_date=extra_hours_data.work_date,
            extra_hours=extra_hours_data.extra_hours,
            hourly_rate=extra_hours_data.hourly_rate,
            reason=extra_hours_data.reason,
            current_user=current_user,
            created_by=current_user.id
        )
        
        return {
            "message": f"Extra hours record updated successfully",
            "extra_hours_id": str(extra_hours_id),
            "updated_by": current_user.email,
            "updated_at": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update extra hours record: {str(e)}"
        )


@router.delete("/extrahours/{extra_hours_id}", response_model=Dict[str, str])
async def delete_extra_hours(
    business_id: int,
    extra_hours_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete extra hours record
    
    **Deletes:**
    - Extra hours record
    - Maintains audit trail
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_user, db)
        
        # Verify the extra hours record exists and belongs to user's business
        from app.models.datacapture import ExtraHour
        extra_hours_record = db.query(ExtraHour).filter(
            ExtraHour.id == extra_hours_id
        ).first()
        
        if not extra_hours_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extra hours record {extra_hours_id} not found"
            )
        
        # Verify business ownership
        if extra_hours_record.business_id != business_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extra hours record {extra_hours_id} not found"
            )
        
        # Delete the record
        db.delete(extra_hours_record)
        db.commit()
        
        return {
            "message": f"Extra hours record {extra_hours_id} deleted successfully",
            "extra_hours_id": str(extra_hours_id),
            "deleted_by": current_user.email,
            "deleted_at": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete extra hours record: {str(e)}"
        )


@router.get("/loans")
async def get_loans(
    business_id: int,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    loan_type: Optional[str] = Query(None),
    loan_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employee loans with filters
    
    **Frontend Compatible Fields:**
    - id, employee, designation, department
    - loanAmount, issueDate, interestMethod
    - CRUD operations support
    """
    try:
        from app.services.loan_service import LoanService
        from fastapi import HTTPException, status
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        loans = loan_service.get_loans_list(
            current_user=current_user,
            from_date=from_date,
            to_date=to_date,
            search=search,
            employee_id=employee_id,
            loan_type=loan_type,
            status=loan_status,
            page=page,
            size=size
        )
        
        return loans
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch loans: {str(e)}"
        )


@router.get("/loans-filters")
async def get_loan_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get filter options for loans"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        filters = loan_service.get_loan_filters(current_user=current_user)
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch loan filters: {str(e)}"
        )


@router.get("/loans-search")
async def search_loan_employees(
    business_id: int,
    search: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search employees for loan assignment"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        employees = loan_service.search_employees(
            search=search,
            current_user=current_user,
            limit=limit
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search employees: {str(e)}"
        )


@router.get("/loans-export-csv")
async def export_loans_csv(
    business_id: int,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    loan_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Export loans to CSV"""
    try:
        from app.services.loan_service import LoanService
        from fastapi.responses import Response
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        csv_content = loan_service.export_loans_csv(
            current_user=current_user,
            from_date=from_date,
            to_date=to_date,
            search=search,
            loan_type=loan_type,
            status=status
        )
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=loans_export.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export loans: {str(e)}"
        )


@router.get("/loans/{loan_id}")
async def get_loan_details(
    business_id: int,
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get detailed loan information"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        loan = loan_service.get_loan_details(loan_id, business_id=business_id)
        
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        return loan
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch loan details: {str(e)}"
        )


class LoanRequest(BaseModel):
    """Loan create/update request with validation"""
    employee_id: int = Field(..., gt=0, description="Employee ID")
    loan_type: str = Field(..., min_length=1, max_length=100, description="Loan type")
    loan_amount: float = Field(..., gt=0, description="Loan amount must be greater than 0")
    interest_rate: float = Field(0.0, ge=0, le=100, description="Interest rate percentage (0-100)")
    tenure_months: int = Field(..., gt=0, le=360, description="Tenure in months (1-360)")
    loan_date: date = Field(..., description="Loan issue date")
    first_emi_date: date = Field(..., description="First EMI date")
    purpose: Optional[str] = Field(None, max_length=500, description="Loan purpose")
    guarantor_name: Optional[str] = Field(None, max_length=255, description="Guarantor name")
    guarantor_relation: Optional[str] = Field(None, max_length=100, description="Guarantor relation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": 1,
                "loan_type": "Personal Loan",
                "loan_amount": 50000.00,
                "interest_rate": 10.5,
                "tenure_months": 24,
                "loan_date": "2024-01-01",
                "first_emi_date": "2024-02-01",
                "purpose": "Home renovation",
                "guarantor_name": "John Doe",
                "guarantor_relation": "Brother"
            }
        }


@router.post("/loans")
async def create_loan(
    business_id: int,
    loan_data: LoanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create new loan record"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        created_by = getattr(current_user, 'id', None)
        loan_service = LoanService(db)
        
        loan = loan_service.create_loan(
            loan_data=loan_data.dict(),
            business_id=business_id,
            created_by=created_by
        )
        
        return loan
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create loan: {str(e)}"
        )


@router.put("/loans/{loan_id}")
async def update_loan(
    business_id: int,
    loan_id: int,
    loan_data: LoanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update loan record"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        loan = loan_service.update_loan(
            loan_id=loan_id,
            loan_data=loan_data.dict(),
            business_id=business_id
        )
        
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        return loan
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update loan: {str(e)}"
        )


@router.delete("/loans/{loan_id}", operation_id="delete_loan_v1")
async def delete_loan(
    business_id: int,
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete loan record"""
    try:
        from app.services.loan_service import LoanService
        
        validate_business_access(business_id, current_user, db)
        loan_service = LoanService(db)
        
        success = loan_service.delete_loan(loan_id, business_id=business_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        return {"message": "Loan deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete loan: {str(e)}"
        )


@router.get("/itDeclarations")
async def get_it_declarations(
    business_id: int,
    financial_year: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get IT declarations with filters
    
    **Frontend Compatible Fields:**
    - employee_name, employee_code, financial_year
    - status, total_80c, declaration amounts
    - CRUD operations support
    """
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        declarations = it_declaration_service.get_declarations_list(
            business_id=business_id,
            financial_year=financial_year,
            employee_id=employee_id,
            status=status,
            search=search,
            page=page,
            size=size
        )
        
        total_count = it_declaration_service.get_declarations_total_count(
            business_id=business_id,
            financial_year=financial_year,
            employee_id=employee_id,
            status=status,
            search=search
        )
        
        return {
            "items": declarations,
            "total": total_count,
            "page": page,
            "size": size,
            "pages": (total_count + size - 1) // size
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch IT declarations: {str(e)}"
        )


@router.get("/itDeclarations-filters")
async def get_it_declaration_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get filter options for IT declarations"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        filters = it_declaration_service.get_declaration_filters(current_user=current_user)
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch IT declaration filters: {str(e)}"
        )


@router.get("/itDeclarations-search")
async def search_it_declaration_employees(
    business_id: int,
    search: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search employees for IT declaration assignment"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        employees = it_declaration_service.search_employees(
            search=search,
            current_user=current_user,
            limit=limit
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search employees: {str(e)}"
        )


@router.get("/itDeclarations-employee/{employee_id}")
async def get_employee_it_declaration(
    business_id: int,
    employee_id: int,
    financial_year: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get or create IT declaration for employee and financial year"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        declaration = it_declaration_service.get_employee_declaration(
            employee_id=employee_id,
            financial_year=financial_year,
            business_id=business_id
        )
        
        return declaration
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee IT declaration: {str(e)}"
        )


@router.put("/itDeclarations-field")
async def update_declaration_field(
    business_id: int,
    employee_id: int = Body(...),
    financial_year: str = Body(...),
    field_name: str = Body(...),
    field_value: Any = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a specific field in IT declaration"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        result = it_declaration_service.update_declaration_field(
            employee_id=employee_id,
            financial_year=financial_year,
            field_name=field_name,
            field_value=field_value,
            business_id=business_id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update declaration field: {str(e)}"
        )


@router.post("/itDeclarations-submit")
async def submit_it_declaration(
    business_id: int,
    employee_id: int = Body(...),
    financial_year: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Submit IT declaration for approval"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        result = it_declaration_service.submit_declaration(
            employee_id=employee_id,
            financial_year=financial_year,
            business_id=business_id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit declaration: {str(e)}"
        )


@router.get("/itDeclarations-limits")
async def get_deduction_limits(
    business_id: int,
    financial_year: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get deduction limits for a financial year"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        limits = it_declaration_service.get_deduction_limits(financial_year)
        return limits
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deduction limits: {str(e)}"
        )


@router.get("/itDeclarations-export-csv")
async def export_it_declarations_csv(
    business_id: int,
    financial_year: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Export IT declarations to CSV"""
    try:
        from app.services.it_declaration_service import ITDeclarationService
        from fastapi.responses import Response
        
        validate_business_access(business_id, current_user, db)
        it_declaration_service = ITDeclarationService(db)
        
        csv_content = it_declaration_service.export_declarations_csv(
            business_id=business_id,
            financial_year=financial_year,
            employee_id=employee_id,
            status=status,
            search=search
        )
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=it_declarations_export.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export IT declarations: {str(e)}"
        )


# ============================================================================
# TDS CHALLANS ENDPOINTS
# ============================================================================

@router.get("/tdschallans", response_model=List[TDSChallansResponse])
async def get_tds_challans(
    business_id: int,
    payment_date_from: Optional[date] = Query(None),
    payment_date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS challans
    
    **Returns:**
    - List of TDS challans
    - Payment details
    - Bank information
    
    **Note:** This is a legacy endpoint. Use /tdschallans/load for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return empty list for mock endpoint - real data should use /tdschallans/load
        return []
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch TDS challans: {str(e)}"
        )


class TDSChallanRequest(BaseModel):
    """TDS challan create/update request"""
    challan_number: str
    payment_date: date
    total_amount: float
    bank_name: str
    branch_code: Optional[str] = None
    employees_count: int
    status: str = "paid"


@router.post("/tdschallans", response_model=TDSChallansResponse)
async def create_tds_challan(
    business_id: int,
    challan_data: TDSChallanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create new TDS challan
    
    **Creates:**
    - New TDS challan record
    - Payment details and bank information
    - Employee count tracking
    
    **Note:** This is a legacy endpoint. Use /tdschallans/save-month for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return error - use /tdschallans/save-month instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use /tdschallans/save-month instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create TDS challan: {str(e)}"
        )


@router.put("/tdschallans/{challan_id}", response_model=TDSChallansResponse)
async def update_tds_challan(
    business_id: int,
    challan_id: int,
    challan_data: TDSChallanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update TDS challan
    
    **Updates:**
    - TDS challan details
    - Payment information
    - Bank details
    
    **Note:** This is a legacy endpoint. Use /tdschallans/save-month for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        
        # Return error - use /tdschallans/save-month instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use /tdschallans/save-month instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update TDS challan: {str(e)}"
        )


@router.delete("/tdschallans/{challan_id}", response_model=Dict[str, str])
async def delete_tds_challan(
    business_id: int,
    challan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete TDS challan
    
    **Deletes:**
    - TDS challan record
    - Maintains audit trail
    
    **Note:** This is a legacy endpoint. Use /tdschallans/month/{month} DELETE for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        
        # Return error - use DELETE /tdschallans/month/{month} instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use DELETE /tdschallans/month/{month} instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete TDS challan: {str(e)}"
        )


# ============================================================================
# TDS CHALLANS APIs - Frontend Compatible (Month-based)
# ============================================================================
# TDS CHALLANS APIs - Frontend Compatible
# ============================================================================


class TDSChallanSaveRequest(BaseModel):
    """TDS challan save request"""
    financial_year: str = Field(..., description="Financial year in format '2024-25'")
    month: str = Field(..., description="Month in format 'APR-2024'")
    bsrcode: str = Field("", description="BSR code")
    date: str = Field("", description="Deposit date in YYYY-MM-DD format")
    challan: str = Field("", description="Challan serial number")


@router.get("/tdschallans/test-simple")
async def test_simple_endpoint(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Simple test endpoint"""
    validate_business_access(business_id, current_user, db)
    return {"message": "TDS Challans API is working", "status": "ok"}


@router.get("/tdschallans/load", response_model=Dict[str, Any])
async def load_tds_challans_for_year(
    business_id: int,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Load TDS challans for a financial year
    
    **Returns:**
    - All 12 months of financial year
    - Existing challan data where available
    - Empty entries for months without data
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSChallanService(db)
        result = service.get_challans_by_financial_year(
            financial_year=financial_year,
            business_id=business_id
        )
        
        # Return raw result without Pydantic validation for now
        return result
    
    except Exception as e:
        # Return error info
        return {
            "error": str(e),
            "financial_year": financial_year,
            "total_months": 12,
            "challans": []
        }


@router.post("/tdschallans/save-month", response_model=Dict[str, Any])
async def save_tds_challan_month(
    business_id: int,
    challan_data: TDSChallanSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Save TDS challan data for a specific month
    
    **Saves:**
    - BSR code, deposit date, and challan number
    - Creates or updates existing record
    - Validates date format and business rules
    """
    try:
        validate_business_access(business_id, current_user, db)
        created_by = current_user.id
        
        # Use service layer
        service = TDSChallanService(db)
        result = service.save_challan_month(
            financial_year=challan_data.financial_year,
            month=challan_data.month,
            bsrcode=challan_data.bsrcode,
            deposit_date=challan_data.date,
            challan_number=challan_data.challan,
            business_id=business_id,
            created_by=created_by
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save TDS challan: {str(e)}"
        )


@router.get("/tdschallans/month/{month}", response_model=Optional[TDSChallanMonthResponse])
async def get_tds_challan_by_month(
    business_id: int,
    month: str,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS challan data for a specific month
    
    **Returns:**
    - Challan data for the specified month
    - BSR code, deposit date, and challan number
    - Returns null if no data found for the month
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSChallanService(db)
        result = service.get_challan_by_month(
            financial_year=financial_year,
            month=month,
            business_id=business_id
        )
        
        if result:
            return TDSChallanMonthResponse(
                month=result["month"],
                bsrcode=result["bsrcode"],
                date=result["date"],
                challan=result["challan"],
                id=result.get("id"),
                created_at=result.get("created_at"),
                updated_at=result.get("updated_at")
            )
        
        return None
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get TDS challan by month: {str(e)}"
        )


@router.delete("/tdschallans/month/{month}", response_model=Dict[str, Any])
async def delete_tds_challan_by_month(
    business_id: int,
    month: str,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete TDS challan data for a specific month
    
    **Deletes:**
    - Challan record for the specified month
    - Maintains audit trail
    - Returns confirmation message
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSChallanService(db)
        result = service.delete_challan_month(
            financial_year=financial_year,
            month=month,
            business_id=business_id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete TDS challan: {str(e)}"
        )


@router.get("/tdschallans/summary", response_model=Dict[str, Any])
async def get_tds_challans_summary(
    business_id: int,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS challans summary for a financial year
    
    **Returns:**
    - Summary statistics for the financial year
    - Total, completed, and pending months
    - Completion percentage
    """
    try:
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = TDSChallanService(db)
        result = service.get_challan_summary(
            financial_year=financial_year,
            business_id=business_id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get TDS challans summary: {str(e)}"
        )


@router.get("/tdsreturns", response_model=List[TDSReturnsResponse])
async def get_tds_returns(
    business_id: int,
    financial_year: Optional[str] = Query(None),
    quarter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS returns
    
    **Returns:**
    - List of TDS returns
    - Filing details
    - Acknowledgment information
    
    **Note:** This is a legacy endpoint. Use /tdsreturns/load for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return empty list for mock endpoint - real data should use /tdsreturns/load
        return []
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch TDS returns: {str(e)}"
        )


class TDSReturnRequest(BaseModel):
    """TDS return create/update request"""
    return_type: str
    financial_year: str
    quarter: str
    total_tds_amount: float
    filing_date: Optional[date] = None
    acknowledgment_number: Optional[str] = None
    status: str = "filed"


@router.post("/tdsreturns", response_model=TDSReturnsResponse)
async def create_tds_return(
    business_id: int,
    return_data: TDSReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create new TDS return
    
    **Creates:**
    - New TDS return record
    - Filing details and acknowledgment
    - Quarter and financial year tracking
    
    **Note:** This is a legacy endpoint. Use /tdsreturns/save-quarter for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return error - use /tdsreturns/save-quarter instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use /tdsreturns/save-quarter instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create TDS return: {str(e)}"
        )


@router.put("/tdsreturns/{return_id}", response_model=TDSReturnsResponse)
async def update_tds_return(
    business_id: int,
    return_id: int,
    return_data: TDSReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update TDS return
    
    **Updates:**
    - TDS return details
    - Filing information
    - Acknowledgment details
    
    **Note:** This is a legacy endpoint. Use /tdsreturns/save-quarter for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return error - use /tdsreturns/save-quarter instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use /tdsreturns/save-quarter instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update TDS return: {str(e)}"
        )


@router.delete("/tdsreturns/{return_id}", response_model=Dict[str, str])
async def delete_tds_return(
    business_id: int,
    return_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete TDS return
    
    **Deletes:**
    - TDS return record
    - Maintains audit trail
    
    **Note:** This is a legacy endpoint. Use DELETE /tdsreturns/quarter/{quarter} for production.
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Return error - use DELETE /tdsreturns/quarter/{quarter} instead
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This endpoint is deprecated. Please use DELETE /tdsreturns/quarter/{quarter} instead."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete TDS return: {str(e)}"
        )


# ============================================================================
# TDS RETURNS APIs - Frontend Compatible
# ============================================================================

class TDSReturnQuarterResponse(BaseModel):
    """TDS return quarter response matching frontend expectations"""
    quarter: str  # Q1, Q2, Q3, Q4
    receipt_number: str  # Acknowledgment/receipt number
    id: Optional[int] = None
    return_type: Optional[str] = None
    filing_date: Optional[str] = None
    total_tds_amount: Optional[float] = None
    is_filed: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TDSReturnYearResponse(BaseModel):
    """TDS return year response with all quarters"""
    financial_year: str
    total_quarters: int
    returns: List[TDSReturnQuarterResponse]


class TDSReturnSaveRequest(BaseModel):
    """TDS return save request"""
    financial_year: str = Field(..., description="Financial year in format '2024-25'")
    quarter: str = Field(..., description="Quarter (Q1, Q2, Q3, Q4)")
    receipt_number: str = Field(..., description="Acknowledgment/receipt number")
    return_type: str = Field("24Q", description="Return type (24Q, 26Q, etc.)")
    filing_date: Optional[str] = Field(None, description="Filing date in YYYY-MM-DD format")


@router.get("/tdsreturns/load", response_model=TDSReturnYearResponse)
async def load_tds_returns_for_year(
    business_id: int,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Load TDS returns for a financial year
    
    **Returns:**
    - All 4 quarters of financial year
    - Existing return data where available
    - Empty entries for quarters without data
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSReturnService(db)
        result = service.get_returns_by_financial_year(
            financial_year=financial_year,
            business_id=business_id
        )
        
        # Convert to response format
        return_responses = []
        for return_data in result["returns"]:
            return_responses.append(TDSReturnQuarterResponse(
                quarter=return_data["quarter"],
                receipt_number=return_data["receipt_number"],
                id=return_data.get("id"),
                return_type=return_data.get("return_type"),
                filing_date=return_data.get("filing_date"),
                total_tds_amount=return_data.get("total_tds_amount"),
                is_filed=return_data.get("is_filed"),
                created_at=return_data.get("created_at"),
                updated_at=return_data.get("updated_at")
            ))
        
        return TDSReturnYearResponse(
            financial_year=result["financial_year"],
            total_quarters=result["total_quarters"],
            returns=return_responses
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load TDS returns: {str(e)}"
        )


@router.post("/tdsreturns/save-quarter", response_model=Dict[str, Any])
async def save_tds_return_quarter(
    business_id: int,
    return_data: TDSReturnSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Save TDS return data for a specific quarter
    
    **Saves:**
    - Receipt/acknowledgment number
    - Return type and filing date
    - Creates or updates existing record
    """
    try:
        validate_business_access(business_id, current_user, db)
        created_by = current_user.id
        # Use service layer
        service = TDSReturnService(db)
        result = service.save_return_quarter(
            financial_year=return_data.financial_year,
            quarter=return_data.quarter,
            receipt_number=return_data.receipt_number,
            return_type=return_data.return_type,
            filing_date=return_data.filing_date,
            business_id=business_id,
            created_by=created_by
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save TDS return: {str(e)}"
        )


@router.get("/tdsreturns/quarter/{quarter}", response_model=Optional[TDSReturnQuarterResponse])
async def get_tds_return_by_quarter(
    business_id: int,
    quarter: str,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS return data for a specific quarter
    
    **Returns:**
    - Return data for the specified quarter
    - Receipt number and filing details
    - Returns null if no data found for the quarter
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSReturnService(db)
        result = service.get_return_by_quarter(
            financial_year=financial_year,
            quarter=quarter,
            business_id=business_id
        )
        
        if result:
            return TDSReturnQuarterResponse(
                quarter=result["quarter"],
                receipt_number=result["receipt_number"],
                id=result.get("id"),
                return_type=result.get("return_type"),
                filing_date=result.get("filing_date"),
                total_tds_amount=result.get("total_tds_amount"),
                is_filed=result.get("is_filed"),
                created_at=result.get("created_at"),
                updated_at=result.get("updated_at")
            )
        
        return None
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get TDS return by quarter: {str(e)}"
        )


@router.delete("/tdsreturns/quarter/{quarter}", response_model=Dict[str, Any])
async def delete_tds_return_by_quarter(
    business_id: int,
    quarter: str,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete TDS return data for a specific quarter
    
    **Deletes:**
    - Return record for the specified quarter
    - Maintains audit trail
    - Returns confirmation message
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSReturnService(db)
        result = service.delete_return_quarter(
            financial_year=financial_year,
            quarter=quarter,
            business_id=business_id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete TDS return: {str(e)}"
        )


@router.get("/tdsreturns/test-simple")
async def test_simple_tds_endpoint(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    return {"message": "TDS Returns API is working", "status": "ok"}


@router.get("/tdsreturns/summary", response_model=Dict[str, Any])
async def get_tds_returns_summary(
    business_id: int,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get TDS returns summary for a financial year
    
    **Returns:**
    - Summary statistics for the financial year
    - Total, filed, and pending quarters
    - Completion percentage and amounts
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = TDSReturnService(db)
        result = service.get_returns_summary(
            financial_year=financial_year,
            business_id=business_id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get TDS returns summary: {str(e)}"
        )


@router.get("/tdsreturns/download/{quarter}")
async def download_tds_return_receipt(
    business_id: int,
    quarter: str,
    financial_year: str = Query(..., description="Financial year in format '2024-25'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Download TDS return receipt for a quarter
    
    **Returns:**
    - Text file with return details
    - Quarter, receipt number, and filing information
    - Downloadable content for records
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        validate_business_access(business_id, current_user, db)
        
        # Use service layer
        service = TDSReturnService(db)
        result = service.download_return_receipt(
            financial_year=financial_year,
            quarter=quarter,
            business_id=business_id
        )
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(result["content"].encode('utf-8')),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={result['filename']}"}
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download TDS return receipt: {str(e)}"
        )


@router.get("", response_model=DataCaptureDashboardResponse)
async def get_datacapture_dashboard(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get data capture dashboard with import/export statistics
    
    Returns:
    - Import/export statistics
    - Recent activities
    - Available templates
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Mock data capture data
        datacapture_data = {
            "statistics": {
                "total_imports": 25,
                "successful_imports": 23,
                "failed_imports": 2,
                "total_exports": 15
            },
            "recent_activities": [
                {
                    "type": "import",
                    "file_name": "employees_batch_1.xlsx",
                    "status": "Success",
                    "records": 50,
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "export",
                    "file_name": "attendance_report.csv",
                    "status": "Success",
                    "records": 1000,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "available_templates": [
                {
                    "name": "Employee Import Template",
                    "file_name": "employee_template.xlsx"
                },
                {
                    "name": "Attendance Import Template", 
                    "file_name": "attendance_template.xlsx"
                }
            ]
        }
        
        return datacapture_data
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get data capture dashboard: {str(e)}"
        )


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_data(
    business_id: int,
    import_request: BulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Bulk import data from file
    
    Supports:
    - Employee data import
    - Attendance data import
    - Salary data import
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Mock bulk import processing
        import_result = {
            "import_id": f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "processing",
            "total_records": import_request.total_records,
            "processed_records": 0,
            "successful_records": 0,
            "failed_records": 0,
            "errors": [],
            "started_at": datetime.now().isoformat()
        }
        
        return BulkImportResponse(**import_result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk import: {str(e)}"
        )

# ============================================================================
# EXTRA DAYS APIs - Frontend Compatible with Repository/Service Pattern
# ============================================================================

@router.get("/extradays-employees", response_model=List[ExtraDaysEmployeeResponse])
async def get_extradays_employees(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with extra days data for frontend table
    
    **Returns:**
    - Employee list with extra days information
    - Extra days, arrear, OT, and comments fields
    - Supports filtering by business unit, location, department
    - Supports search by employee name
    - Supports pagination
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        employees = service.get_employees_with_extra_days(
            month=month,
            business_unit=business_unit,
            location=location,
            department=department,
            search=search,
            page=page,
            size=size,
            business_id=business_id,
            current_user=current_user
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch extra days employees: {str(e)}"
        )


@router.get("/extradays-filters", response_model=ExtraDaysFiltersResponse)
async def get_extradays_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for extra days module
    
    **Returns:**
    - Business units, locations, departments
    - Used for dropdown filters in extra days frontend
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        filters = service.get_filter_options(None, current_user=current_user)
        
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch extra days filters: {str(e)}"
        )


@router.post("/extradays-update", response_model=Dict[str, str])
async def update_extradays_employee(
    business_id: int,
    update_data: ExtraDaysUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update extra days for an employee
    
    **Updates:**
    - Employee extra days, arrear, OT amounts
    - Comments
    - Month-specific data
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        result = service.update_employee_extra_days(
            update_data=update_data,
            business_id=business_id,
            created_by=current_user.id,
            current_user=current_user
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update extra days: {str(e)}"
        )


@router.get("/extradays-search", response_model=List[ExtraDaysSearchResponse])
async def search_extradays_employees(
    business_id: int,
    search: str = Query(..., description="Search term for employee name"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Search employees for autocomplete in extra days module
    
    **Returns:**
    - List of employee names matching search term
    - Used for autocomplete dropdown
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        employees = service.search_employees(search, business_id, limit)
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search employees: {str(e)}"
        )


@router.get("/extradays-export/{employee_id}", response_model=ExtraDaysExportResponse)
async def export_extradays_employee_data(
    business_id: int,
    employee_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    extra: float = Query(0.0),
    arrear: float = Query(0.0),
    ot: float = Query(0.0),
    comments: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export employee extra days data as PDF (returns JSON for frontend PDF generation)
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        export_data = service.export_employee_data(
            employee_id=employee_id,
            month=month,
            extra=extra,
            arrear=arrear,
            ot=ot,
            comments=comments,
            business_id=business_id
        )
        
        return export_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export employee extra days data: {str(e)}"
        )


@router.get("/extradays-export-all", response_model=ExtraDaysExportAllResponse)
async def export_all_extradays_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export all employees extra days data (returns JSON for frontend PDF generation)
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        export_data = service.export_all_employees_data(month, business_id)
        
        return export_data
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export all extra days data: {str(e)}"
        )


@router.get("/extradays-export-csv")
async def export_extradays_csv(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export extra days data as CSV
    """
    try:
        from fastapi.responses import StreamingResponse
        from app.services.extra_days_service import ExtraDaysService
        import io
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        csv_content = service.generate_csv_export(
            month=month,
            location=location,
            department=department,
            business_id=business_id
        )
        
        # Return as streaming response
        filename_month = month.replace('-', '_') if month else datetime.now().strftime('%Y%m%d')
        if csv_content is None:
            csv_content = ""
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=extra_days_{filename_month}.csv"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export extra days CSV: {str(e)}"
        )


@router.post("/extradays-import", response_model=ExtraDaysImportResponse)
async def import_extradays_data(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    overwrite_existing: bool = Query(False),
    csv_data: str = Body(..., media_type="text/plain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Import extra days data from CSV content
    
    **Accepts:**
    - CSV content as string
    - Expected columns: Employee Code, Extra Days, Arrear, OT, Comments
    """
    try:
        from app.services.extra_days_service import ExtraDaysService
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = ExtraDaysService(db)
        result = service.import_csv_data(
            csv_content=csv_data,
            month=month,
            overwrite_existing=overwrite_existing,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import extra days data: {str(e)}"
        )


# ============================================================================
# INCOME TAX TDS APIs - Frontend Compatible
# ============================================================================

class IncomeTaxTDSEmployeeResponse(BaseModel):
    """Income tax TDS employee response matching frontend expectations"""
    id: str  # Employee code (LEV098, etc.)
    name: str
    designation: str
    status: str = "Enabled"
    tds_amount: float = 0.0


@router.get("/incometaxtds-employees", response_model=List[IncomeTaxTDSEmployeeResponse])
async def get_incometaxtds_employees(
    business_id: int,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    business_unit: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get employees with income tax TDS data for frontend table
    
    **Returns:**
    - Employee list with TDS information
    - Employee ID, name, designation, status, TDS amount
    - Supports filtering by business unit, location, department
    - Supports search by employee name
    - Supports pagination
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        employees = service.get_incometaxtds_employees(
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
        
        # Convert to response format
        response_data = []
        for emp in employees:
            response_data.append(IncomeTaxTDSEmployeeResponse(
                id=emp["id"],
                name=emp["name"],
                designation=emp["designation"],
                status=emp["status"],
                tds_amount=emp["tds_amount"]
            ))
        
        return response_data
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch income tax TDS employees: {str(e)}"
        )


@router.get("/incometaxtds-filters", response_model=Dict[str, List[str]])
async def get_incometaxtds_filters(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get filter options for income tax TDS module
    
    **Returns:**
    - Business units, locations, departments
    - Used for dropdown filters in income tax TDS frontend
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        filters = service.get_incometaxtds_filters(business_id=business_id, current_user=current_user)
        
        return filters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch income tax TDS filters: {str(e)}"
        )


class IncomeTaxTDSUpdateRequest(BaseModel):
    """Income tax TDS update request"""
    employee_code: str
    month: str  # Format: "AUG-2025"
    tds_amount: float


@router.post("/incometaxtds-update", response_model=Dict[str, str])
async def update_incometaxtds_employee(
    business_id: int,
    update_data: IncomeTaxTDSUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update income tax TDS for an employee
    
    **Updates:**
    - Employee TDS amount
    - Month-specific data
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        result = service.update_employee_tds(
            employee_code=update_data.employee_code,
            month=update_data.month,
            tds_amount=update_data.tds_amount,
            business_id=business_id,
            updated_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update income tax TDS: {str(e)}"
        )


@router.delete("/incometaxtds-delete/{employee_code}")
async def delete_incometaxtds_employee(
    business_id: int,
    employee_code: str,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete income tax TDS for an employee
    
    **Deletes:**
    - Employee TDS record for specific month
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        result = service.delete_employee_tds(
            employee_code=employee_code,
            month=month,
            business_id=business_id
        )
        
        return {
            "message": result["message"],
            "employee_code": employee_code,
            "month": month,
            "deleted_by": current_user.email,
            "deleted_at": result["deleted_at"]
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # Check if it's a "not found" error
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete income tax TDS: {str(e)}"
        )


class CopyFromPreviousPeriodTDSRequest(BaseModel):
    """Copy from previous period TDS request"""
    copy_from: str = "AUG-2025"
    copy_to: str = "SEP-2025"


@router.post("/incometaxtds-copy-previous", response_model=Dict[str, Any])
async def copy_incometaxtds_from_previous_period(
    business_id: int,
    copy_data: CopyFromPreviousPeriodTDSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Copy income tax TDS data from previous period
    
    **Creates:**
    - TDS records copied from previous period
    - Applies to all employees with existing TDS data
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        result = service.copy_from_previous_period(
            source_period=copy_data.copy_from,
            target_period=copy_data.copy_to,
            overwrite_existing=True,
            business_id=business_id,
            created_by=current_user.id
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to copy income tax TDS from previous period: {str(e)}"
        )


@router.get("/incometaxtds-search")
async def search_incometaxtds_employees(
    business_id: int,
    search: str = Query(..., description="Search term for employee name"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Search employees for autocomplete in income tax TDS module
    
    **Returns:**
    - List of employee names matching search term
    - Used for autocomplete dropdown
    """
    try:
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        employees = service.search_employees(
            search=search,
            limit=limit,
            business_id=business_id
        )
        
        return employees
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search employees: {str(e)}"
        )


@router.get("/incometaxtds-export/{employee_code}")
async def export_incometaxtds_employee_data(
    business_id: int,
    employee_code: str,
    month: str = Query("AUG-2025", description="Month in format 'AUG-2025'"),
    tds_amount: float = Query(0.0, description="TDS amount"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Export employee TDS data as text file
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        validate_business_access(business_id, current_user, db)
        # Use service layer
        service = IncomeTaxTDSService(db)
        export_data = service.export_employee_data(
            employee_code=employee_code,
            month=month,
            business_id=business_id
        )
        
        # Create text content
        content = f"""
Employee Details
----------------
ID: {export_data["id"]}
Name: {export_data["name"]}
Designation: {export_data["designation"]}
Status: {export_data["status"]}
TDS Amount: {export_data["tds_amount"]}
"""
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(content.encode('utf-8')),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={export_data['name']}_TDS.txt"}
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # Check if it's a "not found" error
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export employee TDS data: {str(e)}"
        )


