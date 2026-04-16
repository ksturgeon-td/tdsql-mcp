# Teradata Data Preparation & Feature Engineering

## Column Selection

### Antiselect — Return All Columns Except Specified
```sql
SELECT * FROM Antiselect(
    ON { db.table | db.view | (query) }
    USING
        Exclude('col1', 'col2')                       -- explicit columns or range e.g. '[1:5]'
) AS t;
```

---

## Normalization / Scaling

### Min-Max Scaling (0 to 1)
```sql
SELECT col,
       (col - MIN(col) OVER ()) / NULLIFZERO(MAX(col) OVER () - MIN(col) OVER ()) AS col_minmax
FROM db.table;
```

### Z-Score Standardization
```sql
SELECT col,
       (col - AVG(col) OVER ()) / NULLIFZERO(STDDEV_SAMP(col) OVER ()) AS col_zscore
FROM db.table;
```

### TD_ScaleFit / TD_ScaleTransform
See the Fit/Transform function section below.

### TD_VectorNormalize

Normalizes numeric columns or `VECTOR` columns using one of four approaches. Supports list or range for `IDColumns`, `TargetColumns`, and `Accumulate`.

```sql
SELECT * FROM TD_VectorNormalize(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    USING
        IDColumns({ 'id_col' | col_range }[,...])         -- required; unique row identifier(s)
        TargetColumns({ 'col' | col_range }[,...])        -- required; columns to normalize; supports VECTOR type
        [ Accumulate({ 'col' | col_range }[,...]) ]       -- optional; columns to pass through
        [ Approach('UNITVECTOR'|'FRACTION'|'PERCENTAGE'|'INDEX') ]  -- default 'UNITVECTOR'
        [ BaseColumn('base_col') ]                        -- required with INDEX; per-row denominator column
        [ BaseValue('base_value') ]                       -- required with INDEX; scalar denominator value
) AS t;
```

**Approach options:**

| Approach | Formula | Use case |
|----------|---------|----------|
| `UNITVECTOR` (default) | `x / L2_norm(row)` | Normalize to unit length; required before cosine similarity or HNSW indexing |
| `FRACTION` | `x / sum(row)` | Each value as a fraction of the row total |
| `PERCENTAGE` | `x / sum(row) * 100` | Each value as a percentage of the row total |
| `INDEX` | `(x - B) / V` | Normalize relative to a base; `B` from `BaseColumn`, `V` from `BaseValue` |

> **Embedding pre-processing:** use `Approach('UNITVECTOR')` with a `VECTOR` column before storing embeddings or building an HNSW index. Unit-normalized vectors enable cosine similarity via dot product. See `vector-search` topic.

---

## Binning

### Equal-Width Bins (Manual)
```sql
SELECT id, amount,
       CASE
           WHEN amount < 100  THEN 'low'
           WHEN amount < 500  THEN 'medium'
           WHEN amount < 1000 THEN 'high'
           ELSE 'very_high'
       END AS amount_bin
FROM db.table;
```

### Equal-Frequency Bins / Quantile-Based (Manual)
```sql
SELECT id, amount,
       NTILE(4)  OVER (ORDER BY amount) AS quartile,
       NTILE(10) OVER (ORDER BY amount) AS decile
FROM db.table;
```

### TD_BinCodeFit / TD_BinCodeTransform
See the Fit/Transform function section below.

---

## Encoding Categorical Variables

### One-Hot Encoding (Manual)
```sql
SELECT id,
       CASE WHEN category = 'A' THEN 1 ELSE 0 END AS cat_A,
       CASE WHEN category = 'B' THEN 1 ELSE 0 END AS cat_B,
       CASE WHEN category = 'C' THEN 1 ELSE 0 END AS cat_C
FROM db.table;
```

### Label / Ordinal Encoding (Manual)
```sql
SELECT id, category,
       DENSE_RANK() OVER (ORDER BY category) - 1 AS category_encoded
FROM db.table;
```

### TD_OneHotEncodingFit / TD_OneHotEncodingTransform
### TD_OrdinalEncodingFit / TD_OrdinalEncodingTransform
### TD_TargetEncodingFit / TD_TargetEncodingTransform
See the Fit/Transform function section below.

---

## Reshaping

### Unpivot (Wide → Long) — Manual
```sql
SELECT id, 'jan' AS month, jan_sales AS sales FROM db.t
UNION ALL
SELECT id, 'feb', feb_sales FROM db.t
UNION ALL
SELECT id, 'mar', mar_sales FROM db.t;
```

