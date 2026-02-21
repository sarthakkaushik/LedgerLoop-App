from app.api.analysis import (
    _augment_question_with_context,
    _extract_description_phrase,
    _graph_should_retry,
    _resolve_alias,
)
from app.services.analysis.sql_agent import SQLAgentResult


def test_resolve_alias_maps_first_name_to_full_name() -> None:
    resolved, ambiguous = _resolve_alias(
        "pooja",
        ["Pooja Sharma", "Amit Verma"],
        min_score=0.55,
    )
    assert resolved == "Pooja Sharma"
    assert ambiguous == []


def test_resolve_alias_maps_category_fragment() -> None:
    resolved, ambiguous = _resolve_alias(
        "food",
        ["Groceries", "Food & Dining", "Healthcare"],
        min_score=0.5,
    )
    assert resolved == "Food & Dining"
    assert ambiguous == []


def test_extract_description_phrase_from_keywords_or_quotes() -> None:
    from_keyword = _extract_description_phrase(
        "Show me expenses where description contains gym membership"
    )
    from_quote = _extract_description_phrase(
        "How much did we spend for 'uber airport' rides?"
    )
    assert from_keyword == "gym membership"
    assert from_quote == "uber airport"


def test_augment_question_appends_context_and_fallback_mode() -> None:
    augmented = _augment_question_with_context(
        "How much did pooja spend on food?",
        hints=["Person mention 'pooja' maps to household member 'Pooja Sharma'."],
        household_member_names=["Pooja Sharma", "Amit Verma"],
        household_category_names=["Food", "Groceries", "Healthcare"],
        fuzzy_mode=True,
    )
    assert "Known household members" in augmented
    assert "Known household categories" in augmented
    assert "Resolved context hints" in augmented
    assert "Fallback mode for recall" in augmented


def test_graph_retry_path_for_empty_primary_rows() -> None:
    primary = SQLAgentResult(
        success=True,
        final_sql="SELECT * FROM household_expenses WHERE 1=0",
        answer="No rows.",
        attempts=[],
        columns=["amount"],
        rows=[],
        tool_trace=["tool_select"],
    )
    route = _graph_should_retry(
        {
            "primary_result": primary,
            "should_fuzzy_retry": True,
            "resolved_question": "q1",
            "fallback_question": "q2",
        }
    )
    assert route == "retry_with_fuzzy"


def test_graph_retry_path_for_zero_aggregate_primary_rows() -> None:
    primary = SQLAgentResult(
        success=True,
        final_sql="SELECT COALESCE(SUM(amount), 0) AS total_spend FROM household_expenses",
        answer="0",
        attempts=[],
        columns=["total_spend"],
        rows=[[0.0]],
        tool_trace=["tool_select"],
    )
    route = _graph_should_retry(
        {
            "primary_result": primary,
            "should_fuzzy_retry": True,
            "resolved_question": "q1",
            "fallback_question": "q2",
        }
    )
    assert route == "retry_with_fuzzy"
