"""
Onboarding Repository
Data access layer for onboarding operations following repository pattern
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from ..models.onboarding import (
    OnboardingForm, OfferLetter, OfferLetterTemplate, OnboardingStatus, 
    OnboardingSettings, BulkOnboarding, FormSubmission, OnboardingDocument, 
    OnboardingPolicy
)


class OnboardingRepository(BaseRepository[OnboardingForm]):
    """Repository for onboarding form operations"""
    
    def __init__(self, db: Session):
        super().__init__(OnboardingForm, db)
    
    def get_by_business_id(self, business_id: int, skip: int = 0, limit: int = 100) -> List[OnboardingForm]:
        """Get onboarding forms by business ID"""
        return self.db.query(OnboardingForm).options(joinedload(OnboardingForm.form_policy_mappings)).filter(
            and_(
                OnboardingForm.business_id == business_id,
                OnboardingForm.is_active == True
            )
        ).order_by(desc(OnboardingForm.created_at)).offset(skip).limit(limit).all()
    
    def get_by_token(self, form_token: str) -> Optional[OnboardingForm]:
        """Get onboarding form by token (for public access)"""
        return self.db.query(OnboardingForm).filter(
            OnboardingForm.form_token == form_token
        ).first()
    
    def get_by_status(self, business_id: int, status: OnboardingStatus) -> List[OnboardingForm]:
        """Get forms by status"""
        return self.db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.business_id == business_id,
                OnboardingForm.status == status,
                OnboardingForm.is_active == True
            )
        ).order_by(desc(OnboardingForm.created_at)).all()
    
    def search_forms(self, business_id: int, search_term: str) -> List[OnboardingForm]:
        """Search forms by candidate name, email, or mobile"""
        return self.db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.business_id == business_id,
                OnboardingForm.is_active == True,
                or_(
                    OnboardingForm.candidate_name.ilike(f"%{search_term}%"),
                    OnboardingForm.candidate_email.ilike(f"%{search_term}%"),
                    OnboardingForm.candidate_mobile.ilike(f"%{search_term}%")
                )
            )
        ).order_by(desc(OnboardingForm.created_at)).all()
    
    def get_dashboard_stats(self, business_id: int) -> Dict[str, Any]:
        """Get dashboard statistics"""
        base_query = self.db.query(OnboardingForm).filter(
            OnboardingForm.business_id == business_id
        )
        
        stats = {
            "total_forms": base_query.count(),
            "draft_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.DRAFT).count(),
            "sent_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.SENT).count(),
            "submitted_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.SUBMITTED).count(),
            "approved_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.APPROVED).count(),
            "rejected_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.REJECTED).count(),
            "expired_forms": base_query.filter(OnboardingForm.status == OnboardingStatus.EXPIRED).count(),
        }
        
        stats["pending_approvals"] = stats["submitted_forms"]
        
        return stats
    
    def get_recent_submissions(self, business_id: int, limit: int = 10) -> List[OnboardingForm]:
        """Get recent form submissions"""
        return self.db.query(OnboardingForm).filter(
            and_(
                OnboardingForm.business_id == business_id,
                OnboardingForm.submitted_at.isnot(None)
            )
        ).order_by(desc(OnboardingForm.submitted_at)).limit(limit).all()
    
    def get_monthly_stats(self, business_id: int, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly statistics for the last N months"""
        monthly_stats = []
        
        for i in range(months):
            month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=32)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            
            count = self.db.query(OnboardingForm).filter(
                and_(
                    OnboardingForm.business_id == business_id,
                    OnboardingForm.created_at >= month_start,
                    OnboardingForm.created_at <= month_end
                )
            ).count()
            
            monthly_stats.append({
                "month": month_start.strftime("%Y-%m"),
                "count": count
            })
        
        return monthly_stats
    
    def update_status(self, form_id: int, status: OnboardingStatus, user_id: int) -> Optional[OnboardingForm]:
        """Update form status with appropriate timestamps"""
        form = self.get(form_id)
        if not form:
            return None
        
        form.status = status
        
        # Set appropriate timestamps based on status
        if status == OnboardingStatus.SENT:
            form.sent_at = datetime.now()
        elif status == OnboardingStatus.SUBMITTED:
            form.submitted_at = datetime.now()
        elif status == OnboardingStatus.APPROVED:
            form.approved_at = datetime.now()
            form.approved_by = user_id
        elif status == OnboardingStatus.REJECTED:
            form.rejected_at = datetime.now()
            form.rejected_by = user_id
        
        form.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(form)
        
        return form
    
    def soft_delete(self, form_id: int) -> bool:
        """Soft delete form by setting is_active to False"""
        form = self.get(form_id)
        if not form:
            return False
        
        form.is_active = False
        form.updated_at = datetime.now()
        self.db.commit()
        
        return True


class OfferLetterRepository(BaseRepository[OfferLetter]):
    """Repository for offer letter operations"""
    
    def __init__(self, db: Session):
        super().__init__(OfferLetter, db)
    
    def get_by_form_id(self, form_id: int) -> List[OfferLetter]:
        """Get offer letters by form ID"""
        return self.db.query(OfferLetter).filter(
            OfferLetter.form_id == form_id
        ).order_by(desc(OfferLetter.created_at)).all()
    
    def get_standalone_letters(self) -> List[OfferLetter]:
        """Get standalone offer letters (not attached to forms)"""
        return self.db.query(OfferLetter).filter(
            OfferLetter.form_id.is_(None)
        ).order_by(desc(OfferLetter.created_at)).all()


