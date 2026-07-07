"""
Business Endpoints
CRUD operations for business management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.core.database import get_db
from app.api.v1.deps import get_current_admin
from app.models.user import User
from app.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessResponse,
    BusinessSummary
)
from app.repositories.business_repository import BusinessRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Admin Endpoints (User's Own Businesses)
# ============================================================================

@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business"
)
def create_business(
    data: BusinessCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Create a new business for the logged-in admin.
    
    **Steps:**
    1. Validates all input data (GSTIN, PAN, etc.)
    2. Checks for duplicate GSTIN
    3. Creates business record with owner_id = current user
    4. Returns created business details
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    
    # Check for duplicate GSTIN
    if data.gstin and repo.gstin_exists(data.gstin):
        logger.warning(f"Duplicate GSTIN attempt: {data.gstin}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"GSTIN '{data.gstin}' is already registered"
        )
    
    # Check for duplicate business URL
    if data.business_url and repo.business_url_exists(data.business_url):
        logger.warning(f"Duplicate business URL: {data.business_url}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business URL '{data.business_url}' is already taken"
        )
    
    # Create business
    business_dict = data.model_dump()
    business_dict["owner_id"] = current_admin.id
    business_dict["is_active"] = True
    
    new_business = repo.create(business_dict)
    
    logger.info(
        f"Business created: {new_business.business_name} "
        f"(ID: {new_business.id}, Owner: {current_admin.email})"
    )
    
    return new_business


@router.get(
    "",
    response_model=List[BusinessSummary],
    summary="List all my businesses"
)
def list_my_businesses(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records"),
    active_only: bool = Query(True, description="Show only active businesses"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get all businesses owned by the current admin.
    
    **Features:**
    - Pagination support
    - Filter active/inactive
    - Sorted by creation date (newest first)
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    businesses = repo.get_by_owner(
        owner_id=current_admin.id,
        skip=skip,
        limit=limit,
        active_only=active_only
    )
    
    logger.info(
        f"Listed {len(businesses)} businesses for {current_admin.email}"
    )
    
    return businesses


@router.get(
    "/search",
    response_model=List[BusinessSummary],
    summary="Search my businesses"
)
def search_my_businesses(
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Search businesses by name or GSTIN (owned by current admin).
    
    **Search in:**
    - Business name
    - GSTIN
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    businesses = repo.search_by_name_or_gstin(
        owner_id=current_admin.id,
        search_term=q,
        skip=skip,
        limit=limit
    )
    
    logger.info(
        f"Search '{q}' returned {len(businesses)} results for {current_admin.email}"
    )
    
    return businesses


@router.get(
    "/count",
    summary="Get my business count"
)
def count_my_businesses(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get total count of businesses owned by current admin.
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    count = repo.count_by_owner(
        owner_id=current_admin.id,
        active_only=active_only
    )
    
    return {
        "owner_id": current_admin.id,
        "owner_email": current_admin.email,
        "business_count": count,
        "active_only": active_only
    }


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Get business details"
)
def get_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get detailed information about a specific business.
    
    **Access:** ADMIN (owner only) or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    business = repo.get_by_id_and_owner(business_id, current_admin.id)
    
    if not business:
        logger.warning(
            f"Business {business_id} not found for {current_admin.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or you don't have access"
        )
    
    return business


@router.put(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Update business"
)
def update_business(
    business_id: int,
    data: BusinessUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Update an existing business.
    
    **Features:**
    - Partial updates (only send fields to change)
    - Validates GSTIN/PAN/URL uniqueness
    - Checks ownership
    
    **Access:** ADMIN (owner only) or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    
    # Get existing business
    business = repo.get_by_id_and_owner(business_id, current_admin.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or you don't have access"
        )
    
    # Check GSTIN uniqueness
    if data.gstin and data.gstin != business.gstin:
        if repo.gstin_exists(data.gstin, exclude_id=business_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"GSTIN '{data.gstin}' is already registered"
            )
    
    # Check business URL uniqueness
    if data.business_url and data.business_url != business.business_url:
        if repo.business_url_exists(data.business_url, exclude_id=business_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Business URL '{data.business_url}' is already taken"
            )
    
    # Update only provided fields
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    updated = repo.update(business, update_dict)
    
    logger.info(
        f"Business {business_id} updated by {current_admin.email}"
    )
    
    return updated


@router.patch(
    "/{business_id}/status",
    response_model=BusinessResponse,
    summary="Activate/Deactivate business"
)
def toggle_business_status(
    business_id: int,
    is_active: bool = Query(..., description="New status"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Activate or deactivate a business.
    
    **Access:** ADMIN (owner only) or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    
    business = repo.get_by_id_and_owner(business_id, current_admin.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or you don't have access"
        )
    
    updated = repo.update(business, {"is_active": is_active})
    
    logger.info(
        f"Business {business_id} {'activated' if is_active else 'deactivated'} "
        f"by {current_admin.email}"
    )
    
    return updated


@router.delete(
    "/{business_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete business"
)
def delete_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Permanently delete a business.
    
    **Warning:** This action cannot be undone!
    
    **Access:** ADMIN (owner only) or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    
    business = repo.get_by_id_and_owner(business_id, current_admin.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or you don't have access"
        )
    
    # Store info before deletion
    business_name = business.business_name
    
    # Delete
    repo.delete(business_id)
    
    logger.info(
        f"Business '{business_name}' (ID: {business_id}) deleted by {current_admin.email}"
    )


# ============================================================================
# Superadmin Endpoints (All Businesses)
# ============================================================================

@router.get(
    "/admin/all",
    response_model=List[BusinessSummary],
    summary="[Admin] List all businesses"
)
def list_all_businesses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get all businesses in the system (admin or superadmin).
    
    **Features:**
    - See businesses from all users
    - Pagination
    - Filter by status
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    businesses = repo.get_all_businesses(
        skip=skip,
        limit=limit,
        active_only=active_only
    )
    
    logger.info(
        f"{current_user.email} listed {len(businesses)} businesses"
    )
    
    return businesses


@router.get(
    "/admin/state/{state}",
    response_model=List[BusinessSummary],
    summary="[Admin] Businesses by state"
)
def get_businesses_by_state(
    state: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get all businesses in a specific state.
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    businesses = repo.get_businesses_by_state(state)
    
    return businesses


@router.get(
    "/admin/plan/{plan}",
    response_model=List[BusinessSummary],
    summary="[Admin] Businesses by plan"
)
def get_businesses_by_plan(
    plan: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get all businesses on a specific subscription plan.
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    repo = BusinessRepository(db)
    businesses = repo.get_businesses_by_plan(plan)
    
    return businesses


@router.get(
    "/admin/stats",
    summary="[Admin] Business statistics"
)
def get_business_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Get overall business statistics.
    
    **Returns:**
    - Total businesses
    - Active/Inactive counts
    - Breakdown by plan
    - Breakdown by state
    
    **Access:** ADMIN or SUPERADMIN
    """
    
    from sqlalchemy import func
    from app.models.business import Business
    
    # Total counts
    total = db.query(Business).count()
    active = db.query(Business).filter(Business.is_active == True).count()
    inactive = total - active
    
    # By plan
    by_plan = (
        db.query(Business.plan, func.count(Business.id))
        .filter(Business.is_active == True)
        .group_by(Business.plan)
        .all()
    )
    
    # By state (top 10)
    by_state = (
        db.query(Business.state, func.count(Business.id))
        .filter(Business.is_active == True)
        .group_by(Business.state)
        .order_by(func.count(Business.id).desc())
        .limit(10)
        .all()
    )
    
    return {
        "total_businesses": total,
        "active_businesses": active,
        "inactive_businesses": inactive,
        "by_plan": [{"plan": p, "count": c} for p, c in by_plan],
        "top_states": [{"state": s, "count": c} for s, c in by_state]
    }