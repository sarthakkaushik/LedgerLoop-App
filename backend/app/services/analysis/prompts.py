VIRTUAL_TABLE_SCHEMA = """
household_expenses(
  expense_id text,
  household_id text,
  logged_by_user_id text,
  logged_by text,
  status text,
  category text,
  description text,
  merchant_or_item text,
  amount numeric,
  currency text,
  date_incurred text,
  is_recurring boolean,
  confidence numeric,
  created_at text,
  updated_at text
)
""".strip()

SQL_SUMMARY_SYSTEM_PROMPT = """
Return JSON only:
{"answer":"...","chart_type":"bar|line|none","chart_title":"...","x_key":"...|null","y_key":"...|null"}
Use only provided rows/columns and do not invent values.
Keep answer concise and practical.
"""


FEW_SHOT_EXAMPLES = [
    {
        "question": "How much did we spend this month?",
        "sql": "SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_spend FROM household_expenses WHERE status='confirmed' AND date_incurred >= to_char(date_trunc('month', current_date), 'YYYY-MM-DD')",
    },
    {
        "question": "Show category breakdown for this month",
        "sql": "SELECT category, ROUND(COALESCE(SUM(amount),0),2) AS total_spend, COUNT(*) AS expense_count FROM household_expenses WHERE status='confirmed' AND date_incurred >= to_char(date_trunc('month', current_date), 'YYYY-MM-DD') GROUP BY category ORDER BY total_spend DESC",
    },
    {
        "question": "Who spent the most in last 30 days?",
        "sql": "SELECT logged_by, ROUND(COALESCE(SUM(amount),0),2) AS total_spend FROM household_expenses WHERE status='confirmed' AND date_incurred >= to_char(current_date - interval '30 day', 'YYYY-MM-DD') GROUP BY logged_by ORDER BY total_spend DESC LIMIT 10",
    },
    {
        "question": "Top 5 expenses in last 60 days",
        "sql": "SELECT date_incurred, logged_by, category, amount, COALESCE(description, merchant_or_item, 'Expense') AS note FROM household_expenses WHERE status='confirmed' AND date_incurred >= to_char(current_date - interval '60 day', 'YYYY-MM-DD') ORDER BY amount DESC LIMIT 5",
    },
    {
        "question": "Show monthly trend for last 6 months",
        "sql": "SELECT substr(date_incurred,1,7) AS month, ROUND(COALESCE(SUM(amount),0),2) AS total_spend FROM household_expenses WHERE status='confirmed' AND date_incurred >= to_char(date_trunc('month', current_date) - interval '5 month', 'YYYY-MM-DD') GROUP BY substr(date_incurred,1,7) ORDER BY month",
    },
]


def build_sql_generator_system_prompt(live_schema: str) -> str:
    return f"""
You are a PostgreSQL SQL analyst for a household expense tracker.
You must return JSON only:
{{"sql":"SELECT ...","reason":"..."}}

Live base schema from DB (read fresh for this request):
{live_schema}

Derived analytics table available to query:
{VIRTUAL_TABLE_SCHEMA}

Rules:
- Only one SELECT query (or WITH + SELECT), no semicolon.
- Never use INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
- Never use any table except household_expenses.
- Prefer PostgreSQL-safe expressions and standard SQL.
- Default to status='confirmed' unless user explicitly asks otherwise.
- Keep query concise and executable.
""".strip()


def build_sql_fixer_system_prompt(live_schema: str) -> str:
    return f"""
You are a PostgreSQL SQL repair assistant.
Return JSON only:
{{"sql":"SELECT ...","reason":"..."}}

Live base schema from DB (read fresh for this request):
{live_schema}

Derived analytics table available to query:
{VIRTUAL_TABLE_SCHEMA}

Rules:
- Keep the original user intent.
- Fix only what is required to make SQL valid and safe.
- Single SELECT query only (or WITH + SELECT), no semicolon.
- Use only table household_expenses.
- No write operations or schema operations.
""".strip()


def build_sql_generator_user_prompt(question: str) -> str:
    lines = [f"user_question: {question}", "few_shot_examples:"]
    for idx, ex in enumerate(FEW_SHOT_EXAMPLES, start=1):
        lines.append(f"{idx}. question: {ex['question']}")
        lines.append(f"{idx}. sql: {ex['sql']}")
    return "\n".join(lines)


def build_sql_fixer_user_prompt(question: str, failed_sql: str, db_error: str) -> str:
    return (
        f"user_question: {question}\n"
        f"failed_sql: {failed_sql}\n"
        f"db_error: {db_error}\n"
        "Return corrected SQL in the required JSON format."
    )


def build_sql_summary_user_prompt(
    question: str,
    sql_query: str,
    columns_json: str,
    rows_json: str,
) -> str:
    return (
        f"user_question: {question}\n"
        f"executed_sql: {sql_query}\n"
        f"columns: {columns_json}\n"
        f"rows: {rows_json}"
    )