class OfferLetterTemplateRepository(BaseRepository[OfferLetterTemplate]):
    """Repository for offer letter template operations"""
    
    def __init__(self, db: Session):
        super().__init__(OfferLetterTemplate, db)
    
    def get_by_business_id(self, business_id: int) -> List[OfferLetterTemplate]:
        """Get templates by business ID"""
        return self.db.query(OfferLetterTemplate).filter(
            and_(
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_active == True
            )
        ).order_by(OfferLetterTemplate.name).all()
    
    def get_by_name(self, business_id: int, name: str) -> Optional[OfferLetterTemplate]:
        """Get template by name"""
        return self.db.query(OfferLetterTemplate).filter(
            and_(
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.name == name,
                OfferLetterTemplate.is_active == True
            )
        ).first()
    
    def get_default_template(self, business_id: int) -> Optional[OfferLetterTemplate]:
        """Get default template for business"""
        return self.db.query(OfferLetterTemplate).filter(
            and_(
                OfferLetterTemplate.business_id == business_id,
                OfferLetterTemplate.is_default == True,
                OfferLetterTemplate.is_active == True
            )
        ).first()


class OnboardingSettingsRepository(BaseRepository[OnboardingSettings]):
    """Repository for onboarding settings operations"""
    
    def __init__(self, db: Session):
        super().__init__(OnboardingSettings, db)
    
    def get_by_business_id(self, business_id: int) -> Optional[OnboardingSettings]:
        """Get settings by business ID"""
        return self.db.query(OnboardingSettings).filter(
            OnboardingSettings.business_id == business_id
        ).first()
    
    def create_default_settings(self, business_id: int, user_id: int) -> OnboardingSettings:
        """Create default settings for a business"""
        import json
        
        default_document_requirements = {
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
        
        default_field_requirements = {
            "present_address": True,
            "permanent_address": True,
            "bank_details": True
        }
        
        settings = OnboardingSettings(
            business_id=business_id,
            form_expiry_days=7,
            allow_form_editing=True,
            require_document_upload=True,
            send_welcome_email=True,
            send_reminder_emails=True,
            reminder_frequency_days=2,
            default_verify_mobile=True,
            default_verify_pan=False,
            default_verify_bank=False,
            default_verify_aadhaar=False,
            enable_auto_approval=False,
            document_requirements=json.dumps(default_document_requirements),
            field_requirements=json.dumps(default_field_requirements),
            created_by=user_id,
            created_at=datetime.now()
        )
        
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        
        return settings


class BulkOnboardingRepository(BaseRepository[BulkOnboarding]):
    """Repository for bulk onboarding operations"""
    
    def __init__(self, db: Session):
        super().__init__(BulkOnboarding, db)
    
    def get_by_business_id(self, business_id: int) -> List[BulkOnboarding]:
        """Get bulk operations by business ID"""
        return self.db.query(BulkOnboarding).filter(
            BulkOnboarding.business_id == business_id
        ).order_by(desc(BulkOnboarding.created_at)).all()
    
    def get_recent_operations(self, business_id: int, limit: int = 10) -> List[BulkOnboarding]:
        """Get recent bulk operations"""
        return self.db.query(BulkOnboarding).filter(
            BulkOnboarding.business_id == business_id
        ).order_by(desc(BulkOnboarding.created_at)).limit(limit).all()


class FormSubmissionRepository(BaseRepository[FormSubmission]):
    """Repository for form submission operations"""
    
    def __init__(self, db: Session):
        super().__init__(FormSubmission, db)
    
    def get_by_form_id(self, form_id: int) -> Optional[FormSubmission]:
        """Get submission by form ID"""
        return self.db.query(FormSubmission).filter(
            FormSubmission.form_id == form_id
        ).first()
    
    def get_recent_submissions(self, limit: int = 50) -> List[FormSubmission]:
        """Get recent form submissions"""
        return self.db.query(FormSubmission).order_by(
            desc(FormSubmission.submitted_at)
        ).limit(limit).all()


class OnboardingDocumentRepository(BaseRepository[OnboardingDocument]):
    """Repository for onboarding document operations"""
    
    def __init__(self, db: Session):
        super().__init__(OnboardingDocument, db)
    
    def get_by_form_id(self, form_id: int) -> List[OnboardingDocument]:
        """Get documents by form ID"""
        return self.db.query(OnboardingDocument).filter(
            OnboardingDocument.form_id == form_id
        ).order_by(OnboardingDocument.display_order).all()
    
    def get_mandatory_documents(self, form_id: int) -> List[OnboardingDocument]:
        """Get mandatory documents for a form"""
        return self.db.query(OnboardingDocument).filter(
            and_(
                OnboardingDocument.form_id == form_id,
                OnboardingDocument.is_mandatory == True
            )
        ).order_by(OnboardingDocument.display_order).all()


class OnboardingPolicyRepository(BaseRepository[OnboardingPolicy]):
    """Repository for onboarding policy operations"""
    
    def __init__(self, db: Session):
        super().__init__(OnboardingPolicy, db)
    
    def get_by_form_id(self, form_id: int, business_id: int = None) -> List[OnboardingPolicy]:
        """Get policies by form ID, optionally scoped to a business"""
        q = self.db.query(OnboardingPolicy).filter(OnboardingPolicy.form_id == form_id)
        if business_id is not None:
            q = q.filter(OnboardingPolicy.business_id == business_id)
        return q.order_by(OnboardingPolicy.display_order).all()
    
    def get_mandatory_policies(self, form_id: int, business_id: int = None) -> List[OnboardingPolicy]:
        """Get mandatory policies for a form, optionally scoped to a business"""
        q = self.db.query(OnboardingPolicy).filter(
            OnboardingPolicy.form_id == form_id,
            OnboardingPolicy.is_mandatory == True
        )
        if business_id is not None:
            q = q.filter(OnboardingPolicy.business_id == business_id)
        return q.order_by(OnboardingPolicy.display_order).all()