"""Pydantic schemas for the shorten API."""

from pydantic import BaseModel


class ShortenRequest(BaseModel):
    long_url: str


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
