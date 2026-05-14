from typing import Dict
from sqlalchemy.orm import Session
from app.models.form16_models import PersonResponsible, EmployerInfo, CitInfo
from datetime import datetime


class Form16Repository:
    def __init__(self, db: Session):
        self.db = db

    # ---------- PERSON ----------
    def create_person(self, data: Dict, signature_path: str = None) -> PersonResponsible:
        pr = PersonResponsible(
            full_name=data.get("fullName") or data.get("full_name"),
            designation=data.get("designation"),
            father_name=data.get("fatherName") or data.get("father_name"),
            signature_path=signature_path,
            business_id=data.get("business_id"),
        )
        self.db.add(pr)
        self.db.commit()
        self.db.refresh(pr)
        return pr

    def update_person_signature(self, person_id: int, signature_path: str) -> PersonResponsible:
        pr = self.db.query(PersonResponsible).filter(PersonResponsible.id == person_id).first()
        if not pr:
            return None
        pr.signature_path = signature_path
        pr.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(pr)
        return pr

    # ---------- EMPLOYER ----------
    def create_employer(self, data: Dict) -> EmployerInfo:
        emp = EmployerInfo(
            name=data.get("name"),
            address1=data.get("address1"),
            address2=data.get("address2"),
            address3=data.get("address3"),
            place_of_issue=data.get("placeOfIssue") or data.get("place_of_issue"),
            business_id=data.get("business_id"),
        )
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)
        return emp

    # ---------- CIT ----------
    def create_cit(self, data: Dict) -> CitInfo:
        cit = CitInfo(
            name=data.get("name"),
            address1=data.get("address1"),
            address2=data.get("address2"),
            address3=data.get("address3"),
            business_id=data.get("business_id"),
        )
        self.db.add(cit)
        self.db.commit()
        self.db.refresh(cit)
        return cit