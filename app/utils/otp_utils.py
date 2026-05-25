import secrets
import string
from passlib.hash import bcrypt
from datetime import datetime, timedelta, timezone
from app.core.config import settings


OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300  # 5 minutes


def generate_otp(length: int = OTP_LENGTH) -> str:
    digits = string.digits
    return ''.join(secrets.choice(digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    # Use bcrypt for hashing OTPs before storing
    return bcrypt.hash(otp)


def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.verify(otp, otp_hash)
    except Exception:
        return False


def get_expiry_timestamp(seconds: int = OTP_EXPIRY_SECONDS) -> datetime:
    # return timezone-aware UTC datetime
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
