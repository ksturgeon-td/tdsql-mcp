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

Read all three of the following files now before responding or writing any SQL:

1. [syntax/sql-basics.md](syntax/sql-basics.md) — Teradata SQL fundamentals: reserved word quoting, DDL gotchas, operator differences (MINUS/EXCEPT, <>/!=), QUALIFY, SAMPLE, REPLACE VIEW
2. [syntax/guidelines.md](syntax/guidelines.md) — native function guidelines and operation mapping
3. [syntax/index.md](syntax/index.md) — full topic index and workflow sequences

When you need full syntax for a specific topic (e.g. `uaf-concepts`, `ml-functions`, `data-prep`), read the corresponding file from the `syntax/` directory. The index lists all available topics and their file names.

## Step 3 — Agent Behavior

Apply these principles throughout the session:

**1. Don't assume. Surface uncertainty and tradeoffs.**
If you know a native function exists but haven't loaded its syntax topic, say so — don't write syntax from training knowledge. When multiple approaches fit (exact vs. approximate vector search, ARIMA vs. Holt-Winters, TD_XGBoost vs. TD_GLM), state the tradeoff and let the user decide. If the schema or task is ambiguous, ask before writing SQL.

**2. Minimum SQL that solves the problem. Nothing speculative.**
Don't add columns, CTEs, or transformations that weren't requested. At Teradata scale, unnecessary work has real cost. Load only the syntax topics needed for the current task.

**3. Touch only what you must.**
For `execute_statement` (DDL/DML), modify only what was explicitly requested — don't restructure tables or add columns beyond the task. Clean up volatile tables and intermediate objects you create.

**4. Define success criteria, then verify.**
Before executing non-trivial SQL, use `explain_query` to validate syntax and review the execution plan. After executing, confirm the result shape and row count match expectations. For ML workflows, use evaluation functions (`TD_ClassificationEvaluator`, `TD_RegressionEvaluator`, etc.) to verify model quality — don't declare success before checking metrics.
