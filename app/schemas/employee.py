"""
Employee Schemas
Pydantic models for employee API requests and responses
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"
    PROBATION = "probation"


class MaritalStatus(str, Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


# Base Employee Schemas
class EmployeeBase(BaseModel):
    """Base employee schema"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    email: EmailStr
    mobile: str = Field(..., pattern=r'^[\+]?[0-9]{10,15}$')
    alternate_mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')
    
    # Personal Details
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None
    blood_group: Optional[str] = Field(None, max_length=10)
    nationality: Optional[str] = Field(None, max_length=100)
    religion: Optional[str] = Field(None, max_length=100)
    
    # Employment Details
    date_of_joining: date
    date_of_confirmation: Optional[date] = None
    employee_status: EmployeeStatus = EmployeeStatus.ACTIVE
    
    # Organizational Details
    business_id: int
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    location_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    grade_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None
    
    # Policy Assignments
    shift_policy_id: Optional[int] = None
    weekoff_policy_id: Optional[int] = None
    
    # Biometric and Access Control
    biometric_code: Optional[str] = Field(None, max_length=50)
    send_mobile_login: Optional[bool] = False
    send_web_login: Optional[bool] = True


class EmployeeCreate(EmployeeBase):
    """Schema for creating employee"""
    employee_code: Optional[str] = Field(None, max_length=50)
    
    @validator('date_of_joining')
    def validate_joining_date(cls, v):
        if v > date.today():
            raise ValueError('Date of joining cannot be in the future')
        return v


