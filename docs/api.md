# GitPrompt API

Reference for the `/prompts` and `/account` endpoints exposed by `main.py`. The service runs on `uvicorn main:app` (port 8000 in Docker).

## Authentication

All authenticated endpoints expect an `Authorization: Bearer <token>` header. Two dependencies are defined in `auth.py`:

- **`get_current_user_id` (JWT only)** — Decodes a Supabase HS256 JWT using `JWT_SECRET_KEY` (algorithm from `JWT_ALGORITHM`, default `HS256`), audience `"authenticated"`. The user id is read from the `sub` claim. Used for every write operation and for all `/account/*` endpoints.
- **`get_current_user_id_readonly` (JWT or API key)** — Tries to decode the bearer value as a JWT first; on failure, looks it up as an API key via `repository.get_api_key_by_key`. Used only on read endpoints that are explicitly listed below.

API keys are 64-character strings prefixed `gpk-`. They are stored as SHA-256(`key + per-key salt`) and compared in constant time on lookup.

| Auth requirement | Endpoints |
| --- | --- |
| None | `GET /`, `GET /health`, `GET /healthz`, `GET /api/status` |
| JWT or API key | `GET /prompts`, `GET /prompts/{prompt_slug}` |
| JWT only | `POST /prompts`, `PUT /prompts/{prompt_slug}`, `DELETE /prompts/{prompt_slug}`, `POST /prompts/{prompt_slug}/fork`, all `/account/*` endpoints |

## Health & diagnostics

These endpoints are unauthenticated and exist for liveness/observability tooling.

### `GET /`
Returns `{ "status": "healthy", "message": "GitPrompt API is running" }`.

### `GET /health`
Returns `{ "status": "ok" }`. Lightweight liveness probe (no DB call).

### `GET /healthz`
Pings the database with `SELECT 1`. Responds `200` when healthy, `503` otherwise.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "ok",
  "db_latency_ms": 4.21
}
```

### `GET /api/status`
Reports DB health plus an inventory of registered routes. For each route returns `path`, `methods`, `name`, `db_dependent` (whether the route depends on `get_db`), and `reachable` (false if `db_dependent` and DB is down).

## Prompts

All prompt endpoints are scoped to the authenticated user.

### `GET /prompts` — list prompts (paginated)

**Auth:** JWT or API key.
**Query params:** `page` (int, default `1`, `>=1`), `page_size` (int, default `12`, `1..100`).
**Response:** `PaginatedPrompts`

```json
{
  "total_prompts": 42,
  "total_pages": 4,
  "current_page": 1,
  "page_size": 12,
  "prompts": [
    {
      "id": "…uuid…",
      "title": "My prompt",
      "description": "",
      "visibility": "private",
      "messages": [{"role": "system", "content": "…"}],
      "title_slug": "my-prompt",
      "created_at": "2026-05-01T12:00:00Z",
      "updated_at": null,
      "forked_from_id": null
    }
  ]
}
```

### `POST /prompts` — create a prompt

**Auth:** JWT.
**Request body:** `PromptCreate`

```json
{
  "title": "My prompt",
  "description": "",
  "visibility": "private",
  "messages": [{"role": "system", "content": "You are…"}]
}
```

Constraints: `title` 3–60 chars, `description` ≤ 1000 chars, `visibility` is `public` or `private`, each message `role` is `system`/`user`/`assistant`.

**Response:** `201` with `PromptCreateResponse` (`{ "id": "…", "created_at": "…" }`).

### `GET /prompts/{prompt_slug}` — fetch a prompt

**Auth:** JWT or API key.
**Response:** `PromptPublicById` — same fields as `PromptPublic` minus `forked_from_id`, plus a nested `forked_from` object when the prompt was forked:

```json
{
  "forked_from": {
    "forked_from_username": "alice",
    "forked_from_prompt_title": "Original title"
  }
}
```

`404` if the slug is not found for the current user.

### `PUT /prompts/{prompt_slug}` — replace a prompt

**Auth:** JWT.
**Request body:** `PromptCreate` (full replacement).
**Response:** `PromptCreateResponse`. `404` if not found.

### `DELETE /prompts/{prompt_slug}`

**Auth:** JWT.
**Response:** `{ "status": "deleted", "prompt_slug": "<slug>" }`. `404` if not found.

### `POST /prompts/{prompt_slug}/fork` — fork a prompt

**Auth:** JWT.
**Request body:** `PromptFork`

```json
{
  "new_title": "My fork",
  "new_description": "optional override",
  "new_messages": [{"role": "user", "content": "…"}]
}
```

`new_title` is required (3–60 chars). `new_description` and `new_messages` are optional; omitted fields are copied from the source prompt.

**Response:** `201` with `PromptPublic`. `404` if the source slug is not found.

## Account / API keys

All account endpoints require JWT auth — API keys cannot manage other API keys.

### `POST /account/generate-api-key` — create an API key

**Auth:** JWT.
**Request body:** `APIKeyCreate` — `{ "name": "<1..255 chars>" }`.
**Response:** `201` with `APIKeyCreateResponse`. The plaintext `key` is returned **once** and cannot be retrieved later.

```json
{
  "id": "…uuid…",
  "name": "ci-bot",
  "key": "gpk-…64 chars…",
  "key_display": "gpk-…abcd",
  "created_at": "2026-05-01T12:00:00Z"
}
```

### `GET /account/api-keys` — list API keys

**Auth:** JWT.
**Response:** array of `APIKeyResponse`.

```json
[
  {
    "id": "…uuid…",
    "name": "ci-bot",
    "key_display": "gpk-…abcd",
    "created_at": "2026-05-01T12:00:00Z",
    "last_used_at": null
  }
]
```

### `POST /account/api-keys/{key_id}/regenerate`

**Auth:** JWT.
**Request body:** none.
**Response:** `201` with `APIKeyCreateResponse` (the plaintext `key` is the new key, returned once). `404` if `key_id` does not exist or does not belong to the user.

### `DELETE /account/api-keys/{key_id}`

**Auth:** JWT. The endpoint additionally verifies that `key_id` belongs to the authenticated user before deleting.
**Response:** `{ "status": "deleted", "key_id": "<uuid>" }`. `404` if the key is missing or owned by another user.

## Errors

Errors are returned in FastAPI's standard shape:

```json
{ "detail": "Prompt not found" }
```

Common statuses: `401` (missing/invalid bearer token), `404` (resource not found / not owned by user), `422` (request body fails Pydantic validation), `503` (`/healthz` when the DB is unreachable).
