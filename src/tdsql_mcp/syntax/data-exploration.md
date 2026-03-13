# Teradata Data Exploration

## Quick Profile of a Table
```sql
-- Row count
SELECT COUNT(*) FROM db.table;

-- Distinct value counts per column
SELECT
    COUNT(DISTINCT col1) AS col1_ndv,
    COUNT(DISTINCT col2) AS col2_ndv,
    COUNT(*) AS total_rows
FROM db.table;

-- NULL counts
SELECT
    SUM(CASE WHEN col1 IS NULL THEN 1 ELSE 0 END) AS col1_nulls,
    SUM(CASE WHEN col2 IS NULL THEN 1 ELSE 0 END) AS col2_nulls,
    COUNT(*) AS total
FROM db.table;

-- Min, max, avg for numeric columns
SELECT
    MIN(amount) AS min_val,
    MAX(amount) AS max_val,
    AVG(amount) AS avg_val,
    STDDEV_SAMP(amount) AS stddev,
    APPROX_PERCENTILE(amount, 0.25) AS p25,
    APPROX_PERCENTILE(amount, 0.50) AS median,
    APPROX_PERCENTILE(amount, 0.75) AS p75
FROM db.table;
```

## TD_ANALYZE (Teradata Vantage)
Automated column-level statistics:
```sql
-- Profile all columns in a table
SELECT * FROM TD_ANALYZE(
    ON (SELECT * FROM db.table)
    USING
        TargetColumns('col1', 'col2', 'col3')
        StatisticsTypes('BASIC', 'QUANTILE', 'CARDINALITY')
) AS t;

-- BASIC: count, nulls, min, max, mean, stddev
-- QUANTILE: percentiles
-- CARDINALITY: distinct count, most frequent values
```

## Frequency Distribution
```sql
-- Value counts for a categorical column
SELECT col, COUNT(*) AS freq,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM db.table
GROUP BY col
ORDER BY freq DESC;

-- Top 10 most frequent values
SELECT TOP 10 col, COUNT(*) AS freq
FROM db.table
GROUP BY col
ORDER BY freq DESC;
```

## Histogram (Manual Bucketing)
```sql
-- Equal-width histogram with 10 buckets
SELECT bucket,
       MIN(amount) AS bucket_min,
       MAX(amount) AS bucket_max,
       COUNT(*) AS freq
FROM (
    SELECT amount,
           NTILE(10) OVER (ORDER BY amount) AS bucket
    FROM db.table
    WHERE amount IS NOT NULL
) t
GROUP BY bucket
ORDER BY bucket;

-- Fixed-width buckets
SELECT
    FLOOR(amount / 100) * 100 AS bucket_start,
    COUNT(*) AS freq
FROM db.table
GROUP BY 1
ORDER BY 1;
```

## Correlation
```sql
-- Pearson correlation between two columns
SELECT CORR(col1, col2) FROM db.table;

-- Multiple pairs
SELECT
    CORR(x, y) AS corr_xy,
    CORR(x, z) AS corr_xz,
    CORR(y, z) AS corr_yz
FROM db.table;
```

## Sampling for Exploration
```sql
-- Fixed row count
SELECT * FROM db.table SAMPLE 1000;

-- Percentage
SELECT * FROM db.table SAMPLE .01;   -- 1%

-- Repeatable random sample (seed not directly available — use HASH for stability)
SELECT * FROM db.table
WHERE (HASHBUCKET(HASHROW(id)) MOD 100) < 5   -- ~5% stable sample
ORDER BY id
SAMPLE 1000;
```

## Schema Exploration
```sql
-- Tables in a database
SELECT TableName, TableKind, CreateTimeStamp
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
ORDER BY TableName;

-- Column details
SELECT ColumnName, ColumnType, ColumnLength, Nullable, DefaultValue
FROM DBC.ColumnsV
WHERE DatabaseName = 'mydb' AND TableName = 'mytable'
ORDER BY ColumnId;

-- Tables containing a column name
SELECT DatabaseName, TableName, ColumnName
FROM DBC.ColumnsV
WHERE ColumnName LIKE '%customer%'
ORDER BY DatabaseName, TableName;

-- Row counts from system stats (approximate, no full scan)
SELECT DatabaseName, TableName, LastCollectTimeStamp, SumPerm / 1024 / 1024 AS size_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
ORDER BY SumPerm DESC;
```

## Outlier Detection
```sql
-- IQR method: flag outliers beyond 1.5 × IQR
WITH stats AS (
    SELECT
        APPROX_PERCENTILE(amount, 0.25) AS q1,
        APPROX_PERCENTILE(amount, 0.75) AS q3
    FROM db.table
)
SELECT t.*,
       CASE WHEN t.amount < s.q1 - 1.5 * (s.q3 - s.q1)
              OR t.amount > s.q3 + 1.5 * (s.q3 - s.q1)
            THEN 1 ELSE 0 END AS is_outlier
FROM db.table t CROSS JOIN stats s;
```

## Duplicate Detection
```sql
-- Find duplicate rows by key
SELECT key_col, COUNT(*) AS dup_count
FROM db.table
GROUP BY key_col
HAVING COUNT(*) > 1
ORDER BY dup_count DESC;

-- Inspect duplicate records
SELECT * FROM db.table
QUALIFY COUNT(*) OVER (PARTITION BY key_col) > 1
ORDER BY key_col;
```
