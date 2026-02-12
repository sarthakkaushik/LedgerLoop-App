# Expense Tracker API

## Local setup (no Docker)

1. Install `uv` and PostgreSQL.
2. Copy `.env.example` to `.env`.
3. Create and sync env:
```bash
uv venv
uv sync --extra dev
```
4. Start API:
```bash
uv run uvicorn app.main:app --reload
```
5. Run tests:
```bash
uv run pytest -q
```

## Database for local run
- Default local DB is SQLite (`sqlite+aiosqlite:///./expense_tracker.db`) so you can run without Docker/Postgres.
- If you want Postgres, change `DATABASE_URL` in `.env` to your local or remote Postgres URL.

## Current API coverage
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/token` (OAuth2 form endpoint for Swagger Authorize)
- `POST /auth/invite`
- `POST /auth/join`
- `GET /auth/me`
- `GET /auth/household` (household members, and invite code for admin)
- `POST /expenses/log` (chat-aware parsing + saves draft rows)
- `POST /expenses/confirm` (confirm/edit drafts with idempotency key)
- `GET /expenses/list` (recent expense feed with `logged_by_name`, household-scoped)
- `GET /expenses/dashboard` (month totals + category/user split + trend)
- `POST /analysis/ask` (hybrid analytics: fixed intents + schema-aware SQL agent fallback with validation, execution, and trace)
- `GET /settings/llm`
- `PUT /settings/llm` (disabled in env-managed mode; returns 409)
- `POST /settings/llm/test`

## LLM provider mode
- Local default: `LLM_PROVIDER=mock` (no external API key required)
- Production recommendation: configure `LLM_PROVIDER`, model, and provider key in backend `.env`.
- Runtime now uses server env values directly (no frontend/API key entry required per household).
