# Lab: Build a Database MCP Server with FastMCP and SQLite

This repository contains a complete FastMCP database server implementation for the Day 26 MCP lab. It exposes a small school database through MCP tools and resources, includes validation/error handling, and provides repeatable tests plus client demo instructions.

## Feature checklist

- FastMCP server starts over stdio by default.
- SQLite database initializes with reproducible schema and seed data.
- Clean separation between database logic and MCP server logic.
- Tools:
  - `search` with filters, ordering, column selection, limit, offset, and `has_more` pagination metadata.
  - `insert` with safe column validation and inserted payload return.
  - `aggregate` with `count`, `avg`, `sum`, `min`, `max`, filters, and `group_by`.
- Resources:
  - `schema://database`
  - `schema://table/{table_name}`
- Safety:
  - rejects unknown tables and columns.
  - rejects unsupported operators.
  - rejects bad aggregate requests and empty inserts.
  - uses parameterized values; identifiers are validated before quoting.
- Bonus:
  - SQLite and PostgreSQL share the same adapter interface (`DB_BACKEND=sqlite|postgres`).
  - HTTP/SSE transport demo path with bearer-token instructions.
  - pagination/output limits and structured verification.

## Project structure

```text
implementation/
  db.py                 # DatabaseAdapter, SQLiteAdapter, PostgresAdapter, validation, safe SQL
  init_db.py            # Reproducible SQLite schema and seed data
  mcp_server.py         # FastMCP tools, resources, transports
  verify_server.py      # Repeatable function-level verification checklist
  requirements.txt      # Python dependencies
  start_inspector.sh    # MCP Inspector helper
implementation/tests/
  test_db.py            # Adapter and validation tests
  test_server.py        # MCP wrapper/resource tests
.mcp.json.example       # Claude Code MCP config example
```

> Note: the original `pseudocode/` directory is kept as assignment reference. The working code is in `implementation/`.

## Setup

```bash
cd /ABSOLUTE/PATH/TO/Day26-2A202600958-VuHaiTuan
python -m venv .venv
source .venv/bin/activate
pip install -r implementation/requirements.txt
python implementation/init_db.py
```

Expected output:

```text
SQLite database initialized at .../implementation/data/school.db
```

## Run the MCP server

Default stdio mode:

```bash
python implementation/mcp_server.py
```

HTTP/SSE demo mode:

```bash
MCP_TRANSPORT=http MCP_PORT=8000 python implementation/mcp_server.py --transport http --port 8000
```

Bearer-token demo for HTTP/SSE clients that support custom headers:

```bash
MCP_AUTH_TOKEN=dev-secret MCP_TRANSPORT=http python implementation/mcp_server.py --transport http --port 8000
```

Use this header from the client:

```text
Authorization: Bearer dev-secret
```

For stdio, authentication is normally handled by local process trust and client configuration.

## Tool reference and demo calls

### `search`

Search rows with safe filters, selected columns, ordering, and pagination.

Example: search all students in cohort `A1`:

```json
{
  "table": "students",
  "columns": ["id", "name", "cohort", "age"],
  "filters": [{"column": "cohort", "op": "=", "value": "A1"}],
  "limit": 10,
  "offset": 0,
  "order_by": "name",
  "descending": false
}
```

### `insert`

Insert one row and return the inserted payload including generated id.

```json
{
  "table": "students",
  "values": {
    "name": "Demo Student",
    "cohort": "A1",
    "email": "demo.student@example.edu",
    "age": 24
  }
}
```

### `aggregate`

Count rows:

```json
{
  "table": "students",
  "metric": "count"
}
```

Average enrollment score:

```json
{
  "table": "enrollments",
  "metric": "avg",
  "column": "score"
}
```

Count students by cohort:

```json
{
  "table": "students",
  "metric": "count",
  "group_by": "cohort"
}
```

Supported metrics: `count`, `avg`, `sum`, `min`, `max`.

Supported filter operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`.

## Resource reference

Read the full schema:

```text
schema://database
```

Read a single table schema:

```text
schema://table/students
```

## Verification: retest all functions before submission

Run these commands after every important change:

```bash
python implementation/init_db.py
python -m py_compile implementation/*.py
python -m pytest implementation/tests -q
python implementation/verify_server.py
```

`verify_server.py` checks:

- database initialization.
- schema readability.
- valid `search`, `insert`, and `aggregate` function calls.
- invalid calls fail with clear errors.
- MCP wrapper functions are present.
- schema resources return JSON text.

Invalid-call examples to demonstrate in Inspector/client:

```json
{"table": "missing_table"}
```

```json
{"table": "students", "columns": ["password"]}
```

```json
{
  "table": "students",
  "filters": [{"column": "name", "op": "regex", "value": ".*"}]
}
```

```json
{"table": "students", "metric": "avg", "column": "name"}
```

```json
{"table": "students", "values": {}}
```

Each should return a clear error such as `Unknown table`, `Unknown column`, `Unsupported operator`, `numeric column`, or `non-empty object`.

## MCP Inspector demo

```bash
chmod +x implementation/start_inspector.sh
./implementation/start_inspector.sh
```

In Inspector, capture screenshots showing:

1. server connects successfully.
2. tools list includes `search`, `insert`, `aggregate`.
3. resources include `schema://database` and `schema://table/{table_name}`.
4. one successful `search` call.
5. one successful `insert` call.
6. one successful `aggregate` call.
7. one failing call with a clear validation error.

Suggested screenshot paths:

```text
docs/screenshots/inspector-tools.png
docs/screenshots/search-success.png
docs/screenshots/aggregate-success.png
docs/screenshots/error-invalid-table.png
```

## Claude Code client configuration

Copy `.mcp.json.example` to `.mcp.json` and replace absolute paths:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/Day26-2A202600958-VuHaiTuan/implementation/mcp_server.py"],
      "env": {
        "DB_BACKEND": "sqlite",
        "SQLITE_DB_PATH": "/ABSOLUTE/PATH/TO/Day26-2A202600958-VuHaiTuan/implementation/data/school.db"
      }
    }
  }
}
```

Then ask Claude Code:

```text
Use the sqlite-lab MCP server. Read schema://database, then search the top 2 A1 students ordered by name.
```

## Gemini CLI client option

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/Day26-2A202600958-VuHaiTuan/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server and show me students in cohort A1."
```

## PostgreSQL bonus path

The server uses a shared `DatabaseAdapter` interface. SQLite is the default backend; PostgreSQL can be selected with:

```bash
DB_BACKEND=postgres POSTGRES_DSN="postgresql://user:password@localhost:5432/school" python implementation/mcp_server.py
```

The PostgreSQL backend expects compatible public tables (`students`, `courses`, `enrollments`) and uses the same MCP tool/resource surface.

## 2-minute demo script

1. Show `python implementation/init_db.py` creating the database.
2. Show `python implementation/verify_server.py` passing.
3. Open Inspector and show the 3 tools.
4. Read `schema://database` and `schema://table/students`.
5. Run `search` for cohort `A1`.
6. Run `insert` for a new student.
7. Run `aggregate` average `score` from `enrollments`.
8. Run an invalid table or invalid operator call and show the clear error.
9. Show `.mcp.json.example` or configured client connection.
10. Mention bonus: shared SQLite/PostgreSQL adapter and HTTP/SSE bearer-token demo path.
