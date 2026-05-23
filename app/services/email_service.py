"""
Email Service
Handles sending transactional emails (OTP, verification, etc.)
"""

import aiosmtplib
import httpx
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import logging
import asyncio

from ..core.config import settings
from app.core.otp import otp_manager

logger = logging.getLogger(__name__)


class EmailService:
    """Manages email sending with template rendering."""
    
    def __init__(self):
        """Initialize email service with Jinja2 templates."""
        # Setup template directory
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Log SMTP configuration status
        self._log_smtp_status()
    
    def _log_smtp_status(self):
        """Log SMTP configuration for debugging."""
        if not settings.is_smtp_configured():
            logger.warning(
                "⚠️  SMTP not configured. Emails will be logged but not sent.\n"
                "Update your .env file with SMTP credentials."
            )
        else:
            logger.info(
                f"SMTP configured: {settings.SMTP_HOST}:{settings.SMTP_PORT} "
                f"(From: {settings.SMTP_FROM_EMAIL})"
            )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[dict]] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Send email via SMTP with retry logic and attachments.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text fallback (optional)
            attachments: List of dicts with 'filename', 'content' (bytes), 'mime_type'
            max_retries: Number of retry attempts
        
        Returns:
            True if sent successfully, False otherwise
        """
        # If configured to use Brevo, use Brevo API path
        provider = getattr(settings, 'EMAIL_PROVIDER', 'smtp') or 'smtp'
        if provider.lower() == 'brevo':
            return await self._send_via_brevo(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachments=attachments,
            )

        # Skip if SMTP not configured
        if not settings.is_smtp_configured():
            logger.warning(f"SMTP not configured. Email to {to_email} not sent.")
            logger.info(f"Subject: {subject}")
            return False
        
        # Build email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject
        message["Message-ID"] = f"<{datetime.utcnow().timestamp()}.{to_email}@{settings.SMTP_HOST}>"
        message["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Attach plain text version
        if text_content:
            message.attach(MIMEText(text_content, "plain", "utf-8"))
        
        # Attach HTML version
        message.attach(MIMEText(html_content, "html", "utf-8"))
        
        # Attach files if provided
        if attachments:
            for attachment in attachments:
                try:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    message.attach(part)
                    logger.info(f"Attached file: {attachment['filename']}")
                except Exception as e:
                    logger.error(f"Failed to attach file {attachment.get('filename')}: {e}")
        
        # Retry loop with exponential backoff
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Sending email to {to_email} (attempt {attempt}/{max_retries})...")
                
                # Choose connection method based on settings
                if settings.SMTP_USE_TLS:
                    # SSL/TLS (port 465)
                    await aiosmtplib.send(
                        message,
                        hostname=settings.SMTP_HOST,
                        port=settings.SMTP_PORT,
                        username=settings.SMTP_USERNAME,
                        password=settings.SMTP_PASSWORD,
                        use_tls=True,
                        timeout=settings.SMTP_TIMEOUT,
                    )
                elif settings.SMTP_USE_STARTTLS:
                    # STARTTLS (port 587)
                    await aiosmtplib.send(
                        message,
                        hostname=settings.SMTP_HOST,
                        port=settings.SMTP_PORT,
                        username=settings.SMTP_USERNAME,
                        password=settings.SMTP_PASSWORD,
                        start_tls=True,
                        timeout=settings.SMTP_TIMEOUT,
                    )
                else:
                    # Plain SMTP (port 25, 2525)
                    await aiosmtplib.send(
                        message,
                        hostname=settings.SMTP_HOST,
                        port=settings.SMTP_PORT,
                        username=settings.SMTP_USERNAME,
                        password=settings.SMTP_PASSWORD,
                        timeout=settings.SMTP_TIMEOUT,
                    )
                
                logger.info(f"Email sent successfully to {to_email}")
                return True
                
            except aiosmtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP authentication failed: {e}")
                return False  # Don't retry auth errors
                
            except aiosmtplib.SMTPRecipientsRefused as e:
                logger.error(f"Recipient refused: {to_email} - {e}")
                return False  # Don't retry invalid recipients
                
            except aiosmtplib.SMTPException as e:
                logger.error(f"SMTP error (attempt {attempt}/{max_retries}): {e}")
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to send email after {max_retries} attempts")
                    return False
                    
            except Exception as e:
                logger.error(f"Unexpected email error: {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return False
        
        return False

    async def _send_via_brevo(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[dict]] = None,
    ) -> bool:
        """
        Send email via Brevo (Sendinblue) transactional API.
        """
        try:
            if not settings.is_brevo_configured():
                logger.error("Brevo is not configured (missing API key or sender email)")
                return False

            api_url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
            }

            payload = {
                "sender": {"email": settings.BREVO_SENDER_EMAIL, "name": settings.BREVO_SENDER_NAME or settings.APP_NAME},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
                "textContent": text_content or "",
            }

            # Attachments (base64)
            if attachments:
                brevo_atts = []
                for att in attachments:
                    try:
                        content_b64 = base64.b64encode(att['content']).decode('ascii')
                        brevo_atts.append({"name": att['filename'], "content": content_b64})
                    except Exception as e:
                        logger.error(f"Failed to encode attachment {att.get('filename')}: {e}")
                if brevo_atts:
                    payload['attachment'] = brevo_atts

            timeout = settings.SMTP_TIMEOUT if getattr(settings, 'SMTP_TIMEOUT', None) else 30

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(api_url, json=payload, headers=headers)

            if resp.status_code in (200, 201, 202):
                logger.info(f"Brevo email sent to {to_email} (status {resp.status_code})")
                return True
            else:
                logger.error(f"Brevo send failed: {resp.status_code} - {resp.text}")
                return False

        except Exception as e:
            logger.exception(f"Unexpected Brevo send error: {e}")
            return False
    
    async def send_otp_email(
        self,
        user_email: str,
        user_name: str,
        otp: str
    ) -> bool:
        """
        Send OTP verification email.
        
        Args:
            user_email: Recipient email
            user_name: User's full name
            otp: 6-digit OTP code
        
        Returns:
            True if sent successfully
        """
        try:
            # Template context
            context = {
                "app_name": settings.APP_NAME,
                "user_name": user_name,
                "user_email": user_email,
                "otp": otp,
                "otp_expiry_minutes": otp_manager.OTP_EXPIRY_MINUTES,
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
            }
            
            # Render HTML template
            try:
                template = self.env.get_template("otp_email.html")
                html_content = template.render(**context)
            except Exception:
                # Fallback to inline HTML
                html_content = self._generate_otp_html_fallback(context)
            
            # Render text template
            try:
                template = self.env.get_template("otp_email.txt")
                text_content = template.render(**context)
            except Exception:
                # Fallback to inline text
                text_content = self._generate_otp_text_fallback(context)
            
            # Send email
            subject = f"Your Verification Code - {settings.APP_NAME}"
            
            return await self.send_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            return False
    
    def _generate_otp_html_fallback(self, context: dict) -> str:
        """Generate fallback HTML for OTP email if template missing."""
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
                <h1 style="color: #667eea; text-align: center;">{context['app_name']}</h1>
                <h2>Email Verification</h2>
                
                <p>Hello <strong>{context['user_name']}</strong>,</p>
                
                <p>Thank you for registering! Please use the verification code below:</p>
                
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 20px; border-radius: 8px; text-align: center; margin: 30px 0;">
                    <p style="color: white; margin: 0 0 10px; font-size: 14px;">YOUR VERIFICATION CODE</p>
                    <div style="background: white; padding: 15px; border-radius: 6px;">
                        <p style="margin: 0; font-size: 36px; font-weight: bold; 
                                  color: #333; letter-spacing: 6px; font-family: monospace;">
                            {context['otp']}
                        </p>
                    </div>
                </div>
                
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>⚠️ Important:</strong> This code expires in 
                        <strong>{context['otp_expiry_minutes']} minutes</strong>.
                    </p>
                </div>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    Need help? Contact us at 
                    <a href="mailto:{context['support_email']}" style="color: #667eea;">
                        {context['support_email']}
                    </a>
                </p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="text-align: center; color: #999; font-size: 12px;">
                    &copy; {context['current_year']} {context['app_name']}. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
    
    def _generate_otp_text_fallback(self, context: dict) -> str:
        """Generate fallback plain text for OTP email if template missing."""
        return f"""
{context['app_name']} - Email Verification
{'=' * 70}

