"""
Onboarding API Endpoints - Multi-tenant (business_id) refactor
- Router prefix updated to include `{business_id}`
- All protected endpoints require `business_id: int` path param
- Business isolation enforced via `validate_business_access` dependency/helper
- Removed owner-based .in_() filters and get_user_business_ids usage
- Kept existing schemas and response models intact
"""


from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
import json
import logging
from pathlib import Path as FilePath
from uuid import uuid4
import re

from app.core.database import get_db
from app.core.config import settings
from app.api.v1.deps import get_current_admin, validate_business_access
from app.models.user import User
from app.models.onboarding import (
    OnboardingForm, OfferLetter, OfferLetterTemplate, OnboardingStatus, OnboardingSettings,
    BulkOnboarding, FormSubmission, OnboardingPolicy
)
from app.models.master_policy import MasterPolicy, FormPolicyMapping
from app.schemas.onboarding import (
    OnboardingResponseSchema, CreateOnboardingSchema, UpdateOnboardingSchema,
    OfferLetterCreate, OfferLetterResponse,
    OfferLetterTemplateCreate, OfferLetterTemplateResponse,
    OnboardingDashboardResponse, OnboardingListResponse,
    OnboardingSettingsUpdate, OnboardingSettingsResponse,
    BulkOnboardingCreate, BulkOnboardingResponse,
    FormSubmissionCreate, FormSubmissionResponse,
    OnboardingRejectionRequest, ApproveOnboardingRequest, TemplateGenerationRequest, TemplateGenerationResponse
    , DebugEnvironmentResponse
)
from app.schemas.employee import EmployeeCreate, OnboardingEmployeeCreate
from app.schemas.onboarding_additional import (
    SalaryCalculationRequest, OfferLetterGenerateRequest, PolicyAttachmentRequest,
    DocumentRequirementUpdateRequest, FieldRequirementUpdateRequest,
    BulkSendRequest, SendFormRequest, StepDataRequest,
    OTPSendRequest, OTPVerifyRequest, DocumentUploadRequest,
    FormCreateRequest, FinalizeAndSendRequest, AttachPoliciesResponse,
    SkipOfferLetterRequest, SkipOfferLetterResponse
)
from app.schemas.credits import CreditPurchaseRequest
from app.services.onboarding_service import OnboardingService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Onboarding"])  # ensure router has Onboarding tag by default

PROFILE_PHOTO_DIR = FilePath(settings.UPLOAD_DIR) / "profile_photos"
ONBOARDING_DOCUMENTS_DIR = FilePath(settings.UPLOAD_DIR) / "documents"
ALLOWED_PROFILE_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DOCUMENT_BUCKETS = (
    "aadhaar_card",
    "pan_card",
    "experience_letter",
    "higher_education_document",
    "payslips",
)
DOCUMENT_BUCKET_ALIASES = {
    "adhar_card": "aadhaar_card",
    "aadhar_card": "aadhaar_card",
    "aadhaar_card": "aadhaar_card",
    "pan_card": "pan_card",
    "experience_letter": "experience_letter",
    "higher_education_document": "higher_education_document",
    "resume": "higher_education_document",
    "payslip": "payslips",
    "payslips": "payslips",
}


# ---------------------------------------------------------------------------
# Helper validators (business-scoped)
# ---------------------------------------------------------------------------

def validate_form_access(db: Session, form_id: int, business_id: int, current_user: User):
    """Validate that the onboarding form belongs to the specified business."""
    form = db.query(OnboardingForm).filter(
        OnboardingForm.id == form_id,
        OnboardingForm.business_id == business_id
    ).first()
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
    return form


def _normalize_document_bucket(document_type: str) -> str:
    normalized = (document_type or "").strip().lower()
    return DOCUMENT_BUCKET_ALIASES.get(normalized, normalized)


def _build_form_submission_payload(submission_data: FormSubmissionCreate) -> dict:
    payload = submission_data.dict(exclude_none=True)

    if payload.get("mobile") and not payload.get("alternate_mobile"):
        payload["alternate_mobile"] = payload["mobile"]
    if payload.get("emergency_contact") and not payload.get("emergency_contact_mobile"):
        payload["emergency_contact_mobile"] = payload["emergency_contact"]

    allowed_fields = {
        "first_name", "middle_name", "last_name", "gender", "date_of_birth", "marital_status",
        "blood_group", "nationality", "personal_email", "mobile", "alternate_mobile", "home_phone",
        "father_name", "father_phone", "father_dob", "mother_name", "mother_phone", "mother_dob",
        "present_address", "present_address_line1", "present_address_line2", "present_city", "present_pincode", "present_state", "present_country",
        "permanent_address", "permanent_address_line1", "permanent_address_line2", "permanent_city", "permanent_pincode", "permanent_state", "permanent_country",
        "pan_number", "aadhaar_number", "passport_number", "driving_license_number", "uan_number", "esi_number",
        "bank_name", "account_number", "ifsc_code", "account_holder_name",
        "emergency_contact", "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_mobile",
        "mobile_verified", "education_details", "experience_details", "uploaded_documents", "policy_acknowledgments",
        "ip_address", "user_agent",
    }

    return {key: value for key, value in payload.items() if key in allowed_fields}


def _build_form_submission_response(submission_data: FormSubmissionCreate, submission: FormSubmission) -> dict:
    response_payload = submission_data.dict()
    response_payload.update({
        "id": submission.id,
        "form_id": submission.form_id,
        "submitted_at": submission.submitted_at,
    })
    return response_payload


@router.get("/migrate-schema")
async def migrate_schema(db: Session = Depends(get_db)):
    columns_to_add = {
        "mobile": "VARCHAR(20)",
        "home_phone": "VARCHAR(20)",
        "father_name": "VARCHAR(255)",
        "father_phone": "VARCHAR(20)",
        "father_dob": "DATE",
        "mother_name": "VARCHAR(255)",
        "mother_phone": "VARCHAR(20)",
        "mother_dob": "DATE",
        "passport_number": "VARCHAR(50)",
        "driving_license_number": "VARCHAR(50)",
        "uan_number": "VARCHAR(50)",
        "esi_number": "VARCHAR(50)",
        "present_address_line1": "VARCHAR(255)",
        "present_address_line2": "VARCHAR(255)",
        "present_city": "VARCHAR(100)",
        "present_pincode": "VARCHAR(20)",
        "present_state": "VARCHAR(100)",
        "present_country": "VARCHAR(100)",
        "permanent_address_line1": "VARCHAR(255)",
        "permanent_address_line2": "VARCHAR(255)",
        "permanent_city": "VARCHAR(100)",
        "permanent_pincode": "VARCHAR(20)",
        "permanent_state": "VARCHAR(100)",
        "permanent_country": "VARCHAR(100)",
        "account_holder_name": "VARCHAR(255)",
        "emergency_contact": "VARCHAR(20)",
        "mobile_verified": "BOOLEAN DEFAULT FALSE",
    }
    from sqlalchemy import text
    results = []
    for col_name, col_type in columns_to_add.items():
        try:
            db.execute(text(f"ALTER TABLE form_submissions ADD COLUMN {col_name} {col_type};"))
            db.commit()
            results.append(f"Added {col_name}")
        except Exception as e:
            db.rollback()
            results.append(f"Skipped {col_name} ({e})")
    return {"results": results}


def _build_candidate_documents_response(db: Session, business_id: int, form_token: str):
    from app.models.onboarding import CandidateDocument

    documents = {bucket: [] for bucket in DOCUMENT_BUCKETS}
    records = (
        db.query(CandidateDocument)
        .filter(
            CandidateDocument.business_id == business_id,
            CandidateDocument.form_token == form_token,
        )
        .order_by(CandidateDocument.id.asc())
        .all()
    )

    for record in records:
        bucket = _normalize_document_bucket(record.document_type)
        if bucket in documents:
            documents[bucket].append(record.file_path)

    return documents
import base64


@router.post("/documents")
async def upload_onboarding_documents(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    form_token: str = Query(..., description="Onboarding form token"),
    document_name: str = Query(..., description="Document name"),
    document_type: str = Query(..., description="Document type"),
    file: List[UploadFile] = File(..., description="Document file(s)"),
    db: Session = Depends(get_db),
):
    """Upload onboarding documents and store real file paths in DB."""

    from app.models.onboarding import CandidateDocument

    # validate onboarding form
    form = (
        db.query(OnboardingForm)
        .filter(
            OnboardingForm.business_id == business_id,
            OnboardingForm.form_token == form_token,
        )
        .first()
    )

    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding form not found",
        )

    bucket = _normalize_document_bucket(document_type)

    if bucket not in DOCUMENT_BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid document_type '{document_type}'. "
                f"Allowed values: {', '.join(DOCUMENT_BUCKETS)}"
            ),
        )

    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    ONBOARDING_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    uploaded_files = []

    try:
        for upload_file in file:
            # validate filename
            if not upload_file.filename:
                raise HTTPException(
                    status_code=400,
                    detail="One or more files missing filename",
                )

            # read file bytes
            file_contents = await upload_file.read()

            if not file_contents:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload_file.filename}' is empty",
                )

            safe_form_token = re.sub(r"[^A-Za-z0-9_.-]", "_", form_token).strip("._-") or "form"
            safe_document_type = re.sub(r"[^A-Za-z0-9_.-]", "_", bucket).strip("._-") or "document"
            original_suffix = FilePath(upload_file.filename).suffix.lower()
            stored_filename = f"{safe_form_token}_{safe_document_type}_{uuid4().hex}{original_suffix}"
            stored_file_path = ONBOARDING_DOCUMENTS_DIR / stored_filename
            stored_file_path_str = str(stored_file_path).replace("\\", "/")

            with open(stored_file_path, "wb") as buffer:
                buffer.write(file_contents)

            # Format as absolute URL
            base_url = str(request.base_url)
            if not base_url.endswith("/"):
                base_url += "/"
            relative_path = stored_file_path_str.lstrip("/")
            full_url = f"{base_url}{relative_path}"

            # response list
            uploaded_files.append(
                {
                    "file_name": stored_filename,
                    "file_path": full_url,
                }
            )

            # DB record
            record = CandidateDocument(
                business_id=business_id,
                form_token=form_token,
                document_name=document_name,
                document_type=bucket,
                file_path=full_url,
            )

            db.add(record)

        # save
        db.commit()

        # grouped response
        documents = _build_candidate_documents_response(
            db,
            business_id,
            form_token,
        )

        return {
            "success": True,
            "business_id": business_id,
            "form_token": form_token,
            "documents": documents,
            "uploaded_files": uploaded_files,
            "message": "Document uploaded successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Failed to upload onboarding documents"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(exc)}",
        ) from exc

    finally:
        for upload_file in file:
            try:
                await upload_file.close()
            except Exception:
                pass

