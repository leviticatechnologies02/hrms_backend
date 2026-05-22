from fastapi import APIRouter, Depends, status, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_current_admin, validate_business_access
from app.models.user import User

from app.services.setup.salary_and_deductions.salary_component_service import SalaryComponentService
from app.schemas.setup.salary_and_deductions.salary_component import (
    SalaryComponentCreate,
    SalaryComponentUpdate,
    SalaryComponentOut
)

# Remove the duplicate prefix - it's already set in router.py
router = APIRouter()
service = SalaryComponentService()


# ---------------------------------------------------------
# LIST ALL COMPONENTS FOR A BUSINESS
# ---------------------------------------------------------
@router.get(
    "",
    response_model=list[SalaryComponentOut],
    summary="List all salary components for a business",
    description="Retrieve all salary components configured for a specific business"
)
def list_components(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    List all salary components for a business.
    
    - **business_id**: ID of the business
    """
    if business_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID"
        )
    # verify user has access to this business
    validate_business_access(business_id, current_user, db)
    return service.list(db, business_id)


# ---------------------------------------------------------
# GET A SINGLE COMPONENT (BUSINESS-SCOPED)
# ---------------------------------------------------------
@router.get(
    "/{component_id}",
    response_model=SalaryComponentOut,
    summary="Get salary component by ID",
    description="Retrieve a specific salary component by its ID"
)
def get_component(
    component_id: int = Path(...),
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get a single salary component.
    
    - **business_id**: ID of the business
    - **component_id**: ID of the salary component
    """
    if business_id <= 0 or component_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID or component ID"
        )
    # verify user has access to this business
    validate_business_access(business_id, current_user, db)
    return service.get(db, component_id, business_id)


# ---------------------------------------------------------
# CREATE COMPONENT (BUSINESS-SCOPED)
# ---------------------------------------------------------
@router.post(
    "",
    response_model=SalaryComponentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create salary component",
    description="Create a new salary component for a business"
)
def create_component(
    data: SalaryComponentCreate,
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Create a new salary component.
    
    Required fields:
    - **business_id**: ID of the business
    - **name**: Full name of the component
    - **alias**: Short name/code for the component
    - **component_type**: Type of component (Fixed/Variable/Deduction)
    - **unit_type**: Calculation unit (Paid Days/Fixed/Monthly)
    """
    if business_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid business ID")
    # verify user has access to this business
    validate_business_access(business_id, current_user, db)
    return service.create(db, business_id, data)


# ---------------------------------------------------------
# UPDATE COMPONENT (BUSINESS-SCOPED)
# ---------------------------------------------------------
@router.put(
    "/{component_id}",
    response_model=SalaryComponentOut,
    summary="Update salary component",
    description="Update an existing salary component"
)
def update_component(
    component_id: int = Path(...),
    business_id: int = Path(...),
    data: SalaryComponentUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Update a salary component.
    
    - **business_id**: ID of the business
    - **component_id**: ID of the salary component
    
    All fields are optional. Only provided fields will be updated.
    """
    if business_id <= 0 or component_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID or component ID"
        )
    # verify user has access to this business
    validate_business_access(business_id, current_user, db)
    return service.update(db, component_id, business_id, data)


# ---------------------------------------------------------
# DELETE COMPONENT (BUSINESS-SCOPED)
# ---------------------------------------------------------
@router.delete(
    "/{component_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete salary component",
    description="Delete a salary component (if not in use)"
)
def delete_component(
    component_id: int = Path(...),
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Delete a salary component.
    
    - **business_id**: ID of the business
    - **component_id**: ID of the salary component
    
    Note: Cannot delete if component is being used in salary structures.
    """
    if business_id <= 0 or component_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID or component ID"
        )
    # verify user has access to this business
    validate_business_access(business_id, current_user, db)
    service.delete(db, component_id, business_id)
    return {"message": "Salary component deleted successfully"}
