"""
SMS Service for sending OTP via phone
Supports multiple SMS providers: Twilio, MSG91, Fast2SMS, 2Factor
"""
import logging
from typing import Optional, Tuple
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS messages"""

    def __init__(self):
        self.provider = settings.SMS_PROVIDER  # 'twilio', 'msg91', 'fast2sms', '2factor'

    async def send_otp(self, phone_number: str, otp: str) -> bool:
        """
        Send OTP to phone number.

        Args:
            phone_number: Phone number with or without country code (e.g., +919876543210 or 9876543210)
            otp: 6-digit OTP code

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if self.provider == "2factor":
                return await self._send_via_2factor(phone_number, otp)
            elif self.provider == "twilio":
                return await self._send_via_twilio(phone_number, otp)
            elif self.provider == "msg91":
                return await self._send_via_msg91(phone_number, otp)
            elif self.provider == "fast2sms":
                return await self._send_via_fast2sms(phone_number, otp)
            else:
                logger.error(f"Unknown SMS provider: {self.provider}")
                return False

        except Exception as e:
            logger.error(f"Failed to send SMS OTP: {e}")
            return False

    # ------------------------------------------------------------------
    # 2Factor (https://2factor.in)  — OTP SMS API
    # API: GET https://2factor.in/API/V1/{api_key}/SMS/{phone}/{otp}
    # ------------------------------------------------------------------
    async def _send_via_2factor(self, phone_number: str, otp: str) -> bool:
        """Send SMS OTP via 2Factor.in"""
        try:
            api_key = settings.TWO_FACTOR_API_KEY
            if not api_key:
                logger.error("2Factor API key not configured (TWO_FACTOR_API_KEY missing)")
                return False

            # Normalise phone — strip country code prefix, keep 10 digits
            phone = phone_number.strip()
            for prefix in ("+91", "91"):
                if phone.startswith(prefix):
                    phone = phone[len(prefix):]
                    break
            phone = phone.strip()

            url = f"https://2factor.in/API/V1/{api_key}/SMS/{phone}/{otp}"

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)

            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            logger.info(f"2Factor response [{response.status_code}]: {response.text}")

            if response.status_code == 200 and data.get("Status") == "Success":
                logger.info(f"SMS OTP sent via 2Factor to {phone}")
                return True
            else:
                logger.error(f"2Factor send failed: {response.text}")
                return False

        except Exception as e:
            logger.error(f"2Factor SMS error: {e}")
            return False

    # ------------------------------------------------------------------
    # Twilio
    # ------------------------------------------------------------------
    async def _send_via_twilio(self, phone_number: str, otp: str) -> bool:
        """Send SMS via Twilio"""
        try:
            from twilio.rest import Client

            client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )

            message = client.messages.create(
                body=f"Your Levitica HR verification code is: {otp}. Valid for 10 minutes.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )

            logger.info(f"SMS sent via Twilio: {message.sid}")
            return True

        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            return False

    # ------------------------------------------------------------------
    # MSG91
    # ------------------------------------------------------------------
    async def _send_via_msg91(self, phone_number: str, otp: str) -> bool:
        """Send SMS via MSG91"""
        try:
            url = "https://api.msg91.com/api/v5/otp"

            phone = phone_number.replace("+", "")

            payload = {
                "template_id": settings.MSG91_TEMPLATE_ID,
                "mobile": phone,
                "authkey": settings.MSG91_AUTH_KEY,
                "otp": otp
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    logger.info(f"SMS sent via MSG91 to {phone_number}")
                    return True
                else:
                    logger.error(f"MSG91 error: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"MSG91 SMS error: {e}")
            return False

    # ------------------------------------------------------------------
    # Fast2SMS
    # ------------------------------------------------------------------
    async def _send_via_fast2sms(self, phone_number: str, otp: str) -> bool:
        """Send SMS via Fast2SMS"""
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"

            phone = phone_number.replace("+91", "").replace("+", "")

            headers = {"authorization": settings.FAST2SMS_API_KEY}

            payload = {
                "route": "otp",
                "variables_values": otp,
                "flash": 0,
                "numbers": phone
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    data=payload,
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"SMS sent via Fast2SMS to {phone_number}")
                    return True
                else:
                    logger.error(f"Fast2SMS error: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Fast2SMS error: {e}")
            return False


# Singleton instance
sms_service = SMSService()
