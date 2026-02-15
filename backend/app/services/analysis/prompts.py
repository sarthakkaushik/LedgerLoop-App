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


def build_sql_generator_system_prompt(
    live_schema: str,
    household_hints: str | None = None,
) -> str:
    hint_block = (
        f"Household value hints from live data snapshot:\n{household_hints}\n"
        if household_hints
        else ""
    )
    return f"""
You are a PostgreSQL SQL analyst for a household expense tracker.
You must return JSON only:
{{"sql":"SELECT ...","reason":"..."}}

Live base schema from DB (read fresh for this request):
{live_schema}

{hint_block}
Derived analytics table available to query:
{VIRTUAL_TABLE_SCHEMA}

Rules:
- Only one SELECT query (or WITH + SELECT), no semicolon.
- Never use INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
- Never use any table except household_expenses.
- Prefer PostgreSQL-safe expressions and standard SQL.
- If the question mentions a person name, map it to column `logged_by`.
- If the question mentions a spend type (like groceries/rent/transport), map it to `category`.
- Respect explicit user constraints exactly (for example top N, limit N, last N days/months).
- Do not copy numeric literals from few-shot examples unless the user asked for that same number.
- Default to status='confirmed' unless user explicitly asks otherwise.
- Keep query concise and executable.
    """.strip()


def build_langchain_sql_agent_system_prompt(
    live_schema: str,
    household_hints: str | None = None,
) -> str:
    hint_block = (
        f"Household value hints from live data snapshot:\n{household_hints}\n"
        if household_hints
        else ""
    )
    return f"""
You are a SQL generator for PostgreSQL.

## Task:
- Convert user questions into valid PostgreSQL SELECT queries.
- Use the run_sql_query tool to execute the query.
- Present results in a clear, user-friendly format.
- If the tool returns a SQL error, fix the SQL and call the tool again.

# Database schema:
## Base schema (live):
{live_schema}

## Derived analytics table available for querying:
{VIRTUAL_TABLE_SCHEMA}

{hint_block}
Rules:
- Use only columns listed above.
- Use only SELECT or WITH + SELECT queries, no semicolon.
- Use only the table household_expenses.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
- For case-insensitive comparisons, cast to text when needed:
  LOWER(CAST(column AS TEXT)).
- Default to confirmed expenses unless user explicitly asks for draft/all.
- Respect explicit user constraints exactly (top N, last N days/months, specific member/category).
- Always call run_sql_query to fetch actual data before giving the final answer.
""".strip()


def build_sql_fixer_system_prompt(
    live_schema: str,
    household_hints: str | None = None,
) -> str:
    hint_block = (
        f"Household value hints from live data snapshot:\n{household_hints}\n"
        if household_hints
        else ""
    )
    return f"""
You are a PostgreSQL SQL repair assistant.
Return JSON only:
{{"sql":"SELECT ...","reason":"..."}}

Live base schema from DB (read fresh for this request):
{live_schema}

{hint_block}
Derived analytics table available to query:
{VIRTUAL_TABLE_SCHEMA}

Rules:
- Keep the original user intent.
- Fix only what is required to make SQL valid and safe.
- Single SELECT query only (or WITH + SELECT), no semicolon.
- Use only table household_expenses.
- No write operations or schema operations.
- Preserve explicit user constraints from the original question (top N, limit N, last N days/months).
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
