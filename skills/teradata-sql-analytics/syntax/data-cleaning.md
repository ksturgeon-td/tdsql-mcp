# Teradata Data Cleaning

## NULL Detection and Handling

### Find NULLs
```sql
-- Count NULLs per column
SELECT
    SUM(CASE WHEN col1 IS NULL THEN 1 ELSE 0 END) AS col1_nulls,
    SUM(CASE WHEN col2 IS NULL THEN 1 ELSE 0 END) AS col2_nulls,
    COUNT(*) AS total_rows
FROM db.table;

-- Rows where any column is NULL
SELECT * FROM db.table
WHERE col1 IS NULL OR col2 IS NULL OR col3 IS NULL;

-- TD_GetRowsWithMissingValues: returns all rows that contain NULLs in target columns
SELECT * FROM TD_GetRowsWithMissingValues(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY id_col
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns
        -- or: TargetColumns('[1:5]')                 -- column range by position
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range e.g. '[1:3]'
) AS t;
```

### Replace NULLs
```sql
-- Replace with a literal value
SELECT COALESCE(col, 0)          AS col_filled     FROM db.table;  -- numeric
SELECT COALESCE(col, 'Unknown')  AS col_filled     FROM db.table;  -- string

-- Replace with column mean
SELECT COALESCE(amount, AVG(amount) OVER ()) AS amount_filled
FROM db.table;

-- Replace with group mean
SELECT COALESCE(amount, AVG(amount) OVER (PARTITION BY category)) AS amount_filled
FROM db.table;

-- Forward-fill: carry last non-NULL value forward (time-ordered)
SELECT id, dt,
       LAST_VALUE(value IGNORE NULLS) OVER (
           PARTITION BY id ORDER BY dt
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS value_ffill
FROM db.timeseries;
```

### Remove Rows with NULLs
```sql
-- Exclude rows where any key column is NULL
SELECT * FROM db.table
WHERE col1 IS NOT NULL
  AND col2 IS NOT NULL;
```

---

## Deduplication

### Detect Duplicates
```sql
-- Count duplicates by key
SELECT key_col, COUNT(*) AS dup_count
FROM db.table
GROUP BY key_col
HAVING COUNT(*) > 1
ORDER BY dup_count DESC;

-- Inspect duplicate rows
SELECT * FROM db.table
QUALIFY COUNT(*) OVER (PARTITION BY key_col) > 1
ORDER BY key_col;
```

### Remove Duplicates — Keep One Row
```sql
-- Keep the most recent row per key (by date)
SELECT * FROM db.table
QUALIFY ROW_NUMBER() OVER (PARTITION BY key_col ORDER BY updated_at DESC) = 1;

-- Keep the row with the highest value per key
SELECT * FROM db.table
QUALIFY ROW_NUMBER() OVER (PARTITION BY key_col ORDER BY amount DESC) = 1;

-- Deduplicate fully identical rows (all columns the same)
SELECT DISTINCT * FROM db.table;
```

---

## String Cleaning

### Whitespace and Case
```sql
-- Trim leading/trailing whitespace
SELECT TRIM(col)        AS col_trimmed FROM db.table;
SELECT TRIM(LEADING  ' ' FROM col) FROM db.table;
SELECT TRIM(TRAILING ' ' FROM col) FROM db.table;

-- Normalize case
SELECT UPPER(col) AS col_upper FROM db.table;
SELECT LOWER(col) AS col_lower FROM db.table;
```

### Find and Replace
```sql
-- Replace a substring
SELECT OREPLACE(col, 'old_value', 'new_value') AS col_cleaned FROM db.table;

-- Remove special characters (chain OREPLACE calls)
SELECT OREPLACE(OREPLACE(col, '-', ''), ' ', '') AS col_stripped FROM db.table;
```

