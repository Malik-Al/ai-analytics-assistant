"""Load Olist CSV files into the `raw` schema as-is (all columns TEXT)."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("RAW_DATA_DIR", REPO_ROOT / "data" / "raw"))
SCHEMA = "raw"


def table_name_from_file(path: Path) -> str:
    """olist_orders_dataset.csv -> orders"""
    return path.stem.removeprefix("olist_").removesuffix("_dataset").lower()


def read_header(path: Path) -> list[str]:
    # utf-8-sig strips a BOM if the file has one
    with path.open(encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def load_file(conn: psycopg.Connection, path: Path) -> int:
    table = sql.Identifier(SCHEMA, table_name_from_file(path))
    columns = read_header(path)
    col_defs = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in columns)
    col_list = sql.SQL(", ").join(map(sql.Identifier, columns))

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} ({}, _loaded_at timestamptz NOT NULL DEFAULT now())"
            ).format(table, col_defs)
        )
        cur.execute(sql.SQL("TRUNCATE {}").format(table))

        copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
            table, col_list
        )
        with cur.copy(copy_stmt) as copy, path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                copy.write(chunk)

        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(table))
        return cur.fetchone()[0]


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    dsn = (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ['POSTGRES_PORT']} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
    )

    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        print(f"No CSV files in {DATA_DIR}", file=sys.stderr)
        return 1

    # One transaction for all files: either everything loads or nothing changes
    with psycopg.connect(dsn) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for path in files:
            rows = load_file(conn, path)
            print(f"{SCHEMA}.{table_name_from_file(path):<36} {rows:>9,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
