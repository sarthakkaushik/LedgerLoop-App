from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Literal

from app.services.analysis.category_taxonomy import (
    CATEGORY_TAXONOMY,
    MANUAL_ALIASES,
    expand_category_terms,
    normalize_category_token,
    resolve_member_name,
)

CellValue = str | float | int
Rows = list[list[CellValue]]
Cols = list[str]
Intent = Literal[
    "total_spend",
    "category_breakdown",
    "member_breakdown",
    "top_expenses",
    "monthly_trend",
]

NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
NUMBER_TOKEN_REGEX = (
    r"(?:\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)"
)


@dataclass(slots=True)
class BuiltQuery:
    intent: Intent
    tool_name: str
    sql: str
    period_label: str
    top_n: int
    months: int
    resolved_category: str | None
    resolved_member: str | None


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def _shift_months(value: date, delta_months: int) -> date:
    month_index = (value.month - 1) + delta_months
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _last_day_of_month(value: date) -> date:
    return _shift_months(_first_day_of_month(value), 1) - timedelta(days=1)


def _extract_number(pattern: str, text_value: str) -> int | None:
    match = re.search(pattern, text_value.lower())
    if not match:
        return None
    token = str(match.group(1)).strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def _clamp(value: int, min_v: int, max_v: int) -> int:
    return min(max(value, min_v), max_v)


def infer_intent(question: str, explicit_intent: str | None) -> Intent:
    explicit = (explicit_intent or "").strip().lower()
    q = question.lower()
    if explicit in {
        "total_spend",
        "category_breakdown",
        "member_breakdown",
        "top_expenses",
        "monthly_trend",
    }:
        if explicit == "category_breakdown" and (
            "how much" in q or "total" in q or "sum" in q
        ):
            return "total_spend"
        return explicit  # type: ignore[return-value]

    if "how much" in q or "total" in q or "sum" in q:
        return "total_spend"
    if ("top " in q or "largest" in q or "highest" in q or "biggest" in q) and "expense" in q:
        return "top_expenses"
    if "trend" in q or "month over month" in q or "over time" in q:
        return "monthly_trend"
    if any(token in q for token in ("who", "member", "by user", "by person", "spent most")):
        return "member_breakdown"
    if "category" in q or "breakdown" in q:
        return "category_breakdown"
    return "total_spend"


def _resolve_period_bounds(period: str, reference_date: date) -> tuple[date | None, date | None, str]:
    period_key = period.strip().lower()
    if period_key == "today":
        return reference_date, reference_date, "Today"
    if period_key == "yesterday":
        y = reference_date - timedelta(days=1)
        return y, y, "Yesterday"
    if period_key == "this_week":
        start = reference_date - timedelta(days=reference_date.weekday())
        return start, reference_date, "This week"
    if period_key == "last_7_days":
        return reference_date - timedelta(days=6), reference_date, "Last 7 days"
    if period_key == "last_30_days":
        return reference_date - timedelta(days=29), reference_date, "Last 30 days"
    if period_key == "last_60_days":
        return reference_date - timedelta(days=59), reference_date, "Last 60 days"
    if period_key == "last_90_days":
        return reference_date - timedelta(days=89), reference_date, "Last 90 days"
    if period_key == "last_month":
        start = _shift_months(_first_day_of_month(reference_date), -1)
        return start, _last_day_of_month(start), "Last month"
    if period_key == "this_year":
        start = date(reference_date.year, 1, 1)
        return start, reference_date, "This year"
    if period_key == "all_time":
        return None, None, "All time"
    # Default
    start = _first_day_of_month(reference_date)
    return start, _last_day_of_month(reference_date), "This month"


def _infer_period_from_question(question: str, current_period: str) -> str:
    q = question.lower()
    if "today" in q:
        return "today"
    if "yesterday" in q:
        return "yesterday"
    if "this week" in q:
        return "this_week"
    if "this year" in q:
        return "this_year"
    if "all time" in q:
        return "all_time"
    if "last month" in q or "past month" in q:
        return "last_month"
    if "this month" in q:
        return "this_month"

    day_count = _extract_number(rf"(?:last|past)\s+({NUMBER_TOKEN_REGEX})\s+days?", q)
    if day_count is not None:
        if day_count <= 7:
            return "last_7_days"
        if day_count <= 30:
            return "last_30_days"
        if day_count <= 60:
            return "last_60_days"
        return "last_90_days"

    month_count = _extract_number(
        rf"(?:last|past)\s+({NUMBER_TOKEN_REGEX})\s+months?",
        q,
    )
    if month_count is not None:
        if month_count <= 1:
            return "last_month"
        if month_count == 2:
            return "last_60_days"
        if month_count <= 3:
            return "last_90_days"
        return "all_time"

    return current_period


