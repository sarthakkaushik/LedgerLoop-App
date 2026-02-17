from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.services.analysis.prompts import (
    HARDCODED_SQL_AGENT_SYSTEM_PROMPT,
    SQL_FIXER_SYSTEM_PROMPT,
    build_sql_fixer_user_prompt,
)

CellValue = str | float | int
Rows = list[list[CellValue]]
Cols = list[str]


@dataclass(slots=True)
class SQLAgentAttempt:
    attempt_number: int
    generated_sql: str
    llm_reason: str | None
    validation_ok: bool
    validation_reason: str | None
    execution_ok: bool
    db_error: str | None


@dataclass(slots=True)
class SQLAgentResult:
    success: bool
    final_sql: str
    answer: str
    attempts: list[SQLAgentAttempt]
    columns: Cols
    rows: Rows
    tool_trace: list[str]
    failure_reason: str | None = None


class SQLAgentRunner:
    def __init__(
        self,
        *,
        provider_name: str,
        llm_json: Callable[[str, str], Awaitable[dict | None]],
        validate_sql: Callable[[str], tuple[bool, str]],
        execute_sql: Callable[[str], Awaitable[tuple[Cols, Rows]]],
        default_answer: Callable[[str, Cols, Rows], str],
        model: str,
        api_key: str | None,
    ) -> None:
        self.provider_name = provider_name.lower().strip()
        self._llm_json = llm_json
        self._validate_sql = validate_sql
        self._execute_sql = execute_sql
        self._default_answer = default_answer
        self.model = model
        self.api_key = api_key

    async def run(self, question: str, max_attempts: int = 3) -> SQLAgentResult:
        if self.provider_name != "cerebras":
            return SQLAgentResult(
                success=False,
                final_sql="",
                answer="Analytics SQL agent requires Cerebras provider.",
                attempts=[],
                columns=[],
                rows=[],
                tool_trace=["tool_select"],
                failure_reason="Provider is not cerebras.",
            )
        if not self.api_key:
            return SQLAgentResult(
                success=False,
                final_sql="",
                answer="Cerebras API key is missing for analytics SQL agent.",
                attempts=[],
                columns=[],
                rows=[],
                tool_trace=["tool_select"],
                failure_reason="Missing CEREBRAS API key.",
            )
        return await self._run_langchain_cerebras(question=question, max_attempts=max_attempts)

    async def _run_langchain_cerebras(
        self,
        *,
        question: str,
        max_attempts: int,
    ) -> SQLAgentResult:
        try:
            from langchain.agents import create_agent
            from langchain.tools import tool
            from langchain_cerebras import ChatCerebras
        except Exception as exc:  # pragma: no cover - dependency runtime path
            raise RuntimeError(
                "LangChain Cerebras dependencies missing. Install langchain-cerebras."
            ) from exc

        os.environ["CEREBRAS_API_KEY"] = str(self.api_key)

        attempts: list[SQLAgentAttempt] = []
        tool_trace: list[str] = ["tool_select"]
        final_sql = ""
        final_cols: Cols = []
        final_rows: Rows = []
        last_error: str | None = None

        async def _repair_sql(failed_sql: str, db_error: str) -> tuple[str | None, str | None]:
            payload = await self._llm_json(
                SQL_FIXER_SYSTEM_PROMPT,
                build_sql_fixer_user_prompt(
                    question=question,
                    failed_sql=failed_sql,
                    db_error=db_error,
                ),
            )
            fixed_sql = str((payload or {}).get("sql", "")).strip() or None
            reason = str((payload or {}).get("reason", "")).strip() or None
            return fixed_sql, reason

        @tool("run_sql_query")
        async def run_sql_query(sql: str) -> dict[str, Any]:
            """
            Execute SQL against household_expenses and return rows.
            """

            nonlocal final_sql, final_cols, final_rows, last_error

            tool_trace.append("sql_generate")
            current_sql = sql.strip()
            if not current_sql:
                return {"ok": False, "error": "Agent produced empty SQL."}

            next_reason = "agent_generated_sql"
            for attempt_number in range(1, max_attempts + 1):
                tool_trace.append("sql_validate")
                validation_ok, validation_reason = self._validate_sql(current_sql)
                execution_ok = False
                db_error: str | None = None
                cols: Cols = []
                rows: Rows = []

                if validation_ok:
                    tool_trace.append("sql_execute")
                    try:
                        cols, rows = await self._execute_sql(current_sql)
                        execution_ok = True
                        final_sql = current_sql
                        final_cols = cols
                        final_rows = rows
                    except Exception as exc:  # pragma: no cover - backend/runtime dependent
                        db_error = str(exc)
                        last_error = db_error
                else:
                    db_error = validation_reason
                    last_error = validation_reason

                attempts.append(
                    SQLAgentAttempt(
                        attempt_number=attempt_number,
                        generated_sql=current_sql,
                        llm_reason=next_reason,
                        validation_ok=validation_ok,
                        validation_reason=validation_reason if not validation_ok else None,
                        execution_ok=execution_ok,
                        db_error=db_error if not execution_ok else None,
                    )
                )

                if execution_ok:
                    return {
                        "ok": True,
                        "sql": current_sql,
                        "columns": cols,
                        "rows": rows,
                    }
                if attempt_number >= max_attempts:
                    break

                tool_trace.append(f"sql_fix_{attempt_number + 1}")
                fixed_sql, fix_reason = await _repair_sql(
                    failed_sql=current_sql,
                    db_error=last_error or "unknown execution error",
                )
                if not fixed_sql:
                    break
                current_sql = fixed_sql
                next_reason = fix_reason or "sql_fix_retry"

            return {
                "ok": False,
                "sql": current_sql,
                "error": last_error or "SQL execution failed.",
            }

        llm = ChatCerebras(
            model=self.model,
            api_key=self.api_key,
            temperature=0,
        )
        agent = create_agent(
            model=llm,
            tools=[run_sql_query],
            system_prompt=HARDCODED_SQL_AGENT_SYSTEM_PROMPT,
        )

        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}
        )

        answer = _extract_langchain_agent_answer(response).strip()
        success = any(attempt.execution_ok for attempt in attempts)
        if success:
            if not answer:
                answer = self._default_answer(question, final_cols, final_rows)
            return SQLAgentResult(
                success=True,
                final_sql=final_sql,
                answer=answer,
                attempts=attempts,
                columns=final_cols,
                rows=final_rows,
                tool_trace=tool_trace,
            )

        failure_reason = last_error or (attempts[-1].db_error if attempts else None) or "SQL execution failed."
        if not answer:
            answer = f"SQL execution failed after {len(attempts)} attempt(s): {failure_reason}"
        return SQLAgentResult(
            success=False,
            final_sql=attempts[-1].generated_sql if attempts else "",
            answer=answer,
            attempts=attempts,
            columns=[],
            rows=[],
            tool_trace=tool_trace,
            failure_reason=failure_reason,
        )


def _extract_langchain_agent_answer(response: object) -> str:
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            return _message_content_to_text(messages[-1])
        output = response.get("output")
        if output is not None:
            return str(output).strip()
    return _message_content_to_text(response)


def _message_content_to_text(message: object) -> str:
    if message is None:
        return ""
    content: object = None
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                maybe_text = item.get("text") or item.get("content")
                if isinstance(maybe_text, str):
                    parts.append(maybe_text)
        return "\n".join(part.strip() for part in parts if part).strip()
    if content is not None:
        return str(content).strip()
    return str(message).strip() if isinstance(message, str) else ""


def extract_json_payload(raw: str) -> dict | None:
    text_value = raw.strip()
    if not (text_value.startswith("{") and text_value.endswith("}")):
        start_idx = text_value.find("{")
        end_idx = text_value.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text_value = text_value[start_idx : end_idx + 1]
    try:
        parsed = json.loads(text_value)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None
