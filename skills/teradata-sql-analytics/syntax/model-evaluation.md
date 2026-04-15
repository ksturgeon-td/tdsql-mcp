# Teradata Model Evaluation & Explainability

Functions for splitting data, evaluating trained model performance, and explaining predictions.

> **Tip:** If TD_ClassificationEvaluator reveals poor recall on a minority class, consider applying `TD_SMOTE` (synthetic minority oversampling) in your data preparation step before retraining. See `data-prep` topic.

---

## Data Splitting

### TD_TrainTestSplit

Splits input data into train and test sets by tagging each row with `TD_IsTrainRow`. Supports stratified splits to preserve class proportions, and reproducible splits via `Seed`.

```sql
SELECT * FROM TD_TrainTestSplit(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY [ ORDER BY col [,...] ] ]
    USING
        [ IDColumn('id_col') ]           -- required when Seed is specified; ensures deterministic output across runs
        [ TrainSize(0.75) ]              -- default 0.75; range (0, 1)
        [ TestSize(0.25) ]               -- default 0.25; range (0, 1)
                                         -- TrainSize + TestSize must equal 1.0 if both specified
        [ Seed(seed) ]                   -- integer; range [0, INT_MAX]; omit for a different random split each run
        [ StratifyColumn('col') ]        -- stratified split preserving class proportions; column cannot have NULLs
                                         -- TrainSize and TestSize must each be > number of classes when using stratify
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `TD_IsTrainRow` | BYTEINT | `1` = train row, `0` = test row |
| `<all input columns>` | same as input | All columns copied from InputTable |

> **SQL alternative:** The Teradata `SAMPLE` clause provides a simpler option for basic random splits without function overhead:
> ```sql
> -- 75% train / 25% test using SAMPLE
> SELECT *, 1 AS TD_IsTrainRow FROM db.table SAMPLE 0.75
> UNION ALL
> SELECT *, 0 AS TD_IsTrainRow FROM db.table SAMPLE 0.25;
> ```
> Use `TD_TrainTestSplit` when you need stratification, reproducibility via `Seed`, or a tagged output for downstream filtering.

---

## Supervised Model Evaluation

### TD_ClassificationEvaluator

Evaluates a classification model by computing per-class precision, recall, F1, and support from a table of observed and predicted labels. Produces a confusion-matrix-style primary output and an aggregate metrics secondary output.

```sql
SELECT * FROM TD_ClassificationEvaluator(
    ON { db.table | db.view | (query) } AS InputTable
    [ OUT [ PERMANENT | VOLATILE ] TABLE OutputTable(db.output_table) ]
    USING
        ObservationColumn('actual_col')              -- required; actual class labels
        PredictionColumn('predicted_col')            -- required; predicted class labels
        { NumLabels(n) | Labels('label1'[,...]) }    -- required; mutually exclusive
) AS t;
```

**Primary output** (per-class metrics — one row per label):

| Column | Type | Description |
|--------|------|-------------|
| `SeqNum` | INTEGER | Row sequence number |
| `Prediction` | VARCHAR | Predicted label for this row |
| `Mapping` | VARCHAR | Label mapping used |
| `Class_N` | BIGINT | One column per label — confusion matrix counts |
| `Precision` | REAL | Positive predictive value: TP / (TP + FP) |
| `Recall` | REAL | Sensitivity: TP / (TP + FN) |
| `F1` | REAL | Harmonic mean of Precision and Recall |
| `Support` | BIGINT | Count of actual occurrences of this label in ObservationColumn |

**Secondary output** (OUT TABLE — aggregate metrics):

| Column | Type | Description |
|--------|------|-------------|
| `SeqNum` | INTEGER | Row sequence number |
| `Metric` | VARCHAR | Metric name |
| `MetricValue` | REAL | Metric value |

---

### TD_RegressionEvaluator

Evaluates a regression model by computing a configurable set of error and fit metrics from a table of observed and predicted values. Returns results in wide format — one column per requested metric.

```sql
SELECT * FROM TD_RegressionEvaluator(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        ObservationColumn('actual_col')              -- required; actual observed values
        PredictionColumn('predicted_col')            -- required; model predicted values
        [ Metrics('MAE'[,'MSE','RMSE',...]) ]        -- optional; default: all metrics returned
        [ NumOfIndependentVariables(n) ]             -- required with AR2; ignored otherwise
        [ DegreesOfFreedom(df1, df2) ]               -- required with FSTAT; ignored otherwise
) AS t;
```

**Available metrics:**

| Metric | Description |
|--------|-------------|
| `MAE` | Mean Absolute Error |
| `MSE` | Mean Squared Error |
| `MSLE` | Mean Squared Log Error |
| `MAPE` | Mean Absolute Percentage Error |
| `MPE` | Mean Percentage Error |
| `RMSE` | Root Mean Squared Error |
| `RMSLE` | Root Mean Squared Log Error |
| `R2` | R-Squared |
| `AR2` | Adjusted R-Squared; requires `NumOfIndependentVariables` |
| `EV` | Explained Variation |
| `ME` | Maximum (worst-case) Error |
| `MPD` | Mean Poisson Deviance |
| `MGD` | Mean Gamma Deviance |
| `FSTAT` | F-test; requires `DegreesOfFreedom(df1, df2)`; expands to four columns (see below) |

**Output** — wide format, one column per requested metric:

| Column | Type | Description |
|--------|------|-------------|
| `<metric_name>` | FLOAT | One column per metric specified in `Metrics` |
| `F_score` | FLOAT | [FSTAT only] F-test statistic |
| `F_Criticalvalue` | FLOAT | [FSTAT only] Critical F value at alpha=95% |
| `P_value` | FLOAT | [FSTAT only] Probability value associated with F_score |
| `F_conclusion` | VARCHAR | [FSTAT only] `'reject null hypothesis'` or `'fail to reject null hypothesis'` |

---

### TD_ROC

Computes ROC curve values (threshold, TPR, FPR) across a range of classification thresholds. Optionally computes AUC and Gini coefficient. Supports multiple models/partitions in a single call via `ModelIDColumn`.

```sql
SELECT * FROM TD_ROC(
    ON { db.table | db.view | (query) } AS InputTable
    [ OUT [ VOLATILE | PERMANENT ] TABLE OutputTable(db.output_table) ]
    USING
        ProbabilityColumn('prob_col')                -- required; predicted probability of positive class
        ObservationColumn('actual_col')              -- required; actual class labels
        [ ModelIDColumn('model_id_col') ]            -- optional; evaluate multiple models/partitions in one call
        [ PositiveLabel('1') ]                       -- default 1; positive class label
        [ NumThresholds(50) ]                        -- default 50; range [1, 10000]; uniformly distributed [0, 1]
        [ AUC('false') ]                             -- default false; append AUC column to output
        [ Gini('false') ]                            -- default false; append Gini coefficient column to output
) AS t;
```

**Output columns** (per-threshold ROC curve, written to OUT TABLE):

| Column | Type | Description |
|--------|------|-------------|
| `Model_id` | varies | Model/partition identifier; only present when `ModelIDColumn` specified |
| `Threshold` | REAL | Classification threshold value |
| `TPR` | REAL | True Positive Rate at this threshold: correctly predicted positives / total positives |
| `FPR` | REAL | False Positive Rate at this threshold: incorrectly predicted positives / total negatives |
| `AUC` | REAL | Area under the ROC curve; only present when `AUC('true')` |
| `GINI` | REAL | Gini coefficient; only present when `Gini('true')`; 0 = equal, closer to 1 = more unequal |

---

## Unsupervised Model Evaluation

### TD_Silhouette

Evaluates clustering quality by computing silhouette scores — a measure of how well each point fits its assigned cluster relative to other clusters. Typically used after TD_KMeans. Supports three output granularities.

```sql
SELECT * FROM TD_Silhouette(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        IdColumn('id_col')                           -- required; unique row identifier
        ClusterIdColumn('cluster_id_col')            -- required; assigned cluster ID per row (e.g. from TD_KMeans)
        TargetColumns({ 'col' | col_range }[,...])   -- required; same feature columns used for clustering
        [ OutputType('SCORE'|'CLUSTER_SCORES'|'SAMPLE_SCORES') ]  -- default 'SCORE'
        [ Accumulate({ 'col' | col_range }[,...]) ]  -- SAMPLE_SCORES only
) AS t;
```

**Output — `SCORE` (default)** — single overall score:

| Column | Type | Description |
|--------|------|-------------|
| `Silhouette_Score` | REAL | Mean Silhouette Coefficient across all samples; range [-1, 1]; higher = better-defined clusters |

**Output — `CLUSTER_SCORES`** — one row per cluster:

| Column | Type | Description |
|--------|------|-------------|
| `clusterid_column` | BYTEINT/SMALLINT/INTEGER/BIGINT | Cluster identifier |
| `Silhouette_Score` | REAL | Mean silhouette score for this cluster |

**Output — `SAMPLE_SCORES`** — one row per input point:

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Row identifier |
| `clusterid_column` | BYTEINT/SMALLINT/INTEGER/BIGINT | Cluster assigned to this point |
| `A_i` | REAL | Mean distance to other points in the same cluster |
| `B_i` | REAL | Minimum mean distance to points in any other cluster |
| `Silhouette_Score` | REAL | Score for this point: (B_i - A_i) / max(A_i, B_i) |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---

## Model Explainability

### TD_SHAP

Computes Shapley values (SHAP) to explain the contribution of each feature to individual predictions. Works with TD_GLM, TD_DecisionForest, and TD_XGBoost models. Produces per-sample feature contributions (primary output) and global mean absolute feature importance (GlobalExplanation OUT TABLE).

```sql
SELECT * FROM TD_SHAP(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    OUT [ PERMANENT | VOLATILE ] TABLE GlobalExplanation(db.global_table)  -- required
    USING
        IDColumn('id_col')                                           -- required; row identifier
        TrainingFunction('td_glm'|'td_decisionforest'|'td_xgboost') -- required; must match model source
        InputColumns({ 'col' | col_range }[,...])                    -- required; must exactly match training column names and case
        [ ModelType('Regression'|'Classification') ]                 -- default 'Regression'
        [ Detailed('false') ]                                        -- default false; TD_DecisionForest/TD_XGBoost only
                                                                     -- outputs per-tree SHAP values; 'Final' row = aggregated
        [ NumParallelTrees(1000) ]                                   -- default 1000; TD_DecisionForest/TD_XGBoost only
        [ NumBoostRounds(3) ]                                        -- default 3; TD_XGBoost only
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

> **Performance note:** TD_SHAP parses all branches of every tree — execution time is heavily impacted by model size. Recommended for explainability on small datasets. For large tree models, reduce `NumParallelTrees` and `NumBoostRounds` to limit scope.

**Primary output** (per-sample SHAP values — one row per input row):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Row identifier |
| `accumulate_column(s)` | any | Columns copied from InputTable |
| `<input_columns>` | DOUBLE PRECISION | SHAP value per feature — contribution to prediction |
| `label` | INTEGER | [Classification only] Class label |
| `tree_num` | VARCHAR | [When `Detailed('true')`, tree models only] task_index + tree_num; `'Final'` = aggregated |
| `iter_num` | INTEGER | [When `Detailed('true')`, TD_XGBoost only] Iteration number |

**Secondary output — GlobalExplanation** (OUT TABLE — mean absolute SHAP per feature):

| Column | Type | Description |
|--------|------|-------------|
| `<input_columns>` | DOUBLE PRECISION | Mean absolute SHAP value per feature — global feature importance |
| `label` | INTEGER | [TD_DecisionForest / TD_XGBoost classification only] Class label |
