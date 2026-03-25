# Teradata Native Functions — Guidelines for Agents

## Always Prefer Native Functions Over Hand-Written SQL

Teradata Vantage has built-in distributed table operators for most analytics, ML, data preparation, and search operations. These functions run across all AMPs in parallel, are optimized for Vantage's architecture, and should **always** be used instead of equivalent hand-written SQL.

**Before writing any SQL for analytics, transformation, or ML: check this guide and the relevant syntax topic.**

---

## Minimize Data Movement — Critical at Teradata Scale

Teradata tables routinely contain billions to tens of billions of rows. The native functions in this library are designed to operate at that scale — but only if data stays on the platform. **Every row returned to the agent is a row that crossed the network, consumed session spool, and burned LLM context.** At Teradata scale, pulling data to the client for processing is not just inefficient — it is architecturally wrong.

### Rules for data movement minimization

**1. Never SELECT raw rows for analytics — summarize in-database**

```sql
-- WRONG: pulls millions of rows to agent for inspection
SELECT * FROM db.large_table;

-- RIGHT: compute the summary in-database, return only the result
SELECT * FROM TD_ColumnSummary(
    ON db.large_table AS InputTable PARTITION BY ANY
    USING TargetColumns('[1:20]')
) AS t;
```

**2. Use SAMPLE or TOP N when you need to see rows**

```sql
-- Explore structure and values without touching the full table
SELECT TOP 100 * FROM db.large_table SAMPLE 0.001;
```

**3. Filter before you function — push predicates as deep as possible**

```sql
-- WRONG: passes full table to function, then filters output
SELECT * FROM TD_UnivariateStatistics(...) AS t WHERE partition_col = 'X';

-- RIGHT: filter the input subquery so only relevant rows enter the function
SELECT * FROM TD_UnivariateStatistics(
    ON (SELECT * FROM db.large_table WHERE partition_col = 'X') AS InputTable
    ...
) AS t;
```

**4. Chain pipeline steps as CTEs — keep intermediate results in-database**

```sql
-- WRONG: agent runs Step 1, receives result, passes it back for Step 2
-- (two round trips; intermediate data crosses the network)

-- RIGHT: chain steps in a single query — data never leaves Teradata
WITH cleaned AS (
    SELECT * FROM TD_OutlierFilterTransform(
        ON db.raw_data AS InputTable PARTITION BY ANY
        ON db.outlier_fit AS FitTable DIMENSION
    ) AS t
),
transformed AS (
    SELECT * FROM TD_ColumnTransformer(
        ON cleaned AS InputTable
        ON db.scale_fit AS ScaleFitTable DIMENSION
    ) AS t
)
SELECT * FROM TD_XGBoostPredict(
    ON transformed AS InputTable
    ON db.model AS ModelTable DIMENSION
    USING IDColumn('id')
) AS dt;
```

**5. Persist large outputs with OUT TABLE — never stream model outputs back to the agent**

```sql
-- WRONG: streams the full model or large result set to the agent
SELECT * FROM TD_XGBoost( ON db.training_data ... ) AS t;

-- RIGHT: persist to a named table; agent receives only a status message
SELECT * FROM TD_XGBoost(
    ON db.training_data AS InputTable PARTITION BY ANY
    OUT PERMANENT TABLE ModelTable(db.my_model)
    USING ...
) AS t;
```

**6. Use execute_query with small max_rows for validation only**

`execute_query` is for checking results, previewing schemas, and validating output — not for analytics. Default `max_rows=100` exists for this reason. If you find yourself wanting to increase `max_rows` significantly to "process" data, that is a signal to use a native function instead.

**7. Aggregate before returning — let the database do the grouping**

```sql
-- WRONG: return all prediction rows to agent to count outcomes
SELECT * FROM TD_XGBoostPredict(...) AS t;

-- RIGHT: aggregate in-database, return summary
SELECT td_prediction, COUNT(*) AS n, AVG(confidence) AS avg_confidence
FROM TD_XGBoostPredict(...) AS t
GROUP BY td_prediction;
```

### Why this matters at scale

