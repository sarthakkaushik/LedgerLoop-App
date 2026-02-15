from __future__ import annotations

from datetime import date
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from app.services.analysis.prompts import (
    SQL_SUMMARY_SYSTEM_PROMPT,
    build_langchain_sql_agent_system_prompt,
    build_sql_fixer_system_prompt,
    build_sql_fixer_user_prompt,
    build_sql_generator_system_prompt,
    build_sql_generator_user_prompt,
    build_sql_summary_user_prompt,
)
from app.services.analysis.tool_query_engine import build_answer, build_query

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
        household_hints_text: str | None = None,
        household_categories: list[str] | None = None,
        household_members: list[str] | None = None,
        reference_date: date | None = None,
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
        self.household_hints_text = household_hints_text
        self.household_categories = household_categories or []
        self.household_members = household_members or []
        self.reference_date = reference_date or date.today()

    async def run(self, question: str, max_attempts: int = 3) -> SQLAgentResult:
        if self.provider_name == "openai":
            try:
                result = await self._run_openai_agents_sdk(
                    question=question,
                    max_attempts=max_attempts,
                )
                if result.success:
                    return result
            except RuntimeError:
                # Keep service usable when SDK dependency is missing in local/dev.
                pass
            return await self._run_sequential(
                question=question,
                max_attempts=max_attempts,
            )
        if self.provider_name == "cerebras":
            try:
                result = await self._run_cerebras_langchain_agent(
                    question=question,
                    max_attempts=max_attempts,
                )
                if result.success:
                    return result
            except Exception:
                pass
            try:
                return await self._run_langgraph(
                    question=question,
                    max_attempts=max_attempts,
                )
            except RuntimeError:
                return await self._run_sequential(
                    question=question,
                    max_attempts=max_attempts,
                )
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
                    build_sql_generator_system_prompt(
                        self.live_schema_text,
                        self.household_hints_text,
                    ),
                    build_sql_generator_user_prompt(question),
                )
            else:
                tool_trace.append(f"sql_fix_{idx}")
                sql_payload = await self._call_llm_json(
                    build_sql_fixer_system_prompt(
                        self.live_schema_text,
                        self.household_hints_text,
                    ),
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

    async def _run_cerebras_langchain_agent(
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
                "LangChain Cerebras agent dependencies are required. "
                "Install langchain-cerebras."
            ) from exc

        if self.api_key:
            os.environ["CEREBRAS_API_KEY"] = self.api_key

        system_prompt = build_langchain_sql_agent_system_prompt(
            self.live_schema_text,
            self.household_hints_text,
        )
        attempts: list[SQLAgentAttempt] = []
        tool_trace: list[str] = ["tool_select"]
        final_sql = ""
        final_cols: Cols = []
        final_rows: Rows = []
        last_error: str | None = None
        next_reason: str | None = "langchain_cerebras_tool_sql"

        async def _execute_with_repair(sql: str) -> dict[str, Any]:
            nonlocal final_sql, final_cols, final_rows, last_error, next_reason

            sql_query = sql.strip() or self._fallback_sql(question)
            while len(attempts) < max_attempts:
                attempt_number = len(attempts) + 1
                tool_trace.append("sql_validate")
                validation_ok, validation_reason = self._validate_sql(sql_query)
                execution_ok = False
                db_error: str | None = None
                cols: Cols = []
                rows: Rows = []
                if validation_ok:
                    tool_trace.append("sql_execute")
                    try:
                        cols, rows = await self._execute_sql(sql_query)
                        execution_ok = True
                        final_sql = sql_query
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
                        generated_sql=sql_query,
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
                        "sql": sql_query,
                        "columns": cols,
                        "rows": rows,
                    }
                if len(attempts) >= max_attempts:
                    break

                tool_trace.append(f"sql_fix_{len(attempts) + 1}")
                fix_payload = await self._call_llm_json(
                    build_sql_fixer_system_prompt(
                        self.live_schema_text,
                        self.household_hints_text,
                    ),
                    build_sql_fixer_user_prompt(
                        question=question,
                        failed_sql=sql_query,
                        db_error=last_error or "unknown execution error",
                    ),
                )
                fixed_sql = str((fix_payload or {}).get("sql", "")).strip()
                next_reason = str((fix_payload or {}).get("reason", "")).strip() or "sql_fix_retry"
                if not fixed_sql:
                    break
                sql_query = fixed_sql
            return {
                "ok": False,
                "sql": sql_query,
                "columns": [],
                "rows": [],
                "error": last_error or "SQL execution failed.",
            }

        @tool("run_sql_query")
        async def run_sql_query(sql: str) -> dict[str, Any]:
            """
            Execute a SQL query against household expense analytics data.
            """
            tool_trace.append("sql_generate")
            return await _execute_with_repair(sql)

        llm = ChatCerebras(
            model=self.model,
            api_key=self.api_key,
            temperature=0,
        )
        agent = create_agent(
            model=llm,
            tools=[run_sql_query],
            system_prompt=system_prompt,
        )
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}
        )

        success = any(item.execution_ok for item in attempts)
        if success:
            answer = _extract_langchain_agent_answer(response).strip()
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

        fallback_sql = final_sql or self._fallback_sql(question)
        if not attempts:
            validation_ok, validation_reason = self._validate_sql(fallback_sql)
            db_error = validation_reason if not validation_ok else "Tool call was not executed."
            attempts = [
                SQLAgentAttempt(
                    attempt_number=1,
                    generated_sql=fallback_sql,
                    llm_reason="langchain_agent_missing_tool_call",
                    validation_ok=validation_ok,
                    validation_reason=validation_reason if not validation_ok else None,
                    execution_ok=False,
                    db_error=db_error,
                )
            ]
            last_error = db_error

        failure_reason = last_error or attempts[-1].db_error or "SQL execution failed."
        return SQLAgentResult(
            success=False,
            final_sql=attempts[-1].generated_sql if attempts else fallback_sql,
            answer=f"SQL execution failed after {len(attempts)} attempt(s): {failure_reason}",
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
                build_sql_fixer_system_prompt(
                    self.live_schema_text,
                    self.household_hints_text,
                ),
                build_sql_fixer_user_prompt(
                    question=question,
                    failed_sql=str(state.get("fix_from_sql", "")),
                    db_error=str(state.get("fix_from_error", "unknown execution error")),
                ),
            )
        else:
            trace.append("sql_generate")
            payload = await self._call_llm_json(
                build_sql_generator_system_prompt(
                    self.live_schema_text,
                    self.household_hints_text,
                ),
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
            from agents import Agent, Runner, function_tool
        except Exception as exc:  # pragma: no cover - dependency runtime path
            raise RuntimeError(
                "OpenAI Agents SDK is required for openai provider orchestration. "
                "Install openai-agents and openai."
            ) from exc

        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key

        async def _run_structured_query(
            *,
            intent: str = "auto",
            period: str = "this_month",
            status: str = "confirmed",
            category: str | None = None,
            member: str | None = None,
            top_n: int = 5,
            months: int = 6,
        ) -> dict:
            built = build_query(
                question=question,
                intent=intent,
                period=period,
                status=status,
                category=category,
                member=member,
                top_n=top_n,
                months=months,
                reference_date=self.reference_date,
                household_categories=self.household_categories,
                household_members=self.household_members,
            )
            validation_ok, validation_reason = self._validate_sql(built.sql)
            if not validation_ok:
                return {
                    "ok": False,
                    "tool": built.tool_name,
                    "intent": built.intent,
                    "sql": built.sql,
                    "validation_ok": False,
                    "validation_reason": validation_reason,
                    "execution_ok": False,
                    "db_error": validation_reason,
                    "columns": [],
                    "rows": [],
                    "answer": "",
                    "reason": (
                        f"intent={built.intent}; period={built.period_label}; "
                        f"category={built.resolved_category or 'none'}; "
                        f"member={built.resolved_member or 'none'}"
                    ),
                }

            try:
                cols, rows = await self._execute_sql(built.sql)
            except Exception as exc:  # pragma: no cover - backend/runtime dependent
                return {
                    "ok": False,
                    "tool": built.tool_name,
                    "intent": built.intent,
                    "sql": built.sql,
                    "validation_ok": True,
                    "validation_reason": None,
                    "execution_ok": False,
                    "db_error": str(exc),
                    "columns": [],
                    "rows": [],
                    "answer": "",
                    "reason": (
                        f"intent={built.intent}; period={built.period_label}; "
                        f"category={built.resolved_category or 'none'}; "
                        f"member={built.resolved_member or 'none'}"
                    ),
                }

            return {
                "ok": True,
                "tool": built.tool_name,
                "intent": built.intent,
                "sql": built.sql,
                "validation_ok": True,
                "validation_reason": None,
                "execution_ok": True,
                "db_error": None,
                "columns": cols,
                "rows": rows,
                "answer": build_answer(built, cols, rows),
                "reason": (
                    f"intent={built.intent}; period={built.period_label}; "
                    f"category={built.resolved_category or 'none'}; "
                    f"member={built.resolved_member or 'none'}"
                ),
            }

        @function_tool
        async def analyze_expenses(
            intent: str = "auto",
            period: str = "this_month",
            status: str = "confirmed",
            category: str | None = None,
            member: str | None = None,
            top_n: int = 5,
            months: int = 6,
        ) -> dict:
            """
            Analyze household expenses using deterministic SQL tools.

            Args:
                intent: One of total_spend, category_breakdown, member_breakdown, top_expenses,
                    monthly_trend, or auto.
                period: One of today, yesterday, this_week, last_7_days, last_30_days,
                    last_60_days, last_90_days, this_month, last_month, this_year, all_time.
                status: confirmed, draft, or all.
                category: Optional user category keyword (for example food, groceries, transport).
                member: Optional household member name.
                top_n: Number of rows for top_expenses style queries.
                months: Number of months for monthly_trend.
            """
            return await _run_structured_query(
                intent=intent,
                period=period,
                status=status,
                category=category,
                member=member,
                top_n=top_n,
                months=months,
            )

        household_categories_text = ", ".join(self.household_categories) or "none"
        household_members_text = ", ".join(self.household_members) or "none"
        instructions = (
            "You are an expense analytics planner. "
            "Always call the analyze_expenses tool exactly once. "
            "Do not answer directly without calling the tool.\n"
            "Use status='confirmed' unless user explicitly requests draft/all.\n"
            "Respect explicit constraints exactly (for example top 3, last 2 months).\n"
            "Known household categories: "
            f"{household_categories_text}\n"
            "Known household members: "
            f"{household_members_text}"
        )
        agent = Agent(
            name="expense_analytics_tool_agent",
            instructions=instructions,
            model=self.model,
            tools=[analyze_expenses],
            tool_use_behavior="stop_on_first_tool",
        )

        response = await Runner.run(agent, question)
        payload = _agent_output_to_dict(response.final_output)
        if not payload:
            fallback_sql = self._fallback_sql(question)
            validation_ok, validation_reason = self._validate_sql(fallback_sql)
            db_error = validation_reason if not validation_ok else "Tool call result missing."
            attempts = [
                SQLAgentAttempt(
                    attempt_number=1,
                    generated_sql=fallback_sql,
                    llm_reason="openai_tool_agent_no_structured_tool_output",
                    validation_ok=validation_ok,
                    validation_reason=validation_reason if not validation_ok else None,
                    execution_ok=False,
                    db_error=db_error,
                )
            ]
            return SQLAgentResult(
                success=False,
                final_sql=fallback_sql,
                answer=f"Tool-based analysis failed: {db_error}",
                attempts=attempts,
                columns=[],
                rows=[],
                tool_trace=["tool_select", "tool_missing_output"],
                failure_reason=db_error,
            )

        generated_sql = str(payload.get("sql", "")).strip()
        validation_ok = bool(payload.get("validation_ok", False))
        validation_reason = (
            str(payload.get("validation_reason", "")).strip() or None
        )
        execution_ok = bool(payload.get("execution_ok", False))
        db_error = str(payload.get("db_error", "")).strip() or None
        llm_reason = str(payload.get("reason", "")).strip() or None
        cols: Cols = payload.get("columns", []) if isinstance(payload.get("columns"), list) else []
        rows: Rows = payload.get("rows", []) if isinstance(payload.get("rows"), list) else []
        tool_name = str(payload.get("tool", "analyze_expenses")).strip() or "analyze_expenses"

        attempts = [
            SQLAgentAttempt(
                attempt_number=1,
                generated_sql=generated_sql,
                llm_reason=llm_reason,
                validation_ok=validation_ok,
                validation_reason=validation_reason,
                execution_ok=execution_ok,
                db_error=db_error,
            )
        ]
        if not validation_ok or not execution_ok:
            reason = db_error or validation_reason or "tool execution failed"
            return SQLAgentResult(
                success=False,
                final_sql=generated_sql,
                answer=f"Tool-based analysis failed: {reason}",
                attempts=attempts,
                columns=[],
                rows=[],
                tool_trace=["tool_select", tool_name, "tool_failed"],
                failure_reason=reason,
            )

        answer = str(payload.get("answer", "")).strip()
        if not answer:
            answer = self._default_answer(question, cols, rows)
        return SQLAgentResult(
            success=True,
            final_sql=generated_sql,
            answer=answer,
            attempts=attempts,
            columns=cols,
            rows=rows,
            tool_trace=["tool_select", tool_name, "sql_validate", "sql_execute"],
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
