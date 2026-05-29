"""
Onboarding Models
Employee onboarding workflow data models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import enum
import json
from datetime import datetime

# Try to import JSON, fallback to Text if not available
try:
    from sqlalchemy.dialects.postgresql import JSON
except ImportError:
    try:
        from sqlalchemy import JSON
    except ImportError:
        # Fallback to Text for JSON fields
        JSON = Text


class OnboardingStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OnboardingForm(Base):
    """Main onboarding form records"""
    __tablename__ = "onboarding_forms"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Candidate information
    candidate_name = Column(String(255), nullable=False)
    candidate_email = Column(String(255), nullable=False, index=True)
    candidate_mobile = Column(String(20), nullable=False)
    
    # Form details
    form_token = Column(String(255), unique=True, index=True)  # For public access
    status = Column(Enum(OnboardingStatus), default=OnboardingStatus.DRAFT)
    
    # Verification options
    verify_mobile = Column(Boolean, default=True)
    verify_pan = Column(Boolean, default=False)
    verify_bank = Column(Boolean, default=False)
    verify_aadhaar = Column(Boolean, default=False)
    
    # Workflow timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime)
    submitted_at = Column(DateTime)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Workflow users
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"))
    rejected_by = Column(Integer, ForeignKey("users.id"))
    
    # Additional fields
    rejection_reason = Column(Text)
    notes = Column(Text)
    # policies_data = Column(JSON)  # Store selected policy IDs - DISABLED until DB migration
    # offer_letter_data = Column(JSON)  # Store offer letter details - DISABLED until DB migration
    # salary_options_data = Column(JSON)  # Store salary calculation options - DISABLED until DB migration
    
    # Employee creation
    employee_id = Column(Integer, ForeignKey("employees.id"))  # Set after approval
    
    # System fields
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    business = relationship("Business")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    rejector = relationship("User", foreign_keys=[rejected_by])
    employee = relationship("Employee", back_populates="onboarding_forms")
    
    # Related records
    documents = relationship("OnboardingDocument", back_populates="form")
    policy_records = relationship("OnboardingPolicy", back_populates="form")
    # Mapping to master policies via join table
    # Use simple class-name string so SQLAlchemy can resolve after all models are imported
    form_policy_mappings = relationship("FormPolicyMapping", back_populates="form", cascade="all, delete-orphan")
    offer_letters = relationship("OfferLetter", back_populates="form")
    submissions = relationship("FormSubmission", back_populates="form")

    # Properties for API compatibility (temporarily disabled until DB migration)
    @property
    def policies(self):
        try:
            # Return list of attached master policy IDs via mapping table
            return [m.policy_id for m in getattr(self, 'form_policy_mappings') or []]
        except Exception:
            return []
    
    @policies.setter
    def policies(self, value):
        # Setter intentionally left blank; mappings should be managed via attach endpoints
        return
    
    @property
    def offer_letter(self):
        return None  # self.offer_letter_data
    
    @offer_letter.setter
    def offer_letter(self, value):
        pass  # self.offer_letter_data = value
    
    @property
    def salary_options(self):
        return None  # self.salary_options_data
    
    @salary_options.setter
    def salary_options(self, value):
        pass  # self.salary_options_data = value


class OnboardingDocument(Base):
    """Documents attached to onboarding forms"""
    __tablename__ = "onboarding_documents"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("onboarding_forms.id"), nullable=False)
    
    # Document details
    document_type = Column(String(100), nullable=False)  # policy, template, etc.
    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # Display options
    is_mandatory = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    description = Column(Text)
    
    # System fields
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    form = relationship("OnboardingForm", back_populates="documents")
    uploader = relationship("User")

class CandidateDocument(Base):
    __tablename__ = "candidate_documents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    form_token = Column(String, nullable=False)
    document_name = Column(String, nullable=False)
    document_type = Column(String, nullable=False)

    # Base64 needs Text
    file_path = Column(Text, nullable=False)
    business = relationship("Business")


class OnboardingPolicy(Base):
    """Policies attached to onboarding forms"""
    __tablename__ = "onboarding_policies"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("onboarding_forms.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    
    # Policy details
    policy_name = Column(String(255), nullable=False)
    policy_content = Column(Text)
    policy_file_path = Column(String(500))
    
    # Requirements
    requires_acknowledgment = Column(Boolean, default=True)
    is_mandatory = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    form = relationship("OnboardingForm", back_populates="policy_records")
    business = relationship("Business")
    creator = relationship("User")


class OfferLetter(Base):
    """Offer letters for onboarding"""
    __tablename__ = "offer_letters"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("onboarding_forms.id"), nullable=True)  # Allow standalone offer letters
    template_id = Column(Integer, ForeignKey("offer_letter_templates.id"))
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    
    # Offer details
    position_title = Column(String(255), nullable=False)
    department = Column(String(255))
    location = Column(String(255))
    
    # Compensation
    basic_salary = Column(String(100))
    gross_salary = Column(String(100))
    ctc = Column(String(100))
    
    # Dates
    joining_date = Column(Date)
    offer_valid_until = Column(Date)
    
    # Letter content
    letter_content = Column(Text)
    generated_file_path = Column(String(500))
    
    # Status
    is_generated = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    form = relationship("OnboardingForm", back_populates="offer_letters")
    template = relationship("OfferLetterTemplate")
    business = relationship("Business")
    creator = relationship("User")


class OfferLetterTemplate(Base):
    """Templates for offer letters"""
    __tablename__ = "offer_letter_templates"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Template details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    template_content = Column(Text, nullable=False)
    
    # Template variables (JSON)
    available_variables = Column(Text)  # JSON array of variable names
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")
    offer_letters = relationship("OfferLetter", back_populates="template")


class FormSubmission(Base):
    """Candidate form submissions - Compatible with existing database schema"""
    __tablename__ = "form_submissions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("onboarding_forms.id"), nullable=False)
    
    # Personal Information (existing fields)
    first_name = Column(String(100))
    last_name = Column(String(100))
    middle_name = Column(String(100))
    date_of_birth = Column(Date)
    gender = Column(String(20))
    marital_status = Column(String(20))
    blood_group = Column(String(10))
    nationality = Column(String(100))
    
    # Contact Information (existing fields)
    personal_email = Column(String(255))
    alternate_mobile = Column(String(20))
    
    # Address Information (existing fields)
    present_address = Column(Text)
    permanent_address = Column(Text)
    
    # Statutory Information (existing fields)
    pan_number = Column(String(20))
    aadhaar_number = Column(String(20))
    
    # Bank Information (existing fields)
    bank_name = Column(String(255))
    account_number = Column(String(50))
    ifsc_code = Column(String(20))
    
    # Emergency Contact (existing fields)
    emergency_contact_name = Column(String(255))
    emergency_contact_relationship = Column(String(100))
    emergency_contact_mobile = Column(String(20))
    
    # Education & Experience (existing fields)
    education_details = Column(Text)  # JSON
    experience_details = Column(Text)  # JSON
    
    # Documents (existing fields)
    uploaded_documents = Column(Text)  # JSON array of document info
    
    # Acknowledgments (existing fields)
    policy_acknowledgments = Column(Text)  # JSON of policy IDs acknowledged
    
    # System fields (existing fields)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))
    user_agent = Column(Text)

    # Relationships
    form = relationship("OnboardingForm", back_populates="submissions")
    
    # Helper properties for step-wise data (stored in JSON format)
    @property
    def step_data(self):
        """Get step-wise data from JSON fields"""
        try:
            return json.loads(self.education_details) if self.education_details else {}
        except:
            return {}
    
    @step_data.setter
    def step_data(self, value):
        """Set step-wise data as JSON"""
        self.education_details = json.dumps(value) if value else None
    
    @property
    def current_step(self):
        """Get current step from step data"""
        data = self.step_data
        return data.get("current_step", 1)
    
    @current_step.setter
    def current_step(self, value):
        """Set current step in step data"""
        data = self.step_data
        data["current_step"] = value
        self.step_data = data
    
    @property
    def steps_completed(self):
        """Get completed steps from step data"""
        data = self.step_data
        return data.get("steps_completed", [])
    
    @steps_completed.setter
    def steps_completed(self, value):
        """Set completed steps in step data"""
        data = self.step_data
        data["steps_completed"] = value
        self.step_data = data


class BulkOnboarding(Base):
    """Bulk onboarding operations"""
    __tablename__ = "bulk_onboarding"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Bulk operation details
    operation_name = Column(String(255), nullable=False)
    total_candidates = Column(Integer, default=0)
    successful_sends = Column(Integer, default=0)
    failed_sends = Column(Integer, default=0)
    
    # Verification options (applied to all)
    verify_mobile = Column(Boolean, default=True)
    verify_pan = Column(Boolean, default=False)
    verify_bank = Column(Boolean, default=False)
    verify_aadhaar = Column(Boolean, default=False)
    
    # Status
    status = Column(String(50), default="processing")  # processing, completed, failed
    
    # Results
    results_summary = Column(Text)  # JSON with detailed results
    error_log = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")


class OnboardingSettings(Base):
    """Onboarding configuration settings"""
    __tablename__ = "onboarding_settings"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Form settings
    form_expiry_days = Column(Integer, default=7)
    allow_form_editing = Column(Boolean, default=True)
    require_document_upload = Column(Boolean, default=True)
    
    # Notification settings
    send_welcome_email = Column(Boolean, default=True)
    send_reminder_emails = Column(Boolean, default=True)
    reminder_frequency_days = Column(Integer, default=2)
    
    # Verification settings
    default_verify_mobile = Column(Boolean, default=True)
    default_verify_pan = Column(Boolean, default=False)
    default_verify_bank = Column(Boolean, default=False)
    default_verify_aadhaar = Column(Boolean, default=False)
    
    # Auto-approval settings
    enable_auto_approval = Column(Boolean, default=False)
    auto_approval_criteria = Column(Text)  # JSON criteria
    
    # Custom fields
    custom_fields = Column(Text)  # JSON array of custom field definitions
    
    # Frontend-specific settings
    document_requirements = Column(Text)  # JSON object for document requirements
    field_requirements = Column(Text)  # JSON object for field requirements
    
    # Email templates
    welcome_email_template = Column(Text)
    reminder_email_template = Column(Text)
    approval_email_template = Column(Text)
    rejection_email_template = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")