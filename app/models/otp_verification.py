from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.models.base import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, nullable=False, index=True)
    # Plain OTP stored only in development for testing purposes
    otp = Column(String(16), nullable=True)
    mobile = Column(String(32), nullable=False, index=True)
    country_code = Column(String(8), nullable=True)
    otp_hash = Column(String(255), nullable=False)
    sms_sent = Column(Boolean, default=False)
    whatsapp_sent = Column(Boolean, default=False)
    verified = Column(Boolean, default=False, index=True)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<OTPVerification id={self.id} business={self.business_id} mobile={self.mobile} verified={self.verified}>"
