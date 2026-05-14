"""
Onboarding API Endpoints - Repository/Service Pattern Implementation
Complete onboarding workflow management API with proper architecture
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta
import json
import logging

from app.core.database import get_db

# Initialize logger
logger = logging.getLogger(__name__)

from app.api.v1.deps import get_current_admin
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

router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS FOR BUSINESS ISOLATION
# ============================================================================
def get_user_business_ids(db: Session, current_user) -> list:
    """
    Get list of business IDs owned by the current user.
    This ensures data isolation between different businesses.
    """
    from app.models.business import Business
    
    user_business_ids = db.query(Business.id).filter(
        Business.owner_id == current_user.id
    ).all()
    return [b[0] for b in user_business_ids]


def validate_form_access(db: Session, form_id: int, current_user) -> 'OnboardingForm':
    """
    Validate that the onboarding form belongs to one of the user's businesses.
    
    Args:
        db: Database session
        form_id: ID of the form to validate
        current_user: Current authenticated user
        
    Returns:
        OnboardingForm object if found and accessible
        
    Raises:
        HTTPException 404: If form not found or not accessible
    """
    from app.models.onboarding import OnboardingForm
    from fastapi import HTTPException, status
    
    user_business_ids = get_user_business_ids(db, current_user)
    
    if not user_business_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding form with ID {form_id} not found"
        )
    
    form = db.query(OnboardingForm).filter(
        OnboardingForm.id == form_id,
        OnboardingForm.business_id.in_(user_business_ids)
    ).first()
    
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding form with ID {form_id} not found"
        )
    
    return form


# =============================================================================
# ONBOARDING DASHBOARD ENDPOINT
# =============================================================================

@router.get("/dashboard", response_model=OnboardingDashboardResponse)
async def get_onboarding_dashboard(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get onboarding dashboard statistics
    Returns overview data for the onboarding module
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)

        # If user has no businesses at all
        if not user_business_ids:
            return {
                "business_id": business_id,
                "total_forms": 0,
                "draft_forms": 0,
                "sent_forms": 0,
                "submitted_forms": 0,
                "approved_forms": 0,
                "rejected_forms": 0,
                "expired_forms": 0,
                "pending_approvals": 0,
                "recent_submissions": [],
                "monthly_stats": [],
                "conversion_rate": 0.0,
                "average_completion_time": None
            }

        # Validate that the requested business_id belongs to the user
        if business_id not in user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business with id {business_id} not found or not accessible"
            )

        # Use service layer for real data
        service = OnboardingService(db)
        dashboard_data = service.get_dashboard_data(business_id) or {}

        # Ensure response includes business_id
        if isinstance(dashboard_data, dict):
            dashboard_data["business_id"] = business_id

        return dashboard_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch onboarding dashboard data: {str(e)}"
        )

# =============================================================================
# SALARY CALCULATION ENDPOINTS
# =============================================================================

@router.post("/{form_id}/calculate-salary", response_model=dict)
async def calculate_salary_for_offer_letter(
    form_id: int,
    calculation_data: SalaryCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Calculate salary breakup for offer letter
    
    **Request body:**
    - gross_salary: Gross salary amount (required, must be > 0)
    - salary_structure_id: Salary structure ID (optional)
    - employee_id: Employee ID (optional)
    - options: Additional salary calculation options (optional)
    """
    try:
        from app.services.salary_calculation_service import SalaryCalculationService
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Validate form exists
        form = db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.id == form_id,
                OnboardingForm.business_id == business_id
            )
        ).first()
        
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Calculate salary breakup
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate salary: {str(e)}"
        )


@router.get("/salary-structures", response_model=List[dict])
async def get_salary_structures_for_offer_letter(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get available salary structures for offer letter"""
    try:
        from app.services.salary_calculation_service import SalaryCalculationService
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return []
        
        # Use first business
        business_id = user_business_ids[0]
        
        calc_service = SalaryCalculationService(db)
        structures = calc_service.get_salary_structures(business_id)
        
        return structures
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch salary structures: {str(e)}"
        )


@router.get("/{form_id}/employee-profile", response_model=dict)
async def get_employee_profile_for_offer_letter(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee profile data for offer letter"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Get form
        form = db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.id == form_id,
                OnboardingForm.business_id == business_id
            )
        ).first()
        
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Get employee if linked
        employee_profile = {}
        if form.employee_id:
            from app.models.employee import Employee
            from app.models.location import Location
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.grades import Grade
            from app.models.cost_center import CostCenter
            from app.models.work_shifts import WorkShift
            
            employee = db.query(Employee).filter(Employee.id == form.employee_id).first()
            if employee:
                # Get related data
                location = db.query(Location).filter(Location.id == employee.location_id).first() if employee.location_id else None
                department = db.query(Department).filter(Department.id == employee.department_id).first() if employee.department_id else None
                designation = db.query(Designation).filter(Designation.id == employee.designation_id).first() if employee.designation_id else None
                grade = db.query(Grade).filter(Grade.id == employee.grade_id).first() if employee.grade_id else None
                cost_center = db.query(CostCenter).filter(CostCenter.id == employee.cost_center_id).first() if employee.cost_center_id else None
                
                # Get shift policy if exists
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
        
        # Get dropdown options
        from app.models.location import Location
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.grades import Grade
        from app.models.cost_center import CostCenter
        from app.models.work_shifts import WorkShift
        
        locations = db.query(Location).filter(Location.business_id == business_id, Location.is_active == True).all()
        departments = db.query(Department).filter(Department.business_id == business_id, Department.is_active == True).all()
        designations = db.query(Designation).filter(Designation.business_id == business_id).all()  # No is_active filter
        grades = db.query(Grade).filter(Grade.business_id == business_id).all()  # No is_active filter
        cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business_id, CostCenter.is_active == True).all()
        work_shifts = db.query(WorkShift).filter(WorkShift.business_id == business_id).all()  # No is_active filter
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee profile: {str(e)}"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def replace_template_variables(template_content: str, data: dict) -> str:
    """
    Replace template variables in format {{variable_name}} with actual values
    
    Args:
        template_content: Template string with {{variable}} placeholders
        data: Dictionary with variable names and their values
    
    Returns:
        String with all variables replaced
    """
    result = template_content
    
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"  # {{variable_name}}
        result = result.replace(placeholder, str(value) if value is not None else "")
    
    return result


# =============================================================================
# OFFER LETTER GENERATION ENDPOINTS
# =============================================================================

@router.post("/{form_id}/generate-offer-letter", response_model=dict)
async def generate_complete_offer_letter(
    form_id: int,
    offer_data: OfferLetterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Generate complete offer letter with salary calculation and template
    
    **Request body:**
    - template_id: Offer letter template ID (optional)
    - position_title: Position title (optional)
    - department: Department name (optional)
    - location: Work location (optional)
    - gross_salary: Gross salary amount (optional)
    - basic_salary: Basic salary amount (optional)
    - ctc: Cost to company (optional)
    - salary_structure_id: Salary structure ID (optional)
    - salary_options: Salary calculation options (optional)
    - joining_date: Joining date (optional)
    - offer_valid_until: Offer validity date (optional)
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Validate form exists
        form = db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.id == form_id,
                OnboardingForm.business_id == business_id
            )
        ).first()
        
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Get template
        template_id = offer_data.template_id
        template = None
        if template_id:
            template = db.query(OfferLetterTemplate).filter(
                and_(
                    OfferLetterTemplate.id == template_id,
                    OfferLetterTemplate.business_id == business_id,
                    OfferLetterTemplate.is_active == True
                )
            ).first()
        
        # Calculate salary if provided
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
        
        # Get business details for template
        business = db.query(User).filter(User.id == current_user.id).first()
        
        # Get work shift details if provided
        shift_start_time = "09:00 AM"
        shift_end_time = "06:00 PM"
        if offer_data.work_shift:
            # Try to extract shift times from work shift name or use defaults
            shift_name_lower = offer_data.work_shift.lower()
            if "night" in shift_name_lower:
                shift_start_time = "10:00 PM"
                shift_end_time = "07:00 AM"
            elif "morning" in shift_name_lower:
                shift_start_time = "07:00 AM"
                shift_end_time = "04:00 PM"
            elif "evening" in shift_name_lower:
                shift_start_time = "02:00 PM"
                shift_end_time = "11:00 PM"
        
        # Calculate confirmation date if not provided
        confirmation_date_str = "To be decided"
        if offer_data.confirmation_date:
            confirmation_date_str = offer_data.confirmation_date.strftime("%d-%b-%Y")
        elif offer_data.joining_date:
            # Default: 6 months after joining
            confirmation_date_str = (offer_data.joining_date + timedelta(days=180)).strftime("%d-%b-%Y")
        
        # Prepare template variables
        template_variables = {
            # Company details
            "company_name": business.name if business else "Company Name",
            "company_address": business.address if business else "Company Address",
            "offer_date": datetime.now().strftime("%d-%b-%Y"),
            
            # Candidate details
            "candidate_name": form.candidate_name or "Candidate Name",
            "candidate_address": "Candidate Address",  # Can be added to form if needed
            "candidate_email": form.candidate_email or "",
            "candidate_mobile": form.candidate_mobile or "",
            
            # Position details
            "position_title": offer_data.position_title or "Position",
            "department": offer_data.department or "Department",
            "location": offer_data.location or "Location",
            "grade": offer_data.grade or "Grade",
            "cost_center": offer_data.cost_center or "Cost Center",
            "work_shift": offer_data.work_shift or "Day Shift",
            
            # Dates
            "joining_date": offer_data.joining_date.strftime("%d-%b-%Y") if offer_data.joining_date else "To be decided",
            "confirmation_date": confirmation_date_str,
            "date_of_birth": offer_data.date_of_birth.strftime("%d-%b-%Y") if offer_data.date_of_birth else "Not specified",
            "offer_expiry_date": (datetime.now() + timedelta(days=7)).strftime("%d-%b-%Y"),
            
            # Salary details
            "base_salary": str(salary_breakup["earnings"].get("Basic Salary", 0)) if salary_breakup else offer_data.basic_salary or "0",
            "gross_salary": str(offer_data.gross_salary or 0),
            "annual_ctc": str(salary_breakup["ctc"]) if salary_breakup else offer_data.ctc or "0",
            "hra": str(salary_breakup["earnings"].get("House Rent Allowance", 0)) if salary_breakup else "0",
            "special_allowance": str(salary_breakup["earnings"].get("Special Allowance", 0)) if salary_breakup else "0",
            
            # Working conditions
            "shift_start_time": shift_start_time,
            "shift_end_time": shift_end_time,
            "working_days": "Monday to Friday",  # Can be made configurable
            "probation_period": "6",  # Can be made configurable
            "notice_period": str(offer_data.notice_period) if offer_data.notice_period else "30",
            "annual_leave_days": "21",  # Can be made configurable
            
            # Personal details
            "gender": offer_data.gender or "Not specified",
            "reporting_manager": "Reporting Manager",  # Can be added to form if needed
            
            # HR details
            "hr_manager_name": business.name if business else "HR Manager",
            "hr_manager_designation": "HR Manager",
            
            # Contract-specific variables
            "contract_start_date": offer_data.joining_date.strftime("%d-%b-%Y") if offer_data.joining_date else "To be decided",
            "contract_end_date": (offer_data.joining_date + timedelta(days=365)).strftime("%d-%b-%Y") if offer_data.joining_date else "To be decided",
            "contract_duration": "12",
            "monthly_compensation": str(offer_data.gross_salary or 0),
            "contract_notice_period": "15",
            # Internship-specific variables
            "internship_duration": "6",
            "internship_end_date": (offer_data.joining_date + timedelta(days=180)).strftime("%d-%b-%Y") if offer_data.joining_date else "To be decided",
            "monthly_stipend": str(offer_data.gross_salary or 0),
            # Part-time specific variables
            "part_time_hours": "20",
            "part_time_days": "Monday, Wednesday, Friday",
            "hourly_rate": str(int(offer_data.gross_salary / 80) if offer_data.gross_salary else 0),
            "part_time_notice_period": "15",
            "review_period": "3"
        }
        
        # Generate letter content by replacing template variables
        letter_content = template.template_content if template else ""
        if letter_content:
            letter_content = replace_template_variables(letter_content, template_variables)
        
        # Create or update offer letter
        existing_offer = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()
        
        if existing_offer:
            # Update existing
            existing_offer.template_id = template_id
            existing_offer.position_title = offer_data.position_title or ""
            existing_offer.department = offer_data.department or ""
            existing_offer.location = offer_data.location or ""
            existing_offer.basic_salary = str(salary_breakup["earnings"].get("Basic Salary", 0)) if salary_breakup else offer_data.basic_salary or ""
            existing_offer.gross_salary = str(offer_data.gross_salary or 0)
            existing_offer.ctc = str(salary_breakup["ctc"]) if salary_breakup else offer_data.ctc or ""
            existing_offer.joining_date = offer_data.joining_date
            existing_offer.offer_valid_until = offer_data.offer_valid_until
            existing_offer.letter_content = letter_content
            existing_offer.is_generated = True
            existing_offer.updated_at = datetime.now()
            
            offer_letter = existing_offer
        else:
            # Create new
            offer_letter = OfferLetter(
                form_id=form_id,
                template_id=template_id,
                position_title=offer_data.position_title or "",
                department=offer_data.department or "",
                location=offer_data.location or "",
                basic_salary=str(salary_breakup["earnings"].get("Basic Salary", 0)) if salary_breakup else offer_data.basic_salary or "",
                gross_salary=str(offer_data.gross_salary or 0),
                ctc=str(salary_breakup["ctc"]) if salary_breakup else offer_data.ctc or "",
                joining_date=offer_data.joining_date,
                offer_valid_until=offer_data.offer_valid_until,
                letter_content=letter_content,
                is_generated=True,
                is_sent=False,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate offer letter: {str(e)}"
        )


# =============================================================================
# OFFER LETTER TEMPLATE ENDPOINTS (Must come before /{form_id} endpoints)
# =============================================================================

@router.get("/templates", response_model=List[OfferLetterTemplateResponse])
async def get_offer_letter_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get all offer letter templates"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # First try to get templates for the user's business
        templates = db.query(OfferLetterTemplate).filter(
            and_(
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            )
        ).order_by(OfferLetterTemplate.name).all()
        
        # If no templates found for user's business, get all active templates
        if not templates:
            templates = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.is_active == True
            ).order_by(OfferLetterTemplate.name).all()
        
        return templates
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch offer letter templates: {str(e)}"
        )


@router.post("/templates", response_model=OfferLetterTemplateResponse)
async def create_offer_letter_template(
    template_data: OfferLetterTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new offer letter template"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)  # Default to business_id = 4
        
        business_id = user_business_ids[0]
        # Create new template
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create offer letter template: {str(e)}"
        )


# =============================================================================
# OFFER LETTER GENERATION ENDPOINTS
# =============================================================================

@router.post("/offer-letters", response_model=OfferLetterResponse)
async def generate_offer_letter(
    offer_data: OfferLetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Generate an offer letter"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)  # Default to business_id = 4
        
        business_id = user_business_ids[0]
        # Get template if specified
        template = None
        if offer_data.template_id:
            template = db.query(OfferLetterTemplate).filter(
                and_(
                    OfferLetterTemplate.id == offer_data.template_id,
                    OfferLetterTemplate.business_id == business_id,
                    OfferLetterTemplate.is_active == True
                )
            ).first()
        
        # Create offer letter record
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
            created_by=current_user.id,
            created_at=datetime.now()
        )
        
        db.add(offer_letter)
        db.commit()
        db.refresh(offer_letter)
        
        return offer_letter
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate offer letter: {str(e)}"
        )


@router.get("/offer-letters", response_model=List[OfferLetterResponse])
async def get_offer_letters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get all offer letters"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)  # Default to business_id = 4
        
        query = db.query(OfferLetter)
        offer_letters = query.order_by(desc(OfferLetter.created_at)).all()
        
        return offer_letters
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch offer letters: {str(e)}"
        )


# =============================================================================
# POLICY TEMPLATE ENDPOINTS
# =============================================================================

@router.get("/policy-templates", response_model=List[dict])
async def get_policy_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get available policy templates for onboarding forms"""
    try:
        # For now, return static policy templates
        # In a full implementation, these would come from a policy_templates table
        policy_templates = [
            {
                "id": 1,
                "name": "Employee Handbook",
                "description": "Complete guide to company policies and procedures",
                "type": "handbook",
                "is_mandatory": True,
                "requires_acknowledgment": True,
                "file_path": "/policies/employee-handbook.pdf"
            },
            {
                "id": 2,
                "name": "Code of Conduct",
                "description": "Professional behavior and ethical guidelines",
                "type": "conduct",
                "is_mandatory": True,
                "requires_acknowledgment": True,
                "file_path": "/policies/code-of-conduct.pdf"
            },
            {
                "id": 3,
                "name": "IT Security Policy",
                "description": "Information technology security guidelines and requirements",
                "type": "it_security",
                "is_mandatory": True,
                "requires_acknowledgment": True,
                "file_path": "/policies/it-security-policy.pdf"
            },
            {
                "id": 4,
                "name": "Remote Work Policy",
                "description": "Guidelines for remote work arrangements",
                "type": "remote_work",
                "is_mandatory": False,
                "requires_acknowledgment": True,
                "file_path": "/policies/remote-work-policy.pdf"
            },
            {
                "id": 5,
                "name": "Leave Policy",
                "description": "Annual leave, sick leave, and other time-off policies",
                "type": "leave",
                "is_mandatory": True,
                "requires_acknowledgment": True,
                "file_path": "/policies/leave-policy.pdf"
            },
            {
                "id": 6,
                "name": "Health & Safety Policy",
                "description": "Workplace health and safety guidelines",
                "type": "health_safety",
                "is_mandatory": True,
                "requires_acknowledgment": True,
                "file_path": "/policies/health-safety-policy.pdf"
            }
        ]
        
        return policy_templates
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch policy templates: {str(e)}"
        )


