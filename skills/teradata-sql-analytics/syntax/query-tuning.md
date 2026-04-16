# Teradata Query Tuning & EXPLAIN

## EXPLAIN
Validate syntax and preview the execution plan without running the query:
```sql
EXPLAIN SELECT col1, col2 FROM db.table WHERE id = 1;

-- Dynamic EXPLAIN: better for correlated subqueries, multi-level nesting,
-- or queries where intermediate sizes dramatically change the plan
DYNAMIC EXPLAIN SELECT col1, col2 FROM db.table WHERE id = 1;
```

Use `explain_query` before executing any non-trivial query. If the plan shows critical issues (see below), fix and re-EXPLAIN before running.

### EXPLAIN Phrase Glossary

| Phrase | Optimizer Intent |
|--------|-----------------|
| `single-AMP RETRIEVE by way of the unique primary index` | Best-case tactical access — no spool, no redistribution |
| `by way of an all-rows scan` | Full table scan — examine predicates, stats, and partitioning |
| `redistributed by hash code` | Row movement to co-locate join keys — check skew risk |
| `duplicated on all AMPs` | Broadcast small input to all AMPs — verify it's truly small |
| `(group_amps)` | Spool built on subset of AMPs — potential skew signal |
| `(all_amps)` | Spool built on every AMP — expected for large tables |
| `SORT to order Spool n by row hash` | Preparing for merge/hash join |
| `estimated with no confidence` | Missing statistics — unreliable cardinality estimate |
| `estimated with low confidence` | Partial or stale statistics — conservative planning |
| `estimated with high confidence` | Good statistics — optimizer has reliable estimates |
| `index join confidence` | Optimizer used index stats — reliable |
| `execute the following steps in parallel` | Independent sub-steps dispatched concurrently |
| `RowHash match scan` | Join driven by rowhash ordering |
| `eliminating duplicate rows` | DISTINCT or duplicate removal in spool |
| `hash join` | Standard large-table join — efficient when well-sized |
| `merge join` | Sorted join — efficient when inputs already sorted by join key |
| `product join` | Cartesian join — almost always a problem on large tables |
| `nested join` | Driven by index — efficient for small outer inputs |

### Severity Classification

**Critical — fix before executing:**
- `no confidence` on large tables
- `product join` on large tables (potential Cartesian explosion)
- `all-rows scan` on very large tables (>1M rows) without a clear reason
- Steps consuming >15% of total estimated time
- `(group_amps)` materializing on very few AMPs (severe skew)
- Massive intermediate spool (>1 GB estimated)

**Warning — should investigate:**
- `low confidence` on join or filter columns
- Steps consuming 5–15% of total estimated time
- Large redistributions (>500 MB spool)
- Secondary index scans with large result sets
- Multiple sequential redistributions
- Missing partition elimination on a partitioned table

**Good — plan is efficient:**
- `single-AMP RETRIEVE by way of the unique primary index`
- `high confidence` or `index join confidence` estimates
- `duplicated on all AMPs` on a provably small table
- `execute the following steps in parallel`
- Spool `(Last Use)` markers correctly placed (spool freed promptly)
- Local aggregation (no redistribution needed)

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
