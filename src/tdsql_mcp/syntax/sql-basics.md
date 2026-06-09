# Teradata SQL Basics

## SELECT Syntax
```sql
SELECT [TOP n] col1, col2, ...
FROM   database.table [AS alias]
[WHERE condition]
[GROUP BY ...]
[HAVING ...]
[ORDER BY ...]
```

## Row Limiting
```sql
-- First N rows (deterministic only with ORDER BY)
SELECT TOP 10 * FROM db.table ORDER BY col;

-- Random sample
SELECT * FROM db.table SAMPLE 100;          -- 100 random rows
SELECT * FROM db.table SAMPLE .05;          -- 5% random sample

-- Paging (use QUALIFY for ranked pagination)
SELECT *, ROW_NUMBER() OVER (ORDER BY id) AS rn FROM db.table
QUALIFY rn BETWEEN 101 AND 200;
```

## QUALIFY Clause
Filters rows based on a window function result — no subquery needed:
```sql
-- Top 3 salaries per department
SELECT dept, name, salary,
       RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk
FROM db.employees
QUALIFY rnk <= 3;

-- Deduplicate: keep most recent row per customer
SELECT *,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY event_ts DESC) AS rn
FROM db.events
QUALIFY rn = 1;
```

## Common Table Expressions (CTEs)
```sql
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC) AS rn
    FROM db.events
),
latest AS (
    SELECT * FROM ranked WHERE rn = 1
)
SELECT * FROM latest WHERE status = 'active';
```

## Joins
```sql
-- Standard ANSI joins (always use these — avoid old-style comma joins)
SELECT a.col, b.col
FROM   db.table_a AS a
INNER JOIN db.table_b AS b ON a.id = b.id;

LEFT  JOIN ...   -- all rows from left, matched from right
RIGHT JOIN ...
FULL OUTER JOIN ...
CROSS JOIN ...   -- cartesian product
```

## Set Operations
```sql
UNION     -- distinct rows
UNION ALL -- all rows (faster)
INTERSECT
MINUS     -- Teradata uses MINUS, not EXCEPT
```

## Subqueries
```sql
-- Inline view
SELECT * FROM (SELECT id, COUNT(*) AS cnt FROM db.t GROUP BY id) AS sub
WHERE cnt > 5;

-- Correlated subquery
SELECT * FROM db.orders o
WHERE amount > (SELECT AVG(amount) FROM db.orders WHERE region = o.region);
```

## DDL — Teradata Syntax (Common Gotchas)

Teradata DDL differs from PostgreSQL/MySQL in several ways. Do not use `CREATE OR REPLACE` — it is not valid Teradata syntax.

### Views
```sql
-- WRONG (PostgreSQL/MySQL syntax — does not work in Teradata)
CREATE OR REPLACE VIEW db.my_view AS SELECT ...;

-- RIGHT: REPLACE VIEW creates or replaces in one statement
REPLACE VIEW db.my_view AS
SELECT col1, col2 FROM db.my_table WHERE condition;

-- Create only (fails if view already exists)
CREATE VIEW db.my_view AS SELECT ...;
```

### Tables
```sql
-- Create a new table
CREATE TABLE db.my_table (
    id       INTEGER NOT NULL,
    name     VARCHAR(100),
    created  TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP(0)
) PRIMARY INDEX (id);

-- Create table from a SELECT (CTAS)
CREATE TABLE db.my_table AS (
    SELECT * FROM db.source_table WHERE condition
) WITH DATA;                     -- WITH DATA copies rows; WITH NO DATA copies schema only

-- CREATE OR REPLACE TABLE does not exist — to replace: DROP then CREATE, or use a staging pattern
```

### CREATE USER — DEFAULT CHARACTER SET

```sql
-- WRONG: CHARACTER SET is not valid at the user level
CREATE USER myuser AS PASSWORD = 'secret' CHARACTER SET UNICODE;

-- RIGHT: the clause is DEFAULT CHARACTER SET
CREATE USER myuser AS
    PASSWORD = 'secret'
    DEFAULT DATABASE = mydb
    DEFAULT CHARACTER SET UNICODE;
```