Hello {context['user_name']},

Thank you for registering with {context['app_name']}!

Your verification code is:

    {context['otp']}

⚠️ IMPORTANT: This code expires in {context['otp_expiry_minutes']} minutes.

WHAT'S NEXT?
• Enter the code on the verification page
• Create your password
• Start using your account

Need help? Contact us at {context['support_email']}

{'=' * 70}
© {context['current_year']} {context['app_name']}. All rights reserved.
        """
    
    async def send_password_reset_otp_email(
        self,
        user_email: str,
        user_name: str,
        otp: str
    ) -> bool:
        """
        Send password reset OTP email.
        
        Args:
            user_email: Recipient email
            user_name: User's full name
            otp: 6-digit OTP code
        
        Returns:
            True if sent successfully
        """
        try:
            # Template context
            context = {
                "app_name": settings.APP_NAME,
                "user_name": user_name,
                "user_email": user_email,
                "otp": otp,
                "otp_expiry_minutes": otp_manager.OTP_EXPIRY_MINUTES,
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
            }
            
            # Generate HTML content
            html_content = self._generate_password_reset_html(context)
            
            # Generate text content
            text_content = self._generate_password_reset_text(context)
            
            # Send email
            subject = f"Password Reset Code - {settings.APP_NAME}"
            
            return await self.send_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password reset OTP email: {e}")
            return False
    
    def _generate_password_reset_html(self, context: dict) -> str:
        """Generate HTML for password reset email."""
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
                <h1 style="color: #667eea; text-align: center;">{context['app_name']}</h1>
                <h2>Password Reset Request</h2>
                
                <p>Hello <strong>{context['user_name']}</strong>,</p>
                
                <p>We received a request to reset your password. Use the verification code below:</p>
                
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 20px; border-radius: 8px; text-align: center; margin: 30px 0;">
                    <p style="color: white; margin: 0 0 10px; font-size: 14px;">YOUR PASSWORD RESET CODE</p>
                    <div style="background: white; padding: 15px; border-radius: 6px;">
                        <p style="margin: 0; font-size: 36px; font-weight: bold; 
                                  color: #333; letter-spacing: 6px; font-family: monospace;">
                            {context['otp']}
                        </p>
                    </div>
                </div>
                
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>⚠️ Important:</strong> This code expires in 
                        <strong>{context['otp_expiry_minutes']} minutes</strong>.
                    </p>
                </div>
                
                <div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px; margin: 20px 0;">
                    <p style="margin: 0; color: #721c24;">
                        <strong>🔒 Security Notice:</strong> If you didn't request this password reset, 
                        please ignore this email or contact support immediately.
                    </p>
                </div>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    Need help? Contact us at 
                    <a href="mailto:{context['support_email']}" style="color: #667eea;">
                        {context['support_email']}
                    </a>
                </p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="text-align: center; color: #999; font-size: 12px;">
                    &copy; {context['current_year']} {context['app_name']}. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
    
    def _generate_password_reset_text(self, context: dict) -> str:
        """Generate plain text for password reset email."""
        return f"""
{context['app_name']} - Password Reset
{'=' * 70}

