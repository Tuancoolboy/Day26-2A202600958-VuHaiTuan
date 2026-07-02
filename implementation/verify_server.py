from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from db import SQLiteAdapter, ValidationError  # noqa: E402
from init_db import create_database  # noqa: E402


DB_PATH = ROOT / "data" / "school.db"


def pass_check(name: str) -> None:
    print(f"PASS: {name}")


def expect_validation(name: str, func) -> None:
    try:
        func()
    except (ValidationError, ValueError) as exc:
        print(f"PASS: {name} -> clear error: {exc}")
        return
    raise AssertionError(f"Expected validation failure for {name}")


def main() -> None:
    create_database(DB_PATH)
    pass_check("database initializes reproducibly")

    adapter = SQLiteAdapter(DB_PATH)
    assert set(adapter.list_tables()) == {"students", "courses", "enrollments"}
    pass_check("database schema is readable")

    search_result = adapter.search(
        "students",
        filters=[{"column": "cohort", "op": "=", "value": "A1"}],
        columns=["id", "name", "cohort"],
        limit=2,
        order_by="name",
    )
    assert search_result["returned_count"] == 2
    pass_check("search works with filters, columns, ordering, and pagination")

    insert_result = adapter.insert(
        "students",
        {"name": "Verify Student", "cohort": "A1", "email": "verify.student@example.edu", "age": 26},
    )
    assert insert_result["inserted"]["id"]
    pass_check("insert works and returns inserted payload")

    avg_result = adapter.aggregate("enrollments", "avg", "score")
    grouped_result = adapter.aggregate("students", "count", group_by="cohort")
    assert avg_result["rows"][0]["avg_value"] > 0
    assert len(grouped_result["rows"]) == 3
    pass_check("aggregate supports count, avg, and group_by")

    database_schema = adapter.get_database_schema()
    table_schema = adapter.get_table_schema("students")
    assert "students" in database_schema["tables"]
    assert table_schema["name"] == "students"
    pass_check("schema resource data is available for database and per-table views")

    expect_validation("invalid table rejected", lambda: adapter.search("missing_table"))
    expect_validation("invalid column rejected", lambda: adapter.search("students", columns=["password"]))
    expect_validation(
        "unsupported operator rejected",
        lambda: adapter.search("students", filters=[{"column": "name", "op": "regex", "value": ".*"}]),
    )
    expect_validation("bad aggregate rejected", lambda: adapter.aggregate("students", "avg", "name"))
    expect_validation("empty insert rejected", lambda: adapter.insert("students", {}))

    server = importlib.import_module("mcp_server")
    assert callable(server.search)
    assert callable(server.insert)
    assert callable(server.aggregate)
    pass_check("tool functions are discoverable in mcp_server module: search, insert, aggregate")

    full_schema_json = json.loads(server.database_schema())
    table_schema_json = json.loads(server.table_schema("students"))
    assert "students" in full_schema_json["tables"]
    assert table_schema_json["name"] == "students"
    pass_check("MCP resource functions return JSON schema text")

    print("\nAll verification checks passed. Use MCP Inspector/client to capture final demo screenshots.")


if __name__ == "__main__":
    main()
