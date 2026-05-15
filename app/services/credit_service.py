"""
Credit Service
Business logic for credit management
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from app.models.credits import UserCredits, CreditTransaction, CreditPricing
from app.models.user import User
from app.schemas.credits import CreditPurchaseRequest, CreditUsageRequest
from datetime import datetime
from decimal import Decimal
import uuid


class CreditService:
    
    @staticmethod
    def get_user_credits(db: Session, user_id: int, business_id: int) -> UserCredits:
        """Get or create user credits record"""
        user_credits = db.query(UserCredits).filter(
            and_(UserCredits.user_id == user_id, UserCredits.business_id == business_id)
        ).first()
        if not user_credits:
            user_credits = UserCredits(
                user_id=user_id,
                business_id=business_id,
                credits=0
            )
            db.add(user_credits)
            try:
                db.commit()
                db.refresh(user_credits)
            except IntegrityError:
                # Could be legacy unique constraint on user_id; rollback and try to fetch existing
                db.rollback()
                # Prefer exact match
                user_credits = db.query(UserCredits).filter(
                    and_(UserCredits.user_id == user_id, UserCredits.business_id == business_id)
                ).first()
                if not user_credits:
                    # Fallback: return any record for this user (legacy schema), to avoid 500
                    user_credits = db.query(UserCredits).filter(UserCredits.user_id == user_id).first()
                # If still not found, re-raise to avoid silent failures
                if not user_credits:
                    raise
        
        return user_credits
    
    @staticmethod
    def get_credit_pricing(db: Session, business_id: int) -> dict:
        """Get credit pricing for all services"""
        pricing = db.query(CreditPricing).filter(
            and_(CreditPricing.business_id == business_id, CreditPricing.is_active == True)
        ).all()
        
        # Default pricing if not configured
        if not pricing:
            return {
                "mobile": {"credits": 0, "is_free": True, "display_name": "Mobile Verification"},
                "pan": {"credits": 5, "is_free": False, "display_name": "PAN Verification"},
                "bank": {"credits": 5, "is_free": False, "display_name": "Bank Verification"},
                "aadhaar": {"credits": 10, "is_free": False, "display_name": "Aadhaar Verification"}
            }
        
        return {
            p.service_name: {
                "credits": p.credits_required,
                "is_free": p.is_free,
                "display_name": p.service_display_name
            }
            for p in pricing
        }
    
    @staticmethod
    def calculate_verification_cost(verification_options: dict, pricing: dict) -> int:
        """Calculate total credits required for verification options"""
        total_credits = 0
        
        for service, enabled in verification_options.items():
            if enabled and service in pricing:
                total_credits += pricing[service]["credits"]
        
        return total_credits
    
    @staticmethod
    def purchase_credits(
        db: Session, 
        user_id: int, 
        business_id: int, 
        purchase_request: CreditPurchaseRequest
    ) -> dict:
        """Purchase credits for user"""
        user_credits = CreditService.get_user_credits(db, user_id, business_id)
        
        # Mock payment processing (in real implementation, integrate with payment gateway)
        credits_to_add = purchase_request.credits_to_purchase
        payment_amount = Decimal(credits_to_add * 0.10)  # Mock: $0.10 per credit
        
        # Create transaction record
        transaction = CreditTransaction(
            user_credits_id=user_credits.id,
            transaction_type="purchase",
            amount=credits_to_add,
            balance_before=user_credits.credits,
            balance_after=user_credits.credits + credits_to_add,
            description=f"Purchased {credits_to_add} credits",
            reference_id=f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
            reference_type="purchase",
            payment_method=purchase_request.payment_method,
            payment_reference=f"PAY_{uuid.uuid4().hex[:12]}",
            payment_amount=payment_amount,
            created_by=user_id
        )
        
        # Update user credits
        user_credits.credits += credits_to_add
        user_credits.updated_at = datetime.now()
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        db.refresh(user_credits)
        
        return {
            "success": True,
            "message": f"Successfully purchased {credits_to_add} credits",
            "credits_purchased": credits_to_add,
            "new_balance": user_credits.credits,
            "transaction_id": transaction.reference_id,
            "payment_amount": payment_amount,
            "timestamp": transaction.created_at
        }
    
    @staticmethod
    def use_credits(
        db: Session,
        user_id: int,
        business_id: int,
        usage_request: CreditUsageRequest
    ) -> dict:
        """Use credits for a service"""
        user_credits = CreditService.get_user_credits(db, user_id, business_id)
        pricing = CreditService.get_credit_pricing(db, business_id)
        
        service_name = usage_request.service_name
        if service_name not in pricing:
            raise ValueError(f"Unknown service: {service_name}")
        
        credits_required = pricing[service_name]["credits"] * usage_request.quantity
        
        if pricing[service_name]["is_free"]:
            credits_required = 0
        
        if user_credits.credits < credits_required:
            raise ValueError(f"Insufficient credits. Required: {credits_required}, Available: {user_credits.credits}")
        
        # Create transaction record
        transaction = CreditTransaction(
            user_credits_id=user_credits.id,
            transaction_type="deduction",
            amount=-credits_required,
            balance_before=user_credits.credits,
            balance_after=user_credits.credits - credits_required,
            description=f"Used {credits_required} credits for {service_name}",
            reference_id=usage_request.reference_id,
            reference_type=usage_request.reference_type,
            created_by=user_id
        )
        
        # Update user credits
        user_credits.credits -= credits_required
        user_credits.updated_at = datetime.now()
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        db.refresh(user_credits)
        
        return {
            "success": True,
            "message": f"Used {credits_required} credits for {service_name}",
            "credits_used": credits_required,
            "new_balance": user_credits.credits,
            "transaction_id": transaction.id
        }
    
    @staticmethod
    def check_sufficient_credits(
        db: Session,
        user_id: int,
        business_id: int,
        verification_options: dict
    ) -> dict:
        """Check if user has sufficient credits for verification options"""
        user_credits = CreditService.get_user_credits(db, user_id, business_id)
        pricing = CreditService.get_credit_pricing(db, business_id)
        
        total_required = CreditService.calculate_verification_cost(verification_options, pricing)
        
        return {
            "sufficient": user_credits.credits >= total_required,
            "current_balance": user_credits.credits,
            "required_credits": total_required,
            "shortfall": max(0, total_required - user_credits.credits)
        }