### Validate Format
```sql
-- Flag values that don't match an expected pattern
SELECT col,
       CASE WHEN col LIKE '[0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]'
            THEN 'valid' ELSE 'invalid' END AS phone_check
FROM db.table;

-- Find non-numeric values in a column that should be numeric
SELECT col FROM db.table
WHERE col NOT LIKE '%[^0-9]%'   -- adjust pattern as needed
   OR col IS NULL;
```

---

## Outlier Detection and Handling

### IQR Method (Using NTILE)
```sql
-- Compute Q1 and Q3 via NTILE
WITH quartiles AS (
    SELECT id, amount,
           NTILE(4) OVER (ORDER BY amount) AS quartile
    FROM db.table
    WHERE amount IS NOT NULL
),
bounds AS (
    SELECT
        MAX(CASE WHEN quartile = 1 THEN amount END) AS q1,
        MAX(CASE WHEN quartile = 3 THEN amount END) AS q3
    FROM quartiles
)
SELECT q.id, q.amount,
       CASE WHEN q.amount < b.q1 - 1.5 * (b.q3 - b.q1)
              OR q.amount > b.q3 + 1.5 * (b.q3 - b.q1)
            THEN 1 ELSE 0 END AS is_outlier
FROM quartiles q CROSS JOIN bounds b;
```

### Z-Score Method
```sql
-- Flag rows beyond N standard deviations from the mean
SELECT id, amount,
       (amount - AVG(amount) OVER ()) / NULLIFZERO(STDDEV_SAMP(amount) OVER ()) AS zscore,
       CASE WHEN ABS((amount - AVG(amount) OVER ()) /
                     NULLIFZERO(STDDEV_SAMP(amount) OVER ())) > 3
            THEN 1 ELSE 0 END AS is_outlier
FROM db.table;
```

### Cap Outliers (Winsorization)
```sql
-- Cap values at the 1st and 99th percentile using NTILE boundaries
WITH pct AS (
    SELECT
        MAX(CASE WHEN pct_rank =  1 THEN amount END) AS p01,
        MAX(CASE WHEN pct_rank = 99 THEN amount END) AS p99
    FROM (
        SELECT amount,
               NTILE(100) OVER (ORDER BY amount) AS pct_rank
        FROM db.table WHERE amount IS NOT NULL
    ) t
)
SELECT id,
       GREATEST(p.p01, LEAST(p.p99, t.amount)) AS amount_capped
FROM db.table t CROSS JOIN pct p;
```

---

## Data Type Validation and Casting

### Safe Casting Patterns
```sql
-- Cast with fallback for bad values
SELECT CASE WHEN col (VARCHAR(20)) LIKE '%[^0-9.]%'
            THEN NULL
            ELSE CAST(col AS DECIMAL(18,2))
       END AS col_numeric
FROM db.table;

-- Validate date strings before casting
SELECT col,
       CASE WHEN col IS NULL THEN NULL
            WHEN CHAR_LENGTH(TRIM(col)) <> 10 THEN NULL   -- expect YYYY-MM-DD
            ELSE CAST(col AS DATE FORMAT 'YYYY-MM-DD')
       END AS col_date
FROM db.table;
```

### Standardize Date Formats
```sql
-- Reformat a date column to a consistent output format
SELECT CAST(date_col AS DATE FORMAT 'YYYY-MM-DD') AS date_std
FROM db.table;

-- Extract and reconstruct to normalize messy date representations
SELECT TO_DATE(
    CAST(EXTRACT(YEAR  FROM date_col) AS VARCHAR(4)) || '-' ||
    LPAD(CAST(EXTRACT(MONTH FROM date_col) AS VARCHAR(2)), 2, '0') || '-' ||
    LPAD(CAST(EXTRACT(DAY   FROM date_col) AS VARCHAR(2)), 2, '0'),
    'YYYY-MM-DD'
) AS date_normalized
FROM db.table;
```

---

