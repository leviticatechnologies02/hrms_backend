import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from app.core.redis_client import redis_client
from redis.exceptions import DataError
from app.utils.otp_utils import generate_otp, hash_otp, verify_otp_hash, get_expiry_timestamp, OTP_EXPIRY_SECONDS
from fastapi import HTTPException
from app.utils.messaging import send_sms_via_twilio, send_whatsapp_via_meta
from app.core.config import settings
from app.models.otp_verification import OTPVerification
from app.core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Rate limiting / brute force configs
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = 60  # seconds
RESEND_LIMIT_PER_HOUR = 5


def _redis_key(business_id: int, mobile: str) -> str:
    return f"otp:{business_id}:{mobile}"


def create_and_save_otp(business_id: int, mobile: str):
    """
    Generate OTP, store its hash in Redis and persist an OTPVerification record
    in the database. Commit happens before returning. Returns tuple (otp, otp_record.id).
    Raises HTTPException on DB errors.
    """
    client = redis_client.get_client()
    otp = generate_otp()
    otp_hashed = hash_otp(otp)
    expires_at = get_expiry_timestamp()

    key = _redis_key(business_id, mobile)

    payload = {
        "otp_hash": otp_hashed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "sms_sent": False,
        "whatsapp_sent": False,
    }

    if client:
        # Redis requires simple scalar types; ensure values are strings
        payload_safe = {k: str(v) for k, v in payload.items()}
        try:
            client.hset(key, mapping=payload_safe)
            client.expire(key, OTP_EXPIRY_SECONDS)
        except DataError as e:
            logger.exception(f"Redis DataError when setting OTP payload: {e}")
        except Exception as e:
            logger.exception(f"Redis error when setting OTP payload: {e}")

    db = None
    try:
        db = next(get_db())
        otp_record = OTPVerification(
            business_id=business_id,
            mobile=mobile,
            otp=otp,
            otp_hash=otp_hashed,
            sms_sent=False,
            whatsapp_sent=False,
            verified=False,
            attempts=0,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        try:
            db.add(otp_record)
            print("✅ OTP OBJECT ADDED")
            db.commit()
            print("✅ DB COMMIT SUCCESS")
            db.refresh(otp_record)
            print("✅ OTP SAVED:", otp_record.id)
            return otp, otp_record.id
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to rollback DB session after error")
            print("❌ DB ERROR:", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close DB session")


def send_otp_background(business_id: int, mobile: str, channels: List[str], otp: str = None, otp_record_id: int = None):
    """
    Send OTP via configured channels. If `otp` and `otp_record_id` are provided,
    this function will only send messages and update Redis/DB flags. Otherwise
    it will generate a new OTP and save a new record (used for internal resends).
    """
    client = redis_client.get_client()

    # If otp provided, use it; otherwise generate and create a temporary record
    generated_here = False
    if not otp:
        generated_here = True
        otp = generate_otp()
        otp_hashed = hash_otp(otp)
        expires_at = get_expiry_timestamp()

        key = _redis_key(business_id, mobile)

        payload = {
            "otp_hash": otp_hashed,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
            "sms_sent": False,
            "whatsapp_sent": False,
        }

        if client:
            payload_safe = {k: str(v) for k, v in payload.items()}
            try:
                client.hset(key, mapping=payload_safe)
                client.expire(key, OTP_EXPIRY_SECONDS)
            except DataError as e:
                logger.exception(f"Redis DataError when setting OTP payload: {e}")
            except Exception as e:
                logger.exception(f"Redis error when setting OTP payload: {e}")

    else:
        # otp provided by caller; key likely already created
        key = _redis_key(business_id, mobile)

    # Send via channels
    sms_ok = False
    wa_ok = False
    if "sms" in channels:
        sms_body = f"Levitica HRMS OTP: {otp}. Valid for 5 minutes."
        sms_ok, _ = send_sms_via_twilio(f"+91{mobile}", sms_body)
        if client:
            client.hset(key, "sms_sent", int(bool(sms_ok)))

    if "whatsapp" in channels:
        wa_msg = f"Levitica HRMS\n\nYour verification OTP is: {otp}\n\nValid for 5 minutes."
        wa_ok, _ = send_whatsapp_via_meta(f"+91{mobile}", wa_msg)
        if client:
            client.hset(key, "whatsapp_sent", int(bool(wa_ok)))

    # If caller provided an OTP record id, update that DB record's sent flags
    if otp_record_id:
        db = None
        try:
            db = next(get_db())
            rec = db.query(OTPVerification).filter_by(id=otp_record_id).first()
            if rec:
                rec.sms_sent = bool(sms_ok)
                rec.whatsapp_sent = bool(wa_ok)
                try:
                    db.add(rec)
                    db.commit()
                    db.refresh(rec)
                    print("✅ OTP SAVED (sent flags updated):", rec.id)
                except Exception as e:
                    try:
                        db.rollback()
                    except Exception:
                        logger.exception("Failed to rollback DB session after error")
                    print("❌ DB ERROR while updating sent flags:", str(e))
                    raise
        except Exception as e:
            logger.exception(f"Failed to update OTP sent flags in DB: {e}")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception("Failed to close DB session")

    # If we generated the OTP here (resend path), persist a new DB record
    if generated_here:
        # try to persist the record (similar to previous behavior)
        otp_hashed = hash_otp(otp)
        db = None
        try:
            db = next(get_db())
            otp_record = OTPVerification(
                business_id=business_id,
                mobile=mobile,
                otp=otp,
                otp_hash=otp_hashed,
                sms_sent=bool(sms_ok),
                whatsapp_sent=bool(wa_ok),
                verified=False,
                attempts=0,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            try:
                db.add(otp_record)
                db.commit()
                db.refresh(otp_record)
                print("✅ OTP SAVED:", otp_record.id)
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    logger.exception("Failed to rollback DB session after error")
                print("❌ DB ERROR:", str(e))
                raise
        except Exception as e:
            logger.exception(f"Unhandled error in send_otp_background (generated): {e}")
            raise
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception("Failed to close DB session")


def verify_otp(business_id: int, otp: str) -> Tuple[bool, str]:
    """
    Verify the latest unverified OTP for the given business.
    This does not require mobile in the request — it uses the latest
    unverified OTP record (by created_at) for the business.
    """
    client = redis_client.get_client()

    # Fetch latest unverified DB record for this business
    try:
        db = next(get_db())
        rec = (
            db.query(OTPVerification)
            .filter_by(business_id=business_id, verified=False)
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
    except Exception:
        logger.exception("Failed to read OTP from DB")
        return False, "OTP expired or not found"

    if not rec:
        return False, "OTP expired or not found"

    # Check expiry
    if rec.expires_at and datetime.now(timezone.utc) > rec.expires_at:
        return False, "OTP expired"

    # Verify using plain OTP in dev or hashed OTP
    if getattr(rec, 'otp', None):
        verified_ok = (otp == rec.otp)
    elif getattr(rec, 'otp_hash', None):
        verified_ok = verify_otp_hash(otp, rec.otp_hash)
    else:
        return False, "OTP missing"

    if verified_ok:
        try:
            rec.verified = True
            db.add(rec)
            db.commit()
            print("✅ OTP UPDATED (verified):", rec.id)

            # Also update the matching OnboardingForm's candidate_mobile_verified flag
            try:
                from app.models.onboarding import OnboardingForm
                matching_form = (
                    db.query(OnboardingForm)
                    .filter(
                        OnboardingForm.business_id == business_id,
                        OnboardingForm.candidate_mobile.contains(rec.mobile),
                        OnboardingForm.candidate_mobile_verified == False,
                    )
                    .order_by(OnboardingForm.created_at.desc())
                    .first()
                )
                if matching_form:
                    matching_form.candidate_mobile_verified = True
                    db.add(matching_form)
                    db.commit()
                    print("✅ OnboardingForm mobile_verified updated:", matching_form.id)
            except Exception as e:
                logger.warning(f"Could not update OnboardingForm mobile_verified: {e}")

            return True, "OTP verified"
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to rollback DB session after error")
            logger.exception(f"Failed to update OTP verification in DB: {e}")
            return False, "Failed to verify OTP"
        finally:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close DB session")
    else:
        # increment attempts in DB and commit
        try:
            rec.attempts = (rec.attempts or 0) + 1
            db.add(rec)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to rollback DB session after error")
        finally:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close DB session")
        return False, "Invalid OTP"


def can_resend(business_id: int, mobile: str) -> Tuple[bool, str]:
    client = redis_client.get_client()
    key = _redis_key(business_id, mobile)
    if not client:
        return True, "redis_unavailable"

    last_sent = client.hget(key, "created_at")
    if last_sent:
        # parse ISO
        from datetime import datetime, timezone
        try:
            last_dt = datetime.fromisoformat(last_sent)
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < RESEND_COOLDOWN:
                return False, "Resend cooldown"
        except Exception:
            pass

    # Count resends in last hour - simple approach using redis key
    # We keep a counter key
    counter_key = f"otp_resend_count:{business_id}:{mobile}"
    count = client.get(counter_key)
    count = int(count) if count else 0
    if count >= RESEND_LIMIT_PER_HOUR:
        return False, "Resend limit reached"

    return True, "ok"


def register_resend(business_id: int, mobile: str):
    client = redis_client.get_client()
    if not client:
        return
    counter_key = f"otp_resend_count:{business_id}:{mobile}"
    # increment and set expiry 1 hour
    client.incr(counter_key)
    client.expire(counter_key, 3600)


def get_latest_otp_record(business_id: int):
    """Return the latest OTPVerification record for a business (or None)."""
    db = None
    try:
        db = next(get_db())
        return (
            db.query(OTPVerification)
            .filter(OTPVerification.business_id == business_id, OTPVerification.verified == False)
            .order_by(OTPVerification.id.desc())
            .first()
        )
    except Exception:
        logger.exception("Failed to fetch latest OTP record")
        return None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close DB session")


def get_latest_otp_record_for_mobile(business_id: int, mobile: str):
    """Return the latest unverified OTPVerification record for a business+mobile (or None)."""
    db = None
    try:
        db = next(get_db())
        return (
            db.query(OTPVerification)
            .filter(
                OTPVerification.business_id == business_id,
                OTPVerification.mobile == str(mobile),
                OTPVerification.verified == False,
            )
            .order_by(OTPVerification.id.desc())
            .first()
        )
    except Exception:
        logger.exception("Failed to fetch latest OTP record for mobile")
        return None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close DB session")
