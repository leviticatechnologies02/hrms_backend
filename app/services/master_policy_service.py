"""MasterPolicy service - simple CRUD for master policies"""
from sqlalchemy.orm import Session
from typing import List
from app.models.master_policy import MasterPolicy
from datetime import datetime


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
