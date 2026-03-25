"""tdsql-mcp: MCP server for Teradata SQL operations."""

import argparse
import json
import os
import sys
import threading
from importlib import resources
from typing import Any
from urllib.parse import urlparse, parse_qs, unquote

import teradatasql
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "tdsql-mcp",
    instructions=(
        "You are working with a Teradata Vantage database. "
        "IMPORTANT: Always prefer native Teradata table operators over hand-written SQL equivalents. "
        "Teradata Vantage has built-in distributed functions for analytics, ML, data preparation, "
        "text processing, and vector search. These run across all AMPs in parallel and outperform "
        "equivalent hand-written SQL. Do NOT write manual SQL for operations like scaling, encoding, "
        "binning, statistics, clustering, classification, or similarity search when a native function exists. "
        "Before writing any analytics, transformation, or ML SQL: "
        "(1) call get_syntax_help(topic='guidelines') to see the canonical mapping of common operations "
        "to native Teradata functions, "
        "(2) call get_syntax_help(topic='index') to discover all available topics, "
        "(3) load the relevant topic(s) for exact syntax. "
        "Use explain_query to validate syntax before executing. "
        "Use describe_table and list_tables to explore the schema. "
        "Results are returned as JSON."
    ),
)

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_connection: "teradatasql.TeradataConnection | None" = None
_conn_params: dict[str, Any] = {}
_conn_lock = threading.RLock()  # RLock so tools can call helpers without deadlock
_read_only: bool = False


def _reconnect_if_needed() -> "teradatasql.TeradataConnection":
    """Return a live connection. Must be called with _conn_lock held."""
    global _connection
    if _connection is not None:
        try:
            cur = _connection.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _connection
        except Exception:
            try:
                _connection.close()
            except Exception:
                pass
            _connection = None
    _connection = teradatasql.connect(**_conn_params)
    return _connection


def get_connection() -> "teradatasql.TeradataConnection":
    """Return a live connection, reconnecting if necessary."""
    with _conn_lock:
        return _reconnect_if_needed()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_write() -> None:
    if _read_only:
        raise PermissionError("Server is running in read-only mode; write operations are disabled.")


def _execute_query_internal(sql: str, params: list | None = None) -> list[dict]:
    with _conn_lock:
        conn = _reconnect_if_needed()
        cur = conn.cursor()
        try:
            cur.execute(sql, params or [])
            if cur.description is None:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def execute_query(sql: str, max_rows: int = 100) -> str:
    """Execute a SQL SELECT query and return results as JSON.

    Args:
        sql: The SQL query to execute.
        max_rows: Maximum number of rows to return (default 100, capped at 10000).

    Returns:
        JSON object with keys: rows (array), row_count (int), truncated (bool).
    """
    max_rows = min(max(1, max_rows), 10_000)
    with _conn_lock:
        conn = _reconnect_if_needed()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            if cur.description is None:
                return json.dumps({"rows": [], "row_count": 0, "truncated": False})
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchmany(max_rows)
            result = [dict(zip(columns, row)) for row in rows]
            # Peek to detect truncation without fetching everything
            truncated = cur.fetchone() is not None
            return json.dumps(
                {"rows": result, "row_count": len(result), "truncated": truncated},
                default=str,
            )
        finally:
            cur.close()


@mcp.tool()
def execute_statement(sql: str) -> str:
    """Execute a DDL or DML statement (INSERT, UPDATE, DELETE, CREATE, DROP, etc.).

    Not available when the server is running in read-only mode.

    Args:
        sql: The SQL statement to execute.

    Returns:
        JSON object with keys: status (str), rowcount (int).
    """
    _require_write()
    with _conn_lock:
        conn = _reconnect_if_needed()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            return json.dumps({"status": "success", "rowcount": cur.rowcount}, default=str)
        finally:
            cur.close()


@mcp.tool()
def list_databases() -> str:
    """List all accessible databases/schemas in the Teradata system.

    Returns:
        JSON array of objects with keys: DatabaseName, CommentString.
    """
    rows = _execute_query_internal(
        "SELECT DatabaseName, CommentString FROM DBC.DatabasesV ORDER BY DatabaseName"
    )
    return json.dumps(rows, default=str)


