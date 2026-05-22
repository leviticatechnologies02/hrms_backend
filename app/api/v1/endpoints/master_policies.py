"""Master Policies endpoints (business-scoped)
POST /api/v1/{business_id}/master/policies
GET  /api/v1/{business_id}/master/policies
POST /api/v1/{business_id}/master/policies/upload
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Path
from sqlalchemy.orm import Session
from typing import List
import os

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, get_current_user
from app.schemas.master_setup import MasterPolicyCreate, MasterPolicyResponse
from app.services.master_policy_service import MasterPolicyService
from app.services.file_upload_service import save_upload

router = APIRouter()


@router.post("/{business_id}/master/policies", response_model=MasterPolicyResponse)
async def create_master_policy(
    business_id: int = Path(..., description="Business ID"),
    payload: MasterPolicyCreate = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    try:
        # Validate business exists
        from app.models.business import Business
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        service = MasterPolicyService(db)
        data = payload.model_dump() if hasattr(payload, 'model_dump') else payload.__dict__
        policy = service.create_policy(business_id, data, created_by=current_user.id)
        return policy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{business_id}/master/policies", response_model=List[MasterPolicyResponse])
async def list_master_policies(
    business_id: int = Path(..., description="Business ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        # Validate business exists
        from app.models.business import Business
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        service = MasterPolicyService(db)
        return service.list_policies(business_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{business_id}/master/policies/upload", response_model=dict)
async def upload_policy_file(
    business_id: int = Path(..., description="Business ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    try:
        # Validate business exists
        from app.models.business import Business
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        # Compute dest folder: uploads/business_{id}/policies
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        dest_folder = os.path.join(project_root, 'uploads', f'business_{business_id}', 'policies')

        original, saved_path = save_upload(file, dest_folder)

        # Build response path (web path)
        web_path = saved_path.replace(project_root.replace('\\', '/'), '').replace('\\', '/')
        if not web_path.startswith('/'):
            web_path = '/' + web_path

        return {
            "message": "File uploaded successfully",
            "file_name": original,
            "file_path": web_path
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