from fastapi import UploadFile, File, HTTPException, Query, Path, status, Request
from pathlib import Path as FilePath
from uuid import uuid4
import base64
import re

# import your db session + model
# from app.db.session import SessionLocal
# from app.models.onboarding import OnboardingCandidate


@router.post("/profile-photo")
async def upload_onboarding_profile_photo(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    form_token: str = Query(..., description="Onboarding form token"),
    profile_photo: UploadFile = File(..., description="Profile photo file"),
    db: Session = Depends(get_db),
):
    """Upload onboarding candidate profile photo, save locally and return file path."""

    original_filename = profile_photo.filename or ""
    file_extension = FilePath(original_filename).suffix.lower()
    content_type = (profile_photo.content_type or "").lower()

    if (
        content_type not in ALLOWED_PROFILE_PHOTO_CONTENT_TYPES
        or file_extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPG, JPEG, and PNG profile photos are allowed",
        )

    try:
        # read uploaded image bytes
        contents = await profile_photo.read()

        # Ensure upload directory exists
        PROFILE_PHOTO_DIR.mkdir(parents=True, exist_ok=True)

        # Save the file locally
        safe_form_token = re.sub(r"[^A-Za-z0-9_.-]", "_", form_token).strip("._-") or "profile"
        stored_filename = f"photo_{safe_form_token}_{uuid4().hex}{file_extension}"
        stored_file_path = PROFILE_PHOTO_DIR / stored_filename
        stored_file_path_str = str(stored_file_path).replace("\\", "/")

        # Format as absolute URL
        base_url = str(request.base_url)
        if not base_url.endswith("/"):
            base_url += "/"
        relative_path = stored_file_path_str.lstrip("/")
        full_url = f"{base_url}{relative_path}"

        with open(stored_file_path, "wb") as buffer:
            buffer.write(contents)

        # Save the profile image URL to the FormSubmission record
        form = (
            db.query(OnboardingForm)
            .filter(
                OnboardingForm.business_id == business_id,
                OnboardingForm.form_token == form_token,
            )
            .first()
        )
        if form:
            submission = (
                db.query(FormSubmission)
                .filter(FormSubmission.form_id == form.id)
                .order_by(FormSubmission.id.desc())
                .first()
            )
            if submission:
                # Update the FormSubmission profile image URL
                submission.profile_image = full_url
            
            # Ensure an EmployeeProfile exists and update its image URL if employee is already linked
            if form.employee_id:
                from app.models.employee import EmployeeProfile
                # Try to fetch existing profile
                profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == form.employee_id).first()
                if profile:
                    profile.profile_image_url = full_url
                else:
                    # Create a new EmployeeProfile record linked to the employee
                    new_profile = EmployeeProfile(
                        employee_id=form.employee_id,
                        profile_image_url=full_url,
                    )
                    db.add(new_profile)
            
            db.commit()

        return {
            "success": True,
            "business_id": business_id,
            "form_token": form_token,
            "file_name": original_filename,
            "file_path": full_url,
            "message": "Profile photo uploaded successfully",
        }

    except Exception as exc:
        logger.exception("Failed to upload onboarding profile photo")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload profile photo: {str(exc)}",
        ) from exc

    finally:
        await profile_photo.close()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=OnboardingDashboardResponse)
