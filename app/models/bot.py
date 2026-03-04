from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Bot(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    slug: str
    kb_url: str = "https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card"
    additional_guidelines: str = ""
    auto_fix_enabled: bool = False
    system_prompt: str = ""
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class KBContent(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    bot_id: str
    kb_url: str
    articles: list[dict] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
