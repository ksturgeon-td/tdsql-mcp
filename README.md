# tdsql-mcp

An MCP server that provides SQL tools for working with a Teradata database. Designed to work with Claude Desktop, agent frameworks, and any MCP-compatible client.

## Tools

| Tool | Description |
|------|-------------|
| `execute_query` | Run a SELECT query; returns JSON with rows, row count, and truncation flag |
| `execute_statement` | Run DDL/DML (INSERT, UPDATE, CREATE, etc.); disabled in read-only mode |
| `list_databases` | List all accessible databases/schemas |
| `list_tables` | List tables and views in a given database |
| `describe_table` | Get column definitions for a table or view |
| `explain_query` | Validate SQL syntax and preview the execution plan via Teradata EXPLAIN |

## Resources

| URI | Contents |
|-----|----------|
| `teradata://syntax/{topic}` | Teradata SQL syntax reference by topic — use `get_syntax_help("index")` to browse |

## Configuration

Connection is specified as a single URI via the `DATABASE_URI` environment variable or `--uri` CLI flag.

### URI format

```
teradata://user:password@host[:port][/database][?param=value&...]
```

| Part | Required | Description |
|------|----------|-------------|
| `user` | Yes | Database username |
| `password` | Yes | Database password (URL-encode special characters, e.g. `@` → `%40`) |
| `host` | Yes | Teradata server hostname or IP |
| `port` | No | Database port (default: 1025) |
| `/database` | No | Default database/schema |
| `?...` | No | Any additional `teradatasql` connection parameters |

### Environment variables

| Env var | CLI flag | Description |
|---------|----------|-------------|
| `DATABASE_URI` | `--uri` | Teradata connection URI |
| `TD_READ_ONLY` | `--read-only` | Set to `true` to disable write operations |

### Common extra parameters

Any [teradatasql connection parameter](https://github.com/Teradata/python-driver#connection-parameters)
can be appended as a query-string argument:

| Parameter | Example | Description |
|-----------|---------|-------------|
| `logmech` | `logmech=LDAP` | Auth method: TD2 (default), LDAP, KRB5, BROWSER, JWT, etc. |
| `encryptdata` | `encryptdata=true` | Encrypt data in transit |
| `sslmode` | `sslmode=VERIFY-FULL` | TLS: DISABLE, ALLOW, PREFER, REQUIRE, VERIFY-CA, VERIFY-FULL |
| `logon_timeout` | `logon_timeout=30` | Logon timeout in seconds |
| `connect_timeout` | `connect_timeout=5000` | TCP connection timeout in milliseconds |
| `reconnect_count` | `reconnect_count=5` | Max session reconnect attempts |
| `tmode` | `tmode=ANSI` | Transaction mode: DEFAULT, ANSI, TERA |
| `cop` | `cop=false` | Disable COP discovery (useful for single-node dev systems) |

### Multiple parameters example

Parameters are chained with `&` like any URL query string — order does not matter:

```
# LDAP + encryption + full TLS + timeouts
teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&encryptdata=true&sslmode=VERIFY-FULL&logon_timeout=30&connect_timeout=5000

# Default auth + encryption + custom port + session reconnect
teradata://myuser:mypassword@myhost:1025/mydb?encryptdata=true&reconnect_count=5&reconnect_interval=10

# LDAP + ANSI transaction mode + no COP discovery (single-node dev system)
teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&tmode=ANSI&cop=false
```

See [.env.example](.env.example) for more annotated examples.

## Usage

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb"
      }
    }
  }
}
```

With extra parameters (LDAP auth + encryption):

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&encryptdata=true"
      }
    }
  }
}
```

For read-only mode, add `--read-only` to `args`:

```json
"args": ["tdsql-mcp", "--read-only"]
```

### Running directly

```bash
# Install
pip install tdsql-mcp

# Via environment variable
DATABASE_URI="teradata://me:secret@myhost/mydb" tdsql-mcp

# Via CLI flag
tdsql-mcp --uri "teradata://me:secret@myhost/mydb"

# With extra connection parameters
tdsql-mcp --uri "teradata://me:secret@myhost/mydb?logmech=LDAP&sslmode=VERIFY-FULL"

# Read-only
tdsql-mcp --uri "teradata://me:secret@myhost/mydb" --read-only
```

### Install from source (with virtual environment)

```bash
# Clone and enter the project directory
git clone <repo-url>
cd sql_mcp

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install in editable mode (code and syntax file changes take effect immediately)
pip install -e .

# Set up your connection
cp .env.example .env
# Edit .env and fill in your DATABASE_URI

# Run
tdsql-mcp
```

To install from a pinned snapshot instead of resolving fresh:

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

## Result format

`execute_query` returns:

```json
{
  "rows": [{"col1": "val", "col2": 42}, ...],
  "row_count": 100,
  "truncated": true
}
```

`truncated: true` means more rows were available beyond the `max_rows` limit. Increase `max_rows` or add a `TOP N` / `WHERE` clause to your query.

## Notes

- The server establishes a persistent connection on startup and automatically reconnects on failure.
- `execute_query` defaults to `max_rows=100` to keep token usage manageable. Maximum is 10,000.
- Use `explain_query` before running unfamiliar queries — Teradata's EXPLAIN validates syntax and shows the execution plan without actually running the query.