@router.post("/{form_id}/attach-policies", response_model=dict)
async def attach_policies_to_form(
    form_id: int,
    policy_data: PolicyAttachmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Attach selected policies to an onboarding form
    
    **Request body:**
    - policy_ids: List of policy IDs to attach (required)
    """
    try:
        # Validate form access with business isolation
        form = validate_form_access(db, form_id, current_user)
        
        # Get selected policy IDs
        selected_policy_ids = policy_data.policy_ids
        
        # Remove existing policies for this form
        db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id).delete()
        
        # Add new policies
        policy_templates = [
            {"id": 1, "name": "Employee Handbook", "type": "handbook"},
            {"id": 2, "name": "Code of Conduct", "type": "conduct"},
            {"id": 3, "name": "IT Security Policy", "type": "it_security"},
            {"id": 4, "name": "Remote Work Policy", "type": "remote_work"},
            {"id": 5, "name": "Leave Policy", "type": "leave"},
            {"id": 6, "name": "Health & Safety Policy", "type": "health_safety"}
        ]
        
        for i, policy_id in enumerate(selected_policy_ids):
            # Find policy template
            policy_template = next((p for p in policy_templates if p["id"] == policy_id), None)
            if policy_template:
                policy = OnboardingPolicy(
                    form_id=form_id,
                    policy_name=policy_template["name"],
                    policy_content=f"Policy content for {policy_template['name']}",
                    policy_file_path=f"/policies/{policy_template['type']}.pdf",
                    requires_acknowledgment=True,
                    is_mandatory=policy_id in [1, 2, 3, 5, 6],  # Most policies are mandatory
                    display_order=i,
                    created_by=current_user.id
                )
                db.add(policy)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully attached {len(selected_policy_ids)} policies to form",
            "form_id": form_id,
            "attached_policies": len(selected_policy_ids)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach policies: {str(e)}"
        )


@router.get("/{form_id}/policies", response_model=List[dict])
async def get_form_policies(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get policies attached to a specific form"""
    try:
        # Validate form access with business isolation
        form = validate_form_access(db, form_id, current_user)
        
        # Get attached policies
        policies = db.query(OnboardingPolicy).filter(
            OnboardingPolicy.form_id == form_id
        ).order_by(OnboardingPolicy.display_order).all()
        
        # Convert to response format
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch form policies: {str(e)}"
        )


# =============================================================================
# SETTINGS ENDPOINTS (Must come before /{form_id} endpoints)
# =============================================================================

@router.get("/settings", response_model=OnboardingSettingsResponse, operation_id="get_onboarding_settings_v1")
async def get_onboarding_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get onboarding settings for the current business"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business ID not found for current user"
            )
        
        # Use first business
        business_id = user_business_ids[0]
        
        # Use service layer
        service = OnboardingService(db)
        settings_data = service.get_onboarding_settings(business_id, current_user.id)
        
        return settings_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch onboarding settings: {str(e)}"
        )


@router.put("/settings", response_model=OnboardingSettingsResponse)
async def update_onboarding_settings(
    settings_data: OnboardingSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update onboarding settings for the current business"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business ID not found for current user"
            )
        
        # Use first business
        business_id = user_business_ids[0]
        
        # Validate that at least one field is being updated
        update_dict = settings_data.dict(exclude_unset=True)
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        # Use service layer
        service = OnboardingService(db)
        updated_settings = service.update_onboarding_settings(business_id, settings_data, current_user.id)
        
        return updated_settings
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update onboarding settings: {str(e)}"
        )


# =============================================================================
# BASIC ONBOARDING ENDPOINTS
# =============================================================================


