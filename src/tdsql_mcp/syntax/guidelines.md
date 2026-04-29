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

**Inline NL Query → Embedding → Vector Search:** For RAG retrieval, use the full CTE pipeline pattern — embed the query inline with `AI_TEXTEMBEDDINGS`, normalize with `TD_VectorNormalize(Approach('UNITVECTOR'))`, and search with `TD_VectorDistance` against a pre-built corpus embedding table, all in a single SQL statement. See `vector-search` topic, "Inline NL Query → Embedding → Vector Search Pipeline" section.

**Building a corpus embedding table:** Use the full workflow: source text table → `AI_TEXTEMBEDDINGS` → `TD_VectorNormalize(Approach('UNITVECTOR'))` → CTAS. See `vector-search` topic, "Full Corpus Build Workflow" section.

**Vector dimension introspection:** Use `embedding.LENGTH()` to get the number of dimensions from a VECTOR column — never infer from UDT byte size. `SELECT embedding.LENGTH() AS dims FROM db.table SAMPLE 1;`

**Finding the embedding model for an existing corpus:** Query `TD_SYSAI.TD_CollectionsV` or `TD_SYSAI.TD_VectorStores` to discover the model name, provider, and embedding size used to build a corpus. The query pipeline must use the exact same model — mismatched embeddings produce meaningless scores. See `vector-search` topic, "Discovering Existing Vector Stores" section.

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

### Geospatial

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| External point-in-polygon test | `ST_Within(ageometry)` / `ST_Contains(ageometry)` | `geospatial` |
| External spatial join (points within areas) | Native spatial join with geospatial NUSI — `JOIN ON col.ST_Within(other) = 1` | `geospatial` |
| External distance calculation | `ST_Distance`, `ST_SpheroidalDistance`, `ST_SphericalDistance` | `geospatial` |
| External proximity search | `ST_Distance(...) < constant` with geospatial index | `geospatial` |
| External buffer zone | `ST_Buffer(distance)` | `geospatial` |
| External polygon area / perimeter | `ST_Area()`, `ST_Perimeter()` | `geospatial` |
| External centroid calculation | `ST_Centroid()` | `geospatial` |
| External geometry union/intersection | `ST_Union`, `ST_Intersection`, `AggGeom(USING Operation('Union'))` | `geospatial` |
| External WKT parsing | `NEW ST_Geometry('WKT...')` | `geospatial` |
| External MGRS conversion | `TO_MGRS`, `FROM_MGRS` (TD_SYSFNLIB) | `geospatial` |
| Explode polygon/linestring to point rows | `GeometryToRows(ON ...)` | `geospatial` |
| Split large polygons for performance | `PolygonSplit(ON ...)` | `geospatial` |

### Time Series, DSP & Spatial — Unbounded Array Framework (UAF)

> **Multi-series parallelism:** A single UAF function call processes **all series instances simultaneously** across all AMPs. Whether you are fitting ARIMA models for 1 entity or 1 million, forecasting 10 sensors or 10 million, the call is identical — the platform distributes the work. Never loop, iterate, or run separate queries per entity. Pass all series at once and let the AMP architecture do the parallelism.

