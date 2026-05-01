#!/usr/bin/env bash
# Example curl invocations for the GitPrompt API.
#
# Usage:
#   export BASE_URL="http://localhost:8000"
#   export JWT="<supabase-issued-jwt>"   # required for write ops + all /account/* routes
#   export API_KEY="gpk-..."              # alternative for read-only prompt routes
#   ./examples/curl_examples.sh           # runs the full walk-through
#
# Or copy individual commands. Both JWT and API key are sent as `Authorization: Bearer <token>`.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
JWT="${JWT:-}"
API_KEY="${API_KEY:-}"

jwt_header() {
  if [[ -z "$JWT" ]]; then
    echo "JWT env var is required for this request" >&2
    exit 1
  fi
  printf 'Authorization: Bearer %s' "$JWT"
}

apikey_header() {
  if [[ -z "$API_KEY" ]]; then
    echo "API_KEY env var is required for this request" >&2
    exit 1
  fi
  printf 'Authorization: Bearer %s' "$API_KEY"
}

# ---------------------------------------------------------------------------
# Health / diagnostics (no auth)
# ---------------------------------------------------------------------------

echo "== GET / =="
curl -sS "$BASE_URL/"; echo

echo "== GET /health =="
curl -sS "$BASE_URL/health"; echo

echo "== GET /healthz =="
curl -sS "$BASE_URL/healthz"; echo

echo "== GET /api/status =="
curl -sS "$BASE_URL/api/status"; echo

# ---------------------------------------------------------------------------
# Prompts CRUD (JWT for writes; JWT or API key for reads)
# ---------------------------------------------------------------------------

echo "== POST /prompts (create) =="
CREATE_RESPONSE=$(curl -sS -X POST "$BASE_URL/prompts" \
  -H "$(jwt_header)" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Example Prompt",
    "description": "Demonstration prompt created by curl_examples.sh",
    "visibility": "private",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hello."}
    ]
  }')
echo "$CREATE_RESPONSE"

# Slug is derived from the title; for the example title it is "example-prompt".
SLUG="example-prompt"

echo "== GET /prompts (list, paginated) [JWT] =="
curl -sS "$BASE_URL/prompts?page=1&page_size=12" \
  -H "$(jwt_header)"; echo

echo "== GET /prompts (list, paginated) [API key] =="
curl -sS "$BASE_URL/prompts?page=1&page_size=12" \
  -H "$(apikey_header)"; echo

echo "== GET /prompts/{slug} [JWT] =="
curl -sS "$BASE_URL/prompts/$SLUG" \
  -H "$(jwt_header)"; echo

echo "== GET /prompts/{slug} [API key] =="
curl -sS "$BASE_URL/prompts/$SLUG" \
  -H "$(apikey_header)"; echo

echo "== PUT /prompts/{slug} (update) =="
curl -sS -X PUT "$BASE_URL/prompts/$SLUG" \
  -H "$(jwt_header)" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Example Prompt",
    "description": "Updated description.",
    "visibility": "public",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hello in French."}
    ]
  }'; echo

echo "== POST /prompts/{slug}/fork =="
curl -sS -X POST "$BASE_URL/prompts/$SLUG/fork" \
  -H "$(jwt_header)" \
  -H "Content-Type: application/json" \
  -d '{
    "new_title": "Example Prompt (forked)",
    "new_description": "Forked variant",
    "new_messages": [
      {"role": "system", "content": "You are a concise assistant."},
      {"role": "user", "content": "Greet the user."}
    ]
  }'; echo

echo "== DELETE /prompts/{slug} =="
curl -sS -X DELETE "$BASE_URL/prompts/$SLUG" \
  -H "$(jwt_header)"; echo

# ---------------------------------------------------------------------------
# Account / API keys (all JWT-gated)
# ---------------------------------------------------------------------------

echo "== POST /account/generate-api-key =="
GEN_RESPONSE=$(curl -sS -X POST "$BASE_URL/account/generate-api-key" \
  -H "$(jwt_header)" \
  -H "Content-Type: application/json" \
  -d '{"name": "example-cli-key"}')
echo "$GEN_RESPONSE"
# Note: the plaintext "key" field is only returned at creation/regeneration. Save it now.

echo "== GET /account/api-keys =="
curl -sS "$BASE_URL/account/api-keys" \
  -H "$(jwt_header)"; echo

# Extract the new key's id for the regenerate/delete examples.
# Requires `jq`; otherwise set KEY_ID manually.
if command -v jq >/dev/null 2>&1; then
  KEY_ID=$(printf '%s' "$GEN_RESPONSE" | jq -r '.id')
else
  KEY_ID="${KEY_ID:-<paste-key-id-here>}"
fi

echo "== POST /account/api-keys/{key_id}/regenerate =="
curl -sS -X POST "$BASE_URL/account/api-keys/$KEY_ID/regenerate" \
  -H "$(jwt_header)" \
  -H "Content-Type: application/json" \
  -d '{}'; echo

echo "== DELETE /account/api-keys/{key_id} =="
curl -sS -X DELETE "$BASE_URL/account/api-keys/$KEY_ID" \
  -H "$(jwt_header)"; echo
