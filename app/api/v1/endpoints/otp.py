from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from typing import List
from app.schemas.otp import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, ResendOTPRequest
from app.services.otp_service import send_otp_background, verify_otp, can_resend, register_resend, create_and_save_otp, get_latest_otp_record, get_latest_otp_record_for_mobile
from datetime import datetime, timezone
from app.core.config import settings

router = APIRouter()


@router.post("/otp/send", response_model=SendOTPResponse, tags=["OTP"], status_code=200)
async def send_otp(business_id: int, req: SendOTPRequest, background_tasks: BackgroundTasks):
    """Send OTP via configured channels (sms, whatsapp) — sends synchronously for real-time delivery."""
    import logging
    logger = logging.getLogger(__name__)

    # Basic validation
    if not req.channels:
        raise HTTPException(status_code=400, detail="No channels specified")

    # Create and persist OTP record synchronously (commit before responding)
    otp, otp_record_id = create_and_save_otp(business_id, req.mobile)

    # Send SMS synchronously so we know if it actually worked
    channels_actually_sent = []

    if "sms" in req.channels:
        from app.services.sms_service import sms_service
        logger.info(f"[OTP-SEND] Sending SMS synchronously to {req.mobile}")
        try:
            sms_ok = sms_service.send_otp_sync(req.mobile, otp)
            if sms_ok:
                channels_actually_sent.append("sms")
                logger.info(f"[OTP-SEND] ✅ SMS delivered to {req.mobile}")
            else:
                logger.error(f"[OTP-SEND] ❌ SMS failed for {req.mobile}")
        except Exception as e:
            logger.error(f"[OTP-SEND] ❌ SMS exception: {e}", exc_info=True)

    if "whatsapp" in req.channels:
        from app.utils.messaging import send_whatsapp_via_meta
        wa_msg = f"Levitica HRMS\n\nYour verification OTP is: {otp}\n\nValid for 5 minutes."
        wa_ok, wa_detail = send_whatsapp_via_meta(f"+91{req.mobile}", wa_msg)
        if wa_ok:
            channels_actually_sent.append("whatsapp")

    # Update DB record with sent flags (in background to not delay response)
    background_tasks.add_task(
        _update_otp_sent_flags, otp_record_id,
        "sms" in channels_actually_sent,
        "whatsapp" in channels_actually_sent
    )

    return SendOTPResponse(
        success=len(channels_actually_sent) > 0,
        message=f"OTP sent via: {', '.join(channels_actually_sent)}" if channels_actually_sent else "OTP created but delivery failed — check SMS provider config",
        business_id=business_id,
        mobile=req.mobile,
        channels_sent=channels_actually_sent,
        expires_in=300,
        otp=otp,
    )


def _update_otp_sent_flags(otp_record_id: int, sms_sent: bool, whatsapp_sent: bool):
    """Background task to update OTP record sent flags in DB."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from app.core.database import get_db
        from app.models.otp_verification import OTPVerification
        db = next(get_db())
        rec = db.query(OTPVerification).filter_by(id=otp_record_id).first()
        if rec:
            rec.sms_sent = sms_sent
            rec.whatsapp_sent = whatsapp_sent
            db.commit()
            logger.info(f"[OTP-FLAGS] Updated record {otp_record_id}: sms={sms_sent}, wa={whatsapp_sent}")
        db.close()
    except Exception as e:
        logger.error(f"[OTP-FLAGS] Failed to update sent flags: {e}")



@router.get(
    "/otp/latest/{mobile}",
    tags=["OTP"],
    status_code=200
)
async def get_latest_otp(business_id: int, mobile: str):
    """Fetch latest unverified OTP for the given business+mobile and return only the OTP value."""
    rec = get_latest_otp_record_for_mobile(business_id, mobile)
    if not rec:
        return {"success": False, "message": "OTP not found"}

    otp_value = getattr(rec, 'otp', None)
    if not otp_value:
        return {"success": False, "message": "OTP not found"}

    return {"success": True, "mobile": str(rec.mobile), "otp": str(otp_value)}


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
        otp=otp,
    )
