"""MasterPolicy service - simple CRUD for master policies"""
from sqlalchemy.orm import Session
from typing import List
from app.models.master_policy import MasterPolicy
from datetime import datetime
from app.models.business import Business
from app.core.exceptions import NotFoundError, ValidationError
from typing import Optional


class MasterPolicyService:
    def __init__(self, db: Session):
        self.db = db

    def create_policy(self, business_id: int, data: dict, created_by: int = None) -> MasterPolicy:
        policy = MasterPolicy(
            business_id=business_id,
            name=data.get('name'),
            description=data.get('description'),
            type=data.get('type'),
            is_mandatory=bool(data.get('is_mandatory', False)),
            requires_acknowledgment=bool(data.get('requires_acknowledgment', False)),
            file_path=data.get('file_path'),
            created_by=created_by,
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def list_policies(self, business_id: int) -> List[MasterPolicy]:
        return self.db.query(MasterPolicy).filter(MasterPolicy.business_id == business_id).order_by(MasterPolicy.id).all()

    def get_policy(self, policy_id: int, business_id: Optional[int] = None) -> Optional[MasterPolicy]:
        query = self.db.query(MasterPolicy).filter(MasterPolicy.id == policy_id)
        if business_id is not None:
            query = query.filter(MasterPolicy.business_id == business_id)
        return query.first()

    def update_policy(self, policy_id: int, business_id: int, update_data: dict, updated_by: Optional[int] = None) -> MasterPolicy:
        # Validate business exists
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise NotFoundError("Business not found")

        policy = self.get_policy(policy_id, business_id)
        if not policy:
            raise NotFoundError("Master policy not found")

        # Allowed fields to update
        allowed = {"name", "description", "type", "is_mandatory", "requires_acknowledgment", "file_path"}
        for key, val in update_data.items():
            if key in allowed:
                setattr(policy, key, val)

        if updated_by is not None:
            try:
                policy.updated_by = updated_by
            except Exception:
                # model may not have updated_by field; ignore silently
                pass

        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def delete_policy(self, policy_id: int, business_id: int, hard_delete: bool = False) -> bool:
        # Validate business exists
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise NotFoundError("Business not found")

        policy = self.get_policy(policy_id, business_id)
        if not policy:
            raise NotFoundError("Master policy not found")

        # If policy is attached to onboarding forms, do not delete without explicit hard_delete
        if policy.form_policy_mappings and len(policy.form_policy_mappings) > 0:
            raise ValidationError("Policy is attached to onboarding forms and cannot be deleted")

        # Perform delete (hard delete since model has no soft-delete flag)
        self.db.delete(policy)
        self.db.commit()
        return True
