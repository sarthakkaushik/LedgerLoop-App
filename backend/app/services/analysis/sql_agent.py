from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypedDict

from app.services.analysis.prompts import (
    SQL_SUMMARY_SYSTEM_PROMPT,
    build_sql_fixer_system_prompt,
    build_sql_fixer_user_prompt,
    build_sql_generator_system_prompt,
    build_sql_generator_user_prompt,
    build_sql_summary_user_prompt,
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


class _AgentState(TypedDict, total=False):
    question: str
    mode: str
    attempt: int
    max_attempts: int
    current_sql: str
    llm_reason: str | None
    validation_ok: bool
    validation_reason: str | None
    execution_ok: bool
    db_error: str | None
    columns: Cols
    rows: Rows
    attempts: list[dict]
    tool_trace: list[str]
    fix_from_sql: str
    fix_from_error: str
    final_sql: str
    answer: str
    success: bool
    failure_reason: str | None


class SQLAgentRunner:
    def __init__(
        self,
        *,
        provider_name: str,
        llm_json: Callable[[str, str], Awaitable[dict | None]],
        validate_sql: Callable[[str], tuple[bool, str]],
        execute_sql: Callable[[str], Awaitable[tuple[Cols, Rows]]],
        fallback_sql: Callable[[str], str],
        default_answer: Callable[[str, Cols, Rows], str],
        model: str,
        api_key: str | None,
        live_schema_text: str,
    ):
        self.provider_name = provider_name.lower().strip()
        self._llm_json = llm_json
        self._validate_sql = validate_sql
        self._execute_sql = execute_sql
        self._fallback_sql = fallback_sql
        self._default_answer = default_answer
        self.model = model
        self.api_key = api_key
        self.live_schema_text = live_schema_text

    async def run(self, question: str, max_attempts: int = 3) -> SQLAgentResult:
        if self.provider_name == "openai":
            try:
                return await self._run_openai_agents_sdk(
                    question=question,
                    max_attempts=max_attempts,
                )
            except RuntimeError:
                # Keep service usable when SDK dependency is missing in local/dev.
                return await self._run_sequential(
                    question=question,
                    max_attempts=max_attempts,
                )
        if self.provider_name == "cerebras":
            return await self._run_langgraph(question=question, max_attempts=max_attempts)
        return await self._run_sequential(question=question, max_attempts=max_attempts)

    async def _run_sequential(self, *, question: str, max_attempts: int) -> SQLAgentResult:
        attempts: list[SQLAgentAttempt] = []
        tool_trace: list[str] = []
        sql_query = ""
        last_error: str | None = None
        rows: Rows = []
        cols: Cols = []
        for idx in range(1, max_attempts + 1):
            if idx == 1:
                tool_trace.append("sql_generate")
                sql_payload = await self._call_llm_json(
                    build_sql_generator_system_prompt(self.live_schema_text),
                    build_sql_generator_user_prompt(question),
                )
            else:
                tool_trace.append(f"sql_fix_{idx}")
                sql_payload = await self._call_llm_json(
                    build_sql_fixer_system_prompt(self.live_schema_text),
                    build_sql_fixer_user_prompt(
                        question=question,
                        failed_sql=sql_query,
                        db_error=last_error or "unknown execution error",
                    ),
                )

            sql_query = str((sql_payload or {}).get("sql", "")).strip()
            llm_reason = str((sql_payload or {}).get("reason", "")).strip() or None
            if not sql_query:
                sql_query = self._fallback_sql(question)

            tool_trace.append("sql_validate")
            validation_ok, validation_reason = self._validate_sql(sql_query)

            execution_ok = False
            db_error: str | None = None
            if validation_ok:
                tool_trace.append("sql_execute")
                try:
                    cols, rows = await self._execute_sql(sql_query)
                    execution_ok = True
                except Exception as exc:  # pragma: no cover - backend/runtime dependent
                    db_error = str(exc)
                    last_error = db_error
            else:
                db_error = validation_reason
                last_error = validation_reason

            attempts.append(
                SQLAgentAttempt(
                    attempt_number=idx,
                    generated_sql=sql_query,
                    llm_reason=llm_reason,
                    validation_ok=validation_ok,
                    validation_reason=validation_reason if not validation_ok else None,
                    execution_ok=execution_ok,
                    db_error=db_error if not execution_ok else None,
                )
            )
            if execution_ok:
                tool_trace.append("answer_summarize")
                answer = await self._build_answer(question, sql_query, cols, rows)
                return SQLAgentResult(
                    success=True,
                    final_sql=sql_query,
                    answer=answer,
                    attempts=attempts,
                    columns=cols,
                    rows=rows,
                    tool_trace=tool_trace,
                )

        failure_reason = attempts[-1].db_error if attempts else "No SQL attempt executed."
        answer = f"SQL execution failed after {max_attempts} attempt(s): {failure_reason}"
        return SQLAgentResult(
            success=False,
            final_sql=sql_query,
            answer=answer,
            attempts=attempts,
            columns=[],
            rows=[],
            tool_trace=tool_trace,
            failure_reason=failure_reason,
        )

    async def _run_langgraph(self, *, question: str, max_attempts: int) -> SQLAgentResult:
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception as exc:  # pragma: no cover - dependency runtime path
            raise RuntimeError(
                "langgraph is required for cerebras SQL orchestration. Install langgraph."
            ) from exc

        graph = StateGraph(_AgentState)
        graph.add_node("propose_sql", self._node_propose_sql)
        graph.add_node("validate_sql", self._node_validate_sql)
        graph.add_node("execute_sql", self._node_execute_sql)
        graph.add_node("record_attempt", self._node_record_attempt)
        graph.add_node("prepare_fix", self._node_prepare_fix)
        graph.add_node("summarize_success", self._node_summarize_success)
        graph.add_node("summarize_failure", self._node_summarize_failure)

        graph.add_edge(START, "propose_sql")
        graph.add_edge("propose_sql", "validate_sql")
        graph.add_edge("validate_sql", "execute_sql")
        graph.add_edge("execute_sql", "record_attempt")

        graph.add_conditional_edges(
            "record_attempt",
            self._route_after_attempt,
            {
                "prepare_fix": "prepare_fix",
                "summarize_success": "summarize_success",
                "summarize_failure": "summarize_failure",
            },
        )
        graph.add_edge("prepare_fix", "propose_sql")
        graph.add_edge("summarize_success", END)
        graph.add_edge("summarize_failure", END)

        compiled = graph.compile()
        final_state = await compiled.ainvoke(
            {
                "question": question,
                "attempt": 0,
                "max_attempts": max_attempts,
                "mode": "generate",
                "attempts": [],
                "tool_trace": [],
            }
        )

        attempts = [
            SQLAgentAttempt(
                attempt_number=int(raw.get("attempt_number", 0)),
                generated_sql=str(raw.get("generated_sql", "")),
                llm_reason=raw.get("llm_reason"),
                validation_ok=bool(raw.get("validation_ok", False)),
                validation_reason=raw.get("validation_reason"),
                execution_ok=bool(raw.get("execution_ok", False)),
                db_error=raw.get("db_error"),
            )
            for raw in final_state.get("attempts", [])
        ]
        return SQLAgentResult(
            success=bool(final_state.get("success", False)),
            final_sql=str(final_state.get("final_sql", "")),
            answer=str(final_state.get("answer", "")).strip() or "No response generated.",
            attempts=attempts,
            columns=final_state.get("columns", []),
            rows=final_state.get("rows", []),
            tool_trace=final_state.get("tool_trace", []),
            failure_reason=final_state.get("failure_reason"),
        )

    async def _node_propose_sql(self, state: _AgentState) -> _AgentState:
        attempt = int(state.get("attempt", 0)) + 1
        mode = str(state.get("mode", "generate"))
        question = str(state.get("question", ""))
        trace = list(state.get("tool_trace", []))

        if mode == "fix":
            trace.append(f"sql_fix_{attempt}")
            payload = await self._call_llm_json(
                build_sql_fixer_system_prompt(self.live_schema_text),
                build_sql_fixer_user_prompt(
                    question=question,
                    failed_sql=str(state.get("fix_from_sql", "")),
                    db_error=str(state.get("fix_from_error", "unknown execution error")),
                ),
            )
        else:
            trace.append("sql_generate")
            payload = await self._call_llm_json(
                build_sql_generator_system_prompt(self.live_schema_text),
                build_sql_generator_user_prompt(question),
            )

        sql_query = str((payload or {}).get("sql", "")).strip()
        if not sql_query:
            sql_query = self._fallback_sql(question)
        llm_reason = str((payload or {}).get("reason", "")).strip() or None
        return {
            "attempt": attempt,
            "current_sql": sql_query,
            "llm_reason": llm_reason,
            "tool_trace": trace,
        }

    async def _node_validate_sql(self, state: _AgentState) -> _AgentState:
        trace = list(state.get("tool_trace", []))
        trace.append("sql_validate")
        ok, reason = self._validate_sql(str(state.get("current_sql", "")))
        return {
            "validation_ok": ok,
            "validation_reason": reason if not ok else None,
            "tool_trace": trace,
        }

    async def _node_execute_sql(self, state: _AgentState) -> _AgentState:
        if not bool(state.get("validation_ok", False)):
            return {
                "execution_ok": False,
                "db_error": str(state.get("validation_reason", "SQL validation failed.")),
                "columns": [],
                "rows": [],
            }
        trace = list(state.get("tool_trace", []))
        trace.append("sql_execute")
        try:
            cols, rows = await self._execute_sql(str(state.get("current_sql", "")))
            return {
                "execution_ok": True,
                "db_error": None,
                "columns": cols,
                "rows": rows,
                "tool_trace": trace,
            }
        except Exception as exc:  # pragma: no cover - backend/runtime dependent
            return {
                "execution_ok": False,
                "db_error": str(exc),
                "columns": [],
                "rows": [],
                "tool_trace": trace,
            }

    async def _node_record_attempt(self, state: _AgentState) -> _AgentState:
        attempts = list(state.get("attempts", []))
        attempts.append(
            {
                "attempt_number": int(state.get("attempt", 0)),
                "generated_sql": str(state.get("current_sql", "")),
                "llm_reason": state.get("llm_reason"),
                "validation_ok": bool(state.get("validation_ok", False)),
                "validation_reason": state.get("validation_reason"),
                "execution_ok": bool(state.get("execution_ok", False)),
                "db_error": state.get("db_error"),
            }
        )
        return {"attempts": attempts}

    async def _node_prepare_fix(self, state: _AgentState) -> _AgentState:
        return {
            "mode": "fix",
            "fix_from_sql": str(state.get("current_sql", "")),
            "fix_from_error": str(
                state.get("db_error")
                or state.get("validation_reason")
                or "unknown execution error"
            ),
        }

    async def _node_summarize_success(self, state: _AgentState) -> _AgentState:
        question = str(state.get("question", ""))
        sql_query = str(state.get("current_sql", ""))
        cols = state.get("columns", [])
        rows = state.get("rows", [])
        trace = list(state.get("tool_trace", []))
        trace.append("answer_summarize")
        answer = await self._build_answer(question, sql_query, cols, rows)
        return {
            "success": True,
            "final_sql": sql_query,
            "answer": answer,
            "failure_reason": None,
            "tool_trace": trace,
        }

    async def _node_summarize_failure(self, state: _AgentState) -> _AgentState:
        attempts = int(state.get("attempt", 0))
        reason = str(state.get("db_error") or state.get("validation_reason") or "unknown error")
        return {
            "success": False,
            "final_sql": str(state.get("current_sql", "")),
            "answer": f"SQL execution failed after {attempts} attempt(s): {reason}",
            "failure_reason": reason,
            "columns": [],
            "rows": [],
        }

    def _route_after_attempt(self, state: _AgentState) -> str:
        if bool(state.get("execution_ok", False)):
            return "summarize_success"
        if int(state.get("attempt", 0)) >= int(state.get("max_attempts", 3)):
            return "summarize_failure"
        return "prepare_fix"

    async def _build_answer(
        self,
        question: str,
        sql_query: str,
        cols: Cols,
        rows: Rows,
    ) -> str:
        payload = await self._call_llm_json(
            SQL_SUMMARY_SYSTEM_PROMPT,
            build_sql_summary_user_prompt(
                question=question,
                sql_query=sql_query,
                columns_json=json.dumps(cols),
                rows_json=json.dumps(rows[:30]),
            ),
        )
        answer = str((payload or {}).get("answer", "")).strip()
        if answer:
            return answer
        return self._default_answer(question, cols, rows)

    async def _call_llm_json(self, system_prompt: str, user_prompt: str) -> dict | None:
        system_text, user_text = _render_with_langchain(system_prompt, user_prompt)
        return await self._llm_json(system_text, user_text)

    async def _run_openai_agents_sdk(
        self,
        *,
        question: str,
        max_attempts: int,
    ) -> SQLAgentResult:
        try:
            from agents import Agent, Runner
            from pydantic import BaseModel
        except Exception as exc:  # pragma: no cover - dependency runtime path
            raise RuntimeError(
                "OpenAI Agents SDK is required for openai provider orchestration. "
                "Install openai-agents and openai."
            ) from exc

        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key

        class _SQLPayload(BaseModel):
            sql: str
            reason: str | None = None

        class _SummaryPayload(BaseModel):
            answer: str

        generator_agent = Agent(
            name="sql_generator",
            instructions=build_sql_generator_system_prompt(self.live_schema_text),
            model=self.model,
            output_type=_SQLPayload,
        )
        fixer_agent = Agent(
            name="sql_fixer",
            instructions=build_sql_fixer_system_prompt(self.live_schema_text),
            model=self.model,
            output_type=_SQLPayload,
        )
        summary_agent = Agent(
            name="sql_summarizer",
            instructions=SQL_SUMMARY_SYSTEM_PROMPT,
            model=self.model,
            output_type=_SummaryPayload,
        )

        attempts: list[SQLAgentAttempt] = []
        tool_trace: list[str] = []
        sql_query = ""
        cols: Cols = []
        rows: Rows = []
        last_error: str | None = None

        for idx in range(1, max_attempts + 1):
            if idx == 1:
                tool_trace.append("sql_generate")
                response = await Runner.run(
                    generator_agent,
                    build_sql_generator_user_prompt(question),
                )
            else:
                tool_trace.append(f"sql_fix_{idx}")
                response = await Runner.run(
                    fixer_agent,
                    build_sql_fixer_user_prompt(
                        question=question,
                        failed_sql=sql_query,
                        db_error=last_error or "unknown execution error",
                    ),
                )

            payload = _agent_output_to_dict(response.final_output)
            sql_query = str(payload.get("sql", "")).strip()
            llm_reason = str(payload.get("reason", "")).strip() or None
            if not sql_query:
                sql_query = self._fallback_sql(question)

            tool_trace.append("sql_validate")
            validation_ok, validation_reason = self._validate_sql(sql_query)

            execution_ok = False
            db_error: str | None = None
            if validation_ok:
                tool_trace.append("sql_execute")
                try:
                    cols, rows = await self._execute_sql(sql_query)
                    execution_ok = True
                except Exception as exc:  # pragma: no cover - backend/runtime dependent
                    db_error = str(exc)
                    last_error = db_error
            else:
                db_error = validation_reason
                last_error = validation_reason

            attempts.append(
                SQLAgentAttempt(
                    attempt_number=idx,
                    generated_sql=sql_query,
                    llm_reason=llm_reason,
                    validation_ok=validation_ok,
                    validation_reason=validation_reason if not validation_ok else None,
                    execution_ok=execution_ok,
                    db_error=db_error if not execution_ok else None,
                )
            )
            if execution_ok:
                tool_trace.append("answer_summarize")
                summary_res = await Runner.run(
                    summary_agent,
                    build_sql_summary_user_prompt(
                        question=question,
                        sql_query=sql_query,
                        columns_json=json.dumps(cols),
                        rows_json=json.dumps(rows[:30]),
                    ),
                )
                summary_payload = _agent_output_to_dict(summary_res.final_output)
                answer = str(summary_payload.get("answer", "")).strip()
                if not answer:
                    answer = self._default_answer(question, cols, rows)
                return SQLAgentResult(
                    success=True,
                    final_sql=sql_query,
                    answer=answer,
                    attempts=attempts,
                    columns=cols,
                    rows=rows,
                    tool_trace=tool_trace,
                )

        failure_reason = attempts[-1].db_error if attempts else "No SQL attempt executed."
        return SQLAgentResult(
            success=False,
            final_sql=sql_query,
            answer=f"SQL execution failed after {max_attempts} attempt(s): {failure_reason}",
            attempts=attempts,
            columns=[],
            rows=[],
            tool_trace=tool_trace,
            failure_reason=failure_reason,
        )


def _render_with_langchain(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    try:
        from langchain_core.prompts import ChatPromptTemplate
    except Exception:
        return system_prompt, user_prompt
    template = ChatPromptTemplate.from_messages(
        [("system", "{system_prompt}"), ("human", "{user_prompt}")]
    )
    messages = template.format_messages(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    if len(messages) < 2:
        return system_prompt, user_prompt
    return str(messages[0].content), str(messages[1].content)


def _agent_output_to_dict(output: object) -> dict:
    if output is None:
        return {}
    if isinstance(output, dict):
        return output
    if hasattr(output, "model_dump"):
        try:
            dumped = output.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}