| Instead of this | Use this (native function) | Topic |
|-----------------|---------------------------|-------|
| External time series forecasting (statsmodels, R forecast) | `TD_ARIMAESTIMATE` → `TD_ARIMAVALIDATE` → `TD_ARIMAFORECAST` | `uaf-estimation`, `uaf-forecasting` |
| Per-entity forecast loops | Single UAF call with all series as SERIES_SPEC — all entities processed in parallel | `uaf-concepts` |
| External seasonal decomposition | `TD_SEASONALNORMALIZE` | `uaf-estimation` |
| External exponential smoothing | `TD_HOLT_WINTERS_FORECASTER`, `TD_SIMPLEEXP`, `TD_MAMEAN` | `uaf-forecasting` |
| External regression on ordered sequences | `TD_LINEAR_REGR` / `TD_MULTIVAR_REGR` | `uaf-estimation` |
| External autocorrelation / partial autocorrelation | `TD_ACF` / `TD_PACF` | `uaf-estimation` |
| External differencing for stationarity | `TD_DIFF` / `TD_UNDIFF` | `uaf-estimation` |
| External Fourier transform / frequency analysis | `TD_DFFT` / `TD_POWERSPEC` / `TD_LINESPEC` | `uaf-dsp` |
| External convolution / digital filtering | `TD_CONVOLVE` (with `TD_FILTERFACTORY1D` coefficients) | `uaf-dsp`, `uaf-utility` |
| External wavelet transform | `TD_DWT` / `TD_IDWT` | `uaf-dsp` |
| External time series anomaly detection | `TD_IQR` | `uaf-data-prep` |
| External DTW similarity | `TD_DTW` | `uaf-forecasting` |
| External geospatial tracking metrics | `TD_TRACKINGOP` | `uaf-utility` |
| Residual diagnostics after model fit | `TD_DICKEY_FULLER`, `TD_DURBIN_WATSON`, `TD_PORTMAN`, `TD_BREUSCH_GODFREY`, etc. | `uaf-diagnostics` |

**Start here for UAF:** `get_syntax_help(topic="uaf-concepts")` — covers SERIES_SPEC, MATRIX_SPEC, ART_SPEC, the `EXECUTE FUNCTION INTO ART` execution pattern, ART layers, and TD_EXTRACT_RESULTS.

---

## Pipeline Assembly

When combining multiple steps, use native pipeline patterns rather than chaining manual SQL:

- **Apply multiple transforms in one pass:** `TD_ColumnTransformer` with saved FitTables (see `ml-patterns` topic, CTE pipeline pattern)
- **Full scoring pipeline in one query:** wrap `TD_ColumnTransformer` in a CTE, feed into a Predict function — no temp tables needed
- **Choosing K for clustering:** use the elbow method UNION ALL pattern, not manual iteration (see `ml-patterns`)
- **Class imbalance:** split first, then `TD_SMOTE` on train set only (see `ml-patterns`)
- **UAF multi-step pipelines:** chain ARTs — each function writes to a named ART, the next function reads it via `ART_SPEC(TABLE_NAME(...))`. The canonical pattern is estimate → validate → forecast. See `uaf-concepts` for the full chaining example.

See the `ml-patterns` topic for complete end-to-end ML pipeline examples. See `uaf-concepts` for UAF pipeline patterns.

---

## Query Validation and Optimization with EXPLAIN

For any non-trivial query, run `explain_query` before executing. Read the plan and optimize if needed — do not just use EXPLAIN for syntax checking.

**When to always EXPLAIN first:**
- Queries joining two or more large tables
- Queries without a PI-aligned filter (likely full table scan)
- Queries with subqueries, correlated subqueries, or complex predicates
- Any query you're about to run with `execute_statement` that modifies data

**Decision loop:**
1. Run `explain_query(sql=...)`
2. Scan for red flags (see below) — if found, fix and re-EXPLAIN before executing
3. Only execute once the plan looks reasonable

**Red flags in EXPLAIN output — act on these:**

| Signal | Problem | Action |
|--------|---------|--------|
| `estimated with no confidence` | Missing statistics — optimizer is guessing | `COLLECT STATISTICS ON db.table COLUMN (col)` |
| `estimated with low confidence` | Stale or partial statistics | Refresh stats on join/filter columns |
| `product join` | Potential Cartesian explosion | Check join conditions; add missing predicate |
| `all-rows scan` on large table | Full table scan | Check if PI filter or index is applicable |
| `redistributed by hash code` on large spool | Expensive data movement | Consider PI alignment or pre-staged table |
| `(group_amps)` on very few AMPs | Data skew | Check for skewed join key values |

**Green flags — plan is efficient:**
- `single-AMP RETRIEVE by way of the unique primary index` — best-case access
- `estimated with high confidence` — optimizer has reliable statistics
- `duplicated on all AMPs` on a small table — correct broadcast strategy
- `execute the following steps in parallel` — independent steps dispatched concurrently

For full EXPLAIN interpretation guidance, optimization playbook, and stats collection patterns: `get_syntax_help(topic="query-tuning")`.

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