Hello {context['user_name']},

We received a request to reset your password.

Your password reset code is:

    {context['otp']}

⚠️ IMPORTANT: This code expires in {context['otp_expiry_minutes']} minutes.

WHAT'S NEXT?
• Enter the code on the password reset page
• Create your new password
• Login with your new credentials

🔒 SECURITY NOTICE:
If you didn't request this password reset, please ignore this email 
or contact support immediately.

Need help? Contact us at {context['support_email']}

{'=' * 70}
© {context['current_year']} {context['app_name']}. All rights reserved.
        """
    
    async def send_onboarding_form_email(
        self,
        candidate_email: str,
        candidate_name: str,
        form_id: int,
        form_token: str,
        candidate_mobile: str = None,
        has_policies: bool = False,
        has_offer_letter: bool = False,
        offer_letter_content: Optional[str] = None,
        company_name: str = "Levitica Technologies",
        form = None,  # OnboardingForm instance for advanced PDF
        salary_data: Optional[Dict] = None,  # Salary breakdown for advanced PDF
        offer_letter = None  # OfferLetter instance for advanced PDF
    ) -> bool:
        """
        Send onboarding form email to candidate with optional offer letter PDF.
        
        Args:
            candidate_email: Candidate's email address
            candidate_name: Candidate's full name
            form_id: Onboarding form ID
            form_token: Unique form token for access
            candidate_mobile: Candidate's mobile number
            has_policies: Whether policies are attached
            has_offer_letter: Whether offer letter is attached
            offer_letter_content: Offer letter text content to generate PDF
            company_name: Company name
        
        Returns:
            True if sent successfully
        """
        try:
            # Generate form view URL - candidate onboarding flow
            base_url = settings.FRONTEND_URL or "http://localhost:3000"
            # Updated to match frontend routing: /onboarding/form/{formId}/final
            form_url = f"{base_url}/newhire?token={form_token}&formId={form_id}"
            
            # Get current date in format: 23 Feb 2025
            from datetime import datetime
            current_date = datetime.now().strftime("%d %b %Y")
            
            # Template context
            context = {
                "app_name": settings.APP_NAME,
                "company_name": company_name,
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "candidate_mobile": candidate_mobile,
                "form_id": form_id,
                "form_url": form_url,
                "has_policies": has_policies,
                "has_offer_letter": has_offer_letter,
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
                "current_date": current_date,
            }
            
            # Generate HTML content
            html_content = self._generate_onboarding_html(context)
            
            # Generate text content
            text_content = self._generate_onboarding_text(context)
            
            # Generate PDF attachment if offer letter content provided
            attachments = []
            if offer_letter_content and has_offer_letter:
                try:
                    # Use professional PDF service for exact match with template design
                    if form:
                        from app.services.pdf_professional_template import professional_pdf_service
                        from app.services.pdf_data_mapper import pdf_data_mapper
                        
                        # Map form data to PDF format
                        candidate_data = pdf_data_mapper.map_onboarding_form_to_pdf_data(
                            form=form,
                            offer_letter=offer_letter,  # Pass offer letter object
                            salary_data=salary_data
                        )
                        
                        # Generate professional PDF matching template design
                        pdf_buffer = professional_pdf_service.generate_offer_letter_pdf(
                            candidate_data=candidate_data
                        )
                        
                        if pdf_buffer:
                            filename = professional_pdf_service.generate_filename(candidate_name, "Offer_Letter")
                            attachments.append({
                                'filename': filename,
                                'content': pdf_buffer.read(),
                                'mime_type': 'application/pdf'
                            })
                            logger.info(f"Generated professional offer letter PDF: {filename}")
                    else:
                        # Fallback to simple PDF service
                        from app.services.pdf_service import pdf_service
                        
                        pdf_buffer = pdf_service.generate_offer_letter_pdf(
                            letter_content=offer_letter_content,
                            candidate_name=candidate_name,
                            company_name=company_name
                        )
                        
                        if pdf_buffer:
                            filename = pdf_service.generate_filename(candidate_name, "Offer_Letter")
                            attachments.append({
                                'filename': filename,
                                'content': pdf_buffer.read(),
                                'mime_type': 'application/pdf'
                            })
                            logger.info(f"Generated offer letter PDF: {filename}")
                except Exception as pdf_error:
                    logger.error(f"Failed to generate PDF attachment: {pdf_error}")
                    import traceback
                    traceback.print_exc()
                    # Continue sending email without attachment
            
            # Send email
            subject = f"Welcome to {company_name} - Your Onboarding Form"
            
            return await self.send_email(
                to_email=candidate_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachments=attachments if attachments else None
            )
            
        except Exception as e:
            logger.error(f"Failed to send onboarding form email: {e}")
            return False
    
    def _generate_onboarding_html(self, context: dict) -> str:
        """Generate HTML for onboarding form email with professional animations."""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Onboarding Process - {context['company_name']}</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f4f4f4; padding: 20px 0;">
                <tr>
                    <td align="center">
                        <table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width: 600px; background-color: #2b2b2b; color: #ffffff; border-radius: 8px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                            <tr>
                                <td style="padding: 30px;">
                                    
                                    <!-- Header with Logo -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 30px;">
                                        <tr>
                                            <td width="60" style="vertical-align: middle; padding-right: 15px;">
                                                <table cellpadding="0" cellspacing="0" border="0" width="60" height="60" style="background-color: #d32f2f; border-radius: 50%;">
                                                    <tr>
                                                        <td align="center" valign="middle" style="font-size: 28px; font-weight: bold; color: #ffffff; line-height: 60px;">
                                                            L
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                            <td style="vertical-align: middle;">
                                                <div style="font-size: 16px; font-weight: 600; color: #ffffff; margin-bottom: 4px;">{context['company_name']}</div>
                                                <div style="font-size: 12px; color: #999999;">{context['current_date']}</div>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Greeting -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 25px;">
                                        <tr>
                                            <td>
                                                <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #ffffff;">
                                                    Dear <strong>{context['candidate_name']}</strong>,
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Main Message -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 25px;">
                                        <tr>
                                            <td>
                                                <p style="margin: 0 0 15px 0; font-size: 15px; line-height: 1.6; color: #ffffff;">
                                                    We are pleased to inform you that your onboarding process with <strong>{context['company_name']}</strong> has been successfully initiated.
                                                </p>
                                                <p style="margin: 0 0 15px 0; font-size: 15px; line-height: 1.6; color: #ffffff;">
                                                    To proceed further, please click the link below and complete the required onboarding formalities:
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Onboarding Link Button -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin: 30px 0;">
                                        <tr>
                                            <td align="center">
                                                <a href="{context['form_url']}" style="display: inline-block; background: linear-gradient(135deg, #4a9eff 0%, #357abd 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-size: 15px; font-weight: 600; box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);">
                                                    🚀 Access Your Onboarding Form
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin: 20px 0;">
                                        <tr>
                                            <td align="center">
                                                <p style="margin: 0; font-size: 12px; color: #999999;">
                                                    Or copy this link: <a href="{context['form_url']}" style="color: #4a9eff; text-decoration: none; word-break: break-all;">{context['form_url']}</a>
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Instructions -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 25px; background-color: #333333; border-radius: 6px; border-left: 4px solid #4a9eff;">
                                        <tr>
                                            <td style="padding: 20px;">
                                                <p style="margin: 0 0 15px 0; font-size: 15px; line-height: 1.6; color: #ffffff;">
                                                    📋 <strong>Important Instructions:</strong>
                                                </p>
                                                <p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.6; color: #cccccc;">
                                                    • Ensure all requested details and documents are submitted accurately
                                                </p>
                                                <p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.6; color: #cccccc;">
                                                    • Complete the process within the specified timeline
                                                </p>
                                                <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #cccccc;">
                                                    • Contact our HR team if you need any assistance
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 25px;">
                                        <tr>
                                            <td>
                                                <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #ffffff;">
                                                    We look forward to welcoming you to <strong>{context['company_name']}</strong> and wish you a smooth and successful onboarding experience.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Signature -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #444444;">
                                        <tr>
                                            <td>
                                                <p style="margin: 0 0 20px 0; font-size: 15px; color: #ffffff;">
                                                    <strong>Warm Regards,</strong>
                                                </p>
                                                
                                                <!-- Company Logo Image -->
                                                <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 15px;">
                                                    <tr>
                                                        <td>
                                                            <img src="https://leviticatechnologies.com/assets/Levitica%20logo.png" alt="Levitica Logo" style="height: 50px; width: auto; display: block;" />
                                                        </td>
                                                    </tr>
                                                </table>
                                                
                                                <!-- HR Details -->
                                                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 15px; background-color: #333333; border-radius: 6px;">
                                                    <tr>
                                                        <td style="padding: 15px;">
                                                            <p style="margin: 0 0 5px 0; font-size: 15px; color: #4a9eff; font-weight: 600;">
                                                                Ashritha Rao
                                                            </p>
                                                            <p style="margin: 0 0 12px 0; font-size: 13px; color: #999999;">
                                                                HR Executive
                                                            </p>
                                                            <p style="margin: 0 0 5px 0; font-size: 13px; color: #ffffff;">
                                                                📱 <strong>Mobile:</strong> +91 9032503559
                                                            </p>
                                                            <p style="margin: 0 0 5px 0; font-size: 13px; color: #ffffff;">
                                                                ✉️ <strong>Email:</strong> <a href="mailto:hr@leviticatechnologies.com" style="color: #4a9eff; text-decoration: none;">hr@leviticatechnologies.com</a>
                                                            </p>
                                                            <p style="margin: 0; font-size: 13px; color: #ffffff;">
                                                                🌐 <strong>Website:</strong> <a href="https://www.leviticatechnologies.com" style="color: #4a9eff; text-decoration: none;">www.leviticatechnologies.com</a>
                                                            </p>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Footer -->
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #444444;">
                                        <tr>
                                            <td align="center">
                                                <p style="margin: 0; font-size: 12px; color: #666666;">
                                                    © {context['current_year']} {context['company_name']}. All rights reserved.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    def _generate_onboarding_text(self, context: dict) -> str:
        """Generate plain text for onboarding form email."""
        
        return f"""
{context['company_name']}
{'=' * 70}

