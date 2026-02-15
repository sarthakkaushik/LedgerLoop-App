from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.schemas.analysis import AnalysisAskRequest, AnalysisAskResponse
from app.services.analysis.logging_service import (
    add_attempt_log,
    create_query_log,
    finalize_query_log,
)
from app.services.analysis.sql_agent import (
    SQLAgentResult,
    SQLAgentRunner,
    extract_json_payload,
)
from app.services.analysis.sql_validation import validate_safe_sql
from app.services.llm.settings_service import LLMRuntimeConfig, get_env_runtime_config

router = APIRouter(prefix="/analysis", tags=["analysis"])

HOUSEHOLD_CTE = """
WITH household_expenses AS (
  SELECT
    CAST(e.id AS TEXT) AS expense_id,
    CAST(e.household_id AS TEXT) AS household_id,
    CAST(e.logged_by_user_id AS TEXT) AS logged_by_user_id,
    COALESCE(u.full_name,'Unknown') AS logged_by,
    CAST(e.status AS TEXT) AS status,
    COALESCE(e.category,'Other') AS category,
    e.description AS description,
    e.merchant_or_item AS merchant_or_item,
    e.amount AS amount,
    e.currency AS currency,
    CAST(e.date_incurred AS TEXT) AS date_incurred,
    e.is_recurring AS is_recurring,
    e.confidence AS confidence,
    CAST(e.created_at AS TEXT) AS created_at,
    CAST(e.updated_at AS TEXT) AS updated_at
  FROM expenses e
  LEFT JOIN users u ON u.id = e.logged_by_user_id
  WHERE CAST(e.household_id AS TEXT)=:household_id
)
"""


def _today_for_timezone(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception:
        return date.today()


def _safe_sql(query: str) -> tuple[bool, str]:
    return validate_safe_sql(query, allowed_tables={"household_expenses"})


async def _llm_json(
    runtime: LLMRuntimeConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict | None:
    if runtime.provider.value != "cerebras" or not runtime.api_key:
        return None
    payload = {
        "model": runtime.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {runtime.api_key}"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            raw_content = response.json()["choices"][0]["message"]["content"]
            if isinstance(raw_content, str):
                return extract_json_payload(raw_content)
            return extract_json_payload(str(raw_content))
    except Exception:
        return None


def _cell(value: Any) -> str | float | int:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    return str(value)


async def _run_sql(
    session: AsyncSession,
    household_id: UUID,
    sql_query: str,
) -> tuple[list[str], list[list[str | float | int]]]:
    wrapped = f"{HOUSEHOLD_CTE}\nSELECT * FROM (\n{sql_query}\n) AS agent_result\nLIMIT :result_limit"
    try:
        result = await session.execute(
            text(wrapped),
            {"household_id": str(household_id), "result_limit": 200},
        )
    except Exception:
        await session.rollback()
        raise
    rows = result.mappings().all()
    if not rows:
        return list(result.keys()), []
    columns = list(rows[0].keys())
    return columns, [[_cell(row.get(column)) for column in columns] for row in rows]


def _default_answer(
    question: str,
    cols: list[str],
    rows: list[list[str | float | int]],
) -> str:
    if not rows:
        return "No matching expenses were found."
    if len(rows) == 1:
        summary = ", ".join(f"{cols[i]}={rows[0][i]}" for i in range(min(4, len(cols))))
        return f"Result for '{question}': {summary}."
    return f"I found {len(rows)} row(s) for '{question}'."


async def _run_sql_agent(
    *,
    runtime: LLMRuntimeConfig,
    session: AsyncSession,
    household_id: UUID,
    question: str,
) -> SQLAgentResult:
    async def llm_callback(system_prompt: str, user_prompt: str) -> dict | None:
        return await _llm_json(runtime, system_prompt, user_prompt)

    async def execute_sql(sql_query: str) -> tuple[list[str], list[list[str | float | int]]]:
        return await _run_sql(session, household_id, sql_query)

    runner = SQLAgentRunner(
        provider_name=runtime.provider.value,
        llm_json=llm_callback,
        validate_sql=_safe_sql,
        execute_sql=execute_sql,
        default_answer=_default_answer,
        model=runtime.model,
        api_key=runtime.api_key,
    )
    return await runner.run(question, max_attempts=3)


@router.post("/ask", response_model=AnalysisAskResponse)
async def ask_analysis(
    payload: AnalysisAskRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalysisAskResponse:
    runtime = get_env_runtime_config()
    _today_for_timezone(runtime.timezone)  # timezone evaluation retained for consistent runtime behavior
    question = payload.text.strip()

    query_log = None
    try:
        query_log = await create_query_log(
            session,
            household_id=user.household_id,
            user_id=user.id,
            provider=runtime.provider.value,
            model=runtime.model,
            question=question,
            mode="analytics",
            route="agent",
            tool="sql_chat_agent",
        )
    except Exception:
        await session.rollback()
        query_log = None

    async def _finish(
        response: AnalysisAskResponse,
        *,
        status: str = "success",
        failure_reason: str | None = None,
        attempt_count: int = 0,
        final_sql: str | None = None,
    ) -> AnalysisAskResponse:
        if query_log is not None:
            try:
                await finalize_query_log(
                    session,
                    query_log=query_log,
                    status=status,
                    final_answer=response.answer,
                    attempt_count=attempt_count,
                    final_sql=final_sql,
                    failure_reason=failure_reason,
                    mode=response.mode,
                    route=response.route,
                    tool=response.tool,
                )
            except Exception:
                await session.rollback()
        return response

    try:
        agent_result = await _run_sql_agent(
            runtime=runtime,
            session=session,
            household_id=user.household_id,
            question=question,
        )
    except Exception as exc:
        failure_text = f"SQL agent failed to run: {exc}"
        response = AnalysisAskResponse(
            mode="analytics",
            route="agent",
            confidence=0.2,
            tool="sql_chat_agent",
            tool_trace=["tool_select"],
            sql=None,
            answer=failure_text,
            chart=None,
            table=None,
        )
        return await _finish(
            response,
            status="failed",
            failure_reason=str(exc),
            attempt_count=0,
            final_sql=None,
        )

    if query_log is not None:
        for attempt in agent_result.attempts:
            try:
                await add_attempt_log(
                    session,
                    query_log=query_log,
                    attempt_number=attempt.attempt_number,
                    generated_sql=attempt.generated_sql,
                    llm_reason=attempt.llm_reason,
                    validation_ok=attempt.validation_ok,
                    validation_reason=attempt.validation_reason,
                    execution_ok=attempt.execution_ok,
                    db_error=attempt.db_error,
                )
            except Exception:
                await session.rollback()

    response = AnalysisAskResponse(
        mode="analytics",
        route="agent",
        confidence=0.85 if agent_result.success else 0.35,
        tool="sql_chat_agent",
        tool_trace=agent_result.tool_trace,
        sql=None,
        answer=agent_result.answer,
        chart=None,
        table=None,
    )
    return await _finish(
        response,
        status="success" if agent_result.success else "failed",
        failure_reason=agent_result.failure_reason,
        attempt_count=len(agent_result.attempts),
        final_sql=agent_result.final_sql or None,
    )
