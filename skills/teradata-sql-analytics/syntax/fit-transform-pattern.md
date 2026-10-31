# Teradata Fit/Transform Pattern

Many Teradata native analytic functions follow a two-phase pattern:

- **Fit**: Runs against training data and outputs a "model" — a result set of learned parameters.
- **Transform**: Takes new input data plus the Fit output, applies the learned transformation.

This separation allows the model to be trained once and reused across many datasets, environments,
or time periods without re-running the Fit step.

---

## Model Storage Options

The output of a Fit function is a standard result set and can be stored or passed in three ways. Many Fit functions also support an `OUT TABLE` clause that writes the model directly, without a wrapping `CREATE TABLE AS`:

```sql
SELECT * FROM TD_SomeFit(
    ON db.training_data AS InputTable PARTITION BY ANY
    OUT [ PERMANENT | VOLATILE ] TABLE OutputTable(db.my_model)
    USING TargetColumns('col1', 'col2')
) AS t;
```

See the individual function's syntax in `data-prep` or `data-cleaning` for whether it supports `OUT TABLE`. The three retrieval patterns below apply regardless of how the model was stored.

### 1. Dedicated table per model
```sql
-- Store the Fit output as its own table
CREATE TABLE db.my_model AS (
    SELECT * FROM TD_SomeFit(
        ON db.training_data AS InputTable PARTITION BY ANY
        USING TargetColumns('col1', 'col2')
    ) AS t
) WITH DATA;

-- Apply it: Transform does not take TargetColumns; the Fit model supplies them
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON db.my_model AS FitTable DIMENSION
    USING Accumulate('id_col')              -- optional; use IDColumns for TD_FunctionTransform
) AS t;
```

### 2. Shared model registry table (governed workflow)
```sql
-- Insert fit result into registry with model identifier (model_id must come first)
INSERT INTO db.model_registry
SELECT 'outlier_model_v1' AS model_id, t.*
FROM TD_SomeFit(
    ON db.training_data AS InputTable PARTITION BY ANY
    USING TargetColumns('col1', 'col2')
) AS t;

-- Project the Fit columns by name — SELECT * would pass model_id to the function and fail
-- (the first column in FitTable must be the function's internal stat-type column, e.g. TD_STATTYPE_SCLFIT)
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON (SELECT <fit_stat_col>, col1, col2    -- list Fit output columns by name, not SELECT *
        FROM db.model_registry
        WHERE model_id = 'outlier_model_v1') AS FitTable DIMENSION
    USING Accumulate('id_col')
) AS t;
```

This pattern enables enterprise ML governance:
- Models treated as first-class data assets
- Full lineage, versioning, and history in a single table
- Swap model versions by changing the filter — no code changes needed

### 3. Inline subquery (no persistence)
```sql
-- Pass the Fit result directly into Transform as a subquery
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON (
        SELECT * FROM TD_SomeFit(
            ON db.training_data AS InputTable PARTITION BY ANY
            USING TargetColumns('col1', 'col2')
        ) AS t
    ) AS FitTable DIMENSION
    USING Accumulate('id_col')
) AS t;
```

Useful for one-off transformations where persisting the model is not needed.

---

## Known Fit/Transform Pairs

| Fit | Transform | Purpose |
|-----|-----------|---------|
| `TD_OutlierFilterFit` | `TD_OutlierFilterTransform` | Detect and remove outliers |
| `TD_SimpleImputeFit` | `TD_SimpleImputeTransform` | Impute missing values |
| `TD_ScaleFit` | `TD_ScaleTransform` | Normalize / scale numeric columns |
| `TD_BinCodeFit` | `TD_BinCodeTransform` | Bin numeric columns (equal-width or variable-width) |
| `TD_FunctionFit` | `TD_FunctionTransform` | Apply a mathematical transform from a TransformationTable |
| `TD_NonLinearCombineFit` | `TD_NonLinearCombineTransform` | Compute nonlinear formula combinations of columns |
| `TD_OneHotEncodingFit` | `TD_OneHotEncodingTransform` | One-hot encode categorical columns |
| `TD_OrdinalEncodingFit` | `TD_OrdinalEncodingTransform` | Ordinal-encode categorical columns |
| `TD_PolynomialFeaturesFit` | `TD_PolynomialFeaturesTransform` | Generate polynomial and interaction features |
| `TD_RowNormalizeFit` | `TD_RowNormalizeTransform` | Normalize rows by a learned scale (UNITVECTOR, FRACTION, etc.) |
| `TD_TargetEncodingFit` | `TD_TargetEncodingTransform` | Target-encode categorical columns (requires CategoryTable) |
| `TD_RandomProjectionFit` | `TD_RandomProjectionTransform` | Reduce dimensionality via random projection (wide tables) |

See also `TD_ColumnTransformer` in `data-prep`, which applies several fitted transforms in a single pass.

---

## Key Notes

- The Fit output schema must match what the Transform function expects on its `FitTable` input.
- For an unpartitioned Fit, the `FitTable` ON clause takes `DIMENSION`: the model is a small broadcast table.
- If the Fit was run with a partition or group column, both `InputTable` and `FitTable` are
  `PARTITION BY` that same column instead, and each group is transformed with its own model.
- Transform functions do not accept `TargetColumns` — the Fit model supplies them. The pass-through
  argument is `Accumulate` for most Transform functions and `IDColumns` for `TD_FunctionTransform`.
- The first column of the FitTable is a function-specific internal column (e.g. `TD_STATTYPE_SCLFIT`
  for `TD_ScaleFit`). When using the registry pattern, project Fit columns by name — `SELECT *`
  will include `model_id` as the first column and cause the function to fail.
- When using a shared registry, ensure the filter returns rows for only one model. At least for
  `TD_ScaleTransform`, mixing models raises error 9134 rather than silently producing wrong results.