Dear [{context['candidate_name']}],

We are pleased to inform you that your onboarding process with 
{context['company_name']} has been successfully initiated.

To proceed further, please click the link below and complete the required 
onboarding formalities:

👉 Onboarding Link: {context['form_url']}

Kindly ensure that all requested details and documents are submitted 
accurately within the specified timeline to avoid any delays in the 
onboarding process.

If you face any issues or require assistance at any stage, please feel 
free to reach out to our HR team.

We look forward to welcoming you to {context['company_name']} and wish 
you a smooth and successful onboarding experience.

Warm Regards,

LEVITICA

Ashritha Rao
HR Executive

Mobile: +91 9573945359
Email: {context['support_email']}
Website: https://www.leviticatechnologies.com

{'=' * 70}
© {context['current_year']} {context['company_name']}. All rights reserved.
        """
    
    async def send_mobile_login_email(
        self,
        employee_name: str,
        employee_code: str,
        employee_email: str,
        mobile: str,
        company_name: str = "Levitica Technologies",
        company_id: str = "LEV001",
        login_pin: str = None
    ) -> bool:
        """
        Send mobile login credentials email to employee.
        
        Args:
            employee_name: Employee's full name
            employee_code: Employee code
            employee_email: Employee's email address
            mobile: Employee's mobile number
            company_name: Company name
            company_id: Company ID
            login_pin: Login PIN (auto-generated if not provided)
        
        Returns:
            True if sent successfully
        """
        try:
            from app.services.email_template import generate_mobile_login_html, generate_mobile_login_text
            from app.services.email_template.logo_base64_loader import get_cached_logo_data_url
            from datetime import datetime
            from app.core.config import BASE_URL
            import random
            
            # Get current date in format: 23 Feb 2025
            current_date = datetime.now().strftime("%d %b %Y")
            
            # Generate login PIN if not provided (last 6 digits of mobile)
            if not login_pin:
                login_pin = mobile[-6:] if len(mobile) >= 6 else str(random.randint(100000, 999999))
            
            # Logo URL - use embedded base64 for guaranteed display
            logo_data_url = get_cached_logo_data_url()
            if not logo_data_url:
                # Fallback to server URL if base64 fails
                logo_data_url = f"{BASE_URL}/static/images/runtime-logo.png"
            
            # Template context
            context = {
                "employee_name": employee_name,
                "employee_code": employee_code,
                "mobile": mobile,
                "company_name": company_name,
                "company_id": company_id,
                "login_pin": login_pin,
                "logo_url": logo_data_url,
                "app_download_link": "https://play.google.com/store/apps/details?id=com.runtime.workman",
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
                "current_date": current_date,
            }
            
            # Generate HTML content
            html_content = generate_mobile_login_html(context)
            
            # Generate text content
            text_content = generate_mobile_login_text(context)
            
            # Send email
            subject = f"Runtime Workman Login Details - {company_name}"
            
            return await self.send_email(
                to_email=employee_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send mobile login email: {e}")
            return False
    
    async def send_web_login_email(
        self,
        employee_name: str,
        employee_code: str,
        employee_email: str,
        company_name: str = "Levitica Technologies",
        company_id: str = "LEV001",
        login_pin: str = None,
        temporary_password: str = None
    ) -> bool:
        """
        Send web login credentials email to employee.
        
        Args:
            employee_name: Employee's full name
            employee_code: Employee code
            employee_email: Employee's email address
            company_name: Company name
            company_id: Company ID
            login_pin: Login PIN (auto-generated if not provided)
            temporary_password: Temporary password (optional)
        
        Returns:
            True if sent successfully
        """
        try:
            from app.services.email_template import generate_web_login_html, generate_web_login_text
            from app.services.email_template.logo_base64_loader import get_cached_logo_data_url
            from datetime import datetime
            from app.core.config import BASE_URL
            import random
            
            # Get current date in format: 23 Feb 2025
            current_date = datetime.now().strftime("%d %b %Y")
            
            # Generate login PIN if not provided
            if not login_pin:
                # Use last 6 digits of employee code, pad with zeros if needed
                code_digits = ''.join(filter(str.isdigit, employee_code))
                login_pin = code_digits[-6:].zfill(6) if code_digits else str(random.randint(100000, 999999))
            
            # Web portal URL
            web_portal_url = "https://account.runtime.one/"
            
            # Logo URL - use embedded base64 for guaranteed display
            logo_data_url = get_cached_logo_data_url()
            if not logo_data_url:
                # Fallback to server URL if base64 fails
                logo_data_url = f"{BASE_URL}/static/images/runtime-logo.png"
            
            # Template context
            context = {
                "employee_name": employee_name,
                "employee_code": employee_code,
                "email": employee_email,
                "company_name": company_name,
                "company_id": company_id,
                "login_pin": login_pin,
                "logo_url": logo_data_url,
                "web_portal_url": web_portal_url,
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
                "current_date": current_date,
            }
            
            # Add temporary password if provided
            if temporary_password:
                context["temporary_password"] = temporary_password
            
            # Generate HTML content
            html_content = generate_web_login_html(context)
            
            # Generate text content
            text_content = generate_web_login_text(context)
            
            # Send email
            subject = f"Web Portal Login Details - {company_name}"
            
            return await self.send_email(
                to_email=employee_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send web login email: {e}")
            return False
    
    async def send_runtime_workman_email(
        self,
        employee_name: str,
        company_id: str,
        employee_code: str,
        login_pin: str,
        employee_email: str,
        company_name: str = "Levitica Technologies"
    ) -> bool:
        """
        Send Runtime Workman login credentials email to employee.
        
        Args:
            employee_name: Employee's full name
            company_id: Company ID (e.g., LEV001)
            employee_code: Employee code (e.g., LEV040)
            login_pin: Login PIN (e.g., 644894)
            employee_email: Employee's email address
            company_name: Company name
        
        Returns:
            True if sent successfully
        """
        try:
            from app.services.email_template import generate_runtime_workman_html, generate_runtime_workman_text
            from app.services.email_template.logo_base64_loader import get_cached_logo_data_url
            from datetime import datetime
            from app.core.config import BASE_URL
            
            # Get current date in format: 23 Feb 2025
            current_date = datetime.now().strftime("%d %b %Y")
            
            # Logo URL - use embedded base64 for guaranteed display
            logo_data_url = get_cached_logo_data_url()
            if not logo_data_url:
                # Fallback to server URL if base64 fails
                logo_data_url = f"{BASE_URL}/static/images/runtime-logo.png"
            
            # Template context
            context = {
                "employee_name": employee_name,
                "company_id": company_id,
                "employee_code": employee_code,
                "login_pin": login_pin,
                "company_name": company_name,
                "logo_url": logo_data_url,
                "support_email": settings.SMTP_FROM_EMAIL,
                "current_year": datetime.utcnow().year,
                "current_date": current_date,
            }
            
            # Generate HTML content
            html_content = generate_runtime_workman_html(context)
            
            # Generate text content
            text_content = generate_runtime_workman_text(context)
            
            # Send email
            subject = f"Runtime Workman Login Details - {company_name}"
            
            return await self.send_email(
                to_email=employee_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send Runtime Workman email: {e}")
            return False
    
    async def send_birthday_wishes_email(
        self,
        employee_name: str,
        employee_email: str,
        employee_designation: str = "Team Member",
        company_name: str = "Levitica Technologies",
        sender_name: str = "Team"
    ) -> bool:
        """
        Send birthday wishes email to employee.
        
        Args:
            employee_name: Employee's full name
            employee_email: Employee's email address
            employee_designation: Employee's designation
            company_name: Company name
            sender_name: Name of the person/team sending wishes
        
        Returns:
            True if sent successfully
        """
        try:
            from app.services.email_template import generate_birthday_wishes_html, generate_birthday_wishes_text
            from datetime import datetime
            
            # Get current date in format: 23 Feb 2025
            current_date = datetime.now().strftime("%d %b %Y")
            
            # Template context
            context = {
                "employee_name": employee_name,
                "employee_designation": employee_designation,
                "company_name": company_name,
                "sender_name": sender_name,
                "current_year": datetime.utcnow().year,
                "current_date": current_date,
            }
            
            # Generate HTML content
            html_content = generate_birthday_wishes_html(context)
            
            # Generate text content
            text_content = generate_birthday_wishes_text(context)
            
            # Send email
            subject = f"🎉 Happy Birthday {employee_name.split()[0]}! 🎂"
            
            return await self.send_email(
                to_email=employee_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send birthday wishes email: {e}")
            return False


# Global email service instance
email_service = EmailService()
