import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.expense import Expense, ExpenseStatus
from app.models.llm_setting import LLMProvider
from app.models.user import User
from app.schemas.analysis import (
    AnalysisAskRequest,
    AnalysisAskResponse,
    AnalysisChart,
    AnalysisPoint,
    AnalysisTable,
)
from app.services.analysis.logging_service import (
    add_attempt_log,
    create_query_log,
    finalize_query_log,
)
from app.services.analysis.schema_introspection import load_live_schema_text
from app.services.analysis.sql_agent import SQLAgentResult, SQLAgentRunner
from app.services.analysis.sql_validation import validate_safe_sql
from app.services.llm.settings_service import (
    LLMRuntimeConfig,
    get_env_runtime_config,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

CHAT_HINTS = ("hello", "hi", "hey", "thanks", "thank you", "how are you", "what can you do")
ANALYTICS_HINTS = (
    "expense",
    "spend",
    "spent",
    "budget",
    "category",
    "trend",
    "month",
    "top",
    "dashboard",
    "breakdown",
    "member",
    "user split",
    "total",
    "grocery",
    "grocer",
    "bill",
    "rent",
    "food",
    "uber",
    "transport",
    "merchant",
)
HOUSEHOLD_CTE = """
WITH household_expenses AS (
  SELECT
    CAST(e.id AS TEXT) AS expense_id,
    CAST(e.household_id AS TEXT) AS household_id,
    CAST(e.logged_by_user_id AS TEXT) AS logged_by_user_id,
    COALESCE(u.full_name,'Unknown') AS logged_by,
    e.status AS status,
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
CHAT_PROMPT = """
Return JSON only:
{"answer":"..."}
You are the assistant inside a household expense tracker app.
Rules:
- Answer general questions directly and briefly.
- If user asks about app usage, explain how to log expenses and ask analytics questions.
- If user asks for spending data, suggest analytics-style prompts.
- Keep response concise and practical.
"""


def _first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def _shift_months(value: date, delta: int) -> date:
    idx = (value.month - 1) + delta
    year = value.year + (idx // 12)
    month = (idx % 12) + 1
    return date(year, month, 1)


def _last_day_of_month(value: date) -> date:
    return _shift_months(_first_day_of_month(value), 1) - timedelta(days=1)


def _extract_int(pattern: str, text_value: str, default: int, min_v: int, max_v: int) -> int:
    m = re.search(pattern, text_value)
    if not m:
        return default
    return min(max(int(m.group(1)), min_v), max_v)


def _extract_json(raw: str) -> dict | None:
    t = raw.strip()
    if not (t.startswith("{") and t.endswith("}")):
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e != -1 and e > s:
            t = t[s : e + 1]
    try:
        return json.loads(t)
    except Exception:
        return None


def _looks_chat(text_value: str) -> bool:
    l = text_value.lower().strip()
    if any(x in l for x in ANALYTICS_HINTS):
        return False
    if any(x in l for x in CHAT_HINTS):
        return True
    if l.endswith("?"):
        return True
    return l.startswith(
        (
            "what ",
            "why ",
            "how ",
            "who ",
            "where ",
            "when ",
            "can you ",
            "could you ",
            "tell me ",
            "explain ",
            "help ",
        )
    )


def _fixed_tool(text_value: str) -> tuple[str | None, float]:
    l = text_value.lower()
    if _looks_chat(l):
        return "chat", 1.0
    if any(x in l for x in ("trend", "over time", "month over month")):
        return "monthly_trend", 0.95
    if "category" in l or "breakdown" in l:
        return "category_breakdown", 0.95
    if any(x in l for x in ("who spent", "by member", "by user", "spouse spend")):
        return "member_breakdown", 0.92
    if ("top " in l or "largest" in l or "highest" in l or "biggest" in l) and "expense" in l:
        return "top_expenses", 0.95
    if any(x in l for x in ("how much did we spend", "total spend", "spent this month", "spent last month")):
        return "summary", 0.92
    return None, 0.0


def _period(text_value: str, today: date) -> tuple[date, date, str]:
    l = text_value.lower()
    if "today" in l:
        return today, today, "Today"
    if "yesterday" in l:
        y = today - timedelta(days=1)
        return y, y, "Yesterday"
    if "last month" in l:
        s = _shift_months(_first_day_of_month(today), -1)
        return s, _last_day_of_month(s), "Last month"
    s = _first_day_of_month(today)
    return s, _last_day_of_month(s), "This month"


async def _confirmed(session: AsyncSession, household_id: UUID, start: date | None = None, end: date | None = None) -> list[Expense]:
    q = select(Expense).where(Expense.household_id == household_id, Expense.status == ExpenseStatus.CONFIRMED)
    if start is not None:
        q = q.where(Expense.date_incurred >= start)
    if end is not None:
        q = q.where(Expense.date_incurred <= end)
    res = await session.execute(q)
    return res.scalars().all()


async def _user_names(session: AsyncSession, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    res = await session.execute(select(User).where(User.id.in_(list(ids))))
    return {u.id: u.full_name for u in res.scalars().all()}


def _fixed_summary(expenses: list[Expense], label: str) -> dict:
    vals = [float(x.amount) for x in expenses if x.amount is not None]
    total = round(sum(vals), 2)
    cnt = len(vals)
    avg = round(total / cnt, 2) if cnt else 0.0
    return {
        "answer": f"{label}, your household logged {cnt} confirmed expense(s) totalling {total:.2f}.",
        "chart": None,
        "table": AnalysisTable(columns=["Period", "Confirmed Expenses", "Total", "Average"], rows=[[label, cnt, total, avg]]),
    }


def _fixed_category(expenses: list[Expense], label: str) -> dict:
    sums: dict[str, float] = defaultdict(float)
    cnts: dict[str, int] = defaultdict(int)
    for e in expenses:
        if e.amount is None:
            continue
        c = e.category or "Other"
        sums[c] += float(e.amount)
        cnts[c] += 1
    ordered = sorted(sums.items(), key=lambda i: i[1], reverse=True)
    rows = [[k, round(v, 2), cnts[k]] for k, v in ordered]
    if not rows:
        return {"answer": f"No confirmed expenses found for {label.lower()}.", "chart": None, "table": AnalysisTable(columns=["Category", "Amount", "Count"], rows=[])}
    top_k, top_v = ordered[0]
    return {
        "answer": f"For {label.lower()}, top category is {top_k} at {top_v:.2f}.",
        "chart": AnalysisChart(chart_type="bar", title=f"Category Spend - {label}", points=[AnalysisPoint(label=k, value=round(v, 2)) for k, v in ordered[:8]]),
        "table": AnalysisTable(columns=["Category", "Amount", "Count"], rows=rows),
    }


async def _fixed_member(session: AsyncSession, expenses: list[Expense], label: str) -> dict:
    sums: dict[UUID, float] = defaultdict(float)
    cnts: dict[UUID, int] = defaultdict(int)
    for e in expenses:
        if e.amount is None:
            continue
        sums[e.logged_by_user_id] += float(e.amount)
        cnts[e.logged_by_user_id] += 1
    names = await _user_names(session, set(sums.keys()))
    ordered = sorted(sums.items(), key=lambda i: i[1], reverse=True)
    rows = [[names.get(uid, "Unknown"), round(v, 2), cnts[uid]] for uid, v in ordered]
    if not rows:
        return {"answer": f"No confirmed expenses found for {label.lower()}.", "chart": None, "table": AnalysisTable(columns=["Member", "Amount", "Count"], rows=[])}
    top_uid, top_v = ordered[0]
    top_n = names.get(top_uid, "Unknown")
    return {
        "answer": f"For {label.lower()}, {top_n} spent the most at {top_v:.2f}.",
        "chart": AnalysisChart(chart_type="bar", title=f"Member Spend - {label}", points=[AnalysisPoint(label=names.get(uid, 'Unknown'), value=round(v, 2)) for uid, v in ordered]),
        "table": AnalysisTable(columns=["Member", "Amount", "Count"], rows=rows),
    }


async def _fixed_top(session: AsyncSession, hid: UUID, today: date, question: str) -> dict:
    n_months = _extract_int(r"(?:last|past)\s+(\d{1,2})\s+months?", question.lower(), 3, 1, 24)
    n = _extract_int(r"top\s+(\d{1,2})", question.lower(), 5, 1, 20)
    start = _shift_months(_first_day_of_month(today), -(n_months - 1))
    expenses = await _confirmed(session, hid, start, today)
    ranked = sorted([e for e in expenses if e.amount is not None], key=lambda e: float(e.amount), reverse=True)[:n]
    names = await _user_names(session, {e.logged_by_user_id for e in ranked})
    rows: list[list[str | float | int]] = []
    points: list[AnalysisPoint] = []
    for e in ranked:
        amount = round(float(e.amount), 2)
        cat = e.category or "Other"
        desc = e.description or e.merchant_or_item or "Expense"
        rows.append([str(e.date_incurred), amount, cat, desc, names.get(e.logged_by_user_id, "Unknown")])
        points.append(AnalysisPoint(label=cat, value=amount))
    return {
        "answer": f"Top {len(rows)} confirmed expense(s) from last {n_months} month(s).",
        "chart": AnalysisChart(chart_type="bar", title=f"Top Expenses - Last {n_months} Months", points=points) if rows else None,
        "table": AnalysisTable(columns=["Date", "Amount", "Category", "Description", "Logged By"], rows=rows),
    }


async def _fixed_trend(session: AsyncSession, hid: UUID, today: date, question: str) -> dict:
    months = _extract_int(r"(?:last|past)\s+(\d{1,2})\s+months?", question.lower(), 6, 1, 24)
    first_this = _first_day_of_month(today)
    start = _shift_months(first_this, -(months - 1))
    expenses = await _confirmed(session, hid, start, today)
    m: dict[str, float] = defaultdict(float)
    for e in expenses:
        if e.amount is None:
            continue
        m[e.date_incurred.strftime("%Y-%m")] += float(e.amount)
    rows: list[list[str | float | int]] = []
    points: list[AnalysisPoint] = []
    for i in range(months):
        k = _shift_months(first_this, -(months - 1 - i)).strftime("%Y-%m")
        v = round(m.get(k, 0.0), 2)
        rows.append([k, v])
        points.append(AnalysisPoint(label=k, value=v))
    peak = max(points, key=lambda p: p.value) if points else None
    ans = f"Monthly trend for last {months} month(s). Highest month: {peak.label} with {peak.value:.2f}." if peak else f"No confirmed expenses found in last {months} month(s)."
    return {"answer": ans, "chart": AnalysisChart(chart_type="line", title=f"Monthly Spend Trend - Last {months} Months", points=points), "table": AnalysisTable(columns=["Month", "Amount"], rows=rows)}


def _safe_sql(query: str) -> tuple[bool, str]:
    return validate_safe_sql(query, allowed_tables={"household_expenses"})


def _fallback_sql(question: str) -> str:
    q = question.lower()
    if "category" in q or "breakdown" in q:
        return "SELECT category, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, COUNT(*) AS expense_count FROM household_expenses WHERE status='confirmed' GROUP BY category ORDER BY total_spend DESC"
    if "who" in q or "member" in q or "spouse" in q:
        return "SELECT logged_by, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, COUNT(*) AS expense_count FROM household_expenses WHERE status='confirmed' GROUP BY logged_by ORDER BY total_spend DESC"
    if "trend" in q or "month" in q:
        return "SELECT substr(date_incurred,1,7) AS month, ROUND(COALESCE(SUM(amount),0),2) AS total_spend FROM household_expenses WHERE status='confirmed' GROUP BY substr(date_incurred,1,7) ORDER BY month"
    if "top" in q or "largest" in q or "highest" in q:
        top_n = _extract_int(r"top\s+(\d{1,2})", q, 5, 1, 20)
        return f"SELECT date_incurred, amount, category, COALESCE(description, merchant_or_item, 'Expense') AS note, logged_by FROM household_expenses WHERE status='confirmed' ORDER BY amount DESC LIMIT {top_n}"
    return "SELECT COUNT(*) AS expense_count, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, ROUND(COALESCE(AVG(amount),0),2) AS avg_spend FROM household_expenses WHERE status='confirmed'"


async def _llm_json(provider: LLMProvider, model: str, api_key: str | None, system_prompt: str, user_prompt: str) -> dict | None:
    if provider == LLMProvider.MOCK or not api_key:
        return None
    try:
        if provider == LLMProvider.OPENAI:
            payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0, "response_format": {"type": "json_object"}}
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
                r = await c.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                return _extract_json(r.json()["choices"][0]["message"]["content"])
        if provider == LLMProvider.GEMINI:
            payload = {"contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
                r = await c.post(url, json=payload)
                r.raise_for_status()
                return _extract_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        if provider == LLMProvider.CEREBRAS:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            }
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
                r = await c.post("https://api.cerebras.ai/v1/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                raw_content = r.json()["choices"][0]["message"]["content"]
                if isinstance(raw_content, str):
                    return _extract_json(raw_content)
                return _extract_json(json.dumps(raw_content))
    except Exception:
        return None
    return None


def _cell(v: Any) -> str | float | int:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return v
    return str(v)


async def _run_sql(session: AsyncSession, household_id: UUID, sql_query: str) -> tuple[list[str], list[list[str | float | int]]]:
    q = f"{HOUSEHOLD_CTE}\nSELECT * FROM (\n{sql_query}\n) AS agent_result\nLIMIT :result_limit"
    try:
        r = await session.execute(text(q), {"household_id": str(household_id), "result_limit": 200})
    except Exception:
        await session.rollback()
        raise
    maps = r.mappings().all()
    if not maps:
        return list(r.keys()), []
    cols = list(maps[0].keys())
    return cols, [[_cell(m.get(c)) for c in cols] for m in maps]


def _chart(question: str, cols: list[str], rows: list[list[str | float | int]], hint: dict | None) -> AnalysisChart | None:
    if not rows or len(cols) < 2:
        return None
    nums = {i for i, _ in enumerate(cols) if sum(1 for row in rows[:30] if i < len(row) and isinstance(row[i], (int, float))) >= max(1, len(rows[:30]) // 2)}
    if not nums:
        return None
    if hint:
        xk, yk = hint.get("x_key"), hint.get("y_key")
        ct = str(hint.get("chart_type", "none")).lower()
        if ct in {"bar", "line"} and xk in cols and yk in cols and cols.index(yk) in nums:
            xi, yi = cols.index(xk), cols.index(yk)
            pts = [AnalysisPoint(label=str(r[xi]), value=float(r[yi])) for r in rows[:24] if yi < len(r) and isinstance(r[yi], (int, float))]
            if pts:
                title = str(hint.get("chart_title", f"{cols[yi]} by {cols[xi]}"))
                return AnalysisChart(chart_type=ct, title=title, points=pts)
    yi = min(nums)
    xi = 0 if yi != 0 else 1
    if xi >= len(cols):
        return None
    pts = [AnalysisPoint(label=str(r[xi]), value=float(r[yi])) for r in rows[:24] if yi < len(r) and isinstance(r[yi], (int, float))]
    if not pts:
        return None
    line = "trend" in question.lower() or "month" in question.lower() or "date" in cols[xi].lower()
    return AnalysisChart(chart_type="line" if line else "bar", title=f"{cols[yi]} by {cols[xi]}", points=pts)


def _default_answer(question: str, cols: list[str], rows: list[list[str | float | int]]) -> str:
    if not rows:
        return "No matching confirmed expenses were found for that question."
    if len(rows) == 1:
        return "Computed result: " + ", ".join(f"{cols[i]}={rows[0][i]}" for i in range(min(4, len(cols)))) + "."
    return f"I ran the query for '{question}' and found {len(rows)} row(s)."


def _chat_fallback_answer(question: str) -> str:
    low = question.lower()
    if "what can you do" in low or "help" in low:
        return (
            "I can help with everyday questions and household expense insights. "
            "Try: 'How much did we spend this month?' or ask any general question."
        )
    return (
        "I can answer general questions and also help with household spend analytics. "
        "Ask your question directly, or try 'Show category breakdown for this month'."
    )


async def _chat_llm_answer(runtime: LLMRuntimeConfig, question: str) -> tuple[str, bool]:
    payload = await _llm_json(
        runtime.provider,
        runtime.model,
        runtime.api_key,
        CHAT_PROMPT,
        f"user_message: {question}",
    )
    if isinstance(payload, dict):
        answer = str(payload.get("answer", "")).strip()
        if answer:
            return answer, True
    return _chat_fallback_answer(question), False


async def _run_sql_agent(
    *,
    runtime: LLMRuntimeConfig,
    session: AsyncSession,
    household_id: UUID,
    question: str,
) -> SQLAgentResult:
    live_schema_text = await load_live_schema_text(session)

    async def llm_callback(system_prompt: str, user_prompt: str) -> dict | None:
        return await _llm_json(
            runtime.provider,
            runtime.model,
            runtime.api_key,
            system_prompt,
            user_prompt,
        )

    async def execute_sql(sql_query: str) -> tuple[list[str], list[list[str | float | int]]]:
        return await _run_sql(session, household_id, sql_query)

    runner = SQLAgentRunner(
        provider_name=runtime.provider.value,
        llm_json=llm_callback,
        validate_sql=_safe_sql,
        execute_sql=execute_sql,
        fallback_sql=_fallback_sql,
        default_answer=_default_answer,
        model=runtime.model,
        api_key=runtime.api_key,
        live_schema_text=live_schema_text,
    )
    return await runner.run(question, max_attempts=3)


@router.post("/ask", response_model=AnalysisAskResponse)
async def ask_analysis(payload: AnalysisAskRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> AnalysisAskResponse:
    today = datetime.now(UTC).date()
    question = payload.text.strip()
    tool, conf = _fixed_tool(question)
    runtime = get_env_runtime_config()
    initial_mode = "chat" if tool == "chat" else "analytics"
    initial_route = "chat" if tool == "chat" else ("fixed" if tool else "agent")
    initial_tool = tool or "adhoc_sql"

    query_log = None
    try:
        query_log = await create_query_log(
            session,
            household_id=user.household_id,
            user_id=user.id,
            provider=runtime.provider.value,
            model=runtime.model,
            question=question,
            mode=initial_mode,
            route=initial_route,
            tool=initial_tool,
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
    ) -> AnalysisAskResponse:
        if query_log is not None:
            try:
                await finalize_query_log(
                    session,
                    query_log=query_log,
                    status=status,
                    final_answer=response.answer,
                    attempt_count=attempt_count,
                    final_sql=response.sql,
                    failure_reason=failure_reason,
                    mode=response.mode,
                    route=response.route,
                    tool=response.tool,
                )
            except Exception:
                await session.rollback()
        return response

    if tool == "chat":
        answer, via_llm = await _chat_llm_answer(runtime, question)
        return await _finish(
            AnalysisAskResponse(
            mode="chat",
            route="chat",
            confidence=0.92 if via_llm else 0.6,
            tool="chat",
            tool_trace=["chat_llm"] if via_llm else ["chat_fallback"],
            answer=answer,
            )
        )
    if tool == "summary":
        s, e, lbl = _period(question, today)
        d = _fixed_summary(await _confirmed(session, user.household_id, s, e), lbl)
        return await _finish(
            AnalysisAskResponse(mode="analytics", route="fixed", confidence=conf, tool="summary", tool_trace=["summary"], answer=d["answer"], chart=d["chart"], table=d["table"])
        )
    if tool == "category_breakdown":
        s, e, lbl = _period(question, today)
        d = _fixed_category(await _confirmed(session, user.household_id, s, e), lbl)
        return await _finish(
            AnalysisAskResponse(mode="analytics", route="fixed", confidence=conf, tool="category_breakdown", tool_trace=["category_breakdown"], answer=d["answer"], chart=d["chart"], table=d["table"])
        )
    if tool == "member_breakdown":
        s, e, lbl = _period(question, today)
        d = await _fixed_member(session, await _confirmed(session, user.household_id, s, e), lbl)
        return await _finish(
            AnalysisAskResponse(mode="analytics", route="fixed", confidence=conf, tool="member_breakdown", tool_trace=["member_breakdown"], answer=d["answer"], chart=d["chart"], table=d["table"])
        )
    if tool == "top_expenses":
        d = await _fixed_top(session, user.household_id, today, question)
        return await _finish(
            AnalysisAskResponse(mode="analytics", route="fixed", confidence=conf, tool="top_expenses", tool_trace=["top_expenses"], answer=d["answer"], chart=d["chart"], table=d["table"])
        )
    if tool == "monthly_trend":
        d = await _fixed_trend(session, user.household_id, today, question)
        return await _finish(
            AnalysisAskResponse(mode="analytics", route="fixed", confidence=conf, tool="monthly_trend", tool_trace=["monthly_trend"], answer=d["answer"], chart=d["chart"], table=d["table"])
        )

    try:
        agent_result = await _run_sql_agent(
            runtime=runtime,
            session=session,
            household_id=user.household_id,
            question=question,
        )
    except Exception as exc:
        response = AnalysisAskResponse(
            mode="analytics",
            route="agent",
            confidence=0.35,
            tool="adhoc_sql",
            tool_trace=["sql_generate", "sql_validate", "sql_execute"],
            sql=None,
            answer=f"SQL agent failed to run: {exc}",
            table=AnalysisTable(columns=[], rows=[]),
        )
        return await _finish(
            response,
            status="failed",
            failure_reason=str(exc),
            attempt_count=0,
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

    chart = _chart(question, agent_result.columns, agent_result.rows, None)
    response = AnalysisAskResponse(
        mode="analytics",
        route="agent",
        confidence=0.82 if agent_result.success and runtime.provider != LLMProvider.MOCK else (0.62 if agent_result.success else 0.4),
        tool="adhoc_sql",
        tool_trace=agent_result.tool_trace,
        sql=agent_result.final_sql or None,
        answer=agent_result.answer,
        chart=chart,
        table=AnalysisTable(columns=agent_result.columns, rows=agent_result.rows),
    )
    return await _finish(
        response,
        status="success" if agent_result.success else "failed",
        failure_reason=agent_result.failure_reason,
        attempt_count=len(agent_result.attempts),
    )
