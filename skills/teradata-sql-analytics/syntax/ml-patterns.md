# Teradata ML Pipeline Patterns

Common patterns for assembling Teradata ML functions into end-to-end workflows. These patterns assume familiarity with individual functions — see `ml-functions`, `data-prep`, `model-evaluation`, and `fit-transform-pattern` topics for syntax details.

---

## 1. The Prediction Pipeline — CTE Pattern

The most powerful operationalization pattern: wrap all preprocessing (via `TD_ColumnTransformer` + saved FitTables) in a CTE, then feed the CTE directly into a Predict function. One query — no intermediate tables.

```sql
WITH transformed AS (
    SELECT id, feat1, feat2, feat3_encoded, feat4_scaled, target_col
    FROM TD_ColumnTransformer(
        ON db.new_data AS InputTable

        ON db.impute_fit     AS ImputeFitTable       DIMENSION   -- saved TD_ScaleFit / TD_SimpleImputer output
        ON db.outlier_fit    AS OutlierFitTable       DIMENSION   -- saved TD_OutlierFilterFit output
        ON db.encoding_fit   AS OneHotEncodingFitTable DIMENSION  -- saved TD_OneHotEncodingFit output
        ON db.scale_fit      AS ScaleFitTable         DIMENSION   -- saved TD_ScaleFit output
    ) AS t
)
SELECT * FROM TD_GLMPredict(
    ON transformed AS InputTable
    ON db.my_model AS ModelTable DIMENSION
    USING
        IDColumn('id')
        Accumulate('target_col')   -- pass through actual label for side-by-side comparison
) AS dt;
```

> **Why this works:** `TD_ColumnTransformer` accepts up to 10 named FitTable DIMENSION inputs and applies all transforms in one pass. The CTE result is a clean feature set that feeds directly into any Predict function. FitTables must be **persistent named tables** — not subqueries.

**Swap the Predict function for any Train/Predict pair:**
```sql
-- XGBoost scoring pipeline
SELECT * FROM TD_XGBoostPredict(
    ON transformed AS InputTable
    ON db.xgb_model AS ModelTable DIMENSION
    USING IDColumn('id') Accumulate('target_col')
) AS dt;

-- Decision Forest scoring pipeline
SELECT * FROM TD_DecisionForestPredict(
    ON transformed AS InputTable
    ON db.forest_model AS ModelTable DIMENSION
    USING IDColumn('id') Accumulate('target_col')
) AS dt;
```

**Building the FitTables (one-time setup):**
```sql
-- Run each Fit function once on training data and persist the output
CREATE TABLE db.scale_fit AS (
    SELECT * FROM TD_ScaleFit(
        ON db.training_data PARTITION BY ANY
        USING TargetColumns('feat1', 'feat2', 'feat3') ScaleMethod('STD')
    ) AS t
) WITH DATA;

-- Then reference db.scale_fit in TD_ColumnTransformer indefinitely
```

---

## 2. Elbow Method — Choosing K for KMeans

Run TD_KMeans for a range of K values in a single query using `UNION ALL`. Plot or analyze the resulting WCSS curve to identify the elbow — the point where adding another cluster yields diminishing returns.

```sql
SELECT COUNT(*) AS k, SUM(td_withinss_kmeans) AS wcss
FROM TD_KMeans(
    ON db.scaled_data AS InputTable
    USING
        IdColumn('id')
        TargetColumns('feat1', 'feat2', 'feat3', 'feat4')
        NumClusters(2)
        MaxIterNum(500)
        StopThreshold(0.0395)
) AS t
WHERE td_withinss_kmeans IS NOT NULL

UNION ALL

SELECT COUNT(*) AS k, SUM(td_withinss_kmeans) AS wcss
FROM TD_KMeans(
    ON db.scaled_data AS InputTable
    USING
        IdColumn('id')
        TargetColumns('feat1', 'feat2', 'feat3', 'feat4')
        NumClusters(3)
        MaxIterNum(500)
        StopThreshold(0.0395)
) AS t
WHERE td_withinss_kmeans IS NOT NULL

UNION ALL

SELECT COUNT(*) AS k, SUM(td_withinss_kmeans) AS wcss
FROM TD_KMeans(
    ON db.scaled_data AS InputTable
    USING
        IdColumn('id')
        TargetColumns('feat1', 'feat2', 'feat3', 'feat4')
        NumClusters(4)
        MaxIterNum(500)
        StopThreshold(0.0395)
) AS t
WHERE td_withinss_kmeans IS NOT NULL;
```

