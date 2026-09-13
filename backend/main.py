"""FastAPI application for the URL shortener."""

from collections import Counter
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.config import BASE_URL
from backend.database import SessionLocal, init_db
from backend.models import Url
from backend.schemas import (
    ClicksByDay,
    ShortenRequest,
    ShortenResponse,
    StatsResponse,
)
from backend.services import create_url, register_click


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    init_db()
    yield


app = FastAPI(title="URL Shortener API", lifespan=lifespan)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/api/shorten", response_model=ShortenResponse, status_code=201)
def shorten_url(payload: ShortenRequest, db: Session = Depends(get_db)) -> ShortenResponse:
    try:
        url = create_url(db, payload.long_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    return ShortenResponse(
        short_code=url.short_code,
        short_url=f"{BASE_URL.rstrip('/')}/{url.short_code}",
        long_url=url.long_url,
    )


# API routes first so the catch-all below never shadows them.
@app.get("/api/stats/{short_code}", response_model=StatsResponse)
def get_stats(short_code: str, db: Session = Depends(get_db)) -> StatsResponse:
    url = db.query(Url).filter(Url.short_code == short_code).first()
    if url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    clicks = url.clicks  # via Url.clicks <-> Click.url relationship
    last_clicked_at = max((c.clicked_at for c in clicks), default=None)
    per_day = Counter(c.clicked_at.date().isoformat() for c in clicks)
    return StatsResponse(
        short_code=url.short_code,
        long_url=url.long_url,
        created_at=url.created_at,
        click_count=url.click_count,
        last_clicked_at=last_clicked_at,
        clicks_by_day=[
            ClicksByDay(date=date, clicks=per_day[date]) for date in sorted(per_day)
        ],
    )


# Defined after /api/* so fixed routes (docs, openapi, api) match first.
@app.get("/{short_code}")
def redirect_to_url(
    short_code: str, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    url = db.query(Url).filter(Url.short_code == short_code).first()
    if url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        register_click(db, url, ip_address, user_agent)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    return RedirectResponse(url=url.long_url, status_code=307)