@mcp.tool()
def list_tables(database: str) -> str:
    """List tables and views in a given database/schema.

    Args:
        database: The database or schema name to inspect.

    Returns:
        JSON array of objects with keys: TableName, TableKind, CommentString.
        TableKind: T=table, V=view, O=NoPI table, Q=queue table, etc.
    """
    rows = _execute_query_internal(
        "SELECT TableName, TableKind, CommentString "
        "FROM DBC.TablesV "
        "WHERE DatabaseName = ? "
        "ORDER BY TableKind, TableName",
        [database],
    )
    return json.dumps(rows, default=str)


@mcp.tool()
def describe_table(table_name: str, database: str = "") -> str:
    """Describe the columns of a table or view.

    Args:
        table_name: The table or view name.
        database: The database/schema name. Uses the server default if omitted.

    Returns:
        JSON array of column definitions with keys: ColumnName, ColumnType,
        Nullable, ColumnLength, DecimalTotalDigits, DecimalFractionalDigits,
        ColumnFormat, CommentString.
    """
    db = database or _conn_params.get("database", "")
    if not db:
        return json.dumps(
            {"error": "'database' parameter is required when no default database is configured."}
        )
    rows = _execute_query_internal(
        "SELECT ColumnName, ColumnType, Nullable, ColumnLength, "
        "DecimalTotalDigits, DecimalFractionalDigits, ColumnFormat, CommentString "
        "FROM DBC.ColumnsV "
        "WHERE DatabaseName = ? AND TableName = ? "
        "ORDER BY ColumnId",
        [db, table_name],
    )
    return json.dumps(rows, default=str)


