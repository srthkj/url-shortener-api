from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime
from typing import Optional


class URLCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = None

    @field_validator("custom_alias")
    @classmethod
    def alias_must_be_alphanumeric(cls, v):
        if v and not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Alias must be alphanumeric (hyphens and underscores allowed)")
        if v and len(v) < 3:
            raise ValueError("Alias must be at least 3 characters")
        return v


class URLResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    custom_alias: Optional[str]
    created_at: datetime
    total_clicks: int
    is_active: bool

    model_config = {"from_attributes": True}


class ClickStat(BaseModel):
    clicked_at: datetime
    browser: Optional[str]
    os: Optional[str]
    device: Optional[str]
    referer: Optional[str]

    model_config = {"from_attributes": True}


class URLAnalytics(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    created_at: datetime
    browser_breakdown: dict[str, int]
    os_breakdown: dict[str, int]
    device_breakdown: dict[str, int]
    recent_clicks: list[ClickStat]
