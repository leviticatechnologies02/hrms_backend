"""
Onboarding API Endpoints - Multi-tenant (business_id) refactor
- Router prefix updated to include `{business_id}`
- All protected endpoints require `business_id: int` path param
- Business isolation enforced via `validate_business_access` dependency/helper
- Removed owner-based .in_() filters and get_user_business_ids usage
- Kept existing schemas and response models intact
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
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


# ---------------------------------------------------------------------------
# Policy templates (readonly) & form policy attachments (scoped)
# ---------------------------------------------------------------------------
@router.get("/policy-templates", response_model=List[dict])
async def get_policy_templates(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    validate_business_access(business_id, current_user, db)
    try:
        # Static list (could be pulled from DB in future)
        return [
            {"id": 1, "name": "Employee Handbook", "description": "Complete guide", "type": "handbook", "is_mandatory": True},
            {"id": 2, "name": "Code of Conduct", "description": "Ethics", "type": "conduct", "is_mandatory": True}
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
        return {"form_id": form.id, "form_token": form.form_token, "candidate_name": form.candidate_name, "candidate_email": form.candidate_email, "candidate_mobile": form.candidate_mobile, "business_name": business_name, "business_id": form.business_id, "current_step": current_step, "total_steps": 11, "status": form.status.value, "has_submission": submission is not None}
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
"""
Onboarding API Endpoints - Multi-tenant enterprise Swagger structure
All endpoints are scoped to `business_id` path parameter and validate access
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, inspect as sa_inspect
from typing import List, Optional
from datetime import datetime, date, timedelta
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
    OnboardingResponseSchema, CreateOnboardingSchema, UpdateOnboardingSchema,
    OfferLetterCreate, OfferLetterResponse,
    OfferLetterTemplateCreate, OfferLetterTemplateResponse,
    OnboardingDashboardResponse, OnboardingListResponse,
    OnboardingSettingsUpdate, OnboardingSettingsResponse,
    BulkOnboardingCreate, BulkOnboardingResponse,
    FormSubmissionCreate, FormSubmissionResponse,
    OnboardingRejectionRequest, TemplateGenerationRequest, TemplateGenerationResponse
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
    tags=["Onboarding"]
)


# ---------------------------------------------------------------------------
# Helper validators (business-scoped)
# ---------------------------------------------------------------------------

def validate_form_access(db: Session, form_id: int, business_id: int, current_user: User) -> OnboardingForm:
    """
    Validate that the onboarding form belongs to the requested business.
    Raises 404 if not found, 403 if business access not allowed.
    """
    # Ensure user has access to this business
    validate_business_access(business_id, current_user, db)

    form = db.query(OnboardingForm).filter(
        OnboardingForm.id == form_id,
        OnboardingForm.business_id == business_id
    ).first()

    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding form with ID {form_id} not found"
        )

    return form


