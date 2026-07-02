# Báo cáo bài tập Day 26: Build a Database MCP Server with FastMCP and SQLite

## 1. Thông tin sinh viên

- Họ và tên: **Vu Hai Tuan**
- MSSV: **2A202600958**
- Repository: <https://github.com/Tuancoolboy/Day26-2A202600958-VuHaiTuan>
- Branch triển khai: `complete-mcp-database-lab`

## 2. Mục tiêu bài tập

Bài tập yêu cầu xây dựng một MCP server sử dụng **FastMCP** để expose một cơ sở dữ liệu nhỏ thông qua các MCP tools và resources. Server phải cho phép MCP client hoặc MCP Inspector gọi các thao tác database một cách có kiểm soát, an toàn và có thể kiểm thử lặp lại.

Các yêu cầu chính gồm:

1. Xây dựng FastMCP server chạy được.
2. Kết nối SQLite database có schema và seed data reproducible.
3. Cung cấp 3 tools bắt buộc:
   - `search`
   - `insert`
   - `aggregate`
4. Cung cấp MCP resources:
   - `schema://database`
   - `schema://table/{table_name}`
5. Validate input và xử lý lỗi rõ ràng.
6. Kiểm thử tool discovery, successful calls và failing calls.
7. Cung cấp hướng dẫn setup, demo và client configuration.
8. Thực hiện bonus gồm shared database adapter, pagination/output limits và HTTP/SSE demo path.

## 3. Có sử dụng LLM API không?

Trong project này, **server không gọi trực tiếp bất kỳ LLM API nào** như Claude API, OpenAI API hay Gemini API.

Project chỉ xây dựng một **MCP server**. MCP server expose tools/resources để client gọi. Nếu dùng Claude Code, Gemini CLI hoặc một MCP client có LLM, thì LLM ở phía client có thể quyết định gọi tool nào. Tuy nhiên phần server do bài này triển khai chỉ thực hiện các bước sau:

1. Nhận structured input từ MCP tool call.
2. Validate table, column, operator, metric và pagination.
3. Thực hiện truy vấn database bằng SQL an toàn.
4. Trả về structured JSON output.

Vì vậy có thể mô tả workflow như sau:

```text
MCP Client / Inspector / LLM-powered client
        |
        | structured tool call
        v
FastMCP Server
        |
        | validate input
        v
Database Adapter
        |
        | parameterized SQL
        v
SQLite Database
        |
        | result rows / metadata
        v
FastMCP Server
        |
        | structured JSON output
        v
MCP Client / User
```

LLM không bắt buộc để test server. Server có thể được kiểm thử trực tiếp bằng `pytest`, `verify_server.py` hoặc MCP Inspector.

## 4. Cấu trúc project

```text
.
├── README.md
├── REPORT.md
├── Rubric.md
├── Tips.md
├── .mcp.json.example
├── implementation/
│   ├── db.py
│   ├── init_db.py
│   ├── mcp_server.py
│   ├── verify_server.py
│   ├── requirements.txt
│   ├── start_inspector.sh
│   ├── data/
│   │   └── school.db
│   └── tests/
│       ├── test_db.py
│       └── test_server.py
└── pseudocode/
    ├── db.py
    ├── init_db.py
    └── mcp_server.py
```

## 5. Database design

Database chính là SQLite database tại:

```text
implementation/data/school.db
```

Database được tạo bằng script:

```bash
python implementation/init_db.py
```

Schema gồm 3 bảng:

### 5.1. `students`

Lưu thông tin sinh viên.

Các cột chính:

- `id`
- `name`
- `cohort`
- `email`
- `age`
- `created_at`

### 5.2. `courses`

Lưu thông tin môn học.

Các cột chính:

- `id`
- `code`
- `title`
- `credits`

### 5.3. `enrollments`

Lưu thông tin đăng ký môn học và điểm số.

Các cột chính:

- `id`
- `student_id`
- `course_id`
- `score`
- `semester`

Bảng này có foreign keys tới `students` và `courses`.

## 6. Các MCP tools đã triển khai

### 6.1. Tool `search`

Mục đích: tìm kiếm rows trong một table với filters, selected columns, ordering và pagination.

