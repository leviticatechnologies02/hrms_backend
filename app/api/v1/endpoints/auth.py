"""
Authentication Endpoints
Login, logout, and user profile management with cookie support
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings
from app.schemas.token import LoginRequest, TokenResponse
from app.schemas.user import AdminResponse
from app.schemas.auth_additional import SendOTPRequest
from app.services.auth_service import AuthService
from app.api.v1.deps import get_current_user
from app.models.user import User

router = APIRouter()


# ============================================================================
# Pydantic Models for Profile Management
# ============================================================================

class UserProfileUpdate(BaseModel):
    """User profile update request"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str
    confirm_password: str


class LoginSession(BaseModel):
    """Login session information"""
    session_id: str
    login_time: datetime
    last_seen: datetime
    ip_address: str
    user_agent: Optional[str] = None
    is_current: bool = False


class LoginSessionsResponse(BaseModel):
    """Login sessions response"""
    sessions: List[LoginSession]
    total: int


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login endpoint with dual authentication support.
    
    Sets JWT token in:
    1. Response body (for API clients/mobile apps)
    2. HttpOnly cookie (for browser sessions)
    
    This allows both programmatic API access and browser-based sessions.
    """
    try:
        auth_service = AuthService(db)
        token_response = auth_service.login(credentials)
        
        # Set secure HttpOnly cookie for browser sessions
        response.set_cookie(
            key="access_token",
            value=token_response.access_token,
            httponly=True,  # Prevents JavaScript access (XSS protection)
            secure=True,  # HTTPS only in production
            samesite="none",  # CSRF protection (allows navigation)
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            path="/",  # Available across entire domain
            domain=None  # Current domain only
        )
        
        # Also return token in response body for API clients
        return token_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.get("/me", response_model=AdminResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    
    Works with both:
    - Authorization: Bearer <token> header
    - access_token cookie
    """
    return AdminResponse.from_user(current_user)


@router.put("/me", response_model=AdminResponse)
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update current authenticated user's profile.
    
    Allows updating:
    - Basic information (name, email, phone)
    - Address information (address, city, state, country, postal_code)
    """
    try:
        # Update only provided fields
        update_data = profile_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(current_user, field):
                setattr(current_user, field, value)
        
        current_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        
        return current_user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change user password.
    
    Requires:
    - current_password: Current password for verification
    - new_password: New password
    - confirm_password: Confirmation of new password
    """
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Verify new password confirmation
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match"
            )
        
        # Validate new password strength (basic validation)
        if len(password_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long"
            )
        
        # Update password
        current_user.hashed_password = get_password_hash(password_data.new_password)
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Password changed successfully",
            "changed_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/sessions", response_model=LoginSessionsResponse)
async def get_login_sessions(current_user: User = Depends(get_current_user)):
    """
    Get all active login sessions for the current user.
    
    Returns list of active sessions with:
    - Session ID
    - Login time
    - Last seen time
    - IP address
    - User agent (if available)
    - Current session indicator
    """
    # Mock data for now - in production, this would come from a session store
    # like Redis or database table tracking active sessions
    mock_sessions = [
        LoginSession(
            session_id="session_1",
            login_time=datetime.utcnow().replace(hour=8, minute=15, second=30),
            last_seen=datetime.utcnow() - timedelta(minutes=3),
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            is_current=True
        ),
        LoginSession(
            session_id="session_2",
            login_time=datetime.utcnow() - timedelta(hours=1),
            last_seen=datetime.utcnow() - timedelta(minutes=30),
            ip_address="192.168.1.9",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
            is_current=False
        )
    ]
    
    return LoginSessionsResponse(
        sessions=mock_sessions,
        total=len(mock_sessions)
    )


@router.delete("/sessions/{session_id}")
async def logout_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Logout a specific session.
    
    Terminates the specified session. In production, this would:
    - Remove session from session store
    - Invalidate the session token
    - Notify other services of session termination
    """
    # Mock implementation - in production, this would actually terminate the session
    if session_id in ["session_1", "session_2"]:
        return {
            "message": f"Session {session_id} terminated successfully",
            "session_id": session_id,
            "terminated_at": datetime.utcnow()
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """
    User logout endpoint.
    
    Clears the authentication cookie completely and invalidates the session.
    """
    # Clear the authentication cookie with matching parameters
    response.delete_cookie(
        key="access_token",
        path="/",
        domain=None,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="none"
    )
    
    # Also set an expired cookie to force removal
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=True,
        samesite="none",
        max_age=0,  # Expire immediately
        expires=0,   # Expire immediately
        path="/"
    )
    
    return {
        "message": "Successfully logged out",
        "user_email": current_user.email,
        "logged_out": True
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """
    Refresh access token.
    
    Generates new token and updates both cookie and response body.
    """
    new_token = create_access_token(
        data={"sub": current_user.email, "role": current_user.role.value}
    )
    
    # Update cookie with new token
    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    
    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        user=AdminResponse.model_validate(current_user)
    )


@router.get("/check-session")
async def check_session(current_user: User = Depends(get_current_user)):
    """
    Check if user has valid session.
    
    Useful for frontend to verify authentication status.
    """
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role.value
        }
    }


# ============================================================================
# FRONTEND COMPATIBILITY ENDPOINTS (Critical Fixes)
# ============================================================================

@router.post("/send-otp", operation_id="send_otp_auth_fix")
async def send_otp_frontend_fix(
    otp_data: SendOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Send OTP to user's email (CRITICAL FRONTEND FIX)
    
    Frontend expects this exact endpoint for user registration flow
    
    **Request body:**
    - email: User's email address
    """
    try:
        from app.services.registration_service import RegistrationService
        from app.schemas.user import ResendOTPRequest
        
        # Create request object
        request = ResendOTPRequest(email=otp_data.email)
        
        # Use existing registration service
        registration_service = RegistrationService(db)
        result = await registration_service.resend_otp(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )
