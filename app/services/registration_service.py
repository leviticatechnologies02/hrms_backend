"""
User Registration Service
Handles admin self-registration with OTP email verification
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging
import asyncio
from datetime import datetime, timezone

from app.models.user import User
from app.schemas.user import (
    UnifiedRegistrationRequest,
    UserRegistrationResponse,
    UserResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    ResendOTPRequest,
    SetPasswordRequest,
    SetPasswordResponse,
)
from app.schemas.enums import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash
from app.core.otp import otp_manager
from app.core.config import settings
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


def _email_send_timeout_seconds() -> int:
    """Use a sane minimum timeout so Gmail SMTP handshakes can complete."""
    configured_timeout = int(getattr(settings, "EMAIL_SEND_TIMEOUT", 30) or 30)
    smtp_timeout = int(getattr(settings, "SMTP_TIMEOUT", 30) or 30)
    return max(configured_timeout, smtp_timeout, 15)


class RegistrationService:
    """
    Handles admin self-registration with email verification.
    
    Important: Only ADMIN users can register.
    SUPERADMIN is created only via database initialization.
    
    Flow:
        1. Admin submits registration (no password yet)
        2. Generate and send OTP via email
        3. Admin verifies OTP
        4. Admin creates password
        5. Account is ready for login
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def register_unified(
        self,
        registration_data: UnifiedRegistrationRequest
    ) -> UserRegistrationResponse:
        """
        Register a new admin user or continue incomplete registration.
        
        Behavior:
        - If email is fully registered -> 409 Conflict
        - If email exists but is not verified -> regenerate OTP and resend
        - If email exists, verified, but password not set -> ask user to set password
        - If mobile belongs to another account -> 409 Conflict
        """
        try:
            existing_user = self.user_repo.get_by_email(registration_data.email)

            # -----------------------------------------------------------------
            # Case 1: User with this email already exists
            # -----------------------------------------------------------------
            if existing_user:
                # Fully completed registration
                if existing_user.is_email_verified and existing_user.hashed_password:
                    logger.warning(
                        f"Registration failed: Email already fully registered - {registration_data.email}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Email '{registration_data.email}' is already registered. Please login."
                    )

                # Check if mobile belongs to some OTHER user
                mobile_owner = self.db.query(User).filter(
                    User.mobile == registration_data.mobile,
                    User.id != existing_user.id
                ).first()

                if mobile_owner:
                    logger.warning(
                        f"Registration failed: Mobile exists on another account - {registration_data.mobile}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Mobile number '{registration_data.mobile}' is already registered."
                    )

                # Update incomplete user details
                full_name = f"{registration_data.first_name} {registration_data.last_name}"
                existing_user.name = full_name
                existing_user.mobile = registration_data.mobile

                # Email not verified yet -> regenerate OTP and resend
                if not existing_user.is_email_verified:
                    otp = otp_manager.generate_otp()
                    existing_user.email_otp = otp
                    existing_user.otp_created_at = datetime.now(timezone.utc)
                    existing_user.otp_attempts = 0
                    existing_user.role = UserRole.ADMIN
                    existing_user.status = UserStatus.ACTIVE

                    self.db.commit()
                    self.db.refresh(existing_user)

                    try:
                        await asyncio.wait_for(
                            email_service.send_otp_email(
                                user_email=existing_user.email,
                                user_name=full_name,
                                otp=otp
                            ),
                            timeout=_email_send_timeout_seconds()
                        )
                        logger.info(f"OTP re-sent during re-registration: {existing_user.email}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Email sending timed out for {existing_user.email}")
                    except Exception as email_error:
                        logger.error(f"Email error for {existing_user.email}: {str(email_error)}")

                    return UserRegistrationResponse(
                        message=(
                            f"Registration already exists but email is not verified. "
                            f"A new 6-digit verification code has been sent to {existing_user.email}. "
                            "Please check your inbox."
                        ),
                        user=UserResponse.model_validate(existing_user)
                    )

                # Email verified, but password not set yet
                if existing_user.is_email_verified and not existing_user.hashed_password:
                    self.db.commit()
                    self.db.refresh(existing_user)

                    logger.info(
                        f"Registration continued: Email already verified, password pending - {existing_user.email}"
                    )

                    return UserRegistrationResponse(
                        message=(
                            f"Email {existing_user.email} is already verified. "
                            "Please create your password to complete registration."
                        ),
                        user=UserResponse.model_validate(existing_user)
                    )

            # -----------------------------------------------------------------
            # Case 2: Fresh registration
            # -----------------------------------------------------------------
            if self.user_repo.mobile_exists(registration_data.mobile):
                logger.warning(f"Registration failed: Mobile exists - {registration_data.mobile}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mobile number '{registration_data.mobile}' is already registered."
                )

            otp = otp_manager.generate_otp()
            otp_created_at = datetime.now(timezone.utc)
            full_name = f"{registration_data.first_name} {registration_data.last_name}"

            user_data = {
                "name": full_name,
                "email": registration_data.email,
                "mobile": registration_data.mobile,
                "hashed_password": None,
                "role": UserRole.ADMIN,
                "status": UserStatus.ACTIVE,
                "is_email_verified": False,
                "email_otp": otp,
                "otp_created_at": otp_created_at,
                "otp_attempts": 0,
                "currency": "USD",
                "language": "English",
            }

            new_user = self.user_repo.create(user_data)
            logger.info(
                f"Admin registered (pending verification): {new_user.email} "
                f"(ID: {new_user.id}, Role: {new_user.role.value})"
            )

            try:
                await asyncio.wait_for(
                    email_service.send_otp_email(
                        user_email=new_user.email,
                        user_name=full_name,
                        otp=otp
                    ),
                    timeout=_email_send_timeout_seconds()
                )
                logger.info(f"OTP email sent to {new_user.email}")
            except asyncio.TimeoutError:
                logger.warning(f"Email sending timed out for {new_user.email}")
            except Exception as email_error:
                logger.error(f"Email error for {new_user.email}: {str(email_error)}")

            return UserRegistrationResponse(
                message=(
                    f"Admin registration successful! "
                    f"A 6-digit verification code has been sent to {new_user.email}. "
                    "Please check your inbox."
                ),
                user=UserResponse.model_validate(new_user)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Registration failed for {registration_data.email}: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again later."
            )
    
    def verify_otp(self, verify_data: VerifyOTPRequest) -> VerifyOTPResponse:
        """Verify OTP and mark email as verified."""
        user = self.user_repo.get_by_email(verify_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        
        if user.is_email_verified and user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified and password set. Please login."
            )
        
        is_valid, error_message = otp_manager.validate(
            stored_otp=user.email_otp,
            provided_otp=verify_data.otp,
            created_at=user.otp_created_at,
            attempts=user.otp_attempts
        )
        
        if not is_valid:
            user.otp_attempts += 1
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        try:
            user.is_email_verified = True
            user.email_otp = None
            user.otp_created_at = None
            user.otp_attempts = 0
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Email verified: {user.email} (Role: {user.role.value})")
            
            return VerifyOTPResponse(
                message="Email verified successfully! Please create your password to complete registration.",
                email=user.email,
                email_verified=True,
                redirect_to_password_creation=True
            )
            
        except Exception as e:
            logger.error(f"OTP verification failed: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Verification failed. Please try again."
            )
    
    async def resend_otp(self, resend_data: ResendOTPRequest) -> dict:
        """Resend OTP to user's email."""
        user = self.user_repo.get_by_email(resend_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified. Please set your password or login."
            )
        
        can_resend, seconds_remaining = otp_manager.can_resend(user.otp_created_at)
        
        if not can_resend:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {seconds_remaining} seconds before requesting a new OTP."
            )
        
        try:
            new_otp = otp_manager.generate_otp()
            otp_created_at = datetime.now(timezone.utc)
            
            user.email_otp = new_otp
            user.otp_created_at = otp_created_at
            user.otp_attempts = 0
            
            self.db.commit()
            self.db.refresh(user)
            
            try:
                await asyncio.wait_for(
                    email_service.send_otp_email(
                        user_email=user.email,
                        user_name=user.name,
                        otp=new_otp
                    ),
                    timeout=_email_send_timeout_seconds()
                )
            except asyncio.TimeoutError:
                logger.warning(f"Email timeout for {user.email}")
            except Exception as email_error:
                logger.error(f"Email error while resending OTP to {user.email}: {str(email_error)}")
            
            logger.info(f"OTP resent to: {user.email}")
            
            return {
                "message": f"A new verification code has been sent to {user.email}. Please check your inbox."
            }
            
        except Exception as e:
            logger.error(f"OTP resend failed: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resend OTP. Please try again."
            )
    
    def set_password(self, password_data: SetPasswordRequest) -> SetPasswordResponse:
        """Set password after email verification."""
        user = self.user_repo.get_by_email(password_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please verify your email with OTP first."
            )
        
        if user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password already set. Please use login or reset password."
            )
        
        try:
            user.hashed_password = get_password_hash(password_data.password)
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Password set for admin: {user.email}")
            
            return SetPasswordResponse(
                message="Password created successfully! You can now login with your email and password.",
                email=user.email,
                can_login=True
            )
            
        except Exception as e:
            logger.error(f"Password creation failed: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create password. Please try again."
            )