from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Session(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    class Config:
        populate_by_name = True
