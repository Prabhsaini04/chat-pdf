import uuid

from pydantic import BaseModel, EmailStr, Field

# Minimum length over complexity rules (AUTHENTICATION_AUTHORIZATION_STANDARDS.md).
# 8 is an ASSUMPTION (NIST-aligned default), not a confirmed product
# requirement — flag for Security to confirm, same as other ENG-CPD-003
# open items.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class SignupResponse(BaseModel):
    account_id: uuid.UUID


class AccountOut(BaseModel):
    account_id: uuid.UUID
    email: str
