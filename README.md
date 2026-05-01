# gitprompt

A FastAPI service for storing, versioning, and forking prompts. Authenticates with Supabase JWTs and supports per-user API keys for read access.

## Overview

- Async FastAPI app backed by Postgres (SQLAlchemy 2.x + asyncpg).
- Two auth modes: Supabase JWT (writes + account management) and API keys (reads only).
- Prompt CRUD with slug-based addressing, public/private visibility, and forking.
- API key lifecycle: create, list, regenerate, delete. Plaintext key returned only at creation/regeneration.

### Endpoints

Health/diagnostics:
- `GET /`, `GET /health`, `GET /healthz` — liveness + DB ping + version
- `GET /api/status` — route inventory and DB health

Prompts:
- `GET /prompts` — paginated list (JWT or API key)
- `POST /prompts` — create (JWT)
- `GET /prompts/{slug}` — fetch by slug (JWT or API key)
- `PUT /prompts/{slug}` — update (JWT)
- `DELETE /prompts/{slug}` — delete (JWT)
- `POST /prompts/{slug}/fork` — fork (JWT)

Account / API keys (all JWT-only):
- `POST /account/generate-api-key`
- `GET /account/api-keys`
- `POST /account/api-keys/{key_id}/regenerate`
- `DELETE /account/api-keys/{key_id}`

Pagination defaults to `page_size=12` (max 100). Both JWTs and API keys are sent as `Authorization: Bearer <token>`.

## Install

Requires Python 3.13+ and [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync --frozen
```

## Run

Local development:

```bash
uv run uvicorn main:app --reload
```

The server listens on port 8000 by default.

Docker:

```bash
docker compose up --build
```

The provided `Dockerfile` uses `python:3.13-slim` and runs `uv run uvicorn main:app --host 0.0.0.0 --port 8000`.

## Environment variables

Configured via a `.env` file (loaded by `python-dotenv` at import time).

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres connection string. `postgres://` is auto-rewritten to `postgresql+asyncpg://`. |
| `JWT_SECRET_KEY` | yes | Supabase JWT signing secret (HS256). |
| `JWT_ALGORITHM` | no | JWT algorithm; defaults to `HS256`. |
| `CORS_ORIGIN` | yes | Single allowed origin for CORS (credentials enabled). |

## Tests

```bash
uv run pytest
```
