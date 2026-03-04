from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import IntFlag


class Permission(IntFlag):
    EDIT_KB_URL     = 1 << 0   # 1
    EDIT_GUIDELINES = 1 << 1   # 2
    TOGGLE_AUTOFIX  = 1 << 2   # 4
    REVIEW_MISTAKES = 1 << 3   # 8
    APPROVE_FIXES   = 1 << 4   # 16
    MANAGE_ROLES    = 1 << 5   # 32
    DELETE_BOT      = 1 << 6   # 64

    @classmethod
    def all(cls) -> int:
        return sum(p.value for p in cls)

    @classmethod
    def label(cls, bit: int) -> str:
        try:
            return cls(bit).name.replace("_", " ").title()
        except ValueError:
            return f"Permission {bit}"


class Role(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    bot_id: str
    permission_bitmap: int = 0
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class UserRole(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    role_id: str
    bot_id: str
    granted_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
