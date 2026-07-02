from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from init_db import create_database  # noqa: E402


@pytest.fixture(autouse=True)
def sqlite_env(tmp_path, monkeypatch):
    db_path = tmp_path / "school.db"
    create_database(db_path)
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    yield
    os.environ.pop("SQLITE_DB_PATH", None)


def test_tool_functions_return_structured_data():
    import mcp_server

    result = mcp_server.search("students", filters=[{"column": "cohort", "op": "=", "value": "A1"}], limit=2)
    assert result["table"] == "students"
    assert result["returned_count"] == 2

    inserted = mcp_server.insert(
        "students",
        {"name": "Server Test", "cohort": "B1", "email": "server.test@example.edu", "age": 25},
    )
    assert inserted["inserted"]["id"]

    agg = mcp_server.aggregate("enrollments", "avg", "score")
    assert agg["rows"][0]["avg_value"] > 0


def test_resources_return_json_text():
    import json
    import mcp_server

    full_schema = json.loads(mcp_server.database_schema())
    table_schema = json.loads(mcp_server.table_schema("students"))
    assert "students" in full_schema["tables"]
    assert table_schema["name"] == "students"


def test_tool_errors_are_clear():
    import mcp_server

    with pytest.raises(ValueError, match="Unknown table"):
        mcp_server.search("nope")
    with pytest.raises(ValueError, match="Unsupported operator"):
        mcp_server.search("students", filters=[{"column": "name", "op": "regex", "value": ".*"}])