def _infer_category_from_question(question: str, household_categories: list[str]) -> str | None:
    q_norm = normalize_category_token(question)
    if not q_norm:
        return None

    for category in household_categories:
        norm = normalize_category_token(category)
        if norm and (norm in q_norm or q_norm in norm):
            return category

    for canonical, subs in CATEGORY_TAXONOMY.items():
        c_norm = normalize_category_token(canonical)
        if c_norm in q_norm:
            return canonical
        for sub in subs:
            sub_norm = normalize_category_token(sub)
            if sub_norm and sub_norm in q_norm:
                return canonical

    for canonical, aliases in MANUAL_ALIASES.items():
        for alias in aliases:
            alias_norm = normalize_category_token(alias)
            if alias_norm and alias_norm in q_norm:
                return canonical
    return None


def _build_where_clause(
    *,
    question: str,
    period: str,
    status: str,
    category: str | None,
    member: str | None,
    reference_date: date,
    household_categories: list[str],
    household_members: list[str],
) -> tuple[str, str, str | None, str | None]:
    clauses: list[str] = []

    status_key = status.strip().lower()
    if status_key not in {"confirmed", "draft", "all"}:
        status_key = "confirmed"
    if status_key != "all":
        clauses.append(f"LOWER(status) = '{_escape_sql_literal(status_key)}'")

    period_start, period_end, period_label = _resolve_period_bounds(period, reference_date)
    if period_start is not None:
        clauses.append(f"date_incurred >= '{period_start.isoformat()}'")
    if period_end is not None:
        clauses.append(f"date_incurred <= '{period_end.isoformat()}'")

    category_value = category or _infer_category_from_question(question, household_categories)
    resolved_category = category_value.strip() if category_value and category_value.strip() else None
    if resolved_category:
        terms = expand_category_terms(
            resolved_category,
            household_categories=household_categories,
        )
        if terms:
            in_list = ", ".join(f"'{_escape_sql_literal(term)}'" for term in terms)
            clauses.append(
                "LOWER(REPLACE(REPLACE(COALESCE(category,''),' ','_'),'-','_')) "
                f"IN ({in_list})"
            )

    resolved_member = resolve_member_name(
        member,
        household_members=household_members,
    )
    if resolved_member:
        clauses.append(
            f"LOWER(logged_by) = '{_escape_sql_literal(resolved_member.lower())}'"
        )

    where_clause = " AND ".join(clauses) if clauses else "1=1"
    return where_clause, period_label, resolved_category, resolved_member


def build_query(
    *,
    question: str,
    intent: str | None,
    period: str,
    status: str,
    category: str | None,
    member: str | None,
    top_n: int,
    months: int,
    reference_date: date,
    household_categories: list[str],
    household_members: list[str],
) -> BuiltQuery:
    resolved_intent = infer_intent(question, intent)

    extracted_top = _extract_number(rf"top\s+({NUMBER_TOKEN_REGEX})", question)
    final_top_n = _clamp(extracted_top or top_n or 5, 1, 20)

    extracted_months = _extract_number(
        rf"(?:last|past)\s+({NUMBER_TOKEN_REGEX})\s+months?",
        question,
    )
    final_months = _clamp(extracted_months or months or 6, 1, 24)
    effective_period = _infer_period_from_question(question, period)

    where_clause, period_label, resolved_category, resolved_member = _build_where_clause(
        question=question,
        period=effective_period,
        status=status,
        category=category,
        member=member,
        reference_date=reference_date,
        household_categories=household_categories,
        household_members=household_members,
    )

    if resolved_intent == "category_breakdown":
        sql = (
            "SELECT category, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, "
            "COUNT(*) AS expense_count "
            "FROM household_expenses "
            f"WHERE {where_clause} "
            "GROUP BY category "
            "ORDER BY total_spend DESC "
            "LIMIT 50"
        )
        return BuiltQuery(
            intent=resolved_intent,
            tool_name="get_category_breakdown",
            sql=sql,
            period_label=period_label,
            top_n=final_top_n,
            months=final_months,
            resolved_category=resolved_category,
            resolved_member=resolved_member,
        )

    if resolved_intent == "member_breakdown":
        sql = (
            "SELECT logged_by, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, "
            "COUNT(*) AS expense_count "
            "FROM household_expenses "
            f"WHERE {where_clause} "
            "GROUP BY logged_by "
            "ORDER BY total_spend DESC "
            "LIMIT 50"
        )
        return BuiltQuery(
            intent=resolved_intent,
            tool_name="get_member_breakdown",
            sql=sql,
            period_label=period_label,
            top_n=final_top_n,
            months=final_months,
            resolved_category=resolved_category,
            resolved_member=resolved_member,
        )

    if resolved_intent == "top_expenses":
        sql = (
            "SELECT date_incurred, logged_by, category, amount, "
            "COALESCE(description, merchant_or_item, 'Expense') AS note "
            "FROM household_expenses "
            f"WHERE {where_clause} "
            "ORDER BY amount DESC "
            f"LIMIT {final_top_n}"
        )
        return BuiltQuery(
            intent=resolved_intent,
            tool_name="get_top_expenses",
            sql=sql,
            period_label=period_label,
            top_n=final_top_n,
            months=final_months,
            resolved_category=resolved_category,
            resolved_member=resolved_member,
        )

    if resolved_intent == "monthly_trend":
        month_start = _shift_months(_first_day_of_month(reference_date), -(final_months - 1))
        trend_where = f"{where_clause} AND date_incurred >= '{month_start.isoformat()}'"
        sql = (
            "SELECT substr(date_incurred,1,7) AS month, "
            "ROUND(COALESCE(SUM(amount),0),2) AS total_spend "
            "FROM household_expenses "
            f"WHERE {trend_where} "
            "GROUP BY substr(date_incurred,1,7) "
            "ORDER BY month"
        )
        return BuiltQuery(
            intent=resolved_intent,
            tool_name="get_monthly_trend",
            sql=sql,
            period_label=f"Last {final_months} months",
            top_n=final_top_n,
            months=final_months,
            resolved_category=resolved_category,
            resolved_member=resolved_member,
        )

    sql = (
        "SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_spend, "
        "COUNT(*) AS expense_count "
        "FROM household_expenses "
        f"WHERE {where_clause}"
    )
    return BuiltQuery(
        intent="total_spend",
        tool_name="get_total_spend",
        sql=sql,
        period_label=period_label,
        top_n=final_top_n,
        months=final_months,
        resolved_category=resolved_category,
        resolved_member=resolved_member,
    )