### TD_Unpivoting (Wide → Long)
```sql
-- Basic unpivot
SELECT * FROM TD_Unpivoting(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IDColumn('id_col')                            -- required: identifier column
        TargetColumns('jan_sales', 'feb_sales',
                      'mar_sales')                    -- required: columns to unpivot; or range e.g. '[2:4]'
        AttributeColName('month')                     -- optional: name for attribute column
                                                      -- default: 'AttributeName'
        ValueColName('sales')                         -- optional: name for value column
                                                      -- default: 'AttributeValue'
        AttributeAliasList('January', 'February',
                           'March')                   -- optional: friendly names for TargetColumns
                                                      -- must match count of TargetColumns
        Accumulate('region_col')                      -- optional: columns or range to pass through
        IncludeNulls('false')                         -- optional: include NULL values; default: 'false'
) AS t;

-- Advanced options
SELECT * FROM TD_Unpivoting(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IDColumn('id_col')
        TargetColumns('col1', 'col2', 'col3')         -- or range e.g. '[1:5]'
        InputTypes('true')                            -- optional: output multiple typed value columns
                                                      -- instead of single AttributeValue column
                                                      -- default: 'false'
        OutputVarchar('true')                         -- optional: cast AttributeValue to VARCHAR
                                                      -- default: 'false'; not used with InputTypes
        IndexedAttribute('false')                     -- optional: use column index instead of name
                                                      -- default: 'false'
        IncludeDataTypes('false')                     -- optional: add column with original data type
                                                      -- default: 'false'
) AS t;
```

### Pivot (Long → Wide) — Manual
```sql
SELECT id,
       SUM(CASE WHEN month = 'jan' THEN sales END) AS jan,
       SUM(CASE WHEN month = 'feb' THEN sales END) AS feb,
       SUM(CASE WHEN month = 'mar' THEN sales END) AS mar
FROM db.long_table
GROUP BY id;
```

### TD_Pivoting (Long → Wide)
```sql
-- Mode 1: PivotColumn — a column contains the pivot keys (most common)
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
        ORDER BY category_col
    USING
        PartitionColumns('id_col')                    -- must match PARTITION BY; list or range
        TargetColumns('value_col')                    -- columns to pivot; list or range
        PivotColumn('category_col')                   -- column whose values become new column headers
        PivotKeys('A', 'B', 'C')                      -- which values to pivot (others ignored)
        PivotKeysAlias('cat_a', 'cat_b', 'cat_c')     -- optional: rename pivot key output columns
        DefaultPivotValues('0', '0', '0')             -- optional: fill value when pivot key is absent
        Accumulate('name_col')                        -- optional: pass-through cols; list or range
        OutputColumnNames('id', 'name', 'cat_a',
                          'cat_b', 'cat_c')           -- optional: rename all output columns
) AS t;

-- Mode 2: RowsPerPartition — no pivot key column; spread N rows into N columns
-- ORDER BY is required to ensure deterministic output
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
        ORDER BY seq_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('value_col')                    -- list or range
        RowsPerPartition(4)                           -- max rows to pivot (1-2047 without aggregation)
                                                      -- NULLs added if partition has fewer rows
                                                      -- extra rows omitted if partition has more
) AS t;

-- Mode 3: Aggregation only — no RowsPerPartition or PivotColumn
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('amount', 'quantity')           -- list or range
        Aggregation('SUM')                            -- single aggregation for all target columns
        -- or per-column: Aggregation('amount:SUM', 'quantity:MAX')
        -- options: CONCAT, UNIQUE_CONCAT, SUM, MIN, MAX, AVG
) AS t;

-- CONCAT/UNIQUE_CONCAT additional options
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('tag_col')                      -- list or range
        Aggregation('CONCAT')
        Delimiters('|')                               -- optional: default ','; or per-column 'tag_col:|'
        CombinedColumnSizes(64000)                    -- optional: default 64000 (VARCHAR)
                                                      -- use >64000 for CLOB output
        TruncateColumns('tag_col')                    -- optional: list or range; truncate if over size
) AS t;
```

---

## Dimensionality Reduction

### TD_RandomProjectionMinComponents
Calculates the minimum number of components required before running `TD_RandomProjectionFit`.
Uses the Johnson-Lindenstrauss Lemma — run this first to estimate the `NumComponents` argument.

```sql
SELECT * FROM TD_RandomProjectionMinComponents(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required: columns for projection; or range
        Epsilon(0.1)                                  -- optional: distortion tolerance, range (0, 1)
                                                      -- higher value = more distortion, fewer components
                                                      -- default: 0.1
) AS t;
-- Pass the output value as NumComponents in TD_RandomProjectionFit
```

