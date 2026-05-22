"""
Separation API Endpoints - Clean Working Version
Essential endpoints for frontend integration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta

from app.core.database import get_db
from app.api.v1.deps import get_current_admin, validate_business_access
from app.models.user import User
from app.models.employee import Employee
from app.models.separation import SeparationRequest, SeparationType, SeparationStatus, SeparationClearance, ClearanceStatus, RehireRequest, RehireOfferStatus
from app.models.department import Department
from app.models.designations import Designation
from app.schemas.separation import (
    SeparationRequestCreate, SeparationRequestResponse,
    SeparationApprovalRequest, SeparationRejectionRequest,
    SeparationActionRequest, SeparationActionResponse,
    RehireRequestCreate, RehireResponse
)
from app.services.separation_service import SeparationService

router = APIRouter(
    tags=['Separation']
)


# ============================================================================
# ESSENTIAL FRONTEND ENDPOINTS
# ============================================================================

@router.get("/exit-reasons")
async def get_exit_reasons(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get list of exit reasons for dropdown from database"""
    try:
        from app.models.exit_reason import ExitReason

        validate_business_access(business_id, current_user, db)

        # Get exit reasons for this business
        query = db.query(ExitReason).filter(ExitReason.business_id == business_id)
        
        exit_reasons = query.all()
        
        # Format for frontend dropdown (compatible with existing frontend code)
        result = []
        
        # Add standard separation types first
        standard_reasons = [
            {"id": "resignation", "name": "Resignation", "value": "resignation", "label": "Resignation"},
            {"id": "termination", "name": "Termination", "value": "termination", "label": "Termination"},
            {"id": "retirement", "name": "Retirement", "value": "retirement", "label": "Retirement"},
            {"id": "end_of_contract", "name": "End of Contract", "value": "end_of_contract", "label": "End of Contract"},
            {"id": "layoff", "name": "Layoff", "value": "layoff", "label": "Layoff"},
            {"id": "mutual_separation", "name": "Mutual Separation", "value": "mutual_separation", "label": "Mutual Separation"}
        ]
        
        result.extend(standard_reasons)
        
        # Add custom exit reasons from database
        for reason in exit_reasons:
            result.append({
                "id": reason.id,
                "name": reason.name,
                "value": reason.name.lower().replace(" ", "_"),
                "label": reason.name,
                "esi_mapping": reason.esi_mapping
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch exit reasons: {str(e)}"
        )


@router.get("/employees/search")
async def search_employees_for_separation(
    business_id: int,
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Search for active employees for separation initiation"""
    try:
        validate_business_access(business_id, current_user, db)

        # Search for active employees within the business
        search_term = f"%{q}%"
        query = db.query(Employee).filter(
            or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.employee_code.ilike(search_term)
            ),
            Employee.is_active == True,
            Employee.business_id == business_id
        )

        employees = query.limit(50).all()
        
        result = []
        for emp in employees:
            # Check if employee already has pending separation
            has_pending = db.query(SeparationRequest).filter(
                and_(
                    SeparationRequest.employee_id == emp.id,
                    SeparationRequest.business_id == business_id,
                    SeparationRequest.status.in_([
                        SeparationStatus.INITIATED,
                        SeparationStatus.PENDING_APPROVAL,
                        SeparationStatus.APPROVED,
                        SeparationStatus.IN_PROGRESS
                    ])
                )
            ).first()
            
            result.append({
                "id": emp.id,
                "employee_code": emp.employee_code,
                "full_name": emp.full_name,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "mobile": emp.mobile,
                "department_name": emp.department.name if emp.department else None,
                "designation_name": emp.designation.name if emp.designation else None,
                "date_of_joining": emp.date_of_joining.isoformat() if emp.date_of_joining else None,
                "has_pending_separation": bool(has_pending),
                "profile_image": "/assets/img/users/user-01.jpg"
            })
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search employees: {str(e)}"
        )


@router.get("/employees/{employee_id}/details")
async def get_employee_details_for_separation(
    business_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get employee details for separation form"""
    try:
        validate_business_access(business_id, current_user, db)

        query = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.is_active == True,
            Employee.business_id == business_id
        )

        employee = query.first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Check if employee already has pending separation
        has_pending = db.query(SeparationRequest).filter(
            and_(
                SeparationRequest.employee_id == employee_id,
                SeparationRequest.business_id == business_id,
                SeparationRequest.status.in_([
                    SeparationStatus.INITIATED,
                    SeparationStatus.PENDING_APPROVAL,
                    SeparationStatus.APPROVED,
                    SeparationStatus.IN_PROGRESS
                ])
            )
        ).first()
        
        return {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "mobile": employee.mobile,
            "department_name": employee.department.name if employee.department else None,
            "designation_name": employee.designation.name if employee.designation else None,
            "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
            "has_pending_separation": bool(has_pending),
            "profile_image": "/assets/img/users/user-01.jpg"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get employee details: {str(e)}"
        )


@router.post("/initiate", response_model=SeparationRequestResponse)
async def initiate_separation(
    business_id: int,
    separation_request: SeparationRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Initiate Employee Separation Request
    
    Creates a new separation request for an employee with comprehensive validation
    and automatic clearance item creation.
    
    **Request Body Requirements:**
    - employee_id: Valid active employee ID
    - separation_type: One of resignation, termination, retirement, end_of_contract, layoff, mutual_separation
    - request_date: Date when separation was requested (cannot be future date)
    - last_working_date: Employee's last working day (must be after request_date)
    - reason: Detailed reason for separation (10-1000 characters)
    - initiated_by: Who initiated the separation (employee, manager, hr, admin)
    - notice_period_days: Notice period in days (0-365)
    
    **Business Rules:**
    - Employee must exist and be active
    - Employee cannot have existing pending separation
    - Last working date must be after request date
    - Notice period cannot exceed 365 days
    - Reason must be between 10-1000 characters
    
    **Auto-Generated Features:**
    - Creates default clearance items (IT, HR, Finance, Admin)
    - Sets initial status to 'initiated'
    - Records initiator information
    - Generates timestamps
    
    **Returns:**
    - Complete separation request details
    - Employee information
    - Available actions
    - Timestamps and status
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Initialize separation service
        separation_service = SeparationService(db)
        
        # Create separation request using service layer
        separation_response = separation_service.create_separation_request(
            separation_data=separation_request,
            business_id=business_id,
            initiated_by_user=current_user.id
        )
        
        return separation_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate separation: {str(e)}"
        )


@router.get("/pending")
async def get_pending_separations(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get pending separations in frontend table format"""
    try:
        validate_business_access(business_id, current_user, db)

        # Get pending separations for this business
        pending_statuses = [
            SeparationStatus.INITIATED,
            SeparationStatus.PENDING_APPROVAL,
            SeparationStatus.IN_PROGRESS,
            SeparationStatus.APPROVED
        ]

        query = db.query(SeparationRequest).filter(
            SeparationRequest.status.in_(pending_statuses),
            SeparationRequest.business_id == business_id
        )

        separations = query.order_by(desc(SeparationRequest.created_at)).all()
        
        # Format for frontend table
        formatted_separations = []
        for sep in separations:
            # Get employee details scoped to business
            employee = db.query(Employee).filter(Employee.id == sep.employee_id, Employee.business_id == business_id).first()
            
            if employee:
                formatted_separations.append({
                    "id": sep.id,
                    "employee": {
                        "name": employee.full_name,
                        "code": employee.employee_code,
                        "department": employee.department.name if employee.department else "N/A",
                        "designation": employee.designation.name if employee.designation else "N/A",
                        "profile_image": "/assets/img/users/user-01.jpg"
                    },
                    "exit_info": {
                        "request_date": sep.request_date.strftime("%b %d, %Y") if sep.request_date else "N/A",
                        "last_working_date": sep.last_working_date.strftime("%b %d, %Y") if sep.last_working_date else "N/A",
                        "status": sep.status.value.replace("_", " ").title(),
                        "notice_period": f"{sep.notice_period_days} days" if sep.notice_period_days else "0 days"
                    },
                    "exit_reason": {
                        "type": sep.separation_type.value.replace("_", " ").title(),
                        "reason": sep.reason or "No reason provided",
                        "initiated_by": sep.initiated_by or "System"
                    },
                    "actions": {
                        "can_approve": sep.status.value in ["initiated", "pending_approval"],
                        "can_reject": sep.status.value in ["initiated", "pending_approval"],
                        "can_view": True,
                        "can_edit": sep.status.value in ["initiated"],
                        "can_delete": sep.status.value in ["initiated"]
                    },
                    # Flat structure for easy access
                    "employee_name": employee.full_name,
                    "employee_code": employee.employee_code,
                    "department_name": employee.department.name if employee.department else "N/A",
                    "designation_name": employee.designation.name if employee.designation else "N/A",
                    "separation_type": sep.separation_type.value.replace("_", " ").title(),
                    "status": sep.status.value.replace("_", " ").title(),
                    "request_date": sep.request_date.strftime("%b %d, %Y") if sep.request_date else "N/A",
                    "last_working_date": sep.last_working_date.strftime("%b %d, %Y") if sep.last_working_date else "N/A",
                    "reason": sep.reason or "No reason provided",
                    "initiated_by": sep.initiated_by or "System",
                    "created_at": sep.created_at.isoformat() if sep.created_at else None
                })
        
        return formatted_separations
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending separations: {str(e)}"
        )


@router.get("/ex-employees")
async def get_ex_employees(
    business_id: int,
    page: int = 1,
    size: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get ex-employees in frontend table format"""
    try:
        validate_business_access(business_id, current_user, db)

        # Get ex-employees (completed separations) for this business
        query = db.query(SeparationRequest).filter(
            SeparationRequest.status == SeparationStatus.COMPLETED,
            SeparationRequest.business_id == business_id
        )

        separations = query.order_by(desc(SeparationRequest.completed_at)).all()
        
        # Format for frontend table - Frontend expects flat structure
        formatted_employees = []
        for sep in separations:
            employee = db.query(Employee).filter(Employee.id == sep.employee_id, Employee.business_id == business_id).first()
            
            if employee:
                formatted_employees.append({
                    "id": employee.id,
                    "employee_code": employee.employee_code,
                    "full_name": employee.full_name,
                    "email": employee.email or "N/A",
                    "department_name": employee.department.name if employee.department else "N/A",
                    "designation_name": employee.designation.name if employee.designation else "N/A",
                    "date_of_joining": employee.date_of_joining.strftime("%b %d, %Y") if employee.date_of_joining else "N/A",
                    "date_of_termination": sep.actual_separation_date.strftime("%b %d, %Y") if sep.actual_separation_date else sep.last_working_date.strftime("%b %d, %Y") if sep.last_working_date else "N/A",
                    "separation_type": sep.separation_type.value.replace("_", " ").title(),
                    "separation_reason": sep.reason or "No reason provided",
                    "final_settlement_amount": float(sep.final_settlement_amount) if sep.final_settlement_amount else None,
                    "profile_image": "/assets/img/users/user-01.jpg",
                    # Additional nested structure for compatibility
                    "employee": {
                        "name": employee.full_name,
                        "code": employee.employee_code,
                        "department": employee.department.name if employee.department else "N/A",
                        "designation": employee.designation.name if employee.designation else "N/A",
                        "email": employee.email or "N/A",
                        "profile_image": "/assets/img/users/user-01.jpg"
                    },
                    "exit_info": {
                        "joining_date": employee.date_of_joining.strftime("%b %d, %Y") if employee.date_of_joining else "N/A",
                        "termination_date": sep.actual_separation_date.strftime("%b %d, %Y") if sep.actual_separation_date else sep.last_working_date.strftime("%b %d, %Y") if sep.last_working_date else "N/A",
                        "status": "Completed",
                        "final_settlement": f"₹{sep.final_settlement_amount:,.2f}" if sep.final_settlement_amount else "N/A"
                    },
                    "exit_reason": {
                        "type": sep.separation_type.value.replace("_", " ").title(),
                        "reason": sep.reason or "No reason provided"
                    },
                    "actions": {
                        "can_view": True,
                        "can_download_documents": True,
                        "can_rehire": True
                    }
                })
        
        return {
            "employees": formatted_employees,
            "total": len(formatted_employees),
            "page": page,
            "size": size,
            "pages": 1
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ex-employees: {str(e)}"
        )


@router.post("/{separation_id}/approve", response_model=SeparationActionResponse)
async def approve_separation(
    business_id: int,
    separation_id: int,
    approval_request: SeparationApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Approve Separation Request
    
    Approves a pending separation request with comprehensive validation and processing.
    
    **Path Parameters:**
    - separation_id: ID of the separation request to approve
    
    **Request Body:**
    - notes: Optional admin notes for the approval
    - actual_separation_date: Actual separation date (if different from planned)
    - final_settlement_amount: Final settlement amount to be paid
    - pending_dues: Any pending dues from employee
    - recovery_amount: Amount to be recovered from employee
    - hr_notes: Additional HR notes
    - auto_complete_clearances: Whether to auto-complete mandatory clearances
    - send_notifications: Whether to send approval notifications
    
    **Business Rules:**
    - Only initiated or pending_approval separations can be approved
    - Actual separation date cannot be in future
    - Settlement amounts must be non-negative
    - Admin role required for approval
    
    **Auto-Processing:**
    - Updates separation status to 'approved'
    - Records approval timestamp and approver
    - Optionally completes mandatory clearances
    - Sends notifications if enabled
    - Calculates next steps in the process
    
    **Returns:**
    - Success confirmation with updated status
    - Next steps in the separation process
    - Timestamp and action details
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Initialize separation service
        separation_service = SeparationService(db)
        
        # Convert approval request to action request for service compatibility
        action_data = SeparationActionRequest(
            action="approve",
            notes=approval_request.notes,
            actual_separation_date=approval_request.actual_separation_date,
            final_settlement_amount=approval_request.final_settlement_amount
        )
        
        # Use service layer for approval
        result = separation_service.approve_separation(
            separation_id=separation_id,
            action_data=action_data,
            approved_by=current_user.id,
            business_id=business_id
        )
        
        # Get the updated separation for additional processing
        separation = db.query(SeparationRequest).filter(
            SeparationRequest.id == separation_id,
            SeparationRequest.business_id == business_id
        ).first()
        
        if separation:
            # Update additional fields from approval request
            if approval_request.pending_dues is not None:
                separation.pending_dues = approval_request.pending_dues
            if approval_request.recovery_amount is not None:
                separation.recovery_amount = approval_request.recovery_amount
            if approval_request.hr_notes:
                separation.hr_notes = approval_request.hr_notes
            
            # Auto-complete clearances if requested
            if approval_request.auto_complete_clearances:
                clearances = db.query(SeparationClearance).filter(
                    SeparationClearance.separation_id == separation_id,
                    SeparationClearance.is_mandatory == True,
                    SeparationClearance.status == ClearanceStatus.PENDING
                ).all()
                
                for clearance in clearances:
                    clearance.status = ClearanceStatus.COMPLETED
                    clearance.cleared_by = current_user.id
                    clearance.cleared_at = datetime.now()
                    clearance.clearance_notes = "Auto-completed during approval"
            
            db.commit()
        
        # Define next steps based on separation type and settings
        next_steps = [
            "Employee will be notified of approval",
            "Clearance process will begin",
            "Final settlement calculation will be initiated"
        ]
        
        if separation and separation.separation_type in [SeparationType.RESIGNATION, SeparationType.RETIREMENT]:
            next_steps.append("Exit interview will be scheduled")
        
        if approval_request.auto_complete_clearances:
            next_steps.append("Mandatory clearances have been auto-completed")
        
        next_steps.extend([
            "HR will process final documentation",
            "Payroll will calculate final settlement"
        ])
        
        # Enhanced response with additional information
        return SeparationActionResponse(
            success=True,
            message="Separation request approved successfully",
            separation_id=separation_id,
            action="approve",
            timestamp=datetime.now(),
            updated_status="approved",
            next_steps=next_steps
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve separation: {str(e)}"
        )


@router.post("/{separation_id}/reject", response_model=SeparationActionResponse)
async def reject_separation(
    business_id: int,
    separation_id: int,
    rejection_request: SeparationRejectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Reject Separation Request
    
    Rejects a pending separation request with detailed reason and processing.
    
    **Path Parameters:**
    - separation_id: ID of the separation request to reject
    
    **Request Body:**
    - reason: Detailed reason for rejection (10-1000 characters)
    - notes: Optional additional admin notes
    - send_notifications: Whether to send rejection notifications
    
    **Business Rules:**
    - Only initiated or pending_approval separations can be rejected
    - Rejection reason is mandatory and must be detailed
    - Admin role required for rejection
    
    **Auto-Processing:**
    - Updates separation status to 'rejected'
    - Records rejection timestamp and rejector
    - Stores rejection reason and notes
    - Sends notifications if enabled
    - Provides guidance for next steps
    
    **Returns:**
    - Success confirmation with updated status
    - Next steps for the employee/HR
    - Timestamp and action details
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Initialize separation service
        separation_service = SeparationService(db)
        
        # Convert rejection request to action request for service compatibility
        action_data = SeparationActionRequest(
            action="reject",
            reason=rejection_request.reason,
            notes=rejection_request.notes
        )
        
        # Use service layer for rejection
        result = separation_service.reject_separation(
            separation_id=separation_id,
            action_data=action_data,
            rejected_by=current_user.id,
            business_id=business_id
        )
        
        # Define next steps for rejection
        next_steps = [
            "Employee will be notified of rejection with detailed reason",
            "Employee can address the concerns and resubmit if applicable",
            "HR will provide guidance on policy requirements",
            "Manager will discuss next steps with employee"
        ]
        
        # Enhanced response with additional information
        return SeparationActionResponse(
            success=True,
            message="Separation request rejected successfully",
            separation_id=separation_id,
            action="reject",
            timestamp=datetime.now(),
            updated_status="rejected",
            next_steps=next_steps
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject separation: {str(e)}"
        )


@router.get("/ex-employees/{employee_id}/details")
async def get_ex_employee_details(
    business_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get detailed information about an ex-employee"""
    try:
        validate_business_access(business_id, current_user, db)

        # Find the completed separation for this employee in this business
        query = db.query(SeparationRequest).filter(
            SeparationRequest.employee_id == employee_id,
            SeparationRequest.status == SeparationStatus.COMPLETED,
            SeparationRequest.business_id == business_id
        )

        separation = query.first()
        
        if not separation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ex-employee record not found"
            )
        
        # Get employee details scoped to this business
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.business_id == business_id).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        return {
            "employee": {
                "id": employee.id,
                "employee_code": employee.employee_code,
                "full_name": employee.full_name,
                "email": employee.email,
                "mobile": employee.mobile,
                "department_name": employee.department.name if employee.department else None,
                "designation_name": employee.designation.name if employee.designation else None,
                "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                "profile_image": "/assets/img/users/user-01.jpg"
            },
            "separation": {
                "id": separation.id,
                "separation_type": separation.separation_type.value,
                "status": separation.status.value,
                "request_date": separation.request_date.isoformat() if separation.request_date else None,
                "last_working_date": separation.last_working_date.isoformat() if separation.last_working_date else None,
                "actual_separation_date": separation.actual_separation_date.isoformat() if separation.actual_separation_date else None,
                "reason": separation.reason,
                "detailed_reason": separation.detailed_reason,
                "final_settlement_amount": float(separation.final_settlement_amount) if separation.final_settlement_amount else None,
                "notice_period_days": separation.notice_period_days,
                "initiated_by": separation.initiated_by,
                "completed_at": separation.completed_at.isoformat() if separation.completed_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ex-employee details: {str(e)}"
        )


@router.get("/ex-employees/{employee_id}/documents")
async def get_ex_employee_documents(
    business_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get list of documents for an ex-employee"""
    try:
        validate_business_access(business_id, current_user, db)

        # Find the completed separation for this employee in this business
        query = db.query(SeparationRequest).filter(
            SeparationRequest.employee_id == employee_id,
            SeparationRequest.status == SeparationStatus.COMPLETED,
            SeparationRequest.business_id == business_id
        )

        separation = query.first()
        
        if not separation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ex-employee record not found"
            )
        
        # Get actual documents from database
        from app.models.separation import SeparationDocument
        documents_query = db.query(SeparationDocument).filter(
            SeparationDocument.separation_id == separation.id
        ).order_by(SeparationDocument.uploaded_at.desc())
        
        documents_list = []
        for doc in documents_query.all():
            # Format file size
            file_size_str = "Unknown"
            if doc.file_size:
                if doc.file_size < 1024:
                    file_size_str = f"{doc.file_size} B"
                elif doc.file_size < 1024 * 1024:
                    file_size_str = f"{doc.file_size // 1024} KB"
                else:
                    file_size_str = f"{doc.file_size // (1024 * 1024)} MB"
            
            documents_list.append({
                "id": doc.id,
                "name": doc.document_name,
                "type": doc.document_type,
                "file_path": doc.file_path,
                "file_size": file_size_str,
                "mime_type": doc.mime_type,
                "description": doc.description,
                "is_mandatory": doc.is_mandatory,
                "is_generated": doc.is_generated,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "uploaded_by": doc.uploaded_by
            })
        
        # If no documents found in database, create sample documents for demo
        if not documents_list:
            documents_list = [
                {
                    "id": f"sample_1_{separation.id}",
                    "name": "Resignation Letter",
                    "type": "resignation_letter",
                    "file_path": f"/documents/separation/{separation.id}/resignation_letter.pdf",
                    "file_size": "245 KB",
                    "mime_type": "application/pdf",
                    "description": "Employee resignation letter",
                    "is_mandatory": True,
                    "is_generated": False,
                    "uploaded_at": separation.created_at.isoformat() if separation.created_at else None,
                    "uploaded_by": separation.initiated_by_user
                },
                {
                    "id": f"sample_2_{separation.id}",
                    "name": "Clearance Certificate",
                    "type": "clearance_certificate",
                    "file_path": f"/documents/separation/{separation.id}/clearance_certificate.pdf",
                    "file_size": "180 KB",
                    "mime_type": "application/pdf",
                    "description": "Department clearance certificate",
                    "is_mandatory": True,
                    "is_generated": True,
                    "uploaded_at": separation.completed_at.isoformat() if separation.completed_at else None,
                    "uploaded_by": separation.approved_by
                },
                {
                    "id": f"sample_3_{separation.id}",
                    "name": "Experience Letter",
                    "type": "experience_letter",
                    "file_path": f"/documents/separation/{separation.id}/experience_letter.pdf",
                    "file_size": "156 KB",
                    "mime_type": "application/pdf",
                    "description": "Employment experience letter",
                    "is_mandatory": False,
                    "is_generated": True,
                    "uploaded_at": separation.completed_at.isoformat() if separation.completed_at else None,
                    "uploaded_by": separation.approved_by
                },
                {
                    "id": f"sample_4_{separation.id}",
                    "name": "Final Settlement Statement",
                    "type": "settlement_statement",
                    "file_path": f"/documents/separation/{separation.id}/settlement_statement.pdf",
                    "file_size": "198 KB",
                    "mime_type": "application/pdf",
                    "description": "Final salary and dues settlement statement",
                    "is_mandatory": True,
                    "is_generated": True,
                    "uploaded_at": separation.completed_at.isoformat() if separation.completed_at else None,
                    "uploaded_by": separation.approved_by
                }
            ]
        
        return {
            "documents": documents_list,
            "total": len(documents_list),
            "separation_id": separation.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ex-employee documents: {str(e)}"
        )


@router.post("/ex-employees/{employee_id}/rehire", response_model=RehireResponse)
async def rehire_ex_employee(
    business_id: int,
    employee_id: int,
    rehire_request: RehireRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Initiate Rehire Process for Ex-Employee
    
    Creates a comprehensive rehire offer for an ex-employee with detailed terms,
    salary negotiation, and automated workflow processing.
    
    **Path Parameters:**
    - employee_id: ID of the ex-employee to rehire
    
    **Request Body:**
    - position_offered: Position being offered (required)
    - department_id: Department ID for new position
    - designation_id: Designation ID for new position
    - proposed_salary: Proposed salary amount
    - proposed_start_date: Proposed start date (must be future)
    - employment_type: Type of employment (permanent, contract, temporary, internship)
    - work_location: Work location details
    - reporting_manager_id: Reporting manager ID
    - rehire_reason: Detailed reason for rehiring (10-1000 characters)
    - terms_and_conditions: Special terms and conditions
    - probation_period_months: Probation period (0-12 months)
    - notice_period_days: Notice period (0-90 days)
    - benefits_package: Benefits package details
    - hr_notes: HR notes for internal use
    - send_offer_letter: Whether to send offer letter
    - auto_create_onboarding: Whether to auto-create onboarding record
    
    **Business Rules:**
    - Employee must have completed separation status
    - Employee cannot have active rehire offers
    - Proposed start date must be in future
    - Salary must be positive if provided
    - Admin role required for rehire initiation
    
    **Auto-Processing:**
    - Creates rehire request record
    - Sets offer expiration (30 days default)
    - Optionally sends offer letter
    - Generates workflow next steps
    - Records initiator and timestamps
    
    **Returns:**
    - Complete rehire offer details
    - Offer status and expiration
    - Next steps in rehire process
    - Employee and position information
    """
    try:
        validate_business_access(business_id, current_user, db)

        # Find the completed separation for this employee
        separation = db.query(SeparationRequest).filter(
            SeparationRequest.employee_id == employee_id,
            SeparationRequest.business_id == business_id,
            SeparationRequest.status == SeparationStatus.COMPLETED
        ).first()
        
        if not separation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ex-employee record not found or separation not completed"
            )
        
        # Get employee details scoped to business
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.business_id == business_id).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Check if employee already has active rehire offers
        existing_rehire = db.query(RehireRequest).filter(
            RehireRequest.employee_id == employee_id,
            RehireRequest.business_id == business_id,
            RehireRequest.offer_status.in_([
                RehireOfferStatus.PENDING,
                RehireOfferStatus.ACCEPTED
            ]),
            RehireRequest.is_active == True
        ).first()
        
        if existing_rehire:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee already has an active rehire offer"
            )
        
        # Validate department and designation if provided
        if rehire_request.department_id:
            department = db.query(Department).filter(
                Department.id == rehire_request.department_id,
                Department.business_id == business_id
            ).first()
            if not department:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Department not found"
                )
        
        if rehire_request.designation_id:
            designation = db.query(Designation).filter(
                Designation.id == rehire_request.designation_id,
                Designation.business_id == business_id
            ).first()
            if not designation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Designation not found"
                )
        
        # Calculate offer expiration (30 days from now)
        offer_expires_at = datetime.now() + timedelta(days=30)
        
        # Create rehire request
        rehire = RehireRequest(
            business_id=business_id,
            employee_id=employee_id,
            previous_separation_id=separation.id,
            position_offered=rehire_request.position_offered,
            department_id=rehire_request.department_id,
            designation_id=rehire_request.designation_id,
            reporting_manager_id=rehire_request.reporting_manager_id,
            work_location=rehire_request.work_location,
            employment_type=rehire_request.employment_type,
            proposed_salary=rehire_request.proposed_salary,
            proposed_start_date=rehire_request.proposed_start_date,
            probation_period_months=rehire_request.probation_period_months,
            notice_period_days=rehire_request.notice_period_days,
            rehire_reason=rehire_request.rehire_reason,
            terms_and_conditions=rehire_request.terms_and_conditions,
            benefits_package=rehire_request.benefits_package,
            send_offer_letter=rehire_request.send_offer_letter,
            auto_create_onboarding=rehire_request.auto_create_onboarding,
            hr_notes=rehire_request.hr_notes,
            rehire_initiated_by=current_user.id,
            offer_expires_at=offer_expires_at,
            offer_status=RehireOfferStatus.PENDING
        )
        
        db.add(rehire)
        db.commit()
        db.refresh(rehire)
        
        # Generate next steps based on configuration
        next_steps = []
        
        if rehire_request.send_offer_letter:
            next_steps.append("Offer letter will be sent to employee")
            rehire.offer_sent_at = datetime.now()
        
        next_steps.extend([
            f"Employee has 30 days to respond (expires: {offer_expires_at.strftime('%Y-%m-%d')})",
            "HR will schedule discussion call with employee",
            "Background verification will be initiated if required"
        ])
        
        if rehire_request.auto_create_onboarding:
            next_steps.append("Onboarding process will begin upon acceptance")
        
        next_steps.extend([
            "Department head will be notified of rehire offer",
            "Salary and benefits will be finalized upon acceptance",
            "New employee record will be created upon joining"
        ])
        
        # Update offer sent timestamp if applicable
        if rehire_request.send_offer_letter:
            db.commit()
        
        # Build comprehensive response
        return RehireResponse(
            success=True,
            message=f"Rehire process initiated successfully for {employee.full_name}",
            rehire_id=rehire.id,
            employee_id=employee_id,
            employee_name=employee.full_name,
            employee_code=employee.employee_code,
            position_offered=rehire_request.position_offered,
            proposed_salary=rehire_request.proposed_salary,
            proposed_start_date=rehire_request.proposed_start_date,
            employment_type=rehire_request.employment_type,
            offer_status=RehireOfferStatus.PENDING.value,
            previous_separation_id=separation.id,
            rehire_initiated_by=current_user.id,
            rehire_initiated_at=datetime.now(),
            offer_expires_at=offer_expires_at,
            next_steps=next_steps
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate rehire process: {str(e)}"
        )


@router.get("/pending/{separation_id}/details")
async def get_pending_separation_details(
    business_id: int,
    separation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get detailed information about a pending separation request"""
    try:
        validate_business_access(business_id, current_user, db)

        # Find the separation request for this business
        query = db.query(SeparationRequest).filter(
            SeparationRequest.id == separation_id,
            SeparationRequest.status.in_([
                SeparationStatus.INITIATED,
                SeparationStatus.PENDING_APPROVAL,
                SeparationStatus.IN_PROGRESS,
                SeparationStatus.APPROVED
            ]),
            SeparationRequest.business_id == business_id
        )

        separation = query.first()
        
        if not separation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending separation request not found"
            )
        
        # Get employee details scoped to business
        employee = db.query(Employee).filter(Employee.id == separation.employee_id, Employee.business_id == business_id).first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Get initiator details
        initiator = db.query(User).filter(User.id == separation.initiated_by_user).first()
        
        return {
            "separation": {
                "id": separation.id,
                "separation_type": separation.separation_type.value,
                "status": separation.status.value,
                "request_date": separation.request_date.isoformat() if separation.request_date else None,
                "last_working_date": separation.last_working_date.isoformat() if separation.last_working_date else None,
                "reason": separation.reason,
                "detailed_reason": separation.detailed_reason,
                "notice_period_days": separation.notice_period_days,
                "initiated_by": separation.initiated_by,
                "created_at": separation.created_at.isoformat() if separation.created_at else None,
                "updated_at": separation.updated_at.isoformat() if separation.updated_at else None,
                "admin_notes": separation.admin_notes,
                "hr_notes": separation.hr_notes
            },
            "employee": {
                "id": employee.id,
                "employee_code": employee.employee_code,
                "full_name": employee.full_name,
                "email": employee.email,
                "mobile": employee.mobile,
                "department_name": employee.department.name if employee.department else None,
                "designation_name": employee.designation.name if employee.designation else None,
                "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                "profile_image": "/assets/img/users/user-01.jpg"
            },
            "initiator": {
                "name": f"{initiator.first_name} {initiator.last_name}" if initiator and hasattr(initiator, 'first_name') else initiator.email if initiator else "System",
                "email": initiator.email if initiator else None
            },
            "actions": {
                "can_approve": separation.status.value in ["initiated", "pending_approval"],
                "can_reject": separation.status.value in ["initiated", "pending_approval"],
                "can_edit": separation.status.value in ["initiated"],
                "can_delete": separation.status.value in ["initiated"]
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending separation details: {str(e)}"
        )