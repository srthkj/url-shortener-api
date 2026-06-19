import random
import string
from collections import Counter
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ua_parser import user_agent_parser

from app.config import settings
from app.db.database import URL, Click
from app.models.schemas import URLCreate, URLResponse, URLAnalytics, ClickStat


def _generate_short_code(length: int = settings.short_code_length) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _build_short_url(code: str) -> str:
    return f"{settings.base_url}/{code}"


def _parse_user_agent(ua_string: str | None) -> dict:
    if not ua_string:
        return {"browser": "Unknown", "os": "Unknown", "device": "Unknown"}
    parsed = user_agent_parser.Parse(ua_string)
    browser = parsed["user_agent"]["family"]
    os = parsed["os"]["family"]
    device_family = parsed["device"]["family"]
    if device_family in ("Spider", "Other"):
        device = "Desktop"
    elif any(k in device_family.lower() for k in ("phone", "mobile")):
        device = "Mobile"
    elif "tablet" in device_family.lower() or "ipad" in device_family.lower():
        device = "Tablet"
    else:
        device = "Desktop"
    return {"browser": browser, "os": os, "device": device}


class URLService:

    def create_short_url(self, db: Session, payload: URLCreate) -> URLResponse:
        original = str(payload.original_url)

        if payload.custom_alias:
            existing = db.query(URL).filter(URL.custom_alias == payload.custom_alias).first()
            if existing:
                raise HTTPException(status_code=409, detail="Custom alias already taken")

        for _ in range(10):
            code = _generate_short_code()
            if not db.query(URL).filter(URL.short_code == code).first():
                break
        else:
            raise HTTPException(status_code=500, detail="Could not generate unique code")

        url = URL(
            original_url=original,
            short_code=code,
            custom_alias=payload.custom_alias,
        )
        db.add(url)
        db.commit()
        db.refresh(url)

        return URLResponse(
            short_code=url.short_code,
            short_url=_build_short_url(url.custom_alias or url.short_code),
            original_url=url.original_url,
            custom_alias=url.custom_alias,
            created_at=url.created_at,
            total_clicks=0,
            is_active=url.is_active,
        )

    def resolve_url(
        self,
        db: Session,
        code: str,
        ip: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> str:
        url = (
            db.query(URL)
            .filter((URL.short_code == code) | (URL.custom_alias == code))
            .filter(URL.is_active == True)
            .first()
        )
        if not url:
            raise HTTPException(status_code=404, detail="Short URL not found or inactive")

        ua_data = _parse_user_agent(user_agent)
        click = Click(
            url_id=url.id,
            ip_address=ip,
            user_agent=user_agent,
            referer=referer,
            **ua_data,
        )
        db.add(click)
        db.commit()

        return url.original_url

    def get_analytics(self, db: Session, code: str) -> URLAnalytics:
        url = (
            db.query(URL)
            .filter((URL.short_code == code) | (URL.custom_alias == code))
            .first()
        )
        if not url:
            raise HTTPException(status_code=404, detail="URL not found")

        clicks = url.clicks
        recent = sorted(clicks, key=lambda c: c.clicked_at, reverse=True)[:10]

        return URLAnalytics(
            short_code=url.short_code,
            original_url=url.original_url,
            total_clicks=len(clicks),
            created_at=url.created_at,
            browser_breakdown=dict(Counter(c.browser or "Unknown" for c in clicks)),
            os_breakdown=dict(Counter(c.os or "Unknown" for c in clicks)),
            device_breakdown=dict(Counter(c.device or "Unknown" for c in clicks)),
            recent_clicks=[
                ClickStat(
                    clicked_at=c.clicked_at,
                    browser=c.browser,
                    os=c.os,
                    device=c.device,
                    referer=c.referer,
                )
                for c in recent
            ],
        )

    def deactivate_url(self, db: Session, code: str) -> dict:
        url = db.query(URL).filter(URL.short_code == code).first()
        if not url:
            raise HTTPException(status_code=404, detail="URL not found")
        url.is_active = False
        db.commit()
        return {"message": f"URL '{code}' has been deactivated"}

    def list_urls(self, db: Session, limit: int = 20, offset: int = 0) -> list[URLResponse]:
        urls = db.query(URL).offset(offset).limit(limit).all()
        return [
            URLResponse(
                short_code=u.short_code,
                short_url=_build_short_url(u.custom_alias or u.short_code),
                original_url=u.original_url,
                custom_alias=u.custom_alias,
                created_at=u.created_at,
                total_clicks=u.total_clicks,
                is_active=u.is_active,
            )
            for u in urls
        ]


url_service = URLService()