def build_answer(query: BuiltQuery, cols: Cols, rows: Rows) -> str:
    if query.intent == "total_spend":
        if not rows:
            return f"No matching expenses found for {query.period_label.lower()}."
        total = float(rows[0][0]) if rows[0] else 0.0
        count = int(rows[0][1]) if len(rows[0]) > 1 else 0
        subject_parts: list[str] = []
        if query.resolved_category:
            subject_parts.append(f"category {query.resolved_category}")
        if query.resolved_member:
            subject_parts.append(f"member {query.resolved_member}")
        subject = f" for {' and '.join(subject_parts)}" if subject_parts else ""
        return (
            f"Total spend for {query.period_label.lower()}{subject} is "
            f"{total:.2f} across {count} expense(s)."
        )

    if query.intent == "category_breakdown":
        if not rows:
            return f"No category expenses found for {query.period_label.lower()}."
        top_category = str(rows[0][0]) if rows[0] else "Unknown"
        top_value = float(rows[0][1]) if len(rows[0]) > 1 else 0.0
        return (
            f"Category breakdown for {query.period_label.lower()} is ready. "
            f"Top category is {top_category} at {top_value:.2f}."
        )

    if query.intent == "member_breakdown":
        if not rows:
            return f"No member expenses found for {query.period_label.lower()}."
        top_member = str(rows[0][0]) if rows[0] else "Unknown"
        top_value = float(rows[0][1]) if len(rows[0]) > 1 else 0.0
        return (
            f"Member breakdown for {query.period_label.lower()} is ready. "
            f"Highest spender is {top_member} at {top_value:.2f}."
        )

    if query.intent == "top_expenses":
        if not rows:
            return f"No expenses found for {query.period_label.lower()}."
        highest = rows[0]
        highest_amount = float(highest[3]) if len(highest) > 3 else 0.0
        return (
            f"Top {len(rows)} expense(s) for {query.period_label.lower()} are listed. "
            f"Highest is {highest_amount:.2f}."
        )

    if query.intent == "monthly_trend":
        if not rows:
            return f"No monthly trend data found for {query.period_label.lower()}."
        peak = max(rows, key=lambda row: float(row[1]) if len(row) > 1 else 0.0)
        peak_month = str(peak[0]) if peak else "n/a"
        peak_value = float(peak[1]) if len(peak) > 1 else 0.0
        return (
            f"Monthly trend for {query.period_label.lower()} is ready. "
            f"Highest month is {peak_month} at {peak_value:.2f}."
        )

    if not rows:
        return "No matching expenses found."
    if len(rows) == 1:
        head = ", ".join(f"{cols[i]}={rows[0][i]}" for i in range(min(3, len(cols))))
        return f"Computed result: {head}."
    return f"Found {len(rows)} row(s) matching your question."
