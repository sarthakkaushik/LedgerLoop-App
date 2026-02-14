# Talk-to-Data (Postgres SQL Agent) Implementation Plan

## Goal
Build a reliable analytics agent that answers user expense questions using PostgreSQL SQL generated from LLM prompts, with:

- Schema-grounded SQL generation
- Execution + error capture
- Automatic SQL repair (up to 3 attempts)
- Full attempt logging in database
- Cerebras API (`gpt-oss-120b`) as the only LLM runtime
- LangChain + LangGraph orchestration for the SQL agent workflow

This plan is intentionally implementation-focused so work can be tracked and reviewed during execution.

---

## 1) Product Behavior (Target)

Given a user question in `POST /analysis/ask`:

1. Generate SQL from schema + few-shot prompt.
2. Validate SQL safety and scope.
3. Execute against Postgres.
4. If execution fails, capture DB error and call SQL-fixer LLM.
5. Retry up to 3 total attempts.
6. Return final answer/table/chart when successful.
7. Persist full trace in DB for observability and offline quality review.

Failure behavior:

- If all attempts fail, respond gracefully with last error summary.
- Do not execute unsafe SQL even if LLM outputs it.

---

## 2) Current Code Areas Affected

Primary existing path:

- `backend/app/api/analysis.py`

Related runtime/provider configuration:

- `backend/app/core/config.py`
- `backend/app/models/llm_setting.py`
- `backend/app/services/llm/settings_service.py`
- `backend/app/services/llm/provider_factory.py` (only if shared abstractions are reused)

Models init:

- `backend/app/models/__init__.py`

Testing:

- `backend/tests/test_analysis_api.py`
- Add focused tests for SQL retry + repair + logging.

---

## 3) New Components to Add

### 3.1 SQL Agent Service Layer

Create new module:

- `backend/app/services/analysis/sql_agent.py`

Responsibilities:

- Build SQL generation prompt (schema + few-shot + constraints)
- Build SQL repair prompt (failed SQL + DB error + constraints)
- Run LangGraph state flow:
  - `generate_sql` -> `validate_sql` -> `execute_sql`
  - on execution/validation error -> `fix_sql`
  - loop up to 3 attempts -> `summarize`
- Return structured result:
  - `final_sql`
  - `columns`, `rows`
  - `attempt_count`
  - `attempt_trace`
  - `failure_reason` (if any)

### 3.2 Prompt Templates

Create module:

- `backend/app/services/analysis/prompts.py`

Include:

- SQL generator system prompt
- SQL fixer system prompt
- Few-shot examples mapped to real expense questions

### 3.3 Query/Audit Logging Models

Create models:

- `backend/app/models/analysis_query.py`
- `backend/app/models/analysis_query_attempt.py`

Tables:

- `analysis_queries` (one row per user question)
- `analysis_query_attempts` (one row per attempt)

Fields (minimum):

- Query table:
  - `id`, `household_id`, `user_id`, `question`
  - `status` (`success` / `failed`)
  - `final_sql`, `final_answer`
  - `attempt_count`
  - `created_at`, `updated_at`

- Attempt table:
  - `id`, `analysis_query_id`, `attempt_number`
  - `generated_sql`
  - `validation_ok`, `validation_reason`
  - `execution_ok`, `db_error`
  - `llm_reason`
  - `created_at`

### 3.4 Logging Service

Create:

- `backend/app/services/analysis/logging_service.py`

Responsibilities:

- Start query log row
- Append attempt rows
- Mark final success/failure

---

## 4) Provider Integration (Cerebras + gpt-oss-120b)

### 4.1 Configuration updates

Update:

- `backend/app/core/config.py`

Add:

- `cerebras_api_key`
- `cerebras_model` (default `gpt-oss-120b`)

### 4.2 LLM provider enum/runtime

Update:

- `backend/app/models/llm_setting.py`
- `backend/app/services/llm/settings_service.py`

Add provider:

- `cerebras`

Runtime resolution:

- If `LLM_PROVIDER=cerebras`, use Cerebras key + model.

### 4.3 Orchestration (Mandatory)

Implementation must use:

- `langchain` for prompt/model invocation abstraction
- `langgraph` for the retry state machine and node transitions

