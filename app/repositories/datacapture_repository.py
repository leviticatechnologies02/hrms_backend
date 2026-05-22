from sqlalchemy.orm import Session
from typing import Optional, List
from app.models.datacapture import EmployeeLoan, SalaryVariable


class LoanRepository:
    """Repository example showing tenant-aware CRUD for EmployeeLoan."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, business_id: int, payload) -> EmployeeLoan:
        loan = EmployeeLoan(
            business_id=business_id,
            employee_id=payload.employee_id,
            loan_type=payload.loan_type,
            loan_amount=payload.loan_amount,
            interest_rate=payload.interest_rate,
            tenure_months=payload.tenure_months,
            emi_amount=payload.emi_amount,
            loan_date=payload.loan_date,
            first_emi_date=payload.first_emi_date,
            outstanding_amount=payload.loan_amount,
            remaining_emis=payload.tenure_months,
            created_by=payload.created_by
        )
        self.db.add(loan)
        self.db.commit()
        self.db.refresh(loan)
        return loan

    def get_by_id(self, loan_id: int, business_id: int) -> Optional[EmployeeLoan]:
        return self.db.query(EmployeeLoan).filter(
            EmployeeLoan.id == loan_id,
            EmployeeLoan.business_id == business_id
        ).first()

    def list_by_business(self, business_id: int) -> List[EmployeeLoan]:
        return self.db.query(EmployeeLoan).filter(
            EmployeeLoan.business_id == business_id
        ).all()

    def delete(self, loan_id: int, business_id: int) -> bool:
        loan = self.get_by_id(loan_id, business_id)
        if not loan:
            return False
        self.db.delete(loan)
        self.db.commit()
        return True


class SalaryVariableRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_business(self, business_id: int):
        return self.db.query(SalaryVariable).filter(SalaryVariable.business_id == business_id).all()