### TD_RandomProjectionFit / TD_RandomProjectionTransform
See the Fit/Transform function section below.

---

## Pipeline — Apply Multiple Transforms in One Pass

### TD_ColumnTransformer
Applies multiple Fit/Transform operations to an input table in a single step.
Each FitTable DIMENSION input is optional — include only the transforms needed.
Note: multiple `NonLinearCombineFitTable` instances are allowed; all other FitTable types allow only one.

```sql
SELECT * FROM TD_ColumnTransformer(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS BincodeFitTable DIMENSION
    ON { db.table | db.view | (query) } AS FunctionFitTable DIMENSION
    ON { db.table | db.view | (query) } AS NonLinearCombineFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OneHotEncodingFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OrdinalEncodingFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OutlierFilterFitTable DIMENSION
    ON { db.table | db.view | (query) } AS PolynomialFeaturesFitTable DIMENSION
    ON { db.table | db.view | (query) } AS RowNormalizeFitTable DIMENSION
    ON { db.table | db.view | (query) } AS ScaleFitTable DIMENSION
    ON { db.table | db.view | (query) } AS SimpleImputeFitTable DIMENSION
    USING
        FillRowIDColumnName('row_id')                 -- optional: adds unique row ID column to output
) AS t;

-- Practical example: impute nulls, scale, and one-hot encode in one operation
SELECT * FROM TD_ColumnTransformer(
    ON db.new_data AS InputTable
    ON db.impute_fit  AS SimpleImputeFitTable DIMENSION
    ON db.scale_fit   AS ScaleFitTable DIMENSION
    ON db.onehot_fit  AS OneHotEncodingFitTable DIMENSION
) AS t;
```

---

## Feature Engineering Patterns

### Lag / Lead Features (Time Series)
```sql
SELECT id, dt, value,
       LAG(value, 1)  OVER (PARTITION BY id ORDER BY dt) AS value_lag1,
       LAG(value, 7)  OVER (PARTITION BY id ORDER BY dt) AS value_lag7,
       LEAD(value, 1) OVER (PARTITION BY id ORDER BY dt) AS value_next
FROM db.timeseries;
```

### Rolling Statistics
```sql
SELECT id, dt, value,
       AVG(value)         OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 6  PRECEDING AND CURRENT ROW) AS rolling_7d_avg,
       STDDEV_SAMP(value) OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS rolling_30d_std
FROM db.timeseries;
```

### Ratio / Interaction Features
```sql
SELECT id,
       revenue / NULLIFZERO(visits)        AS revenue_per_visit,
       clicks  / NULLIFZERO(impressions)   AS ctr,
       (revenue - cost) / NULLIFZERO(cost) AS roi
FROM db.campaign;
```

---

## Class Imbalance / Oversampling

### TD_SMOTE

Generates synthetic minority-class samples to address class imbalance in training data. Supports four oversampling strategies: standard SMOTE, ADASYN, Borderline-SMOTE, and SMOTE-NC (for mixed numeric + categorical features).

> **Output contains synthetic samples only** — `UNION ALL` with the original training table to produce the full augmented dataset before training.

```sql
SELECT * FROM TD_SMOTE(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    [ ON db.encodings_table AS EncodingsTable DIMENSION ]   -- smotenc only; see below
    USING
        IDColumn('id_col')                                  -- required; unique row identifier
        ResponseColumn('response_col')                      -- required; numeric class label column
        InputColumns({ 'col' | col_range }[,...])           -- required; numeric columns used for synthesis
        MinorityClass('minority_label')                     -- required; minority class label (integer, quoted as string)
        [ CategoricalInputColumns({ 'col' | col_range }[,...]) ]  -- smotenc only; required for smotenc
        [ MedianStandardDeviation(med) ]                    -- smotenc only; required for smotenc (see tip below)
        [ OversamplingFactor(5) ]                           -- default 5; value of 1.0 = same count as minority class
        [ SamplingStrategy('smote'|'adasyn'|'borderline'|'smotenc') ]  -- default 'smote'
        [ NumberOfNeighbors(5) ]                            -- default 5; see note on effective neighbors below
        [ FillSampleID('true') ]                            -- default true; writes source obs ID to id_col in output
        [ ValueForNonInputColumns('sample'|'neighbor'|'null') ]  -- default 'sample'
        [ Seed(186006) ]                                    -- default 186006; set for deterministic output
) AS t;
```

**Combine with original data:**
```sql
-- Full augmented training set (original + synthetic minority samples)
SELECT * FROM db.training_table
UNION ALL
SELECT * FROM TD_SMOTE(
    ON db.training_table PARTITION BY ANY
    USING
        IDColumn('id')
        ResponseColumn('label')
        InputColumns('feat1', 'feat2', 'feat3')
        MinorityClass('1')
        OversamplingFactor(5)
) AS t;
```

