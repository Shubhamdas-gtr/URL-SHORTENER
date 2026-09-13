"""Database-backed URL creation service."""

from sqlalchemy.orm import Session

from backend.models import Click, Url
from backend.utils import encode_base62, normalize_url


def create_url(db: Session, long_url: str) -> Url:
    """Validate the URL, insert a row to get its id, then assign Base62(id).

    Uses the DB-assigned primary key as the uniqueness source, so no
    random codes, hashing, or collision retries are needed.
    """
    normalized = normalize_url(long_url)
    # Placeholder short_code: NOT NULL column, replaced with Base62(id)
    # after flush assigns the id. Single transaction: failure rolls back
    # so no partial row is left behind.
    url = Url(long_url=normalized, short_code="")
    try:
        db.add(url)
        db.flush()  # assigns url.id without committing yet
        url.short_code = encode_base62(url.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(url)
    return url


def register_click(
    db: Session, url: Url, ip_address: str | None, user_agent: str | None
) -> None:
    """Record a click and bump the counter in a single transaction.

    Simple read/increment/write is fine for this MVP; a future step
    could use an atomic UPDATE (click_count = click_count + 1).
    """
    try:
        db.add(Click(url_id=url.id, ip_address=ip_address, user_agent=user_agent))
        url.click_count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
