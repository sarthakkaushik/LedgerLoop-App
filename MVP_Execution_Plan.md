# Expense Tracker MVP Execution Plan

Last updated: 2026-02-07

## 1) Product Goal
Build a chat-first family expense tracker for a household (husband and wife), validate with local testing first, then deploy online for real usage.

## 2) MVP Success Criteria
- Two users can join one household and log expenses through chat.
- Draft -> confirm/edit flow prevents wrong LLM entries.
- Dashboard shows monthly spend, category split, and user split.
- Analytics questions are answered with safe predefined query intents.
- User can configure LLM provider and model from Settings.
- App handles concurrent requests without data leaks across households.

## 3) MVP Scope (In)
- Auth: register/login + household invite/join.
- Expense ingestion: natural language to structured draft via LLM.
- Draft confirmation and manual edit before DB save.
- Dashboard APIs and charts.
- Analysis chat using intent-based analytics (not open SQL generation).
- Settings page for LLM provider config (OpenAI/Gemini in v1).
- Recurring expense drafts via scheduled job.
- Local run without Docker (native Python + Node setup).

## 4) Non-Goals (Out for MVP)
- Open-ended text-to-SQL from users.
- Advanced budgeting rules and forecasting.
- Bank integrations and auto-sync.
- Multi-household per user.

## 5) Recommended Stack
- Backend: FastAPI (async endpoints), Pydantic v2.
- DB: PostgreSQL + SQLModel/SQLAlchemy async engine (parity for cloud deploy).
- Cache/Queue (optional MVP+): Redis for throttling or queued jobs.
- Frontend: React + Tailwind + charts (Recharts).
- Auth: JWT access/refresh tokens.
- LLM calls: provider adapters over async HTTP clients.
- Scheduler: APScheduler for local dev, then platform cron/worker in production.

## 6) Data Model (MVP)

### household
- id (uuid)
- name
- invite_code (unique)
- created_at

### user
- id (uuid)
- email (unique)
- hashed_password
- full_name
- household_id (fk)
- role (admin/member)
- created_at

### expense
- id (uuid)
- household_id (fk, indexed)
- logged_by_user_id (fk)
- amount (numeric)
- currency (default INR)
- category
- description
- is_recurring (bool)
- recurrence_day (int nullable)
- status (draft/confirmed)
- date_incurred
- created_at

### llm_setting (per household)
- id (uuid)
- household_id (fk, unique)
- provider (openai/gemini)
- model
- api_key_encrypted
- is_active
- created_at
- updated_at

### parse_log (audit)
- id (uuid)
- household_id (fk)
- user_id (fk)
- input_text
- llm_output_json
- validation_errors
- created_at

## 7) Tenant Isolation Rules (Critical)
- Derive `household_id` from JWT user context only.
- Never trust client-provided `household_id`.
- Every query must include household filter at repository/service layer.
- Add tests that prove cross-household reads/writes fail.

## 8) LLM Provider Settings Design
- Settings UI:
  - Provider dropdown: OpenAI, Gemini.
  - Model input/dropdown.
  - API key input (masked, replace flow).
  - Test connection button.
- Storage:
  - Encrypt API keys before DB write.
  - Encryption key from server env (`APP_ENCRYPTION_KEY`).
- Runtime:
  - Use provider adapter interface:
    - `parse_expenses(text, context)`
    - `summarize_analysis(intent_result)`
  - Resolve active provider per household.

## 9) Async and Concurrency Requirements
- Use async FastAPI routes and async DB sessions.
- Use async HTTP clients for LLM APIs.
- Add request timeouts and retries (with backoff) for provider calls.
- Use idempotency key on confirm endpoint to prevent duplicate inserts.
- Add optimistic guards where needed for recurring job draft creation.
- Load test at least 25-50 concurrent requests locally.

## 10) API Plan (v1)

### Auth + Household
- `POST /auth/register` -> create user + household.
- `POST /auth/login` -> jwt tokens.
- `POST /auth/invite` -> generate/refresh invite code (admin only).
- `POST /auth/join` -> join household with invite code.

