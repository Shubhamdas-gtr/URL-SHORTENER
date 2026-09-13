# URL Shortener

A simple full-stack URL shortening service: paste a long URL, get a short link, track clicks with per-day analytics, browse recent URLs, and share links via QR code.

## Project Objective

The goal of this project is to learn and demonstrate how a real client/server web application fits together: a REST API backend with a relational database, a separate frontend that talks to it over HTTP, and the classic backend concerns — validation, persistence, transactions, and analytics — kept small enough to explain in an interview.

## Features

- Shorten long URLs into compact links (e.g. `http://localhost:8000/2`)
- URL validation and normalization (trims input, defaults missing scheme to `https://`, accepts only `http`/`https`, rejects empty/overlong/whitespace URLs)
- Redirect short links to the original URL with HTTP 307
- Click tracking: every redirect records a click event and increments a counter
- Analytics per short code: total clicks, last-clicked time, clicks grouped by day (with a bar chart)
- Recent URL history (newest-first, configurable limit)
- QR code generation for each short URL, with PNG download
- Interactive API docs via FastAPI/Swagger

## Architecture

The frontend and backend are separate processes. The frontend never touches the database — all data flows through the backend's HTTP API.

```text
User / Browser
      ↓
Streamlit (:8501)            ← UI: forms, analytics charts, QR codes
      ↓ HTTP (requests, JSON)
FastAPI (:8000)              ← REST API: shorten, redirect, stats, history
      ↓
SQLAlchemy                   ← ORM: models, sessions, transactions
      ↓
SQLite (urls.db)             ← persistence: urls + clicks tables
```

## Technology Stack

- **Python** — the single language for backend, frontend, and data access.
- **FastAPI** — backend web framework; routing, request handling, and automatic interactive docs (`/docs`).
- **Pydantic** — request/response validation and serialization (FastAPI builds on it; e.g. a missing `long_url` is rejected with 422 before any app code runs).
- **SQLAlchemy** — ORM for defining the `urls`/`clicks` tables, querying, and managing sessions/transactions.
- **SQLite** — file-based relational database (`urls.db`); zero-setup, ideal for local development and interviews.
- **Streamlit** — frontend framework; the UI in `frontend/app.py` renders forms/charts and calls the backend over HTTP.
- **requests** — HTTP client the Streamlit frontend uses to call the FastAPI backend (with timeouts and backend-down messaging).
- **qrcode[pil]** — generates a QR code image for each short URL (the `[pil]` extra provides image/PNG support via Pillow).
- **Base62** — the short-code encoding: the alphabet `0-9a-zA-Z` (62 characters) converts a numeric database ID into a short, URL-safe string.

## Project Structure

