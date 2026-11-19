"""Build a small, referentially consistent sample of the Olist dataset for CI.

Takes N random orders and keeps only the rows of other tables that relate to them,
so every foreign key in the sample points to an existing row.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "data" / "raw"
DST_DIR = REPO_ROOT / "data" / "sample"

N_ORDERS = 300
MAX_GEO_ROWS_PER_ZIP = 5
SEED = 42  # fixed seed -> the same sample on every run

Row = dict[str, str]


def read_csv(name: str) -> tuple[list[str], list[Row]]:
    with (SRC_DIR / name).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(name: str, fields: list[str], rows: list[Row]) -> None:
    DST_DIR.mkdir(parents=True, exist_ok=True)
    with (DST_DIR / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name:<45} {len(rows):>6} rows")


def keep(rows: list[Row], column: str, allowed: set[str]) -> list[Row]:
    return [r for r in rows if r[column] in allowed]


def main() -> None:
    random.seed(SEED)

    fields, orders = read_csv("olist_orders_dataset.csv")
    orders = random.sample(orders, N_ORDERS)
    write_csv("olist_orders_dataset.csv", fields, orders)
    order_ids = {o["order_id"] for o in orders}
    customer_ids = {o["customer_id"] for o in orders}

    fields, items = read_csv("olist_order_items_dataset.csv")
    items = keep(items, "order_id", order_ids)
    write_csv("olist_order_items_dataset.csv", fields, items)
    product_ids = {i["product_id"] for i in items}
    seller_ids = {i["seller_id"] for i in items}

    for name in ("olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv"):
        fields, rows = read_csv(name)
        write_csv(name, fields, keep(rows, "order_id", order_ids))

    fields, customers = read_csv("olist_customers_dataset.csv")
    customers = keep(customers, "customer_id", customer_ids)
    write_csv("olist_customers_dataset.csv", fields, customers)

    fields, rows = read_csv("olist_products_dataset.csv")
    write_csv("olist_products_dataset.csv", fields, keep(rows, "product_id", product_ids))

    fields, sellers = read_csv("olist_sellers_dataset.csv")
    sellers = keep(sellers, "seller_id", seller_ids)
    write_csv("olist_sellers_dataset.csv", fields, sellers)

    zips = {c["customer_zip_code_prefix"] for c in customers}
    zips |= {s["seller_zip_code_prefix"] for s in sellers}
    fields, geo = read_csv("olist_geolocation_dataset.csv")
    per_zip: dict[str, int] = defaultdict(int)
    geo_sample = []
    for row in geo:
        zip_code = row["geolocation_zip_code_prefix"]
        if zip_code in zips and per_zip[zip_code] < MAX_GEO_ROWS_PER_ZIP:
            per_zip[zip_code] += 1
            geo_sample.append(row)
    write_csv("olist_geolocation_dataset.csv", fields, geo_sample)

    fields, rows = read_csv("product_category_name_translation.csv")
    write_csv("product_category_name_translation.csv", fields, rows)


if __name__ == "__main__":
    main()