Input ví dụ:

```json
{
  "table": "students",
  "columns": ["id", "name", "cohort", "age"],
  "filters": [
    {
      "column": "cohort",
      "op": "=",
      "value": "A1"
    }
  ],
  "limit": 2,
  "offset": 0,
  "order_by": "name",
  "descending": false
}
```

Output ví dụ:

```json
{
  "table": "students",
  "columns": ["id", "name", "cohort", "age"],
  "rows": [
    {
      "id": 1,
      "name": "An Nguyen",
      "cohort": "A1",
      "age": 20
    }
  ],
  "returned_count": 1,
  "limit": 2,
  "offset": 0,
  "has_more": false
}
```

Các operator được hỗ trợ:

```text
=, !=, >, >=, <, <=, like, in
```

### 6.2. Tool `insert`

Mục đích: insert một row mới vào database với column validation.

Input ví dụ:

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

Output ví dụ:

```json
{
  "table": "students",
  "inserted": {
    "name": "Demo Student",
    "cohort": "A1",
    "email": "demo.student@example.edu",
    "age": 24,
    "id": 7
  }
}
```

### 6.3. Tool `aggregate`

Mục đích: tính toán aggregate metrics trên table.

Các metric hỗ trợ:

```text
count, avg, sum, min, max
```

Input ví dụ - count students:

```json
{
  "table": "students",
  "metric": "count"
}
```

Input ví dụ - average score:

```json
{
  "table": "enrollments",
  "metric": "avg",
  "column": "score"
}
```

Input ví dụ - count students by cohort:

```json
{
  "table": "students",
  "metric": "count",
  "group_by": "cohort"
}
```

Output ví dụ:

```json
{
  "table": "students",
  "metric": "count",
  "column": "*",
  "group_by": "cohort",
  "rows": [
    {
      "group_value": "A1",
      "count_value": 2
    },
    {
      "group_value": "A2",
      "count_value": 2
    },
    {
      "group_value": "B1",
      "count_value": 2
    }
  ]
}
```

## 7. MCP resources đã triển khai

### 7.1. Full database schema

URI:

```text
schema://database
```

Resource này trả về JSON mô tả toàn bộ database schema.

### 7.2. Per-table schema

URI template:

```text
schema://table/{table_name}
```

Ví dụ:

```text
schema://table/students
```

Resource này trả về JSON schema cho một bảng cụ thể.

## 8. Validation và safety

Project có class `ValidationError` và validation logic trong `implementation/db.py`.

Các kiểm tra an toàn gồm:

1. Reject table không tồn tại.
2. Reject column không tồn tại.
3. Reject identifier không hợp lệ.
4. Reject operator không được hỗ trợ.
5. Reject empty insert.
6. Reject bad aggregate metric.
7. Reject `avg` hoặc `sum` trên non-numeric column.
8. Validate `limit` từ 1 đến 100.
9. Validate `offset >= 0`.
10. Dùng parameterized SQL cho values.

Project không expose raw SQL tool như `run_sql` để tránh rủi ro `DROP TABLE`, `DELETE FROM`, hoặc SQL injection.

## 9. Bonus đã thực hiện

### 9.1. Shared SQLite/PostgreSQL adapter interface

File `implementation/db.py` có base class:

```text
DatabaseAdapter
```

và implementations:

```text
SQLiteAdapter
PostgresAdapter
```

Backend được chọn qua biến môi trường:

```bash
DB_BACKEND=sqlite
DB_BACKEND=postgres
```

SQLite là backend mặc định. PostgreSQL dùng `POSTGRES_DSN`.

### 9.2. Pagination và output limits

Tool `search` có:

- `limit`
- `offset`
- `has_more`
- `returned_count`

Max limit được giới hạn ở `100` để tránh output quá lớn.

### 9.3. Structured testing

Project có:

```text
implementation/tests/test_db.py
implementation/tests/test_server.py
implementation/verify_server.py
```

### 9.4. HTTP/SSE demo path

Server hỗ trợ cấu hình transport qua CLI/env:

```bash
python implementation/mcp_server.py --transport http --port 8000
```

Có hướng dẫn token auth demo bằng:

