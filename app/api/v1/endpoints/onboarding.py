"""
Onboarding API Endpoints - Multi-tenant (business_id) refactor
- Router prefix updated to include `{business_id}`
- All protected endpoints require `business_id: int` path param
- Business isolation enforced via `validate_business_access` dependency/helper
- Removed owner-based .in_() filters and get_user_business_ids usage
- Kept existing schemas and response models intact
"""


from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
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
    OnboardingRejectionRequest, TemplateGenerationRequest, TemplateGenerationResponse
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
    "resume",
    "payslips",
)
DOCUMENT_BUCKET_ALIASES = {
    "adhar_card": "aadhaar_card",
    "aadhar_card": "aadhaar_card",
    "aadhaar_card": "aadhaar_card",
    "pan_card": "pan_card",
    "experience_letter": "experience_letter",
    "resume": "resume",
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
        "first_name",
        "middle_name",
        "last_name",
        "gender",
        "date_of_birth",
        "marital_status",
        "blood_group",
        "nationality",
        "personal_email",
        "alternate_mobile",
        "present_address",
        "permanent_address",
        "pan_number",
        "aadhaar_number",
        "bank_name",
        "account_number",
        "ifsc_code",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "emergency_contact_mobile",
        "education_details",
        "experience_details",
        "uploaded_documents",
        "policy_acknowledgments",
        "ip_address",
        "user_agent",
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
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Query,
    Path,
    Depends,
    status,
)
from sqlalchemy.orm import Session
from typing import List
import base64

# your imports
# from app.db.session import get_db
# from app.models.onboarding import OnboardingForm, CandidateDocument

router = APIRouter(tags=["Onboarding"])


@router.post("/documents")
async def upload_onboarding_documents(
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

            # response list
            uploaded_files.append(
                {
                    "file_name": stored_filename,
                    "file_path": stored_file_path_str,
                }
            )

            # DB record
            record = CandidateDocument(
                business_id=business_id,
                form_token=form_token,
                document_name=document_name,
                document_type=bucket,
                file_path=stored_file_path_str,
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
            "company_name": business.name if business else "Company",
            "company_address": getattr(business, 'address', '') if business else "",
            "offer_date": datetime.now().strftime("%d-%b-%Y"),
            "candidate_name": form.candidate_name or "",
            "candidate_email": form.candidate_email or "",
            "gross_salary": str(offer_data.gross_salary or 0)
        }

        if letter_content:
            letter_content = replace_template_variables(letter_content, template_variables)

        # Persist offer letter (scoped)
        existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id, OfferLetter.business_id == business_id).first()
        if existing_offer:
            existing_offer.template_id = offer_data.template_id
            existing_offer.letter_content = letter_content
            existing_offer.updated_at = datetime.now()
            offer_letter = existing_offer
        else:
            offer_letter = OfferLetter(
                form_id=form_id,
                template_id=offer_data.template_id,
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

        db.commit()
        db.refresh(offer_letter)

        return {
            "success": True,
            "offer_letter_id": offer_letter.id,
            "form_id": form_id,
            "salary_breakup": salary_breakup,
            "template_name": template.name if template else "Default",
            "generated_at": offer_letter.created_at.isoformat() if offer_letter.created_at else None
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

        # Remove existing onboarding policy records for this form (scoped)
        if table_has_column(db, 'onboarding_policies', 'business_id'):
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).delete()
        else:
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id).delete()

        # Remove existing form-policy mappings for this form
        if table_has_column(db, 'form_policy_mapping', 'business_id'):
            db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form_id, FormPolicyMapping.business_id == business_id).delete()
        else:
            db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form_id).delete()

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
            if table_has_column(db, 'onboarding_policies', 'business_id'):
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
        if table_has_column(db, 'onboarding_policies', 'business_id'):
            policies = db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).order_by(OnboardingPolicy.display_order).all()
        else:
            policies = db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id).order_by(OnboardingPolicy.display_order).all()
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


@router.post("/{form_id}/approve", response_model=OnboardingResponseSchema)
async def approve_onboarding_form(
    business_id: int = Path(...),
    form_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Keep approval workflow intact but ensure business scoping for employees creation
        from app.models.employee import Employee
        form = validate_form_access(db, form_id, business_id, current_user)
        if form.status == OnboardingStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Form is already approved")

        submissions = db.query(FormSubmission).filter(FormSubmission.form_id == form_id).all()
        # Extract employee_data (existing logic preserved)
        employee_data = {"first_name": None, "email": form.candidate_email, "mobile": form.candidate_mobile}
        for submission in submissions:
            step_data = submission.step_data or {}
            if submission.step_number == 2:
                employee_data['first_name'] = step_data.get('first_name')
        if not employee_data['first_name']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: First name is missing from form data")
        if not employee_data['email']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create employee: Email is missing from form data")

        existing_employee = db.query(Employee).filter(Employee.email == employee_data['email'], Employee.business_id == business_id).first()
        if existing_employee:
            form.employee_id = existing_employee.id
            form.status = OnboardingStatus.APPROVED
            form.approved_by = current_user.id
            form.approved_at = datetime.now()
            db.commit()
            db.refresh(form)
            return form

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
            employee_status='ACTIVE',
            date_of_joining=date.today(),
            created_by=current_user.id,
            is_active=True
        )
        db.add(new_employee)
        db.flush()
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        form.employee_id = new_employee.id
        db.commit()
        db.refresh(form)
        db.refresh(new_employee)
        return form
    except HTTPException:
        raise
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
# End of file
# ---------------------------------------------------------------------------
