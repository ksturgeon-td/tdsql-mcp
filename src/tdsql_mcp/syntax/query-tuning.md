# Teradata Query Tuning & EXPLAIN

## EXPLAIN
Validate syntax and preview the execution plan without running the query:
```sql
EXPLAIN SELECT col1, col2 FROM db.table WHERE id = 1;
```
Key things to look for in EXPLAIN output:
- **"No confidence"** — statistics are missing; collect stats on join/filter columns
- **"Low confidence"** — stale or partial stats
- **"We do an all-AMPs"** — full table scan (may be fine or may need an index)
- **"We do a single-AMP"** — efficient PI lookup
- **Product join** — potentially expensive; check join conditions
- **Spool usage** — large intermediate results; consider pushing filters earlier

## Collect Statistics
Missing stats = bad plans. Collect on PI columns, join columns, and WHERE-clause columns:
```sql
COLLECT STATISTICS ON db.table COLUMN (id);
COLLECT STATISTICS ON db.table COLUMN (customer_id, order_date);  -- composite
COLLECT STATISTICS ON db.table INDEX (primary_index_col);
```

## Primary Index (PI) Design Principles
- The PI determines how rows are distributed across AMPs
- Good PI: high cardinality, frequently used in joins/filters
- Bad PI: low cardinality (e.g., boolean, status) → AMP skew
- Check for skew:
```sql
SELECT Hashamp() + 1 AS amp, COUNT(*) AS row_count
FROM db.table
GROUP BY Hashamp()
ORDER BY row_count DESC;
```

## NoPI Tables (Staging / Load)
```sql
CREATE MULTISET TABLE db.staging_table, NO PRIMARY INDEX AS
(SELECT * FROM db.source WHERE 1=0);
```
Use NoPI for temp/staging tables where you don't know the access pattern yet.

## Volatile Tables (Session-Scoped Temp Tables)
```sql
CREATE VOLATILE TABLE tmp_results AS (
    SELECT customer_id, SUM(amount) AS total
    FROM db.orders
    GROUP BY customer_id
) WITH DATA
ON COMMIT PRESERVE ROWS;

-- Use in subsequent queries
SELECT * FROM tmp_results WHERE total > 1000;
```
Volatile tables exist only for the session duration — no cleanup needed.

## Derived Tables vs CTEs
Both are equivalent in Teradata. CTEs are generally more readable:
```sql
-- CTE (preferred for multi-step logic)
WITH base AS (SELECT ... FROM db.t WHERE ...),
     agg  AS (SELECT id, SUM(val) FROM base GROUP BY id)
SELECT * FROM agg;
```

## Filtering Early
Push filters as close to the base table as possible:
```sql
-- Better: filter before join
SELECT a.*, b.name
FROM (SELECT * FROM db.orders WHERE order_date >= CURRENT_DATE - 30) a
JOIN db.customers b ON a.customer_id = b.id;

-- Worse: filter after join
SELECT a.*, b.name
FROM db.orders a JOIN db.customers b ON a.customer_id = b.id
WHERE a.order_date >= CURRENT_DATE - 30;
```

## Avoiding Common Anti-Patterns
```sql
-- Avoid functions on indexed columns in WHERE (prevents PI lookup)
-- Bad:
WHERE EXTRACT(YEAR FROM order_date) = 2024
-- Better:
WHERE order_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31'

-- Avoid implicit type conversions in joins
-- Bad (CHAR vs VARCHAR mismatch):
WHERE char_col = varchar_col
-- Better: explicit CAST
WHERE CAST(char_col AS VARCHAR(50)) = varchar_col

-- Avoid SELECT * in production queries — enumerate needed columns
```

## Session-Level Tuning
```sql
-- Show current session info
SELECT * FROM DBC.SessionInfoV WHERE SessionNo = SESSION;

-- Increase spool space limit for a session (if you have rights)
-- Usually set by DBA at user/profile level
```