**Notes:**

- **NumberOfNeighbors gotcha** — TD_KNN includes the observation itself as neighbor #1. `NumberOfNeighbors(5)` uses only 4 neighbors for interpolation. Set to 6 to get 5 effective neighbors; adjust accordingly.
- **OversamplingFactor** — value of `1.0` generates as many synthetic samples as there are minority observations. Default `5` generates 5× the minority count. ADASYN uses local density estimation, so the actual count may differ slightly.
- **SamplingStrategy 'adasyn' / 'borderline'** — for extreme imbalance or very few minority samples, oversample in fractions rather than using a large OversamplingFactor to avoid duplicates.
- **FillSampleID** — when `true`, the `id_col` in the output contains the original minority observation ID used to generate the synthetic sample, not a new unique ID. Set to `false` and generate your own IDs if you need unique keys in the augmented table.
- **ValueForNonInputColumns** — controls the value of columns not listed in `InputColumns`: `'sample'` (value from source observation), `'neighbor'` (value from the chosen neighbor), or `'null'`.

**SMOTE-NC (mixed numeric + categorical):**

SMOTE-NC requires an `EncodingsTable` produced by `TD_OrdinalEncodingFit` and a pre-computed `MedianStandardDeviation` value.

```sql
-- Step 1: build encodings table for categorical columns (Approach AUTO, no DefaultValue)
CREATE TABLE db.smote_encodings AS (
    SELECT * FROM TD_OrdinalEncodingFit(
        ON db.training_table PARTITION BY ANY
        USING
            TargetColumn('cat_col1', 'cat_col2')
            Approach('AUTO')
    ) AS t
) WITH DATA;

-- Step 2: compute MedianStandardDeviation (median of std devs of numeric input columns, minority class only)
SELECT StatValue AS MedianValue FROM TD_UnivariateStatistics(
    ON (
        SELECT * FROM TD_UnivariateStatistics(
            ON (SELECT * FROM db.training_table WHERE label = 1) AS InputTable
            USING
                TargetColumns('feat1', 'feat2', 'feat3')
                Stats('STANDARD DEVIATION')
        ) AS dt
    ) AS InputTable
    USING
        TargetColumns('StatValue')
        Stats('MED')
) AS dtu;

-- Step 3: run TD_SMOTE with smotenc
SELECT * FROM TD_SMOTE(
    ON db.training_table PARTITION BY ANY
    ON db.smote_encodings AS EncodingsTable DIMENSION
    USING
        IDColumn('id')
        ResponseColumn('label')
        InputColumns('feat1', 'feat2', 'feat3')
        CategoricalInputColumns('cat_col1', 'cat_col2')
        MinorityClass('1')
        SamplingStrategy('smotenc')
        MedianStandardDeviation(0.45)     -- value from Step 2
        OversamplingFactor(3)
) AS t;
```

> **smotenc restrictions:** Column aliasing is not allowed on `InputTable` or `EncodingsTable`. `EncodingsTable` must be a real table (no subquery); produce it from `TD_OrdinalEncodingFit` with `Approach('AUTO')` and **no** `DefaultValue` argument.

---

## Fit/Transform Functions

The following functions follow the two-phase Fit/Transform pattern. The Fit function learns parameters from training data (bin boundaries, encoding mappings, scaling factors, etc.) and writes them to a FitTable. The Transform function applies those parameters to any dataset.

**FitTable outputs should be saved and reused** — use the `OUT TABLE` clause on the Fit function to persist the FitTable to a named database table. If `OUT TABLE` is not available for a given function, use `CREATE TABLE AS (SELECT * FROM TD_XxxFit(...)) WITH DATA` or `INSERT INTO saved_table SELECT * FROM TD_XxxFit(...)` to capture the output. The same FitTable can then be applied to new or incoming data without refitting, ensuring consistent transformations across training and scoring pipelines.

See the `fit-transform-pattern` topic for full syntax details on storing and reusing Fit outputs.

