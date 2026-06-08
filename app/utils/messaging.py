import logging
import os
from typing import Tuple
import httpx
from app.core.config import settings
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


def send_sms_via_twilio(to_number: str, body: str) -> Tuple[bool, str]:
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER

    if not (sid and token and from_number):
        logger.warning("Twilio not configured; SMS not sent")
        return True, "twilio_not_configured"

    try:
        client = TwilioClient(sid, token)
        msg = client.messages.create(body=body, from_=from_number, to=to_number)
        logger.info(f"Twilio SMS sent: {msg.sid}")
        return True, msg.sid
    except Exception as e:
        logger.error(f"Twilio SMS send failed: {e}")
        return False, str(e)


def send_whatsapp_via_meta(phone_number: str, message: str) -> Tuple[bool, str]:
    # Uses WhatsApp Business Cloud API (Meta)
    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not (token and phone_number_id):
        logger.warning("WhatsApp not configured (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID missing); message not sent")
        return False, "whatsapp_not_configured"

    # Normalize phone number: strip non-digits, add 91 for Indian numbers
    digits = "".join(filter(str.isdigit, phone_number))
    if len(digits) == 10:
        digits = "91" + digits  # Add India country code
    elif digits.startswith("0"):
        digits = "91" + digits[1:]  # Replace leading 0 with 91

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": digits,
        "type": "text",
        "text": {"body": message}
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10)
        logger.info(f"WhatsApp API response [{resp.status_code}]: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        msg_id = data.get("messages", [{}])[0].get("id", "sent")
        logger.info(f"WhatsApp message sent to {digits}: {msg_id}")
        return True, msg_id
    except Exception as e:
        logger.error(f"WhatsApp send failed to {digits}: {e}")
        return False, str(e)