> **`DEFAULT CHARACTER SET`**, not `CHARACTER SET`, is the correct syntax in `CREATE USER` and `MODIFY USER`. Using `CHARACTER SET` alone will fail.

### Other DDL reminders
```sql
-- Teradata uses MINUS, not EXCEPT (already noted in Set Operations above)
-- String concatenation: use || (ANSI) or CONCAT() — not +
-- Semicolons: required in BTEQ; optional in most client tools
```

## Reserved Words and Identifier Quoting

Quote any identifier (column, table, alias) that conflicts with a reserved word using **double quotes**:

```sql
SELECT id, "type", "format" FROM db.events;

CREATE TABLE db.events (
    id       INTEGER,
    "type"   VARCHAR(30),   -- reserved word — must quote
    label    VARCHAR(100)
) PRIMARY INDEX (id);
```

> **Quoted identifiers are case-sensitive.** Use consistent casing — `"type"` and `"TYPE"` are different identifiers.

### Teradata-Specific Reserved Words — Common Identifier Conflicts

The ANSI SQL reserved words are well-known. The words below are **Teradata-only** — not in the ANSI SQL-99 standard — so agents may not recognize them as reserved. Always quote these when using them as column, table, or alias names.

**Words that frequently appear as column or table names:**

| Reserved word | Commonly appears as | TD since |
|--------------|---------------------|----------|
| `TYPE` | transaction type, event type, record type | V2R3 |
| `FORMAT` | file format, output format, date format | V2R3 |
| `TITLE` | document title; also controls the TD column display header | V2R3 |
| `MODE` | processing mode, run mode, lock mode | V2R3 |
| `ACCOUNT` | account_id, account-related tables | V2R3 |
| `LOG` | log tables, audit logs, log level | V2R3 |
| `LOCK` | lock status, concurrency tables | V2R3 |
| `HASH` | hash keys, checksums, deduplication columns | V2R3 |
| `REQUEST` | request_id, API and service event tables | V2R3 |
| `STATISTICS` | monitoring tables, collected stats columns | V2R3 |
| `JOURNAL` | financial journals, transaction audit logs | V2R3 |
| `CLUSTER` | cluster_id, partition or segment label | V2R3 |
| `NAMED` | TD column alias syntax (`expr (NAMED alias)`) — risky as a column name | V2R3 |
| `RANK` | search rank, priority rank, competition rank | V2R3 |
| `DATABASE` | database name columns in catalog/metadata tables | V2R3 |
| `PERCENT` | percent_change, completion_percent, analytics columns | V2R3 |
| `ENABLED` / `DISABLED` | feature flag columns, configuration status | V2R3 |
| `CLASS` | object class, classification, CSS class | V2R5 |
| `PROFILE` | user profiles, configuration profiles | V2R5 |
| `SUMMARY` | summary text columns, reporting tables | V2R5 |
| `THRESHOLD` | alert thresholds, monitoring limit columns | V2R5 |
| `TRACE` | trace_id, debug or telemetry columns | V2R5 |

**Teradata SQL extension keywords — these are clause keywords, not identifiers:**

| Keyword | Purpose |
|---------|---------|
| `QUALIFY` | Filters window function results — like WHERE for OVER clauses; not in ANSI SQL |
| `SAMPLE` | Random row sampling: `SELECT * FROM t SAMPLE 100` or `SAMPLE .05` |
| `VOLATILE` | Session-scoped temp table: `CREATE VOLATILE TABLE ...` |
| `LOCKING` | Lock modifier: `LOCKING TABLE t FOR ACCESS SELECT ...` |
| `REPLACE` | TD DDL: `REPLACE VIEW` — not `CREATE OR REPLACE` |
| `EXPLAIN` | Execution plan: `EXPLAIN SELECT ...` |
| `FALLBACK` | Table-level data protection option at `CREATE TABLE` time |
| `MULTISET` | Table type allowing duplicate rows: `CREATE MULTISET TABLE ...` |
| `MACRO` | Stored parameterized query: `CREATE MACRO ...` |
| `COLLECT` | Statistics collection: `COLLECT STATISTICS ON db.t COLUMN (col)` |
| `BT` / `ET` | Begin Transaction / End Transaction |
| `SEL` | Shorthand for `SELECT` |
| `DEL` / `INS` / `UPD` | Shorthands for DELETE / INSERT / UPDATE — `DEL` and `INS` can appear as column aliases in CDC/audit schemas |
| `CM` / `CT` / `CD` / `CS` / `CV` / `SS` / `UC` | Additional 2-letter Teradata BTEQ abbreviations — all reserved |

