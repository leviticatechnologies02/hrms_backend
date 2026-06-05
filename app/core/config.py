"""
Application Configuration
Manages environment variables and application settings
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, EmailStr, field_validator
from typing import List, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv
import json
import os

# Load .env file explicitly
load_dotenv()

# If you already have settings class, integrate these into it.
BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

# Local upload folder (Option A)
UPLOAD_FOLDER = os.path.join("app", "uploads", "business_units")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='allow'
    )
    
    # Application metadata
    APP_NAME: str = "Levitica HR Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database configuration (PostgreSQL)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_NAME: str = "levitica_hr"
    DATABASE_URL: Optional[str] = None
    
    # Database connection pooling
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Redis Cloud Configuration
    REDIS_HOST: str = "redis-16358.crce214.us-east-1-3.ec2.cloud.redislabs.com"
    REDIS_PORT: int = 16358
    REDIS_DB: int = 0
    REDIS_USERNAME: str = "default"
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD")
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_SSL: bool = True  # Redis Cloud requires SSL
    
    # Session Configuration
    SESSION_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ============================================================================
    # SMTP CONFIGURATION
    # ============================================================================
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "False").lower() == "true"
    SMTP_USE_STARTTLS: bool = os.getenv("SMTP_USE_STARTTLS", "True").lower() == "true"

    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "nagendrareddy1017@gmail.com")

    # Gmail app passwords are often shown with spaces; normalize them here.
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")

    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "nagendrareddy1017@gmail.com")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Levitica HRMS")

    SMTP_TIMEOUT: int = int(os.getenv("SMTP_TIMEOUT", "30"))
    EMAIL_SEND_TIMEOUT: int = int(os.getenv("EMAIL_SEND_TIMEOUT", "30"))
    
    # SMS Configuration
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "2factor")  # Options: 'twilio', 'msg91', 'fast2sms', '2factor'

    # 2Factor (https://2factor.in)
    TWO_FACTOR_API_KEY: Optional[str] = os.getenv("TWO_FACTOR_API_KEY")

    # Twilio
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # MSG91
    MSG91_AUTH_KEY: Optional[str] = None
    MSG91_TEMPLATE_ID: Optional[str] = None
    
    # Fast2SMS
    FAST2SMS_API_KEY: Optional[str] = None
    
    # Frontend configuration
    FRONTEND_URL: str = "http://localhost:3000"
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24

    # Email provider selection - options: 'smtp', 'brevo'
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "smtp")

    # Brevo (Sendinblue) configuration
    BREVO_API_KEY: Optional[str] = os.getenv("BREVO_API_KEY")
    BREVO_SENDER_EMAIL: Optional[str] = os.getenv("BREVO_SENDER_EMAIL")
    BREVO_SENDER_NAME: Optional[str] = os.getenv("BREVO_SENDER_NAME")

    def is_brevo_configured(self) -> bool:
        return bool(self.BREVO_API_KEY and self.BREVO_SENDER_EMAIL)

    # CORS settings stored as a comma-separated string to keep .env parsing simple
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,https://levitica-hr-frontend.onrender.com"

    @property
    def backend_cors_origins_list(self) -> List[str]:
        raw_value = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not raw_value:
            return []

        if raw_value.startswith("[") and raw_value.endswith("]"):
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, list):
                    return [str(origin).strip().strip("\"'") for origin in parsed if str(origin).strip()]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return [
            origin.strip().strip("\"'")
            for origin in raw_value.split(",")
            if origin.strip().strip("\"'")
        ]
    
    # File upload settings
    MAX_FILE_SIZE: int = 4 * 1024 * 1024
    UPLOAD_DIR: str = "uploads"
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/jpg,image/gif"
    
    @property
    def allowed_image_types_list(self) -> List[str]:
        """Convert comma-separated string to list"""
        return [mime_type.strip() for mime_type in self.ALLOWED_IMAGE_TYPES.split(',')]
    
    # Default superadmin credentials
    SUPERADMIN_EMAIL: str = "superadmin@levitica.com"
    SUPERADMIN_PASSWORD: str = "Admin@123"
    SUPERADMIN_NAME: str = "Super Administrator"
    
    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        encoded_password = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql://{self.DB_USER}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def redis_url(self) -> str:
        """
        Generate Redis Cloud connection URL with SSL support.
        
        Format: rediss://username:password@host:port/db
        Note: 'rediss://' (with double 's') indicates SSL connection
        """
        protocol = "rediss" if self.REDIS_SSL else "redis"
        
        # URL encode password to handle special characters
        encoded_password = quote_plus(self.REDIS_PASSWORD)
        
        if self.REDIS_USERNAME:
            return f"{protocol}://{self.REDIS_USERNAME}:{encoded_password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"{protocol}://:{encoded_password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @field_validator('SMTP_PASSWORD')
    @classmethod
    def validate_smtp_password(cls, value: Optional[str]) -> Optional[str]:
        if not value or not value.strip():
            import warnings
            warnings.warn("SMTP_PASSWORD is empty. Email functionality will not work.")
            return None
        return value.replace(" ", "").strip()
    
    def is_smtp_configured(self) -> bool:
        return bool(
            self.SMTP_USERNAME and self.SMTP_PASSWORD 
            and self.SMTP_FROM_EMAIL and self.SMTP_HOST
        )


# Global settings instance
settings = Settings()
