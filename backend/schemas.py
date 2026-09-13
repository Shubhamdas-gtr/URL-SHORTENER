"""Pydantic schemas for the URL shortener API."""

from datetime import datetime

from pydantic import BaseModel


class ShortenRequest(BaseModel):
    long_url: str


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str


class ClicksByDay(BaseModel):
    date: str
    clicks: int


class StatsResponse(BaseModel):
    short_code: str
    long_url: str
    created_at: datetime
    click_count: int
    last_clicked_at: datetime | None
    clicks_by_day: list[ClicksByDay]
