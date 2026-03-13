# tdsql-mcp

MCP server providing SQL tools for Teradata (Vantage) databases. Designed for use with Claude Desktop, agent frameworks, and any MCP-compatible client.

## Project Status

**Phase:** Initial build complete, not yet tested against a live database.

## Package

- **Package name:** `tdsql-mcp`
- **Entry point:** `tdsql-mcp` CLI command → `tdsql_mcp.server:main`
- **Python:** 3.10+
- **Key dependencies:** `mcp`, `teradatasql`

## Structure

```
sql_mcp/
├── CLAUDE.md
├── README.md
├── pyproject.toml
└── src/tdsql_mcp/
    ├── __init__.py
    ├── server.py               # All MCP tools, resources, connection logic
    └── syntax/                 # Teradata SQL reference files (auto-discovered)
        ├── index.md            # Topic directory — LLM entry point
        ├── sql-basics.md
        ├── string-functions.md
        ├── numeric-functions.md
        ├── date-time.md
        ├── aggregate-functions.md
        ├── window-functions.md
        ├── conditional.md
        ├── data-types-casting.md
        ├── ml-functions.md
        ├── data-exploration.md
        ├── data-prep.md
        ├── catalog-views.md
        └── query-tuning.md
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `execute_query` | Run SELECT queries; returns JSON with rows, row_count, truncated flag |
| `execute_statement` | Run DDL/DML; disabled in read-only mode |
| `list_databases` | List accessible databases via DBC.DatabasesV |
| `list_tables` | List tables/views in a database via DBC.TablesV |
| `describe_table` | Column definitions via DBC.ColumnsV |
| `explain_query` | Run Teradata EXPLAIN — validates syntax and shows execution plan |
| `get_syntax_help` | Return syntax reference for a topic; use topic="index" to list all |

## MCP Resources

- `teradata://syntax/{topic}` — file-backed, same content as `get_syntax_help`

## Configuration

| Env var | CLI flag | Description |
|---------|----------|-------------|
| `DATABASE_URI` | `--uri` | Teradata connection URI (required) |
| `TD_READ_ONLY` | `--read-only` | Disable write operations |

### URI format
```
teradata://user:password@host[:port][/database][?param=value&...]
```
Any `teradatasql` connection parameter (logmech, encryptdata, sslmode, logon_timeout, etc.)
can be appended as a query-string argument and is passed through to `teradatasql.connect()` as-is.

## Key Design Decisions

- **Single file** (`server.py`) for all server logic — easy to read and distribute.
- **Persistent connection** with automatic reconnect on failure (`threading.RLock` serializes all DB access).
- **Eager connection** on startup — misconfigured credentials fail immediately with a clear error.
- **`execute_query` result limiting** — defaults to 100 rows, max 10,000. Uses `fetchmany` + peek to detect truncation without pulling all rows into memory.
- **`get_syntax_help` auto-discovery** — scans `syntax/*.md` at call time via `importlib.resources`; drop a new file in and it's immediately available, no code changes needed.
- **Read-only mode** — set via env var or CLI flag; `execute_statement` returns a `PermissionError` if called.

## Syntax Reference Library

Files live in `src/tdsql_mcp/syntax/`. To add or update a topic:
1. Create or edit a `.md` file in that directory.
2. Add an entry to `index.md` so the LLM can discover it.
3. No code changes needed — the tool picks it up automatically.

Topics planned but not yet written (add as needed):
- `json-functions.md` — Teradata JSON_* functions
- `geospatial.md` — ST_* geospatial functions
- `temporal-tables.md` — Teradata temporal/bitemporal table syntax
- `user-defined-functions.md` — UDF and UDT usage patterns

## Local Development

```bash
# Install in editable mode (syntax file edits reflect immediately)
pip install -e .

# Run
DATABASE_URI="teradata://me:secret@myhost/mydb" tdsql-mcp

# With extra connection params
DATABASE_URI="teradata://me:secret@myhost/mydb?logmech=LDAP&encryptdata=true" tdsql-mcp

# Read-only
tdsql-mcp --uri "teradata://me:secret@myhost/mydb" --read-only
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://your-user:your-password@your-host/your-default-db"
      }
    }
  }
}
```
