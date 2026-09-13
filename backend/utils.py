"""URL normalization and Base62 encoding helpers."""

import re
from urllib.parse import urlsplit

BASE62_ALPHABET: str = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

MAX_URL_LENGTH: int = 2048

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def encode_base62(number: int) -> str:
    """Encode a non-negative integer as a Base62 string."""
    if not isinstance(number, int) or isinstance(number, bool):
        raise ValueError("number must be an integer")
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return BASE62_ALPHABET[0]
    base = len(BASE62_ALPHABET)
    digits: list[str] = []
    while number:
        number, remainder = divmod(number, base)
        digits.append(BASE62_ALPHABET[remainder])
    return "".join(reversed(digits))


def normalize_url(url: str) -> str:
    """Trim, default scheme, and validate a URL. Returns the normalized URL."""
    if not isinstance(url, str):
        raise ValueError("URL must be a string")
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL must not be empty")
    if len(cleaned) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters")
    if " " in cleaned or "\t" in cleaned or "\n" in cleaned:
        raise ValueError("URL must not contain whitespace")
    # Default to https when the user omits the scheme ("google.com").
    if not _SCHEME_RE.match(cleaned):
        cleaned = "https://" + cleaned
    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("URL scheme must be http or https")
    if not parsed.hostname:
        raise ValueError("URL is malformed")
    if len(cleaned) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters")
    return cleaned