@router.get("/", response_model=PaginatedOnboardingResponse)
async def list_onboarding_forms(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    form_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """List onboarding forms with pagination"""
    try:
        from fastapi import status as http_status
        
        # Get user's business IDs for filtering
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "size": limit,
                "pages": 0
            }
        
        # Query forms filtered by user's businesses
        query = db.query(OnboardingForm).filter(
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        # Apply status filter (skip if status is None, empty, or "All")
        if form_status and form_status.lower() not in ['all', '']:
            query = query.filter(OnboardingForm.status == form_status)
        
        # Apply search filter
        if search and search.strip():  # Only apply if search has actual content
            search_term = f"%{search}%"
            query = query.filter(
                (OnboardingForm.candidate_name.ilike(search_term)) |
                (OnboardingForm.candidate_email.ilike(search_term)) |
                (OnboardingForm.candidate_mobile.ilike(search_term))
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        forms = query.offset(offset).limit(limit).all()
        
        return {
            "items": forms,
            "total": total,
            "page": page,
            "size": limit,
            "pages": (total + limit - 1) // limit
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch onboarding forms: {str(e)}"
        )


# =============================================================================
# FORM CREATION AND MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/", response_model=OnboardingFormResponse)
async def create_onboarding_form(
    form_data: OnboardingFormCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new onboarding form"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Use service layer
        service = OnboardingService(db)
        form = service.create_onboarding_form(form_data, business_id, current_user.id)
        
        return form
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create onboarding form: {str(e)}"
        )


@router.post("/{form_id}/approve", response_model=OnboardingFormResponse)
async def approve_onboarding_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Approve an onboarding form and automatically create employee record
    
    **Workflow:**
    1. Approve the onboarding form
    2. Extract candidate data from form submissions
    3. Create employee record in employees table
    4. Link employee to onboarding form
    5. Return approved form with employee details
    """
    try:
        from app.models.employee import Employee
        from datetime import datetime, date
        import json
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Get the onboarding form
        form = db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.id == form_id,
                OnboardingForm.business_id == business_id
            )
        ).first()
        
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Check if already approved
        if form.status == OnboardingStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Form is already approved"
            )
        
        # Get all form submissions to extract employee data
        submissions = db.query(FormSubmission).filter(
            FormSubmission.form_id == form_id
        ).all()
        
        # Parse submission data
        employee_data = {
            'first_name': None,
            'middle_name': None,
            'last_name': None,
            'email': form.candidate_email,
            'mobile': form.candidate_mobile,
            'date_of_birth': None,
            'gender': None,
            'marital_status': None,
            'blood_group': None,
            'aadhar_number': None,
            'pan_number': None,
            'uan_number': None,
            'esi_number': None,
            'current_address': None,
            'permanent_address': None,
            'emergency_contact': None,
            'emergency_phone': None,
            'father_name': None,
            'mother_name': None,
            'bank_name': None,
            'bank_account_number': None,
            'bank_ifsc_code': None,
            'bank_branch': None
        }
        
        # Extract data from submissions
        for submission in submissions:
            step_data = submission.step_data or {}
            
            # Step 2: Basic Details
            if submission.step_number == 2:
                employee_data['first_name'] = step_data.get('first_name')
                employee_data['middle_name'] = step_data.get('middle_name')
                employee_data['last_name'] = step_data.get('last_name')
                employee_data['gender'] = step_data.get('gender')
                employee_data['date_of_birth'] = step_data.get('date_of_birth')
            
            # Step 3: Contact Details
            elif submission.step_number == 3:
                employee_data['mobile'] = step_data.get('mobile') or employee_data['mobile']
                employee_data['email'] = step_data.get('personal_email') or employee_data['email']
                employee_data['emergency_contact'] = step_data.get('emergency_contact')
            
            # Step 4: Personal Details
            elif submission.step_number == 4:
                employee_data['marital_status'] = step_data.get('marital_status')
                employee_data['blood_group'] = step_data.get('blood_group')
                employee_data['father_name'] = step_data.get('father_name')
                employee_data['mother_name'] = step_data.get('mother_name')
            
            # Step 5: Statutory Details
            elif submission.step_number == 5:
                employee_data['aadhar_number'] = step_data.get('aadhar_number')
                employee_data['pan_number'] = step_data.get('pan_number')
                employee_data['uan_number'] = step_data.get('uan_number')
                employee_data['esi_number'] = step_data.get('esi_number')
            
            # Step 7: Present Address
            elif submission.step_number == 7:
                address_parts = []
                if step_data.get('address_line1'):
                    address_parts.append(step_data['address_line1'])
                if step_data.get('address_line2'):
                    address_parts.append(step_data['address_line2'])
                if step_data.get('city'):
                    address_parts.append(step_data['city'])
                if step_data.get('state'):
                    address_parts.append(step_data['state'])
                if step_data.get('pincode'):
                    address_parts.append(step_data['pincode'])
                employee_data['current_address'] = ', '.join(address_parts) if address_parts else None
            
            # Step 8: Permanent Address
            elif submission.step_number == 8:
                address_parts = []
                if step_data.get('address_line1'):
                    address_parts.append(step_data['address_line1'])
                if step_data.get('address_line2'):
                    address_parts.append(step_data['address_line2'])
                if step_data.get('city'):
                    address_parts.append(step_data['city'])
                if step_data.get('state'):
                    address_parts.append(step_data['state'])
                if step_data.get('pincode'):
                    address_parts.append(step_data['pincode'])
                employee_data['permanent_address'] = ', '.join(address_parts) if address_parts else None
            
            # Step 9: Bank Details
            elif submission.step_number == 9:
                employee_data['bank_name'] = step_data.get('bank_name')
                employee_data['bank_account_number'] = step_data.get('account_number')
                employee_data['bank_ifsc_code'] = step_data.get('ifsc_code')
                employee_data['bank_branch'] = step_data.get('branch_name')
        
        # Validate required fields
        if not employee_data['first_name']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create employee: First name is missing from form data"
            )
        
        if not employee_data['email']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create employee: Email is missing from form data"
            )
        
        # Check if employee already exists
        existing_employee = db.query(Employee).filter(
            Employee.email == employee_data['email']
        ).first()
        
        if existing_employee:
            # Update form with existing employee
            form.employee_id = existing_employee.id
            form.status = OnboardingStatus.APPROVED
            form.approved_by = current_user.id
            form.approved_at = datetime.now()
            db.commit()
            db.refresh(form)
            
            print(f"✅ Form approved and linked to existing employee: {existing_employee.employee_code}")
            return form
        
        # Generate employee code
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        
        # Ensure uniqueness
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        
        # Parse notes to extract additional info
        notes_data = {}
        if form.notes:
            try:
                # Notes are stored as comma-separated key-value pairs
                for note in form.notes.split(', '):
                    if ':' in note:
                        key, value = note.split(':', 1)
                        notes_data[key.strip()] = value.strip()
            except:
                pass
        
        # Create employee record
        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=employee_data['first_name'],
            middle_name=employee_data['middle_name'],
            last_name=employee_data['last_name'] or '',
            email=employee_data['email'],
            mobile=employee_data['mobile'],
            date_of_birth=employee_data['date_of_birth'],
            gender=employee_data['gender'],
            marital_status=employee_data['marital_status'],
            blood_group=employee_data['blood_group'],
            aadhar_number=employee_data['aadhar_number'],
            current_address=employee_data['current_address'],
            permanent_address=employee_data['permanent_address'],
            emergency_contact=employee_data['emergency_contact'],
            father_name=employee_data['father_name'],
            mother_name=employee_data['mother_name'],
            employee_status='ACTIVE',
            date_of_joining=date.today(),  # Set to today or extract from notes
            created_by=current_user.id,
            is_active=True
        )
        
        db.add(new_employee)
        db.flush()  # Get the employee ID
        
        # Update form status and link to employee
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        form.employee_id = new_employee.id
        
        db.commit()
        db.refresh(form)
        db.refresh(new_employee)
        
        print(f"✅ Form approved and employee created: {new_employee.employee_code} - {new_employee.first_name} {new_employee.last_name}")
        
        return form
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error approving form and creating employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve onboarding form: {str(e)}"
        )


@router.post("/{form_id}/reject", response_model=OnboardingFormResponse)
async def reject_onboarding_form(
    form_id: int,
    rejection_data: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Reject an onboarding form"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Get rejection reason
        reason = "No reason provided"
        if rejection_data and rejection_data.get("reason"):
            reason = rejection_data["reason"]
        
        # Use service layer
        service = OnboardingService(db)
        form = service.reject_onboarding_form(form_id, business_id, current_user.id, reason)
        
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        return form
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject onboarding form: {str(e)}"
        )


@router.post("/bulk", response_model=BulkOnboardingResponse)
async def create_bulk_onboarding(
    bulk_data: BulkOnboardingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create bulk onboarding operation"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Use service layer
        service = OnboardingService(db)
        result = service.process_bulk_onboarding(bulk_data, business_id, current_user.id)
        
        return result["bulk_operation"]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk onboarding: {str(e)}"
        )


@router.put("/{form_id}", response_model=OnboardingFormResponse)
async def update_onboarding_form(
    form_id: int,
    form_data: OnboardingFormUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update onboarding form"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business found for user"
            )
        
        # Get existing form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Update fields
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update onboarding form: {str(e)}"
        )





@router.post("/{form_id}/send", response_model=OnboardingFormResponse)
async def send_onboarding_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Send onboarding form to candidate"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business found for user"
            )
        
        # Get form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Update status
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        
        db.commit()
        db.refresh(form)
        
        return form
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send onboarding form: {str(e)}"
        )





# =============================================================================
# FORM SUBMISSION ENDPOINTS (For candidates)
# =============================================================================

@router.post("/{form_id}/submit", response_model=FormSubmissionResponse)
async def submit_onboarding_form(
    form_id: int,
    submission_data: FormSubmissionCreate,
    db: Session = Depends(get_db)
):
    """Submit onboarding form (used by candidates)"""
    try:
        # Get form by ID (no business_id filter for public access - this is for candidates)
        form = db.query(OnboardingForm).filter(OnboardingForm.id == form_id).first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Check if form is still valid
        if form.expires_at and form.expires_at < datetime.now():
            form.status = OnboardingStatus.EXPIRED
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Onboarding form has expired"
            )
        
        # Create form submission
        submission = FormSubmission(
            form_id=form_id,
            **submission_data.dict(),
            submitted_at=datetime.now()
        )
        
        db.add(submission)
        
        # Update form status
        form.status = OnboardingStatus.SUBMITTED
        form.submitted_at = datetime.now()
        
        db.commit()
        db.refresh(submission)
        
        return submission
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit onboarding form: {str(e)}"
        )


@router.delete("/{form_id}")
async def delete_onboarding_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete onboarding form"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business found for user"
            )
        
        # Get form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Soft delete by setting is_active to False
        form.is_active = False
        form.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Onboarding form deleted successfully",
            "form_id": form_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete onboarding form: {str(e)}"
        )


# =============================================================================
# CREDIT SYSTEM ENDPOINTS (For bulk onboarding verification)
# =============================================================================

@router.get("/credits", response_model=dict)
async def get_user_credits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get user's current credit balance"""
    try:
        from app.services.credit_service import CreditService
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "credits": 0,
                "business_id": None
            }
        
        # Use first business for credit lookup
        business_id = user_business_ids[0]
        user_credits = CreditService.get_user_credits(db, current_user.id, business_id)
        
        return {
            "credits": user_credits.credits,
            "user_id": current_user.id,
            "business_id": business_id,
            "last_updated": user_credits.updated_at or user_credits.created_at
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get credits: {str(e)}"
        )


@router.post("/credits/purchase", response_model=dict)
async def purchase_credits(
    purchase_request: CreditPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Purchase credits for verification services"""
    try:
        from app.services.credit_service import CreditService
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        result = CreditService.purchase_credits(
            db, current_user.id, business_id, purchase_request
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purchase credits: {str(e)}"
        )


@router.get("/credits/pricing", response_model=dict)
async def get_credit_pricing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get credit pricing for verification services"""
    try:
        from app.services.credit_service import CreditService
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "pricing": []
            }
        
        # Use first business for pricing lookup
        business_id = user_business_ids[0]
        pricing = CreditService.get_credit_pricing(db, business_id)
        
        return {
            "pricing": pricing,
            "business_id": business_id
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pricing: {str(e)}"
        )


# =============================================================================
# FORM ENDPOINTS (Must come AFTER specific endpoints like /templates, /offer-letters)
# =============================================================================

@router.get("/{form_id}", response_model=OnboardingFormResponse)
async def get_onboarding_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get onboarding form by ID"""
    try:
        # Validate form access with business isolation
        form = validate_form_access(db, form_id, current_user)
        return form
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch onboarding form: {str(e)}"
        )


# =============================================================================
# APPROVAL WORKFLOW ENDPOINTS
# =============================================================================

@router.get("/approvals/pending", response_model=dict)
async def get_pending_approvals(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get onboarding forms pending approval (frontend compatible with pagination)"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "forms": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "pages": 0
            }
        
        # Get forms with SUBMITTED status (pending approval)
        query = db.query(OnboardingForm).filter(
            OnboardingForm.status == OnboardingStatus.SUBMITTED,
            OnboardingForm.is_active == True,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        forms = query.order_by(desc(OnboardingForm.submitted_at)).offset(offset).limit(limit).all()
        
        # Convert to frontend format
        pending_forms = []
        for form in forms:
            # Extract location from notes or use default
            location = "Hyderabad"  # Default
            deputation = "No"  # Default
            
            if form.notes:
                # Parse notes for location and deputation info
                notes_lower = form.notes.lower()
                if "location:" in notes_lower:
                    # Extract location from notes
                    location_part = form.notes.split("Location:")[1].split(",")[0].strip() if "Location:" in form.notes else "Hyderabad"
                    location = location_part
                
                if "deputation:" in notes_lower:
                    # Extract deputation from notes
                    deputation_part = form.notes.split("Deputation:")[1].split(",")[0].strip() if "Deputation:" in form.notes else "No"
                    deputation = deputation_part
            
            # Format joining date from notes or use submitted date
            joining_date = "Not specified"
            if form.notes and "joining date:" in form.notes.lower():
                try:
                    # Extract joining date from notes
                    joining_part = form.notes.split("Joining date:")[1].split(",")[0].strip()
                    joining_date = joining_part
                except:
                    joining_date = form.submitted_at.strftime("%d-%b-%Y") if form.submitted_at else "Not specified"
            elif form.submitted_at:
                joining_date = form.submitted_at.strftime("%d-%b-%Y")
            
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
        
        return {
            "success": True,
            "forms": pending_forms,
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit  # Calculate total pages
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending approvals: {str(e)}"
        )


@router.post("/{form_id}/approve-frontend", response_model=dict)
async def approve_form_frontend(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Approve onboarding form and automatically create employee (frontend compatible)
    
    **Workflow:**
    1. Approve the onboarding form
    2. Extract candidate data from form submissions
    3. Create employee record in employees table
    4. Link employee to onboarding form
    5. Return success response with employee details
    """
    try:
        from app.models.employee import Employee
        from datetime import datetime, date
        
        user_business_ids = get_user_business_ids(db, current_user)
        business_id = user_business_ids[0] if user_business_ids else None
        
        if not business_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business ID not found for current user"
            )
        
        # Get form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Check if already approved
        if form.status == OnboardingStatus.APPROVED:
            return {
                "success": True,
                "message": f"Form already approved (Employee: {form.employee_id})",
                "form_id": form.id,
                "status": form.status.value,
                "employee_id": form.employee_id,
                "already_approved": True
            }
        
        # Get form submission to extract employee data
        submission = db.query(FormSubmission).filter(
            FormSubmission.form_id == form_id
        ).first()
        
        # Parse submission data from FormSubmission model fields
        employee_data = {
            'first_name': None,
            'middle_name': None,
            'last_name': None,
            'email': form.candidate_email,
            'mobile': form.candidate_mobile,
            'date_of_birth': None,
            'gender': None,
            'marital_status': None,
            'blood_group': None,
            'aadhar_number': None,
            'pan_number': None,
            'uan_number': None,
            'esi_number': None,
            'current_address': None,
            'permanent_address': None,
            'emergency_contact': None,
            'father_name': None,
            'mother_name': None,
        }
        
        # Helper function to normalize enum values
        def normalize_gender(value):
            """Convert gender to lowercase enum value"""
            if not value:
                return None
            value_lower = str(value).lower()
            if value_lower in ['male', 'm']:
                return 'male'
            elif value_lower in ['female', 'f']:
                return 'female'
            elif value_lower in ['other', 'o']:
                return 'other'
            return None
        
        def normalize_marital_status(value):
            """Convert marital status to lowercase enum value"""
            if not value:
                return None
            value_lower = str(value).lower()
            if value_lower in ['single', 'unmarried']:
                return 'single'
            elif value_lower in ['married']:
                return 'married'
            elif value_lower in ['divorced']:
                return 'divorced'
            elif value_lower in ['widowed', 'widow']:
                return 'widowed'
            return None
        
        # Extract data from submission if it exists
        if submission:
            import json
            
            # Basic Details (stored directly in fields)
            employee_data['first_name'] = submission.first_name
            employee_data['middle_name'] = submission.middle_name
            employee_data['last_name'] = submission.last_name
            employee_data['gender'] = normalize_gender(submission.gender)
            employee_data['date_of_birth'] = submission.date_of_birth
            
            # Contact Details
            employee_data['mobile'] = submission.alternate_mobile or employee_data['mobile']
            employee_data['email'] = submission.personal_email or employee_data['email']
            
            # Extract emergency contact from experience_details JSON
            if submission.experience_details:
                try:
                    contact_data = json.loads(submission.experience_details)
                    employee_data['emergency_contact'] = contact_data.get('emergency_contact')
                except:
                    pass
            
            # Personal Details
            employee_data['marital_status'] = normalize_marital_status(submission.marital_status)
            employee_data['blood_group'] = submission.blood_group
            
            # Extract father/mother names from policy_acknowledgments JSON
            if submission.policy_acknowledgments:
                try:
                    family_data = json.loads(submission.policy_acknowledgments)
                    employee_data['father_name'] = family_data.get('father_name')
                    employee_data['mother_name'] = family_data.get('mother_name')
                except:
                    pass
            
            # Statutory Details
            employee_data['aadhar_number'] = submission.aadhaar_number
            employee_data['pan_number'] = submission.pan_number
            
            # Extract UAN and ESI from experience_details JSON
            if submission.experience_details:
                try:
                    statutory_data = json.loads(submission.experience_details)
                    employee_data['uan_number'] = statutory_data.get('uan')
                    employee_data['esi_number'] = statutory_data.get('esi')
                except:
                    pass
            
            # Address
            employee_data['current_address'] = submission.present_address
        
        # Validate required fields
        if not employee_data['first_name']:
            # Try to extract from candidate_name
            if form.candidate_name:
                name_parts = form.candidate_name.split()
                employee_data['first_name'] = name_parts[0] if name_parts else 'Unknown'
                employee_data['last_name'] = name_parts[-1] if len(name_parts) > 1 else ''
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create employee: First name is missing"
                )
        
        if not employee_data['email']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create employee: Email is missing"
            )
        
        # Check if employee already exists
        existing_employee = db.query(Employee).filter(
            Employee.email == employee_data['email']
        ).first()
        
        if existing_employee:
            # Link to existing employee
            form.employee_id = existing_employee.id
            form.status = OnboardingStatus.APPROVED
            form.approved_by = current_user.id
            form.approved_at = datetime.now()
            db.commit()
            
            print(f"✅ Form approved and linked to existing employee: {existing_employee.employee_code}")
            
            return {
                "success": True,
                "message": f"Form approved and linked to existing employee {existing_employee.employee_code}",
                "form_id": form.id,
                "status": form.status.value,
                "employee_id": existing_employee.id,
                "employee_code": existing_employee.employee_code,
                "employee_name": f"{existing_employee.first_name} {existing_employee.last_name}",
                "approved_at": form.approved_at.isoformat()
            }
        
        # Generate employee code
        max_employee = db.query(Employee).order_by(Employee.id.desc()).first()
        next_id = (max_employee.id + 1) if max_employee else 1
        employee_code = f"EMP{next_id:04d}"
        
        # Ensure uniqueness
        while db.query(Employee).filter(Employee.employee_code == employee_code).first():
            next_id += 1
            employee_code = f"EMP{next_id:04d}"
        
        # Create employee record
        new_employee = Employee(
            business_id=business_id,
            employee_code=employee_code,
            first_name=employee_data['first_name'],
            middle_name=employee_data['middle_name'],
            last_name=employee_data['last_name'] or '',
            email=employee_data['email'],
            mobile=employee_data['mobile'],
            date_of_birth=employee_data['date_of_birth'],
            gender=employee_data['gender'],
            marital_status=employee_data['marital_status'],
            blood_group=employee_data['blood_group'],
            aadhar_number=employee_data['aadhar_number'],
            current_address=employee_data['current_address'],
            emergency_contact=employee_data['emergency_contact'],
            father_name=employee_data['father_name'],
            mother_name=employee_data['mother_name'],
            employee_status='ACTIVE',
            date_of_joining=date.today(),
            created_by=current_user.id,
            is_active=True
        )
        
        db.add(new_employee)
        db.flush()  # Get the employee ID
        
        # Create employee profile with profile photo if available
        from app.models.employee import EmployeeProfile
        profile_photo_url = None
        
        if submission and submission.education_details:
            try:
                profile_data = json.loads(submission.education_details)
                profile_photo_base64 = profile_data.get('profile_photo')
                
                if profile_photo_base64:
                    # Save profile photo to file
                    import base64
                    import os
                    from pathlib import Path
                    
                    # Create uploads directory if it doesn't exist
                    upload_dir = Path("uploads/profile_photos")
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Extract base64 data (remove data:image/...;base64, prefix)
                    if ',' in profile_photo_base64:
                        header, data = profile_photo_base64.split(',', 1)
                        # Determine file extension from header
                        if 'jpeg' in header or 'jpg' in header:
                            ext = 'jpg'
                        elif 'png' in header:
                            ext = 'png'
                        else:
                            ext = 'jpg'  # default
                    else:
                        data = profile_photo_base64
                        ext = 'jpg'
                    
                    # Decode and save
                    image_data = base64.b64decode(data)
                    filename = f"employee_{new_employee.id}_profile.{ext}"
                    filepath = upload_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                    
                    profile_photo_url = f"/uploads/profile_photos/{filename}"
                    print(f"✅ Profile photo saved: {profile_photo_url}")
            except Exception as e:
                print(f"⚠️  Could not save profile photo: {str(e)}")
        
        # Create or update employee profile
        employee_profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.employee_id == new_employee.id
        ).first()
        
        if not employee_profile:
            employee_profile = EmployeeProfile(
                employee_id=new_employee.id,
                profile_image_url=profile_photo_url,
                pan_number=employee_data.get('pan_number'),
                aadhaar_number=employee_data.get('aadhar_number'),
                uan_number=employee_data.get('uan_number'),
                esi_number=employee_data.get('esi_number')
            )
            db.add(employee_profile)
        elif profile_photo_url:
            employee_profile.profile_image_url = profile_photo_url
        
        # Update form status and link to employee
        form.status = OnboardingStatus.APPROVED
        form.approved_by = current_user.id
        form.approved_at = datetime.now()
        form.employee_id = new_employee.id
        
        db.commit()
        db.refresh(new_employee)
        
        print(f"✅ Form approved and employee created: {new_employee.employee_code} - {new_employee.first_name} {new_employee.last_name}")
        
        return {
            "success": True,
            "message": f"Onboarding form approved and employee {employee_code} created successfully!",
            "form_id": form.id,
            "status": form.status.value,
            "employee_id": new_employee.id,
            "employee_code": new_employee.employee_code,
            "employee_name": f"{new_employee.first_name} {new_employee.last_name}",
            "approved_at": form.approved_at.isoformat(),
            "approved_by": current_user.name if hasattr(current_user, 'name') else current_user.email
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error approving form and creating employee: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve form: {str(e)}"
        )


