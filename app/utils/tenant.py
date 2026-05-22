from sqlalchemy.orm import Session
from fastapi import HTTPException, status

def validate_business(business_id: int, db: Session):
    """Simple business existence validator for tenant isolation.

    Raises 404 if business not found. Returns the business model instance.
    """
    from app.models.business import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    return business
