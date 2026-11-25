"""Guards the dependency rule: the core must not depend on infrastructure or protocols."""

import ast
from pathlib import Path

import pytest

import olist_mcp

PACKAGE_DIR = Path(olist_mcp.__file__).parent
CORE_MODULES = sorted(
    [*(PACKAGE_DIR / "domain").glob("*.py"), PACKAGE_DIR / "ports.py", PACKAGE_DIR / "services.py"]
)
FORBIDDEN = {"psycopg", "psycopg_pool", "openai", "mcp"}


def imported_packages(path: Path) -> set[str]:
    """Top-level package names imported by a module: `from psycopg.rows import x` -> psycopg."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_core_modules_are_found():
    # protects against a vacuous pass if files are moved or renamed
    assert {p.name for p in CORE_MODULES} >= {
        "models.py",
        "sql_guard.py",
        "ports.py",
        "services.py",
    }


@pytest.mark.parametrize("path", CORE_MODULES, ids=lambda p: p.name)
def test_core_does_not_import_infrastructure(path):
    leaked = imported_packages(path) & FORBIDDEN
    assert not leaked, f"{path.name} imports {sorted(leaked)}; core must depend only on ports"