| Function Pair | Purpose |
|---|---|
| `TD_BinCodeFit` / `TD_BinCodeTransform` | Bin numeric data into categorical intervals |
| `TD_FunctionFit` / `TD_FunctionTransform` | Apply numeric transformations (log, sqrt, etc.) |
| `TD_NonLinearCombineFit` / `TD_NonLinearCombineTransform` | Generate features from non-linear formulas |
| `TD_OneHotEncodingFit` / `TD_OneHotEncodingTransform` | One-hot encode categorical columns |
| `TD_OrdinalEncodingFit` / `TD_OrdinalEncodingTransform` | Map categories to ordinal values |
| `TD_PolynomialFeaturesFit` / `TD_PolynomialFeaturesTransform` | Generate polynomial feature combinations |
| `TD_RandomProjectionFit` / `TD_RandomProjectionTransform` | Reduce dimensionality via random projection |
| `TD_RowNormalizeFit` / `TD_RowNormalizeTransform` | Normalize input columns row-wise |
| `TD_ScaleFit` / `TD_ScaleTransform` | Scale numeric columns (ZSCORE, RANGE, etc.) |
| `TD_TargetEncodingFit` / `TD_TargetEncodingTransform` | Encode categoricals using target statistics |

---

### TD_BinCodeFit / TD_BinCodeTransform

```sql
-- Equal-width bins
SELECT * FROM TD_BincodeFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_bincode_model)  -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('amount', 'price')              -- required; explicit columns or range e.g. '[1:5]'
        MethodType('equal-width')
        NBins('10')                                   -- single value for all cols, or one per col e.g. '10','5'
        LabelPrefix('bin')                            -- optional: prefix for bin labels e.g. 'bin_1', 'bin_2'
        -- or separate prefixes: LabelPrefix('amount_bin', 'price_bin')
) AS t;

-- Variable-width bins using a dimension table
-- FitInput table schema: (ColumnName, MinValue, MaxValue, Label)
SELECT * FROM TD_BincodeFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.bin_boundaries | db.view | (query) } AS FitInput DIMENSION
    USING
        TargetColumns('amount', 'price')              -- required; explicit columns or range
        MethodType('variable-width')
        MinValueColumn('MinValue')                    -- optional: FitInput column with bin min
        MaxValueColumn('MaxValue')                    -- optional: FitInput column with bin max
        LabelColumn('Label')                          -- optional: FitInput column with bin label
        TargetColNames('ColumnName')                  -- optional: FitInput column with target col names
) AS t;

SELECT * FROM TD_BinCodeTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_BincodeFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_FunctionFit / TD_FunctionTransform

```sql
-- TD_FunctionFit: no USING clause — all config is in the TransformationTable
SELECT * FROM TD_FunctionFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.transformation_table | db.view | (query) } AS TransformationTable DIMENSION
) AS t;

-- TransformationTable schema:
-- TargetColumn (VARCHAR)   — InputTable column to transform
-- Transformation (VARCHAR) — transformation to apply (see below)
-- Parameters (VARCHAR)     — optional: JSON format e.g. '{"base": 10}'
-- DefaultValue (NUMERIC)   — optional: value when input is NULL or non-numeric; default 0

-- Available transformations:
--   ABS      — |x|
--   CEIL     — least integer >= x
--   EXP      — e^x
--   FLOOR    — greatest integer <= x
--   LOG      — log_base(x); param: {"base": base}; default base: e
--   POW      — x^exponent; param: {"exponent": exponent}; default exponent: 1
--   SIGMOID  — 1 / (1 + e^-x)
--   TANH     — (e^x - e^-x) / (e^x + e^-x)

SELECT * FROM TD_FunctionTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_FunctionFit(...)) } AS FitTable DIMENSION
    USING
        -- IDColumns('id_col', 'date_col')            -- optional: columns or range to pass through
) AS t;
```

---

### TD_NonLinearCombineFit / TD_NonLinearCombineTransform

```sql
SELECT * FROM TD_NonLinearCombineFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_nlc_model)      -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required; explicit columns or range e.g. '[1:3]'
                                                      -- referenced in Formula as X0, X1, X2... (ordinal)
        Formula('Y = X0 + X1')                        -- required: expression using column ordinals
        ResultColumn('combined_feature')              -- optional: name for the output column
) AS t;

-- Formula examples using standard Teradata arithmetic, hyperbolic, and trigonometric syntax:
--   Formula('Y = X0 + X1')               — sum of two columns
--   Formula('Y = ABS(X0)')               — absolute value
--   Formula('Y = LN(X1) * X2')           — log of col2 multiplied by col3
--   Formula('Y = SQRT(X0 * X1)')         — square root of product
--   Formula('Y = X0 / NULLIFZERO(X1)')   — safe division

