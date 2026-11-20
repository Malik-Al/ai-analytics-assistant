import pytest

from sql_guard import UnsafeSqlError, validate_sql

TABLES = {"fct_orders", "dim_customers"}


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from fct_orders",
        "select * from marts.fct_orders limit 5;",
        "with t as (select order_id from fct_orders) select count(*) from t",
        "select order_id from fct_orders union select customer_unique_id from dim_customers",
    ],
)
def test_allows_selects_over_marts(sql):
    assert validate_sql(sql, TABLES).upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("delete from fct_orders", "Only SELECT"),
        ("drop table fct_orders", "Only SELECT"),
        ("select 1; drop table fct_orders", "Exactly one"),
        ("with d as (delete from fct_orders returning *) select * from d", "DELETE"),
        ("select * into backup from fct_orders", "INTO"),
        ("select * from raw.orders", "not allowed"),
        ("select * from pg_user", "not allowed"),
        ("select pg_read_file('/etc/passwd')", "pg_read_file"),
        ("select pg_sleep(60)", "pg_sleep"),
    ],
)
def test_rejects_unsafe_sql(sql, reason):
    with pytest.raises(UnsafeSqlError, match=reason):
        validate_sql(sql, TABLES)