| Operation | 1M rows | 1B rows | 10B rows |
|-----------|---------|---------|----------|
| `SELECT *` to agent | slow | session-killing | impossible |
| `TD_ColumnSummary` | fast | fast | fast |
| CTE pipeline → result | fast | fast | fast |

Native functions distribute across all AMPs. The result set returned to the agent is always small — a model table, a metrics row, a summary. The compute scales with the platform; the data movement does not grow with table size.

---

## Common Operations → Native Function Mapping

### Data Exploration & Statistics

| Instead of this (manual SQL) | Use this (native function) | Topic |
|-------------------------------|---------------------------|-------|
| `SELECT col, COUNT(*), AVG(col), STDDEV(col)...` per column | `TD_ColumnSummary` | `data-exploration` |
| Manual percentile / histogram queries | `TD_UnivariateStatistics` | `data-exploration` |
| Manual histogram buckets with CASE | `TD_Histogram` | `data-exploration` |
| Manual quantile-quantile calculations | `TD_QQNorm` | `data-exploration` |
| Manual moving/rolling average with window functions | `TD_MovingAverage` | `data-exploration` |
| Manual Pearson correlation | `TD_Correlation` | `data-exploration` |

### Data Cleaning

| Instead of this (manual SQL) | Use this (native function) | Topic |
|-------------------------------|---------------------------|-------|
| Manual CASE-based outlier detection | `TD_OutlierFilterFit` / `TD_OutlierFilterTransform` | `data-cleaning` |
| Manual COALESCE / UPDATE for NULL fill | `TD_SimpleImputeFit` / `TD_SimpleImputeTransform` | `data-cleaning` |
| Manual ROW_NUMBER deduplication | Manual SQL pattern (ROW_NUMBER + QUALIFY) | `data-cleaning` |
| Find rows containing NULLs | `TD_GetRowsWithMissingValues` / `TD_GetRowsWithoutMissingValues` | `data-cleaning` |
| Identify low-variance / useless columns | `TD_GetFutileColumns` | `data-cleaning` |
| String fuzzy matching / distance | `StringSimilarity` | `data-cleaning` |
| Type conversion with defined rules | `TD_ConvertTo` | `data-cleaning` |

### Data Preparation & Feature Engineering

| Instead of this (manual SQL) | Use this (native function) | Topic |
|-------------------------------|---------------------------|-------|
| Manual Z-score: `(x - AVG) / STDDEV` | `TD_ScaleFit` / `TD_ScaleTransform` | `data-prep` |
| Manual min-max: `(x - min) / (max - min)` | `TD_ScaleFit` / `TD_ScaleTransform` (MinMax method) | `data-prep` |
| Manual L2 normalization | `TD_VectorNormalize(Approach('UNITVECTOR'))` | `data-prep` |
| Manual CASE-based binning | `TD_BinCodeFit` / `TD_BinCodeTransform` | `data-prep` |
| Manual one-hot encoding with CASE | `TD_OneHotEncodingFit` / `TD_OneHotEncodingTransform` | `data-prep` |
| Manual label encoding | `TD_OrdinalEncodingFit` / `TD_OrdinalEncodingTransform` | `data-prep` |
| Manual target encoding | `TD_TargetEncodingFit` / `TD_TargetEncodingTransform` | `data-prep` |
| Manual pivot / unpivot | `TD_Pivoting` / `TD_Unpivoting` | `data-prep` |
| Manual polynomial feature cross products | `TD_PolynomialFeaturesFit` / `TD_PolynomialFeaturesTransform` | `data-prep` |
| Manual SMOTE / class rebalancing | `TD_SMOTE` | `data-prep` |
| Applying multiple transforms separately | `TD_ColumnTransformer` (all in one pass) | `data-prep` |
| Manual row normalization | `TD_RowNormalizeFit` / `TD_RowNormalizeTransform` | `data-prep` |
| Manual non-linear feature transforms | `TD_FunctionFit` / `TD_FunctionTransform` | `data-prep` |
| Manual polynomial combinations | `TD_NonLinearCombineFit` / `TD_NonLinearCombineTransform` | `data-prep` |