class EmployeeUpdate(BaseModel):
    """Schema for updating employee"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')
    alternate_mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')
    
    # Personal Details
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None
    blood_group: Optional[str] = Field(None, max_length=10)
    nationality: Optional[str] = Field(None, max_length=100)
    religion: Optional[str] = Field(None, max_length=100)
    
    # Employment Details
    date_of_confirmation: Optional[date] = None
    date_of_termination: Optional[date] = None
    employee_status: Optional[EmployeeStatus] = None
    
    # Organizational Details
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    location_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    grade_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None


class OnboardingEmployeeCreate(BaseModel):
    """Schema used by onboarding create endpoint (limited fields).

    Excludes employee_status, business_id, reporting_manager_id,
    marital_status, blood_group, nationality, religion.
    """
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    email: EmailStr
    mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')
    alternate_mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')

    # Employment / personal
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    date_of_joining: Optional[date] = None
    date_of_confirmation: Optional[date] = None



    # Allow clients to send numeric ids directly (preferred in onboarding payloads)
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    location_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    grade_id: Optional[int] = None
    shift_policy_id: Optional[int] = None
    week_off_policy_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None

    # Misc
    biometric_code: Optional[str] = Field(None, max_length=50)
    send_mobile_login: Optional[bool] = False
    send_web_login: Optional[bool] = True
    employee_code: Optional[str] = Field(None, max_length=50)

    @validator('date_of_joining')
    def validate_joining_date_onboarding(cls, v):
        if v and v > date.today():
            raise ValueError('Date of joining cannot be in the future')
        return v
    
class EmployeeProfileBase(BaseModel):
    """Base employee profile schema"""
    # Address Information
    present_address_line1: Optional[str] = Field(None, max_length=255)
    present_address_line2: Optional[str] = Field(None, max_length=255)
    present_city: Optional[str] = Field(None, max_length=100)
    present_state: Optional[str] = Field(None, max_length=100)
    present_country: Optional[str] = Field(None, max_length=100)
    present_pincode: Optional[str] = Field(None, max_length=20)
    
    permanent_address_line1: Optional[str] = Field(None, max_length=255)
    permanent_address_line2: Optional[str] = Field(None, max_length=255)
    permanent_city: Optional[str] = Field(None, max_length=100)
    permanent_state: Optional[str] = Field(None, max_length=100)
    permanent_country: Optional[str] = Field(None, max_length=100)
    permanent_pincode: Optional[str] = Field(None, max_length=20)
    
    # Statutory Information
    pan_number: Optional[str] = Field(None, max_length=20)
    aadhaar_number: Optional[str] = Field(None, max_length=20)
    uan_number: Optional[str] = Field(None, max_length=20)
    esi_number: Optional[str] = Field(None, max_length=20)
    
    # Bank Information
    bank_name: Optional[str] = Field(None, max_length=255)
    bank_account_number: Optional[str] = Field(None, max_length=50)
    bank_ifsc_code: Optional[str] = Field(None, max_length=20)
    bank_branch: Optional[str] = Field(None, max_length=255)
    
    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100)
    emergency_contact_mobile: Optional[str] = Field(None, pattern=r'^[\+]?[0-9]{10,15}$')
    emergency_contact_address: Optional[str] = None
    
    # Additional Information
    bio: Optional[str] = None
    skills: Optional[List[str]] = []
    certifications: Optional[List[str]] = []


class EmployeeProfileCreate(EmployeeProfileBase):
    """Schema for creating employee profile"""
    employee_id: int


class EmployeeProfileUpdate(EmployeeProfileBase):
    """Schema for updating employee profile"""
    pass


class EmployeeDocumentBase(BaseModel):
    """Base employee document schema"""
    document_type: str = Field(..., max_length=100)
    document_name: str = Field(..., max_length=255)


class EmployeeDocumentCreate(EmployeeDocumentBase):
    """Schema for creating employee document"""
    employee_id: int
    file_path: str = Field(..., max_length=500)
    file_size: Optional[int] = None
    mime_type: Optional[str] = Field(None, max_length=100)


class EmployeeDocumentResponse(EmployeeDocumentBase):
    """Schema for employee document response"""
    id: int
    employee_id: int
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class EmployeeSalaryBase(BaseModel):
    """Base employee salary schema"""
    salary_structure_id: Optional[int] = None
    basic_salary: float = Field(..., gt=0)
    gross_salary: float = Field(..., gt=0)
    ctc: float = Field(..., gt=0)
    effective_from: date


class EmployeeSalaryCreate(EmployeeSalaryBase):
    """Schema for creating employee salary"""
    employee_id: int


class EmployeeSalaryUpdate(BaseModel):
    """Schema for updating employee salary"""
    salary_structure_id: Optional[int] = None
    basic_salary: Optional[float] = Field(None, gt=0)
    gross_salary: Optional[float] = Field(None, gt=0)
    ctc: Optional[float] = Field(None, gt=0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class EmployeeSalaryResponse(EmployeeSalaryBase):
    """Schema for employee salary response"""
    id: int
    employee_id: int
    effective_to: Optional[date]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Response Schemas
class EmployeeProfileResponse(EmployeeProfileBase):
    """Schema for employee profile response"""
    id: int
    employee_id: int
    profile_image_url: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class EmployeeResponse(EmployeeBase):
    """Schema for employee response"""
    id: int
    employee_code: str
    full_name: str
    display_name: str
    date_of_termination: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Related data
    profile: Optional[EmployeeProfileResponse] = None
    documents: List[EmployeeDocumentResponse] = []
    salary_records: List[EmployeeSalaryResponse] = []
    
    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    """Schema for employee list response"""
    id: int
    employee_code: str
    full_name: str
    email: str
    mobile: str
    employee_status: EmployeeStatus
    date_of_joining: date
    department_name: Optional[str] = None
    designation_name: Optional[str] = None
    location_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class EmployeeSearchRequest(BaseModel):
    """Schema for employee search request"""
    query: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    location_id: Optional[int] = None
    employee_status: Optional[EmployeeStatus] = None
    date_of_joining_from: Optional[date] = None
    date_of_joining_to: Optional[date] = None
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100)


class EmployeeBulkCreateRequest(BaseModel):
    """Schema for bulk employee creation"""
    employees: List[EmployeeCreate]
    send_welcome_email: bool = True


class EmployeeBulkUpdateRequest(BaseModel):
    """Schema for bulk employee update"""
    employee_ids: List[int]
    updates: EmployeeUpdate


class EmployeeStatsResponse(BaseModel):
    """Schema for employee statistics"""
    total_employees: int
    active_employees: int
    inactive_employees: int
    new_joinings_this_month: int
    terminations_this_month: int
    employees_on_probation: int
    employees_by_department: Dict[str, int]
    employees_by_location: Dict[str, int]
    employees_by_status: Dict[str, int]


class PaginatedEmployeeResponse(BaseModel):
    """Schema for paginated employee response"""
    items: List[EmployeeListResponse]
    total: int
    page: int
    size: int
    pages: int