from __future__ import annotations

import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.services.analysis.prompts import (
    SPEND_ANALYSIS_AGENT_SYSTEM_PROMPT,
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
        validate_sql: Callable[[str], tuple[bool, str]],
        execute_sql: Callable[[str], Awaitable[tuple[Cols, Rows]]],
        default_answer: Callable[[str, Cols, Rows], str],
        model: str,
        api_key: str | None,
    ) -> None:
        self.provider_name = provider_name.lower().strip()
        self._validate_sql = validate_sql
        self._execute_sql = execute_sql
        self._default_answer = default_answer
        self.model = model
        self.api_key = api_key

    async def run(self, question: str, max_attempts: int = 3) -> SQLAgentResult:
        if self.provider_name not in {"cerebras", "groq"}:
            return SQLAgentResult(
                success=False,
                final_sql="",
                answer="Analytics SQL agent requires Groq or Cerebras provider.",
                attempts=[],
                columns=[],
                rows=[],
                tool_trace=["tool_select"],
                failure_reason="Provider is not supported for SQL agent.",
            )
        if not self.api_key:
            provider_label = self.provider_name.upper()
            return SQLAgentResult(
                success=False,
                final_sql="",
                answer=f"{provider_label} API key is missing for analytics SQL agent.",
                attempts=[],
                columns=[],
                rows=[],
                tool_trace=["tool_select"],
                failure_reason=f"Missing {provider_label} API key.",
            )
        return await self._run_langchain_tool_agent(question=question, max_attempts=max_attempts)

    async def _run_langchain_tool_agent(
        self,
        *,
        question: str,
        max_attempts: int,
    ) -> SQLAgentResult:
        try:
            from langchain.agents import create_agent
            from langchain.tools import tool
            from langchain_cerebras import ChatCerebras
            from langchain_groq import ChatGroq
        except Exception as exc:  # pragma: no cover - dependency runtime path
            raise RuntimeError(
                "LangChain SQL agent dependencies missing. Install langchain-cerebras and langchain-groq."
            ) from exc

        if self.provider_name == "cerebras":
            os.environ["CEREBRAS_API_KEY"] = str(self.api_key)
        if self.provider_name == "groq":
            os.environ["GROQ_API_KEY"] = str(self.api_key)

        attempts: list[SQLAgentAttempt] = []
        tool_trace: list[str] = ["tool_select"]
        final_sql = ""
        final_cols: Cols = []
        final_rows: Rows = []
        last_error: str | None = None

        status_map = {
            "approved": "confirmed",
            "confirm": "confirmed",
            "confirmed": "confirmed",
            "pending": "draft",
            "draft": "draft",
        }

        def _normalize_sql(query: str) -> str:
            normalized = query.strip().rstrip(";")

            def _rewrite_status(match) -> str:
                raw = str(match.group(1)).strip().lower()
                resolved = status_map.get(raw, raw)
                return f"LOWER(CAST(status AS TEXT)) = '{resolved}'"

            return re.sub(
                r"\bstatus\s*=\s*'([^']+)'",
                _rewrite_status,
                normalized,
                flags=re.IGNORECASE,
            )

        @tool("run_sql_query")
        async def run_sql_query(sql: str) -> list[dict[str, Any]]:
            """
            Execute SQL against household_expenses and return rows.
            """

            nonlocal final_sql, final_cols, final_rows, last_error

            attempt_number = len(attempts) + 1
            if attempt_number > max_attempts:
                raise ValueError(f"Exceeded max SQL attempts ({max_attempts}).")

            tool_trace.append("sql_generate")
            current_sql = _normalize_sql(sql)
            if not current_sql:
                last_error = "Agent produced empty SQL."
                attempts.append(
                    SQLAgentAttempt(
                        attempt_number=attempt_number,
                        generated_sql=current_sql,
                        llm_reason="agent_generated_sql",
                        validation_ok=False,
                        validation_reason=last_error,
                        execution_ok=False,
                        db_error=last_error,
                    )
                )
                raise ValueError(last_error)

            tool_trace.append("sql_validate")
            validation_ok, validation_reason = self._validate_sql(current_sql)
            if not validation_ok:
                last_error = validation_reason or "SQL validation failed."
                attempts.append(
                    SQLAgentAttempt(
                        attempt_number=attempt_number,
                        generated_sql=current_sql,
                        llm_reason="agent_generated_sql",
                        validation_ok=False,
                        validation_reason=validation_reason,
                        execution_ok=False,
                        db_error=last_error,
                    )
                )
                raise ValueError(last_error)

            tool_trace.append("sql_execute")
            try:
                cols, rows = await self._execute_sql(current_sql)
            except Exception as exc:  # pragma: no cover - backend/runtime dependent
                last_error = str(exc)
                attempts.append(
                    SQLAgentAttempt(
                        attempt_number=attempt_number,
                        generated_sql=current_sql,
                        llm_reason="agent_generated_sql",
                        validation_ok=True,
                        validation_reason=None,
                        execution_ok=False,
                        db_error=last_error,
                    )
                )
                raise ValueError(last_error)

            final_sql = current_sql
            final_cols = cols
            final_rows = rows
            attempts.append(
                SQLAgentAttempt(
                    attempt_number=attempt_number,
                    generated_sql=current_sql,
                    llm_reason="agent_generated_sql",
                    validation_ok=True,
                    validation_reason=None,
                    execution_ok=True,
                    db_error=None,
                )
            )
            return [dict(zip(cols, row, strict=False)) for row in rows]

        if self.provider_name == "groq":
            llm = ChatGroq(
                model=self.model,
                api_key=self.api_key,
                temperature=0,
            )
        else:
            llm = ChatCerebras(
                model=self.model,
                api_key=self.api_key,
                temperature=0,
            )
        agent = create_agent(
            model=llm,
            tools=[run_sql_query],
            system_prompt=SPEND_ANALYSIS_AGENT_SYSTEM_PROMPT,
        )

        try:
            response = await agent.ainvoke(
                {"messages": [{"role": "user", "content": question}]}
            )
        except Exception as exc:  # pragma: no cover - backend/runtime dependent
            failure_reason = str(exc)
            return SQLAgentResult(
                success=False,
                final_sql=attempts[-1].generated_sql if attempts else "",
                answer=f"SQL execution failed after {len(attempts)} attempt(s): {failure_reason}",
                attempts=attempts,
                columns=[],
                rows=[],
                tool_trace=tool_trace,
                failure_reason=failure_reason,
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