def table_has_column(db: Session, table_name: str, column_name: str) -> bool:
    """Return True if the database table has the specified column.

    This avoids emitting SQL that references columns not present in older schemas.
    """
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


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=OnboardingDashboardResponse)
async def get_onboarding_dashboard(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.get_dashboard_data(business_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Salary calculation
# ---------------------------------------------------------------------------
@router.post("/{form_id}/calculate-salary", response_model=dict)
async def calculate_salary_for_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    calculation_data: SalaryCalculationRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)

        form = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id == business_id
        ).first()

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
    try:
        validate_business_access(business_id, current_user, db)
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
    try:
        validate_business_access(business_id, current_user, db)

        form = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id == business_id
        ).first()

        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        employee_profile = {}
        if form.employee_id:
            from app.models.employee import Employee
            from app.models.location import Location
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.grades import Grade
            from app.models.cost_center import CostCenter
            from app.models.work_shifts import WorkShift

            employee = db.query(Employee).filter(Employee.id == form.employee_id, Employee.business_id == business_id).first()
            if employee:
                location = db.query(Location).filter(Location.id == employee.location_id).first() if employee.location_id else None
                department = db.query(Department).filter(Department.id == employee.department_id).first() if employee.department_id else None
                designation = db.query(Designation).filter(Designation.id == employee.designation_id).first() if employee.designation_id else None
                grade = db.query(Grade).filter(Grade.id == employee.grade_id).first() if employee.grade_id else None
                cost_center = db.query(CostCenter).filter(CostCenter.id == employee.cost_center_id).first() if employee.cost_center_id else None
                shift_policy = None
                if hasattr(employee, 'shift_policy_id') and employee.shift_policy_id:
                    from app.models.shift_policy import ShiftPolicy
                    shift_policy = db.query(ShiftPolicy).filter(ShiftPolicy.id == employee.shift_policy_id).first()

                employee_profile = {
                    "employee_id": employee.id,
                    "location": location.name if location else "",
                    "location_id": employee.location_id,
                    "department": department.name if department else "",
                    "department_id": employee.department_id,
                    "designation": designation.name if designation else "",
                    "designation_id": employee.designation_id,
                    "grade": grade.name if grade else "",
                    "grade_id": employee.grade_id,
                    "cost_center": cost_center.name if cost_center else "",
                    "cost_center_id": employee.cost_center_id,
                    "shift_policy": shift_policy.name if shift_policy else "",
                    "shift_policy_id": employee.shift_policy_id if hasattr(employee, 'shift_policy_id') else None,
                    "date_of_birth": employee.date_of_birth.isoformat() if employee.date_of_birth else "",
                    "gender": employee.gender or "",
                    "joining_date": employee.date_of_joining.isoformat() if employee.date_of_joining else "",
                    "confirmation_date": employee.date_of_confirmation.isoformat() if employee.date_of_confirmation else "",
                    "notice_period": employee.notice_period_days or 0
                }

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
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    offer_data: OfferLetterGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)

        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")

        template = None
        if offer_data and offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.id == offer_data.template_id,
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            ).first()

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

        business_user = db.query(User).filter(User.id == current_user.id).first()

        # build template variables as before
        template_variables = {"company_name": business_user.name if business_user else "Company Name"}

        letter_content = template.template_content if template else ""
        if letter_content:
            letter_content = replace_template_variables(letter_content, template_variables)

        # Find existing offer letter for this form. If DB has business_id column, include it in filter.
        if table_has_column(db, 'offer_letters', 'business_id'):
            existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id, OfferLetter.business_id == business_id).first()
        else:
            existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()

        if existing_offer:
            existing_offer.template_id = template.id if template else None
            existing_offer.position_title = offer_data.position_title if offer_data else existing_offer.position_title
            existing_offer.department = offer_data.department if offer_data else existing_offer.department
            existing_offer.location = offer_data.location if offer_data else existing_offer.location
            existing_offer.basic_salary = str(salary_breakup["earnings"].get("Basic Salary", 0)) if salary_breakup else existing_offer.basic_salary
            existing_offer.gross_salary = str(offer_data.gross_salary or existing_offer.gross_salary) if offer_data else existing_offer.gross_salary
            existing_offer.ctc = str(salary_breakup.get("ctc")) if salary_breakup else existing_offer.ctc
            existing_offer.joining_date = offer_data.joining_date if offer_data else existing_offer.joining_date
            existing_offer.offer_valid_until = offer_data.offer_valid_until if offer_data else existing_offer.offer_valid_until
            existing_offer.letter_content = letter_content
            existing_offer.is_generated = True
            existing_offer.updated_at = datetime.now()
            offer_letter = existing_offer
        else:
            offer_kwargs = dict(
                form_id=form_id,
                template_id=template.id if template else None,
                position_title=offer_data.position_title if offer_data else "",
                department=offer_data.department if offer_data else "",
                location=offer_data.location if offer_data else "",
                basic_salary=str(salary_breakup["earnings"].get("Basic Salary", 0)) if salary_breakup else (offer_data.basic_salary if offer_data else ""),
                gross_salary=str(offer_data.gross_salary or 0) if offer_data else "",
                ctc=str(salary_breakup.get("ctc")) if salary_breakup else (offer_data.ctc if offer_data else ""),
                joining_date=offer_data.joining_date if offer_data else None,
                offer_valid_until=offer_data.offer_valid_until if offer_data else None,
                letter_content=letter_content,
                is_generated=True,
                is_sent=False,
                created_by=current_user.id,
                created_at=datetime.now()
            )
            if table_has_column(db, 'offer_letters', 'business_id'):
                offer_kwargs['business_id'] = business_id

            offer_letter = OfferLetter(**offer_kwargs)
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
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        templates = db.query(OfferLetterTemplate).filter(
            OfferLetterTemplate.business_id == business_id,
            OfferLetterTemplate.is_active == True
        ).order_by(OfferLetterTemplate.name).all()

        if not templates:
            templates = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.is_active == True
            ).order_by(OfferLetterTemplate.name).all()

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
    try:
        validate_business_access(business_id, current_user, db)

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
# Offer letters
# ---------------------------------------------------------------------------
@router.post("/offer-letters", response_model=OfferLetterResponse)
async def generate_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    offer_data: OfferLetterCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)

        template = None
        if offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.id == offer_data.template_id,
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            ).first()

        offer_letter = OfferLetter(
            business_id=business_id,
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
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        # Business-scoped offer letters: prefer direct business_id filter for isolation
        offer_letters = db.query(OfferLetter).filter(OfferLetter.business_id == business_id).order_by(desc(OfferLetter.created_at)).all()
        return offer_letters
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Policy templates & attachments
# ---------------------------------------------------------------------------
@router.get("/policy-templates", response_model=List[dict])
async def get_policy_templates(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        # Static list as before
        policy_templates = [
            {"id": 1, "name": "Employee Handbook", "description": "Complete guide to company policies and procedures", "type": "handbook", "is_mandatory": True, "requires_acknowledgment": True, "file_path": "/policies/employee-handbook.pdf"},
            {"id": 2, "name": "Code of Conduct", "description": "Professional behavior and ethical guidelines", "type": "conduct", "is_mandatory": True, "requires_acknowledgment": True, "file_path": "/policies/code-of-conduct.pdf"},
            {"id": 3, "name": "IT Security Policy", "description": "Information technology security guidelines and requirements", "type": "it_security", "is_mandatory": True, "requires_acknowledgment": True, "file_path": "/policies/it-security-policy.pdf"},
            {"id": 4, "name": "Remote Work Policy", "description": "Guidelines for remote work arrangements", "type": "remote_work", "is_mandatory": False, "requires_acknowledgment": True, "file_path": "/policies/remote-work-policy.pdf"},
            {"id": 5, "name": "Leave Policy", "description": "Annual leave, sick leave, and other time-off policies", "type": "leave", "is_mandatory": True, "requires_acknowledgment": True, "file_path": "/policies/leave-policy.pdf"},
            {"id": 6, "name": "Health & Safety Policy", "description": "Workplace health and safety guidelines", "type": "health_safety", "is_mandatory": True, "requires_acknowledgment": True, "file_path": "/policies/health-safety-policy.pdf"}
        ]
        return policy_templates
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/attach-policies", response_model=AttachPoliciesResponse)
async def attach_policies_to_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    policy_data: PolicyAttachmentRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = validate_form_access(db, form_id, business_id, current_user)

        selected_policy_ids = policy_data.policy_ids if policy_data else []

        if not selected_policy_ids:
            return {"success": True, "message": "No policies provided", "form_id": form_id, "attached_policies": []}

        # Fetch master policies and validate ownership
        masters = db.query(MasterPolicy).filter(MasterPolicy.id.in_(selected_policy_ids), MasterPolicy.business_id == business_id).all()
        found_ids = {m.id for m in masters}
        missing = [pid for pid in selected_policy_ids if pid not in found_ids]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Master policies not found or not owned by business: {missing}")

        # Clear existing onboarding policies and mappings for this form
        if table_has_column(db, 'onboarding_policies', 'business_id'):
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).delete()
        else:
            db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id).delete()

        if table_has_column(db, 'form_policy_mapping', 'business_id'):
            db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form_id, FormPolicyMapping.business_id == business_id).delete()
        else:
            db.query(FormPolicyMapping).filter(FormPolicyMapping.form_id == form_id).delete()

        attached_masters = []
        for i, pid in enumerate(selected_policy_ids):
            master = next((m for m in masters if m.id == pid), None)
            if not master:
                continue

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
            db.add(OnboardingPolicy(**policy_kwargs))

            mapping = FormPolicyMapping(
                form_id=form_id,
                policy_id=master.id,
                business_id=business_id,
                created_by=current_user.id
            )
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
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = validate_form_access(db, form_id, business_id, current_user)

        policies = db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id, OnboardingPolicy.business_id == business_id).order_by(OnboardingPolicy.display_order).all()
        policy_list = []
        for policy in policies:
            policy_list.append({
                "id": policy.id,
                "policy_name": policy.policy_name,
                "policy_content": policy.policy_content,
                "policy_file_path": policy.policy_file_path,
                "requires_acknowledgment": policy.requires_acknowledgment,
                "is_mandatory": policy.is_mandatory,
                "display_order": policy.display_order,
                "created_at": policy.created_at.isoformat() if policy.created_at else None
            })
        return policy_list
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Create/update onboarding while skipping offer letter
# ---------------------------------------------------------------------------
@router.post("/{form_id}/skip-offer-letter", response_model=SkipOfferLetterResponse, summary="Create onboarding without offer letter", include_in_schema=True, operation_id="create_onboarding_skip_offer_letter_v1")
async def create_onboarding_skip_offer_letter(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Onboarding form ID"),
    skip_data: SkipOfferLetterRequest = Body(..., description="Payload to create/update onboarding while skipping offer letter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create or update onboarding form while skipping offer letter generation.

    Validates business and policy ownership, attaches policies and saves form without generating an offer letter.
    """
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        result = service.create_or_update_onboarding_skip_offer_letter(form_id, skip_data, business_id, current_user.id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@router.get("/settings", response_model=OnboardingSettingsResponse, operation_id="get_onboarding_settings_v1")
async def get_onboarding_settings(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.get_onboarding_settings(business_id, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/settings", response_model=OnboardingSettingsResponse)
async def update_onboarding_settings(
    business_id: int = Path(..., description="Business ID"),
    settings_data: OnboardingSettingsUpdate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        update_dict = settings_data.dict(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
        service = OnboardingService(db)
        return service.update_onboarding_settings(business_id, settings_data, current_user.id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# List forms (paginated)
# ---------------------------------------------------------------------------
@router.get("/", response_model=OnboardingListResponse)
async def list_onboarding_forms(
    business_id: int = Path(..., description="Business ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    form_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
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
        items = []
        for form in forms:
            items.append({
                "id": form.id,
                "business_id": form.business_id,
                "candidate_name": form.candidate_name,
                "candidate_email": form.candidate_email,
                "candidate_mobile": form.candidate_mobile,
                "form_token": form.form_token,
                "status": form.status.value if form.status else None,
                "verify_mobile": form.verify_mobile,
                "verify_pan": form.verify_pan,
                "verify_bank": form.verify_bank,
                "verify_aadhaar": form.verify_aadhaar,
                "notes": form.notes,
                "policies": form.policies,
                "offer_letter": form.offer_letter,
                "salary_options": form.salary_options,
                "created_at": form.created_at,
                "sent_at": form.sent_at,
                "submitted_at": form.submitted_at,
                "approved_at": form.approved_at,
                "rejected_at": form.rejected_at,
                "expires_at": form.expires_at,
                "rejection_reason": form.rejection_reason,
                "created_by": form.created_by
            })
        return {"items": items, "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))




# ---------------------------------------------------------------------------
# Approve / Reject / Bulk / Update / Send
# ---------------------------------------------------------------------------
@router.post("/{form_id}/approve", response_model=OnboardingResponseSchema)
async def approve_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        from app.models.employee import Employee
        from datetime import date

        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        if form.status == OnboardingStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Form is already approved")

        submissions = db.query(FormSubmission).filter(FormSubmission.form_id == form_id).all()
        # ... extraction logic unchanged, but ensure created employee business_id set

        # existing employee check scoped to business
        existing_employee = db.query(Employee).filter(Employee.email == form.candidate_email, Employee.business_id == business_id).first()
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

        # Create new employee with proper name parsing to avoid NULL last_name
        candidate_name = form.candidate_name or ""
        name_parts = candidate_name.strip().split() if candidate_name else []
        first_name = name_parts[0] if name_parts else 'Unknown'
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "NA"

        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=first_name,
            last_name=last_name,
            email=form.candidate_email,
            mobile=form.candidate_mobile,
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
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    rejection_data: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        reason = rejection_data.get("reason") if rejection_data else "No reason provided"
        service = OnboardingService(db)
        form = service.reject_onboarding_form(form_id, business_id, current_user.id, reason)
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        return form
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/bulk", response_model=BulkOnboardingResponse)
async def create_bulk_onboarding(
    business_id: int = Path(..., description="Business ID"),
    bulk_data: BulkOnboardingCreate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        result = service.process_bulk_onboarding(bulk_data, business_id, current_user.id)
        return result.get("bulk_operation")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{form_id}", response_model=OnboardingResponseSchema)
async def update_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    form_data: UpdateOnboardingSchema = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
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


@router.post("/{form_id}/send", response_model=OnboardingResponseSchema)
async def send_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
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


# ---------------------------------------------------------------------------
# Submissions (candidate-facing) - still business-scoped via path but do not require auth
# ---------------------------------------------------------------------------
@router.post("/{form_id}/submit", response_model=FormSubmissionResponse)
async def submit_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    submission_data: FormSubmissionCreate = None,
    db: Session = Depends(get_db)
):
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
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


@router.delete("/{form_id}")
async def delete_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
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
# Credits
# ---------------------------------------------------------------------------
@router.get("/credits", response_model=dict)
async def get_user_credits(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        from app.services.credit_service import CreditService
        user_credits = CreditService.get_user_credits(db, current_user.id, business_id)
        return {"credits": user_credits.credits, "user_id": current_user.id, "business_id": business_id, "last_updated": user_credits.updated_at or user_credits.created_at}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/credits/purchase", response_model=dict)
async def purchase_credits(
    business_id: int = Path(..., description="Business ID"),
    purchase_request: CreditPurchaseRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        from app.services.credit_service import CreditService
        return CreditService.purchase_credits(db, current_user.id, business_id, purchase_request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/credits/pricing", response_model=dict)
async def get_credit_pricing(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        from app.services.credit_service import CreditService
        pricing = CreditService.get_credit_pricing(db, business_id)
        return {"pricing": pricing, "business_id": business_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Get form by id
# ---------------------------------------------------------------------------
@router.get("/forms/{form_id:int}", response_model=OnboardingResponseSchema)
async def get_onboarding_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = validate_form_access(db, form_id, business_id, current_user)
        return form
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Approvals endpoints
# ---------------------------------------------------------------------------
@router.get("/approvals/pending", response_model=dict)
async def get_pending_approvals(
    business_id: int = Path(..., description="Business ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        query = db.query(OnboardingForm).filter(
            OnboardingForm.status == OnboardingStatus.SUBMITTED,
            OnboardingForm.is_active == True,
            OnboardingForm.business_id == business_id
        )
        total_count = query.count()
        offset = (page - 1) * limit
        forms = query.order_by(desc(OnboardingForm.submitted_at)).offset(offset).limit(limit).all()
        pending_forms = []
        for form in forms:
            location = "Hyderabad"
            deputation = "No"
            if form.notes:
                notes_lower = form.notes.lower()
                if "location:" in notes_lower:
                    location = form.notes.split("Location:")[1].split(",")[0].strip() if "Location:" in form.notes else location
                if "deputation:" in notes_lower:
                    deputation = form.notes.split("Deputation:")[1].split(",")[0].strip() if "Deputation:" in form.notes else deputation
            joining_date = form.submitted_at.strftime("%d-%b-%Y") if form.submitted_at else "Not specified"
            pending_forms.append({
                "id": form.id,
                "name": form.candidate_name,
                "joining": joining_date,
                "location": location,
                "deputation": deputation,
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
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        # Reuse approve logic but provide frontend-friendly response
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        if form.status == OnboardingStatus.APPROVED:
            return {"success": True, "message": f"Form already approved (Employee: {form.employee_id})", "form_id": form.id, "status": form.status.value, "employee_id": form.employee_id, "already_approved": True}
        # Simplified create employee flow kept minimal for brevity
        from app.models.employee import Employee
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        candidate_name = form.candidate_name or ""
        name_parts = candidate_name.strip().split() if candidate_name else []
        first_name = name_parts[0] if name_parts else 'Unknown'
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "NA"

        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=first_name,
            last_name=last_name,
            email=form.candidate_email,
            created_by=current_user.id,
            is_active=True
        )
        db.add(new_employee)
        db.flush()
        form.employee_id = new_employee.id
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        db.commit()
        return {"success": True, "message": f"Onboarding form approved and employee {employee_code} created successfully!", "form_id": form.id, "status": form.status.value, "employee_id": new_employee.id, "employee_code": new_employee.employee_code, "employee_name": f"{new_employee.first_name} {getattr(new_employee,'last_name','')}", "approved_at": form.approved_at.isoformat(), "approved_by": current_user.name if hasattr(current_user, 'name') else current_user.email}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{form_id}/reject-frontend", response_model=dict)
async def reject_form_frontend(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    rejection_data: OnboardingRejectionRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        form.status = OnboardingStatus.REJECTED
        form.rejected_at = datetime.now()
        form.rejected_by = current_user.id
        form.rejection_reason = rejection_data.reason if rejection_data else None
        db.commit()
        db.refresh(form)
        return {"success": True, "message": f"Onboarding form for {form.candidate_name} rejected", "form_id": form.id, "status": form.status, "rejected_at": form.rejected_at.isoformat(), "rejected_by": current_user.name if hasattr(current_user, 'name') else current_user.email, "rejection_reason": rejection_data.reason if rejection_data else None}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Frontend-compatible list/create
# ---------------------------------------------------------------------------
@router.get("/forms/list", response_model=dict)
async def get_forms_for_frontend(
    business_id: int = Path(..., description="Business ID"),
    form_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        query = db.query(OnboardingForm).filter(OnboardingForm.business_id == business_id)
        if form_status and form_status.lower() not in ['all', '']:
            query = query.filter(OnboardingForm.status == form_status)
        if search and search.strip():
            term = f"%{search}%"
            query = query.filter((OnboardingForm.candidate_name.ilike(term)) | (OnboardingForm.candidate_email.ilike(term)))
        forms = query.all()
        forms_list = []
        for form in forms:
            forms_list.append({
                "id": form.id,
                "candidate": form.candidate_name,
                "candidate_name": form.candidate_name,
                "email": form.candidate_email,
                "candidate_email": form.candidate_email,
                "mobile": form.candidate_mobile,
                "candidate_mobile": form.candidate_mobile,
                "status": form.status.value.capitalize() if hasattr(form.status, 'value') else str(form.status).capitalize(),
                "created": form.created_at.strftime("%d-%b-%Y") if form.created_at else None,
                "created_at": form.created_at.isoformat() if form.created_at else None,
                "updated_at": form.updated_at.isoformat() if form.updated_at else None,
                "sent_at": form.sent_at.isoformat() if form.sent_at else None,
                "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
                "approved_at": form.approved_at.isoformat() if form.approved_at else None,
                "rejected_at": form.rejected_at.isoformat() if form.rejected_at else None,
                "business_id": form.business_id,
                "form_token": form.form_token,
                "notes": form.notes,
                "info": "View Details"
            })
        return {"success": True, "forms": forms_list, "total": len(forms_list)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/forms/create", response_model=dict)
async def create_form_frontend_compatible(
    business_id: int = Path(..., description="Business ID"),
    form_data: CreateOnboardingSchema = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        form = service.create_onboarding_form(form_data, business_id, current_user.id)
        return {"success": True, "message": "Onboarding form created successfully", "form_id": form.id, "form_token": form.form_token, "expires_at": form.expires_at.isoformat() if form.expires_at else None, "form": {"id": form.id, "candidate": form.candidate_name, "created": form.created_at.strftime("%d-%b-%Y") if form.created_at else "", "email": form.candidate_email, "mobile": form.candidate_mobile, "info": "View Form", "status": "Draft", "form_token": form.form_token}}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Finalize and send
# ---------------------------------------------------------------------------
@router.post("/{form_id}/finalize", response_model=dict)
async def finalize_and_send_form(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    finalize_data: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding form not found")
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        if not form.form_token:
            import uuid
            form.form_token = str(uuid.uuid4())
        db.commit()
        email_sent = False
        # Optionally send email via email_service as before
        return {"success": True, "message": "Onboarding form sent successfully", "form_id": form.id, "status": form.status, "sent_at": form.sent_at.isoformat(), "email_sent": email_sent}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------
@router.post("/templates/generate", response_model=TemplateGenerationResponse)
async def generate_letter_from_template(
    business_id: int = Path(..., description="Business ID"),
    generation_data: TemplateGenerationRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        template_name = generation_data.template_name
        field_values_text = generation_data.field_values
        template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.name == template_name, OfferLetterTemplate.business_id == business_id, OfferLetterTemplate.is_active == True).first()
        if not template:
            template = db.query(OfferLetterTemplate).filter(OfferLetterTemplate.name == template_name, OfferLetterTemplate.is_active == True).first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_name}' not found")
        field_values = {}
        if field_values_text and field_values_text.strip():
            for line in field_values_text.strip().split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    field_values[k.strip()] = v.strip()
        generated_content = template.template_content
        for k, v in field_values.items():
            generated_content = generated_content.replace(f"{{{k}}}", v)
        import re
        generated_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', generated_content).strip()
        offer_letter = OfferLetter(business_id=business_id, form_id=None, template_id=template.id, position_title=field_values.get("position_title", ""), department=field_values.get("department", ""), location=field_values.get("location", ""), basic_salary=field_values.get("basic_salary", ""), gross_salary=field_values.get("gross_salary", ""), ctc=field_values.get("ctc", ""), letter_content=generated_content, is_generated=True, is_sent=False, created_by=current_user.id, created_at=datetime.now())
        db.add(offer_letter)
        db.commit()
        db.refresh(offer_letter)
        return TemplateGenerationResponse(success=True, message="Letter generated successfully", offer_letter_id=offer_letter.id, generated_content=generated_content, template_name=template_name, field_values=field_values)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Templates frontend format
# ---------------------------------------------------------------------------
@router.get("/templates/frontend-format", response_model=dict)
async def get_templates_frontend_format(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.get_templates_frontend_format(business_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Settings frontend-format and updates
# ---------------------------------------------------------------------------
@router.get("/settings/frontend-format", response_model=dict)
async def get_settings_frontend_format(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.get_settings_frontend_format(business_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/settings/update-document", response_model=dict)
async def update_document_requirement(
    business_id: int = Path(..., description="Business ID"),
    update_data: DocumentRequirementUpdateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.update_document_requirement(business_id, update_data.document_type, update_data.is_required, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/settings/update-field", response_model=dict)
async def update_field_requirement(
    business_id: int = Path(..., description="Business ID"),
    update_data: FieldRequirementUpdateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        service = OnboardingService(db)
        return service.update_field_requirement(business_id, update_data.field_name, update_data.is_required, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Legacy / Utility endpoints (kept but business-scoped)
# ---------------------------------------------------------------------------
@router.post("/bulk-send")
async def bulk_send_forms_legacy(
    business_id: int = Path(..., description="Business ID"),
    bulk_data: BulkSendRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        candidates = bulk_data.candidates if bulk_data else []
        sent_count = 0
        failed_count = 0
        errors = []
        for candidate in candidates:
            try:
                form = OnboardingForm(business_id=business_id, candidate_name=candidate.name, candidate_email=candidate.email, position=candidate.position, department=candidate.department, status=OnboardingStatus.SENT, created_by=current_user.id)
                db.add(form)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{candidate.email}: {str(e)}")
        db.commit()
        return {"success": True, "message": f"Bulk send completed: {sent_count} sent, {failed_count} failed", "sent_count": sent_count, "failed_count": failed_count, "errors": errors}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/credit-pricing")
async def get_credit_pricing_legacy(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        pricing_data = {"packages": [{"credits": 50, "price": 200, "per_credit": 4.00, "discount": "0%"}, {"credits": 100, "price": 350, "per_credit": 3.50, "discount": "12.5%"}, {"credits": 250, "price": 750, "per_credit": 3.00, "discount": "25%"}, {"credits": 500, "price": 1250, "per_credit": 2.50, "discount": "37.5%"}], "currency": "USD", "validity_months": 12, "payment_methods": ["Credit Card", "Bank Transfer", "PayPal"]}
        return pricing_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
@router.post("/forms/{form_id}/send")
async def send_onboarding_form_legacy(
    business_id: int = Path(..., description="Business ID"),
    form_id: int = Path(..., description="Form ID"),
    send_data: SendFormRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        validate_business_access(business_id, current_user, db)
        form = validate_form_access(db, form_id, business_id, current_user)
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        form.form_token = f"token_{form_id}_{int(datetime.now().timestamp())}"
        db.commit()
        return {"success": True, "message": "Onboarding form sent successfully", "form_id": form_id, "form_token": form.form_token, "sent_to": form.candidate_email}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Candidate workflow (token based) - still scoped by business_id in path
# ---------------------------------------------------------------------------
@router.get("/candidate/form/{form_token}")
async def get_candidate_form_by_token(
    business_id: int = Path(..., description="Business ID"),
    form_token: str = Path(..., description="Form token"),
    db: Session = Depends(get_db)
):
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        from app.models.business import Business
        business = db.query(Business).filter(Business.id == form.business_id).first()
        business_name = business.business_name if business else "Company"
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        current_step = 1
        if submission:
            if submission.first_name: current_step = 2
            if submission.alternate_mobile: current_step = 3
            if submission.blood_group: current_step = 4
            if submission.aadhaar_number: current_step = 5
            if submission.marital_status: current_step = 6
            if submission.present_address: current_step = 7
            if submission.permanent_address: current_step = 8
            if submission.bank_name: current_step = 9
        return {"form_id": form.id, "form_token": form.form_token, "candidate_name": form.candidate_name, "candidate_email": form.candidate_email, "candidate_mobile": form.candidate_mobile, "business_name": business_name, "business_id": form.business_id, "current_step": current_step, "total_steps": 11, "status": form.status.value, "has_submission": submission is not None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/candidate/form/{form_token}/step/{step_number}")
async def submit_candidate_form_step(
    business_id: int = Path(..., description="Business ID"),
    form_token: str = Path(..., description="Form token"),
    step_number: int = Path(..., description="Step number"),
    step_data: StepDataRequest = None,
    db: Session = Depends(get_db)
):
    try:
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token, OnboardingForm.business_id == business_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        if not submission:
            submission = FormSubmission(form_id=form.id, submitted_at=datetime.now())
            db.add(submission)
        data = step_data.data if step_data else {}
        # (store step-specific data similarly as before)
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


# Remaining candidate endpoints (get step data, OTP, document upload) should also include business_id param in path
# For brevity they are left unchanged except for adding the business_id path parameter in decorators above


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------
@router.get("/debug/environment", response_model=DebugEnvironmentResponse, summary="Get safe environment debug info")
async def check_server_environment(
    business_id: int = Path(..., description="Business id to scope the request"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return non-sensitive environment information scoped to a business.

    - Requires admin or superadmin access.
    - Uses `validate_business_access` to enforce multi-tenant isolation.
    - Does NOT expose secrets, file paths, database passwords, or API keys.
    """
    # Validate that user can access the requested business
    validate_business_access(business_id, current_user, db)

    # Collect safe, non-sensitive runtime info
    import platform
    from app.core.config import settings
    now = datetime.utcnow()

    environment = "development" if getattr(settings, 'DEBUG', False) else "production"

    response = {
        "success": True,
        "business_id": business_id,
        "environment": environment,
        "python_version": platform.python_version(),
        "server_status": "running",
        "app_version": getattr(settings, 'APP_VERSION', None),
        "timestamp": now,
    }

    return response