### Reserved Words in Table Operator String Arguments

In table operator clauses that take column names as **string arguments** (`Accumulate`, `IDColumn`, `TargetColumns`, `ResponseColumn`, etc.), double-quotes must be embedded **inside** the single-quoted string:

```sql
-- WRONG: 'type' is a reserved word — Teradata will reject or misparse this
USING IDColumn('id') Accumulate('type', 'value')

-- RIGHT: double-quote reserved words inside the string literal
USING IDColumn('id') Accumulate('"type"', '"value"')
```

This applies to any table operator clause that takes column names as string arguments:

```sql
IDColumn('"type"')
TargetColumns('"value"', '"date"', 'non_reserved_col')
Accumulate('"type"', 'amount', '"date"')
ResponseColumn('"value"')
```

**When in doubt, quote it.** Double-quoting a non-reserved word inside a string argument is harmless; leaving a reserved word unquoted will cause a parse error.

## Teradata Operator Differences

| Operation | Wrong (MySQL/PostgreSQL) | Correct (Teradata) |
|-----------|-------------------------|--------------------|
| Not equal | `!=` | `<>` |
| Set difference | `EXCEPT` | `MINUS` |
| String concat | `+` | `\|\|` or `CONCAT()` |

```sql
-- WRONG
WHERE status != 'active'

-- RIGHT
WHERE status <> 'active'
```

---

## External Data Access — Notation and SQL

### Three-Tier Dot Notation (OTF Tables)

Open Table Format tables (Iceberg, Delta Lake) use three-tier notation: `datalake.database.table`. Database references use two tiers: `datalake.database`.

```sql
-- Query OTF table
SELECT * FROM my_lake.sales_db.orders WHERE order_date >= DATE '2024-01-01';

-- Join OTF table with a relational table
SELECT o.order_id, c.name
FROM my_lake.sales_db.orders o
JOIN mydb.customers c ON o.customer_id = c.customer_id;

-- CTAS from OTF into a relational table
CREATE TABLE mydb.orders_local AS (
    SELECT * FROM my_lake.sales_db.orders
) WITH DATA;

-- Reference OTF database
HELP DATABASE my_lake.sales_db;
```

### HELP Commands — Pass Through as-is

`HELP DATALAKE`, `HELP DATABASE`, and `HELP TABLE` are first-class Teradata statements for OTF and foreign table metadata. Pass them through `execute_query` exactly as written — do NOT rewrite as SELECT queries against DBC views.

```sql
HELP DATALAKE my_lake;                    -- list databases in datalake
HELP DATABASE my_lake.sales_db;           -- list tables in OTF database
HELP TABLE my_lake.sales_db.orders;       -- describe OTF table columns
HELP TABLE mydb.my_foreign_table;         -- describe foreign table columns
```

`describe_table` (which queries `DBC.ColumnsV`) does not work for OTF tables or NOS foreign tables. Always use `HELP TABLE` for schema inspection of these table types.

### READ_NOS — Two Equivalent Calling Forms

You may encounter READ_NOS written in two forms — both are valid and produce identical results:

```sql
-- Explicit form — generate this when writing new SQL
SELECT * FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/bucket/path/')
    AUTHORIZATION (my_auth)
    RETURNTYPE ('NOSREAD_KEYS')
) AS d;

-- Implicit shorthand — valid syntax you may see in existing code; do not "fix" it
SELECT * FROM (
  LOCATION='/S3/s3.amazonaws.com/bucket/path/'
  AUTHORIZATION=my_auth
  RETURNTYPE='NOSREAD_KEYS'
) AS d;
```

Always generate the explicit `READ_NOS(USING(...))` form when writing new SQL.