SELECT * FROM TD_NonLinearCombineTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.fit_table | (SELECT * FROM TD_NonLinearCombineFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_OneHotEncodingFit / TD_OneHotEncodingTransform

```sql
-- DENSE INPUT, Approach LIST, CategoricalValues (single target column)
SELECT * FROM TD_OneHotEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IsInputDense('true')
        TargetColumn('gender')                        -- single column or range e.g. '[1:3]'
        Approach('LIST')
        CategoricalValues('M', 'F')                   -- explicit category list (single target col only)
        OtherColumnName('other')                      -- optional: output col for unlisted values
                                                      -- default: 'other'
) AS t;

-- DENSE INPUT, Approach LIST, CategoryTable (multiple target columns)
SELECT * FROM TD_OneHotEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.category_table | db.view | (query) } AS CategoryTable DIMENSION
    USING
        IsInputDense('true')
        TargetColumn('gender', 'region')              -- explicit columns or range
        Approach('LIST')
        TargetColumnNames('col_name_column')          -- CategoryTable column containing target col names
        CategoriesColumn('category_column')           -- CategoryTable column containing category values
        OtherColumnName('other_gender', 'other_region') -- optional: one per target column
) AS t;

-- DENSE INPUT, Approach AUTO (categories learned from data)
SELECT * FROM TD_OneHotEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IsInputDense('true')
        TargetColumn('gender', 'region')              -- explicit columns or range
        Approach('AUTO')
        CategoryCounts(2, 4)                          -- required with AUTO: one count per target column
        OtherColumnName('other_gender', 'other_region') -- optional: one per target column
) AS t;

-- SPARSE INPUT (data in attribute/value format)
SELECT * FROM TD_OneHotEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY attribute_column
    USING
        IsInputDense('false')
        AttributeColumn('attribute_column')           -- required: column containing attribute names
        ValueColumn('value_column')                   -- required: column containing attribute values
        TargetAttributes('gender', 'region')          -- required: which attributes to encode
        OtherAttributesNames('other_gender',
                             'other_region')          -- optional: one per TargetAttribute;
                                                      -- must match count of TargetAttributes
) AS t;

-- DENSE Transform
SELECT * FROM TD_OneHotEncodingTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.fit_table | (SELECT * FROM TD_OneHotEncodingFit(...)) } AS FitTable DIMENSION
    USING
        IsInputDense('true')
) AS t;

-- SPARSE Transform (both tables partition by the same attribute column)
SELECT * FROM TD_OneHotEncodingTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY attribute_column
    ON { db.fit_table | (SELECT * FROM TD_OneHotEncodingFit(...)) } AS FitTable PARTITION BY attribute_column
    USING
        IsInputDense('false')
) AS t;
```

---

### TD_OrdinalEncodingFit / TD_OrdinalEncodingTransform

```sql
-- Approach AUTO (default): categories learned from data
SELECT * FROM TD_OrdinalEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_ordinal_model)  -- optional; PERMANENT or VOLATILE
    USING
        TargetColumn('color', 'size')                 -- required; explicit columns or range e.g. '[1:3]'
        Approach('AUTO')                              -- default: 'AUTO'
        StartValue(0)                                 -- optional: starting ordinal; single or one per col
                                                      -- default: 0
        DefaultValue(0)                               -- optional: ordinal for unseen categories in Transform
                                                      -- WARNING: if omitted, Transform errors on unseen values
) AS t;

-- Approach LIST, Categories (single target column)
SELECT * FROM TD_OrdinalEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumn('size')
        Approach('LIST')
        Categories('S', 'M', 'L', 'XL')              -- required with LIST + single target col
        OrdinalValues(1, 2, 3, 4)                     -- optional: custom ordinal per category
                                                      -- default: StartValue to NumCategories-1
        DefaultValue(-1)                              -- optional: value for unseen categories in Transform
) AS t;

-- Approach LIST, CategoryTable (multiple target columns)
SELECT * FROM TD_OrdinalEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.category_table | db.view | (query) } AS CategoryTable DIMENSION
    USING
        TargetColumn('color', 'size')                 -- explicit columns or range
        Approach('LIST')
        TargetColumnNames('col_name_column')          -- CategoryTable column with target column names
        CategoriesColumn('category_column')           -- CategoryTable column with category values
        OrdinalValuesColumn('ordinal_column')         -- optional: CategoryTable column with ordinal values
        StartValue(0, 1)                              -- optional: one per target column; default 0
        DefaultValue(-1, -1)                          -- optional: one per target column
) AS t;

SELECT * FROM TD_OrdinalEncodingTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_OrdinalEncodingFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_PolynomialFeaturesFit / TD_PolynomialFeaturesTransform

```sql
SELECT * FROM TD_PolynomialFeaturesFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_poly_model)     -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required; explicit columns or range; max 5 columns
        Degree(2)                                     -- optional: max polynomial degree; 1, 2, or 3
                                                      -- default: 2
        IncludeBias('true')                           -- optional: include column of ones (intercept term)
                                                      -- default: 'true'
        InteractionOnly('false')                      -- optional: cross-products only (no x^2, y^2 etc.)
                                                      -- default: 'false'
) AS t;

