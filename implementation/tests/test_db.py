from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import SQLiteAdapter, ValidationError  # noqa: E402
from init_db import create_database  # noqa: E402


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "school.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_list_tables_and_schema(adapter):
    assert adapter.list_tables() == ["courses", "enrollments", "students"]
    schema = adapter.get_database_schema()
    assert "students" in schema["tables"]
    assert any(column["name"] == "cohort" for column in schema["tables"]["students"]["columns"])


def test_search_with_filters_ordering_and_pagination(adapter):
    result = adapter.search(
        "students",
        columns=["name", "cohort", "age"],
        filters=[{"column": "cohort", "op": "=", "value": "A1"}],
        limit=1,
        offset=0,
        order_by="age",
        descending=True,
    )
    assert result["returned_count"] == 1
    assert result["has_more"] is True
    assert result["rows"][0]["cohort"] == "A1"


def test_insert_returns_inserted_payload(adapter):
    result = adapter.insert(
        "students",
        {"name": "New Student", "cohort": "A1", "email": "new.student@example.edu", "age": 24},
    )
    assert result["inserted"]["id"] >= 1
    assert result["inserted"]["email"] == "new.student@example.edu"


def test_aggregate_count_avg_sum_min_max(adapter):
    count = adapter.aggregate("students", "count")
    assert count["rows"][0]["count_value"] == 6

    avg = adapter.aggregate("enrollments", "avg", "score")
    assert avg["rows"][0]["avg_value"] > 80

    grouped = adapter.aggregate("students", "count", group_by="cohort")
    assert {row["group_value"] for row in grouped["rows"]} == {"A1", "A2", "B1"}

    assert adapter.aggregate("enrollments", "sum", "score")["rows"][0]["sum_value"] > 900
    assert adapter.aggregate("enrollments", "min", "score")["rows"][0]["min_value"] == 69.5
    assert adapter.aggregate("enrollments", "max", "score")["rows"][0]["max_value"] == 95.0


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda a: a.search("missing"), "Unknown table"),
        (lambda a: a.search("students", columns=["missing"]), "Unknown column"),
        (lambda a: a.search("students", filters=[{"column": "name", "op": "regex", "value": ".*"}]), "Unsupported operator"),
        (lambda a: a.insert("students", {}), "non-empty"),
        (lambda a: a.aggregate("students", "median", "age"), "Unsupported aggregate"),
        (lambda a: a.aggregate("students", "avg", "name"), "numeric column"),
        (lambda a: a.search("students", limit=101), "limit"),
    ],
)
def test_invalid_requests_are_rejected(adapter, call, message):
    with pytest.raises(ValidationError, match=message):
        call(adapter)
