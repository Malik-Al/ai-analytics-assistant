"""Validate LLM-written SQL before it reaches the database."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_SCHEMAS = {"", "marts"}  # "" = unqualified name, resolved via search_path
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Into,  # SELECT ... INTO new_table
)
FORBIDDEN_FUNC_PREFIXES = ("pg_", "lo_", "dblink", "set_config", "current_setting")


class UnsafeSqlError(ValueError):
    """The query is not a single read-only SELECT over the allowed schema."""


def validate_sql(sql: str, allowed_tables: set[str]) -> str:
    """Return the query normalized for Postgres, or raise UnsafeSqlError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeSqlError(f"Cannot parse SQL: {e}") from e

    if len(statements) != 1:
        raise UnsafeSqlError("Exactly one SQL statement is allowed.")
    stmt = statements[0]

    # SELECT, UNION, INTERSECT, EXCEPT (CTEs hang off them) are exp.Query
    if not isinstance(stmt, exp.Query):
        raise UnsafeSqlError("Only SELECT queries are allowed.")

    # catches data-modifying CTEs: WITH d AS (DELETE ... RETURNING *) SELECT ...
    if node := stmt.find(*FORBIDDEN_NODES):
        raise UnsafeSqlError(f"{node.key.upper()} is not allowed.")

    for func in stmt.find_all(exp.Func):
        name = func.name.lower() if isinstance(func, exp.Anonymous) else func.sql_name().lower()
        if name.startswith(FORBIDDEN_FUNC_PREFIXES):
            raise UnsafeSqlError(f"Function {name}() is not allowed.")

    cte_names = {cte.alias_or_name for cte in stmt.find_all(exp.CTE)}
    for table in stmt.find_all(exp.Table):
        if table.name in cte_names and not table.db:
            continue
        # allowlist, not denylist: unqualified pg_user would otherwise resolve to pg_catalog
        if table.catalog or table.db not in ALLOWED_SCHEMAS or table.name not in allowed_tables:
            raise UnsafeSqlError(
                f"Table {table.sql()} is not allowed. Use only: {', '.join(sorted(allowed_tables))}"
            )

    return stmt.sql(dialect="postgres")
