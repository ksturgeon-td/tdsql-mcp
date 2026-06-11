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

### Other DDL reminders
```sql
-- Teradata uses MINUS, not EXCEPT (already noted in Set Operations above)
-- String concatenation: use || (ANSI) or CONCAT() — not +
-- Semicolons: required in BTEQ; optional in most client tools
```

## Reserved Words as Column Names in Table Operator Clauses

When a column name is a Teradata reserved word (e.g. `type`, `date`, `time`, `value`, `name`, `format`, `title`), it must be double-quoted. In regular SQL projections this looks normal:

```sql
SELECT "type", "date" FROM db.my_table;
```

In table operator string arguments (`ACCUMULATE`, `IDColumn`, `TargetColumns`, `Accumulate`, etc.), the double-quotes must be embedded **inside** the single-quoted string:

```sql
-- WRONG: 'type' is a reserved word — Teradata will reject or misparse this
USING IDColumn('id') Accumulate('type', 'value')

-- RIGHT: double-quote reserved words inside the string literal
USING IDColumn('id') Accumulate('"type"', '"value"')
```

This applies to **any** table operator clause that takes column names as string arguments:

```sql
-- All of these follow the same rule
IDColumn('"type"')
TargetColumns('"value"', '"date"', 'non_reserved_col')
Accumulate('"type"', 'amount', '"date"')
ResponseColumn('"value"')
```

**When in doubt, quote it.** Double-quoting a non-reserved word in a string argument is harmless; leaving a reserved word unquoted will cause a parse error.

Common Teradata reserved words that appear as column names: `type`, `date`, `time`, `timestamp`, `value`, `name`, `format`, `title`, `level`, `mode`, `status`, `class`, `key`, `index`, `year`, `month`, `day`, `hour`, `minute`, `second`.

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
