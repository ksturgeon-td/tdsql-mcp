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
    STDDEV_SAMP(amount) AS stddev
FROM db.table;
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

## MovingAverage
```sql
-- Simple moving average (most common)
SELECT * FROM MovingAverage(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY partition_col
    ORDER BY date_col
    USING
        MAvgType('S')
        TargetColumns('amount')
        WindowSize(3)
) AS t;

-- Exponential moving average (with optional tuning)
SELECT * FROM MovingAverage(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY partition_col
    ORDER BY date_col
    USING
        MAvgType('E')
        TargetColumns('amount')
        Alpha(0.2)
        StartRows(2)
        IncludeFirst('true')
) AS t;

-- MAvgType options:
--   'C' = Cumulative (default)
--   'E' = Exponential  (uses Alpha, StartRows, IncludeFirst)
--   'M' = Modified     (uses WindowSize, IncludeFirst)
--   'S' = Simple       (uses WindowSize, IncludeFirst)
--   'T' = Triangular   (uses WindowSize, IncludeFirst)
--   'W' = Weighted     (uses WindowSize, IncludeFirst)
```

## TD_CategoricalSummary
```sql
SELECT * FROM TD_CategoricalSummary(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('cat_col1', 'cat_col2')         -- explicit columns
        -- or: TargetColumns('[1:5]')                 -- column range by position
) AS t;
```

## TD_ColumnSummary
```sql
SELECT * FROM TD_ColumnSummary(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns
        -- or: TargetColumns('[1:5]')                 -- column range by position
) AS t;
```

## TD_GetRowsWithMissingValues
```sql
SELECT * FROM TD_GetRowsWithMissingValues(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY id_col
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns
        -- or: TargetColumns('[1:5]')                 -- column range by position
        -- Accumulate('id_col', 'date_col')           -- optional: columns to pass through to output
) AS t;
```

## TD_Histogram
```sql
-- Auto-binning (Sturges or Scott method)
SELECT * FROM TD_Histogram(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        MethodType('Sturges')                         -- or 'Scott'
        TargetColumn('amount')
        GroupbyColumns('region')                      -- optional: histogram per group
) AS t;

-- Equal-width bins with explicit count (multiple target columns)
SELECT * FROM TD_Histogram(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.minmax_table | db.view | (query) } AS MinMax DIMENSION
    USING
        MethodType('Equal-Width')
        TargetColumn('amount', 'price')
        NBins(10, 20)                                 -- one per target column
        Inclusion('left', 'right')                    -- one per target column: 'left' or 'right'
        GroupbyColumns('region')                      -- optional
) AS t;

-- Variable-width bins (bin boundaries defined in MinMax table)
SELECT * FROM TD_Histogram(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.minmax_table | db.view | (query) } AS MinMax DIMENSION
    USING
        MethodType('Variable-Width')
        TargetColumn('amount')
) AS t;

-- MinMax table schema for Equal-Width:    (ColumnName, MinValue, MaxValue)
-- MinMax table schema for Variable-Width: (ColumnName, MinValue, MaxValue, Label)
```

## TD_QQNorm
Checks whether a column follows a normal distribution by comparing its quantiles to theoretical
normal quantiles. Requires pre-computed rank columns — use RANK() or ROW_NUMBER() in a subquery.
```sql
-- Step 1: pre-compute ranks
WITH ranked AS (
    SELECT amount,
           RANK() OVER (ORDER BY amount) AS amount_rank
    FROM db.table
    WHERE amount IS NOT NULL
)
-- Step 2: pass ranked data to TD_QQNorm
SELECT * FROM TD_QQNorm(
    ON ranked AS InputTable
    PARTITION BY ANY
    ORDER BY amount_rank
    USING
        TargetColumns('amount')
        RankColumns('amount_rank')
        -- OutputColumns('amount_theoretical_q')      -- optional: default is amount_theoretical_quantiles
        -- Accumulate('id_col')                       -- optional: columns to pass through to output
) AS t;
```

## TD_UnivariateStatistics
```sql
-- Default: computes all statistics
SELECT * FROM TD_UnivariateStatistics(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns or range
        PartitionColumns('group_col')                 -- optional: stats per group
) AS t;

-- Selective statistics with optional tuning
SELECT * FROM TD_UnivariateStatistics(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    USING
        TargetColumns('col1', 'col2')
        PartitionColumns('group_col')                 -- optional: stats per group
        Stats('MEAN', 'STD', 'MEDIAN', 'IQR',
              'PERCENTILES', 'SKEWNESS', 'KURTOSIS')  -- default: 'ALL'
        Centiles(10, 25, 50, 75, 90)                  -- optional: used with PERCENTILES or ALL
                                                      -- default: 1,5,10,25,50,75,90,95,99
        TrimPercentile(20)                            -- optional: used with TRIMMED MEAN or ALL
                                                      -- default: 20, range [1,50]
) AS t;
```

## TD_WhichMax / TD_WhichMin
Returns all rows where the target column equals its maximum (or minimum) value. TargetColumn is singular.
```sql
-- Returns all rows where target_column equals its maximum value
SELECT * FROM TD_WhichMax(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY order_col
    USING
        TargetColumn('amount')                        -- single column only
) AS t;

-- Returns all rows where target_column equals its minimum value
SELECT * FROM TD_WhichMin(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY order_col
    USING
        TargetColumn('amount')                        -- single column only
) AS t;
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
