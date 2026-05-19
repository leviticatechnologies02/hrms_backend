"""
Onboarding Service
Business logic layer for onboarding operations using repository pattern
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import json

from ..repositories.onboarding_repository import (
    OnboardingRepository, OfferLetterRepository, OfferLetterTemplateRepository,
    OnboardingSettingsRepository, BulkOnboardingRepository, FormSubmissionRepository,
    OnboardingDocumentRepository, OnboardingPolicyRepository
)
from ..models.onboarding import OnboardingForm, OnboardingStatus
from ..schemas.onboarding import (
    CreateOnboardingSchema, UpdateOnboardingSchema, BulkOnboardingCreate,
    FormSubmissionCreate, OnboardingSettingsUpdate
)


class OnboardingService:
    """Service layer for onboarding operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.onboarding_repo = OnboardingRepository(db)
        self.offer_letter_repo = OfferLetterRepository(db)
        self.template_repo = OfferLetterTemplateRepository(db)
        self.settings_repo = OnboardingSettingsRepository(db)
        self.bulk_repo = BulkOnboardingRepository(db)
        self.submission_repo = FormSubmissionRepository(db)
        self.document_repo = OnboardingDocumentRepository(db)
        self.policy_repo = OnboardingPolicyRepository(db)
    
    # =============================================================================
    # ONBOARDING FORM OPERATIONS
    # =============================================================================
    
    def create_onboarding_form(self, form_data: CreateOnboardingSchema, business_id: int, user_id: int) -> OnboardingForm:
        """Create a new onboarding form"""
        # Generate unique form token
        form_token = str(uuid.uuid4())
        # Calculate expiry date (use provided or default 7 days)
        expires_at = getattr(form_data, 'expires_at', None) or (datetime.now() + timedelta(days=7))

        # Create form data - only include columns that exist on the model
        create_data = {
            "business_id": business_id,
            "candidate_name": form_data.candidate_name,
            "candidate_email": form_data.candidate_email,
            "candidate_mobile": form_data.candidate_mobile,
            "form_token": form_token,
            "status": OnboardingStatus.DRAFT if not getattr(form_data, 'status', None) else form_data.status,
            "verify_mobile": form_data.verify_mobile,
            "verify_pan": form_data.verify_pan,
            "verify_bank": form_data.verify_bank,
            "verify_aadhaar": form_data.verify_aadhaar,
            "notes": form_data.notes,
            "expires_at": expires_at,
            "created_by": user_id,
            "created_at": datetime.now()
        }

        form = self.onboarding_repo.create(create_data)

        # Build response dict combining stored fields and nested objects from request
        response = {
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
            "policies": getattr(form_data, 'policies', None),
            "offer_letter": getattr(form_data, 'offer_letter', None),
            "salary_options": getattr(form_data, 'salary_options', None),
            "created_at": form.created_at,
            "sent_at": form.sent_at,
            "submitted_at": form.submitted_at,
            "approved_at": form.approved_at,
            "rejected_at": form.rejected_at,
            "expires_at": form.expires_at,
            "rejection_reason": form.rejection_reason,
            "created_by": form.created_by
        }

        return response
    
    def get_onboarding_form(self, form_id: int, business_id: int = None) -> Optional[OnboardingForm]:
        """Get onboarding form by ID"""
        form = self.onboarding_repo.get(form_id)
        
        # Check business_id if provided
        if form and business_id and form.business_id != business_id:
            return None
        
        return form
    
    def get_onboarding_forms(self, business_id: int, skip: int = 0, limit: int = 100) -> List[OnboardingForm]:
        """Get onboarding forms for a business"""
        return self.onboarding_repo.get_by_business_id(business_id, skip, limit)
    
    def update_onboarding_form(self, form_id: int, form_data: UpdateOnboardingSchema, business_id: int = None) -> Optional[OnboardingForm]:
        """Update onboarding form"""
        form = self.get_onboarding_form(form_id, business_id)
        if not form:
            return None

        # Prepare update data for DB columns
        update_data = form_data.dict(exclude_unset=True)
        # Remove nested objects before passing to DB update
        nested = {}
        for key in ['policies', 'offer_letter', 'salary_options']:
            if key in update_data:
                nested[key] = update_data.pop(key)

        update_data["updated_at"] = datetime.now()

        updated_form = self.onboarding_repo.update(form, update_data)

        # Build response merging stored and nested
        response = {
            "id": updated_form.id,
            "business_id": updated_form.business_id,
            "candidate_name": updated_form.candidate_name,
            "candidate_email": updated_form.candidate_email,
            "candidate_mobile": updated_form.candidate_mobile,
            "form_token": updated_form.form_token,
            "status": updated_form.status.value if updated_form.status else None,
            "verify_mobile": updated_form.verify_mobile,
            "verify_pan": updated_form.verify_pan,
            "verify_bank": updated_form.verify_bank,
            "verify_aadhaar": updated_form.verify_aadhaar,
            "notes": updated_form.notes,
            "policies": nested.get('policies', None),
            "offer_letter": nested.get('offer_letter', None),
            "salary_options": nested.get('salary_options', None),
            "created_at": updated_form.created_at,
            "sent_at": updated_form.sent_at,
            "submitted_at": updated_form.submitted_at,
            "approved_at": updated_form.approved_at,
            "rejected_at": updated_form.rejected_at,
            "expires_at": updated_form.expires_at,
            "rejection_reason": updated_form.rejection_reason,
            "created_by": updated_form.created_by
        }

        return response
    
    def delete_onboarding_form(self, form_id: int, business_id: int = None) -> bool:
        """Soft delete onboarding form"""
        form = self.get_onboarding_form(form_id, business_id)
        if not form:
            return False
        
        return self.onboarding_repo.soft_delete(form_id)
    
    def search_onboarding_forms(self, business_id: int, search_term: str = None, status: str = None) -> List[OnboardingForm]:
        """Search onboarding forms"""
        if search_term:
            forms = self.onboarding_repo.search_forms(business_id, search_term)
        else:
            forms = self.onboarding_repo.get_by_business_id(business_id)
        
        # Filter by status if provided
        if status and status != "All":
            if status == "Pending":
                status = OnboardingStatus.SUBMITTED
            forms = [f for f in forms if f.status == status.lower()]
        
        return forms
    
    def get_forms_for_frontend(self, business_id: int, status: str = None, search: str = None) -> Dict[str, Any]:
        """Get forms in frontend-compatible format"""
        forms = self.search_onboarding_forms(business_id, search, status)
        
        # Convert to frontend format
        frontend_forms = []
        for form in forms:
            # Map backend status to frontend status
            frontend_status = form.status.title() if form.status else "Draft"
            if form.status == "submitted":
                frontend_status = "Pending"
            
            frontend_forms.append({
                "id": form.id,
                "candidate": form.candidate_name,
                "created": form.created_at.strftime("%d-%b-%Y") if form.created_at else "",
                "email": form.candidate_email,
                "mobile": form.candidate_mobile,
                "info": "View Form",
                "status": frontend_status,
                "form_token": form.form_token,
                "expires_at": form.expires_at.isoformat() if form.expires_at else None,
                "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
                "approved_at": form.approved_at.isoformat() if form.approved_at else None,
                "rejected_at": form.rejected_at.isoformat() if form.rejected_at else None
            })
        
        return {
            "success": True,
            "forms": frontend_forms,
            "total": len(frontend_forms)
        }
    
    # =============================================================================
    # FORM STATUS OPERATIONS
    # =============================================================================
    
    def send_onboarding_form(self, form_id: int, business_id: int, user_id: int) -> Optional[OnboardingForm]:
        """Send onboarding form to candidate"""
        form = self.get_onboarding_form(form_id, business_id)
        if not form:
            return None
        
        return self.onboarding_repo.update_status(form_id, OnboardingStatus.SENT, user_id)
    
    def approve_onboarding_form(self, form_id: int, business_id: int, user_id: int) -> Optional[OnboardingForm]:
        """Approve onboarding form"""
        form = self.get_onboarding_form(form_id, business_id)
        if not form:
            return None
        
        return self.onboarding_repo.update_status(form_id, OnboardingStatus.APPROVED, user_id)
    
    def reject_onboarding_form(self, form_id: int, business_id: int, user_id: int, reason: str = None) -> Optional[OnboardingForm]:
        """Reject onboarding form"""
        form = self.get_onboarding_form(form_id, business_id)
        if not form:
            return None
        
        # Update with rejection reason
        form = self.onboarding_repo.update_status(form_id, OnboardingStatus.REJECTED, user_id)
        if form and reason:
            form.rejection_reason = reason
            self.db.commit()
            self.db.refresh(form)
        
        return form
    
    # =============================================================================
    # DASHBOARD OPERATIONS
    # =============================================================================
    
    def get_dashboard_data(self, business_id: int) -> Dict[str, Any]:
        """Get onboarding dashboard data"""
        # Get basic stats
        stats = self.onboarding_repo.get_dashboard_stats(business_id)
        
        # Get recent submissions (last 10)
        recent_forms = self.onboarding_repo.get_by_business_id(business_id, 0, 10)
        recent_submissions = []
        for form in recent_forms:
            recent_submissions.append({
                "id": form.id,
                "candidate_name": form.candidate_name,
                "candidate_email": form.candidate_email,
                "status": form.status.value if form.status else "draft",
                "submitted_at": form.submitted_at.isoformat() if form.submitted_at else form.created_at.isoformat()
            })
        
        # Get real monthly stats from database
        monthly_stats = self._get_monthly_hiring_stats(business_id)
        
        # Calculate conversion rate
        conversion_rate = 0
        if stats["total_forms"] > 0:
            conversion_rate = round((stats["approved_forms"] / stats["total_forms"]) * 100, 2)
        
        return {
            "total_forms": stats["total_forms"],
            "pending_approvals": stats["pending_approvals"],
            "approved_forms": stats["approved_forms"],
            "rejected_forms": stats["rejected_forms"],
            "draft_forms": stats["draft_forms"],
            "sent_forms": stats["sent_forms"],
            "submitted_forms": stats["submitted_forms"],
            "expired_forms": stats["expired_forms"],
            "recent_submissions": recent_submissions,
            "monthly_stats": monthly_stats,
            "conversion_rate": conversion_rate
        }
    
    def _get_monthly_hiring_stats(self, business_id: int) -> List[Dict[str, Any]]:
        """Get monthly hiring statistics from database"""
        from sqlalchemy import extract, func
        from datetime import datetime, timedelta
        
        # Get data for last 12 months
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Query monthly approved forms
        monthly_data = self.db.query(
            extract('year', OnboardingForm.approved_at).label('year'),
            extract('month', OnboardingForm.approved_at).label('month'),
            func.count(OnboardingForm.id).label('count')
        ).filter(
            OnboardingForm.business_id == business_id,
            OnboardingForm.status == OnboardingStatus.APPROVED,
            OnboardingForm.approved_at >= start_date,
            OnboardingForm.approved_at <= end_date
        ).group_by(
            extract('year', OnboardingForm.approved_at),
            extract('month', OnboardingForm.approved_at)
        ).order_by(
            extract('year', OnboardingForm.approved_at),
            extract('month', OnboardingForm.approved_at)
        ).all()
        
        # Convert to monthly stats format
        monthly_stats = []
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]
        
        # Create a map of existing data
        data_map = {}
        for row in monthly_data:
            key = f"{int(row.year)}-{int(row.month):02d}"
            data_map[key] = int(row.count)
        
        # Generate last 12 months with data
        current_date = end_date
        for i in range(12):
            month_date = current_date - timedelta(days=30 * i)
            year = month_date.year
            month = month_date.month
            key = f"{year}-{month:02d}"
            
            month_name = f"{month_names[month-1]} {year}"
            count = data_map.get(key, 0)
            
            monthly_stats.insert(0, {
                "month": month_name,
                "value": count,
                "count": count  # For backward compatibility
            })
        
        return monthly_stats
    
    # =============================================================================
    # BULK ONBOARDING OPERATIONS
    # =============================================================================
    
    def process_bulk_onboarding(self, bulk_data: BulkOnboardingCreate, business_id: int, user_id: int) -> Dict[str, Any]:
        """Process bulk onboarding operation"""
        # Create bulk operation record
        bulk_create_data = {
            "business_id": business_id,
            "operation_name": bulk_data.operation_name,
            "total_candidates": len(bulk_data.candidates),
            "verify_mobile": bulk_data.verify_mobile,
            "verify_pan": bulk_data.verify_pan,
            "verify_bank": bulk_data.verify_bank,
            "verify_aadhaar": bulk_data.verify_aadhaar,
            "status": "processing",
            "created_by": user_id,
            "created_at": datetime.now()
        }
        
        bulk_operation = self.bulk_repo.create(bulk_create_data)
        
        # Get business details for email
        from app.models.business import Business
        business = self.db.query(Business).filter(Business.id == business_id).first()
        business_name = business.business_name if business else "Company"
        
        # Import email service
        from app.services.email_service import EmailService
        email_service = EmailService()
        
        # Create individual forms and send emails
        successful_sends = 0
        failed_sends = 0
        results = []
        
        for candidate in bulk_data.candidates:
            try:
                form_token = str(uuid.uuid4())
                expires_at = datetime.now() + timedelta(days=7)
                
                form_data = {
                    "business_id": business_id,
                    "candidate_name": candidate.candidate_name,
                    "candidate_email": candidate.candidate_email,
                    "candidate_mobile": candidate.candidate_mobile,
                    "form_token": form_token,
                    "status": OnboardingStatus.SENT,
                    "verify_mobile": bulk_data.verify_mobile,
                    "verify_pan": bulk_data.verify_pan,
                    "verify_bank": bulk_data.verify_bank,
                    "verify_aadhaar": bulk_data.verify_aadhaar,
                    "expires_at": expires_at,
                    "created_by": user_id,
                    "sent_at": datetime.now(),
                    "created_at": datetime.now()
                }
                
                form = self.onboarding_repo.create(form_data)
                
                # Send onboarding email
                try:
                    # Run async email function using asyncio.create_task or run_in_executor
                    import asyncio
                    try:
                        # Try to get the current event loop
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        # If no loop exists, create a new one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Use asyncio.run if we're not in an async context
                    if loop.is_running():
                        # If loop is already running, schedule the coroutine
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                asyncio.run,
                                email_service.send_onboarding_form_email(
                                    candidate_email=candidate.candidate_email,
                                    candidate_name=candidate.candidate_name,
                                    form_id=form.id,
                                    form_token=form_token,
                                    candidate_mobile=candidate.candidate_mobile,
                                    has_policies=False,
                                    has_offer_letter=False,
                                    company_name=business_name
                                )
                            )
                            email_sent = future.result(timeout=30)
                    else:
                        # If no loop is running, use run_until_complete
                        email_sent = loop.run_until_complete(
                            email_service.send_onboarding_form_email(
                                candidate_email=candidate.candidate_email,
                                candidate_name=candidate.candidate_name,
                                form_id=form.id,
                                form_token=form_token,
                                candidate_mobile=candidate.candidate_mobile,
                                has_policies=False,
                                has_offer_letter=False,
                                company_name=business_name
                            )
                        )
                    
                    if not email_sent:
                        print(f"Warning: Email not sent to {candidate.candidate_email}, but form created")
                    else:
                        print(f"✅ Email sent successfully to {candidate.candidate_email}")
                except Exception as email_error:
                    print(f"Error sending email to {candidate.candidate_email}: {str(email_error)}")
                    # Continue even if email fails - form is still created
                
                successful_sends += 1
                results.append({
                    "candidate_name": candidate.candidate_name,
                    "candidate_email": candidate.candidate_email,
                    "status": "success",
                    "form_id": form.id,
                    "form_token": form_token
                })
                
            except Exception as e:
                failed_sends += 1
                results.append({
                    "candidate_name": candidate.candidate_name,
                    "candidate_email": candidate.candidate_email,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Update bulk operation
        update_data = {
            "successful_sends": successful_sends,
            "failed_sends": failed_sends,
            "status": "completed",
            "completed_at": datetime.now(),
            "results_summary": json.dumps(results)
        }
        
        bulk_operation = self.bulk_repo.update(bulk_operation, update_data)
        
        return {
            "bulk_operation": bulk_operation,
            "results": results,
            "summary": {
                "total": len(bulk_data.candidates),
                "successful": successful_sends,
                "failed": failed_sends
            }
        }
    
    # =============================================================================
    # FORM SUBMISSION OPERATIONS
    # =============================================================================
    
    def submit_onboarding_form(self, form_id: int, submission_data: FormSubmissionCreate) -> Optional[Dict[str, Any]]:
        """Submit onboarding form (used by candidates)"""
        # Get form by ID (no business_id filter for public access)
        form = self.onboarding_repo.get(form_id)
        if not form:
            return None
        
        # Check if form is still valid
        if form.expires_at and form.expires_at < datetime.now():
            # Update form status to expired
            self.onboarding_repo.update_status(form_id, OnboardingStatus.EXPIRED, form.created_by)
            return {"error": "Form has expired"}
        
        # Create form submission
        submission_create_data = {
            "form_id": form_id,
            **submission_data.dict(),
            "submitted_at": datetime.now()
        }
        
        submission = self.submission_repo.create(submission_create_data)
        
        # Update form status
        self.onboarding_repo.update_status(form_id, OnboardingStatus.SUBMITTED, form.created_by)
        
        return {"submission": submission, "form": form}
    
    # =============================================================================
    # SETTINGS OPERATIONS
    # =============================================================================
    
    def get_onboarding_settings(self, business_id: int, user_id: int) -> Dict[str, Any]:
        """Get onboarding settings"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create default settings
            settings = self.settings_repo.create_default_settings(business_id, user_id)
        
        # Parse JSON fields for response
        document_requirements = {}
        field_requirements = {}

        try:
            if settings.document_requirements:
                document_requirements = json.loads(settings.document_requirements)
        except (json.JSONDecodeError, TypeError):
            document_requirements = {}

        try:
            if settings.field_requirements:
                field_requirements = json.loads(settings.field_requirements)
        except (json.JSONDecodeError, TypeError):
            field_requirements = {}

        # Map storage to new API shape: `fields` and `documents` with snake_case keys
        return {
            "id": settings.id,
            "business_id": settings.business_id,
            "fields": field_requirements,
            "documents": document_requirements,
            "created_at": settings.created_at,
            "updated_at": settings.updated_at,
            "created_by": settings.created_by
        }
    
    def update_onboarding_settings(self, business_id: int, settings_data: OnboardingSettingsUpdate, user_id: int) -> Dict[str, Any]:
        """Update onboarding settings"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create new settings if none exist
            settings = self.settings_repo.create_default_settings(business_id, user_id)
        

        # Prepare update data
        update_data = settings_data.dict(exclude_unset=True)

        # Accept new API shape: `documents` and `fields` and convert to storage keys
        if "documents" in update_data and update_data["documents"] is not None:
            try:
                update_data["document_requirements"] = json.dumps(update_data.pop("documents"))
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid documents format: {str(e)}")

        if "fields" in update_data and update_data["fields"] is not None:
            try:
                update_data["field_requirements"] = json.dumps(update_data.pop("fields"))
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid fields format: {str(e)}")
        
        # Validate JSON fields if they exist (legacy keys remain supported)
        if "auto_approval_criteria" in update_data and update_data["auto_approval_criteria"]:
            try:
                json.loads(update_data["auto_approval_criteria"])
            except json.JSONDecodeError:
                raise ValueError("Invalid auto_approval_criteria JSON format")

        if "custom_fields" in update_data and update_data["custom_fields"]:
            try:
                json.loads(update_data["custom_fields"])
            except json.JSONDecodeError:
                raise ValueError("Invalid custom_fields JSON format")
        
        update_data["updated_at"] = datetime.now()
        
        settings = self.settings_repo.update(settings, update_data)
        
        return self.get_onboarding_settings(business_id, user_id)
    
    def get_settings_frontend_format(self, business_id: int, user_id: int) -> Dict[str, Any]:
        """Get settings in frontend-compatible format"""
        settings_data = self.get_onboarding_settings(business_id, user_id)
        
        # Convert document requirements to frontend format (array of booleans)
        # Map display names to storage keys (snake_case)
        frontend_documents = [
            ("PAN Card", "pan_card"),
            ("Adhar Card", "adhar_card"),
            ("ESI Card", "esi_card"),
            ("Driving License", "driving_license"),
            ("Passport", "passport"),
            ("Voter ID", "voter_id"),
            ("Last Relieving Letter", "last_relieving_letter"),
            ("Last Salary Slip", "last_salary_slip"),
            ("Latest Bank Statement", "latest_bank_statement"),
            ("Highest Education Proof", "highest_education_proof")
        ]

        document_requirements = settings_data.get("documents", {})
        document_states = []
        for display_name, key in frontend_documents:
            document_states.append(document_requirements.get(key, False))

        # For compatibility, return human-readable list of document names (same as before)
        frontend_document_names = [d[0] for d in frontend_documents]
        
        return {
            "success": True,
            "settings": {
                "id": settings_data["id"],
                "business_id": settings_data["business_id"],
                "documents": frontend_document_names,
                "document_states": document_states,
                "field_requirements": settings_data.get("field_requirements", {}),
                "form_expiry_days": settings_data["form_expiry_days"],
                "allow_form_editing": settings_data["allow_form_editing"],
                "require_document_upload": settings_data["require_document_upload"],
                "send_welcome_email": settings_data["send_welcome_email"],
                "send_reminder_emails": settings_data["send_reminder_emails"],
                "reminder_frequency_days": settings_data["reminder_frequency_days"]
            }
        }
    
    def update_document_requirement(self, business_id: int, document_name: str, required: bool, user_id: int) -> Dict[str, Any]:
        """Update document requirement (auto-save for frontend)"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create new settings if none exist
            settings = self.settings_repo.create_default_settings(business_id, user_id)
        
        # Update document requirements
        document_requirements = json.loads(settings.document_requirements) if settings.document_requirements else {}
        document_requirements[document_name] = required
        
        update_data = {
            "document_requirements": json.dumps(document_requirements),
            "updated_at": datetime.now()
        }
        
        settings = self.settings_repo.update(settings, update_data)
        
        return {
            "success": True,
            "message": f"Document '{document_name}' requirement updated",
            "document_name": document_name,
            "required": required,
            "updated_at": settings.updated_at.isoformat()
        }
    
    def update_field_requirement(self, business_id: int, field_name: str, required: bool, user_id: int) -> Dict[str, Any]:
        """Update field requirement (auto-save for frontend)"""
        settings = self.settings_repo.get_by_business_id(business_id)
        
        if not settings:
            # Create new settings if none exist
            settings = self.settings_repo.create_default_settings(business_id, user_id)
        
        # Update field requirements
        field_requirements = json.loads(settings.field_requirements) if settings.field_requirements else {}
        field_requirements[field_name] = required
        
        update_data = {
            "field_requirements": json.dumps(field_requirements),
            "updated_at": datetime.now()
        }
        
        settings = self.settings_repo.update(settings, update_data)
        
        return {
            "success": True,
            "message": f"Field '{field_name}' requirement updated",
            "field_name": field_name,
            "required": required,
            "updated_at": settings.updated_at.isoformat()
        }
    
    # =============================================================================
    # OFFER LETTER OPERATIONS
    # =============================================================================
    
    def get_offer_letter_templates(self, business_id: int) -> List[Dict[str, Any]]:
        """Get offer letter templates"""
        templates = self.template_repo.get_by_business_id(business_id)
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "template_content": t.template_content,
                "available_variables": t.available_variables,
                "is_active": t.is_active,
                "is_default": t.is_default,
                "created_at": t.created_at,
                "updated_at": t.updated_at
            }
            for t in templates
        ]
    
    def get_templates_frontend_format(self, business_id: int) -> Dict[str, Any]:
        """Get templates in frontend-compatible format"""
        templates = self.template_repo.get_by_business_id(business_id)
        
        # Convert to frontend format (name -> content mapping)
        template_dict = {}
        for template in templates:
            template_dict[template.name] = template.template_content
        
        return {
            "success": True,
            "templates": template_dict,
            "count": len(templates)
        }
