from app.services.analysis.sql_validation import validate_safe_sql


def test_validate_safe_sql_allows_simple_select() -> None:
    ok, reason = validate_safe_sql(
        "SELECT category, SUM(amount) FROM household_expenses GROUP BY category",
        allowed_tables={"household_expenses"},
    )
    assert ok is True
    assert reason == ""


def test_validate_safe_sql_blocks_write_statement() -> None:
    ok, _ = validate_safe_sql(
        "DELETE FROM household_expenses",
        allowed_tables={"household_expenses"},
    )
    assert ok is False


def test_validate_safe_sql_blocks_disallowed_table() -> None:
    ok, reason = validate_safe_sql(
        "SELECT * FROM users",
        allowed_tables={"household_expenses"},
    )
    assert ok is False
    assert "allowed" in reason.lower() or "disallowed" in reason.lower()


def test_validate_safe_sql_blocks_invalid_sql() -> None:
    ok, reason = validate_safe_sql(
        "SELECT FROM household_expenses",
        allowed_tables={"household_expenses"},
    )
    assert ok is False
    assert "parse" in reason.lower() or "validation" in reason.lower() or "select list" in reason.lower()