-- Example output for TargetColumns('x','y'), Degree(2), IncludeBias('true'):
--   1, x, y, x^2, xy, y^2
-- With InteractionOnly('true'):
--   1, x, y, xy

SELECT * FROM TD_PolynomialFeaturesTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.fit_table | (SELECT * FROM TD_PolynomialFeaturesFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_RandomProjectionFit / TD_RandomProjectionTransform

```sql
-- Step 1 (optional): calculate minimum NumComponents
-- SELECT * FROM TD_RandomProjectionMinComponents(
--     ON { db.table | db.view | (query) } AS InputTable
--     USING
--         TargetColumns('col1', 'col2', 'col3')
--         Epsilon(0.1)                               -- must match Epsilon used in TD_RandomProjectionFit
-- ) AS t;

-- Step 2: fit the random projection matrix
SELECT * FROM TD_RandomProjectionFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_rp_model)       -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required; explicit columns or range
        NumComponents(10)                             -- required: target number of dimensions
                                                      -- use TD_RandomProjectionMinComponents to find minimum
        Seed(42)                                      -- optional: non-negative integer for reproducibility
                                                      -- default: non-deterministic
        Epsilon(0.1)                                  -- optional: distortion tolerance, range (0,1)
                                                      -- default: 0.1
        ProjectionMethod('GAUSSIAN')                  -- optional: 'GAUSSIAN' or 'SPARSE'; default: 'GAUSSIAN'
        Density(0.33333333)                           -- optional: ratio of non-zero elements in matrix
                                                      -- only used with ProjectionMethod('SPARSE')
                                                      -- range: (0,1]; default: 0.33333333
        OutputFeatureNamesPrefix('td_rpj_feature')    -- optional: prefix for output column names
                                                      -- default: 'td_rpj_feature'
) AS t;

SELECT * FROM TD_RandomProjectionTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_RandomProjectionFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_RowNormalizeFit / TD_RowNormalizeTransform

```sql
-- Default: UNITVECTOR normalization
SELECT * FROM TD_RowNormalizeFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_rownorm_model)  -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required; explicit columns or range e.g. '[1:5]'
        Approach('UNITVECTOR')                        -- optional; default: 'UNITVECTOR'
                                                      -- 'UNITVECTOR'  — X' = X / sqrt(Σ Xi²)
                                                      -- 'FRACTION'    — X' = X / Σ Xi
                                                      -- 'PERCENTAGE'  — X' = X*100 / Σ Xi
                                                      -- 'INDEX'       — X' = V + ((X - B) / B) * 100
) AS t;

-- INDEX approach: requires BaseColumn and BaseValue together
SELECT * FROM TD_RowNormalizeFit(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2', 'col3')
        Approach('INDEX')
        BaseColumn('base_col')                        -- required with INDEX: column containing B values
        BaseValue(100)                                -- required with INDEX: V value in formula
) AS t;