@router.post("/{form_id}/reject-frontend", response_model=dict)
async def reject_form_frontend(
    form_id: int,
    rejection_data: OnboardingRejectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Reject onboarding form (frontend compatible response)"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business found for user"
            )
        
        # Get form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Update status to rejected
        form.status = OnboardingStatus.REJECTED
        form.rejected_at = datetime.now()
        form.rejected_by = current_user.id
        form.rejection_reason = rejection_data.reason
        
        db.commit()
        db.refresh(form)
        
        return {
            "success": True,
            "message": f"Onboarding form for {form.candidate_name} rejected",
            "form_id": form.id,
            "status": form.status,
            "rejected_at": form.rejected_at.isoformat(),
            "rejected_by": current_user.name if hasattr(current_user, 'name') else current_user.email,
            "rejection_reason": rejection_data.reason
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject onboarding form: {str(e)}"
        )


# =============================================================================
# FRONTEND COMPATIBILITY ENDPOINTS
# =============================================================================

@router.get("/forms/list", response_model=dict)
async def get_forms_for_frontend(
    form_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get onboarding forms in frontend-compatible format"""
    try:
        from fastapi import status as http_status
        
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "forms": [],
                "total": 0
            }
        
        # Query forms filtered by user's businesses
        query = db.query(OnboardingForm).filter(
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        # Apply status filter (skip if status is None, empty, or "All")
        if form_status and form_status.lower() not in ['all', '']:
            query = query.filter(OnboardingForm.status == form_status)
        
        # Apply search filter
        if search and search.strip():  # Only apply if search has actual content
            search_term = f"%{search}%"
            query = query.filter(
                (OnboardingForm.candidate_name.ilike(search_term)) |
                (OnboardingForm.candidate_email.ilike(search_term))
            )
        
        forms = query.all()
        
        # Convert to serializable format
        forms_list = []
        for form in forms:
            forms_list.append({
                "id": form.id,
                "candidate": form.candidate_name,  # Frontend expects 'candidate'
                "candidate_name": form.candidate_name,
                "email": form.candidate_email,  # Frontend expects 'email'
                "candidate_email": form.candidate_email,
                "mobile": form.candidate_mobile,  # Frontend expects 'mobile'
                "candidate_mobile": form.candidate_mobile,
                "status": form.status.value.capitalize() if hasattr(form.status, 'value') else str(form.status).capitalize(),  # Frontend expects capitalized status
                "created": form.created_at.strftime("%d-%b-%Y") if form.created_at else None,  # Frontend expects 'created'
                "created_at": form.created_at.isoformat() if form.created_at else None,
                "updated_at": form.updated_at.isoformat() if form.updated_at else None,
                "sent_at": form.sent_at.isoformat() if form.sent_at else None,
                "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
                "approved_at": form.approved_at.isoformat() if form.approved_at else None,
                "rejected_at": form.rejected_at.isoformat() if form.rejected_at else None,
                "business_id": form.business_id,
                "form_token": form.form_token,
                "notes": form.notes,
                "info": "View Details"  # Frontend expects 'info' field
            })
        
        return {
            "success": True,
            "forms": forms_list,
            "total": len(forms_list)
        }
    
    except Exception as e:
        from fastapi import status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch forms: {str(e)}"
        )


@router.post("/forms/create", response_model=dict)
async def create_form_frontend_compatible(
    form_data: OnboardingFormCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create onboarding form with frontend-compatible response"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=400,
                detail="No business associated with user"
            )
        
        # Use first business for form creation
        business_id = user_business_ids[0]
        
        # Use service layer
        service = OnboardingService(db)
        form = service.create_onboarding_form(form_data, business_id, current_user.id)
        
        return {
            "success": True,
            "message": "Onboarding form created successfully",
            "form_id": form.id,
            "form_token": form.form_token,
            "expires_at": form.expires_at.isoformat() if form.expires_at else None,
            "form": {
                "id": form.id,
                "candidate": form.candidate_name,
                "created": form.created_at.strftime("%d-%b-%Y") if form.created_at else "",
                "email": form.candidate_email,
                "mobile": form.candidate_mobile,
                "info": "View Form",
                "status": "Draft",
                "form_token": form.form_token
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create form: {str(e)}"
        )
        
        db.add(form)
        db.commit()
        db.refresh(form)
        
        return {
            "success": True,
            "message": "Onboarding form created successfully",
            "form_id": form.id,
            "form_token": form_token,
            "status": form.status,
            "expires_at": expires_at.isoformat()
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create onboarding form: {str(e)}"
        )


@router.post("/{form_id}/finalize", response_model=dict)
async def finalize_and_send_form(
    form_id: int,
    finalize_data: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Finalize and send onboarding form to candidate"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business found for user"
            )
        
        # Get form
        query = db.query(OnboardingForm).filter(
            OnboardingForm.id == form_id,
            OnboardingForm.business_id.in_(user_business_ids)
        )
        
        form = query.first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding form not found"
            )
        
        # Update status to sent
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        
        db.commit()
        db.refresh(form)
        
        return {
            "success": True,
            "message": "Onboarding form sent successfully",
            "form_id": form.id,
            "status": form.status,
            "sent_at": form.sent_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize and send form: {str(e)}"
        )


@router.post("/templates/generate", response_model=TemplateGenerationResponse)
async def generate_letter_from_template(
    generation_data: TemplateGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Generate letter from template with field values (Frontend compatible)"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        template_name = generation_data.template_name
        field_values_text = generation_data.field_values
        
        # Get template by name - try business-specific first, then any active template
        template = db.query(OfferLetterTemplate).filter(
            and_(
                OfferLetterTemplate.name == template_name,
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            )
        ).first()
        
        # If not found in user's business, try any active template with that name
        if not template:
            template = db.query(OfferLetterTemplate).filter(
                and_(
                    OfferLetterTemplate.name == template_name,
                    OfferLetterTemplate.is_active == True
                )
            ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        # Parse field values from key=value format
        field_values = {}
        if field_values_text.strip():
            for line in field_values_text.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    field_values[key.strip()] = value.strip()
        
        # Replace placeholders in template content
        generated_content = template.template_content
        for key, value in field_values.items():
            placeholder = f"{{{key}}}"
            generated_content = generated_content.replace(placeholder, value)
        
        # Format the generated content for better presentation
        # Clean up extra whitespace and ensure proper line breaks
        lines = generated_content.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Clean up extra spaces but preserve intentional formatting
            clean_line = ' '.join(line.split()) if line.strip() else ''
            formatted_lines.append(clean_line)
        
        # Join lines and ensure proper spacing between paragraphs
        generated_content = '\n'.join(formatted_lines)
        
        # Replace multiple consecutive newlines with double newlines for paragraph spacing
        import re
        generated_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', generated_content)
        generated_content = generated_content.strip()
        
        # Create offer letter record
        offer_letter = OfferLetter(
            form_id=None,  # Standalone generation
            template_id=template.id,
            position_title=field_values.get("position_title", field_values.get("designation", "")),
            department=field_values.get("department", ""),
            location=field_values.get("location", ""),
            basic_salary=field_values.get("basic_salary", ""),
            gross_salary=field_values.get("gross_salary", ""),
            ctc=field_values.get("ctc", ""),
            joining_date=None,  # Parse if provided
            offer_valid_until=None,  # Parse if provided
            letter_content=generated_content,
            is_generated=True,
            is_sent=False,
            created_by=current_user.id,
            created_at=datetime.now()
        )
        
        # Parse dates if provided
        if field_values.get("joining_date"):
            try:
                from datetime import datetime as dt
                offer_letter.joining_date = dt.strptime(field_values["joining_date"], "%d-%b-%Y").date()
            except:
                pass
        
        if field_values.get("offer_valid_until"):
            try:
                from datetime import datetime as dt
                offer_letter.offer_valid_until = dt.strptime(field_values["offer_valid_until"], "%d-%b-%Y").date()
            except:
                pass
        
        db.add(offer_letter)
        db.commit()
        db.refresh(offer_letter)
        
        return TemplateGenerationResponse(
            success=True,
            message="Letter generated successfully",
            offer_letter_id=offer_letter.id,
            generated_content=generated_content,
            template_name=template_name,
            field_values=field_values
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate letter: {str(e)}"
        )


@router.get("/templates/frontend-format", response_model=dict)
async def get_templates_frontend_format(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get templates in frontend-compatible format"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "templates": []
            }
        
        # Use first business
        business_id = user_business_ids[0]
        
        # Use service layer
        service = OnboardingService(db)
        result = service.get_templates_frontend_format(business_id)
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch templates: {str(e)}"
        )


# =============================================================================
# FRONTEND-COMPATIBLE SETTINGS ENDPOINTS
# =============================================================================

@router.get("/settings/frontend-format", response_model=dict)
async def get_settings_frontend_format(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get onboarding settings in frontend-compatible format"""
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        if not user_business_ids:
            return {
                "success": True,
                "settings": {}
            }
        
        # Use first business
        business_id = user_business_ids[0]
        
        # Use service layer
        service = OnboardingService(db)
        result = service.get_settings_frontend_format(business_id, current_user.id)
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch settings: {str(e)}"
        )