**How it works:**
- `td_withinss_kmeans` is a column on the primary TD_KMeans output; centroid rows carry a non-NULL WCSS value, other output rows are NULL
- `WHERE td_withinss_kmeans IS NOT NULL` isolates one row per cluster centroid
- `COUNT(*) AS k` = number of clusters for this run; `SUM(td_withinss_kmeans)` = total WCSS
- Extend the `UNION ALL` chain to as many K values as needed (e.g., K=2 through K=10)

**Interpreting the result:**

| k | wcss |
|---|------|
| 2 | 8420 |
| 3 | 3210 |
| 4 | 1850 |
| 5 | 1780 |
| 6 | 1760 |

The elbow is at K=4 — large WCSS drop from 3→4, then flat from 4→5+. The result set can be plotted externally or slope-analyzed in SQL using window functions (`LAG` to compute delta WCSS per step).

> **Tip:** Always scale your input features before running KMeans (`TD_ScaleFit` / `TD_ScaleTransform` or the manual Z-score pattern). Unscaled features with different value ranges will dominate the distance calculation.

---

## 3. Train → Evaluate → Retrain Loop

The standard supervised learning iteration cycle. Split once with a fixed seed, then retrain and evaluate as many times as needed without re-splitting.

```sql
-- Step 1: Split — tag rows as train (1) or test (0), persist the split
CREATE TABLE db.data_split AS (
    SELECT * FROM TD_TrainTestSplit(
        ON db.labeled_data PARTITION BY ANY
        USING
            IDColumn('id')
            TrainSize(0.75)
            TestSize(0.25)
            Seed(42)
            StratifyColumn('label')   -- preserve class proportions; omit if not needed
    ) AS t
) WITH DATA;

-- Step 2: Train on training rows
CREATE TABLE db.my_model AS (
    SELECT * FROM TD_XGBoost(
        ON (SELECT * FROM db.data_split WHERE TD_IsTrainRow = 1) AS InputTable
        USING
            IDColumn('id')
            ResponseColumn('label')
            InputColumns('feat1', 'feat2', 'feat3')
            MaxDepth(6)
            NumBoostedRounds(50)
    ) AS t
) WITH DATA;

-- Step 3: Score test rows
CREATE VOLATILE TABLE predictions AS (
    SELECT * FROM TD_XGBoostPredict(
        ON (SELECT * FROM db.data_split WHERE TD_IsTrainRow = 0) AS InputTable
        ON db.my_model AS ModelTable DIMENSION
        USING IDColumn('id') Accumulate('label')
    ) AS t
) WITH DATA ON COMMIT PRESERVE ROWS;

-- Step 4: Evaluate
SELECT * FROM TD_ClassificationEvaluator(
    ON predictions AS InputTable
    USING
        ObservationColumn('label')
        PredictionColumn('td_prediction')
        NumLabels(2)
) AS t;
```

**Retrain loop:** adjust hyperparameters or features, drop and recreate `db.my_model`, re-score and re-evaluate against the same `db.data_split`. The test set stays locked — no leakage.

> **When to iterate:** if `TD_ClassificationEvaluator` shows poor recall on the minority class, consider applying `TD_SMOTE` to the training set before retraining — see the Class Imbalance Workflow below. Use `TD_SHAP` after the final model to understand feature contributions before deploying.

---

