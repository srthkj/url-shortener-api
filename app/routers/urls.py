from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.schemas import URLCreate, URLResponse, URLAnalytics
from app.services.url_service import url_service
from app.config import settings

health_router = APIRouter()
router = APIRouter()


@health_router.get("/health", summary="Health check")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/shorten", response_model=URLResponse, status_code=201, summary="Shorten a URL")
def shorten_url(payload: URLCreate, db: Session = Depends(get_db)):
    """
    Create a shortened URL. Optionally provide a custom alias.

    - **original_url**: The full URL to shorten
    - **custom_alias**: Optional custom slug (e.g. `my-link`)
    """
    return url_service.create_short_url(db, payload)


@router.get("/urls", response_model=list[URLResponse], summary="List all shortened URLs")
def list_urls(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated list of all shortened URLs with click counts."""
    return url_service.list_urls(db, limit, offset)


@router.get("/analytics/{code}", response_model=URLAnalytics, summary="Get click analytics")
def get_analytics(code: str, db: Session = Depends(get_db)):
    """
    Detailed analytics for a shortened URL:
    - Total clicks
    - Browser, OS, and device breakdowns
    - 10 most recent clicks
    """
    return url_service.get_analytics(db, code)


@router.delete("/urls/{code}", summary="Deactivate a short URL")
def deactivate_url(code: str, db: Session = Depends(get_db)):
    """Deactivates a short URL so it no longer redirects."""
    return url_service.deactivate_url(db, code)


@router.get("/{code}", summary="Redirect to original URL", include_in_schema=False)
def redirect(code: str, request: Request, db: Session = Depends(get_db)):
    """Resolves the short code and redirects, logging analytics data."""
    original_url = url_service.resolve_url(
        db=db,
        code=code,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )
    return RedirectResponse(url=original_url, status_code=302)
