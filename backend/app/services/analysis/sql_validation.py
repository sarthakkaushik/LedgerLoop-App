import re

FORBIDDEN_SQL_TOKENS = (
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "alter ",
    "truncate ",
    "create ",
    "replace ",
    "attach ",
    "detach ",
    "pragma ",
    "vacuum ",
    "reindex ",
    "grant ",
    "revoke ",
    "copy ",
    "execute ",
    "information_schema",
    "sqlite_master",
    "pg_catalog",
)

FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "dblink_connect",
    "dblink_exec",
    "pg_read_file",
    "lo_import",
}


def validate_safe_sql(query: str, *, allowed_tables: set[str]) -> tuple[bool, str]:
    q = query.strip()
    low = q.lower()
    if not q:
        return False, "Empty SQL."
    if ";" in q:
        return False, "Semicolon not allowed."
    if not (low.startswith("select ") or low.startswith("with ")):
        return False, "Only SELECT allowed."
    for token in FORBIDDEN_SQL_TOKENS:
        if token in f"{low} ":
            return False, f"Forbidden token: {token.strip()}."

    ast_ok, ast_reason = _validate_with_sqlglot(q, allowed_tables=allowed_tables)
    if not ast_ok:
        return False, ast_reason

    refs = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w\.]*)", low)
    if any(r not in allowed_tables for r in refs):
        return False, f"Only these tables are allowed: {', '.join(sorted(allowed_tables))}."
    return True, ""


def _validate_with_sqlglot(query: str, *, allowed_tables: set[str]) -> tuple[bool, str]:
    try:
        import sqlglot
        from sqlglot import exp
    except Exception:
        # Fallback to string checks when dependency is not installed yet.
        low = query.lower()
        if low.strip().startswith("select from "):
            return False, "SQL validation failed."
        if not re.search(r"^\s*(select\s+.+\s+from\s+|with\s+.+\s+select\s+.+\s+from\s+)", low, flags=re.DOTALL):
            return False, "SQL validation failed."
        refs = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w\.]*)", low)
        if any(r not in allowed_tables for r in refs):
            return False, "Table validation failed."
        return True, ""

    try:
        tree = sqlglot.parse_one(query, read="postgres")
    except Exception as exc:
        return False, f"SQL parse error: {exc}"

    forbidden_nodes = [
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Command,
    ]
    for node_type in forbidden_nodes:
        if tree.find(node_type) is not None:
            return False, "Only SELECT statements are allowed."

    table_refs = {tbl.name.lower() for tbl in tree.find_all(exp.Table)}
    unknown = sorted(t for t in table_refs if t not in allowed_tables)
    if unknown:
        return False, f"Disallowed table reference: {', '.join(unknown)}."

    select_nodes = list(tree.find_all(exp.Select))
    if not select_nodes:
        return False, "Only SELECT statements are allowed."
    for select_node in select_nodes:
        if not select_node.expressions:
            return False, "SELECT list cannot be empty."

    for fn in tree.find_all(exp.Anonymous):
        name = fn.name.lower() if fn.name else ""
        if name in FORBIDDEN_FUNCTIONS:
            return False, f"Forbidden function: {name}."

    return True, ""