## 4. Class Imbalance Workflow

When the minority class is rare, split first — then oversample the training set only. Oversampling before splitting leaks synthetic samples into the test set and inflates evaluation metrics.

```sql
-- Step 1: Split first (locks test set — do not touch it again)
CREATE TABLE db.data_split AS (
    SELECT * FROM TD_TrainTestSplit(
        ON db.labeled_data PARTITION BY ANY
        USING
            IDColumn('id')
            TrainSize(0.80)
            Seed(42)
            StratifyColumn('label')
    ) AS t
) WITH DATA;

-- Step 2: Oversample minority class in train set only
CREATE TABLE db.train_augmented AS (
    -- Original training rows
    SELECT id, feat1, feat2, feat3, label
    FROM db.data_split WHERE TD_IsTrainRow = 1

    UNION ALL

    -- Synthetic minority samples — generated from training rows only
    SELECT id, feat1, feat2, feat3, label
    FROM TD_SMOTE(
        ON (SELECT * FROM db.data_split WHERE TD_IsTrainRow = 1) PARTITION BY ANY
        USING
            IDColumn('id')
            ResponseColumn('label')
            InputColumns('feat1', 'feat2', 'feat3')
            MinorityClass('1')
            OversamplingFactor(4)
            Seed(42)
    ) AS t
) WITH DATA;

-- Step 3: Train on augmented training set
CREATE TABLE db.my_model AS (
    SELECT * FROM TD_XGBoost(
        ON db.train_augmented AS InputTable
        USING
            IDColumn('id')
            ResponseColumn('label')
            InputColumns('feat1', 'feat2', 'feat3')
            NumBoostedRounds(50)
    ) AS t
) WITH DATA;

-- Step 4: Evaluate on original (unaugmented) test set
SELECT * FROM TD_ClassificationEvaluator(
    ON (
        SELECT * FROM TD_XGBoostPredict(
            ON (SELECT * FROM db.data_split WHERE TD_IsTrainRow = 0) AS InputTable
            ON db.my_model AS ModelTable DIMENSION
            USING IDColumn('id') Accumulate('label')
        ) AS t
    ) AS InputTable
    USING
        ObservationColumn('label')
        PredictionColumn('td_prediction')
        NumLabels(2)
) AS t;
```

> **Key rule:** SMOTE on the train split only, evaluate on the original test split only. Synthetic samples should never appear in the test set.

---

## 5. Micromodeling Pipeline — TD_GLM

Train one model per partition in parallel, then score new data partition-by-partition using the same key. Best for cases where distinct segments (regions, products, customer tiers) are better modeled independently.

```sql
-- Step 1: Train — one model per partition_key value, in parallel
CREATE TABLE db.micro_models AS (
    SELECT * FROM TD_GLM(
        ON db.training_data PARTITION BY partition_key
        USING
            InputColumns('feat1', 'feat2', 'feat3')
            ResponseColumn('target')
            Family('Gaussian')
            MaxIterNum(100)
    ) AS t
) WITH DATA;

-- Step 2: Score — ModelTable uses PARTITION BY (not DIMENSION) to match partitions
SELECT * FROM TD_GLMPredict(
    ON db.new_data AS InputTable PARTITION BY partition_key
    ON db.micro_models AS ModelTable PARTITION BY partition_key
    USING
        IDColumn('id')
        Accumulate('partition_key', 'target')
) AS t;
```

**Key structural difference vs. global model:**

| | Global Model | Micromodel |
|---|---|---|
| Train `InputTable` | `PARTITION BY ANY` | `PARTITION BY key` |
| `ModelTable` in Predict | `DIMENSION` | `PARTITION BY key` |
| Models produced | 1 | 1 per partition value |

> **When to use micromodeling:** when you have a natural segmentation variable (e.g., region, product category, store ID) and you expect the relationship between features and target to differ meaningfully across segments. Each partition trains and scores fully independently — Vantage runs them in parallel across AMPs.
