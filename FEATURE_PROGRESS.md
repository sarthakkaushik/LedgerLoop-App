# Expense Tracker Build Progress

Last updated: 2026-02-07

## Current Sprint
- Completed: Feature 1 - Auth + Household foundation.
- Completed: Feature 2 - Expense Draft Parsing (LLM adapter + draft API).
- Completed: Feature 6 (MVP slice) - LLM runtime configuration via server env.
- Completed: Feature 8 (Foundation) - Frontend app with auth, chat log, and household UI.
- Completed: Feature 3 - Expense Confirm/Edit and Save.
- Completed: Feature 4 - Dashboard APIs + dashboard UI tab.
- Completed: Feature 5 - Analytics Chat (Intent-Based + tool routing + UI tab).
- Completed: Feature 5.1 - Hybrid Analytics (fixed intents + agent fallback + route trace).
- Completed: Feature 5.2 - Schema-aware SQL agent (generate, validate, execute, summarize).
- Completed: Feature 8.1 - Household collaboration UI + expense ledger by member.
- Completed: Feature 8.2 - Admin member deletion + category dropdown fallback in draft confirm.
- Next up: Feature 7 - Recurring Expense Draft Job.

## Feature Checklist
- [x] Feature 1: Auth + Household
  - [x] Backend scaffold with `uv` package management
  - [x] Async FastAPI app setup
  - [x] User + Household models
  - [x] JWT auth utilities
  - [x] Register/Login/Invite/Join/Me APIs
  - [x] Initial integration test file
  - [x] Local test execution and verification (`uv run pytest -q` passed)
- [x] Feature 2: Expense Draft Parsing (LLM)
  - [x] `POST /expenses/log` endpoint with auth guard
  - [x] LLM provider adapter interface
  - [x] Mock provider for local/offline parsing
  - [x] Draft response schema + clarification flow
  - [x] Tests passing (`uv run pytest -q`)
- [x] Feature 3: Expense Confirm/Edit and Save
- [x] Feature 4: Dashboard APIs
- [x] Feature 5: Analytics (Intent-Based)
- [x] Feature 6: LLM Runtime Config
  - [x] `GET /settings/llm`
  - [x] `PUT /settings/llm` (env-managed mode returns 409)
  - [x] `POST /settings/llm/test`
  - [x] Runtime parser provider selection uses backend `.env` values directly
- [ ] Feature 7: Recurring Expense Draft Job
- [x] Feature 8: Frontend Integration
  - [x] React frontend scaffold (Vite)
  - [x] Auth screens (register/login)
  - [x] Join household flow (invite code based)
  - [x] Expense chat parsing screen (now chat-aware)
  - [x] LLM settings removed from UI (server env-managed config)
  - [x] Confirm flow screen (edit + save drafts)
  - [x] Dashboard screen
  - [x] Household tab (members, invite code, who-logged-what ledger)
  - [x] Admin can remove member access (soft deactivate; ledger history preserved)
  - [x] Category dropdown in confirm flow with `Others` fallback option
- [ ] Feature 9: Local UAT + Hardening

## Next Steps
1. Start Feature 7 recurring expense draft scheduler job with idempotent monthly generation.
2. Add recurring template management in frontend.
3. Run local UAT scripts and production hardening checklist, including two-user household testing.
