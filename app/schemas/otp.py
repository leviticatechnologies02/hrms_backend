from pydantic import BaseModel, Field
from typing import List, Optional


class SendOTPRequest(BaseModel):
    mobile: str = Field(..., example="9876543210")
    channels: List[str] = Field(..., example=["sms", "whatsapp"])


class ResendOTPRequest(BaseModel):
    mobile: str
    channels: List[str]


class VerifyOTPRequest(BaseModel):
    otp: str


class SendOTPResponse(BaseModel):
    success: bool
    message: str
    business_id: int
    mobile: str
    channels_sent: List[str]
    expires_in: int
    otp: Optional[str] = None


class VerifyOTPResponse(BaseModel):
    success: bool
    message: str
    verified: bool
