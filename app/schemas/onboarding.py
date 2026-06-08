"""
Onboarding Schemas
Pydantic models for onboarding API requests and responses
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


class OnboardingStatusEnum(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Base schemas
# Nested explicit schemas to ensure Swagger shows concrete fields
class PoliciesSchema(BaseModel):
    # Legacy schema placeholder - replaced by list[int] of master policy IDs
    weekoff_policy_id: int = None
    shift_policy_id: int = None
    work_shift_id: int = None


class OfferLetterSchema(BaseModel):
    designation: str
    department: str
    joining_date: date
    salary: float


class SalaryOptionsSchema(BaseModel):
    ctc: float
    basic: float
    hra: float
    special_allowance: float


class ApproveOnboardingRequest(BaseModel):
    form_id: int
    employee_id: Optional[int] = None
    joining_date: Optional[date] = None
    confirmation_date: Optional[date] = None
    business_unit: Optional[str] = None
    location: Optional[str] = None
    cost_center: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    reporting_manager: Optional[str] = None
    shift: Optional[str] = None
    grade: Optional[str] = None
    week_off: Optional[str] = None
    employment_type: Optional[str] = None
    work_mode: Optional[str] = None

    class Config:
        populate_by_name = True
        alias_generator = lambda s: ''.join(word.title() if i else word for i, word in enumerate(s.split('_')))


# Base schemas
class OnboardingFormBase(BaseModel):
    candidate_name: str = Field(..., min_length=2, max_length=255)
    candidate_email: EmailStr
    candidate_mobile: str = Field(..., min_length=10, max_length=20)
    verify_mobile: bool = True
    verify_pan: bool = False
    verify_bank: bool = False
    verify_aadhaar: bool = False
    notes: Optional[str] = None
    # Policies is a list of master policy IDs
    policies: List[int] = []
    offer_letter: Optional[OfferLetterSchema] = None
    salary_options: Optional[SalaryOptionsSchema] = None


# Nested explicit schemas to ensure Swagger shows concrete fields
# Minimal/allow-extra nested schemas for create payloads
class PoliciesCreateSchema(BaseModel):
    """Minimal policies object for onboarding creation payloads."""
    class Config:
        extra = "allow"


class OfferLetterCreateMinimal(BaseModel):
    """Offer letter object for create payloads without detailed fields."""
    class Config:
        extra = "allow"


class SalaryOptionsCreateMinimal(BaseModel):
    """Salary options for create payloads without detailed breakdowns."""
    class Config:
        extra = "allow"


class CreateOnboardingSchema(BaseModel):
    candidate_name: str = Field(..., min_length=2, max_length=255)
    candidate_email: EmailStr
    candidate_mobile: str = Field(..., min_length=10, max_length=20)

    verify_mobile: bool = True
    verify_pan: bool = False
    verify_bank: bool = False
    verify_aadhaar: bool = False

    notes: Optional[str] = None

    policies: List[int] = []



class UpdateOnboardingSchema(CreateOnboardingSchema):
    status: Optional[str] = None
    expires_at: Optional[datetime] = None


class OnboardingResponseSchema(CreateOnboardingSchema):
    id: int
    business_id: int
    form_token: str
    status: str

    created_at: datetime
    sent_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    rejection_reason: Optional[str] = None
    candidate_mobile_verified: bool = False
    # Response may come from DB where nested objects are not stored yet
    policies: List[int] = []


    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "candidate_name": "string",
                "candidate_email": "user@example.com",
                "candidate_mobile": "stringstri",
                "verify_mobile": True,
                "verify_pan": False,
                "verify_bank": False,
                "verify_aadhaar": False,
                "notes": "string",
                "policies": { },

                "id": 0,
                "business_id": 0,
                "form_token": "string",
                "status": "string",
                "created_at": "2026-05-19T17:08:09.875Z",
                "sent_at": "2026-05-19T17:08:09.875Z",
                "submitted_at": "2026-05-19T17:08:09.875Z",
                "approved_at": "2026-05-19T17:08:09.875Z",
                "rejected_at": "2026-05-19T17:08:09.875Z",
                "expires_at": "2026-05-19T17:08:09.875Z",
                "rejection_reason": "string",
                "candidate_mobile_verified": False
            }
        }


class OnboardingListResponse(BaseModel):
    items: List[OnboardingResponseSchema]
    total: int
    page: int
    limit: int


class OnboardingFormCreate(OnboardingFormBase):
    pass


class OnboardingFormUpdate(BaseModel):
    candidate_name: Optional[str] = Field(None, min_length=2, max_length=255)
    candidate_email: Optional[EmailStr] = None
    candidate_mobile: Optional[str] = Field(None, min_length=10, max_length=20)
    verify_mobile: Optional[bool] = None
    verify_pan: Optional[bool] = None
    verify_bank: Optional[bool] = None
    verify_aadhaar: Optional[bool] = None
    notes: Optional[str] = None
    policies: Optional[List[int]] = None
    offer_letter: Optional[OfferLetterSchema] = None
    salary_options: Optional[SalaryOptionsSchema] = None
    status: Optional[str] = None
    verify_mobile: Optional[bool] = None
    verify_pan: Optional[bool] = None
    verify_bank: Optional[bool] = None
    verify_aadhaar: Optional[bool] = None
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None

    # Nested update objects
    policies: Optional[List[int]] = None
    offer_letter: Optional[OfferLetterSchema] = None
    salary_options: Optional[SalaryOptionsSchema] = None


class OnboardingFormResponse(OnboardingFormBase):
    id: int
    business_id: int
    form_token: str
    status: OnboardingStatusEnum
    created_at: datetime
    sent_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    employee_id: Optional[int] = None
    policies: Optional[List[int]] = None
    offer_letter: Optional[OfferLetterSchema] = None
    salary_options: Optional[SalaryOptionsSchema] = None
    
    class Config:
        from_attributes = True


# Document schemas
class OnboardingDocumentCreate(BaseModel):
    document_type: str = Field(..., max_length=100)
    document_name: str = Field(..., max_length=255)
    file_path: str = Field(..., max_length=500)
    file_size: Optional[int] = None
    mime_type: Optional[str] = Field(None, max_length=100)
    is_mandatory: bool = False
    display_order: int = 0
    description: Optional[str] = None


class OnboardingDocumentResponse(OnboardingDocumentCreate):
    id: int
    form_id: int
    uploaded_at: datetime
    uploaded_by: Optional[int] = None
    
    class Config:
        from_attributes = True


# Policy schemas
class OnboardingPolicyCreate(BaseModel):
    policy_name: str = Field(..., max_length=255)
    policy_content: Optional[str] = None
    policy_file_path: Optional[str] = Field(None, max_length=500)
    requires_acknowledgment: bool = True
    is_mandatory: bool = True
    display_order: int = 0


class OnboardingPolicyResponse(OnboardingPolicyCreate):
    id: int
    business_id: int
    form_id: int
    created_at: datetime
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


# Offer letter schemas
class OfferLetterCreate(BaseModel):
    template_id: Optional[int] = None
    position_title: str = Field(..., max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    basic_salary: Optional[str] = Field(None, max_length=100)
    gross_salary: Optional[str] = Field(None, max_length=100)
    ctc: Optional[str] = Field(None, max_length=100)
    joining_date: Optional[date] = None
    offer_valid_until: Optional[date] = None
    letter_content: Optional[str] = None


class OfferLetterResponse(OfferLetterCreate):
    id: int
    business_id: int
    form_id: Optional[int] = None  # Allow standalone offer letters
    generated_file_path: Optional[str] = None
    is_generated: bool = False
    is_sent: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


# Candidate onboarding workflow schemas
class CandidateBasicDetails(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    date_of_birth: date
    profile_photo: Optional[str] = None  # File path or base64


class CandidateContactDetails(BaseModel):
    mobile: str = Field(..., pattern="^[0-9]{10}$")
    email: EmailStr = Field(..., max_length=100)
    home_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact: Optional[str] = Field(None, max_length=20)
    mobile_verified: bool = False
    otp_verified: bool = False


class CandidatePersonalDetails(BaseModel):
    blood_group: str = Field(..., pattern="^(A\\+|A-|B\\+|B-|O\\+|O-|AB\\+|AB-)$")
    passport: Optional[str] = Field(None, pattern="^[A-PR-WYa-pr-wy][1-9]\\d{6}$")
    driving_license: Optional[str] = Field(None, pattern="^[A-Z]{2}-\\d{13}$")


class CandidateStatutoryDetails(BaseModel):
    aadhar: str = Field(..., pattern="^\\d{12}$")
    pan: str = Field(..., pattern="^[A-Z]{5}[0-9]{4}[A-Z]$")
    uan: str = Field(..., pattern="^\\d{12}$")
    esi: str = Field(..., pattern="^\\d{2}-\\d{2}-\\d{6}-\\d{3}-\\d{4}$")


class CandidateFamilyDetails(BaseModel):
    marital_status: str = Field(..., pattern="^(Single|Married)$")
    father_name: Optional[str] = Field(None, max_length=50)
    father_phone: Optional[str] = Field(None, max_length=20)
    father_dob: Optional[date] = None
    mother_name: Optional[str] = Field(None, max_length=50)
    mother_phone: Optional[str] = Field(None, max_length=20)
    mother_dob: Optional[date] = None


class CandidateAddressDetails(BaseModel):
    address1: str = Field(..., min_length=1, max_length=100)
    address2: Optional[str] = Field(None, max_length=100)
    city: str = Field(..., min_length=1, max_length=50)
    pincode: str = Field(..., pattern="^\\d{6}$")
    state: str = Field(..., min_length=1, max_length=50)
    country: str = Field(default="India", max_length=50)


class CandidateBankDetails(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=50)
    ifsc_code: str = Field(..., min_length=11, max_length=11)
    account_number: str = Field(..., min_length=1, max_length=20)
    account_holder: str = Field(..., min_length=1, max_length=100)


class CandidateDocumentUpload(BaseModel):
    pan: Optional[str] = None  # File path
    uan: Optional[str] = None  # File path
    esi: Optional[str] = None  # File path
    dl: Optional[str] = None   # File path
    passport: Optional[str] = None  # File path


# Complete form submission schema
class FormSubmissionCreate(BaseModel):
    # Basic Details (Step 2)
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    profile_photo: Optional[str] = None
    
    # Contact Details (Step 3)
    mobile: Optional[str] = Field(None, max_length=20)
    personal_email: Optional[EmailStr] = None
    home_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact: Optional[str] = Field(None, max_length=20)
    mobile_verified: Optional[bool] = False
    
    # Personal Details (Step 4)
    blood_group: Optional[str] = Field(None, max_length=10)
    passport_number: Optional[str] = Field(None, max_length=20)
    driving_license_number: Optional[str] = Field(None, max_length=30)
    
    # Statutory Details (Step 5)
    aadhaar_number: Optional[str] = Field(None, max_length=20)
    pan_number: Optional[str] = Field(None, max_length=20)
    uan_number: Optional[str] = Field(None, max_length=20)
    esi_number: Optional[str] = Field(None, max_length=30)
    
    # Family Details (Step 6)
    marital_status: Optional[str] = Field(None, max_length=20)
    father_name: Optional[str] = Field(None, max_length=100)
    father_phone: Optional[str] = Field(None, max_length=20)
    father_dob: Optional[date] = None
    mother_name: Optional[str] = Field(None, max_length=100)
    mother_phone: Optional[str] = Field(None, max_length=20)
    mother_dob: Optional[date] = None
    
    # Present Address (Step 7)
    present_address_line1: Optional[str] = Field(None, max_length=100)
    present_address_line2: Optional[str] = Field(None, max_length=100)
    present_city: Optional[str] = Field(None, max_length=50)
    present_pincode: Optional[str] = Field(None, max_length=6)
    present_state: Optional[str] = Field(None, max_length=50)
    present_country: Optional[str] = Field(None, max_length=50)
    
    # Permanent Address (Step 8)
    permanent_address_line1: Optional[str] = Field(None, max_length=100)
    permanent_address_line2: Optional[str] = Field(None, max_length=100)
    permanent_city: Optional[str] = Field(None, max_length=50)
    permanent_pincode: Optional[str] = Field(None, max_length=6)
    permanent_state: Optional[str] = Field(None, max_length=50)
    permanent_country: Optional[str] = Field(None, max_length=50)
    
    # Bank Details (Step 9)
    bank_name: Optional[str] = Field(None, max_length=255)
    account_number: Optional[str] = Field(None, max_length=50)
    ifsc_code: Optional[str] = Field(None, max_length=20)
    account_holder_name: Optional[str] = Field(None, max_length=100)
    
    # Document Upload (Step 10)
    uploaded_documents: Optional[str] = None  # JSON string
    
    # Additional fields
    nationality: Optional[str] = Field(None, max_length=100)
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100)
    emergency_contact_mobile: Optional[str] = Field(None, max_length=20)
    education_details: Optional[str] = None  # JSON string
    experience_details: Optional[str] = None  # JSON string
    policy_acknowledgments: Optional[str] = None  # JSON string
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = None


# Step-wise submission schemas for partial updates
class StepSubmissionBase(BaseModel):
    form_token: str
    step_number: int = Field(..., ge=1, le=11)


class Step1Submission(StepSubmissionBase):
    # Welcome page - no data to submit
    pass


class Step2Submission(StepSubmissionBase):
    basic_details: CandidateBasicDetails


class Step3Submission(StepSubmissionBase):
    contact_details: CandidateContactDetails


class Step4Submission(StepSubmissionBase):
    personal_details: CandidatePersonalDetails


class Step5Submission(StepSubmissionBase):
    statutory_details: CandidateStatutoryDetails


class Step6Submission(StepSubmissionBase):
    family_details: CandidateFamilyDetails


class Step7Submission(StepSubmissionBase):
    present_address: CandidateAddressDetails


class Step8Submission(StepSubmissionBase):
    permanent_address: CandidateAddressDetails


class Step9Submission(StepSubmissionBase):
    bank_details: CandidateBankDetails


class Step10Submission(StepSubmissionBase):
    documents: CandidateDocumentUpload


class Step11Submission(StepSubmissionBase):
    # Final submission - triggers complete form submission
    final_submission: bool = True


class FormSubmissionResponse(FormSubmissionCreate):
    id: int
    form_id: int
    submitted_at: datetime
    
    class Config:
        from_attributes = True


# Bulk onboarding schemas
class BulkOnboardingCandidate(BaseModel):
    candidate_name: str = Field(..., min_length=2, max_length=255)
    candidate_email: EmailStr
    candidate_mobile: str = Field(..., min_length=10, max_length=20)


class BulkOnboardingCreate(BaseModel):
    operation_name: str = Field(..., max_length=255)
    candidates: List[BulkOnboardingCandidate] = Field(..., min_items=1, max_items=100)
    verify_mobile: bool = True
    verify_pan: bool = False
    verify_bank: bool = False
    verify_aadhaar: bool = False


class BulkOnboardingResponse(BaseModel):
    id: int
    business_id: int
    operation_name: str
    total_candidates: int
    successful_sends: int
    failed_sends: int
    status: str
    results_summary: Optional[str] = None
    error_log: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


# Settings schemas
# New explicit nested schemas for settings (avoid generic dicts)
class FieldsSchema(BaseModel):
    present_address: bool = False
    permanent_address: bool = False
    bank_details: bool = False


class DocumentsSchema(BaseModel):
    pan_card: bool = False
    adhar_card: bool = False
    esi_card: bool = False
    driving_license: bool = False
    passport: bool = False
    voter_id: bool = False
    last_relieving_letter: bool = False
    last_salary_slip: bool = False
    latest_bank_statement: bool = False
    highest_education_proof: bool = False


class OnboardingSettingsUpdateSchema(BaseModel):
    fields: FieldsSchema
    documents: DocumentsSchema

    class Config:
        json_schema_extra = {
            "example": {
                "fields": {
                    "present_address": True,
                    "permanent_address": True,
                    "bank_details": True
                },
                "documents": {
                    "pan_card": True,
                    "adhar_card": True,
                    "esi_card": False,
                    "driving_license": False,
                    "passport": False,
                    "voter_id": False,
                    "last_relieving_letter": False,
                    "last_salary_slip": False,
                    "latest_bank_statement": False,
                    "highest_education_proof": True
                }
            }
        }


# Response schema includes metadata
class OnboardingSettingsResponseSchema(OnboardingSettingsUpdateSchema):
    id: int
    business_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "business_id": 1,
                "fields": {
                    "present_address": True,
                    "permanent_address": True,
                    "bank_details": True
                },
                "documents": {
                    "pan_card": True,
                    "adhar_card": True,
                    "esi_card": False,
                    "driving_license": False,
                    "passport": False,
                    "voter_id": False,
                    "last_relieving_letter": False,
                    "last_salary_slip": False,
                    "latest_bank_statement": False,
                    "highest_education_proof": True
                },
                "created_at": "2026-05-19T00:00:00Z",
                "updated_at": "2026-05-19T00:00:00Z",
                "created_by": 1
            }
        }

# Alias old names for compatibility
OnboardingSettingsUpdate = OnboardingSettingsUpdateSchema
OnboardingSettingsResponse = OnboardingSettingsResponseSchema


# Diagnostic/debug response schema
class DebugEnvironmentResponse(BaseModel):
    success: bool = True
    business_id: int
    environment: str
    python_version: str
    server_status: str
    app_version: Optional[str] = None
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "business_id": 1,
                "environment": "development",
                "python_version": "3.11.4",
                "server_status": "running",
                "app_version": "1.0.0",
                "timestamp": "2026-05-15T00:00:00Z"
            }
        }
    custom_fields: Optional[str] = Field(None, max_length=5000, description="Custom fields definition (JSON)")
    welcome_email_template: Optional[str] = Field(None, max_length=5000, description="Welcome email template")
    reminder_email_template: Optional[str] = Field(None, max_length=5000, description="Reminder email template")
    approval_email_template: Optional[str] = Field(None, max_length=5000, description="Approval email template")
    rejection_email_template: Optional[str] = Field(None, max_length=5000, description="Rejection email template")
    # Frontend-specific fields with proper validation
    document_requirements: Optional[Dict[str, bool]] = Field(None, description="Document requirement settings")
    field_requirements: Optional[Dict[str, bool]] = Field(None, description="Field requirement settings")
    
    @validator('document_requirements')
    def validate_document_requirements(cls, v):
        if v is not None:
            valid_documents = [
                "pan_card", "adhar_card", "esi_card", "driving_license", "passport",
                "voter_id", "last_relieving_letter", "last_salary_slip",
                "latest_bank_statement", "highest_education_proof"
            ]
            for doc_name in v.keys():
                if doc_name not in valid_documents:
                    raise ValueError(f"Invalid document type: {doc_name}")
        return v
    
    @validator('field_requirements')
    def validate_field_requirements(cls, v):
        if v is not None:
            valid_fields = ["present_address", "permanent_address", "bank_details"]
            for field_name in v.keys():
                if field_name not in valid_fields:
                    raise ValueError(f"Invalid field type: {field_name}")
        return v


# OnboardingSettingsResponse class removed; use OnboardingSettingsResponseSchema via alias
# Dashboard and statistics schemas
class OnboardingDashboardResponse(BaseModel):
    total_forms: int
    draft_forms: int
    sent_forms: int
    submitted_forms: int
    approved_forms: int
    rejected_forms: int
    expired_forms: int
    pending_approvals: int
    recent_submissions: List[Dict[str, Any]]
    monthly_stats: List[Dict[str, Any]]
    conversion_rate: float
    average_completion_time: Optional[float] = None


class OnboardingStatsResponse(BaseModel):
    total_candidates: int
    successful_onboardings: int
    pending_forms: int
    expired_forms: int
    rejection_rate: float
    completion_rate: float
    average_time_to_complete: Optional[float] = None
    monthly_trends: List[Dict[str, Any]]


# Pagination schemas
class PaginatedOnboardingResponse(BaseModel):
    items: List[OnboardingFormResponse]
    total: int
    page: int
    limit: int


# Action schemas
class OnboardingActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|send|resend)$")
    reason: Optional[str] = None
    notes: Optional[str] = None


class OnboardingRejectionRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for rejection")


class OnboardingActionResponse(BaseModel):
    success: bool
    message: str
    form_id: int
    action: str
    timestamp: datetime


# Template schemas
class OfferLetterTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    template_content: str
    available_variables: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class OfferLetterTemplateResponse(OfferLetterTemplateCreate):
    id: int
    business_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


# Template generation schema
class TemplateGenerationRequest(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=255, description="Name of the template to use")
    field_values: str = Field(..., min_length=1, description="Field values in key=value format, one per line")
    
    @validator('field_values')
    def validate_field_values(cls, v):
        """Validate field values format"""
        if not v.strip():
            raise ValueError("Field values cannot be empty")
        
        lines = v.strip().split('\n')
        for line in lines:
            if line.strip() and '=' not in line:
                raise ValueError(f"Invalid field value format: '{line}'. Expected 'key=value' format")
        
        return v


class TemplateGenerationResponse(BaseModel):
    success: bool
    message: str
    offer_letter_id: Optional[int] = None
    generated_content: str
    template_name: str
    field_values: Dict[str, str]


# Search and filter schemas
class OnboardingSearchRequest(BaseModel):
    query: Optional[str] = None
    status: Optional[OnboardingStatusEnum] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    created_by: Optional[int] = None
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100)