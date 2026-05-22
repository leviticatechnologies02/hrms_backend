from sqlalchemy.orm import Session
from typing import Any, Dict, List
from app.repositories.datacapture_repository import LoanRepository, SalaryVariableRepository


class LoanService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LoanRepository(db)

    def create_loan(self, business_id: int, payload) -> Dict[str, Any]:
        loan = self.repo.create(business_id, payload)
        return {"loan_id": loan.id, "message": "created"}

    def get_loan(self, loan_id: int, business_id: int) -> Dict[str, Any]:
        loan = self.repo.get_by_id(loan_id, business_id)
        if not loan:
            raise Exception("Loan not found")
        return loan


class SalaryVariableService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SalaryVariableRepository(db)

    def list_variables(self, business_id: int) -> List[Dict]:
        vars = self.repo.list_by_business(business_id)
        return vars
