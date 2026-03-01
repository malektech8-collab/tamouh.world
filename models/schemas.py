"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123"
            }
        }


class UserLoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123"
            }
        }


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400
            }
        }


class UserResponse(BaseModel):
    """Schema for user response (no password)."""
    id: str
    email: str
    is_active: bool
    plan: str
    credits: int

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "is_active": True,
                "plan": "free",
                "credits": 5
            }
        }


class UserRegisterResponse(BaseModel):
    """Schema for registration response."""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "is_active": True,
                    "plan": "free",
                    "credits": 5
                },
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class ResumeJobResponse(BaseModel):
    """Schema for resume job response."""
    job_id: str
    status: str
    progress: int
    resume: Optional[dict] = None
    audit: Optional[dict] = None
    pdf_url: Optional[str] = None
    error: Optional[str] = None
    metrics: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "processing",
                "progress": 40,
                "error": None,
                "metrics": {
                    "tokens": 1500,
                    "estimated_cost": 0.0023
                }
            }
        }
