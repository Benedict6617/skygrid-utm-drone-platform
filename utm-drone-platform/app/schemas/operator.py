from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class OperatorCreate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=120)
    contact_email: EmailStr
    password: str = Field(..., min_length=8)
    faa_certificate_number: Optional[str] = None
    phone_number: Optional[str] = None


class OperatorOut(BaseModel):
    id: str
    company_name: str
    contact_email: EmailStr
    faa_certificate_number: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    contact_email: EmailStr
    password: str
