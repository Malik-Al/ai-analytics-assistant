from pathlib import Path

import pytest

from load_raw import read_header, table_name_from_file


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("olist_orders_dataset.csv", "orders"),
        ("olist_order_items_dataset.csv", "order_items"),
        ("product_category_name_translation.csv", "product_category_name_translation"),
    ],
)
def test_table_name_from_file(filename: str, expected: str) -> None:
    assert table_name_from_file(Path(filename)) == expected


def test_read_header_strips_bom(tmp_path: Path) -> None:
    f = tmp_path / "x.csv"
    f.write_bytes("\ufeffa,b\n1,2\n".encode())
    assert read_header(f) == ["a", "b"]