SELECT * FROM TD_RowNormalizeTransform(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY order_col
    ON { db.fit_table | (SELECT * FROM TD_RowNormalizeFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_ScaleFit / TD_ScaleTransform

```sql
-- Dense input, no partition (most common)
SELECT * FROM TD_ScaleFit(
    ON { db.table | db.view | (query) } AS InputTable
    OUT VOLATILE TABLE OutputTable(my_scale_model)    -- optional; PERMANENT or VOLATILE
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required for dense; explicit columns or range
        ScaleMethod('STD')                            -- required; one method for all cols, or one per col
                                                      -- options: MEAN, SUM, USTD, STD, RANGE,
                                                      --          MIDRANGE, MAXABS,
                                                      --          RESCALE({lb=0,ub=1})
                                                      --          RESCALE({lb=0})  — lower bound only
                                                      --          RESCALE({ub=1})  — upper bound only
        MissValue('KEEP')                             -- optional: KEEP (default), ZERO, LOCATION
        GlobalScale('false')                          -- optional: scale all cols together; default 'false'
        Multiplier('1')                               -- optional: one or one per col; default 1
        Intercept('0')                                -- optional: one or one per col; default 0
                                                      -- accepts: number, min, mean, max e.g. '-min'
        IgnoreInvalidLocationScale('false')           -- optional: replace bad location/scale with 0/1
                                                      -- default: 'false'
) AS t;

-- Sparse input, no partition
SELECT * FROM TD_ScaleFit(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        AttributeNameColumn('attr_name_col')          -- required for sparse: column with attribute names
        AttributeValueColumn('attr_value_col')        -- required for sparse: column with attribute values
        ScaleMethod('STD')
        TargetAttributes('attr1', 'attr2')            -- optional: which attributes to scale (default: all)
        MissValue('KEEP')
) AS t;

-- Dense input, with partition
SELECT * FROM TD_ScaleFit(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY partition_col
    ON { db.param_table | db.view | (query) } AS ParameterTable PARTITION BY partition_col  -- optional
    ON { db.attr_table  | db.view | (query) } AS AttributeTable PARTITION BY partition_col  -- optional
    USING
        TargetColumns('col1', 'col2', 'col3')
        ScaleMethod('STD')
        PartitionColumns('partition_col')             -- required if PARTITION BY cols contain UNICODE
                                                      -- must match PARTITION BY cols; range NOT supported
        UnusedAttributes('UNSCALED')                  -- optional: dense + AttributeTable only
                                                      -- UNSCALED (default) or NULLIFY
) AS t;

-- TD_ScaleTransform — dense, no partition
SELECT * FROM TD_ScaleTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_ScaleFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;

-- TD_ScaleTransform — dense, with partition (both tables partition on same column)
SELECT * FROM TD_ScaleTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY partition_col
    ON { db.fit_table | (SELECT * FROM TD_ScaleFit(...)) } AS FitTable PARTITION BY partition_col
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;

-- TD_ScaleTransform — sparse, no partition
SELECT * FROM TD_ScaleTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_ScaleFit(...)) } AS FitTable DIMENSION
    USING
        AttributeNameColumn('attr_name_col')          -- required for sparse
        AttributeValueColumn('attr_value_col')        -- required for sparse
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;

-- TD_ScaleTransform — sparse, with partition
SELECT * FROM TD_ScaleTransform(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY partition_col
    ON { db.fit_table | (SELECT * FROM TD_ScaleFit(...)) } AS FitTable PARTITION BY partition_col
    USING
        AttributeNameColumn('attr_name_col')          -- required for sparse
        AttributeValueColumn('attr_value_col')        -- required for sparse
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

### TD_TargetEncodingFit / TD_TargetEncodingTransform

```sql
-- CBM_BETA: binary classification (response values are 0 or 1)
SELECT * FROM TD_TargetEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.category_table | db.view | (query) } AS CategoryTable DIMENSION
    OUT VOLATILE TABLE OutputTable(my_te_model)       -- optional; PERMANENT or VOLATILE
    USING
        EncoderMethod('CBM_BETA')                     -- binary classification
        TargetColumns('cat_col1', 'cat_col2')         -- required; explicit columns or range; max 2018
        ResponseColumn('target_col')                  -- required: column with response values (0 or 1)
        AlphaPrior(1.0)                               -- optional: prior parameter for CBM_BETA
        BetaPrior(1.0)                                -- optional: prior parameter for CBM_BETA
        DefaultValues(0)                              -- optional: value for unseen categories in Transform
                                                      -- single value or one per target column
) AS t;

-- CBM_DIRICHLET: multiclass classification (response values are 1,...,k)
SELECT * FROM TD_TargetEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.category_table | db.view | (query) } AS CategoryTable DIMENSION
    USING
        EncoderMethod('CBM_DIRICHLET')                -- multiclass classification
        TargetColumns('cat_col1', 'cat_col2')
        ResponseColumn('target_col')                  -- column with class values (1,...,k)
        NumDistinctResponses(3)                       -- required with CBM_DIRICHLET: number of classes
        AlphaPriors(1.0, 1.0, 1.0)                   -- optional: one prior per class (must match NumDistinctResponses)
        DefaultValues(0)
) AS t;

-- CBM_GAUSSIAN_INVERSE_GAMMA: regression (response values are continuous numeric)
SELECT * FROM TD_TargetEncodingFit(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.category_table | db.view | (query) } AS CategoryTable DIMENSION
    USING
        EncoderMethod('CBM_GAUSSIAN_INVERSE_GAMMA')   -- regression
        TargetColumns('cat_col1', 'cat_col2')
        ResponseColumn('target_col')                  -- column with continuous response values
        U0Prior(0.0)                                  -- optional: prior parameters
        V0Prior(1.0)
        Alpha0Prior(1.0)
        Beta0Prior(1.0)
        DefaultValues(0)
) AS t;

SELECT * FROM TD_TargetEncodingTransform(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.fit_table | (SELECT * FROM TD_TargetEncodingFit(...)) } AS FitTable DIMENSION
    USING
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```
