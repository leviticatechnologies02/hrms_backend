"""
Cleaned Onboarding API router — single implementation, router prefix set to /{business_id}/onboarding
All endpoint paths are relative to the router prefix and keep `business_id: int = Path(...)` in function signatures.
This file preserves existing onboarding logic while removing duplicated route definitions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timedelta, date
import json
import logging

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, validate_business_access
from app.models.user import User
from app.models.onboarding import (
    OnboardingForm, OfferLetter, OfferLetterTemplate, OnboardingStatus, OnboardingSettings,
    BulkOnboarding, FormSubmission, OnboardingPolicy
)
from app.schemas.onboarding import (
    OnboardingFormResponse, OnboardingFormCreate, OnboardingFormUpdate,
    OfferLetterCreate, OfferLetterResponse,
    OfferLetterTemplateCreate, OfferLetterTemplateResponse,
    OnboardingDashboardResponse, PaginatedOnboardingResponse,
    OnboardingSettingsUpdate, OnboardingSettingsResponse,
    BulkOnboardingCreate, BulkOnboardingResponse,
    FormSubmissionCreate, FormSubmissionResponse,
    OnboardingRejectionRequest, TemplateGenerationRequest, TemplateGenerationResponse,
    DebugEnvironmentResponse
)
from app.schemas.onboarding_additional import (
    SalaryCalculationRequest, OfferLetterGenerateRequest, PolicyAttachmentRequest,
    DocumentRequirementUpdateRequest, FieldRequirementUpdateRequest,
    BulkSendRequest, SendFormRequest, StepDataRequest,
    OTPSendRequest, OTPVerifyRequest, DocumentUploadRequest,
    FormCreateRequest, FinalizeAndSendRequest
)
from app.schemas.credits import CreditPurchaseRequest
from app.services.onboarding_service import OnboardingService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/{business_id}/onboarding",
    tags=["Onboarding"]
)


# Helpers

def table_has_column(db: Session, table_name: str, column_name: str) -> bool:
    try:
        engine = db.get_bind()
        inspector = sa_inspect(engine)
        cols = inspector.get_columns(table_name)
        return any(c.get('name') == column_name for c in cols)
    except Exception:
        return False


def replace_template_variables(template_content: str, data: dict) -> str:
    result = template_content
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value) if value is not None else "")
    return result


def validate_form_access(db: Session, form_id: int, business_id: int, current_user: User):
    form = db.query(OnboardingForm).filter(
        OnboardingForm.id == form_id,
        OnboardingForm.business_id == business_id
    ).first()
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
    return form


# Dashboard
@router.get("/dashboard", response_model=OnboardingDashboardResponse)
async def get_onboarding_dashboard(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        return service.get_dashboard_data(business_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Salary calculation
@router.post("/{form_id}/calculate-salary", response_model=dict)
async def calculate_salary_for_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    calculation_data: SalaryCalculationRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        from app.services.salary_calculation_service import SalaryCalculationService
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
    business_id: int = Path(..., description="Business ID"),
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
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        employee_profile = {
            "candidate_name": form.candidate_name,
            "candidate_email": form.candidate_email,
            "candidate_mobile": form.candidate_mobile,
            "offer_letter": None,
            "salary_options": None,
            "policies": None
        }

        if form.offer_letters and len(form.offer_letters) > 0:
            offer = form.offer_letters[0]
            nested_offer = {
                "designation": getattr(offer, 'position_title', None),
                "department": getattr(offer, 'department', None),
                "joining_date": offer.joining_date.isoformat() if getattr(offer, 'joining_date', None) else None,
                "work_location": getattr(offer, 'location', None)
            }
            employee_profile["offer_letter"] = nested_offer

        if form.employee_id:
            from app.models.employee import Employee
            employee = db.query(Employee).filter(Employee.id == form.employee_id, Employee.business_id == business_id).first()
            if employee:
                employee_profile.update({
                    "employee_id": employee.id,
                    "location": getattr(employee, 'location_id', None),
                    "department": getattr(employee, 'department_id', None),
                    "designation": getattr(employee, 'designation_id', None),
                    "grade": getattr(employee, 'grade_id', None)
                })

        from app.models.location import Location
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.grades import Grade
        from app.models.cost_center import CostCenter
        from app.models.work_shifts import WorkShift

        locations = db.query(Location).filter(Location.business_id == business_id, Location.is_active == True).all()
        departments = db.query(Department).filter(Department.business_id == business_id, Department.is_active == True).all()
        designations = db.query(Designation).filter(Designation.business_id == business_id).all()
        grades = db.query(Grade).filter(Grade.business_id == business_id).all()
        cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business_id, CostCenter.is_active == True).all()
        work_shifts = db.query(WorkShift).filter(WorkShift.business_id == business_id).all()

        return {
            "success": True,
            "employee_profile": employee_profile,
            "dropdown_options": {
                "locations": [{"id": l.id, "name": l.name} for l in locations],
                "departments": [{"id": d.id, "name": d.name} for d in departments],
                "designations": [{"id": d.id, "name": d.name} for d in designations],
                "grades": [{"id": g.id, "name": g.name} for g in grades]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Offer letter generation
@router.post("/{form_id}/generate-offer-letter", response_model=dict)
async def generate_complete_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    offer_data: OfferLetterGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        template = None
        if offer_data and offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.id == offer_data.template_id, OfferLetterTemplate.business_id == business_id, OfferLetterTemplate.is_active == True).first()

        salary_breakup = None
        if offer_data and offer_data.gross_salary:
            from app.services.salary_calculation_service import SalaryCalculationService
            calc_service = SalaryCalculationService(db)
            salary_breakup = calc_service.calculate_salary_breakup(
                gross_salary=offer_data.gross_salary,
                salary_structure_id=offer_data.salary_structure_id,
                employee_id=form.employee_id,
                business_id=business_id,
                options=offer_data.salary_options
            )

        letter_content = template.template_content if template else ""
        if letter_content:
            letter_content = replace_template_variables(letter_content, {"company_name": (db.query(User).filter(User.id == current_user.id).first().name if current_user else "Company")})

        if table_has_column(db, 'offer_letters', 'business_id'):
            existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id, OfferLetter.business_id == business_id).first()
        else:
            existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()

        if existing_offer:
            existing_offer.template_id = offer_data.template_id if offer_data else existing_offer.template_id
            existing_offer.letter_content = letter_content
            existing_offer.updated_at = datetime.now()
            offer_letter = existing_offer
        else:
            offer_letter = OfferLetter(form_id=form_id, template_id=(offer_data.template_id if offer_data else None), letter_content=letter_content, is_generated=True, is_sent=False, business_id=business_id, created_by=current_user.id, created_at=datetime.now())
            db.add(offer_letter)

        db.commit()
        db.refresh(offer_letter)

        return {"success": True, "offer_letter_id": offer_letter.id, "form_id": form_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Offer letter templates
@router.get("/templates", response_model=List[OfferLetterTemplateResponse])
async def get_offer_letter_templates(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        templates = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.business_id == business_id, OfferLetterTemplate.is_active == True).order_by(OfferLetterTemplate.name).all()
        return templates
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/templates", response_model=OfferLetterTemplateResponse)
async def create_offer_letter_template(
    business_id: int = Path(..., description="Business ID"),
    template_data: OfferLetterTemplateCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        template = OfferLetterTemplate(business_id=business_id, name=template_data.name, description=template_data.description, template_content=template_data.template_content, available_variables=template_data.available_variables, is_active=template_data.is_active, is_default=template_data.is_default, created_by=current_user.id, created_at=datetime.now())
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Offer letters list & create
@router.post("/offer-letters", response_model=OfferLetterResponse)
async def generate_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    offer_data: OfferLetterCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        template = None
        if offer_data and offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.id == offer_data.template_id, OfferLetterTemplate.business_id == business_id, OfferLetterTemplate.is_active == True).first()
        offer_letter = OfferLetter(form_id=None, template_id=(offer_data.template_id if offer_data else None), position_title=(offer_data.position_title if offer_data else None), department=(offer_data.department if offer_data else None), location=(offer_data.location if offer_data else None), basic_salary=(offer_data.basic_salary if offer_data else None), gross_salary=(offer_data.gross_salary if offer_data else None), ctc=(offer_data.ctc if offer_data else None), joining_date=(offer_data.joining_date if offer_data else None), offer_valid_until=(offer_data.offer_valid_until if offer_data else None), letter_content=(offer_data.letter_content or (template.template_content if template else "")), is_generated=True, is_sent=False, business_id=business_id, created_by=current_user.id, created_at=datetime.now())
        db.add(offer_letter)
        db.commit()
        db.refresh(offer_letter)
        return offer_letter
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/offer-letters", response_model=List[OfferLetterResponse])
async def get_offer_letters(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        offer_letters = db.query(OfferLetter).filter(OfferLetter.business_id == business_id).order_by(desc(OfferLetter.created_at)).all()
        return offer_letters
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Policy templates
@router.get("/policy-templates", response_model=List[dict])
async def get_policy_templates(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        return [
            {"id": 1, "name": "Employee Handbook", "description": "Complete guide", "type": "handbook", "is_mandatory": True},
            {"id": 2, "name": "Code of Conduct", "description": "Ethics", "type": "conduct", "is_mandatory": True}
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/attach-policies", response_model=dict)
async def attach_policies_to_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    policy_data: PolicyAttachmentRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        selected_policy_ids = policy_data.policy_ids or []
        if table_has_column(db, 'onboarding_policies', 'business_id'):
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).delete()
        else:
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id).delete()
        for i, pid in enumerate(selected_policy_ids):
            policy_kwargs = dict(form_id=form_id, policy_name=f"Policy {pid}", policy_content=f"Policy content for {pid}", policy_file_path=f"/policies/{pid}.pdf", requires_acknowledgment=True, is_mandatory=True, display_order=i, created_by=current_user.id)
            if table_has_column(db, 'onboarding_policies', 'business_id'):
                policy_kwargs['business_id'] = business_id
            p = OnboardingPolicy(**policy_kwargs)
            db.add(p)
        db.commit()
        return {"success": True, "attached_policies": len(selected_policy_ids), "form_id": form_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{form_id}/policies", response_model=List[dict])
async def get_form_policies(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
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
        return [{"id": p.id, "policy_name": p.policy_name, "policy_content": p.policy_content, "policy_file_path": p.policy_file_path, "requires_acknowledgment": p.requires_acknowledgment, "is_mandatory": p.is_mandatory, "display_order": p.display_order, "created_at": p.created_at.isoformat() if p.created_at else None} for p in policies]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Settings
@router.get("/settings", response_model=OnboardingSettingsResponse, operation_id="get_onboarding_settings_v1")
async def get_onboarding_settings(
    business_id: int = Path(..., description="Business ID"),
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
    business_id: int = Path(..., description="Business ID"),
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


# Forms list/create/get/update/delete
@router.get("/", response_model=PaginatedOnboardingResponse)
async def list_onboarding_forms(
    business_id: int = Path(..., description="Business ID"),
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
            query = query.filter((OnboardingForm.candidate_name.ilike(term)) | (OnboardingForm.candidate_email.ilike(term)) | (OnboardingForm.candidate_mobile.ilike(term)))
        total = query.count()
        offset = (page - 1) * limit
        forms = query.offset(offset).limit(limit).all()
        return {"items": forms, "total": total, "page": page, "size": limit, "pages": (total + limit - 1) // limit}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/", response_model=OnboardingFormResponse)
async def create_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_data: OnboardingFormCreate = None,
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


@router.get("/forms/{form_id}", response_model=OnboardingFormResponse)
async def get_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
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


@router.put("/{form_id}", response_model=OnboardingFormResponse)
async def update_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    form_data: OnboardingFormUpdate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        form = validate_form_access(db, form_id, business_id, current_user)
        update_data = form_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(form, field):
                setattr(form, field, value)
        form.updated_at = datetime.now()
        db.commit()
        db.refresh(form)
        return form
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{form_id}")
async def delete_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
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


# Send / Submit / Approve / Reject
@router.post("/{form_id}/send", response_model=OnboardingFormResponse)
async def send_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
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
    form_id: int = Path(..., description="Form ID"),
    submission_data: FormSubmissionCreate = None,
    db: Session = Depends(get_db)
):
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        if form.expires_at and form.expires_at < datetime.now():
            form.status = OnboardingStatus.EXPIRED
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Onboarding form has expired")
        submission = FormSubmission(form_id=form_id, **submission_data.dict(), submitted_at=datetime.now())
        db.add(submission)
        form.status = OnboardingStatus.SUBMITTED
        form.submitted_at = datetime.now()
        db.commit()
        db.refresh(submission)
        return submission
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/approve", response_model=OnboardingFormResponse)
async def approve_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.models.employee import Employee
        form = validate_form_access(db, form_id, business_id, current_user)
        if form.status == OnboardingStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Form is already approved")
        submissions = db.query(FormSubmission).filter(FormSubmission.form_id == form_id).all()
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
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        candidate_name = form.candidate_name or ""
        name_parts = candidate_name.strip().split() if candidate_name else []
        first_name = employee_data.get('first_name') or (name_parts[0] if name_parts else 'Unknown')
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "NA"
        new_employee = Employee(business_id=business_id, employee_code=employee_code, first_name=first_name, last_name=last_name, email=employee_data['email'], mobile=employee_data['mobile'], employee_status='ACTIVE', date_of_joining=date.today(), created_by=current_user.id, is_active=True)
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


@router.post("/{form_id}/reject", response_model=OnboardingFormResponse)
async def reject_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
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


# Bulk, credits, approvals and diagnostics etc. (kept concise)
@router.post("/bulk", response_model=BulkOnboardingResponse)
async def create_bulk_onboarding(
    business_id: int = Path(..., description="Business ID"),
    bulk_data: BulkOnboardingCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        service = OnboardingService(db)
        result = service.process_bulk_onboarding(bulk_data, business_id, current_user.id)
        return result.get('bulk_operation')
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/credits", response_model=dict)
async def get_user_credits(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        from app.services.credit_service import CreditService
        user_credits = CreditService.get_user_credits(db, current_user.id, business_id)
        return {"credits": user_credits.credits, "user_id": current_user.id, "business_id": business_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/approvals/pending", response_model=dict)
async def get_pending_approvals(
    business_id: int = Path(..., description="Business ID"),
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
            pending_forms.append({"id": form.id, "name": form.candidate_name, "joining": form.submitted_at.isoformat() if form.submitted_at else None, "email": form.candidate_email, "mobile": form.candidate_mobile})
        return {"success": True, "forms": pending_forms, "total": total_count, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/debug/environment", response_model=DebugEnvironmentResponse)
async def check_server_environment(
    business_id: int = Path(..., description="Business id to scope the request"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    validate_business_access(business_id, current_user, db)
    import platform
    from app.core.config import settings
    now = datetime.utcnow()
    environment = "development" if getattr(settings, 'DEBUG', False) else "production"
    return {"success": True, "business_id": business_id, "environment": environment, "python_version": platform.python_version(), "timestamp": now}


# End of file
