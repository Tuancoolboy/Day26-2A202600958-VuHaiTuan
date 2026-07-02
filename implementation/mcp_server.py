from __future__ import annotations

import argparse
import json
import os
from typing import Any

from fastmcp import FastMCP

from db import ValidationError, get_adapter


mcp = FastMCP("SQLite Lab MCP Server")


def _adapter():
    return get_adapter()


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _raise_clear_error(exc: Exception) -> None:
    raise ValueError(str(exc)) from exc


@mcp.tool(name="search")
def search(
    table: str,
    filters: list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows with validated filters, ordering, and pagination."""
    try:
        return _adapter().search(table, columns, filters, limit, offset, order_by, descending)
    except ValidationError as exc:
        _raise_clear_error(exc)


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert one row using validated columns and parameterized SQL."""
    try:
        return _adapter().insert(table, values)
    except ValidationError as exc:
        _raise_clear_error(exc)


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Run count, avg, sum, min, or max with optional filters and grouping."""
    try:
        return _adapter().aggregate(table, metric, column, filters, group_by)
    except ValidationError as exc:
        _raise_clear_error(exc)


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full database schema as JSON text."""
    try:
        return _json(_adapter().get_database_schema())
    except ValidationError as exc:
        _raise_clear_error(exc)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return one table schema as JSON text."""
    try:
        return _json(_adapter().get_table_schema(table_name))
    except ValidationError as exc:
        _raise_clear_error(exc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastMCP database lab server")
    parser.add_argument("--transport", choices=["stdio", "http", "sse"], default=os.environ.get("MCP_TRANSPORT", "stdio"))
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")))
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    auth_token = os.environ.get("MCP_AUTH_TOKEN")
    if auth_token and args.transport == "stdio":
        print("MCP_AUTH_TOKEN is set; auth applies to HTTP/SSE demos, while stdio uses local process trust.")
    if auth_token and args.transport in {"http", "sse"}:
        print("HTTP/SSE auth demo enabled. Use Authorization: Bearer <MCP_AUTH_TOKEN> from clients that support headers.")

    if args.transport == "stdio":
        mcp.run()
    else:
        try:
            mcp.run(transport=args.transport, host=args.host, port=args.port)
        except TypeError:
            mcp.run(transport=args.transport)


if __name__ == "__main__":
    run()