## TD_GetFutileColumns
Identifies columns that provide no analytical value. Futile column types:
- **Constant** — same value in every row
- **Unique ID** — distinct value in every row
- **Redundant** — duplicate of another column
- **Unstructured text** — free-text with no reusable pattern

```sql
-- Basic usage
SELECT * FROM TD_GetFutileColumns(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        ThresholdValue(0.95)                          -- optional: 0-1, default 0.95
) AS t;

-- With CategoryTable: pass output of TD_CategoricalSummary for richer detection
SELECT * FROM TD_GetFutileColumns(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.cat_summary | (SELECT * FROM TD_CategoricalSummary(...)) } AS CategoryTable DIMENSION
    USING
        CategoricalSummaryColumn('ColumnName')        -- optional: column from CategoryTable, default 'ColumnName'
        ThresholdValue(0.95)                          -- optional: default 0.95
) AS t;
```

---

## TD_OutlierFilterFit / TD_OutlierFilterTransform
Two-phase outlier handling. See `fit-transform-pattern` topic for model storage options.

```sql
-- TD_OutlierFilterFit: learn outlier boundaries from training data
-- Percentile method (default)
SELECT * FROM TD_OutlierFilterFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_outlier_model)  -- optional; rows still returned when OUT is used
    USING
        TargetColumns('col1', 'col2')                 -- required; explicit columns or range e.g. '[1:5]'
        GroupColumns('group_col')                     -- optional: compute boundaries per group
        OutlierMethod('percentile')                   -- default; options: 'percentile', 'tukey', 'carling'
        LowerPercentile(0.05)                         -- default: 0.05
        UpperPercentile(0.95)                         -- default: 0.95
        ReplacementValue('delete')                    -- default: 'delete'; options: 'delete', 'null',
                                                      --   'median', or any numeric literal e.g. 0 or -999
        RemoveTail('both')                            -- default: 'both'; options: 'upper', 'lower'
        PercentileMethod('PercentileDISC')            -- default: 'PercentileDISC'; or 'PercentileCont'
) AS t;

-- Tukey method (IQR-based) — use LowerPercentile(0.25) and UpperPercentile(0.75)
SELECT * FROM TD_OutlierFilterFit(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2')                 -- or range e.g. '[1:5]'
        OutlierMethod('tukey')
        LowerPercentile(0.25)                         -- recommended for Tukey
        UpperPercentile(0.75)                         -- recommended for Tukey
        IQRMultiplier(1.5)                            -- default: 1.5 (moderate); use 3.0 for serious outliers
        ReplacementValue('median')
) AS t;

-- Carling method (median-based) — use LowerPercentile(0.25) and UpperPercentile(0.75)
SELECT * FROM TD_OutlierFilterFit(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2')                 -- or range e.g. '[1:5]'
        OutlierMethod('carling')
        LowerPercentile(0.25)                         -- recommended for Carling
        UpperPercentile(0.75)                         -- recommended for Carling
        GroupColumns('group_col')                     -- optional: Carling uses group row count in formula
        ReplacementValue('null')
) AS t;

-- TD_OutlierFilterTransform: apply learned boundaries to new data
-- Flavor 1: PARTITION BY ANY
SELECT * FROM TD_OutlierFilterTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.fit_table | (SELECT * FROM TD_OutlierFilterFit(...)) } AS FitTable DIMENSION
) AS t;

-- Flavor 2: partition by group column (use when Fit was run with GroupColumns)
SELECT * FROM TD_OutlierFilterTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY group_column
    ON { db.fit_table | (SELECT * FROM TD_OutlierFilterFit(...)) } AS FitTable PARTITION BY group_column
) AS t;
```

---

## TD_GetRowsWithoutMissingValues
Returns only rows that have no NULLs in the target columns (complement of TD_GetRowsWithMissingValues).

```sql
SELECT * FROM TD_GetRowsWithoutMissingValues(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY id_col
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns or range e.g. '[1:5]'
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range e.g. '[1:3]'
) AS t;
```

---

