from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal
from difflib import SequenceMatcher
import re
from typing import Any, TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends
from langgraph.graph import END, START, StateGraph
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.models.user import User
from app.schemas.analysis import (
    AnalysisAskE2EPostgresRequest,
    AnalysisAskRequest,
    AnalysisAskResponse,
)
from app.services.analysis.logging_service import (
    add_attempt_log,
    create_query_log,
    finalize_query_log,
)
from app.services.analysis.sql_agent import (
    SQLAgentAttempt,
    SQLAgentResult,
    SQLAgentRunner,
    extract_json_payload,
)
from app.services.analysis.sql_validation import validate_safe_sql
from app.services.llm.settings_service import LLMRuntimeConfig, get_env_runtime_config
from app.services.taxonomy_service import build_household_taxonomy_map

router = APIRouter(prefix="/analysis", tags=["analysis"])
settings = get_settings()

SQLExecutor = Callable[[str], Awaitable[tuple[list[str], list[list[str | float | int]]]]]
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_INTERNAL_ID_COL_RE = re.compile(r"_id$", flags=re.IGNORECASE)
_INTERNAL_TOKEN_RE = re.compile(
    r"\b(?:expense_id|household_id|logged_by_user_id|user_id)\b",
    flags=re.IGNORECASE,
)
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_PERSON_FRAGMENT_PATTERNS = [
    re.compile(
        r"\bhow\s+much\s+([a-z][a-z\s.'-]{1,40}?)\s+(?:spend|spent|pay|paid|pays)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b(?:spent|spend|paid|pay)\s+by\s+([a-z][a-z\s.'-]{1,40})\b", flags=re.IGNORECASE),
    re.compile(r"\b([a-z][a-z\s.'-]{1,40})['’]s\s+(?:spend|spending|expenses?)\b", flags=re.IGNORECASE),
]
_CATEGORY_FRAGMENT_PATTERNS = [
    re.compile(r"\b(?:on|for|in|under)\s+([a-z][a-z0-9\s&/_-]{1,40})\s+category\b", flags=re.IGNORECASE),
    re.compile(r"\bcategory\s+(?:is\s+)?([a-z][a-z0-9\s&/_-]{1,40})\b", flags=re.IGNORECASE),
]
_SUBCATEGORY_FRAGMENT_PATTERNS = [
    re.compile(
        r"\b(?:on|for|in|under)\s+([a-z][a-z0-9\s&/_-]{1,40})\s+subcategory\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\bsubcategory\s+(?:is\s+)?([a-z][a-z0-9\s&/_-]{1,40})\b", flags=re.IGNORECASE),
]
_QUOTED_PHRASE_RE = re.compile(r"[\"']([^\"']{2,80})[\"']")
_DESCRIPTION_FRAGMENT_RE = re.compile(
    r"\b(?:description|merchant|item|memo|note)\s+"
    r"(?:contains|contain|like|with|matching)\s+([a-z0-9][a-z0-9\s&/_-]{1,80})",
    flags=re.IGNORECASE,
)
_EMPTY_HINTS: list[str] = []


class _AnalysisGraphState(TypedDict, total=False):
    question: str
    resolved_question: str
    fallback_question: str
    context_hints: list[str]
    should_fuzzy_retry: bool
    runtime: LLMRuntimeConfig
    execute_sql: SQLExecutor
    household_id: UUID
    session: AsyncSession
    primary_result: SQLAgentResult
    final_result: SQLAgentResult


