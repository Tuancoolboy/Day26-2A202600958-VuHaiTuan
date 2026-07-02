from __future__ import annotations

import os
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "school.db"
MAX_LIMIT = 100
SUPPORTED_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "like", "in"}
SUPPORTED_METRICS = {"count", "avg", "sum", "min", "max"}
NUMERIC_TYPES = {"INTEGER", "REAL", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class DatabaseAdapter(ABC):
    placeholder = "?"

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def list_tables(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_table_schema(self, table: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_database_schema(self) -> dict[str, Any]:
        return {"tables": {table: self.get_table_schema(table) for table in self.list_tables()}}

    def validate_identifier_shape(self, identifier: str, kind: str = "identifier") -> None:
        if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
            raise ValidationError(f"Invalid {kind}: {identifier!r}")

    def quote_identifier(self, identifier: str) -> str:
        self.validate_identifier_shape(identifier)
        return f'"{identifier}"'

    def validate_table(self, table: str) -> None:
        self.validate_identifier_shape(table, "table")
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table}")

    def column_names(self, table: str) -> list[str]:
        return [column["name"] for column in self.get_table_schema(table)["columns"]]

    def column_info(self, table: str, column: str) -> dict[str, Any]:
        for info in self.get_table_schema(table)["columns"]:
            if info["name"] == column:
                return info
        raise ValidationError(f"Unknown column {table}.{column}")

    def validate_column(self, table: str, column: str) -> None:
        self.validate_identifier_shape(column, "column")
        if column not in self.column_names(table):
            raise ValidationError(f"Unknown column {table}.{column}")

    def validate_columns(self, table: str, columns: list[str] | None) -> list[str]:
        if columns is None:
            return self.column_names(table)
        if not columns:
            raise ValidationError("columns must not be empty")
        for column in columns:
            self.validate_column(table, column)
        return columns

    def normalize_limit_offset(self, limit: int, offset: int) -> tuple[int, int]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError) as exc:
            raise ValidationError("limit and offset must be integers") from exc
        if limit < 1 or limit > MAX_LIMIT:
            raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}")
        if offset < 0:
            raise ValidationError("offset must be greater than or equal to 0")
        return limit, offset

    def build_filters(self, table: str, filters: list[dict[str, Any]] | None) -> tuple[str, list[Any]]:
        if filters is None:
            return "", []
        if not isinstance(filters, list):
            raise ValidationError("filters must be a list of filter objects")

        clauses: list[str] = []
        params: list[Any] = []
        for item in filters:
            if not isinstance(item, dict):
                raise ValidationError("each filter must be an object")
            column = item.get("column")
            op = str(item.get("op", "=")).lower()
            value = item.get("value")
            self.validate_column(table, column)
            if op not in SUPPORTED_OPERATORS:
                raise ValidationError(f"Unsupported operator: {op}")
            quoted_column = self.quote_identifier(column)
            if op == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("Operator 'in' requires a non-empty list value")
                placeholders = ", ".join([self.placeholder] * len(value))
                clauses.append(f"{quoted_column} IN ({placeholders})")
                params.extend(value)
            elif op == "like":
                clauses.append(f"{quoted_column} LIKE {self.placeholder}")
                params.append(value)
            else:
                clauses.append(f"{quoted_column} {op} {self.placeholder}")
                params.append(value)

        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    def _is_numeric_column(self, table: str, column: str) -> bool:
        info = self.column_info(table, column)
        declared_type = str(info.get("type", "")).upper()
        return any(token in declared_type for token in NUMERIC_TYPES)

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self.validate_table(table)
        selected_columns = self.validate_columns(table, columns)
        limit, offset = self.normalize_limit_offset(limit, offset)
        where_sql, params = self.build_filters(table, filters)

        order_sql = ""
        if order_by:
            self.validate_column(table, order_by)
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {self.quote_identifier(order_by)} {direction}"

        table_sql = self.quote_identifier(table)
        columns_sql = ", ".join(self.quote_identifier(column) for column in selected_columns)
        sql = f"SELECT {columns_sql} FROM {table_sql}{where_sql}{order_sql} LIMIT {self.placeholder} OFFSET {self.placeholder}"
        rows = self.execute_rows(sql, [*params, limit + 1, offset])
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "table": table,
            "columns": selected_columns,
            "rows": rows,
            "returned_count": len(rows),
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self.validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("insert values must be a non-empty object")
        for column in values:
            self.validate_column(table, column)

        columns = list(values.keys())
        table_sql = self.quote_identifier(table)
        columns_sql = ", ".join(self.quote_identifier(column) for column in columns)
        placeholders = ", ".join([self.placeholder] * len(columns))
        sql = f"INSERT INTO {table_sql} ({columns_sql}) VALUES ({placeholders})"
        inserted_id = self.execute_insert(sql, [values[column] for column in columns])
        payload = dict(values)
        if inserted_id is not None and "id" not in payload:
            payload["id"] = inserted_id
        return {"table": table, "inserted": payload}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        self.validate_table(table)
        metric = str(metric).lower()
        if metric not in SUPPORTED_METRICS:
            raise ValidationError(f"Unsupported aggregate metric: {metric}")

        if metric == "count" and (column is None or column == "*"):
            metric_target = "*"
        else:
            if not column:
                raise ValidationError(f"Metric {metric} requires a column")
            self.validate_column(table, column)
            if metric in {"avg", "sum"} and not self._is_numeric_column(table, column):
                raise ValidationError(f"Metric {metric} requires a numeric column")
            metric_target = self.quote_identifier(column)

        group_sql = ""
        select_group = ""
        if group_by:
            self.validate_column(table, group_by)
            quoted_group = self.quote_identifier(group_by)
            select_group = f"{quoted_group} AS group_value, "
            group_sql = f" GROUP BY {quoted_group} ORDER BY {quoted_group}"

        where_sql, params = self.build_filters(table, filters)
        table_sql = self.quote_identifier(table)
        value_alias = f"{metric}_value"
        sql = f"SELECT {select_group}{metric.upper()}({metric_target}) AS {value_alias} FROM {table_sql}{where_sql}{group_sql}"
        rows = self.execute_rows(sql, params)
        return {"table": table, "metric": metric, "column": column or "*", "group_by": group_by, "rows": rows}

    @abstractmethod
    def execute_rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def execute_insert(self, sql: str, params: list[Any]) -> int | None:
        raise NotImplementedError


