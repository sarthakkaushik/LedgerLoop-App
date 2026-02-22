from pydantic import BaseModel, Field

from app.models.family_member import FamilyMemberType


class FamilyMemberCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    member_type: FamilyMemberType = FamilyMemberType.OTHER
    linked_user_id: str | None = None


class FamilyMemberUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    member_type: FamilyMemberType | None = None
    linked_user_id: str | None = None
    is_active: bool | None = None


class FamilyMemberResponse(BaseModel):
    id: str
    household_id: str
    full_name: str
    normalized_name: str
    member_type: str
    linked_user_id: str | None = None
    linked_user_name: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


class FamilyMemberListResponse(BaseModel):
    items: list[FamilyMemberResponse]


class FamilyMemberDeleteResponse(BaseModel):
    family_member_id: str
    message: str


class FamilyMemberBootstrapResponse(BaseModel):
    created_count: int
    items: list[FamilyMemberResponse]