## TD_SimpleImputeFit / TD_SimpleImputeTransform
Two-phase missing value imputation. See `fit-transform-pattern` topic for model storage options.

```sql
-- TD_SimpleImputeFit: learn imputation values from training data
-- Literals only: replace missing values with specified constants
SELECT * FROM TD_SimpleImputeFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_impute_model)   -- optional; PERMANENT or VOLATILE
    USING
        ColsForLiterals('col1', 'col2')               -- columns to impute with literal values
        Literals('replacement_value1', 'replacement_value2')  -- one literal per column, positional mapping
) AS t;

-- Stats only: replace missing values with computed statistics
SELECT * FROM TD_SimpleImputeFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_impute_model)   -- optional; PERMANENT or VOLATILE
    USING
        ColsForStats('col1', 'col2')                  -- columns to impute with stats
        Stats('MEAN', 'MEDIAN')                       -- one stat per column, positional mapping
                                                      -- numeric: MIN, MAX, MEAN, MEDIAN
                                                      -- any type: MODE
        PartitionColumn('group_col')                  -- optional: compute stats per group
) AS t;

-- Combined: literals for some columns, stats for others
SELECT * FROM TD_SimpleImputeFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_impute_model)
    USING
        ColsForLiterals('cat_col')
        Literals('replacement_value')
        ColsForStats('num_col1', 'num_col2')
        Stats('MEAN', 'MEDIAN')
        PartitionColumn('group_col')                  -- optional
) AS t;

-- TD_SimpleImputeTransform: apply learned imputation to new data
-- Flavor 1: PARTITION BY ANY
SELECT * FROM TD_SimpleImputeTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.fit_table | (SELECT * FROM TD_SimpleImputeFit(...)) } AS FitTable DIMENSION
) AS t;

-- Flavor 2: partition by group column (use when Fit was run with PartitionColumn)
SELECT * FROM TD_SimpleImputeTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY group_column
    ON { db.fit_table | (SELECT * FROM TD_SimpleImputeFit(...)) } AS FitTable PARTITION BY group_column
) AS t;
```

---

## Pack / Unpack
Pack combines multiple columns into a single delimited string column. Unpack reverses the operation.

```sql
-- Pack: combine columns into a single output column
-- Pack all columns (default behavior)
SELECT * FROM Pack(
    ON { db.table | db.view | (query) }
    USING
        OutputColumn('packed_col')                    -- required: name of the output packed column
) AS t;

-- Pack specific columns with options
SELECT * FROM Pack(
    ON { db.table | db.view | (query) }
    USING
        TargetColumns('col1', 'col2', 'col3')         -- optional: columns or range e.g. '[1:5]'
                                                      -- default: all columns packed
        OutputColumn('packed_col')                    -- required
        Delimiter('|')                                -- optional: single Unicode char, default ','
        IncludeColumnName('true')                     -- optional: prefix values with col name (col:value)
                                                      -- default: 'true'
        ColCast('true')                               -- optional: cast numeric cols to VARCHAR
                                                      -- default: 'false'; set 'true' for better performance
        Accumulate('id_col', 'date_col')              -- optional: columns or range to pass through
) AS t;
-- Example output with defaults (IncludeColumnName='true', Delimiter=','):
--   col1:value1,col2:value2,col3:value3
-- Example output with IncludeColumnName='false':
--   value1,value2,value3

-- Unpack: split a packed column back into separate columns
-- Delimiter-based (default)
SELECT * FROM Unpack(
    ON { db.table | db.view | (query) } AS InputTable   -- ON clause is optional
    USING
        TargetColumn('packed_col')                    -- required: column containing packed data
        OutputColumns('col1', 'col2', 'col3')         -- required: names for unpacked columns
        OutputDataTypes('VARCHAR', 'INTEGER', 'DATE') -- required: one type per output column,
                                                      -- or one type applied to all columns
                                                      -- supported: VARCHAR, INTEGER, DOUBLE PRECISION,
                                                      --            TIME, DATE, TIMESTAMP
        Delimiter(',')                                -- optional: default ','
                                                      -- NOTE: do not use with ColumnLength
        Accumulate('id_col', 'date_col')              -- optional: columns or range to pass through
        IgnoreInvalid('false')                        -- optional: default 'false' — fails on invalid data
) AS t;

-- Fixed-width: unpack columns of known length (no delimiter)
SELECT * FROM Unpack(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumn('packed_col')
        OutputColumns('col1', 'col2', 'col3')
        OutputDataTypes('VARCHAR')                    -- single type applied to all output columns
        ColumnLength('2', '1', '*')                   -- one length per column; '*' captures remainder
                                                      -- NOTE: do not use with Delimiter
) AS t;

-- Regex: unpack labeled data e.g. "age:34,gender:male" (as produced by Pack with IncludeColumnName='true')
SELECT * FROM Unpack(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumn('packed_col')
        OutputColumns('age', 'gender')
        OutputDataTypes('INTEGER', 'VARCHAR')
        Delimiter(',')
        Regex('.*:(.*)')                              -- pattern to extract values after 'col_name:'
        RegexSet('1')                                 -- optional: which capture group holds the value
                                                      -- default: last group; max: 30
) AS t;
```

