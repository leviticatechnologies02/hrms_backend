from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from typing import List
from app.schemas.otp import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, ResendOTPRequest
from app.services.otp_service import send_otp_background, verify_otp, can_resend, register_resend, create_and_save_otp
from app.core.config import settings

router = APIRouter()


@router.post("/otp/send", response_model=SendOTPResponse, tags=["OTP"], status_code=200)
async def send_otp(business_id: int, req: SendOTPRequest, background_tasks: BackgroundTasks):
    """Send OTP via configured channels (sms, whatsapp)"""
    # Basic validation
    if not req.channels:
        raise HTTPException(status_code=400, detail="No channels specified")

    # Create and persist OTP record synchronously (commit before responding)
    otp, otp_record_id = create_and_save_otp(business_id, req.mobile)

    # Schedule background sending (will use the created OTP and update sent flags)
    background_tasks.add_task(send_otp_background, business_id, req.mobile, req.channels, otp, otp_record_id)

    return SendOTPResponse(
        success=True,
        message="OTP send scheduled",
        business_id=business_id,
        mobile=req.mobile,
        channels_sent=req.channels,
        expires_in=300,
        otp=otp if settings.DEBUG else None,
    )


@router.post("/otp/verify", response_model=VerifyOTPResponse, tags=["OTP"], status_code=200)
async def verify_otp_endpoint(business_id: int, req: VerifyOTPRequest):
    ok, msg = verify_otp(business_id, req.otp)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return VerifyOTPResponse(success=True, message="OTP verified successfully", verified=True)


@router.post("/otp/resend", response_model=SendOTPResponse, tags=["OTP"], status_code=200)
async def resend_otp(business_id: int, req: ResendOTPRequest, background_tasks: BackgroundTasks):
    can, reason = can_resend(business_id, req.mobile)
    if not can:
        raise HTTPException(status_code=429, detail=reason)

    register_resend(business_id, req.mobile)

    otp, otp_record_id = create_and_save_otp(business_id, req.mobile)
    background_tasks.add_task(send_otp_background, business_id, req.mobile, req.channels, otp, otp_record_id)

    return SendOTPResponse(
        success=True,
        message="OTP resend scheduled",
        business_id=business_id,
        mobile=req.mobile,
        channels_sent=req.channels,
        expires_in=300,
        otp=otp if settings.DEBUG else None,
    )
