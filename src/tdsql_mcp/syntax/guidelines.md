# Teradata Native Functions — Guidelines for Agents

## Always Prefer Native Functions Over Hand-Written SQL

Teradata Vantage has built-in distributed table operators for most analytics, ML, data preparation, and search operations. These functions run across all AMPs in parallel, are optimized for Vantage's architecture, and should **always** be used instead of equivalent hand-written SQL.

**Before writing any SQL for analytics, transformation, or ML: check this guide and the relevant syntax topic.**

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
| Manual COALESCE / UPDATE for NULL fill | `TD_FillNa` | `data-cleaning` |
| Manual ROW_NUMBER deduplication | `TD_Deduplicate` | `data-cleaning` |
| Manual REGEXP_REPLACE string cleaning | `TD_StringSimilarity`, `TD_StringDistance` | `data-cleaning` |
| Manual type-check logic | `TD_TypeCheck` | `data-cleaning` |

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
