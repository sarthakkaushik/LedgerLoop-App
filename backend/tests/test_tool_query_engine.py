from datetime import date

from app.services.analysis.tool_query_engine import build_query, infer_intent


def test_infer_intent_prefers_total_for_how_much() -> None:
    intent = infer_intent("How much did I spend on food category this month?", None)
    assert intent == "total_spend"


def test_build_query_expands_food_category_aliases() -> None:
    query = build_query(
        question="How much did I spend on food category this month?",
        intent="auto",
        period="this_month",
        status="confirmed",
        category="food",
        member=None,
        top_n=5,
        months=6,
        reference_date=date(2026, 2, 15),
        household_categories=["Groceries", "Transport", "Food"],
        household_members=["Sarthak Kaushik"],
    )
    assert query.intent == "total_spend"
    assert "LOWER(REPLACE(REPLACE(COALESCE(category,''),' ','_'),'-','_')) IN" in query.sql
    assert "'food'" in query.sql
    assert "'groceries'" in query.sql


def test_build_query_top_expenses_uses_word_numbers() -> None:
    query = build_query(
        question="Show top three expenses in last one month",
        intent="top_expenses",
        period="this_month",
        status="confirmed",
        category=None,
        member=None,
        top_n=5,
        months=6,
        reference_date=date(2026, 2, 15),
        household_categories=[],
        household_members=[],
    )
    assert query.intent == "top_expenses"
    assert "LIMIT 3" in query.sql
    assert "date_incurred >= '2026-01-01'" in query.sql
    assert "date_incurred <= '2026-01-31'" in query.sql


def test_build_query_monthly_trend_respects_word_months() -> None:
    query = build_query(
        question="Show monthly trend for last six months",
        intent="monthly_trend",
        period="this_month",
        status="confirmed",
        category=None,
        member=None,
        top_n=5,
        months=3,
        reference_date=date(2026, 2, 15),
        household_categories=[],
        household_members=[],
    )
    assert query.intent == "monthly_trend"
    assert query.months == 6
    assert "date_incurred >= '2025-09-01'" in query.sql