async def get_onboarding_dashboard(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        return service.get_dashboard_data(business_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
@router.post("/create-employee", response_model=dict)
async def create_employee(
    employee_data: OnboardingEmployeeCreate,
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

        # Department: accept `department_id` (int) or `department` (name)
        if getattr(employee_data, 'department_id', None) is not None:
            from app.models.department import Department
            dept = db.query(Department).filter(Department.id == int(employee_data.department_id), Department.business_id == business_id).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Department id {employee_data.department_id} not found")
            department_id = int(employee_data.department_id)
        elif getattr(employee_data, 'department', None):
            from app.models.department import Department
            department_id = resolve(Department, employee_data.department)
            if employee_data.department and department_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department '{employee_data.department}' not found")

        # Designation: accept `designation_id` or `designation` (name)
        if getattr(employee_data, 'designation_id', None) is not None:
            from app.models.designations import Designation
            des = db.query(Designation).filter(Designation.id == int(employee_data.designation_id), Designation.business_id == business_id).first()
            if not des:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Designation id {employee_data.designation_id} not found")
            designation_id = int(employee_data.designation_id)
        elif getattr(employee_data, 'designation', None):
            from app.models.designations import Designation
            designation_id = resolve(Designation, employee_data.designation)
            if employee_data.designation and designation_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Designation '{employee_data.designation}' not found")

        # Location: accept `location_id` or `location` (name)
        if getattr(employee_data, 'location_id', None) is not None:
            from app.models.location import Location
            loc = db.query(Location).filter(Location.id == int(employee_data.location_id), Location.business_id == business_id).first()
            if not loc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location id {employee_data.location_id} not found")
            location_id = int(employee_data.location_id)
        elif getattr(employee_data, 'location', None):
            from app.models.location import Location
            location_id = resolve(Location, employee_data.location)
            if employee_data.location and location_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Location '{employee_data.location}' not found")
        
        # Cost center: accept `cost_center_id` or `cost_center` (name)
        if getattr(employee_data, 'cost_center_id', None) is not None:
            from app.models.cost_center import CostCenter
            cc = db.query(CostCenter).filter(CostCenter.id == int(employee_data.cost_center_id), CostCenter.business_id == business_id).first()
            if not cc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Cost center id {employee_data.cost_center_id} not found")
            cost_center_id = int(employee_data.cost_center_id)
        elif getattr(employee_data, 'cost_center', None):
            from app.models.cost_center import CostCenter
            cost_center_id = resolve(CostCenter, employee_data.cost_center)
            if employee_data.cost_center and cost_center_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cost center '{employee_data.cost_center}' not found")

        # Grade: accept `grade_id` or `grade` (name)
        if getattr(employee_data, 'grade_id', None) is not None:
            from app.models.grades import Grade
            gd = db.query(Grade).filter(Grade.id == int(employee_data.grade_id), Grade.business_id == business_id).first()
            if not gd:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Grade id {employee_data.grade_id} not found")
            grade_id = int(employee_data.grade_id)
        elif getattr(employee_data, 'grade', None):
            from app.models.grades import Grade
            grade_id = resolve(Grade, employee_data.grade)
            if employee_data.grade and grade_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Grade '{employee_data.grade}' not found")

        # Shift policy: accept `shift_policy_id` or `shift_policy` (name)
        if getattr(employee_data, 'shift_policy_id', None) is not None:
            from app.models.shift_policy import ShiftPolicy
            sp = db.query(ShiftPolicy).filter(ShiftPolicy.id == int(employee_data.shift_policy_id), ShiftPolicy.business_id == business_id).first()
            if not sp:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Shift policy id {employee_data.shift_policy_id} not found")
            shift_policy_id = int(employee_data.shift_policy_id)
        elif getattr(employee_data, 'shift_policy', None):
            from app.models.shift_policy import ShiftPolicy
            shift_policy_id = resolve(ShiftPolicy, employee_data.shift_policy)
            if employee_data.shift_policy and shift_policy_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Shift policy '{employee_data.shift_policy}' not found")

        # Week off policy: accept `week_off_policy_id` or `week_off_policy` (name)
        if getattr(employee_data, 'week_off_policy_id', None) is not None:
            from app.models.weekoff_policy import WeekOffPolicy
            wp = db.query(WeekOffPolicy).filter(WeekOffPolicy.id == int(employee_data.week_off_policy_id), WeekOffPolicy.business_id == business_id).first()
            if not wp:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Week off policy id {employee_data.week_off_policy_id} not found")
            weekoff_policy_id = int(employee_data.week_off_policy_id)
        elif getattr(employee_data, 'week_off_policy', None):
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

        # Validate reporting manager id if provided
        reporting_manager_id = None
        if getattr(employee_data, 'reporting_manager_id', None) is not None:
            try:
                mgr_id = int(employee_data.reporting_manager_id)
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reporting_manager_id")
            mgr = db.query(Employee).filter(Employee.id == mgr_id, Employee.business_id == business_id).first()
            if not mgr:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reporting manager id {mgr_id} not found")
            reporting_manager_id = mgr_id

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
            date_of_joining=getattr(employee_data, 'date_of_joining', None),
            date_of_birth=getattr(employee_data, 'date_of_birth', None),
            date_of_confirmation=getattr(employee_data, 'date_of_confirmation', None),
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
            send_mobile_login=getattr(employee_data, 'send_mobile_login', False),
            send_web_login=getattr(employee_data, 'send_web_login', True),
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
            # Foreign keys
            "business_id": new_employee.business_id,
            "location_id": new_employee.location_id,
            "cost_center_id": new_employee.cost_center_id,
            "department_id": new_employee.department_id,
            "grade_id": new_employee.grade_id,
            "designation_id": new_employee.designation_id,
            "shift_policy_id": new_employee.shift_policy_id,
            "week_off_policy_id": new_employee.weekoff_policy_id,
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



@router.get("/credit-pricing", response_model=dict)
async def get_credit_pricing_legacy(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        pricing_data = {
            "packages": [
                {"credits": 50, "price": 200, "per_credit": 4.00, "discount": "0%"},
                {"credits": 100, "price": 350, "per_credit": 3.50, "discount": "12.5%"},
                {"credits": 250, "price": 750, "per_credit": 3.00, "discount": "25%"},
                {"credits": 500, "price": 1250, "per_credit": 2.50, "discount": "37.5%"}
            ],
            "currency": "USD",
            "validity_months": 12,
            "payment_methods": ["Credit Card", "Bank Transfer", "PayPal"]
        }
        return pricing_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Salary calculation
# ---------------------------------------------------------------------------
@router.post("/{form_id}/calculate-salary", response_model=dict)
async def calculate_salary_for_offer_letter(
    business_id: int = Path(...),
    form_id: int = Path(...),
    calculation_data: SalaryCalculationRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.salary_calculation_service import SalaryCalculationService
        # Ensure form exists within business
        form = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id == business_id
        ).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        calc_service = SalaryCalculationService(db)
        result = calc_service.calculate_salary_breakup(
            gross_salary=calculation_data.gross_salary,
            salary_structure_id=calculation_data.salary_structure_id,
            employee_id=calculation_data.employee_id,
            business_id=business_id,
            options=calculation_data.options
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/salary-structures", response_model=List[dict])
async def get_salary_structures_for_offer_letter(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.salary_calculation_service import SalaryCalculationService
        calc_service = SalaryCalculationService(db)
        return calc_service.get_salary_structures(business_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{form_id}/employee-profile", response_model=dict)
async def get_employee_profile_for_offer_letter(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id == business_id
        ).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        # Build employee_profile from onboarding form (prefer form values; override with employee record if linked)
        employee_profile = {
            "candidate_name": form.candidate_name,
            "candidate_email": form.candidate_email,
            "candidate_mobile": form.candidate_mobile,
            "offer_letter": None,
            "salary_options": None,
            "policies": []
        }

        # Try to populate offer_letter/salary_options/policies from form properties (may be None)
        try:
            employee_profile["offer_letter"] = form.offer_letter if getattr(form, 'offer_letter', None) is not None else None
        except Exception:
            employee_profile["offer_letter"] = None

        try:
            employee_profile["salary_options"] = form.salary_options if getattr(form, 'salary_options', None) is not None else None
        except Exception:
            employee_profile["salary_options"] = None

        try:
            employee_profile["policies"] = form.policies if getattr(form, 'policies', None) is not None else []
        except Exception:
            employee_profile["policies"] = []

        # If the form has an associated offer_letter record(s), prefer the first record for nested fields
        if form.offer_letters and len(form.offer_letters) > 0:
            offer = form.offer_letters[0]
            nested_offer = {
                "designation": getattr(offer, 'position_title', None),
                "department": getattr(offer, 'department', None),
                "joining_date": offer.joining_date.isoformat() if getattr(offer, 'joining_date', None) else None,
                "work_location": getattr(offer, 'location', None),
                "employment_type": getattr(offer, 'employment_type', None) if hasattr(offer, 'employment_type') else None,
                "reporting_manager": getattr(offer, 'reporting_manager', None) if hasattr(offer, 'reporting_manager') else None
            }
            # Merge into employee_profile.offer_letter (replace or create)
            if employee_profile.get("offer_letter") and isinstance(employee_profile.get("offer_letter"), dict):
                merged = dict(employee_profile.get("offer_letter"))
                merged.update({k: v for k, v in nested_offer.items() if v is not None})
                employee_profile["offer_letter"] = merged
            else:
                employee_profile["offer_letter"] = nested_offer

        # If form linked to an employee, enrich profile with employee DB values
        if form.employee_id:
            from app.models.employee import Employee
            employee = db.query(Employee).filter(Employee.id == form.employee_id, Employee.business_id == business_id).first()
            if employee:
                # keep candidate details but add internal ids and other fields
                employee_profile.update({
                    "employee_id": employee.id,
                    "location": getattr(employee, 'location_id', None),
                    "location_id": getattr(employee, 'location_id', None),
                    "department": getattr(employee, 'department_id', None),
                    "department_id": getattr(employee, 'department_id', None),
                    "designation": getattr(employee, 'designation_id', None),
                    "designation_id": getattr(employee, 'designation_id', None),
                    "grade": getattr(employee, 'grade_id', None),
                    "grade_id": getattr(employee, 'grade_id', None),
                    "cost_center": getattr(employee, 'cost_center_id', None),
                    "cost_center_id": getattr(employee, 'cost_center_id', None),
                    "shift_policy": getattr(employee, 'shift_policy_id', None),
                    "shift_policy_id": getattr(employee, 'shift_policy_id', None),
                    "date_of_birth": employee.date_of_birth.isoformat() if getattr(employee, 'date_of_birth', None) else None,
                    "gender": getattr(employee, 'gender', None),
                    "joining_date": getattr(employee, 'date_of_joining', None).isoformat() if getattr(employee, 'date_of_joining', None) else None,
                    "confirmation_date": getattr(employee, 'date_of_confirmation', None)
                })

        # Dropdowns (scoped)
        from app.models.location import Location
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.grades import Grade
        from app.models.cost_center import CostCenter
        from app.models.work_shifts import WorkShift

        locations = db.query(Location).filter(Location.business_id == business_id, Location.is_active == True).all()
        departments = db.query(Department).filter(Department.business_id == business_id, Department.is_active == True).all()
        designations = db.query(Designation).filter(Designation.business_id == business_id, Designation.is_active == True).all()
        grades = db.query(Grade).filter(Grade.business_id == business_id, Grade.is_active == True).all()
        cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business_id, CostCenter.is_active == True).all()
        work_shifts = db.query(WorkShift).filter(WorkShift.business_id == business_id, WorkShift.is_active == True).all()

        return {
            "success": True,
            "employee_profile": employee_profile,
            "dropdown_options": {
                "locations": [{"id": l.id, "name": l.name} for l in locations],
                "departments": [{"id": d.id, "name": d.name} for d in departments],
                "designations": [{"id": d.id, "name": d.name} for d in designations],
                "grades": [{"id": g.id, "name": g.name} for g in grades],
                "cost_centers": [{"id": c.id, "name": c.name} for c in cost_centers],
                "work_shifts": [{"id": w.id, "name": w.name} for w in work_shifts]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Offer letter generation
# ---------------------------------------------------------------------------
@router.post("/{form_id}/generate-offer-letter", response_model=dict)
async def generate_complete_offer_letter(
    business_id: int = Path(...),
    form_id: int = Path(...),
    offer_data: OfferLetterGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Validate form belongs to business
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        # Template lookup scoped
        template = None
        if offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.id == offer_data.template_id,
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            ).first()

        # Calculate salary if provided (scoped)
        salary_breakup = None
        if offer_data.gross_salary:
            from app.services.salary_calculation_service import SalaryCalculationService
            calc_service = SalaryCalculationService(db)
            salary_breakup = calc_service.calculate_salary_breakup(
                gross_salary=offer_data.gross_salary,
                salary_structure_id=offer_data.salary_structure_id,
                employee_id=form.employee_id,
                business_id=business_id,
                options=offer_data.salary_options
            )

        # Build letter content
        letter_content = template.template_content if template else ""
        # Replace variables (simple replace function)
        def replace_template_variables(template_content: str, data: dict) -> str:
            result = template_content
            for key, value in data.items():
                placeholder = f"{{{{{key}}}}}"
                result = result.replace(placeholder, str(value) if value is not None else "")
            return result

        business = db.query(User).filter(User.id == current_user.id).first()
        template_variables = {
            "company_name": getattr(business, 'business_name', 'Company') if business else "Company",
            "company_address": getattr(business, 'address', '') if business else "",
            "offer_date": datetime.now().strftime("%d-%b-%Y"),
            "candidate_name": form.candidate_name or "",
            "candidate_email": form.candidate_email or "",
            "gross_salary": str(offer_data.gross_salary or 0)
        }

        if letter_content:
            letter_content = replace_template_variables(letter_content, template_variables)

        # Persist offer letter (scoped)
        actual_template_id = template.id if template else None
        
        existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id, OfferLetter.business_id == business_id).first()
        if existing_offer:
            existing_offer.template_id = actual_template_id
            existing_offer.position_title = offer_data.position_title or ""
            existing_offer.department = offer_data.department or ""
            existing_offer.location = offer_data.location or ""
            existing_offer.basic_salary = str(salary_breakup['earnings'].get('Basic Salary', 0)) if salary_breakup else (offer_data.basic_salary or "")
            existing_offer.gross_salary = str(offer_data.gross_salary or 0)
            existing_offer.ctc = str(salary_breakup['ctc']) if salary_breakup else (offer_data.ctc or "")
            existing_offer.joining_date = offer_data.joining_date
            existing_offer.offer_valid_until = offer_data.offer_valid_until
            existing_offer.letter_content = letter_content
            existing_offer.is_generated = True
            existing_offer.updated_at = datetime.now()
            offer_letter = existing_offer
        else:
            offer_letter = OfferLetter(
                form_id=form_id,
                template_id=actual_template_id,
                position_title=offer_data.position_title or "",
                department=offer_data.department or "",
                location=offer_data.location or "",
                basic_salary=str(salary_breakup['earnings'].get('Basic Salary', 0)) if salary_breakup else (offer_data.basic_salary or ""),
                gross_salary=str(offer_data.gross_salary or 0),
                ctc=str(salary_breakup['ctc']) if salary_breakup else (offer_data.ctc or ""),
                joining_date=offer_data.joining_date,
                offer_valid_until=offer_data.offer_valid_until,
                letter_content=letter_content,
                is_generated=True,
                is_sent=False,
                business_id=business_id,
                created_by=current_user.id,
                created_at=datetime.now()
            )
            db.add(offer_letter)

        # Generate physical PDF file
        try:
            from app.services.pdf_professional_template import professional_pdf_service
            from app.services.pdf_data_mapper import pdf_data_mapper
            from app.services.file_upload_service import ensure_dir
            import os
            
            candidate_data = pdf_data_mapper.map_onboarding_form_to_pdf_data(
                form=form,
                salary_data=salary_breakup,
                offer_letter=offer_letter
            )
            
            pdf_buffer = professional_pdf_service.generate_offer_letter_pdf(
                candidate_data=candidate_data
            )
            
            if pdf_buffer:
                filename = professional_pdf_service.generate_filename(form.candidate_name or "Candidate", "Offer_Letter")
                uploads_dir = os.getenv("UPLOAD_DIR", "uploads")
                dest_folder = os.path.join(uploads_dir, "offer_letters")
                ensure_dir(dest_folder)
                
                saved_path = os.path.join(dest_folder, filename).replace('\\', '/')
                with open(saved_path, "wb") as f:
                    f.write(pdf_buffer.read())
                
                offer_letter.generated_file_path = saved_path
        except Exception as pdf_err:
            import logging
            logging.error(f"Failed to generate physical PDF for offer letter: {pdf_err}")

        db.commit()
        db.refresh(offer_letter)

        return {
            "success": True,
            "offer_letter_id": offer_letter.id,
            "form_id": form_id,
            "salary_breakup": salary_breakup,
            "template_name": template.name if template else "Default",
            "generated_at": offer_letter.created_at.isoformat() if offer_letter.created_at else None,
            "file_path": offer_letter.generated_file_path
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Offer letter templates
# ---------------------------------------------------------------------------
@router.get("/templates", response_model=List[OfferLetterTemplateResponse])
async def get_offer_letter_templates(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        templates = db.query(OfferLetterTemplate).filter(
            OfferLetterTemplate.business_id == business_id,
            OfferLetterTemplate.is_active == True
        ).order_by(OfferLetterTemplate.name).all()
        return templates
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/templates", response_model=OfferLetterTemplateResponse)
async def create_offer_letter_template(
    business_id: int = Path(...),
    template_data: OfferLetterTemplateCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        template = OfferLetterTemplate(
            business_id=business_id,
            name=template_data.name,
            description=template_data.description,
            template_content=template_data.template_content,
            available_variables=template_data.available_variables,
            is_active=template_data.is_active,
            is_default=template_data.is_default,
            created_by=current_user.id,
            created_at=datetime.now()
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Offer letters list & create (standalone)
# ---------------------------------------------------------------------------
@router.post("/offer-letters", response_model=OfferLetterResponse)
async def generate_offer_letter(
    business_id: int = Path(...),
    offer_data: OfferLetterCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        template = None
        if offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.id == offer_data.template_id,
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            ).first()

        offer_letter = OfferLetter(
            form_id=None,
            template_id=offer_data.template_id,
            position_title=offer_data.position_title,
            department=offer_data.department,
            location=offer_data.location,
            basic_salary=offer_data.basic_salary,
            gross_salary=offer_data.gross_salary,
            ctc=offer_data.ctc,
            joining_date=offer_data.joining_date,
            offer_valid_until=offer_data.offer_valid_until,
            letter_content=offer_data.letter_content or (template.template_content if template else ""),
            is_generated=True,
            is_sent=False,
            business_id=business_id,
            created_by=current_user.id,
            created_at=datetime.now()
        )
        db.add(offer_letter)
        db.commit()
        db.refresh(offer_letter)
        return offer_letter
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/offer-letters", response_model=List[OfferLetterResponse])
async def get_offer_letters(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Business-scoped offer letters: prefer direct business_id filter for isolation
        offer_letters = db.query(OfferLetter).filter(OfferLetter.business_id == business_id).order_by(desc(OfferLetter.created_at)).all()
        return offer_letters
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/policy-templates", response_model=List[dict])
async def get_policy_templates(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.models.master_policy import MasterPolicy
        policies = db.query(MasterPolicy).filter(MasterPolicy.business_id == business_id).all()
        
        if not policies:
            # Auto-create some default master policies for this business so they can be attached and used without error
            default_policies = [
                {"name": "Employee Handbook", "description": "Complete guide to company policies and procedures", "type": "handbook", "is_mandatory": True, "requires_acknowledgment": True},
                {"name": "Code of Conduct", "description": "Professional behavior and ethical guidelines", "type": "conduct", "is_mandatory": True, "requires_acknowledgment": True},
                {"name": "IT Security Policy", "description": "Information technology security guidelines and requirements", "type": "it_security", "is_mandatory": True, "requires_acknowledgment": True},
                {"name": "Remote Work Policy", "description": "Guidelines for remote work arrangements", "type": "remote_work", "is_mandatory": False, "requires_acknowledgment": True},
                {"name": "Leave Policy", "description": "Annual leave, sick leave, and other time-off policies", "type": "leave", "is_mandatory": True, "requires_acknowledgment": True},
                {"name": "Health & Safety Policy", "description": "Workplace health and safety guidelines", "type": "health_safety", "is_mandatory": True, "requires_acknowledgment": True}
            ]
            for dp in default_policies:
                new_policy = MasterPolicy(
                    business_id=business_id,
                    name=dp["name"],
                    description=dp["description"],
                    type=dp["type"],
                    is_mandatory=dp["is_mandatory"],
                    requires_acknowledgment=dp["requires_acknowledgment"],
                    created_by=current_user.id
                )
                db.add(new_policy)
            db.commit()
            policies = db.query(MasterPolicy).filter(MasterPolicy.business_id == business_id).all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "type": p.type or "other",
                "is_mandatory": bool(p.is_mandatory),
                "requires_acknowledgment": bool(p.requires_acknowledgment),
                "file_path": p.file_path or ""
            }
            for p in policies
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/attach-policies", response_model=AttachPoliciesResponse)
async def attach_policies_to_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    policy_data: PolicyAttachmentRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        selected_policy_ids = policy_data.policy_ids or []
        # Validate requested master policies belong to this business
        if not selected_policy_ids:
            return {"success": True, "message": "No policies provided", "form_id": form_id, "attached_policies": []}

        masters = db.query(MasterPolicy).filter(MasterPolicy.id.in_(selected_policy_ids), MasterPolicy.business_id == business_id).all()
        found_ids = {m.id for m in masters}
        missing = [pid for pid in selected_policy_ids if pid not in found_ids]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Master policies not found or not owned by business: {missing}")

        # Remove existing onboarding policy records for this form (scoped by business)
        db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).delete()

        # Remove existing form-policy mappings for this form (scoped by business)
        db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form_id, FormPolicyMapping.business_id == business_id).delete()

        # Preserve order as sent by client
        attached_masters = []
        for i, pid in enumerate(selected_policy_ids):
            master = next((m for m in masters if m.id == pid), None)
            if not master:
                continue

            # Create onboarding policy record for backward compatibility
            policy_kwargs = dict(
                form_id=form_id,
                policy_name=master.name or f"Policy {pid}",
                policy_content=master.description,
                policy_file_path=master.file_path,
                requires_acknowledgment=bool(master.requires_acknowledgment),
                is_mandatory=bool(master.is_mandatory),
                display_order=i,
                created_by=current_user.id
            )
            policy_kwargs['business_id'] = business_id
            policy = OnboardingPolicy(**policy_kwargs)
            db.add(policy)

            # Create mapping entry
            mapping_kwargs = dict(
                form_id=form_id,
                policy_id=master.id,
                business_id=business_id,
                created_by=current_user.id
            )
            mapping = FormPolicyMapping(**mapping_kwargs)
            db.add(mapping)

            attached_masters.append(master)

        db.commit()

        return {
            "success": True,
            "message": "Successfully attached policies to form",
            "form_id": form_id,
            "attached_policies": attached_masters
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{form_id}/policies", response_model=List[dict])
async def get_form_policies(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        _ = validate_form_access(db, form_id, business_id, current_user)
        policies = db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).order_by(OnboardingPolicy.display_order).all()
        return [
            {
                "id": p.id,
                "policy_name": p.policy_name,
                "policy_content": p.policy_content,
                "policy_file_path": p.policy_file_path,
                "requires_acknowledgment": p.requires_acknowledgment,
                "is_mandatory": p.is_mandatory,
                "display_order": p.display_order,
                "created_at": p.created_at.isoformat() if p.created_at else None
            } for p in policies
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@router.get("/settings", response_model=OnboardingSettingsResponse, operation_id="get_onboarding_settings_v1")
async def get_onboarding_settings(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        return service.get_onboarding_settings(business_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/settings", response_model=OnboardingSettingsResponse)
async def update_onboarding_settings(
    business_id: int = Path(...),
    settings_data: OnboardingSettingsUpdate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        update_dict = settings_data.dict(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
        service = OnboardingService(db)
        return service.update_onboarding_settings(business_id, settings_data, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Onboarding forms CRUD
# ---------------------------------------------------------------------------
@router.get("/", response_model=OnboardingListResponse)
async def list_onboarding_forms(
    business_id: int = Path(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    form_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        query = db.query(OnboardingForm).filter(OnboardingForm.business_id == business_id)
        if form_status and form_status.lower() not in ['all', '']:
            query = query.filter(OnboardingForm.status == form_status)
        if search and search.strip():
            term = f"%{search}%"
            query = query.filter(
                (OnboardingForm.candidate_name.ilike(term)) |
                (OnboardingForm.candidate_email.ilike(term)) |
                (OnboardingForm.candidate_mobile.ilike(term))
            )
        total = query.count()
        offset = (page - 1) * limit
        forms = query.offset(offset).limit(limit).all()
        return {"items": forms, "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/create", response_model=OnboardingResponseSchema)
async def create_onboarding_form(
    business_id: int = Path(...),
    form_data: CreateOnboardingSchema = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        form = service.create_onboarding_form(form_data, business_id, current_user.id)
        return form
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))




@router.get("/forms/{form_id:int}", response_model=OnboardingResponseSchema)
async def get_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        return form
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{form_id}", response_model=OnboardingResponseSchema)
async def update_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    form_data: UpdateOnboardingSchema = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Use service layer to handle nested fields and response shaping
        service = OnboardingService(db)
        result = service.update_onboarding_form(form_id, form_data, business_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{form_id}")
async def delete_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        form.is_active = False
        form.updated_at = datetime.now()
        db.commit()
        return {"success": True, "message": "Onboarding form deleted successfully", "form_id": form_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Send / Submit / Approve / Reject endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{form_id}/skip-offer-letter",
    response_model=SkipOfferLetterResponse,
    summary="Create or update onboarding form skipping offer letter",
)
async def skip_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    form_data: SkipOfferLetterRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Create or update an onboarding form while skipping offer letter generation.

    - If a form with the given `form_id` exists for the business, it is updated.
    - If not found, a new form is created.
    - Policies (list of master policy IDs) are attached/replaced for the form.
    - `offer_letter` and `salary_options` fields are accepted in the payload but ignored
      (they are skipped intentionally).
    - `candidate_mobile_verified` defaults to `false`.
    """
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        result = service.create_or_update_onboarding_skip_offer_letter(
            form_id=form_id,
            form_data=form_data,
            business_id=business_id,
            user_id=current_user.id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{form_id}/finalize",
    response_model=OnboardingResponseSchema,
    summary="Finalize onboarding form and optionally send onboarding email"
)
async def finalize_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    payload: FinalizeAndSendRequest = Body(..., description="Finalize payload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Finalize the onboarding form creation process.
    - Updates candidate email if provided in the payload.
    - Sets the status to 'SENT'.
    - If `send_email` is true, sends an onboarding email with the link to the candidate.
    """
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        
        # 1. Update candidate email if provided in payload
        if payload.candidate_email:
            form.candidate_email = payload.candidate_email
            
        # 2. Finalize status and timestamp
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        form.updated_at = datetime.now()
        db.commit()
        db.refresh(form)
        
        # 3. Send email if requested
        if payload.send_email:
            from app.services.email_service import EmailService
            from app.models.business import Business
            
            business = db.query(Business).filter(Business.id == business_id).first()
            company_name = business.business_name if business else "Levitica Technologies"
            
            # Check if policies are attached
            has_policies = db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form.id).count() > 0
            
            email_service = EmailService()
            email_sent = await email_service.send_onboarding_form_email(
                candidate_email=form.candidate_email,
                candidate_name=form.candidate_name,
                form_id=form.id,
                form_token=form.form_token,
                candidate_mobile=form.candidate_mobile,
                has_policies=has_policies,
                has_offer_letter=bool(payload.include_offer_letter),
                company_name=company_name
            )
            if not email_sent:
                logger.warning(f"Failed to send onboarding email to {form.candidate_email}")
                
        return form
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/send", response_model=OnboardingResponseSchema)
async def send_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        db.commit()
        db.refresh(form)
        return form
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/submit", response_model=FormSubmissionResponse)
async def submit_onboarding_form(
    form_id: int = Path(...),
    submission_data: FormSubmissionCreate = None,
    db: Session = Depends(get_db)
):
    # Candidate-facing endpoint: public, does not require business validation
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        if form.expires_at and form.expires_at < datetime.now():
            form.status = OnboardingStatus.EXPIRED
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Onboarding form has expired")
        submission_payload = _build_form_submission_payload(submission_data)
        submission = FormSubmission(form_id=form_id, **submission_payload, submitted_at=datetime.now())
        db.add(submission)
        form.status = OnboardingStatus.SUBMITTED
        form.submitted_at = datetime.now()
        db.commit()
        db.refresh(submission)
        return _build_form_submission_response(submission_data, submission)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{form_id}/reviewform", response_model=dict, summary="Review submitted onboarding form")
async def review_onboarding_form(
    request: Request,
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get the full onboarding form details along with submitted candidate data for review.
    Returns form metadata, candidate info, and all submission fields grouped by step.
    """
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)

        # Get the latest submission for this form
        submission = (
            db.query(FormSubmission)
            .filter(FormSubmission.form_id == form_id)
            .order_by(FormSubmission.id.desc())
            .first()
        )

        # Build form overview
        form_overview = {
            "form_id": form.id,
            "form_token": form.form_token,
            "status": form.status.value,
            "candidate_name": form.candidate_name,
            "candidate_email": form.candidate_email,
            "candidate_mobile": form.candidate_mobile,
            "candidate_mobile_verified": bool(getattr(form, "candidate_mobile_verified", False)),
            "verify_mobile": form.verify_mobile,
            "verify_pan": form.verify_pan,
            "verify_bank": form.verify_bank,
            "verify_aadhaar": form.verify_aadhaar,
            "notes": form.notes,
            "created_at": form.created_at.isoformat() if form.created_at else None,
            "sent_at": form.sent_at.isoformat() if form.sent_at else None,
            "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
            "approved_at": form.approved_at.isoformat() if form.approved_at else None,
            "rejected_at": form.rejected_at.isoformat() if form.rejected_at else None,
            "expires_at": form.expires_at.isoformat() if form.expires_at else None,
            "rejection_reason": form.rejection_reason,
        }

        # Also fetch attached policies for this form
        from app.models.master_policy import FormPolicyMapping, MasterPolicy
        policy_mappings = (
            db.query(FormPolicyMapping)
            .filter(FormPolicyMapping.form_id == form_id)
            .all()
        )
        attached_policies = []
        for pm in policy_mappings:
            policy = db.query(MasterPolicy).filter(MasterPolicy.id == pm.policy_id).first()
            if policy:
                attached_policies.append({
                    "id": policy.id,
                    "name": policy.name,
                    "description": policy.description or "",
                    "type": policy.type or "other",
                    "is_mandatory": bool(policy.is_mandatory),
                })

        # Fetch offer letter if attached
        from app.models.onboarding import OfferLetter
        offer_letter = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()
        offer_letter_data = None
        if offer_letter:
            offer_letter_data = {
                "id": offer_letter.id,
                "position_title": offer_letter.position_title,
                "department": offer_letter.department,
                "location": offer_letter.location,
                "basic_salary": offer_letter.basic_salary,
                "gross_salary": offer_letter.gross_salary,
                "ctc": offer_letter.ctc,
                "joining_date": offer_letter.joining_date.isoformat() if offer_letter.joining_date else None,
                "offer_valid_until": offer_letter.offer_valid_until.isoformat() if offer_letter.offer_valid_until else None,
                "letter_content": offer_letter.letter_content,
                "is_generated": offer_letter.is_generated,
                "is_sent": offer_letter.is_sent
            }

        if not submission:
            return {
                "success": True,
                "form": form_overview,
                "has_submission": False,
                "submission": None,
                "attached_policies": attached_policies,
                "offer_letter": offer_letter_data,
            }

        # Parse JSON fields safely
        def _safe_json_parse(value):
            if not value:
                return None
            if isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        # Build structured submission data matching the flat structure of the submission model
        submission_data = {}
        if submission:
            for column in submission.__table__.columns:
                if column.name in ["present_address", "permanent_address", "mobile_verified"]:
                    continue
                val = getattr(submission, column.name)
                if isinstance(val, (datetime, date)):
                    submission_data[column.name] = val.isoformat()
                elif column.name in ["education_details", "experience_details", "uploaded_documents", "policy_acknowledgments"]:
                    submission_data[column.name] = _safe_json_parse(val)
                else:
                    submission_data[column.name] = val

        # If profile_image is null, look for uploaded photo on disk by form_token
        if not submission_data.get("profile_image"):
            safe_token = re.sub(r"[^A-Za-z0-9_.-]", "_", form.form_token).strip("._-")
            if PROFILE_PHOTO_DIR.exists():
                matching_photos = sorted(
                    PROFILE_PHOTO_DIR.glob(f"photo_{safe_token}_*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if matching_photos:
                    photo_path = str(matching_photos[0]).replace("\\", "/")
                    base_url = str(request.base_url)
                    if not base_url.endswith("/"):
                        base_url += "/"
                    relative_path = photo_path.lstrip("/")
                    submission_data["profile_image"] = f"{base_url}{relative_path}"

                    # Also save it to DB so next time it's found directly
                    submission.profile_image = submission_data["profile_image"]
                    db.commit()

        return {
            "success": True,
            "form": form_overview,
            "has_submission": True,
            "submission": submission_data,
            "attached_policies": attached_policies,
            "offer_letter": offer_letter_data,
        }
    except HTTPException:
        raise

def sync_onboarding_submission_to_employee(db: Session, employee, submission):
    if not submission:
        return

    # Sync candidate onboarding documents to EmployeeDocument
    try:
        from app.models.onboarding import OnboardingForm, CandidateDocument
        from app.models.employee import EmployeeDocument
        from urllib.parse import urlparse
        from datetime import datetime
        import os

        form = db.query(OnboardingForm).filter(OnboardingForm.id == submission.form_id).first()
        if form and form.form_token:
            candidate_docs = db.query(CandidateDocument).filter(
                CandidateDocument.business_id == employee.business_id,
                CandidateDocument.form_token == form.form_token
            ).all()

            if candidate_docs:
                existing_docs = db.query(EmployeeDocument).filter(
                    EmployeeDocument.employee_id == employee.id
                ).all()

                def normalize_path(p):
                    if not p:
                        return ""
                    return p.replace("\\", "/").strip("/")

                existing_paths = {normalize_path(d.file_path) for d in existing_docs if d.file_path}

                for doc in candidate_docs:
                    file_url = doc.file_path or ""
                    local_path = file_url
                    if file_url.startswith("http://") or file_url.startswith("https://"):
                        parsed = urlparse(file_url)
                        local_path = parsed.path.lstrip("/")

                    normalized_local = normalize_path(local_path)
                    if normalized_local in existing_paths:
                        continue

                    filename = os.path.basename(local_path) if local_path else "document"
                    new_doc = EmployeeDocument(
                        employee_id=employee.id,
                        document_type=doc.document_type or "general",
                        document_name=doc.document_name or "Onboarding Document",
                        file_path=local_path,
                        original_filename=filename,
                        file_size=0,
                        mime_type=None,
                        hidden=False,
                        created_at=datetime.now(),
                        uploaded_at=datetime.now()
                    )

                    try:
                        if os.path.exists(local_path):
                            new_doc.file_size = os.path.getsize(local_path)
                    except Exception as sz_err:
                        print(f"Warning: Could not get file size for {local_path}: {sz_err}")

                    db.add(new_doc)
    except Exception as doc_sync_err:
        print(f"Warning: Failed to sync onboarding documents during submission sync: {doc_sync_err}")
    
    # Update Employee fields from submission
    if submission.first_name:
        employee.first_name = submission.first_name
    if submission.last_name:
        employee.last_name = submission.last_name
    if submission.middle_name:
        employee.middle_name = submission.middle_name
    if submission.date_of_birth:
        employee.date_of_birth = submission.date_of_birth
    if submission.gender:
        g = submission.gender.lower()
        if g in ["male", "female", "other"]:
            employee.gender = g
    if submission.marital_status:
        m = submission.marital_status.lower()
        if m in ["single", "married", "divorced", "widowed"]:
            employee.marital_status = m
    if submission.blood_group:
        employee.blood_group = submission.blood_group
    if submission.nationality:
        employee.nationality = submission.nationality
    if submission.mobile:
        employee.mobile = submission.mobile
    if submission.alternate_mobile:
        employee.alternate_mobile = submission.alternate_mobile
    if submission.father_name:
        employee.father_name = submission.father_name
    if submission.mother_name:
        employee.mother_name = submission.mother_name
    if submission.aadhaar_number:
        employee.aadhar_number = submission.aadhaar_number
    if submission.passport_number:
        employee.passport_number = submission.passport_number
    if submission.driving_license_number:
        employee.driving_license = submission.driving_license_number
        
    if submission.emergency_contact_name:
        employee.emergency_contact = submission.emergency_contact_name
    if submission.emergency_contact_mobile:
        employee.emergency_phone = submission.emergency_contact_mobile
    elif submission.emergency_contact:
        employee.emergency_phone = submission.emergency_contact
        
    if submission.present_address:
        employee.current_address = submission.present_address
    elif submission.present_address_line1:
        addr_parts = [submission.present_address_line1, submission.present_address_line2, submission.present_city, submission.present_state, submission.present_country or "India", submission.present_pincode]
        employee.current_address = ", ".join([p for p in addr_parts if p])
        
    if submission.permanent_address:
        employee.permanent_address = submission.permanent_address
    elif submission.permanent_address_line1:
        addr_parts = [submission.permanent_address_line1, submission.permanent_address_line2, submission.permanent_city, submission.permanent_state, submission.permanent_country or "India", submission.permanent_pincode]
        employee.permanent_address = ", ".join([p for p in addr_parts if p])

    # Update EmployeeProfile fields
    from app.models.employee import EmployeeProfile
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee.id).first()
    if not profile:
        profile = EmployeeProfile(employee_id=employee.id)
        db.add(profile)
        
    if submission.present_address_line1:
        profile.present_address_line1 = submission.present_address_line1
    if submission.present_address_line2:
        profile.present_address_line2 = submission.present_address_line2
    if submission.present_city:
        profile.present_city = submission.present_city
    if submission.present_state:
        profile.present_state = submission.present_state
    if submission.present_country:
        profile.present_country = submission.present_country
    if submission.present_pincode:
        profile.present_pincode = submission.present_pincode
        
    if submission.permanent_address_line1:
        profile.permanent_address_line1 = submission.permanent_address_line1
    if submission.permanent_address_line2:
        profile.permanent_address_line2 = submission.permanent_address_line2
    if submission.permanent_city:
        profile.permanent_city = submission.permanent_city
    if submission.permanent_state:
        profile.permanent_state = submission.permanent_state
    if submission.permanent_country:
        profile.permanent_country = submission.permanent_country
    if submission.permanent_pincode:
        profile.permanent_pincode = submission.permanent_pincode
        
    if submission.pan_number:
        profile.pan_number = submission.pan_number
    if submission.aadhaar_number:
        profile.aadhaar_number = submission.aadhaar_number
    if submission.uan_number:
        profile.uan_number = submission.uan_number
    if submission.esi_number:
        profile.esi_number = submission.esi_number
        
    if submission.bank_name:
        profile.bank_name = submission.bank_name
    if submission.account_number:
        profile.bank_account_number = submission.account_number
    if submission.ifsc_code:
        profile.bank_ifsc_code = submission.ifsc_code
        
    if submission.emergency_contact_name:
        profile.emergency_contact_name = submission.emergency_contact_name
    if submission.emergency_contact_relationship:
        profile.emergency_contact_relationship = submission.emergency_contact_relationship
    if submission.emergency_contact_mobile:
        profile.emergency_contact_mobile = submission.emergency_contact_mobile
        
    if submission.profile_image:
        image_url = submission.profile_image
        if image_url.startswith('http'):
            from urllib.parse import urlparse
            parsed = urlparse(image_url)
            image_url = parsed.path
        profile.profile_image_url = image_url

    # Sync family members from onboarding submission to EmployeeRelative table
    try:
        from app.models.employee_relative import EmployeeRelative
        from sqlalchemy import or_

        existing_relatives = db.query(EmployeeRelative).filter(
            EmployeeRelative.employee_id == employee.id
        ).all()
        existing_relations = {r.relation.lower() for r in existing_relatives}

        family_entries = []
        if submission.father_name and submission.father_name.strip():
            family_entries.append({
                "relation": "Father",
                "name": submission.father_name.strip(),
                "phone": getattr(submission, "father_phone", None) or "",
                "dob": getattr(submission, "father_dob", None),
            })
        if submission.mother_name and submission.mother_name.strip():
            family_entries.append({
                "relation": "Mother",
                "name": submission.mother_name.strip(),
                "phone": getattr(submission, "mother_phone", None) or "",
                "dob": getattr(submission, "mother_dob", None),
            })

        for entry in family_entries:
            if entry["relation"].lower() not in existing_relations:
                new_relative = EmployeeRelative(
                    employee_id=employee.id,
                    relation=entry["relation"],
                    relative_name=entry["name"],
                    phone=entry["phone"] or None,
                    date_of_birth=entry["dob"],
                    dependent="No",
                    is_active=True,
                )
                db.add(new_relative)
                print(f"✅ Created EmployeeRelative: {entry['relation']} - {entry['name']} for employee {employee.id}")
    except Exception as rel_err:
        print(f"⚠️ Warning: Failed to sync family members to EmployeeRelative: {rel_err}")


@router.post("/{form_id}/approve", response_model=Dict[str, Any])
async def approve_onboarding_form(
    request: Request,
    business_id: int = Path(...),
    form_id: int = Path(...),
    approve_data: Optional[ApproveOnboardingRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    print("DEBUG RAW PAYLOAD: ", await request.body())
    print("DEBUG PARSED PAYLOAD: ", approve_data)
    validate_business_access(business_id, current_user, db)
    try:
        from app.models.employee import Employee
        form = validate_form_access(db, form_id, business_id, current_user)
        if form.status == OnboardingStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Form is already approved")

        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form_id).first()
        # Extract employee_data
        employee_data = {
            "first_name": submission.first_name if submission and submission.first_name else None,
            "email": form.candidate_email, 
            "mobile": form.candidate_mobile
        }
        
        # Fallback to parsing candidate_name from form if first_name wasn't in submission
        if not employee_data['first_name'] and form.candidate_name:
            employee_data['first_name'] = form.candidate_name.split()[0]
            
        if not employee_data['first_name']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: First name is missing from form data")
        if not employee_data['email']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: Email is missing from form data")

        existing_employee = db.query(Employee).filter(Employee.email == employee_data['email'], Employee.business_id == business_id).first()
        
        # Apply payload data if available
        if approve_data:
            employee_updates = {
                "date_of_joining": approve_data.joining_date,
                "date_of_confirmation": approve_data.confirmation_date,
                "business_unit_id": int(approve_data.business_unit) if approve_data.business_unit and str(approve_data.business_unit).isdigit() else None,
                "location_id": int(approve_data.location) if approve_data.location and str(approve_data.location).isdigit() else None,
                "cost_center_id": int(approve_data.cost_center) if approve_data.cost_center and str(approve_data.cost_center).isdigit() else None,
                "department_id": int(approve_data.department) if approve_data.department and str(approve_data.department).isdigit() else None,
                "designation_id": int(approve_data.designation) if approve_data.designation and str(approve_data.designation).isdigit() else None,
                "reporting_manager_id": int(approve_data.reporting_manager) if approve_data.reporting_manager and str(approve_data.reporting_manager).isdigit() else None,
                "shift_policy_id": int(approve_data.shift) if approve_data.shift and str(approve_data.shift).isdigit() else None,
                "grade_id": int(approve_data.grade) if approve_data.grade and str(approve_data.grade).isdigit() else None,
                "weekoff_policy_id": int(approve_data.week_off) if approve_data.week_off and str(approve_data.week_off).isdigit() else None,
                "employment_type": approve_data.employment_type,
                "work_mode": approve_data.work_mode,
            }
            # Remove None values so we don't overwrite with nulls unnecessarily
            employee_updates = {k: v for k, v in employee_updates.items() if v is not None}
        else:
            employee_updates = {}

        if existing_employee:
            for key, value in employee_updates.items():
                setattr(existing_employee, key, value)
            
            form.employee_id = existing_employee.id
            form.status = OnboardingStatus.APPROVED
            form.approved_by = current_user.id
            form.approved_at = datetime.now()
            
            # Sync submission details (photo + addresses etc.)
            sync_onboarding_submission_to_employee(db, existing_employee, submission)
            
            db.commit()
            db.refresh(form)
            
            return {
                "form_id": form.id,
                "employee_id": existing_employee.id,
                "joining_date": existing_employee.date_of_joining,
                "confirmation_date": existing_employee.date_of_confirmation,
                "business_unit": existing_employee.business_unit_id,
                "location": existing_employee.location_id,
                "cost_center": existing_employee.cost_center_id,
                "department": existing_employee.department_id,
                "designation": existing_employee.designation_id,
                "reporting_manager": existing_employee.reporting_manager_id,
                "shift": existing_employee.shift_policy_id,
                "grade": existing_employee.grade_id,
                "week_off": existing_employee.weekoff_policy_id,
                "employment_type": existing_employee.employment_type,
                "work_mode": existing_employee.work_mode,
                "status": form.status
            }

        # Create employee (scoped)
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        # Parse candidate name to ensure first_name and last_name are present
        candidate_name = form.candidate_name or ""
        name_parts = candidate_name.strip().split() if candidate_name else []
        first_name = employee_data.get('first_name') or (name_parts[0] if name_parts else 'Unknown')
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "NA"

        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=first_name,
            last_name=last_name,
            email=employee_data['email'],
            mobile=employee_data['mobile'],
            employee_status='active',
            date_of_joining=date.today(),
            created_by=current_user.id,
            is_active=True
        )
        for key, value in employee_updates.items():
            setattr(new_employee, key, value)
            
        db.add(new_employee)
        db.flush()
        
        # Sync submission details (photo + addresses etc.)
        sync_onboarding_submission_to_employee(db, new_employee, submission)
        
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        form.employee_id = new_employee.id
        db.commit()
        db.refresh(form)
        db.refresh(new_employee)
        
        return {
            "form_id": form.id,
            "employee_id": new_employee.id,
            "joining_date": new_employee.date_of_joining,
            "confirmation_date": new_employee.date_of_confirmation,
            "business_unit": new_employee.business_unit_id,
            "location": new_employee.location_id,
            "cost_center": new_employee.cost_center_id,
            "department": new_employee.department_id,
            "designation": new_employee.designation_id,
            "reporting_manager": new_employee.reporting_manager_id,
            "shift": new_employee.shift_policy_id,
            "grade": new_employee.grade_id,
            "week_off": new_employee.weekoff_policy_id,
            "employment_type": new_employee.employment_type,
            "work_mode": new_employee.work_mode,
            "status": form.status
        }
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig)
        detail = "Invalid data provided."
        if "foreign key constraint" in error_msg.lower():
            if "shift_policy" in error_msg:
                detail = "Invalid Shift selected. The selected shift does not exist."
            elif "department" in error_msg:
                detail = "Invalid Department selected."
            elif "designation" in error_msg:
                detail = "Invalid Designation selected."
            elif "location" in error_msg:
                detail = "Invalid Location selected."
            elif "cost_center" in error_msg:
                detail = "Invalid Cost Center selected."
            elif "grade" in error_msg:
                detail = "Invalid Grade selected."
            elif "weekoff_policy" in error_msg:
                detail = "Invalid Week-off Policy selected."
            elif "reporting_manager" in error_msg:
                detail = "Invalid Reporting Manager selected."
            else:
                detail = "One of the selected options is invalid and does not exist in the database."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/reject", response_model=OnboardingResponseSchema)
async def reject_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    rejection_data: OnboardingRejectionRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        reason = rejection_data.reason if rejection_data and getattr(rejection_data, 'reason', None) else "No reason provided"
        form.status = OnboardingStatus.REJECTED
        form.rejected_at = datetime.now()
        form.rejected_by = current_user.id
        form.rejection_reason = reason
        db.commit()
        db.refresh(form)
        return form
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Bulk onboarding
# ---------------------------------------------------------------------------
@router.post("/bulk", response_model=BulkOnboardingResponse)
async def create_bulk_onboarding(
    business_id: int = Path(...),
    bulk_data: BulkOnboardingCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        result = service.process_bulk_onboarding(bulk_data, business_id, current_user.id)
        return result['bulk_operation']
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------
@router.get("/credits", response_model=dict)
async def get_user_credits(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.credit_service import CreditService
        user_credits = CreditService.get_user_credits(db, current_user.id, business_id)
        return {"credits": user_credits.credits, "user_id": current_user.id, "business_id": business_id, "last_updated": user_credits.updated_at or user_credits.created_at}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/credits/purchase", response_model=dict)
async def purchase_credits(
    business_id: int = Path(...),
    purchase_request: CreditPurchaseRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.credit_service import CreditService
        return CreditService.purchase_credits(db, current_user.id, business_id, purchase_request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/credits/pricing", response_model=dict)
async def get_credit_pricing(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.credit_service import CreditService
        pricing = CreditService.get_credit_pricing(db, business_id)
        return {"pricing": pricing, "business_id": business_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Approvals listing and approve-frontend
# ---------------------------------------------------------------------------
@router.get("/approvals/pending", response_model=dict)
async def get_pending_approvals(
    business_id: int = Path(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        query = db.query(OnboardingForm).filter(OnboardingForm.status == OnboardingStatus.SUBMITTED, OnboardingForm.is_active == True, OnboardingForm.business_id == business_id)
        total_count = query.count()
        offset = (page - 1) * limit
        forms = query.order_by(desc(OnboardingForm.submitted_at)).offset(offset).limit(limit).all()
        pending_forms = []
        for form in forms:
            pending_forms.append({
                "id": form.id,
                "name": form.candidate_name,
                "joining": form.submitted_at.strftime("%d-%b-%Y") if form.submitted_at else None,
                "location": None,
                "deputation": None,
                "email": form.candidate_email,
                "mobile": form.candidate_mobile,
                "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
                "notes": form.notes
            })
        return {"success": True, "forms": pending_forms, "total": total_count, "page": page, "limit": limit, "pages": (total_count + limit - 1) // limit}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/approve-frontend", response_model=dict)
async def approve_form_frontend(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Reuse approve logic but return frontend-friendly response
        from app.models.employee import Employee
        form = validate_form_access(db, form_id, business_id, current_user)
        if form.status == OnboardingStatus.APPROVED:
            return {"success": True, "message": "Already approved", "form_id": form.id, "employee_id": form.employee_id}
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form_id).first()
        employee_data = {"first_name": submission.first_name if submission else None, "email": form.candidate_email}
        if not employee_data['first_name'] and form.candidate_name:
            employee_data['first_name'] = form.candidate_name.split()[0]
        if not employee_data['email']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: Email missing")
        existing_employee = db.query(Employee).filter(Employee.email == employee_data['email'], Employee.business_id == business_id).first()
        if existing_employee:
            form.employee_id = existing_employee.id
            form.status = OnboardingStatus.APPROVED
            form.approved_by = current_user.id
            form.approved_at = datetime.now()
            db.commit()
            
            if submission and submission.profile_image:
                from app.models.employee import EmployeeProfile
                emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == form.employee_id).first()
                image_url = submission.profile_image
                if image_url.startswith('http'):
                    from urllib.parse import urlparse
                    parsed = urlparse(image_url)
                    image_url = parsed.path
                if emp_profile:
                    emp_profile.profile_image_url = image_url
                else:
                    new_profile = EmployeeProfile(employee_id=form.employee_id, profile_image_url=image_url)
                    db.add(new_profile)
                db.commit()
                
            return {"success": True, "message": "Linked to existing employee", "employee_id": existing_employee.id}
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        # Ensure last_name is set to avoid DB NOT NULL violations
        candidate_name = form.candidate_name or ""
        name_parts = candidate_name.strip().split() if candidate_name else []
        first_name = employee_data.get('first_name') or (name_parts[0] if name_parts else 'Unknown')
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "NA"

        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=first_name,
            last_name=last_name,
            email=employee_data['email'],
            employee_status='ACTIVE',
            date_of_joining=date.today(),
            created_by=current_user.id,
            is_active=True
        )
        db.add(new_employee)
        try:
            db.flush()
        except IntegrityError as ie:
            db.rollback()
            # Try to find existing employee by email (global). If found and same business, link it.
            conflict_emp = db.query(Employee).filter(Employee.email == employee_data['email']).first()
            if conflict_emp:
                if conflict_emp.business_id == business_id:
                    form.employee_id = conflict_emp.id
                    form.status = OnboardingStatus.APPROVED
                    form.approved_by = current_user.id
                    form.approved_at = datetime.now()
                    db.commit()
                    
                    if submission and submission.profile_image:
                        from app.models.employee import EmployeeProfile
                        emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == form.employee_id).first()
                        image_url = submission.profile_image
                        if image_url.startswith('http'):
                            from urllib.parse import urlparse
                            parsed = urlparse(image_url)
                            image_url = parsed.path
                        if emp_profile:
                            emp_profile.profile_image_url = image_url
                        else:
                            new_profile = EmployeeProfile(employee_id=form.employee_id, profile_image_url=image_url)
                            db.add(new_profile)
                        db.commit()
                        
                    return {"success": True, "message": "Linked to existing employee (post-conflict)", "employee_id": conflict_emp.id}
                else:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: email already exists in another business")
            # If no conflicting employee found, re-raise original error
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ie))

        form.employee_id = new_employee.id
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        db.commit()
        db.refresh(new_employee)
        
        if submission and submission.profile_image:
            from app.models.employee import EmployeeProfile
            emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == form.employee_id).first()
            image_url = submission.profile_image
            if image_url.startswith('http'):
                from urllib.parse import urlparse
                parsed = urlparse(image_url)
                image_url = parsed.path
            if emp_profile:
                emp_profile.profile_image_url = image_url
            else:
                new_profile = EmployeeProfile(employee_id=form.employee_id, profile_image_url=image_url)
                db.add(new_profile)
            db.commit()
            
        return {"success": True, "message": "Form approved and employee created", "employee_id": new_employee.id, "employee_code": new_employee.employee_code}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Frontend-compatible endpoints and templates generation
# ---------------------------------------------------------------------------
@router.post("/templates/generate", response_model=TemplateGenerationResponse)
async def generate_letter_from_template(
    business_id: int = Path(...),
    generation_data: TemplateGenerationRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.name == generation_data.template_name, OfferLetterTemplate.business_id == business_id, OfferLetterTemplate.is_active == True).first()
        if not template:
            template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.name == generation_data.template_name, OfferLetterTemplate.is_active == True).first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{generation_data.template_name}' not found")
        # parse field values
        field_values = {}
        if generation_data.field_values and generation_data.field_values.strip():
            for line in generation_data.field_values.strip().split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    field_values[k.strip()] = v.strip()
        generated_content = template.template_content
        for k, v in field_values.items():
            generated_content = generated_content.replace(f"{{{k}}}", v)
        db.add(OfferLetter(form_id=None, template_id=template.id, letter_content=generated_content, is_generated=True, is_sent=False, business_id=business_id, created_by=current_user.id, created_at=datetime.now()))
        db.commit()
        return TemplateGenerationResponse(success=True, message="Letter generated successfully", offer_letter_id=None, generated_content=generated_content, template_name=generation_data.template_name, field_values=field_values)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Additional frontend helpers, OTP, candidate flows (kept as-is but scoped where needed)
# ---------------------------------------------------------------------------
@router.post("/candidate/otp/send")
async def send_otp_for_mobile_verification(otp_data: OTPSendRequest, db: Session = Depends(get_db)):
    try:
        return {"success": True, "message": "OTP sent successfully", "mobile_number": otp_data.mobile_number, "otp_sent": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/candidate/otp/verify")
async def verify_otp_for_mobile(verification_data: OTPVerifyRequest, db: Session = Depends(get_db)):
    try:
        is_valid = verification_data.otp_code == "123456"
        return {"success": is_valid, "message": "OTP verified" if is_valid else "Invalid OTP", "mobile_verified": is_valid}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Candidate public endpoints by token (no business validation)
@router.get("/candidate/form/{form_token}")
async def get_candidate_form_by_token(form_token: str, db: Session = Depends(get_db)):
    try:
        from app.models.business import Business
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found or token expired")
        business = db.query(Business).filter(Business.id == form.business_id).first()
        business_name = getattr(business, 'business_name', 'Company')
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        current_step = 1
        if submission:
            if submission.first_name:
                current_step = 2
        return {
            "form_id": form.id,
            "form_token": form.form_token,
            "candidate_name": form.candidate_name,
            "candidate_email": form.candidate_email,
            "candidate_mobile": form.candidate_mobile,
            "business_name": business_name,
            "business_id": form.business_id,
            "current_step": current_step,
            "total_steps": 11,
            "status": form.status.value,
            "has_submission": submission is not None,
            "candidate_mobile_verified": bool(getattr(form, "candidate_mobile_verified", False)),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/candidate/form/{form_token}/step/{step_number}")
async def submit_candidate_form_step(form_token: str, step_number: int, step_data: StepDataRequest, db: Session = Depends(get_db)):
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found or token expired")
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        if not submission:
            submission = FormSubmission(form_id=form.id, submitted_at=datetime.now())
            db.add(submission)
        # simplified: store step_data in JSON column if exists
        submission.step_data = step_data.data
        submission.step_number = step_number
        if step_number >= 9:
            form.status = OnboardingStatus.SUBMITTED
            form.submitted_at = datetime.now()
        db.commit()
        db.refresh(submission)
        return {"success": True, "message": f"Step {step_number} submitted successfully", "next_step": step_number + 1 if step_number < 11 else None, "is_complete": step_number >= 9}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Repair / Backfill: sync profile images from approved onboarding forms
# ---------------------------------------------------------------------------
@router.post("/repair/sync-profile-images", response_model=dict)
async def repair_sync_profile_images(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    One-time repair endpoint: For every APPROVED onboarding form that has a
    profile_image on its submission, ensure the linked EmployeeProfile row has
    the correct profile_image_url.  Call this once after updating the code to
    backfill existing employees (e.g. employee ID 6).
    """
    validate_business_access(business_id, current_user, db)
    try:
        from app.models.employee import EmployeeProfile
        from urllib.parse import urlparse

        # Fetch all approved forms for this business that have an employee linked
        approved_forms = (
            db.query(OnboardingForm)
            .filter(
                OnboardingForm.business_id == business_id,
                OnboardingForm.status == OnboardingStatus.APPROVED,
                OnboardingForm.employee_id.isnot(None),
            )
            .all()
        )

        synced = []
        skipped = []

        for form in approved_forms:
            submission = (
                db.query(FormSubmission)
                .filter(FormSubmission.form_id == form.id)
                .first()
            )

            if not submission or not submission.profile_image:
                skipped.append({"form_id": form.id, "reason": "no profile_image in submission"})
                continue

            # Normalise to a relative path so the URL rebuilds correctly via request
            image_url = submission.profile_image
            if image_url.startswith("http"):
                parsed = urlparse(image_url)
                image_url = parsed.path  # e.g. /uploads/profile_photos/...

            emp_profile = (
                db.query(EmployeeProfile)
                .filter(EmployeeProfile.employee_id == form.employee_id)
                .first()
            )

            if emp_profile:
                if emp_profile.profile_image_url == image_url:
                    skipped.append({"form_id": form.id, "employee_id": form.employee_id, "reason": "already up-to-date"})
                    continue
                emp_profile.profile_image_url = image_url
            else:
                new_profile = EmployeeProfile(
                    employee_id=form.employee_id,
                    profile_image_url=image_url
                )
                db.add(new_profile)

            synced.append({"form_id": form.id, "employee_id": form.employee_id, "image_path": image_url})

        db.commit()

        return {
            "success": True,
            "synced_count": len(synced),
            "skipped_count": len(skipped),
            "synced": synced,
            "skipped": skipped,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repair failed: {str(e)}"
        )


# ---------------------------------------------------------------------------
# End of file
# ---------------------------------------------------------------------------