### Expenses
- `POST /expenses/log` -> input text, return parsed draft list.
- `POST /expenses/confirm` -> save edited draft(s), idempotent.
- `GET /expenses` -> list/filter/paginate (household-scoped).

### Dashboard + Analysis
- `GET /expenses/dashboard` -> totals, category split, user split.
- `POST /analysis/ask` -> intent classify + safe query templates + summary.

### Settings
- `GET /settings/llm` -> current provider/model status.
- `PUT /settings/llm` -> update provider/model/api key.
- `POST /settings/llm/test` -> verify credentials.

## 11) Safe Analytics Approach (Instead of Free SQL)
- Step 1: Classify question into known intents:
  - `total_by_period`
  - `category_spend_by_period`
  - `month_over_month_compare`
  - `top_expense_categories`
- Step 2: Parse entities (time range, category, user).
- Step 3: Execute parameterized SQL template per intent.
- Step 4: Generate concise natural-language answer.
- Result: safer, faster, predictable, and easier to test.

## 12) Local Run Plan (First Milestone, No Docker)

### Prerequisites
- Python 3.11+
- `uv` (Python package manager and virtual environment tool)
- Node.js 20+
- PostgreSQL 15+ running locally (or a remote dev Postgres URL)

### Local services
- `db`: PostgreSQL service
- `api`: FastAPI via `uvicorn`
- `web`: React dev server

### Local steps
1. Copy `.env.example` to `.env` (backend and frontend).
2. Initialize backend env and dependencies with `uv`:
   - `uv venv`
   - `uv sync`
3. Create local Postgres database and set `DATABASE_URL`.
4. Run DB migrations.
5. Start backend: `uv run uvicorn app.main:app --reload`.
6. Start frontend: `npm install` then `npm run dev`.
7. Seed demo household/users.
8. Execute integration tests and concurrency tests.

## 13) Online Deployment Plan (After Local Validation)

### Option A: Railway
- Deploy API and Web as separate services.
- Use managed Postgres.
- Add cron service for recurring drafts.
- Deploy using Dockerfiles or Nixpacks/buildpacks (either is fine).

### Option B: DigitalOcean
- App Platform for API/Web + managed Postgres.
- Worker or cron component for scheduled tasks.
- Deploy using Dockerfiles or native buildpack flow.

### Production minimum checklist
- HTTPS enabled.
- Secrets configured in platform env.
- DB backups enabled.
- Error monitoring (Sentry).
- Basic rate limiting on auth and analysis endpoints.

## 14) Execution Roadmap (2 Weeks)

### Week 1
1. Project setup, native local run setup with `uv`, env management, migrations.
2. Auth + household/invite flows.
3. Expense schema + CRUD + tenant guardrails.
4. LLM parser service + draft confirm flow.

### Week 2
1. Dashboard APIs + React screens.
2. Analytics intent engine + response summaries.
3. LLM settings UI/API + encrypted key handling.
4. Recurring expense scheduler + draft generation.
5. Test pass, bug fixes, local UAT with wife.

## 15) Test Plan
- Unit tests: parser validation, intent classification, tenant filters.
- Integration tests: auth, invite, confirm flow, dashboard metrics.
- Security tests: cross-tenant access attempts.
- Concurrency tests: simultaneous log/confirm requests.
- Failure tests: LLM timeout, invalid API key, provider downtime.

## 16) Risks and Mitigations
- Risk: LLM mis-parses amounts/categories.
  - Mitigation: mandatory confirm/edit step + strict schema validation.
- Risk: household data leak.
  - Mitigation: enforced tenant filter in repository layer + tests.
- Risk: provider latency/failures.
  - Mitigation: async timeout/retry and clear UI fallback messaging.

## 17) Definition of Done (MVP)
- End-to-end flow works locally for two users in one household.
- No tenant isolation test failures.
- Dashboard and analysis produce consistent numbers.
- LLM settings can switch provider/model and pass connectivity test.
- App is ready to deploy to Railway or DigitalOcean with documented steps.
