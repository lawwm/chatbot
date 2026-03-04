from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Mistake(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    bot_id: str
    session_id: str
    customer_message: str
    bot_response: str
    complaint: str
    status: str = "open"  # "open" | "fixed"
    suggested_fix: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class MistakeArchive(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    original_id: str
    bot_id: str
    session_id: str
    customer_message: str
    bot_response: str
    complaint: str
    suggested_fix: str
    fix_applied: str
    fixed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