Actual repository layout (no test suite is checked in; regression testing was done ad hoc — see [Testing](#testing)):

```text
URL-SHORTENER/
├── app.py               # Early placeholder Streamlit page (not the app entrypoint)
├── requirements.txt     # Runtime + test-workflow dependencies
├── urls.db              # SQLite file, created at runtime (git-ignored)
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes, lifespan, DB dependency
│   ├── config.py        # BASE_DIR, DB path/URL, BASE_URL
│   ├── database.py      # Engine, SessionLocal, Base, init_db()
│   ├── models.py        # Url and Click SQLAlchemy models
│   ├── schemas.py       # Pydantic request/response models
│   ├── services.py      # create_url() and register_click() transactions
│   └── utils.py         # URL normalization + Base62 helpers
└── frontend/
    └── app.py           # Streamlit UI (shorten, analytics, recent URLs, QR)
```

## How URL Shortening Works

`POST /api/shorten` → `create_url()` in `backend/services.py`:

1. **URL validation** — `normalize_url()` trims the input, prepends `https://` when no scheme is given, and rejects empty URLs, URLs over 2048 characters, URLs containing whitespace, non-`http`/`https` schemes, and malformed hosts. Failures raise `ValueError`, which the API translates to `400`.
2. **Database insert** — a `Url` row is added with a placeholder `short_code` (the column is `NOT NULL`, so it can't be left empty).
3. **Flush** — `db.flush()` sends the INSERT without committing, so the database assigns the row its autoincrement **ID** while the transaction is still open.
4. **Base62 conversion** — the ID is encoded with `encode_base62()` (e.g. ID `62` → `"10"`). Because IDs are unique, codes are unique with no random generation, hashing, or collision retries.
5. **short_code storage** — the code is written onto the row and the transaction is **committed** (any failure rolls back, leaving no partial row).
6. **Response** — the API returns `201` with the code, the full short URL built from `BASE_URL`, and the normalized long URL:

```json
{ "short_code": "2", "short_url": "http://localhost:8000/2", "long_url": "https://example.com/some/long/path" }
```

## Redirect Flow

`GET /{short_code}` (registered after all `/api/*` routes so it never shadows them):

```text
short_code lookup → click creation → click_count increment → transaction commit → 307 redirect
```

1. Look up the `Url` row by `short_code`; unknown codes return `404`.
2. Insert a `Click` row (`url_id`, timestamp, client IP, user agent).
3. Increment `Url.click_count`.
4. Commit both in a single transaction (failure rolls back and returns `500`).
5. Return `307 Temporary Redirect` to the stored long URL (307 preserves the request method, unlike 302).

## Analytics

`GET /api/stats/{short_code}` derives analytics from two sources:

- **`click_count`** — a fast counter column on `urls`, incremented on every redirect.
- **`Click` records** — one row per redirect in `clicks`, each with its own timestamp.
- **`last_clicked_at`** — the maximum `clicked_at` across the URL's clicks (`null` when there are no clicks yet).
- **`clicks_by_day`** — clicks grouped by calendar date (`YYYY-MM-DD` → count), sorted ascending; the frontend renders this as a bar chart.

Example response:

```json
{
  "short_code": "2",
  "long_url": "https://example.com/some/long/path",
  "created_at": "2026-09-13T19:54:48.887280",
  "click_count": 3,
  "last_clicked_at": "2026-09-13T20:01:10.123456",
  "clicks_by_day": [{ "date": "2026-09-13", "clicks": 3 }]
}
```

## Recent URL History

`GET /api/urls` returns the most recently created URLs, **newest-first**:

- Default limit is **10**; `?limit=` accepts **1–50** (anything outside that range is rejected with 422).
- Each item contains `short_code`, `short_url`, `long_url`, and `created_at`.

```json
[{ "short_code": "3", "short_url": "http://localhost:8000/3", "long_url": "https://example.com/x", "created_at": "2026-09-13T19:59:22.877000" }]
```

## QR Code

- The QR code encodes the **short URL** (so scanning it visits the redirect, which also records a click).
- It is generated **in memory** with `qrcode.make()` and served as **PNG bytes** — shown in the UI with an optional **PNG download** button.
- It is **not stored in the database**; it is regenerated from the short URL whenever the result panel renders.

## Database Schema

Two tables in SQLite (`urls.db`, created automatically at backend startup via `init_db()`):

**`urls`** — one row per shortened link:

| Column       | Type        | Notes                                              |
| ------------ | ----------- | -------------------------------------------------- |
| `id`         | INTEGER     | Primary key, autoincrement                         |
| `short_code` | VARCHAR(16) | Unique, indexed; Base62 of `id`                    |
| `long_url`   | TEXT        | Normalized URL, not null                           |
| `created_at` | DATETIME    | Not null                                           |
| `click_count`| INTEGER     | Not null, default 0                                |

**`clicks`** — one row per redirect:

| Column       | Type         | Notes                                              |
| ------------ | ------------ | -------------------------------------------------- |
| `id`         | INTEGER      | Primary key, autoincrement                         |
| `url_id`     | INTEGER      | Foreign key → `urls.id`, indexed, not null         |
| `clicked_at` | DATETIME     | Not null                                           |
| `ip_address` | VARCHAR(64)  | Nullable                                           |
| `user_agent` | VARCHAR(512) | Nullable                                           |

Relationship: **`Url` 1 ──── \* `Click`** — `Url.clicks` / `Click.url` with `cascade="all, delete-orphan"`, so deleting a URL removes its clicks. The `short_code` unique constraint plus its index guarantees code uniqueness and fast redirect lookups; the `url_id` index keeps per-URL click queries fast.

## API Documentation

Interactive docs are served by the backend at `/docs` (Swagger UI) and `/openapi.json`.

### POST /api/shorten — create a short URL

- **Input:** JSON body `{ "long_url": "example.com/some/path" }`
- **Success:** `201` with `{ "short_code", "short_url", "long_url" }` (see example in [How URL Shortening Works](#how-url-shortening-works))
- **Errors:** `400` invalid URL (empty, bad scheme, malformed, too long, whitespace); `422` missing/wrong-typed field; `500` unexpected server error

### GET /{short_code} — redirect to the original URL

- **Purpose:** look up the code, record the click, and redirect
- **Success:** `307 Temporary Redirect` with a `Location` header pointing at the long URL
- **Errors:** `404` unknown short code; `500` click-recording failure

### GET /api/stats/{short_code} — analytics for a code

- **Success:** `200` with `{ "short_code", "long_url", "created_at", "click_count", "last_clicked_at", "clicks_by_day" }` (see example in [Analytics](#analytics))
- **Errors:** `404` unknown short code

### GET /api/urls — recent URLs, newest-first

- **Input:** optional query param `?limit=` (default `10`, allowed `1`–`50`)
- **Success:** `200` with a JSON array of `{ "short_code", "short_url", "long_url", "created_at" }`
- **Errors:** `422` when `limit` is outside 1–50

## Running Locally

Backend (serves the API at `http://localhost:8000`, docs at `http://localhost:8000/docs`):

```bash
uvicorn backend.main:app --reload --port 8000
```

Frontend (serves the UI at `http://localhost:8501` — requires the backend to be running):

```bash
streamlit run frontend/app.py
```

| Service  | URL                   |
| -------- | --------------------- |
| Backend  | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Frontend | http://localhost:8501 |

Note: `app.py` in the project root is an early placeholder page, not an entrypoint — the real frontend is `frontend/app.py`.

## Testing

There is **no permanent automated test suite checked into the repository** (no `tests/` directory or `test_*.py` files). The project was instead verified with an ad-hoc regression run (FastAPI `TestClient` against an isolated in-memory database, plus live probes against the real SQLite file with test rows cleaned up afterwards):

- **52/52 API checks passed**, covering: shorten happy path + scheme defaulting + code uniqueness; all invalid-input cases (empty, whitespace, `ftp://`, embedded spaces, overlong, missing/wrong-typed field); redirect 307 + `Location` + unknown-code 404; click counting across repeated redirects; stats shape incl. zero-click URLs; history ordering and limit validation (0/51 → 422); route ordering (`/api/*` before `/{short_code}`); `/openapi.json` and `/docs` reachability; Base62 encode/reject unit cases; URL-normalization reject cases; and service rollback leaving no partial row.
- **Database integrity passed**: `integrity_check = ok`, no foreign-key violations, no orphan clicks, no empty/duplicate codes, no `click_count` mismatches.
- **Frontend passed**: HTTP-only access (no direct DB imports), all three API integrations, timeouts + backend-down messaging, QR generation/download, analytics chart, recent-URL list; all source files compile.

## Design Decisions / Trade-offs

- **Why FastAPI + Streamlit** — FastAPI gives a typed REST API with free interactive docs; Streamlit gives a working UI in one Python file with no frontend toolchain. Both are Python, keeping the project approachable.
- **Why SQLite** — zero-setup file database; perfect for local development and easy to reason about in an interview.
- **Why SQLAlchemy** — the ORM maps `Url`/`Click` cleanly, manages sessions, and expresses relationships, cascades, and transactions without hand-written SQL.
- **Why Base62** — `0-9a-zA-Z` is compact and URL-safe without escaping (unlike Base64's `+/=`).
- **Why ID-based codes** — the autoincrement primary key is already unique, so codes need no randomness, hashing, or collision-retry loops. One subtlety this creates: the same long URL submitted twice gets two different codes (each insert is a new row).
- **Why no fixed code length** — codes are the natural variable-length Base62 representation of the ID (`1`, `2`, … `10`, …), so no truncation (which could collide) or zero-padding (which adds no value) is needed. There is intentionally no `CODE_LENGTH` setting.
- **Why QR is not stored** — the QR is a deterministic rendering of the short URL; storing it would duplicate data. It is cheaper to regenerate it in memory on demand.
- **Why the frontend doesn't access the database** — client/server separation: the API owns validation and persistence, so rules can't be bypassed and either side can be replaced independently.
- **Why analytics stores click events plus click_count** — `click_count` gives O(1) totals; the `Click` rows preserve per-event detail (timestamps for `clicks_by_day`/`last_clicked_at`, plus IP/user-agent). The trade-off is keeping the two consistent, which the single-transaction `register_click()` handles.

## Current Limitations

Honest constraints of the present implementation:

- SQLite is not ideal for high-scale concurrent workloads (single-file, limited write concurrency).
- Base62 IDs are **predictable/enumerable** — anyone can guess neighboring short codes.
- The `click_count` read/increment/write can **race** under concurrent redirects (lost updates); there is no atomic `UPDATE ... SET click_count = click_count + 1` yet.
- No authentication — anyone can shorten URLs and view any code's analytics.
- No rate limiting — the shorten endpoint could be spammed.
- No abuse/malicious-URL protection — phishing/malware destinations are not screened.
- Analytics are basic (totals + per-day counts only; no referrers, geography, unique-visitor dedup).
- No caching — every redirect hits the database.
- No production observability — no structured logging, metrics, or alerting.

## Production Evolution

These are **future/production improvements, NOT current implementation**:

- **PostgreSQL** (or another server database) for concurrent writes and durability.
- **Redis/cache** for hot short-code lookups to take redirect traffic off the database.
- **Atomic counters** (`click_count = click_count + 1` in a single UPDATE) to remove the increment race.
- **Load balancer + multiple API instances** for availability and scale-out (the app is already stateless apart from the DB).
- **Rate limiting** on shorten/redirect endpoints.
- **Abuse protection**: blocklists/allow-lists, malware/phishing screening, link expiration and reporting.
- **HTTPS** termination and secure deployment configuration.
- **Observability**: structured logs, request metrics, error tracking, dashboards/alerts.
- **Random/non-enumerable codes** (with collision retries) if unpredictability matters more than the simplicity of ID-based codes.

## Interview Talking Points

The concepts this project demonstrates, in one line each:

- **Client/server separation** — Streamlit UI and FastAPI API are independent processes communicating only over HTTP/JSON.
- **REST API** — resource-oriented endpoints (`POST /api/shorten`, `GET /{code}`, `GET /api/stats/{code}`, `GET /api/urls`) with proper status codes (201/307/400/404/422/500).
- **Base62** — compact URL-safe encoding of integers using a 62-character alphabet.
- **Primary key and uniqueness** — the autoincrement `id` is the uniqueness source for codes; `short_code` has its own unique constraint as a second line of defense.
- **Foreign keys** — `clicks.url_id → urls.id` links each click event to its URL.
- **Indexes** — on `short_code` (redirect lookups) and `url_id` (per-URL click queries).
- **Transactions** — create and click-recording each commit atomically, rolling back on failure so no partial state survives.
- **flush vs commit** — `flush()` obtains the DB-assigned ID inside the open transaction; `commit()` makes it durable.
- **Dependency injection** — FastAPI's `Depends(get_db)` supplies a fresh DB session per request and closes it afterwards (overridable in tests).
- **Pydantic validation** — schemas reject malformed requests (e.g. missing `long_url` → 422) before business logic runs.
- **Redirects** — 307 Temporary Redirect preserves the request method while sending the browser to the long URL.
- **Concurrency** — the current read-modify-write counter can race; the fix is an atomic increment.
- **Scaling** — path to production: Postgres, caching, stateless replicas behind a load balancer, rate limiting, observability.
