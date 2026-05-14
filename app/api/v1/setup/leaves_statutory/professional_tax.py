"""
Professional Tax Endpoints
API routes for Professional Tax configuration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from sqlalchemy.orm import Session
from typing import List
import logging

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, validate_business_access
from app.models.user import User
from app.schemas.professional_tax import (
    ProfessionalTaxSettingsResponse,
    ProfessionalTaxSettingsUpdate,
    PTComponentMappingCreate,
    PTComponentMappingUpdate,
    PTComponentMappingResponse,
    PTComponentBulkUpdate,
    ProfessionalTaxRateCreate,
    ProfessionalTaxRateUpdate,
    ProfessionalTaxRateResponse,
    PTRatesByStateResponse,
)
from app.services.professional_tax_service import ProfessionalTaxService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=ProfessionalTaxSettingsResponse,
    summary="Get Professional Tax Settings"
)
def get_professional_tax_settings(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get Professional Tax settings for a business.
    Creates default settings if none exist.
    
    **Access:** ADMIN or SUPERADMIN
    """
    service = ProfessionalTaxService(db)
    settings = service.get_or_create_settings(business_id)
    
    logger.info(f"Professional Tax settings retrieved for business {business_id} by {current_user.email}")
    return settings


@router.put(
    "/{settings_id}",
    response_model=ProfessionalTaxSettingsResponse,
    summary="Update Professional Tax Settings"
)
def update_professional_tax_settings(
    business_id: int = Path(...),
    settings_id: int = Path(...),
    data: ProfessionalTaxSettingsUpdate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update Professional Tax settings (enable/disable, calculation base).
    
    **Access:** ADMIN or SUPERADMIN
    """
    service = ProfessionalTaxService(db)

    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    try:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        settings = service.update_settings(settings_id, update_dict)

        logger.info(f"Professional Tax settings {settings_id} updated for business {business_id} by {current_user.email}")
        return settings
    except Exception as e:
        logger.error(f"Error updating Professional Tax settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Component Mapping Endpoints
# ============================================================================

@router.post(
    "/{settings_id}/components",
    response_model=PTComponentMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Component Mapping"
)
def add_component_mapping(
    business_id: int = Path(...),
    settings_id: int = Path(...),
    data: PTComponentMappingCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Add a new salary component to Professional Tax calculation.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        payload = data.model_dump()
        component = service.add_component_mapping(settings_id, payload)
        logger.info(f"Component added to PT settings {settings_id} by {current_user.email}")
        return component
    except Exception as e:
        logger.error(f"Error adding component: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/components/{component_id}",
    response_model=PTComponentMappingResponse,
    summary="Update Component Mapping"
)
def update_component_mapping(
    business_id: int = Path(...),
    component_id: int = Path(...),
    data: PTComponentMappingUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update component selection status.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        component = service.update_component_mapping(component_id, update_dict)

        logger.info(f"Component {component_id} updated for business {business_id} by {current_user.email}")
        return component
    except Exception as e:
        logger.error(f"Error updating component: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/components/bulk-update",
    summary="Bulk Update Components"
)
def bulk_update_components(
    business_id: int = Path(...),
    data: PTComponentBulkUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Bulk update component selection status.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        count = service.bulk_update_components(data.component_ids, data.is_selected)
        logger.info(f"{count} components updated for business {business_id} by {current_user.email}")
        return {"updated_count": count, "message": f"{count} components updated successfully"}
    except Exception as e:
        logger.error(f"Error bulk updating components: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Tax Rate Endpoints
# ============================================================================

@router.post(
    "/{settings_id}/rates",
    response_model=ProfessionalTaxRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Professional Tax Rate"
)
def add_professional_tax_rate(
    business_id: int = Path(...),
    settings_id: int = Path(...),
    data: ProfessionalTaxRateCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Add a new Professional Tax rate slab.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        payload = data.model_dump()
        rate = service.add_tax_rate(settings_id, payload)
        logger.info(f"PT rate added to settings {settings_id} for business {business_id} by {current_user.email}")
        return rate
    except Exception as e:
        logger.error(f"Error adding PT rate: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put(
    "/rates/{rate_id}",
    response_model=ProfessionalTaxRateResponse,
    summary="Update Professional Tax Rate"
)
def update_professional_tax_rate(
    business_id: int = Path(...),
    rate_id: int = Path(...),
    data: ProfessionalTaxRateUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update an existing Professional Tax rate.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        rate = service.update_tax_rate(rate_id, update_dict)

        logger.info(f"PT rate {rate_id} updated for business {business_id} by {current_user.email}")
        return rate
    except Exception as e:
        logger.error(f"Error updating PT rate: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/rates/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Professional Tax Rate"
)
def delete_professional_tax_rate(
    business_id: int = Path(...),
    rate_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a Professional Tax rate slab.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        service.delete_tax_rate(rate_id)
        logger.info(f"PT rate {rate_id} deleted for business {business_id} by {current_user.email}")
    except Exception as e:
        logger.error(f"Error deleting PT rate: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{settings_id}/rates/by-state",
    response_model=List[ProfessionalTaxRateResponse],
    summary="Get Rates by State"
)
def get_rates_by_state(
    business_id: int = Path(...),
    settings_id: int = Path(...),
    state: str = Query(..., description="State name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get all Professional Tax rates for a specific state.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        rates = service.get_rates_by_state(settings_id, state)
        logger.info(f"PT rates for state {state} retrieved for business {business_id} by {current_user.email}")
        return rates
    except Exception as e:
        logger.error(f"Error retrieving PT rates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{settings_id}/calculate",
    summary="Calculate Professional Tax"
)
def calculate_professional_tax(
    business_id: int = Path(...),
    settings_id: int = Path(...),
    state: str = Query(..., description="State name"),
    salary: float = Query(..., ge=0, description="Salary amount"),
    month: str = Query("All Months", description="Month"),
    gender: str = Query("All Genders", description="Gender"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Calculate Professional Tax for given parameters.
    
    **Access:** ADMIN or SUPERADMIN
    """
    # Validate admin access to the business path param
    validate_business_access(business_id, current_user, db)

    service = ProfessionalTaxService(db)

    try:
        tax_amount = service.calculate_tax(settings_id, state, salary, month, gender)
        return {
            "state": state,
            "salary": salary,
            "month": month,
            "gender": gender,
            "tax_amount": tax_amount
        }
    except Exception as e:
        logger.error(f"Error calculating PT: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
