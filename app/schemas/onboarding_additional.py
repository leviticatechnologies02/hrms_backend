"""
Additional Pydantic schemas for Onboarding endpoints
Replaces dict with proper typed schemas for Swagger/OpenAPI documentation
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from app.schemas.master_setup import MasterPolicyResponse


class SalaryCalculationRequest(BaseModel):
    """Schema for calculating salary breakup for offer letter"""
    
    gross_salary: float = Field(
        ...,
        gt=0,
        description="Gross salary amount",
        example=50000.0
    )
    salary_structure_id: Optional[int] = Field(
        default=None,
        description="Salary structure ID",
        example=1
    )
    employee_id: Optional[int] = Field(
        default=None,
        description="Employee ID",
        example=1
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional salary calculation options",
        example={"include_pf": True, "include_esi": True}
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "gross_salary": 50000.0,
                "salary_structure_id": 1,
                "employee_id": 1,
                "options": {"include_pf": True, "include_esi": True}
            }
        }


class OfferLetterGenerateRequest(BaseModel):
    """Schema for generating complete offer letter"""
    
    template_id: Optional[int] = Field(
        default=None,
        description="Offer letter template ID",
        example=1
    )
    position_title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Position title / Designation",
        example="Software Engineer"
    )
    department: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Department name",
        example="Engineering"
    )
    location: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Work location",
        example="Hyderabad"
    )
    grade: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Employee grade",
        example="Senior Engineer"
    )
    cost_center: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Cost center",
        example="Engineering"
    )
    work_shift: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Work shift",
        example="Day Shift"
    )
    gross_salary: Optional[float] = Field(
        default=None,
        description="Gross salary amount",
        example=50000.0
    )
    basic_salary: Optional[str] = Field(
        default=None,
        description="Basic salary amount",
        example="25000"
    )
    ctc: Optional[str] = Field(
        default=None,
        description="Cost to company",
        example="600000"
    )
    salary_structure_id: Optional[int] = Field(
        default=None,
        description="Salary structure ID",
        example=1
    )
    salary_options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Salary calculation options",
        example={}
    )
    joining_date: Optional[date] = Field(
        default=None,
        description="Joining date",
        example="2026-03-01"
    )
    confirmation_date: Optional[date] = Field(
        default=None,
        description="Confirmation date",
        example="2026-09-01"
    )
    date_of_birth: Optional[date] = Field(
        default=None,
        description="Date of birth",
        example="1995-01-15"
    )
    notice_period: Optional[int] = Field(
        default=None,
        description="Notice period in days",
        example=30
    )
    gender: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Gender",
        example="Male"
    )
    offer_valid_until: Optional[date] = Field(
        default=None,
        description="Offer validity date",
        example="2026-02-28"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": 1,
                "position_title": "Software Engineer",
                "department": "Engineering",
                "location": "Hyderabad",
                "grade": "Senior Engineer",
                "cost_center": "Engineering",
                "work_shift": "Day Shift",
                "gross_salary": 50000.0,
                "ctc": "600000",
                "joining_date": "2026-03-01",
                "confirmation_date": "2026-09-01",
                "date_of_birth": "1995-01-15",
                "notice_period": 30,
                "gender": "Male",
                "offer_valid_until": "2026-02-28"
            }
        }


class PolicyAttachmentRequest(BaseModel):
    """Schema for attaching policies to onboarding form"""
    
    policy_ids: List[int] = Field(
        ...,
        description="List of policy IDs to attach",
        example=[1, 2, 3, 5, 6]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_ids": [1, 2, 3, 5, 6]
            }
        }


class AttachPoliciesResponse(BaseModel):
    success: bool = True
    message: str
    form_id: int
    attached_policies: List[MasterPolicyResponse]

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully attached policies to form",
                "form_id": 1,
                "attached_policies": []
            }
        }


class DocumentRequirementUpdateRequest(BaseModel):
    """Schema for updating document requirement settings"""
    
    document_type: str = Field(
        ...,
        max_length=100,
        description="Document type",
        example="aadhar_card"
    )
    is_required: bool = Field(
        ...,
        description="Whether document is required",
        example=True
    )
    display_order: Optional[int] = Field(
        default=None,
        description="Display order",
        example=1
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "aadhar_card",
                "is_required": True,
                "display_order": 1
            }
        }


class FieldRequirementUpdateRequest(BaseModel):
    """Schema for updating field requirement settings"""
    
    field_name: str = Field(
        ...,
        max_length=100,
        description="Field name",
        example="date_of_birth"
    )
    is_required: bool = Field(
        ...,
        description="Whether field is required",
        example=True
    )
    is_visible: Optional[bool] = Field(
        default=True,
        description="Whether field is visible",
        example=True
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "field_name": "date_of_birth",
                "is_required": True,
                "is_visible": True
            }
        }


class CandidateInfo(BaseModel):
    """Schema for candidate information in bulk send"""
    
    name: str = Field(..., description="Candidate name", example="John Doe")
    email: EmailStr = Field(..., description="Candidate email", example="john.doe@example.com")
    position: Optional[str] = Field(default=None, description="Position", example="Software Engineer")
    department: Optional[str] = Field(default=None, description="Department", example="Engineering")


class BulkSendRequest(BaseModel):
    """Schema for bulk sending onboarding forms"""
    
    candidates: List[CandidateInfo] = Field(
        ...,
        description="List of candidates",
        min_length=1
    )
    template_id: Optional[int] = Field(
        default=None,
        description="Template ID",
        example=1
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "candidates": [
                    {
                        "name": "John Doe",
                        "email": "john.doe@example.com",
                        "position": "Software Engineer",
                        "department": "Engineering"
                    }
                ],
                "template_id": 1
            }
        }


class SendFormRequest(BaseModel):
    """Schema for sending onboarding form to candidate"""
    
    candidate_email: EmailStr = Field(
        ...,
        description="Candidate email address",
        example="candidate@example.com"
    )
    send_email: Optional[bool] = Field(
        default=True,
        description="Whether to send email notification",
        example=True
    )
    custom_message: Optional[str] = Field(
        default=None,
        description="Custom message to include in email",
        example="Welcome to our company!"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "candidate_email": "candidate@example.com",
                "send_email": True,
                "custom_message": "Welcome to our company!"
            }
        }


class StepDataRequest(BaseModel):
    """Schema for submitting onboarding form step data"""
    
    data: Dict[str, Any] = Field(
        ...,
        description="Step data as key-value pairs",
        example={"first_name": "John", "last_name": "Doe", "email": "john@example.com"}
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "phone": "+91-9876543210"
                }
            }
        }


class OTPSendRequest(BaseModel):
    """Schema for sending OTP for mobile verification"""
    
    mobile_number: str = Field(
        ...,
        max_length=20,
        description="Mobile number",
        example="+91-9876543210"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "mobile_number": "+91-9876543210"
            }
        }


class OTPVerifyRequest(BaseModel):
    """Schema for verifying OTP"""
    
    mobile_number: str = Field(
        ...,
        max_length=20,
        description="Mobile number",
        example="+91-9876543210"
    )
    otp_code: str = Field(
        ...,
        min_length=4,
        max_length=6,
        description="OTP code",
        example="123456"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "mobile_number": "+91-9876543210",
                "otp_code": "123456"
            }
        }


class DocumentUploadRequest(BaseModel):
    """Schema for document upload metadata"""
    
    file_name: str = Field(
        ...,
        max_length=255,
        description="File name",
        example="aadhar_card.pdf"
    )
    file_size: Optional[int] = Field(
        default=None,
        description="File size in bytes",
        example=1024000
    )
    file_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="File MIME type",
        example="application/pdf"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_name": "aadhar_card.pdf",
                "file_size": 1024000,
                "file_type": "application/pdf"
            }
        }


class FormCreateRequest(BaseModel):
    """Schema for creating onboarding form (Part A)"""
    
    candidate_name: str = Field(
        ...,
        max_length=200,
        description="Candidate name",
        example="John Doe"
    )
    candidate_email: EmailStr = Field(
        ...,
        description="Candidate email",
        example="john.doe@example.com"
    )
    position: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Position",
        example="Software Engineer"
    )
    department: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Department",
        example="Engineering"
    )
    joining_date: Optional[date] = Field(
        default=None,
        description="Expected joining date",
        example="2026-03-01"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "candidate_name": "John Doe",
                "candidate_email": "john.doe@example.com",
                "position": "Software Engineer",
                "department": "Engineering",
                "joining_date": "2026-03-01"
            }
        }


class FinalizeAndSendRequest(BaseModel):
    """Schema for finalizing and sending onboarding form"""
    
    send_email: Optional[bool] = Field(
        default=True,
        description="Whether to send email notification",
        example=True
    )
    custom_message: Optional[str] = Field(
        default=None,
        description="Custom message for candidate",
        example="Welcome aboard!"
    )
    include_offer_letter: Optional[bool] = Field(
        default=True,
        description="Whether to include offer letter",
        example=True
    )
    include_policies: Optional[bool] = Field(
        default=True,
        description="Whether to include policies",
        example=True
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "send_email": True,
                "custom_message": "Welcome aboard!",
                "include_offer_letter": True,
                "include_policies": True
            }
        }


class SkipOfferLetterRequest(BaseModel):
    """Schema for creating/updating an onboarding form while skipping offer letter generation"""

    candidate_name: str = Field(..., max_length=200, example="ASASA")
    candidate_email: EmailStr = Field(..., example="chandupatel.1434@gmail.com")
    candidate_mobile: str = Field(..., max_length=20, example="9494231334")
    verify_mobile: Optional[bool] = True
    verify_pan: Optional[bool] = False
    verify_bank: Optional[bool] = False
    verify_aadhaar: Optional[bool] = False
    policies: Optional[List[int]] = Field(default_factory=list, example=[1,2,3])
    offer_letter: Optional[dict] = None
    salary_options: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_name": "ASASA",
                "candidate_email": "chandupatel.1434@gmail.com",
                "candidate_mobile": "9494231334",
                "verify_mobile": True,
                "verify_pan": False,
                "verify_bank": False,
                "verify_aadhaar": False,
                "policies": [1,2,3],
                "offer_letter": None,
                "salary_options": None
            }
        }


class SkipOfferLetterResponse(BaseModel):
    success: bool = True
    message: str
    form_id: int
    business_id: int
    policies: List[int]
    offer_letter_skipped: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Onboarding created successfully without offer letter",
                "form_id": 2,
                "business_id": 1,
                "policies": [1,2,3],
                "offer_letter_skipped": True
            }
        }
