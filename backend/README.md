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
- `POST /auth/clerk/exchange` (verify Clerk session and exchange to app token)
- `POST /auth/clerk/onboarding/create` (first-time Clerk user creates household)
- `POST /auth/clerk/onboarding/join` (first-time Clerk user joins via invite code)
- `GET /auth/me`
- `GET /auth/household` (household members, and invite code for admin)
- `POST /expenses/log` (chat-aware parsing + saves draft rows)
- `POST /expenses/transcribe-audio` (voice note transcription via Groq Whisper; returns text for Capture/Insights query boxes)
- `POST /expenses/confirm` (confirm/edit drafts with idempotency key)
- `GET /expenses/list` (recent expense feed with `logged_by_name`, household-scoped)
- `GET /expenses/dashboard` (month totals + category/user split + trend)
- `POST /analysis/ask` (fixed intents + schema-aware SQL agent with 3-attempt auto-repair, safe SQL validation, execution trace, and DB logging)
- `GET /settings/llm`
- `PUT /settings/llm` (disabled in env-managed mode; returns 409)
- `POST /settings/llm/test`

## LLM provider mode
- Local default: `LLM_PROVIDER=mock` (no external API key required)
- Production recommendation: configure `LLM_PROVIDER`, model, and provider key in backend `.env`.
- Runtime now uses server env values directly (no frontend/API key entry required per household).
- Cerebras mode: set `LLM_PROVIDER=cerebras`, `CEREBRAS_API_KEY`, and `CEREBRAS_MODEL=gpt-oss-120b`.
- Groq mode: set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL` (for example `moonshotai/kimi-k2-instruct-0905`).
- OpenAI mode: set `LLM_PROVIDER=openai` with `OPENAI_API_KEY`; analytics SQL agent uses OpenAI Agents SDK and injects live DB schema into system instructions on each request.
- Voice transcription: set `GROQ_API_KEY` and optionally `GROQ_WHISPER_MODEL` (default `whisper-large-v3-turbo`) and `VOICE_MAX_UPLOAD_MB` (default `10`).

## Clerk auth mode (optional)
- Enable with `CLERK_ENABLED=true`.
- Set `CLERK_ISSUER` to your Clerk JWT issuer URL.
- Optional overrides: `CLERK_JWKS_URL`, `CLERK_AUTHORIZED_PARTIES` (comma-separated `azp` list), `CLERK_JWT_AUDIENCE`.
- The exchange/onboarding endpoints require an email claim in the Clerk session token.
