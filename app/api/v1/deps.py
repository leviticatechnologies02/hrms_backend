"""
API Dependencies
Supports both Bearer token (header) and cookie-based authentication
"""

from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.enums import UserRole, UserStatus
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme (auto_error=False allows fallback to cookie)
security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate current user from JWT token.
    
    Authentication priority:
    1. Authorization header: Bearer <token> (API clients)
    2. Cookie: access_token (Browser sessions)
    
    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header (optional)
        access_token: JWT token from cookie (optional)
        db: Database session
    
    Returns:
        Authenticated User object
    
    Raises:
        HTTPException 401: If not authenticated or token invalid
        HTTPException 403: If account is not active
    """
    token = None
    auth_method = None
    
    # Priority 1: Check Authorization header (for API clients)
    if credentials and credentials.credentials:
        token = credentials.credentials
        auth_method = "Bearer header"
    
    # Priority 2: Check cookie (for browser sessions)
    elif access_token:
        token = access_token
        auth_method = "Cookie"
    
    # No authentication provided
    if not token:
        logger.warning(f"Authentication failed: No credentials provided for {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please login first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and validate token
    # Log a short, safe summary of the token for debugging (avoid full token in logs)
    try:
        token_summary = f"{token[:8]}... (len={len(token)})"
    except Exception:
        token_summary = "<unavailable>"
    logger.debug(f"Decoding token from {auth_method}: {token_summary}")

    payload = decode_access_token(token)
    if not payload:
        logger.warning(f"Authentication failed: Invalid/expired token via {auth_method}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user email from token
    email = payload.get("sub")
    if not email:
        logger.error("Token missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(email)
    
    if not user:
        logger.warning(f"User not found in database: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check account status
    if user.status != UserStatus.ACTIVE:
        logger.warning(f"Inactive account login attempt: {email} (status: {user.status.value})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value}. Contact administrator."
        )
    
    logger.debug(f"Authentication successful: {email} via {auth_method}")
    return user


def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require current user to be a superadmin.
    
    Args:
        current_user: Authenticated user
    
    Returns:
        User object if superadmin
    
    Raises:
        HTTPException 403: If user is not superadmin
    """
    if current_user.role != UserRole.SUPERADMIN:
        logger.warning(
            f"Superadmin access denied for {current_user.email} "
            f"(role: {current_user.role.value})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required"
        )
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require current user to be an admin or superadmin.
    
    Args:
        current_user: Authenticated user
    
    Returns:
        User object if admin or superadmin
    
    Raises:
        HTTPException 403: If user is not admin
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        logger.warning(
            f"Admin access denied for {current_user.email} "
            f"(role: {current_user.role.value})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user



def get_user_business_id(current_user: User, db: Session) -> int:
    """
    Get the business_id for the current user.
    
    For business owners, returns the ID of the business they own.
    For employees, returns their associated business_id.
    
    Args:
        current_user: Authenticated user
        db: Database session
    
    Returns:
        business_id (int)
    
    Raises:
        HTTPException 404: If user has no associated business
    """
    from app.models.business import Business
    
    # Check if user owns a business
    business = db.query(Business).filter(Business.owner_id == current_user.id).first()
    
    if business:
        logger.debug(f"User {current_user.email} owns business: {business.id} - {business.business_name}")
        return business.id
    
    # Check if user has business_id attribute (for employees)
    if hasattr(current_user, 'business_id') and current_user.business_id:
        logger.debug(f"User {current_user.email} is employee of business: {current_user.business_id}")
        return current_user.business_id
    
    # No business association found
    logger.error(f"User {current_user.email} has no associated business")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No business associated with this user"
    )


def validate_business_access(business_id: int, current_user: User, db: Session) -> bool:
    """
    Validate that the current user has access to the specified business.
    
    Args:
        business_id: Business ID to validate access for
        current_user: Authenticated user
        db: Database session
    
    Returns:
        True if user has access
    
    Raises:
        HTTPException 403: If user doesn't have access to the business
    """
    # Superadmins have unrestricted access
    if getattr(current_user, 'role', None) == UserRole.SUPERADMIN:
        return True

    user_business_id = get_user_business_id(current_user, db)

    if user_business_id != business_id:
        logger.warning(
            f"Business access denied: User {current_user.email} "
            f"(business_id: {user_business_id}) attempted to access business_id: {business_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to access this business data"
        )
    
    return True
