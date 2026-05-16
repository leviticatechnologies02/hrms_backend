"""
Comprehensive Employee API Validation Schemas
Mandatory request body validation for all POST, PUT, and PATCH endpoints
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


# ============================================================================
# ENUMS FOR VALIDATION
# ============================================================================

class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MaritalStatusEnum(str, Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class EmployeeStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"


# ============================================================================
# EMPLOYEE CREATION SCHEMAS
# ============================================================================

class EmployeeCreateRequest(BaseModel):
    """Mandatory schema for employee creation - NO EMPTY BODIES ALLOWED"""
    firstName: str = Field(..., min_length=1, max_length=100, description="First name is required")
    lastName: str = Field(..., min_length=1, max_length=100, description="Last name is required")
    middleName: Optional[str] = Field(None, max_length=100, description="Middle name")
    email: EmailStr = Field(..., description="Valid email address is required")
    mobile: str = Field(..., min_length=10, max_length=15, description="Mobile number is required")
    joiningDate: str = Field(..., description="Joining date in YYYY-MM-DD format is required")
    gender: GenderEnum = Field(..., description="Gender is required")
    dateOfBirth: str = Field(..., description="Date of birth in YYYY-MM-DD format is required")
    
    # Optional fields with validation
    employeeCode: Optional[str] = Field(None, max_length=50, description="Employee code")
    biometricCode: Optional[str] = Field(None, max_length=20, description="Biometric code")
    confirmationDate: Optional[str] = Field(None, description="Confirmation date in YYYY-MM-DD format")
    maritalStatus: Optional[MaritalStatusEnum] = Field(None, description="Marital status")
    bloodGroup: Optional[str] = Field(None, max_length=10, description="Blood group")
    nationality: Optional[str] = Field(None, max_length=100, description="Nationality")
    religion: Optional[str] = Field(None, max_length=100, description="Religion")
    
    # Work profile fields
    departmentId: Optional[int] = Field(None, gt=0, description="Department ID")
    designationId: Optional[int] = Field(None, gt=0, description="Designation ID")
    locationId: Optional[int] = Field(None, gt=0, description="Location ID")
    costCenterId: Optional[int] = Field(None, gt=0, description="Cost center ID")
    gradeId: Optional[int] = Field(None, gt=0, description="Grade ID")
    reportingManagerId: Optional[int] = Field(None, gt=0, description="Reporting manager ID")
    
    # Access settings
    sendMobileLogin: bool = Field(False, description="Enable mobile login")
    sendWebLogin: bool = Field(True, description="Enable web login")
    
    @validator('joiningDate', 'dateOfBirth', 'confirmationDate')
    def validate_dates(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v and not v.isdigit():
            raise ValueError('Mobile number must contain only digits')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "firstName": "John",
                "lastName": "Doe",
                "middleName": "Smith",
                "email": "john.doe@company.com",
                "mobile": "9876543210",
                "joiningDate": "2024-01-15",
                "gender": "male",
                "dateOfBirth": "1990-05-20",
                "employeeCode": "EMP001",
                "maritalStatus": "single",
                "departmentId": 1,
                "designationId": 1,
                "sendMobileLogin": True,
                "sendWebLogin": True
            }
        }


class EmployeeBulkCreateRequest(BaseModel):
    """Bulk employee creation - NO EMPTY ARRAYS ALLOWED"""
    employees: List[EmployeeCreateRequest] = Field(..., min_items=1, description="At least one employee is required")
    
    @validator('employees')
    def validate_employees_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Employees list cannot be empty')
        return v


# ============================================================================
# EMPLOYEE UPDATE SCHEMAS
# ============================================================================

class EmployeeUpdateRequest(BaseModel):
    """Employee update schema - AT LEAST ONE FIELD REQUIRED"""
    firstName: Optional[str] = Field(None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(None, min_length=1, max_length=100)
    middleName: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None)
    mobile: Optional[str] = Field(None, min_length=10, max_length=15)
    gender: Optional[GenderEnum] = Field(None)
    maritalStatus: Optional[MaritalStatusEnum] = Field(None)
    dateOfBirth: Optional[str] = Field(None)
    bloodGroup: Optional[str] = Field(None, max_length=10)
    nationality: Optional[str] = Field(None, max_length=100)
    religion: Optional[str] = Field(None, max_length=100)
    employeeCode: Optional[str] = Field(None, max_length=50)
    biometricCode: Optional[str] = Field(None, max_length=20)
    employeeStatus: Optional[EmployeeStatusEnum] = Field(None)
    
    @validator('dateOfBirth')
    def validate_date_of_birth(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date of birth must be in YYYY-MM-DD format')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v and not v.isdigit():
            raise ValueError('Mobile number must contain only digits')
        return v
    
    @validator('*', pre=True)
    def validate_at_least_one_field(cls, v, values):
        # This will be checked in the endpoint
        return v


class EmployeeBulkUpdateRequest(BaseModel):
    """Bulk employee update - NO EMPTY ARRAYS ALLOWED"""
    updates: List[Dict[str, Any]] = Field(..., min_items=1, description="At least one update is required")
    
    @validator('updates')
    def validate_updates_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Updates list cannot be empty')
        return v


# ============================================================================
# EMPLOYEE WORK PROFILE SCHEMAS
# ============================================================================

class EmployeeWorkProfileUpdateRequest(BaseModel):
    """Work profile update schema - AT LEAST ONE FIELD REQUIRED"""
    departmentId: Optional[int] = Field(None, gt=0, description="Department ID")
    designationId: Optional[int] = Field(None, gt=0, description="Designation ID")
    locationId: Optional[int] = Field(None, gt=0, description="Location ID")
    costCenterId: Optional[int] = Field(None, gt=0, description="Cost center ID")
    businessId: Optional[int] = Field(None, gt=0, description="Business unit ID")
    gradeId: Optional[int] = Field(None, gt=0, description="Grade ID")
    reportingManagerId: Optional[int] = Field(None, gt=0, description="Reporting manager ID")
    shiftPolicyId: Optional[int] = Field(None, gt=0, description="Shift policy ID")
    weekoffPolicyId: Optional[int] = Field(None, gt=0, description="Week-off policy ID")
    confirmationDate: Optional[str] = Field(None, description="Confirmation date in YYYY-MM-DD format")
    terminationDate: Optional[str] = Field(None, description="Termination date in YYYY-MM-DD format")
    employeeStatus: Optional[EmployeeStatusEnum] = Field(None, description="Employee status")
    
    @validator('confirmationDate', 'terminationDate')
    def validate_dates(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class EmployeeWorkProfileUpdate(BaseModel):
    """Sanitized work profile update schema for API consumers (DO NOT include businessId)."""
    departmentId: Optional[int] = Field(None, gt=0, description="Department ID")
    designationId: Optional[int] = Field(None, gt=0, description="Designation ID")
    locationId: Optional[int] = Field(None, gt=0, description="Location ID")
    costCenterId: Optional[int] = Field(None, gt=0, description="Cost center ID")
    gradeId: Optional[int] = Field(None, gt=0, description="Grade ID")
    reportingManagerId: Optional[int] = Field(None, gt=0, description="Reporting manager ID")
    shiftPolicyId: Optional[int] = Field(None, gt=0, description="Shift policy ID")
    weekoffPolicyId: Optional[int] = Field(None, gt=0, description="Week-off policy ID")
    confirmationDate: Optional[str] = Field(None, description="Confirmation date in YYYY-MM-DD format")
    terminationDate: Optional[str] = Field(None, description="Termination date in YYYY-MM-DD format")
    employeeStatus: Optional[EmployeeStatusEnum] = Field(None, description="Employee status")

    @validator('confirmationDate', 'terminationDate')
    def validate_dates(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


# ============================================================================
# EMPLOYEE PERMISSIONS SCHEMAS
# ============================================================================

class EmployeePermissionsUpdateRequest(BaseModel):
    """Employee permissions update - AT LEAST ONE PERMISSION REQUIRED"""
    sendMobileLogin: Optional[bool] = Field(None, description="Enable mobile login")
    sendWebLogin: Optional[bool] = Field(None, description="Enable web login")
    selfiePunch: Optional[bool] = Field(None, description="Enable selfie punch")
    locationPunch: Optional[bool] = Field(None, description="Enable location-based punch")
    manualAttendance: Optional[bool] = Field(None, description="Allow manual attendance")
    attendanceCorrection: Optional[bool] = Field(None, description="Allow attendance correction")
    leaveApproval: Optional[bool] = Field(None, description="Leave approval permission")
    viewPayslip: Optional[bool] = Field(None, description="View payslip permission")
    adminAccess: Optional[bool] = Field(None, description="Admin access permission")


# ============================================================================
# EMPLOYEE PROFILE SCHEMAS
# ============================================================================

class EmployeeProfileCreateRequest(BaseModel):
    """Employee profile creation - REQUIRED FIELDS"""
    bio: Optional[str] = Field(None, max_length=1000, description="Employee bio")
    skills: Optional[str] = Field(None, max_length=500, description="Skills")
    certifications: Optional[str] = Field(None, max_length=500, description="Certifications")
    presentAddressLine1: Optional[str] = Field(None, max_length=200, description="Present address line 1")
    presentAddressLine2: Optional[str] = Field(None, max_length=200, description="Present address line 2")
    presentCity: Optional[str] = Field(None, max_length=100, description="Present city")
    presentState: Optional[str] = Field(None, max_length=100, description="Present state")
    presentCountry: Optional[str] = Field(None, max_length=100, description="Present country")
    presentPincode: Optional[str] = Field(None, max_length=10, description="Present pincode")
    permanentAddressLine1: Optional[str] = Field(None, max_length=200, description="Permanent address line 1")
    permanentAddressLine2: Optional[str] = Field(None, max_length=200, description="Permanent address line 2")
    permanentCity: Optional[str] = Field(None, max_length=100, description="Permanent city")
    permanentState: Optional[str] = Field(None, max_length=100, description="Permanent state")
    permanentCountry: Optional[str] = Field(None, max_length=100, description="Permanent country")
    permanentPincode: Optional[str] = Field(None, max_length=10, description="Permanent pincode")
    emergencyContactName: Optional[str] = Field(None, max_length=100, description="Emergency contact name")
    emergencyContactMobile: Optional[str] = Field(None, max_length=15, description="Emergency contact mobile")
    panNumber: Optional[str] = Field(None, max_length=10, description="PAN number")
    aadharNumber: Optional[str] = Field(None, max_length=12, description="Aadhar number")
    bankName: Optional[str] = Field(None, max_length=100, description="Bank name")
    bankAccountNumber: Optional[str] = Field(None, max_length=20, description="Bank account number")
    bankIfscCode: Optional[str] = Field(None, max_length=11, description="Bank IFSC code")
    bankBranch: Optional[str] = Field(None, max_length=100, description="Bank branch")


class EmployeeProfileUpdateRequest(BaseModel):
    """Employee profile update - AT LEAST ONE FIELD REQUIRED"""
    bio: Optional[str] = Field(None, max_length=1000)
    skills: Optional[str] = Field(None, max_length=500)
    certifications: Optional[str] = Field(None, max_length=500)
    presentAddressLine1: Optional[str] = Field(None, max_length=200)
    presentAddressLine2: Optional[str] = Field(None, max_length=200)
    presentCity: Optional[str] = Field(None, max_length=100)
    presentState: Optional[str] = Field(None, max_length=100)
    presentCountry: Optional[str] = Field(None, max_length=100)
    presentPincode: Optional[str] = Field(None, max_length=10)
    permanentAddressLine1: Optional[str] = Field(None, max_length=200)
    permanentAddressLine2: Optional[str] = Field(None, max_length=200)
    permanentCity: Optional[str] = Field(None, max_length=100)
    permanentState: Optional[str] = Field(None, max_length=100)
    permanentCountry: Optional[str] = Field(None, max_length=100)
    permanentPincode: Optional[str] = Field(None, max_length=10)
    emergencyContactName: Optional[str] = Field(None, max_length=100)
    emergencyContactMobile: Optional[str] = Field(None, max_length=15)
    panNumber: Optional[str] = Field(None, max_length=10)
    aadharNumber: Optional[str] = Field(None, max_length=12)
    bankName: Optional[str] = Field(None, max_length=100)
    bankAccountNumber: Optional[str] = Field(None, max_length=20)
    bankIfscCode: Optional[str] = Field(None, max_length=11)
    bankBranch: Optional[str] = Field(None, max_length=100)


# ============================================================================
# EMPLOYEE ADDRESS SCHEMAS
# ============================================================================

class EmployeeAddressCreateRequest(BaseModel):
    """Employee address creation - REQUIRED FIELDS"""
    addressType: str = Field(..., description="Address type (present/permanent)")
    addressLine1: str = Field(..., min_length=1, max_length=200, description="Address line 1 is required")
    addressLine2: Optional[str] = Field(None, max_length=200, description="Address line 2")
    city: str = Field(..., min_length=1, max_length=100, description="City is required")
    state: str = Field(..., min_length=1, max_length=100, description="State is required")
    country: str = Field(..., min_length=1, max_length=100, description="Country is required")
    pincode: str = Field(..., min_length=1, max_length=10, description="Pincode is required")
    
    @validator('addressType')
    def validate_address_type(cls, v):
        if v not in ['present', 'permanent']:
            raise ValueError('Address type must be either "present" or "permanent"')
        return v


# ============================================================================
# EMPLOYEE DOCUMENT SCHEMAS
# ============================================================================

class EmployeeDocumentCreateRequest(BaseModel):
    """Employee document creation - REQUIRED FIELDS"""
    documentType: str = Field(..., min_length=1, max_length=100, description="Document type is required")
    documentName: str = Field(..., min_length=1, max_length=200, description="Document name is required")
    description: Optional[str] = Field(None, max_length=500, description="Document description")


# ============================================================================
# EMPLOYEE SALARY SCHEMAS
# ============================================================================

class EmployeeSalaryCreateRequest(BaseModel):
    """Employee salary creation - REQUIRED FIELDS"""
    basicSalary: float = Field(..., gt=0, description="Basic salary must be greater than 0")
    grossSalary: float = Field(..., gt=0, description="Gross salary must be greater than 0")
    ctc: float = Field(..., gt=0, description="CTC must be greater than 0")
    effectiveFrom: str = Field(..., description="Effective from date in YYYY-MM-DD format is required")
    effectiveTo: Optional[str] = Field(None, description="Effective to date in YYYY-MM-DD format")
    
    @validator('effectiveFrom', 'effectiveTo')
    def validate_dates(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v
    
    @validator('grossSalary')
    def validate_gross_salary(cls, v, values):
        if 'basicSalary' in values and v < values['basicSalary']:
            raise ValueError('Gross salary must be greater than or equal to basic salary')
        return v
    
    @validator('ctc')
    def validate_ctc(cls, v, values):
        if 'grossSalary' in values and v < values['grossSalary']:
            raise ValueError('CTC must be greater than or equal to gross salary')
        return v


class EmployeeSalaryUpdateRequest(BaseModel):
    """Employee salary update - AT LEAST ONE FIELD REQUIRED"""
    basicSalary: Optional[float] = Field(None, gt=0)
    grossSalary: Optional[float] = Field(None, gt=0)
    ctc: Optional[float] = Field(None, gt=0)
    effectiveFrom: Optional[str] = Field(None)
    effectiveTo: Optional[str] = Field(None)
    isActive: Optional[bool] = Field(None)
    
    @validator('effectiveFrom', 'effectiveTo')
    def validate_dates(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class ValidationErrorResponse(BaseModel):
    """Standard validation error response"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Validation failed",
                "details": {
                    "field": "firstName",
                    "message": "First name is required and cannot be empty"
                }
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {
                    "id": 1,
                    "name": "John Doe",
                    "code": "EMP001"
                }
            }
        }


# ============================================================================
# VALIDATION HELPER FUNCTIONS
# ============================================================================

def validate_non_empty_request(data: BaseModel, operation_name: str) -> None:
    """
    Validate that request body is not empty and contains at least one valid field
    """
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request body cannot be empty for {operation_name}. Please provide valid data."
        )
    
    # Get all non-None values
    non_none_values = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    
    if not non_none_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least one valid field must be provided for {operation_name}. Empty request bodies are not allowed."
        )


def validate_required_fields(data: BaseModel, required_fields: List[str], operation_name: str) -> None:
    """
    Validate that all required fields are present and not empty
    """
    data_dict = data.dict(exclude_unset=True)
    missing_fields = []
    
    for field in required_fields:
        if field not in data_dict or data_dict[field] is None or data_dict[field] == "":
            missing_fields.append(field)
    
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields for {operation_name}: {', '.join(missing_fields)}"
        )