HOUSEHOLD_CTE = """
WITH household_expenses AS (
  SELECT
    CAST(e.id AS TEXT) AS expense_id,
    CAST(e.household_id AS TEXT) AS household_id,
    CAST(e.logged_by_user_id AS TEXT) AS logged_by_user_id,
    COALESCE(u.full_name,'Unknown') AS logged_by,
    CAST(e.status AS TEXT) AS status,
    COALESCE(e.category,'Other') AS category,
    e.subcategory AS subcategory,
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
    *,
    model: str,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
) -> dict | None:
    if not api_key:
        return None
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
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


def _redact_uuids(text: str) -> str:
    return _UUID_RE.sub("member", text)


def _is_internal_id_column(column: str) -> bool:
    normalized = column.strip().lower()
    if normalized in {"expense_id", "household_id", "logged_by_user_id", "user_id"}:
        return True
    return bool(_INTERNAL_ID_COL_RE.search(normalized))


def _sanitize_table(
    columns: list[str],
    rows: list[list[str | float | int]],
) -> tuple[list[str], list[list[str | float | int]]]:
    if not columns:
        return [], []
    keep_indexes = [idx for idx, column in enumerate(columns) if not _is_internal_id_column(column)]
    if not keep_indexes:
        keep_indexes = list(range(len(columns)))
    safe_columns = [columns[idx] for idx in keep_indexes]
    safe_rows: list[list[str | float | int]] = []
    for row in rows:
        safe_row: list[str | float | int] = []
        for idx in keep_indexes:
            value = row[idx] if idx < len(row) else ""
            if isinstance(value, str):
                safe_row.append(_redact_uuids(value))
            else:
                safe_row.append(value)
        safe_rows.append(safe_row)
    return safe_columns, safe_rows


def _find_column_index(columns: list[str], *names: str) -> int | None:
    lowered = {column.lower(): idx for idx, column in enumerate(columns)}
    for name in names:
        idx = lowered.get(name.lower())
        if idx is not None:
            return idx
    return None


def _format_date_for_answer(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        try:
            parsed = datetime.combine(date.fromisoformat(raw), datetime.min.time())
        except Exception:
            return raw
    return parsed.strftime("%b %d, %Y").replace(" 0", " ")


def _format_amount_for_answer(value: str | float | int, currency: str | None) -> str:
    try:
        numeric = float(value)
    except Exception:
        return str(value)
    code = (currency or "INR").strip().upper() or "INR"
    return f"{numeric:,.2f} {code}"


def _build_friendly_row_summary(
    columns: list[str],
    row: list[str | float | int],
) -> str:
    person_idx = _find_column_index(columns, "logged_by", "user_name", "member", "person")
    amount_idx = _find_column_index(columns, "amount", "total", "sum", "spend")
    currency_idx = _find_column_index(columns, "currency")
    category_idx = _find_column_index(columns, "category")
    subcategory_idx = _find_column_index(columns, "subcategory")
    desc_idx = _find_column_index(columns, "description", "merchant_or_item", "merchant")
    date_idx = _find_column_index(columns, "date_incurred", "date", "created_at")

    person = str(row[person_idx]).strip() if person_idx is not None and person_idx < len(row) else ""
    category = str(row[category_idx]).strip() if category_idx is not None and category_idx < len(row) else ""
    subcategory = (
        str(row[subcategory_idx]).strip()
        if subcategory_idx is not None and subcategory_idx < len(row)
        else ""
    )
    description = str(row[desc_idx]).strip() if desc_idx is not None and desc_idx < len(row) else ""
    date_text = (
        _format_date_for_answer(str(row[date_idx]))
        if date_idx is not None and date_idx < len(row)
        else ""
    )
    currency = (
        str(row[currency_idx]).strip()
        if currency_idx is not None and currency_idx < len(row)
        else "INR"
    )
    amount_text = (
        _format_amount_for_answer(row[amount_idx], currency)
        if amount_idx is not None and amount_idx < len(row)
        else ""
    )

    summary = person or "Household member"
    details: list[str] = []
    if amount_text:
        details.append(amount_text)
    if category:
        details.append(
            f"{category} > {subcategory}" if subcategory and subcategory.lower() != category.lower() else category
        )
    if description:
        details.append(description)
    if date_text:
        details.append(date_text)
    if details:
        summary += ": " + ", ".join(details)
    return summary


def _build_friendly_answer(
    question: str,
    columns: list[str],
    rows: list[list[str | float | int]],
) -> str:
    if not rows:
        return "I could not find matching confirmed expenses for that request."
    preview_count = min(3, len(rows))
    lines = [f'Here is a clear summary for "{question}":']
    for row in rows[:preview_count]:
        lines.append(f"- {_build_friendly_row_summary(columns, row)}")
    if len(rows) > preview_count:
        lines.append(f"- Plus {len(rows) - preview_count} more row(s) in the table below.")
    return "\n".join(lines)


def _looks_like_raw_table_dump(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    low = stripped.lower()
    return stripped.count("|") >= 12 or "user_id" in low or "------" in stripped


def _finalize_user_answer(
    *,
    question: str,
    raw_answer: str,
    columns: list[str],
    rows: list[list[str | float | int]],
    success: bool,
) -> str:
    clean = _redact_uuids(raw_answer or "")
    clean = _INTERNAL_TOKEN_RE.sub("member", clean).strip()
    if not success:
        return clean
    if _looks_like_raw_table_dump(clean):
        return _build_friendly_answer(question, columns, rows)
    return clean


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


def _normalize_fragment(value: str) -> str:
    collapsed = _NON_WORD_RE.sub(" ", value.lower()).strip()
    return " ".join(collapsed.split())


def _clean_extracted_fragment(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized_space = " ".join(raw.split())
    trimmed = re.sub(r"\b(?:category|subcategory|description)\b$", "", normalized_space, flags=re.IGNORECASE)
    return " ".join(trimmed.strip().split())


def _extract_first_fragment(question: str, patterns: list[re.Pattern[str]]) -> str:
    for pattern in patterns:
        match = pattern.search(question)
        if not match:
            continue
        extracted = _clean_extracted_fragment(match.group(1))
        if extracted:
            return extracted
    return ""


def _extract_description_phrase(question: str) -> str:
    quoted = _QUOTED_PHRASE_RE.search(question)
    if quoted:
        phrase = _clean_extracted_fragment(quoted.group(1))
        if phrase:
            return phrase
    match = _DESCRIPTION_FRAGMENT_RE.search(question)
    if not match:
        return ""
    return _clean_extracted_fragment(match.group(1))


def _match_score(fragment: str, candidate: str) -> float:
    fragment_norm = _normalize_fragment(fragment)
    candidate_norm = _normalize_fragment(candidate)
    if not fragment_norm or not candidate_norm:
        return 0.0
    if fragment_norm == candidate_norm:
        return 1.0
    if candidate_norm.startswith(f"{fragment_norm} "):
        return 0.96
    if f" {fragment_norm} " in f" {candidate_norm} ":
        return 0.92
    fragment_tokens = set(fragment_norm.split())
    candidate_tokens = set(candidate_norm.split())
    overlap = (
        len(fragment_tokens & candidate_tokens) / len(fragment_tokens)
        if fragment_tokens
        else 0.0
    )
    seq_ratio = SequenceMatcher(None, fragment_norm, candidate_norm).ratio()
    return max(overlap * 0.92, seq_ratio * 0.78)


def _resolve_alias(fragment: str, candidates: list[str], *, min_score: float = 0.6) -> tuple[str | None, list[str]]:
    cleaned_fragment = _clean_extracted_fragment(fragment)
    if not cleaned_fragment:
        return None, []
    scored: list[tuple[float, str]] = []
    for candidate in candidates:
        score = _match_score(cleaned_fragment, candidate)
        if score >= min_score:
            scored.append((score, candidate))
    if not scored:
        return None, []
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_candidate = scored[0]
    close_candidates = [
        candidate
        for score, candidate in scored
        if score >= max(top_score - 0.03, min_score)
    ]
    if len(close_candidates) == 1:
        return top_candidate, []
    return None, close_candidates[:3]


async def _load_resolution_candidates(
    session: AsyncSession,
    *,
    household_id: UUID,
) -> tuple[list[str], list[str], list[str]]:
    members_result = await session.execute(
        select(User.full_name).where(
            User.household_id == household_id,
            User.is_active.is_(True),
        )
    )
    member_names = sorted(
        {
            str(name).strip()
            for name in members_result.scalars().all()
            if name and str(name).strip()
        }
    )
    categories, taxonomy = await build_household_taxonomy_map(
        session,
        household_id=household_id,
    )
    subcategories = sorted(
        {
            str(subcategory).strip()
            for values in taxonomy.values()
            for subcategory in values
            if subcategory and str(subcategory).strip()
        }
    )
    return member_names, categories, subcategories


async def _resolve_question_context(
    *,
    question: str,
    session: AsyncSession,
    household_id: UUID,
) -> tuple[list[str], bool]:
    hints: list[str] = []
    should_fuzzy_retry = False
    member_names, categories, subcategories = await _load_resolution_candidates(
        session,
        household_id=household_id,
    )

    person_fragment = _extract_first_fragment(question, _PERSON_FRAGMENT_PATTERNS)
    if person_fragment:
        resolved_person, ambiguous_people = _resolve_alias(person_fragment, member_names, min_score=0.58)
        if resolved_person:
            hints.append(
                f"Person mention '{person_fragment}' maps to household member '{resolved_person}'."
            )
            should_fuzzy_retry = True
        elif ambiguous_people:
            hints.append(
                "Person mention "
                f"'{person_fragment}' is ambiguous across: {', '.join(ambiguous_people)}."
            )
            should_fuzzy_retry = True

    category_fragment = _extract_first_fragment(question, _CATEGORY_FRAGMENT_PATTERNS)
    if category_fragment:
        resolved_category, ambiguous_categories = _resolve_alias(
            category_fragment,
            categories,
            min_score=0.55,
        )
        if resolved_category:
            hints.append(
                f"Category mention '{category_fragment}' maps to '{resolved_category}'."
            )
            should_fuzzy_retry = True
        elif ambiguous_categories:
            hints.append(
                "Category mention "
                f"'{category_fragment}' is ambiguous across: {', '.join(ambiguous_categories)}."
            )
            should_fuzzy_retry = True

    subcategory_fragment = _extract_first_fragment(question, _SUBCATEGORY_FRAGMENT_PATTERNS)
    if subcategory_fragment:
        resolved_subcategory, ambiguous_subcategories = _resolve_alias(
            subcategory_fragment,
            subcategories,
            min_score=0.55,
        )
        if resolved_subcategory:
            hints.append(
                f"Subcategory mention '{subcategory_fragment}' maps to '{resolved_subcategory}'."
            )
            should_fuzzy_retry = True
        elif ambiguous_subcategories:
            hints.append(
                "Subcategory mention "
                f"'{subcategory_fragment}' is ambiguous across: {', '.join(ambiguous_subcategories)}."
            )
            should_fuzzy_retry = True

    description_phrase = _extract_description_phrase(question)
    if description_phrase:
        hints.append(
            "Description text filter detected: "
            f"'{description_phrase}'. Search across description and merchant_or_item."
        )
        should_fuzzy_retry = True

    return hints, should_fuzzy_retry


def _augment_question_with_context(
    question: str,
    *,
    hints: list[str],
    fuzzy_mode: bool,
) -> str:
    clean_question = question.strip()
    if not hints and not fuzzy_mode:
        return clean_question

    sections = [clean_question]
    if hints:
        hint_lines = "\n".join(f"- {hint}" for hint in hints)
        sections.append(f"Resolved context hints:\n{hint_lines}")
    if fuzzy_mode:
        sections.append(
            "Fallback mode for recall: if strict filters return no rows, relax filters with "
            "LOWER(CAST(column AS TEXT)) LIKE '%term%' for logged_by, category, and subcategory. "
            "For free-text matching, search LOWER(COALESCE(description,'') || ' ' || COALESCE(merchant_or_item,'')) "
            "with LIKE."
        )
    return "\n\n".join(sections)


def _reindex_attempts(attempts: list[SQLAgentAttempt], *, start: int = 0) -> list[SQLAgentAttempt]:
    reindexed: list[SQLAgentAttempt] = []
    for offset, attempt in enumerate(attempts, start=1):
        reindexed.append(
            SQLAgentAttempt(
                attempt_number=start + offset,
                generated_sql=attempt.generated_sql,
                llm_reason=attempt.llm_reason,
                validation_ok=attempt.validation_ok,
                validation_reason=attempt.validation_reason,
                execution_ok=attempt.execution_ok,
                db_error=attempt.db_error,
            )
        )
    return reindexed


def _merge_agent_results(primary: SQLAgentResult, fallback: SQLAgentResult) -> SQLAgentResult:
    use_fallback = (
        (fallback.success and len(fallback.rows) > 0)
        or (not primary.success and fallback.success)
    )
    chosen = fallback if use_fallback else primary
    merged_attempts = _reindex_attempts(primary.attempts)
    merged_attempts.extend(_reindex_attempts(fallback.attempts, start=len(merged_attempts)))
    merged_trace = [*primary.tool_trace, "langgraph_fuzzy_retry", *fallback.tool_trace]
    return SQLAgentResult(
        success=chosen.success,
        final_sql=chosen.final_sql,
        answer=chosen.answer,
        attempts=merged_attempts or chosen.attempts,
        columns=chosen.columns,
        rows=chosen.rows,
        tool_trace=merged_trace,
        failure_reason=chosen.failure_reason,
    )


async def _graph_resolve_context(state: _AnalysisGraphState) -> _AnalysisGraphState:
    question = str(state.get("question") or "").strip()
    session = state.get("session")
    household_id = state.get("household_id")
    if not question or session is None or household_id is None:
        return {
            "context_hints": _EMPTY_HINTS,
            "should_fuzzy_retry": False,
            "resolved_question": question,
            "fallback_question": question,
        }
    hints, should_retry = await _resolve_question_context(
        question=question,
        session=session,
        household_id=household_id,
    )
    return {
        "context_hints": hints,
        "should_fuzzy_retry": should_retry,
        "resolved_question": _augment_question_with_context(
            question,
            hints=hints,
            fuzzy_mode=False,
        ),
        "fallback_question": _augment_question_with_context(
            question,
            hints=hints,
            fuzzy_mode=True,
        ),
    }


async def _graph_run_primary(state: _AnalysisGraphState) -> _AnalysisGraphState:
    runtime = state.get("runtime")
    execute_sql = state.get("execute_sql")
    question = str(state.get("resolved_question") or state.get("question") or "").strip()
    if runtime is None or execute_sql is None:
        raise RuntimeError("LangGraph state is missing runtime or execute_sql.")
    primary_result = await _run_sql_agent_with_executor(
        runtime=runtime,
        question=question,
        execute_sql=execute_sql,
    )
    return {"primary_result": primary_result}


def _graph_should_retry(state: _AnalysisGraphState) -> str:
    primary = state.get("primary_result")
    if primary is None:
        return "use_primary"
    if primary.success and len(primary.rows) > 0:
        return "use_primary"
    if not bool(state.get("should_fuzzy_retry")):
        return "use_primary"
    resolved_question = str(state.get("resolved_question") or "").strip()
    fallback_question = str(state.get("fallback_question") or "").strip()
    if not fallback_question or fallback_question == resolved_question:
        return "use_primary"
    return "retry_with_fuzzy"


def _graph_finalize_primary(state: _AnalysisGraphState) -> _AnalysisGraphState:
    primary = state.get("primary_result")
    if primary is None:
        raise RuntimeError("Primary result missing in LangGraph finalize node.")
    return {"final_result": primary}


async def _graph_run_fallback(state: _AnalysisGraphState) -> _AnalysisGraphState:
    runtime = state.get("runtime")
    execute_sql = state.get("execute_sql")
    fallback_question = str(state.get("fallback_question") or "").strip()
    primary = state.get("primary_result")
    if runtime is None or execute_sql is None or primary is None:
        raise RuntimeError("LangGraph fallback state is incomplete.")
    fallback_result = await _run_sql_agent_with_executor(
        runtime=runtime,
        question=fallback_question,
        execute_sql=execute_sql,
    )
    return {"final_result": _merge_agent_results(primary, fallback_result)}


def _build_analysis_graph() -> StateGraph:
    builder = StateGraph(_AnalysisGraphState)
    builder.add_node("resolve_context", _graph_resolve_context)
    builder.add_node("run_primary", _graph_run_primary)
    builder.add_node("finalize_primary", _graph_finalize_primary)
    builder.add_node("run_fallback", _graph_run_fallback)
    builder.add_edge(START, "resolve_context")
    builder.add_edge("resolve_context", "run_primary")
    builder.add_conditional_edges(
        "run_primary",
        _graph_should_retry,
        {
            "use_primary": "finalize_primary",
            "retry_with_fuzzy": "run_fallback",
        },
    )
    builder.add_edge("finalize_primary", END)
    builder.add_edge("run_fallback", END)
    return builder.compile()


ANALYSIS_LANGGRAPH = _build_analysis_graph()


async def _run_sql_agent_langgraph_with_executor(
    *,
    runtime: LLMRuntimeConfig,
    question: str,
    household_id: UUID,
    session: AsyncSession,
    execute_sql: SQLExecutor,
) -> SQLAgentResult:
    graph_state = await ANALYSIS_LANGGRAPH.ainvoke(
        {
            "question": question,
            "runtime": runtime,
            "execute_sql": execute_sql,
            "household_id": household_id,
            "session": session,
        }
    )
    result = graph_state.get("final_result") or graph_state.get("primary_result")
    if result is None:
        raise RuntimeError("LangGraph analysis pipeline returned no result.")
    return result


async def _run_sql_agent(
    *,
    runtime: LLMRuntimeConfig,
    session: AsyncSession,
    household_id: UUID,
    question: str,
) -> SQLAgentResult:
    async def execute_sql(sql_query: str) -> tuple[list[str], list[list[str | float | int]]]:
        return await _run_sql(session, household_id, sql_query)
    return await _run_sql_agent_langgraph_with_executor(
        runtime=runtime,
        question=question,
        household_id=household_id,
        session=session,
        execute_sql=execute_sql,
    )


def _resolve_cerebras_runtime(runtime: LLMRuntimeConfig) -> tuple[str, str | None]:
    cerebras_model = settings.cerebras_model.strip() or runtime.model
    cerebras_api_key = (
        settings.cerebras_api_key.strip()
        if settings.cerebras_api_key and settings.cerebras_api_key.strip()
        else (runtime.api_key if runtime.provider.value == "cerebras" else None)
    )
    return cerebras_model, cerebras_api_key


async def _run_sql_agent_with_executor(
    *,
    runtime: LLMRuntimeConfig,
    question: str,
    execute_sql: SQLExecutor,
) -> SQLAgentResult:
    cerebras_model, cerebras_api_key = _resolve_cerebras_runtime(runtime)
    async def llm_callback(system_prompt: str, user_prompt: str) -> dict | None:
        return await _llm_json(
            model=cerebras_model,
            api_key=cerebras_api_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    runner = SQLAgentRunner(
        provider_name="cerebras",
        llm_json=llm_callback,
        validate_sql=_safe_sql,
        execute_sql=execute_sql,
        default_answer=_default_answer,
        model=cerebras_model,
        api_key=cerebras_api_key,
    )
    return await runner.run(question, max_attempts=3)


def _to_async_sqlalchemy_url(postgres_url: str) -> str:
    url = postgres_url.strip()
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


async def _run_sql_external_postgres(
    postgres_url: str,
    household_id: UUID,
    sql_query: str,
) -> tuple[list[str], list[list[str | float | int]]]:
    async_url = _to_async_sqlalchemy_url(postgres_url)
    connect_args: dict[str, str] = {}
    lower_url = async_url.lower()
    if "sslmode=" not in lower_url and "ssl=" not in lower_url:
        connect_args["ssl"] = "require"
    engine = create_async_engine(async_url, connect_args=connect_args)
    wrapped = f"{HOUSEHOLD_CTE}\nSELECT * FROM (\n{sql_query}\n) AS agent_result\nLIMIT :result_limit"
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(wrapped),
                {"household_id": str(household_id), "result_limit": 200},
            )
            rows = result.mappings().all()
            if not rows:
                return list(result.keys()), []
            columns = list(rows[0].keys())
            return columns, [[_cell(row.get(column)) for column in columns] for row in rows]
    finally:
        await engine.dispose()


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
    log_model = settings.cerebras_model.strip() or runtime.model
    try:
        query_log = await create_query_log(
            session,
            household_id=user.household_id,
            user_id=user.id,
            provider="cerebras",
            model=log_model,
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

    safe_columns, safe_rows = _sanitize_table(agent_result.columns, agent_result.rows)
    response = AnalysisAskResponse(
        mode="analytics",
        route="agent",
        confidence=0.85 if agent_result.success else 0.35,
        tool="sql_chat_agent",
        tool_trace=agent_result.tool_trace,
        sql=None,
        answer=_finalize_user_answer(
            question=question,
            raw_answer=agent_result.answer,
            columns=safe_columns,
            rows=safe_rows,
            success=agent_result.success,
        ),
        chart=None,
        table=(
            {
                "columns": safe_columns,
                "rows": safe_rows,
            }
            if agent_result.success
            else None
        ),
    )
    return await _finish(
        response,
        status="success" if agent_result.success else "failed",
        failure_reason=agent_result.failure_reason,
        attempt_count=len(agent_result.attempts),
        final_sql=agent_result.final_sql or None,
    )


@router.post("/ask-e2e-postgres", response_model=AnalysisAskResponse)
async def ask_analysis_e2e_postgres(
    payload: AnalysisAskE2EPostgresRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalysisAskResponse:
    runtime = get_env_runtime_config()
    _today_for_timezone(runtime.timezone)
    question = payload.text.strip()
    postgres_url = payload.postgres_url.strip()
    if not postgres_url:
        return AnalysisAskResponse(
            mode="analytics",
            route="agent",
            confidence=0.2,
            tool="sql_chat_agent_e2e_postgres",
            tool_trace=["tool_select"],
            sql=None,
            answer="postgres_url is required.",
            chart=None,
            table=None,
        )

    log_model, _ = _resolve_cerebras_runtime(runtime)
    query_log = None
    try:
        query_log = await create_query_log(
            session,
            household_id=user.household_id,
            user_id=user.id,
            provider="cerebras",
            model=log_model,
            question=question,
            mode="analytics",
            route="agent",
            tool="sql_chat_agent_e2e_postgres",
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

    async def execute_external(sql_query: str) -> tuple[list[str], list[list[str | float | int]]]:
        return await _run_sql_external_postgres(
            postgres_url=postgres_url,
            household_id=user.household_id,
            sql_query=sql_query,
        )

    try:
        agent_result = await _run_sql_agent_langgraph_with_executor(
            runtime=runtime,
            question=question,
            household_id=user.household_id,
            session=session,
            execute_sql=execute_external,
        )
    except Exception as exc:
        response = AnalysisAskResponse(
            mode="analytics",
            route="agent",
            confidence=0.2,
            tool="sql_chat_agent_e2e_postgres",
            tool_trace=["tool_select"],
            sql=None,
            answer=f"SQL agent failed to run: {exc}",
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

    safe_columns, safe_rows = _sanitize_table(agent_result.columns, agent_result.rows)
    response = AnalysisAskResponse(
        mode="analytics",
        route="agent",
        confidence=0.85 if agent_result.success else 0.35,
        tool="sql_chat_agent_e2e_postgres",
        tool_trace=agent_result.tool_trace,
        sql=None,
        answer=_finalize_user_answer(
            question=question,
            raw_answer=agent_result.answer,
            columns=safe_columns,
            rows=safe_rows,
            success=agent_result.success,
        ),
        chart=None,
        table=(
            {
                "columns": safe_columns,
                "rows": safe_rows,
            }
            if agent_result.success
            else None
        ),
    )
    return await _finish(
        response,
        status="success" if agent_result.success else "failed",
        failure_reason=agent_result.failure_reason,
        attempt_count=len(agent_result.attempts),
        final_sql=agent_result.final_sql or None,
    )