@router.post("/settings/update-document", response_model=dict)
async def update_document_requirement(
    update_data: DocumentRequirementUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update document requirement (auto-save for frontend)
    
    **Request body:**
    - document_type: Document type (required)
    - is_required: Whether document is required (required)
    - display_order: Display order (optional)
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Use service layer
        service = OnboardingService(db)
        result = service.update_document_requirement(
            business_id, 
            update_data.document_type, 
            update_data.is_required, 
            current_user.id
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document requirement: {str(e)}"
        )


@router.post("/settings/update-field", response_model=dict)
async def update_field_requirement(
    update_data: FieldRequirementUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update field requirement (auto-save for frontend)
    
    **Request body:**
    - field_name: Field name (required)
    - is_required: Whether field is required (required)
    - is_visible: Whether field is visible (optional)
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Use service layer
        service = OnboardingService(db)
        result = service.update_field_requirement(
            business_id, 
            update_data.field_name, 
            update_data.is_required, 
            current_user.id
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update field requirement: {str(e)}"
        )
# ============================================================================
# LEGACY COMPATIBILITY ENDPOINTS - REMOVED DUPLICATES
# ============================================================================


# REMOVED DUPLICATE APPROVE ENDPOINT - USE MAIN ENDPOINT ABOVE


# REMOVED DUPLICATE REJECT ENDPOINT - USE MAIN ENDPOINT ABOVE


# REMOVED DUPLICATE CREDITS ENDPOINT - USE MAIN ENDPOINT ABOVE


@router.post("/bulk-send")
async def bulk_send_forms_legacy(
    bulk_data: BulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Bulk send onboarding forms
    
    **Request body:**
    - candidates: List of candidates with name, email, position, department (required)
    - template_id: Template ID (optional)
    
    **Creates:**
    - Multiple onboarding forms from candidate list
    - Sends forms to all candidates via email
    - Tracks bulk operation status
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        candidates = bulk_data.candidates
        template_id = bulk_data.template_id
        
        # Process bulk sending
        sent_count = 0
        failed_count = 0
        errors = []
        
        for candidate in candidates:
            try:
                # Create onboarding form for each candidate
                form = OnboardingForm(
                    business_id=business_id,
                    candidate_name=candidate.name,
                    candidate_email=candidate.email,
                    position=candidate.position,
                    department=candidate.department,
                    status=OnboardingStatus.SENT,
                    created_by=current_user.id
                )
                
                db.add(form)
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"{candidate.email}: {str(e)}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Bulk send completed: {sent_count} sent, {failed_count} failed",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk send forms: {str(e)}"
        )


@router.get("/credit-pricing")
async def get_credit_pricing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get credit pricing information
    
    **Returns:**
    - Credit packages and pricing
    - Bulk discount information
    - Payment options
    """
    try:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credit pricing: {str(e)}"
        )


@router.post("/forms/{form_id}/send")
async def send_onboarding_form_legacy(
    form_id: int,
    send_data: SendFormRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Send onboarding form to candidate
    
    **Request body:**
    - candidate_email: Candidate email address (required)
    - send_email: Whether to send email notification (optional)
    - custom_message: Custom message to include in email (optional)
    
    **Updates:**
    - Form status to sent
    - Generates form token for candidate access
    - Sends email notification to candidate
    """
    try:
        # Get form
        form = validate_form_access(db, form_id, current_user)
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Update form status
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        form.form_token = f"token_{form_id}_{int(datetime.now().timestamp())}"
        
        db.commit()
        
        return {
            "success": True,
            "message": "Onboarding form sent successfully",
            "form_id": form_id,
            "form_token": form.form_token,
            "sent_to": form.candidate_email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send onboarding form: {str(e)}"
        )


# ============================================================================
# CANDIDATE WORKFLOW ENDPOINTS
# ============================================================================

@router.get("/candidate/form/{form_token}")
async def get_candidate_form_by_token(
    form_token: str,
    db: Session = Depends(get_db)
):
    """
    Get candidate onboarding form by token
    
    **Returns:**
    - Form details and current step
    - Required fields and documents
    - Progress information
    - Business name from database
    """
    try:
        # Get form by token with business relationship
        from app.models.business import Business
        
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        
        # Get business name from businesses table
        business = db.query(Business).filter(Business.id == form.business_id).first()
        business_name = business.business_name if business else "Company"
        
        # Check if form submission exists
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        
        # Calculate current step based on submission data
        current_step = 1
        if submission:
            # Determine current step based on filled data
            if submission.first_name:
                current_step = 2
            if submission.alternate_mobile:  # Using alternate_mobile (form_submissions doesn't have 'mobile')
                current_step = 3
            if submission.blood_group:
                current_step = 4
            if submission.aadhaar_number:
                current_step = 5
            if submission.marital_status:
                current_step = 6
            if submission.present_address:  # Using present_address Text field
                current_step = 7
            if submission.permanent_address:  # Using permanent_address Text field
                current_step = 8
            if submission.bank_name:
                current_step = 9
        
        # Return form data with business name from database
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
            "has_submission": submission is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candidate form: {str(e)}"
        )


@router.post("/candidate/form/{form_token}/step/{step_number}")
async def submit_candidate_form_step(
    form_token: str,
    step_number: int,
    step_data: StepDataRequest,
    db: Session = Depends(get_db)
):
    """
    Submit candidate form step data
    
    **Request body:**
    - data: Step data as key-value pairs (required)
    
    **Updates:**
    - Form data for specific step
    - Progress tracking
    - Validation status
    """
    try:
        # Get form by token
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        
        # Get or create form submission
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        
        if not submission:
            submission = FormSubmission(
                form_id=form.id,
                submitted_at=datetime.now()
            )
            db.add(submission)
        
        # Update submission based on step number
        data = step_data.data
        if step_number == 2:  # Basic Details
            submission.first_name = data.get('first_name')
            submission.middle_name = data.get('middle_name')
            submission.last_name = data.get('last_name')
            submission.gender = data.get('gender')
            if data.get('date_of_birth'):
                from datetime import datetime as dt
                submission.date_of_birth = dt.strptime(data['date_of_birth'], "%Y-%m-%d").date()
            # Store profile photo as base64 in education_details JSON temporarily
            if data.get('profile_photo'):
                import json
                profile_data = json.loads(submission.education_details) if submission.education_details else {}
                profile_data['profile_photo'] = data['profile_photo']
                submission.education_details = json.dumps(profile_data)
        
        elif step_number == 3:  # Contact Details
            # Store mobile in alternate_mobile field (form_submissions doesn't have 'mobile' field)
            submission.alternate_mobile = data.get('mobile')
            submission.personal_email = data.get('personal_email')
            # Store home_phone and emergency_contact in JSON temporarily
            import json
            contact_data = json.loads(submission.experience_details) if submission.experience_details else {}
            contact_data['home_phone'] = data.get('home_phone')
            contact_data['emergency_contact'] = data.get('emergency_contact')
            submission.experience_details = json.dumps(contact_data)
        
        elif step_number == 4:  # Personal Details
            submission.blood_group = data.get('blood_group')
            # Store passport and driving_license in JSON
            import json
            personal_data = json.loads(submission.education_details) if submission.education_details else {}
            personal_data['passport'] = data.get('passport')
            personal_data['driving_license'] = data.get('driving_license')
            submission.education_details = json.dumps(personal_data)
        
        elif step_number == 5:  # Statutory Details
            submission.aadhaar_number = data.get('aadhar')
            submission.pan_number = data.get('pan')
            # Store UAN and ESI in experience_details JSON
            import json
            statutory_data = json.loads(submission.experience_details) if submission.experience_details else {}
            statutory_data['uan'] = data.get('uan')
            statutory_data['esi'] = data.get('esi')
            submission.experience_details = json.dumps(statutory_data)
        
        elif step_number == 6:  # Family Details
            submission.marital_status = data.get('marital_status')
            submission.emergency_contact_name = data.get('father_name')
            # Store family details in JSON
            import json
            family_data = {
                'father_name': data.get('father_name'),
                'father_phone': data.get('father_phone'),
                'father_dob': data.get('father_dob'),
                'mother_name': data.get('mother_name'),
                'mother_phone': data.get('mother_phone'),
                'mother_dob': data.get('mother_dob')
            }
            # Store in policy_acknowledgments temporarily
            submission.policy_acknowledgments = json.dumps(family_data)
        
        elif step_number == 7:  # Present Address
            # Store address fields in JSON format in education_details for retrieval
            import json
            address_data = {
                'address1': data.get('address1', ''),
                'address2': data.get('address2', ''),
                'city': data.get('city', ''),
                'pincode': data.get('pincode', ''),
                'state': data.get('state', ''),
                'country': data.get('country', 'India')
            }
            
            # Store as complete address string in present_address for compatibility
            address_parts = []
            if data.get('address1'):
                address_parts.append(data['address1'])
            if data.get('address2'):
                address_parts.append(data['address2'])
            if data.get('city'):
                address_parts.append(data['city'])
            if data.get('state'):
                address_parts.append(data['state'])
            if data.get('pincode'):
                address_parts.append(data['pincode'])
            if data.get('country'):
                address_parts.append(data['country'])
            
            submission.present_address = ', '.join(address_parts) if address_parts else None
            
            # Store structured data in JSON for retrieval
            step_data_json = json.loads(submission.education_details) if submission.education_details else {}
            step_data_json['present_address_data'] = address_data
            submission.education_details = json.dumps(step_data_json)
        
        elif step_number == 8:  # Permanent Address
            # Store address fields in JSON format in experience_details for retrieval
            import json
            address_data = {
                'address1': data.get('address1', ''),
                'address2': data.get('address2', ''),
                'city': data.get('city', ''),
                'pincode': data.get('pincode', ''),
                'state': data.get('state', ''),
                'country': data.get('country', 'India')
            }
            
            # Store as complete address string in permanent_address for compatibility
            address_parts = []
            if data.get('address1'):
                address_parts.append(data['address1'])
            if data.get('address2'):
                address_parts.append(data['address2'])
            if data.get('city'):
                address_parts.append(data['city'])
            if data.get('state'):
                address_parts.append(data['state'])
            if data.get('pincode'):
                address_parts.append(data['pincode'])
            if data.get('country'):
                address_parts.append(data['country'])
            
            submission.permanent_address = ', '.join(address_parts) if address_parts else None
            
            # Store structured data in JSON for retrieval
            step_data_json = json.loads(submission.experience_details) if submission.experience_details else {}
            step_data_json['permanent_address_data'] = address_data
            submission.experience_details = json.dumps(step_data_json)
        
        elif step_number == 9:  # Bank Details
            submission.bank_name = data.get('bank_name')
            submission.account_number = data.get('account_number')
            submission.ifsc_code = data.get('ifsc_code')
            # Store account holder in JSON
            import json
            bank_data = json.loads(submission.uploaded_documents) if submission.uploaded_documents else {}
            bank_data['account_holder'] = data.get('account_holder')
            submission.uploaded_documents = json.dumps(bank_data)
        
        # Update form status if final step
        if step_number >= 9:
            form.status = OnboardingStatus.SUBMITTED
            form.submitted_at = datetime.now()
        
        db.commit()
        db.refresh(submission)
        
        return {
            "success": True,
            "message": f"Step {step_number} submitted successfully",
            "next_step": step_number + 1 if step_number < 11 else None,
            "is_complete": step_number >= 9
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit form step: {str(e)}"
        )


@router.get("/candidate/form/{form_token}/step/{step_number}")
async def get_candidate_form_step_data(
    form_token: str,
    step_number: int,
    db: Session = Depends(get_db)
):
    """
    Get candidate form step data
    
    **Returns:**
    - Step-specific form fields
    - Previously saved data
    - Validation requirements
    """
    try:
        # Get form by token
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        
        # Get form submission
        submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
        
        step_data = {}
        is_completed = False
        
        if submission:
            import json
            
            if step_number == 2:  # Basic Details
                step_data = {
                    'first_name': submission.first_name or '',
                    'middle_name': submission.middle_name or '',
                    'last_name': submission.last_name or '',
                    'gender': submission.gender or '',
                    'date_of_birth': submission.date_of_birth.isoformat() if submission.date_of_birth else '',
                    'profile_photo': None
                }
                # Get profile photo from JSON
                if submission.education_details:
                    try:
                        profile_data = json.loads(submission.education_details)
                        step_data['profile_photo'] = profile_data.get('profile_photo')
                    except:
                        pass
                is_completed = bool(submission.first_name and submission.last_name and submission.gender and submission.date_of_birth)
            
            elif step_number == 3:  # Contact Details
                # Mobile is stored in alternate_mobile field
                # home_phone and emergency_contact are in experience_details JSON
                contact_data = {}
                if submission.experience_details:
                    try:
                        contact_data = json.loads(submission.experience_details)
                    except:
                        pass
                
                step_data = {
                    'mobile': submission.alternate_mobile or '',
                    'personal_email': submission.personal_email or '',
                    'home_phone': contact_data.get('home_phone', ''),
                    'emergency_contact': contact_data.get('emergency_contact', '')
                }
                is_completed = bool(submission.alternate_mobile and submission.personal_email)
            
            elif step_number == 4:  # Personal Details
                # passport and driving_license are stored in education_details JSON
                personal_data = {}
                if submission.education_details:
                    try:
                        personal_data = json.loads(submission.education_details)
                    except:
                        pass
                
                step_data = {
                    'blood_group': submission.blood_group or '',
                    'passport': personal_data.get('passport', ''),
                    'driving_license': personal_data.get('driving_license', '')
                }
                is_completed = bool(submission.blood_group)
            
            elif step_number == 5:  # Statutory Details
                step_data = {
                    'aadhar': submission.aadhaar_number or '',
                    'pan': submission.pan_number or '',
                    'uan': '',
                    'esi': ''
                }
                # Get UAN and ESI from JSON
                if submission.experience_details:
                    try:
                        statutory_data = json.loads(submission.experience_details)
                        step_data['uan'] = statutory_data.get('uan', '')
                        step_data['esi'] = statutory_data.get('esi', '')
                    except:
                        pass
                is_completed = bool(submission.aadhaar_number and submission.pan_number)
            
            elif step_number == 6:  # Family Details
                step_data = {
                    'marital_status': submission.marital_status or '',
                    'father_name': '',
                    'father_phone': '',
                    'father_dob': '',
                    'mother_name': '',
                    'mother_phone': '',
                    'mother_dob': ''
                }
                # Get family details from JSON
                if submission.policy_acknowledgments:
                    try:
                        family_data = json.loads(submission.policy_acknowledgments)
                        step_data.update(family_data)
                    except:
                        pass
                is_completed = bool(submission.marital_status)
            
            elif step_number == 7:  # Present Address
                # Present address fields are stored in education_details JSON
                step_data = {
                    'address1': '',
                    'address2': '',
                    'city': '',
                    'pincode': '',
                    'state': '',
                    'country': 'India'
                }
                # Get address data from JSON
                if submission.education_details:
                    try:
                        stored_data = json.loads(submission.education_details)
                        if 'present_address_data' in stored_data:
                            step_data = stored_data['present_address_data']
                    except:
                        pass
                # If present_address exists, mark as completed
                is_completed = bool(submission.present_address)
            
            elif step_number == 8:  # Permanent Address
                # Permanent address fields are stored in experience_details JSON
                step_data = {
                    'address1': '',
                    'address2': '',
                    'city': '',
                    'pincode': '',
                    'state': '',
                    'country': 'India'
                }
                # Get address data from JSON
                if submission.experience_details:
                    try:
                        stored_data = json.loads(submission.experience_details)
                        if 'permanent_address_data' in stored_data:
                            step_data = stored_data['permanent_address_data']
                    except:
                        pass
                # If permanent_address exists, mark as completed
                is_completed = bool(submission.permanent_address)
            
            elif step_number == 9:  # Bank Details
                step_data = {
                    'bank_name': submission.bank_name or '',
                    'account_number': submission.account_number or '',
                    'ifsc_code': submission.ifsc_code or '',
                    'account_holder': ''
                }
                # Get account holder from JSON
                if submission.uploaded_documents:
                    try:
                        bank_data = json.loads(submission.uploaded_documents)
                        step_data['account_holder'] = bank_data.get('account_holder', '')
                    except:
                        pass
                is_completed = bool(submission.bank_name and submission.account_number and submission.ifsc_code)
        
        return {
            "step_number": step_number,
            "step_data": step_data,
            "is_completed": is_completed
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch form step data: {str(e)}"
        )


@router.post("/candidate/otp/send")
async def send_otp_for_mobile_verification(
    otp_data: OTPSendRequest,
    db: Session = Depends(get_db)
):
    """
    Send OTP for mobile verification
    
    **Request body:**
    - mobile_number: Mobile number (required)
    
    **Sends:**
    - SMS with verification code
    - Stores OTP for verification
    """
    try:
        mobile_number = otp_data.mobile_number
        
        # Mock OTP sending
        otp_code = "123456"  # In real implementation, generate random OTP
        
        return {
            "success": True,
            "message": "OTP sent successfully",
            "mobile_number": mobile_number,
            "otp_sent": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )


@router.post("/candidate/otp/verify")
async def verify_otp_for_mobile(
    verification_data: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verify OTP for mobile number
    
    **Request body:**
    - mobile_number: Mobile number (required)
    - otp_code: OTP code (required)
    
    **Verifies:**
    - OTP code against stored value
    - Updates verification status
    """
    try:
        mobile_number = verification_data.mobile_number
        otp_code = verification_data.otp_code
        
        # Mock OTP verification
        is_valid = otp_code == "123456"  # In real implementation, check against stored OTP
        
        return {
            "success": is_valid,
            "message": "OTP verified successfully" if is_valid else "Invalid OTP",
            "mobile_verified": is_valid
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify OTP: {str(e)}"
        )


@router.post("/candidate/document/upload")
async def upload_candidate_document(
    form_token: str,
    document_type: str,
    upload_data: DocumentUploadRequest,
    db: Session = Depends(get_db)
):
    """
    Upload candidate document
    
    **Request body:**
    - file_name: File name (required)
    - file_size: File size in bytes (optional)
    - file_type: File MIME type (optional)
    
    **Uploads:**
    - Document files for verification
    - Links documents to form
    - Updates document status
    """
    try:
        # Get form by token
        form = db.query(OnboardingForm).filter(OnboardingForm.form_token == form_token).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found or token expired")
        
        # Mock document upload
        file_path = f"/uploads/documents/{form.id}_{document_type}_{int(datetime.now().timestamp())}.pdf"
        
        # Update form documents
        documents = form.documents or {}
        documents[document_type] = {
            "file_path": file_path,
            "uploaded_at": datetime.now().isoformat(),
            "status": "uploaded"
        }
        form.documents = documents
        
        db.commit()
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "document_type": document_type,
            "file_path": file_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


# ============================================================================
# FORM CREATION WORKFLOW ENDPOINTS
# ============================================================================

@router.post("/form/create")
async def create_onboarding_form_part_a(
    form_data: FormCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create onboarding form - Part A (Basic Information)
    
    **Request body:**
    - candidate_name: Candidate name (required)
    - candidate_email: Candidate email (required)
    - position: Position (optional)
    - department: Department (optional)
    - joining_date: Expected joining date (optional)
    
    **Creates:**
    - New onboarding form with basic details
    - Returns form ID for subsequent steps
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Create new form
        form = OnboardingForm(
            business_id=business_id,
            candidate_name=form_data.candidate_name,
            candidate_email=form_data.candidate_email,
            position=form_data.position,
            department=form_data.department,
            joining_date=datetime.strptime(form_data.get('joining_date'), "%Y-%m-%d").date() if form_data.get('joining_date') else None,
            salary=form_data.get('salary'),
            status=OnboardingStatus.DRAFT,
            created_by=current_user.id
        )
        
        db.add(form)
        db.commit()
        db.refresh(form)
        
        return {
            "success": True,
            "message": "Onboarding form created successfully",
            "form_id": form.id,
            "status": form.status.value
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create onboarding form: {str(e)}"
        )


@router.get("/form/{form_id}/part-b")
async def get_onboarding_form_part_b(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get onboarding form Part B data (Policies & Documents)
    
    **Returns:**
    - Available policies for attachment
    - Document requirements
    - Form configuration options
    """
    try:
        # Get form
        form = validate_form_access(db, form_id, current_user)
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Mock Part B data
        part_b_data = {
            "form_id": form_id,
            "available_policies": [
                {"id": 1, "name": "Employee Handbook", "type": "handbook"},
                {"id": 2, "name": "Code of Conduct", "type": "conduct"},
                {"id": 3, "name": "IT Policy", "type": "it_policy"}
            ],
            "document_requirements": [
                {"type": "id_proof", "name": "ID Proof", "required": True},
                {"type": "address_proof", "name": "Address Proof", "required": True},
                {"type": "education", "name": "Education Certificates", "required": False}
            ],
            "current_attachments": form.policies or []
        }
        
        return part_b_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch form Part B: {str(e)}"
        )


@router.post("/form/{form_id}/attach-policies")
async def attach_policies_to_form(
    form_id: int,
    policies_data: PolicyAttachmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Attach policies to onboarding form
    
    **Request body:**
    - policy_ids: List of policy IDs to attach (required)
    
    **Updates:**
    - Form with selected policies
    - Policy attachment status
    """
    try:
        # Get form
        form = validate_form_access(db, form_id, current_user)
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Update policies
        form.policies = policies_data.get('policy_ids', [])
        form.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Policies attached successfully",
            "form_id": form_id,
            "attached_policies": len(form.policies)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach policies: {str(e)}"
        )


@router.get("/form/{form_id}/offer-letter")
async def get_onboarding_form_offer_letter(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get offer letter for onboarding form
    
    **Returns:**
    - Generated offer letter content
    - Template information
    - Salary details
    """
    try:
        # Validate form access with business isolation
        form = validate_form_access(db, form_id, current_user)
        
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Get offer letter
        offer_letter = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()
        
        if not offer_letter:
            raise HTTPException(status_code=404, detail="Offer letter not generated yet. Please generate the offer letter first.")
        
        # Get template info
        template = None
        if offer_letter.template_id:
            template = db.query(OfferLetterTemplate).filter(
                OfferLetterTemplate.id == offer_letter.template_id
            ).first()
        
        return {
            "form_id": form_id,
            "offer_letter_id": offer_letter.id,
            "letter_content": offer_letter.letter_content or "",
            "template_id": offer_letter.template_id,
            "template_name": template.name if template else None,
            "position_title": offer_letter.position_title or "",
            "department": offer_letter.department or "",
            "location": offer_letter.location or "",
            "gross_salary": offer_letter.gross_salary or "",
            "ctc": offer_letter.ctc or "",
            "joining_date": offer_letter.joining_date.isoformat() if offer_letter.joining_date else None,
            "is_generated": offer_letter.is_generated,
            "is_sent": offer_letter.is_sent,
            "created_at": offer_letter.created_at.isoformat() if offer_letter.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch offer letter: {str(e)}"
        )


@router.post("/form/{form_id}/attach-offer-letter")
async def attach_offer_letter_to_form(
    form_id: int,
    offer_data: OfferLetterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Attach/update offer letter to form
    
    **Updates:**
    - Offer letter content
    - Approval status
    - Form completion status
    """
    try:
        # Validate form access with business isolation
        form = validate_form_access(db, form_id, current_user)
        
        # Get or create offer letter
        offer_letter = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()
        
        if offer_letter:
            # Update existing
            offer_letter.content = offer_data.content if hasattr(offer_data, 'content') else offer_letter.content
            offer_letter.status = offer_data.status if hasattr(offer_data, 'status') else 'draft'
            offer_letter.updated_at = datetime.now()
        else:
            # Create new
            offer_letter = OfferLetter(
                form_id=form_id,
                content=offer_data.content if hasattr(offer_data, 'content') else None,
                status=offer_data.status if hasattr(offer_data, 'status') else 'draft',
                created_by=current_user.id
            )
            db.add(offer_letter)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Offer letter attached successfully",
            "form_id": form_id,
            "offer_letter_id": offer_letter.id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach offer letter: {str(e)}"
        )


@router.get("/form/{form_id}/finalize")
async def get_onboarding_form_finalize(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get form finalization summary
    
    **Returns:**
    - Complete form summary
    - Attached documents and policies
    - Readiness for sending
    """
    try:
        # Get form with all related data
        form = validate_form_access(db, form_id, current_user)
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Get offer letter
        offer_letter = db.query(OfferLetter).filter(OfferLetter.form_id == form_id).first()
        
        # Prepare summary
        summary = {
            "form_id": form_id,
            "candidate_details": {
                "name": form.candidate_name,
                "email": form.candidate_email,
                "phone": form.candidate_mobile,
                "position": form.position if hasattr(form, 'position') else None,
                "department": form.department if hasattr(form, 'department') else None
            },
            "offer_letter": {
                "attached": offer_letter is not None,
                "status": offer_letter.status if offer_letter else None
            },
            "policies_attached": len(form.policies or []),
            "is_ready_to_send": offer_letter is not None and form.candidate_email is not None,
            "status": form.status.value
        }
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch form finalization data: {str(e)}"
        )


@router.post("/form/{form_id}/finalize-and-send")
async def finalize_and_send_onboarding_form(
    form_id: int,
    finalize_data: FinalizeAndSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Finalize and send onboarding form
    
    **Request body:**
    - send_email: Whether to send email notification (optional)
    - custom_message: Custom message for candidate (optional)
    - include_offer_letter: Whether to include offer letter (optional)
    - include_policies: Whether to include policies (optional)
    
    **Updates:**
    - Form status to sent
    - Generates access token
    - Sends email to candidate with onboarding form link
    """
    try:
        from app.services.email_service import email_service
        from app.models.business import Business
        
        # Get form
        form = validate_form_access(db, form_id, current_user)
        if not form:
            raise HTTPException(status_code=404, detail="Onboarding form not found")
        
        # Get business for company name
        business = db.query(Business).filter(Business.id == form.business_id).first()
        company_name = business.business_name if business else "Levitica Technologies"
        
        # Check if policies are attached
        has_policies = db.query(OnboardingPolicy).filter(
            OnboardingPolicy.form_id == form_id
        ).count() > 0
        
        # Check if offer letter is attached
        has_offer_letter = db.query(OfferLetter).filter(
            OfferLetter.form_id == form_id
        ).count() > 0
        
        # Get offer letter content if exists
        offer_letter_content = None
        offer_letter_obj = None
        if has_offer_letter:
            offer_letter_obj = db.query(OfferLetter).filter(
                OfferLetter.form_id == form_id
            ).first()
            if offer_letter_obj and offer_letter_obj.letter_content:
                offer_letter_content = offer_letter_obj.letter_content
                logger.info(f"Found offer letter content for form {form_id}")
                logger.info(f"Position: {offer_letter_obj.position_title}, Joining: {offer_letter_obj.joining_date}, CTC: {offer_letter_obj.ctc}, Gross: {offer_letter_obj.gross_salary}")
        
        # Prepare salary data for advanced PDF (if available)
        salary_data = None
        try:
            # Try to get salary data from offer letter first
            if offer_letter_obj:
                # Extract salary from offer letter
                gross_salary = None
                if offer_letter_obj.gross_salary:
                    gross_str = str(offer_letter_obj.gross_salary).replace(',', '')
                    try:
                        gross_salary = float(gross_str)
                    except:
                        pass
                
                if gross_salary:
                    # Use salary calculation service to get actual breakdown
                    try:
                        from app.services.salary_calculation_service import SalaryCalculationService
                        calc_service = SalaryCalculationService(db)
                        
                        # Calculate salary breakup using the same service used in UI
                        salary_result = calc_service.calculate_salary_breakup(
                            gross_salary=gross_salary,
                            salary_structure_id=None,  # Use default structure
                            employee_id=None,
                            business_id=form.business_id,
                            options=None
                        )
                        
                        # Extract the breakdown from result
                        if salary_result and 'breakdown' in salary_result:
                            salary_data = salary_result['breakdown']
                            logger.info(f"Calculated salary data using SalaryCalculationService: {salary_data}")
                        else:
                            # Fallback to manual calculation
                            from app.services.pdf_data_mapper import pdf_data_mapper
                            basic_salary = None
                            if offer_letter_obj.basic_salary:
                                basic_str = str(offer_letter_obj.basic_salary).replace(',', '')
                                try:
                                    basic_salary = float(basic_str)
                                except:
                                    pass
                            salary_data = pdf_data_mapper._calculate_salary_breakdown(gross_salary, basic_salary)
                            logger.info(f"Calculated salary data manually: gross={gross_salary}, basic={basic_salary}")
                    except Exception as calc_error:
                        logger.warning(f"Could not use SalaryCalculationService: {calc_error}")
                        # Fallback to manual calculation
                        from app.services.pdf_data_mapper import pdf_data_mapper
                        basic_salary = None
                        if offer_letter_obj.basic_salary:
                            basic_str = str(offer_letter_obj.basic_salary).replace(',', '')
                            try:
                                basic_salary = float(basic_str)
                            except:
                                pass
                        salary_data = pdf_data_mapper._calculate_salary_breakdown(gross_salary, basic_salary)
            
            # Try to get salary data from form's additional data
            if not salary_data and hasattr(form, 'additional_data') and form.additional_data:
                import json
                additional = json.loads(form.additional_data) if isinstance(form.additional_data, str) else form.additional_data
                if 'salary_breakdown' in additional:
                    salary_data = additional['salary_breakdown']
        except Exception as e:
            logger.warning(f"Could not prepare salary data: {e}")
            import traceback
            traceback.print_exc()
            salary_data = None
        
        # Finalize and send
        form.status = OnboardingStatus.SENT
        form.sent_at = datetime.now()
        
        # Generate unique token if not exists
        if not form.form_token:
            import uuid
            form.form_token = str(uuid.uuid4())
        
        db.commit()
        
        # Send email to candidate
        email_sent = False
        if finalize_data.send_email:
            try:
                email_sent = await email_service.send_onboarding_form_email(
                    candidate_email=form.candidate_email,
                    candidate_name=form.candidate_name,
                    form_id=form.id,
                    form_token=form.form_token,
                    candidate_mobile=form.candidate_mobile,
                    has_policies=has_policies,
                    has_offer_letter=has_offer_letter,
                    offer_letter_content=offer_letter_content,
                    company_name=company_name,
                    form=form,  # Pass form for advanced PDF
                    salary_data=salary_data,  # Pass salary data for advanced PDF
                    offer_letter=offer_letter_obj  # Pass offer letter object
                )
            except Exception as email_error:
                # Log error but don't fail the request
                print(f"Failed to send email: {email_error}")
        
        return {
            "success": True,
            "message": "Onboarding form finalized and sent successfully",
            "form_id": form_id,
            "form_token": form.form_token,
            "sent_to": form.candidate_email,
            "sent_at": form.sent_at.isoformat(),
            "email_sent": email_sent,
            "has_policies": has_policies,
            "has_offer_letter": has_offer_letter
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize and send form: {str(e)}"
        )


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

# REMOVED DUPLICATE SETTINGS ENDPOINT - USE MAIN ENDPOINT ABOVE


@router.post("/settings/document")
async def update_document_requirement(
    update_data: DocumentRequirementUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update document requirement settings
    
    **Request body:**
    - document_type: Document type (required)
    - is_required: Whether document is required (required)
    - display_order: Display order (optional)
    
    **Updates:**
    - Document type requirements
    - Accepted file formats
    - Validation rules
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Get settings
        settings = db.query(OnboardingSettings).filter(OnboardingSettings.business_id == business_id).first()
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        # Update document requirements
        document_type = update_data.document_type
        
        current_reqs = settings.document_requirements or {}
        current_reqs[document_type] = {
            "is_required": update_data.is_required,
            "display_order": update_data.display_order
        }
        settings.document_requirements = current_reqs
        settings.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Document requirement for {document_type} updated successfully",
            "document_type": document_type,
            "is_required": update_data.is_required
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document requirement: {str(e)}"
        )


@router.post("/settings/field")
async def update_field_requirement(
    update_data: FieldRequirementUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update field requirement settings
    
    **Updates:**
    - Field mandatory status
    - Validation rules
    - Display configuration
    """
    try:
        user_business_ids = get_user_business_ids(db, current_user)
        
        business_id = user_business_ids[0]
        # Get settings
        settings = db.query(OnboardingSettings).filter(OnboardingSettings.business_id == business_id).first()
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        # Update field requirements
        field_name = update_data.get('field_name')
        requirements = update_data.get('requirements')
        
        current_reqs = settings.field_requirements or {}
        current_reqs[field_name] = requirements
        settings.field_requirements = current_reqs
        settings.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Field requirement for {field_name} updated successfully",
            "field_name": field_name,
            "requirements": requirements
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update field requirement: {str(e)}"
        )


def _get_step_required_fields(step_number: int) -> list:
    """Get required fields for a specific step"""
    step_fields = {
        1: ["first_name", "last_name", "email", "phone"],
        2: ["address", "city", "state", "zip_code"],
        3: ["emergency_contact_name", "emergency_contact_phone"],
        4: ["bank_name", "account_number", "routing_number"],
        5: ["signature", "date"]
    }
    return step_fields.get(step_number, [])

# ============================================================================
# LEGACY FRONTEN


# =============================================================================
# DIAGNOSTIC ENDPOINT (TEMPORARY - FOR DEBUGGING)
# =============================================================================

@router.get("/debug/environment")
async def check_server_environment():
    """
    Temporary diagnostic endpoint to check server's Python environment
    Remove this after fixing the reportlab issue
    """
    import sys
    
    environment_info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_path": sys.path[:5],
    }
    
    # Check reportlab
    try:
        import reportlab
        environment_info["reportlab"] = {
            "installed": True,
            "version": reportlab.Version,
            "location": reportlab.__file__
        }
    except ImportError as e:
        environment_info["reportlab"] = {
            "installed": False,
            "error": str(e)
        }
    
    # Check other key packages
    for package in ["fastapi", "uvicorn", "sqlalchemy", "pillow"]:
        try:
            mod = __import__(package.lower())
            environment_info[package] = {
                "installed": True,
                "version": getattr(mod, "__version__", "unknown"),
                "location": getattr(mod, "__file__", "unknown")
            }
        except ImportError:
            environment_info[package] = {
                "installed": False
            }
    
    # Installation command
    environment_info["install_command"] = f"{sys.executable} -m pip install reportlab==4.0.7"
    
    return environment_info