class SQLiteAdapter(DatabaseAdapter):
    placeholder = "?"

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise ValidationError(f"SQLite database not found: {self.db_path}. Run implementation/init_db.py first.")
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def list_tables(self) -> list[str]:
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        with self.connect() as connection:
            return [row["name"] for row in connection.execute(sql)]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self.validate_table(table) if table not in getattr(self, "_schema_lookup", set()) else None
        with self.connect() as connection:
            rows = connection.execute(f"PRAGMA table_info({self.quote_identifier(table)})").fetchall()
            foreign_keys = connection.execute(f"PRAGMA foreign_key_list({self.quote_identifier(table)})").fetchall()
        if not rows:
            raise ValidationError(f"Unknown table: {table}")
        return {
            "name": table,
            "columns": [
                {
                    "cid": row["cid"],
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ],
            "foreign_keys": [dict(row) for row in foreign_keys],
        }

    def execute_rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_insert(self, sql: str, params: list[Any]) -> int | None:
        try:
            with self.connect() as connection:
                cursor = connection.execute(sql, params)
                connection.commit()
                return int(cursor.lastrowid) if cursor.lastrowid else None
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"Insert failed: {exc}") from exc


class PostgresAdapter(DatabaseAdapter):
    placeholder = "%s"

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("POSTGRES_DSN")
        if not self.dsn:
            raise ValidationError("POSTGRES_DSN is required when DB_BACKEND=postgres")

    def connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise ValidationError("Install psycopg[binary] to use the PostgreSQL backend") from exc
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def list_tables(self) -> list[str]:
        sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return [row["table_name"] for row in cursor.fetchall()]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self.validate_table(table)
        sql = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [table])
                rows = cursor.fetchall()
        return {
            "name": table,
            "columns": [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "not_null": row["is_nullable"] == "NO",
                    "default": row["column_default"],
                    "primary_key": False,
                }
                for row in rows
            ],
            "foreign_keys": [],
        }

    def execute_rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]

    def execute_insert(self, sql: str, params: list[Any]) -> int | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql + " RETURNING id", params)
                row = cursor.fetchone()
                connection.commit()
                return int(row["id"]) if row and "id" in row else None


def get_adapter() -> DatabaseAdapter:
    backend = os.environ.get("DB_BACKEND", "sqlite").lower()
    if backend == "sqlite":
        return SQLiteAdapter(os.environ.get("SQLITE_DB_PATH", DEFAULT_DB_PATH))
    if backend in {"postgres", "postgresql"}:
        return PostgresAdapter()
    raise ValidationError(f"Unsupported DB_BACKEND: {backend}")
