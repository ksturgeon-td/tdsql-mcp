# Teradata Fit/Transform Pattern

Many Teradata native analytic functions follow a two-phase pattern:

- **Fit**: Runs against training data and outputs a "model" — a result set of learned parameters.
- **Transform**: Takes new input data plus the Fit output, applies the learned transformation.

This separation allows the model to be trained once and reused across many datasets, environments,
or time periods without re-running the Fit step.

---

## Model Storage Options

The output of a Fit function is a standard result set and can be stored or passed in three ways:

### 1. Dedicated table per model
```sql
-- Store the Fit output as its own table
CREATE TABLE db.my_model AS (
    SELECT * FROM TD_SomeFit(
        ON db.training_data AS InputTable PARTITION BY ANY
        USING TargetColumns('col1', 'col2')
    ) AS t
) WITH DATA;

-- Reference it in Transform
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON db.my_model AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
) AS t;
```

### 2. Shared model registry table (governed workflow)
```sql
-- Insert multiple Fit results into a central registry with a model identifier
INSERT INTO db.model_registry
SELECT 'outlier_model_v1' AS model_id, t.*
FROM TD_SomeFit(
    ON db.training_data AS InputTable PARTITION BY ANY
    USING TargetColumns('col1', 'col2')
) AS t;

-- Transform filters the registry by model_id
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON (SELECT * FROM db.model_registry
        WHERE model_id = 'outlier_model_v1') AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
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
    ) AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
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

---

## Key Notes

- The Fit output schema must match what the Transform function expects on its `ModelTable` input.
- The `ModelTable` ON clause always takes `DIMENSION` — this tells Teradata the model is a small
  broadcast table, not a partitioned input.
- When using a shared registry, ensure the filter on `ModelTable` returns rows for only one model —
  mixing model rows will produce incorrect results.