@mcp.tool()
def explain_query(sql: str) -> str:
    """Run EXPLAIN on a SQL query to validate syntax and preview the execution plan.

    Use this to check whether a query is syntactically correct before executing it.

    Args:
        sql: The SQL query to explain (do not include the EXPLAIN keyword).

    Returns:
        JSON object with keys: valid (bool), plan (list of step strings) on success,
        or error (str) on failure.
    """
    with _conn_lock:
        conn = _reconnect_if_needed()
        cur = conn.cursor()
        try:
            cur.execute(f"EXPLAIN {sql}")
            steps = [row[0] for row in cur.fetchall()]
            return json.dumps({"valid": True, "plan": steps})
        except Exception as exc:
            return json.dumps({"valid": False, "error": str(exc)})
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Syntax help — file-backed, auto-discovers src/tdsql_mcp/syntax/*.md
# ---------------------------------------------------------------------------

def _syntax_dir():
    """Return a Traversable pointing at the syntax/ package directory."""
    return resources.files("tdsql_mcp") / "syntax"


def _list_topics() -> list[str]:
    """Return sorted list of available topic names (filename without .md)."""
    return sorted(
        f.name[:-3]
        for f in _syntax_dir().iterdir()
        if f.name.endswith(".md")
    )


def _read_topic(topic: str) -> str | None:
    path = _syntax_dir() / f"{topic}.md"
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        return None


@mcp.tool()
def get_syntax_help(topic: str = "index") -> str:
    """Return Teradata SQL syntax reference for a given topic.

    IMPORTANT: Call this tool BEFORE writing any analytics, transformation, ML, or data
    preparation SQL. Teradata Vantage has native distributed table operators for most
    operations — scaling, encoding, binning, statistics, clustering, classification, text
    analytics, vector search, and more. These outperform hand-written SQL and should always
    be preferred. Do not write manual SQL for an operation if a native function exists.

    Recommended call order:
      1. get_syntax_help(topic='guidelines') — see the canonical mapping of common SQL
         patterns to native Teradata functions (start here if unsure what exists)
      2. get_syntax_help(topic='index') — browse all available topics and the Workflows
         section that maps use cases to topic sequences
      3. get_syntax_help(topic='<specific-topic>') — load exact syntax for a topic

    Args:
        topic: The topic name (e.g. 'data-prep', 'ml-functions', 'vector-search').
               Use 'index' to list all available topics.
               Use 'guidelines' for the native-functions-first reference.

    Returns:
        Markdown reference text for the requested topic, or a list of valid topics
        if the requested topic is not found.
    """
    content = _read_topic(topic)
    if content is not None:
        return content
    available = _list_topics()
    return (
        f"Topic '{topic}' not found.\n\n"
        f"Available topics:\n"
        + "\n".join(f"  - {t}" for t in available)
    )


# ---------------------------------------------------------------------------
# Resources — file-backed, same source as get_syntax_help tool
# ---------------------------------------------------------------------------

@mcp.resource("teradata://syntax/{topic}")
def get_syntax_resource(topic: str) -> str:
    """Teradata SQL syntax reference for a given topic. Use 'index' to list all topics."""
    content = _read_topic(topic)
    if content is not None:
        return content
    available = _list_topics()
    return (
        f"Topic '{topic}' not found.\n\n"
        f"Available topics:\n"
        + "\n".join(f"  - {t}" for t in available)
    )


# ---------------------------------------------------------------------------
# URI parsing
# ---------------------------------------------------------------------------

def _parse_uri(uri: str) -> dict[str, Any]:
    """Parse a Teradata connection URI into a teradatasql.connect() kwargs dict.

    URI format:
        teradata://user:password@host[:port][/database][?param=value&...]

    URI components map to teradatasql parameters:
        user     → user
        password → password
        host     → host
        port     → dbs_port  (Teradata default: 1025)
        /path    → database
        ?query   → passed through as-is to teradatasql.connect()

    Any additional teradatasql connection parameter (logmech, encryptdata,
    sslmode, logon_timeout, etc.) can be appended as query-string key=value pairs.
    """
    parsed = urlparse(uri)

    if parsed.scheme.lower() != "teradata":
        raise ValueError(
            f"Invalid URI scheme '{parsed.scheme}'. Must be 'teradata'. "
            f"Expected format: teradata://user:password@host/database?param=value"
        )

    params: dict[str, Any] = {}

    if not parsed.hostname:
        raise ValueError("URI is missing a hostname. Expected: teradata://user:password@host/...")

    params["host"] = parsed.hostname

    if parsed.username:
        params["user"] = unquote(parsed.username)

    if parsed.password:
        params["password"] = unquote(parsed.password)

    if parsed.port:
        params["dbs_port"] = str(parsed.port)

    # Path becomes the default database (strip leading slash)
    if parsed.path and parsed.path.lstrip("/"):
        params["database"] = parsed.path.lstrip("/")

    # All query-string parameters are passed through to teradatasql as-is.
    # Values are always strings, which is correct — teradatasql expects quoted
    # integers and booleans as strings (e.g. logon_timeout="30", encryptdata="true").
    for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
        params[key] = values[0]

    if not params.get("user"):
        raise ValueError("URI is missing a username. Expected: teradata://user:password@host/...")
    if not params.get("password"):
        raise ValueError("URI is missing a password. Expected: teradata://user:password@host/...")

    return params


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _conn_params, _read_only

    # Load .env file if present (no-op if missing)
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="tdsql-mcp: Teradata SQL MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Connection URI format:\n"
            "  teradata://user:password@host[:port][/database][?param=value&...]\n\n"
            "Examples:\n"
            "  teradata://alice:s3cr3t@myhost/mydb\n"
            "  teradata://alice:s3cr3t@myhost:1025/mydb?logmech=LDAP&encryptdata=true\n"
            "  teradata://alice:s3cr3t@myhost/mydb?logon_timeout=30&sslmode=VERIFY-FULL\n\n"
            "Any teradatasql connection parameter can be added as a query-string argument.\n"
            "See: https://github.com/Teradata/python-driver#connection-parameters"
        ),
    )
    parser.add_argument("--read-only", action="store_true", help="Disable all write operations")
    parser.add_argument(
        "--uri",
        metavar="URI",
        help="Teradata connection URI (overrides DATABASE_URI env var)",
    )
    args = parser.parse_args()

    _read_only = args.read_only or os.getenv("TD_READ_ONLY", "").lower() in ("1", "true", "yes")

    raw_uri = args.uri or os.getenv("DATABASE_URI", "")
    if not raw_uri:
        parser.error(
            "A connection URI is required.\n"
            "Set DATABASE_URI env var or pass --uri.\n"
            "Format: teradata://user:password@host/database"
        )

    try:
        _conn_params = _parse_uri(raw_uri)
    except ValueError as exc:
        parser.error(str(exc))

    # Eagerly connect so startup errors surface immediately
    try:
        get_connection()
    except Exception as exc:
        raise SystemExit(f"Failed to connect to Teradata at {_conn_params.get('host')!r}: {exc}") from exc

    mode = "read-only" if _read_only else "read-write"
    print(f"tdsql-mcp started ({mode}) — connected to {_conn_params['host']}", file=sys.stderr, flush=True)

    mcp.run()


if __name__ == "__main__":
    main()
