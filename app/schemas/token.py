"""
Token and Authentication Schemas
"""

from pydantic import BaseModel, EmailStr
from .user import AdminResponse


class LoginRequest(BaseModel):
    """Login request with email and password."""
    
    email: EmailStr
    password: str
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "chandupatel.1434@gmail.com",
                    "password": "Chandu@1434"
                }
            ]
        }
    }


class TokenResponse(BaseModel):
    """JWT token response with user data."""
    
    access_token: str
    token_type: str = "bearer"
    user: AdminResponse
    
    model_config = {"from_attributes": True}


class TokenData(BaseModel):
    """Decoded token payload data."""
    
    email: str | None = None
    role: str | None = None