---

## StringSimilarity
Computes similarity scores between pairs of string columns. Multiple comparison methods can be
specified in a single call, each with its own method and optional constant.

```sql
SELECT * FROM StringSimilarity(
    ON { db.table | db.view | (query) } PARTITION BY ANY
    USING
        ComparisonColumnPairs(
            'jaro(col1, col2) AS jaro_sim',                -- Jaro distance
            'jaro_winkler(col1, col2, 0.1) AS jw_sim',    -- Jaro-Winkler; constant = p factor (default 0.1)
            'n_gram(col1, col2, 2) AS ngram_sim',          -- N-gram; constant = N (default 2)
            'LD(col1, col2) AS levenshtein',               -- Levenshtein edit distance
            'jaccard(col1, col2) AS jaccard_sim',          -- Jaccard index
            'cosine(col1, col2) AS cosine_sim'             -- Cosine similarity
        )
        CaseSensitive('false')                             -- optional: one value for all pairs,
                                                           -- or one per pair e.g. ('true','false','true')
                                                           -- default: 'false'
        Accumulate('id_col')                               -- optional: columns or range to pass through
) AS t;

-- Available comparison_type options:
--   'jaro'         — Jaro distance
--   'jaro_winkler' — Jaro-Winkler distance (constant = p, 0 ≤ p ≤ 0.25, default 0.1)
--   'n_gram'       — N-gram similarity (constant = N, default 2)
--   'LD'           — Levenshtein distance (insertions, deletions, substitutions)
--   'LDWS'         — Levenshtein without substitution
--   'OSA'          — Optimal string alignment (each substring edited once)
--   'DL'           — Damerau-Levenshtein (substrings can be edited multiple times)
--   'hamming'      — Hamming distance (equal-length strings; -1 if unequal length)
--   'LCS'          — Longest common substring length
--   'jaccard'      — Jaccard index
--   'cosine'       — Cosine similarity
--   'soundexcode'  — English soundex match (1=match, 0=no match, -1=non-English char)
-- Output column default: sim_i (where i = sequence number of the pair)
-- Similarity scores in [0,1]; distance measures (LD, LDWS, OSA, DL, hamming, LCS) return integers
```

---

## TD_ConvertTo
Converts columns to specified target data types. See `data-types-casting` topic for the full
source → target type conversion rules.

```sql
SELECT * FROM TD_ConvertTo(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2')                 -- explicit columns or range e.g. '[1:5]'
        TargetDataType('VARCHAR', 'INTEGER')          -- one type per column, or one applied to all
        -- Accumulate('id_col')                       -- optional: columns or range to pass through
) AS t;
```