Design constraints:

- Keep orchestration in service layer (`app/services/analysis`) and keep route layer thin.
- Graph state must carry: question, attempt_number, sql, validation_reason, db_error, rows, columns, final_answer.
- Retry edges must stop at max 3 attempts.

---

## 5) API Route Changes (`/analysis/ask`)

Update flow inside:

- `backend/app/api/analysis.py`

Changes:

1. Keep fixed deterministic tools for high-confidence intents if needed.
2. For agent route:
   - Call SQL agent service (new module).
   - Use 3-attempt loop outcome.
   - Use existing answer/chart rendering path (or thinly refactor it into helper).
3. Store query + attempt logs through logging service.
4. Return tool trace that reflects real steps (`generate`, `validate`, `execute`, `fix_n`).

---

## 6) SQL Safety Rules (Non-Negotiable)

Enforced before execution:

- Single `SELECT` only (or `WITH ... SELECT`)
- No semicolon
- Block DDL/DML keywords
- Block system schema/table access
- Restrict to allowed table set (currently `expenses`)
- Require household scoping behavior in execution wrapper

AST validation (mandatory):

- Parse SQL with `sqlglot` using PostgreSQL dialect.
- Reject query if parsing fails.
- Reject any statement that is not `SELECT`/`WITH ... SELECT`.
- Extract table references from AST and allow only approved tables.
- Reject blacklisted functions/tokens even if obfuscated in raw string.
- Run existing string-level checks as defense-in-depth after AST checks.

Execution wrapper:

- Continue wrapping with secure household filter context so cross-household leaks cannot happen from prompt mistakes.

---

## 7) Retry and Repair Logic

`max_attempts = 3`

Attempt 1:

- SQL generator prompt

Attempt 2-3:

- SQL fixer prompt with:
  - original user question
  - failed SQL
  - concrete DB error message
  - schema + constraints

Stop conditions:

- Success on execute
- Unsafe SQL after validation (can still try repair until attempts exhausted)
- Max attempts reached

---

## 8) Test Plan

Add/extend tests in backend:

1. Generates safe SQL and executes successfully.
2. First SQL fails, second SQL fixed and succeeds.
3. All 3 attempts fail -> graceful error response.
4. Unsafe SQL never executes.
5. Query logs persist for success path.
6. Attempt logs persist for each retry.
7. Household-scoping isolation still holds.

Also run:

- Existing analysis tests to catch regressions.

---

## 9) Execution Checklist (Tracking)

### Phase A - Foundation

- [ ] Add `cerebras` provider config and runtime wiring
- [ ] Add `langchain` + `langgraph` dependencies in `backend/pyproject.toml`
- [ ] Add `sqlglot` dependency for AST SQL validation
- [ ] Add new analysis log models
- [ ] Ensure models imported for table creation

### Phase B - Agent Core

- [ ] Add prompt templates (generator + fixer + few-shot)
- [ ] Implement SQL agent service (generate/validate/execute/repair loop)
- [ ] Implement logging service

### Phase C - API Integration

- [ ] Integrate agent service into `/analysis/ask`
- [ ] Preserve/adjust response shape for frontend compatibility

### Phase D - Quality

- [ ] Add retry+logging test coverage
- [ ] Add tests for AST validator (`SELECT` allowed, non-`SELECT` blocked, table whitelist enforced)
- [ ] Run backend test suite
- [ ] Verify no regressions in fixed analytics tools

### Phase E - Delivery

- [ ] Update docs (`backend/README.md`) with provider/env usage
- [ ] Commit with clear message
- [ ] Push branch

---

## 10) Open Inputs Needed Before Final Wiring

1. Confirm final deployment model string stays `gpt-oss-120b` across environments.
2. Final canonical table name in production (`expenses` vs transformed CTE alias usage).
3. Whether to fully replace current ad-hoc SQL branch or keep deterministic fixed tools before agent fallback.
4. Any additional table(s) that should be queryable in v1.

---

## 11) Notes

- The provided sample schema/data is sufficient for v1 prompts.
- Logging every attempt enables prompt tuning using real failure cases.
- LangGraph orchestration is required for transparent retry control and future extensibility.
