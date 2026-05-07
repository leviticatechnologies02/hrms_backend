from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, get_user_business_id, validate_business_access
from app.models.user import User
from app.models.leave_policy import LeavePolicy
from app.schemas.leave_policy import (
    LeavePolicyCreate,
    LeavePolicyResponse,
    LeavePolicyUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[LeavePolicyResponse], summary="List leave policies (root)")
def root(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    """
    Return list of leave policies for the business.
    This enforces business isolation and mirrors `/list` behavior.
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)

    try:
        query = db.query(LeavePolicy).filter(LeavePolicy.business_id == business_id)
        policies = query.order_by(LeavePolicy.created_at.desc()).offset(skip).limit(limit).all()
        return [LeavePolicyResponse.model_validate(policy) for policy in policies]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching policies: {str(e)}")


@router.post("/", response_model=LeavePolicyResponse, status_code=201)
def create_leave_policy(
    policy: LeavePolicyCreate,
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Create a leave policy for a business.
    
    **Security**: Business isolation enforced
    - Uses user's business_id from get_user_business_id()
    - Works for both business owners and employees
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_admin, db)
        
        existing = db.query(LeavePolicy).filter(
            LeavePolicy.leave_type == policy.leave_type,
            LeavePolicy.business_id == business_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Leave policy for '{policy.leave_type}' already exists for this business")

        db_policy = LeavePolicy(
            business_id=business_id,
            leave_type=policy.leave_type,
            policy_name=policy.policy_name,
            description=policy.description,
            grant_enabled=policy.grant_enabled,
            grant_condition=policy.grant_condition,
            monthly_grant_leaves=policy.monthly_grant_leaves,
            reset_negative_balance=policy.reset_negative_balance,
            lapse_enabled=policy.lapse_enabled,
            monthly_lapse_limits=policy.monthly_lapse_limits,
            do_not_apply_during_probation=policy.do_not_apply_during_probation,
            do_not_apply_after_probation=policy.do_not_apply_after_probation,
            auto_apply=policy.auto_apply,
        )

        db.add(db_policy)
        db.commit()
        db.refresh(db_policy)

        return LeavePolicyResponse.model_validate(db_policy)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating policy: {str(e)}")


@router.get("/list", response_model=List[LeavePolicyResponse])
def get_all_leave_policies(
    business_id: int = Path(...),
    leave_type: Optional[str] = None,
    grant_enabled: Optional[bool] = None,
    lapse_enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get all leave policies for user's business.
    
    **Security**: Business isolation enforced
    - Ignores business_id parameter from frontend
    - Always uses user's business_id from get_user_business_id()
    - Returns only policies for user's business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    try:
        # Filter by business_id
        query = db.query(LeavePolicy).filter(LeavePolicy.business_id == business_id)
        
        if leave_type:
            query = query.filter(LeavePolicy.leave_type.ilike(f"%{leave_type}%"))
        if grant_enabled is not None:
            query = query.filter(LeavePolicy.grant_enabled == grant_enabled)
        if lapse_enabled is not None:
            query = query.filter(LeavePolicy.lapse_enabled == lapse_enabled)
        
        policies = query.order_by(LeavePolicy.created_at.desc()).offset(skip).limit(limit).all()
        return [LeavePolicyResponse.model_validate(policy) for policy in policies]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching policies: {str(e)}")


@router.get("/{policy_id}", response_model=LeavePolicyResponse)
def get_leave_policy(
    policy_id: int = Path(...),
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get a specific leave policy.
    
    **Security**: Business isolation enforced
    - Only returns policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    # Query with business isolation
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.id == policy_id,
        LeavePolicy.business_id == business_id
    ).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    
    return LeavePolicyResponse.model_validate(policy)


@router.get("/type/{leave_type}", response_model=LeavePolicyResponse)
def get_leave_policy_by_type(
    leave_type: str,
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get a leave policy by leave type.
    
    **Security**: Business isolation enforced
    - Only returns policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.leave_type == leave_type,
        LeavePolicy.business_id == business_id
    ).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail=f"Leave policy for '{leave_type}' not found for this business")
    
    return LeavePolicyResponse.model_validate(policy)


@router.put("/{policy_id}", response_model=LeavePolicyResponse)
def update_leave_policy(
    policy_id: int = Path(...),
    business_id: int = Path(...),
    policy: LeavePolicyUpdate = ...,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Update a leave policy.
    
    **Security**: Business isolation enforced
    - Only updates policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_admin, db)
        
        # Query with business isolation
        db_policy = db.query(LeavePolicy).filter(
            LeavePolicy.id == policy_id,
            LeavePolicy.business_id == business_id
        ).first()
        
        if not db_policy:
            raise HTTPException(status_code=404, detail="Leave policy not found")

        # Check for duplicate leave_type if changing
        if db_policy.leave_type != policy.leave_type:
            existing = db.query(LeavePolicy).filter(
                LeavePolicy.leave_type == policy.leave_type,
                LeavePolicy.business_id == business_id,
                LeavePolicy.id != policy_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Leave policy for '{policy.leave_type}' already exists")

        db_policy.leave_type = policy.leave_type
        db_policy.policy_name = policy.policy_name
        db_policy.description = policy.description
        db_policy.grant_enabled = policy.grant_enabled
        db_policy.grant_condition = policy.grant_condition
        db_policy.monthly_grant_leaves = policy.monthly_grant_leaves
        db_policy.reset_negative_balance = policy.reset_negative_balance
        db_policy.lapse_enabled = policy.lapse_enabled
        db_policy.monthly_lapse_limits = policy.monthly_lapse_limits
        db_policy.do_not_apply_during_probation = policy.do_not_apply_during_probation
        db_policy.do_not_apply_after_probation = policy.do_not_apply_after_probation
        db_policy.auto_apply = policy.auto_apply
        db_policy.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(db_policy)
        return LeavePolicyResponse.model_validate(db_policy)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating policy: {str(e)}")


@router.delete("/{policy_id}", status_code=200)
def delete_leave_policy(
    policy_id: int = Path(...),
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Delete a leave policy.
    
    **Security**: Business isolation enforced
    - Only deletes policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    try:
        # Validate business access
        validate_business_access(business_id, current_admin, db)
        
        # Query with business isolation
        policy = db.query(LeavePolicy).filter(
            LeavePolicy.id == policy_id,
            LeavePolicy.business_id == business_id
        ).first()
        
        if not policy:
            raise HTTPException(status_code=404, detail="Leave policy not found")
        
        leave_type = policy.leave_type
        db.delete(policy)
        db.commit()
        return {"message": "Leave policy deleted successfully", "id": policy_id, "leave_type": leave_type}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting policy: {str(e)}")


@router.post("/{policy_id}/calculate-grant")
def calculate_monthly_grant(
    policy_id: int = Path(...),
    business_id: int = Path(...),
    presents_count: int = Query(..., ge=0),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Calculate monthly grant for a leave policy.
    
    **Security**: Business isolation enforced
    - Only calculates for policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    # Query with business isolation
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.id == policy_id,
        LeavePolicy.business_id == business_id
    ).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    
    if not policy.grant_enabled:
        return {"grant_eligible": False, "reason": "Grant is not enabled for this policy", "leaves_to_grant": 0}
    if presents_count >= policy.grant_condition:
        leaves_to_grant = policy.monthly_grant_leaves[month - 1]
        return {"grant_eligible": True, "reason": f"Presents ({presents_count}) >= Required ({policy.grant_condition})", "leaves_to_grant": leaves_to_grant, "month": month}
    else:
        return {"grant_eligible": False, "reason": f"Presents ({presents_count}) < Required ({policy.grant_condition})", "leaves_to_grant": 0, "month": month}


@router.post("/{policy_id}/check-lapse")
def check_lapse_eligibility(
    policy_id: int = Path(...),
    business_id: int = Path(...),
    current_balance: float = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Check lapse eligibility for a leave policy.
    
    **Security**: Business isolation enforced
    - Only checks for policy if it belongs to user's business
    - Returns 404 if policy belongs to different business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    # Query with business isolation
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.id == policy_id,
        LeavePolicy.business_id == business_id
    ).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    
    if not policy.lapse_enabled:
        return {"lapse_eligible": False, "reason": "Lapse is not enabled for this policy", "leaves_to_lapse": 0}
    lapse_limit = policy.monthly_lapse_limits[month - 1]
    if current_balance > lapse_limit:
        leaves_to_lapse = current_balance - lapse_limit
        return {"lapse_eligible": True, "reason": f"Balance ({current_balance}) exceeds limit ({lapse_limit})", "leaves_to_lapse": leaves_to_lapse, "remaining_balance": lapse_limit, "month": month}
    else:
        return {"lapse_eligible": False, "reason": f"Balance ({current_balance}) within limit ({lapse_limit})", "leaves_to_lapse": 0, "remaining_balance": current_balance, "month": month}


@router.get("/stats/summary")
def get_policies_summary(
    business_id: int = Path(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get policies summary statistics for user's business.
    
    **Security**: Business isolation enforced
    - Always uses user's business_id from get_user_business_id()
    - Returns only stats for user's business
    """
    # Validate business access
    validate_business_access(business_id, current_admin, db)
    
    # Always filter by user's business
    query = db.query(LeavePolicy).filter(LeavePolicy.business_id == business_id)
    
    total_policies = query.count()
    grant_enabled_count = query.filter(LeavePolicy.grant_enabled == True).count()
    lapse_enabled_count = query.filter(LeavePolicy.lapse_enabled == True).count()
    auto_apply_count = query.filter(LeavePolicy.auto_apply == True).count()
    
    return {"total_policies": total_policies, "grant_enabled": grant_enabled_count, "lapse_enabled": lapse_enabled_count, "auto_apply_enabled": auto_apply_count}
