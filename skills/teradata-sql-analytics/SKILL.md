---
name: teradata-sql-analytics
description: Load at the start of any Teradata analytics session. Injects native function guidelines and syntax.
---

You are working with a Teradata Vantage database.

## Step 1 — Verify database connection

Check whether a Teradata database connection tool is available in this session (e.g. `execute_query`, `execute_statement`, `list_databases`, `list_tables`, `describe_table`, `explain_query`).

- If a connection tool is available: confirm to the user that you have a live database connection and are ready to execute queries.
- If no connection tool is available: inform the user that no database connection was detected. You can still help write and review SQL, but you will not be able to execute queries or inspect the schema. Ask the user to configure a Teradata MCP server if they need live query execution.

## Step 2 — Load syntax reference

Read both of the following files now before responding or writing any SQL:

1. [syntax/guidelines.md](syntax/guidelines.md) — native function guidelines and operation mapping
2. [syntax/index.md](syntax/index.md) — full topic index and workflow sequences

When you need full syntax for a specific topic (e.g. `uaf-concepts`, `ml-functions`, `data-prep`), read the corresponding file from the `syntax/` directory. The index lists all available topics and their file names.
