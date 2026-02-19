from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    household_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class JoinRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    invite_code: str = Field(min_length=6, max_length=32)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    household_id: str
    household_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    token: TokenResponse
    user: UserResponse


class InviteResponse(BaseModel):
    invite_code: str
    message: str


class DeleteMemberResponse(BaseModel):
    member_id: str
    message: str


class HouseholdMemberResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    created_at: str


class HouseholdOverviewResponse(BaseModel):
    household_id: str
    household_name: str
    invite_code: str | None = None
    members: list[HouseholdMemberResponse]


class HouseholdRenameRequest(BaseModel):
    household_name: str = Field(min_length=2, max_length=120)
