# Health & Diagnostics Endpoints

GitPrompt exposes four unauthenticated endpoints for liveness, readiness, and diagnostics. None of them require a JWT or API key.

| Endpoint | Purpose | DB check | Status code |
|---|---|---|---|
| `GET /` | Liveness banner | No | `200` |
| `GET /health` | Minimal liveness probe | No | `200` |
| `GET /healthz` | Readiness probe (DB + version) | Yes | `200` healthy / `503` degraded |
| `GET /api/status` | Diagnostic route inventory | Yes | `200` |

## `GET /`

Returns a static identifier so a hit on the root URL confirms the process is up.

**Response (`200`):**

```json
{
  "status": "healthy",
  "message": "GitPrompt API is running"
}
```

## `GET /health`

Cheapest liveness probe — no I/O. Suitable for orchestrator liveness checks where any DB blip should not restart the container.

**Response (`200`):**

```json
{
  "status": "ok"
}
```

## `GET /healthz`

Readiness probe. Pings the database with `SELECT 1` and reports the installed package version plus DB latency. Use this for orchestrator readiness checks and to fail traffic over when the DB is unreachable.

- Status `200` when the DB ping succeeds.
- Status `503` when the DB ping raises; the error message is included in the `db` field.
- `version` resolves from the installed `gitprompt` package metadata; returns `"unknown"` if the package is not installed.
- `db_latency_ms` is the round-trip time of the ping in milliseconds.

**Response (`200`, healthy):**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "ok",
  "db_latency_ms": 3.41
}
```

**Response (`503`, DB unreachable):**

```json
{
  "status": "error",
  "version": "0.1.0",
  "db": "error: <exception message>",
  "db_latency_ms": 12.07
}
```

## `GET /api/status`

Diagnostic endpoint that returns the full route inventory along with a DB health flag and per-route reachability. Intended for debugging deployments and verifying that routes that depend on the database are usable.

A route is marked `db_dependent: true` when its FastAPI dependency graph transitively depends on `get_db`. When the DB ping fails, every DB-dependent route is reported as `reachable: false` and the top-level `status` becomes `"degraded"` (the HTTP status remains `200`).

**Response (`200`, healthy):**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "ok",
  "route_count": 14,
  "routes": [
    {
      "path": "/prompts",
      "methods": ["GET"],
      "name": "read_prompts",
      "db_dependent": true,
      "reachable": true
    }
  ]
}
```

**Response (`200`, degraded — DB unreachable):**

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "db": "error",
  "route_count": 14,
  "routes": [
    {
      "path": "/prompts",
      "methods": ["GET"],
      "name": "read_prompts",
      "db_dependent": true,
      "reachable": false
    }
  ]
}
```

## Recommended probe wiring

- **Liveness:** `GET /health` — fast, no dependencies.
- **Readiness:** `GET /healthz` — distinguishes "process up but DB down" via `503`.
- **Debug / dashboards:** `GET /api/status` — full route inventory; not for automated probes.