```bash
MCP_AUTH_TOKEN=dev-secret
```

Ghi chú: stdio mode là default và phù hợp nhất cho local MCP client. Auth thường áp dụng với HTTP/SSE deployment.

## 10. Cách cài đặt và chạy

### 10.1. Tạo virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 10.2. Cài dependencies

```bash
pip install -r implementation/requirements.txt
```

### 10.3. Khởi tạo database

```bash
python implementation/init_db.py
```

### 10.4. Chạy MCP server

```bash
python implementation/mcp_server.py
```

## 11. Kiểm thử và kết quả verify

Các lệnh kiểm thử đã chạy:

```bash
python implementation/init_db.py
python -m py_compile implementation/*.py
python -m pytest implementation/tests -q
python implementation/verify_server.py
```

Kết quả pytest:

```text
14 passed
```

Kết quả `verify_server.py`:

```text
PASS: database initializes reproducibly
PASS: database schema is readable
PASS: search works with filters, columns, ordering, and pagination
PASS: insert works and returns inserted payload
PASS: aggregate supports count, avg, and group_by
PASS: schema resource data is available for database and per-table views
PASS: invalid table rejected -> clear error: Unknown table: missing_table
PASS: invalid column rejected -> clear error: Unknown column students.password
PASS: unsupported operator rejected -> clear error: Unsupported operator: regex
PASS: bad aggregate rejected -> clear error: Metric avg requires a numeric column
PASS: empty insert rejected -> clear error: insert values must be a non-empty object
PASS: tool functions are discoverable in mcp_server module: search, insert, aggregate
PASS: MCP resource functions return JSON schema text
```

## 12. MCP Inspector demo

Có thể chạy Inspector bằng helper script:

```bash
chmod +x implementation/start_inspector.sh
./implementation/start_inspector.sh
```

Các nội dung cần demo/chụp screenshot:

1. Server connected.
2. Tools xuất hiện: `search`, `insert`, `aggregate`.
3. Resources xuất hiện: `schema://database`, `schema://table/{table_name}`.
4. Gọi `search` thành công.
5. Gọi `insert` thành công.
6. Gọi `aggregate` thành công.
7. Gọi invalid table hoặc invalid operator và thấy clear error.

## 13. MCP client configuration

File `.mcp.json.example` cung cấp cấu hình mẫu cho Claude Code:

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

Sau khi sửa absolute path, MCP client có thể discover tools và resources.

## 14. Mapping với rubric

| Rubric item | Trạng thái |
|---|---|
| FastMCP server starts successfully | Đã triển khai |
| Project structure clean | Đã triển khai |
| SQLite reproducible schema/data | Đã triển khai |
| Server/database logic separated | Đã triển khai |
| `search` with filters/order/pagination | Đã triển khai |
| `insert` returns inserted payload | Đã triển khai |
| `aggregate` count/avg/sum/min/max | Đã triển khai |
| Full schema resource | Đã triển khai |
| Per-table schema resource template | Đã triển khai |
| Invalid table/column rejected | Đã triển khai |
| Unsupported operators/bad aggregates rejected | Đã triển khai |
| Parameterized SQL patterns | Đã triển khai |
| Tool discovery and calls verified | Đã kiểm thử |
| Failing calls verified | Đã kiểm thử |
| Client setup and demo docs | Đã viết trong README |
| Bonus: PostgreSQL shared interface | Đã triển khai |
| Bonus: pagination/output limit/testing polish | Đã triển khai |
| Bonus: HTTP/SSE auth demo path | Đã mô tả và hỗ trợ cấu hình |

## 15. Kết luận

Project đã hoàn thành các yêu cầu chính của bài lab. Server expose đúng các database MCP tools cần thiết, có schema resources, validation an toàn, test tự động và verification script. Project không gọi trực tiếp LLM API; thay vào đó, nó cung cấp MCP interface để MCP clients hoặc LLM-powered clients có thể sử dụng tools theo structured schema.

Các chức năng quan trọng đã được test lại:

- `search`
- `insert`
- `aggregate`
- database schema resources
- invalid request handling
- MCP wrapper functions

Kết quả kiểm thử cuối cùng: **14 tests passed** và **all verification checks passed**.