### Machine Learning — Training

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| External gradient boosting (XGBoost) | `TD_XGBoost` / `TD_XGBoostPredict` | `ml-functions` |
| External random forest | `TD_DecisionForest` / `TD_DecisionForestPredict` | `ml-functions` |
| External GLM / logistic / linear regression | `TD_GLM` / `TD_GLMPredict` | `ml-functions` |
| External K-means clustering | `TD_KMeans` / `TD_KMeansPredict` | `ml-functions` |
| External KNN | `TD_KNN` | `ml-functions` |
| External SVM | `TD_SVM` / `TD_SVMPredict` | `ml-functions` |
| External naive Bayes | `TD_NaiveBayes` / `TD_NaiveBayesPredict` | `ml-functions` |
| External anomaly detection | `TD_OneClassSVM` / `TD_OneClassSVMPredict` | `ml-functions` |

### Model Evaluation

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| Manual train/test row tagging | `TD_TrainTestSplit` | `model-evaluation` |
| Manual confusion matrix | `TD_ClassificationEvaluator` | `model-evaluation` |
| Manual MAE / RMSE / R² calculations | `TD_RegressionEvaluator` | `model-evaluation` |
| Manual ROC curve | `TD_ROC` | `model-evaluation` |
| Manual silhouette score | `TD_Silhouette` | `model-evaluation` |
| Manual feature importance | `TD_SHAP` | `model-evaluation` |

### Text Analytics

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| Manual tokenization / n-gram splitting | `TD_NgramSplitter` | `text-analytics` |
| External text classification | `TD_NaiveBayesTextClassifierTrainer` / `Predict` | `text-analytics` |
| External NER | `TD_NERExtractor` | `text-analytics` |
| External sentiment analysis | `TD_SentimentExtractor` | `text-analytics` |
| External stemming / lemmatization | `TD_TextMorph` | `text-analytics` |
| External TF-IDF | `TD_TFIDF` | `text-analytics` |
| External word embeddings | `TD_WordEmbeddings` | `text-analytics` |

### Vector Search

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| Manual pairwise distance loops | `TD_VectorDistance` | `vector-search` |
| External approximate nearest neighbor index | `TD_HNSW` / `TD_HNSWPredict` | `vector-search` |
| External embedding storage type | `VECTOR` / `Vector32` data type | `data-types-casting` |

### Statistical Testing

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| Manual ANOVA calculation | `TD_ANOVA` | `hypothesis-testing` |
| Manual chi-squared test | `TD_ChiSq` | `hypothesis-testing` |
| Manual F-test | `TD_FTest` | `hypothesis-testing` |
| Manual Z-test | `TD_ZTest` | `hypothesis-testing` |

### Sequence & Path Analysis

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| Manual session window logic | `Sessionize` | `path-analysis` |
| Manual funnel / path counting | `nPath` | `path-analysis` |
| Manual attribution modeling | `Attribution` | `path-analysis` |

---

## Pipeline Assembly

When combining multiple steps, use native pipeline patterns rather than chaining manual SQL:

- **Apply multiple transforms in one pass:** `TD_ColumnTransformer` with saved FitTables (see `ml-patterns` topic, CTE pipeline pattern)
- **Full scoring pipeline in one query:** wrap `TD_ColumnTransformer` in a CTE, feed into a Predict function — no temp tables needed
- **Choosing K for clustering:** use the elbow method UNION ALL pattern, not manual iteration (see `ml-patterns`)
- **Class imbalance:** split first, then `TD_SMOTE` on train set only (see `ml-patterns`)

See the `ml-patterns` topic for complete end-to-end pipeline examples.

---

## When Manual SQL Is Appropriate

Native functions do not cover everything. Use hand-written SQL for:

- Basic SELECT, filtering, joining, aggregation (`sql-basics`, `aggregate-functions`)
- Date/time arithmetic (`date-time`)
- CASE expressions and NULL handling (`conditional`)
- Window functions for lag/lead features, running totals (`window-functions`)
- Schema discovery queries against DBC.* views (`catalog-views`)
- One-off computations not covered by any native function

If you are unsure whether a native function exists for an operation, call `get_syntax_help(topic='index')` and check.
