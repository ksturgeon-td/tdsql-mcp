# Teradata SQL Syntax Reference — Topic Index

Use `get_syntax_help(topic="<name>")` to load any topic below.

> **Always prefer native Teradata functions over hand-written SQL.** Before writing analytics, transformation, ML, or search SQL, call `get_syntax_help(topic="guidelines")` to see the canonical mapping of common operations to native functions. Native table operators run distributed across all AMPs and outperform equivalent manual SQL.
>
> **Minimize data movement.** Teradata tables can contain billions of rows. Never SELECT raw data to the agent for processing — use native functions that summarize and compute in-database. Chain pipeline steps as CTEs. Persist large outputs with OUT TABLE. Return results, not data.

## Start Here
| Topic | Description |
|-------|-------------|
| `guidelines` | **Native functions first** — canonical mapping of common SQL patterns to native Teradata functions; when to use each |

## Core SQL
| Topic | Description |
|-------|-------------|
| `sql-basics` | SELECT syntax, TOP N, SAMPLE, QUALIFY, CTEs, joins |
| `data-types-casting` | Data types, CAST / type conversion patterns, VECTOR and Vector32 embedding types |
| `conditional` | CASE, COALESCE, NULLIFZERO, ZEROIFNULL, NULLIF |

## Functions
| Topic | Description |
|-------|-------------|
| `string-functions` | Character manipulation: SUBSTR, INDEX, OREPLACE, TRIM, etc. |
| `numeric-functions` | Math and numeric functions: ROUND, MOD, LOG, ABS, etc. |
| `date-time` | Date/time literals, arithmetic, formatting, EXTRACT |
| `aggregate-functions` | GROUP BY, COUNT, SUM, AVG, percentiles, GROUPING SETS |
| `window-functions` | ROW_NUMBER, RANK, LAG/LEAD, running totals, QUALIFY |

## Analytics & ML
| Topic | Description |
|-------|-------------|
| `fit-transform-pattern` | Reusable two-phase pattern: Fit learns from training data, Transform applies to new data |
| `ml-functions` | Vantage ML: TD_XGBoost, TD_DecisionForest, TD_LogReg, scoring |
| `data-exploration` | Descriptive stats, sampling, histogram, correlation, MovingAverage, TD_UnivariateStatistics, TD_Histogram, TD_QQNorm |
| `data-cleaning` | NULL handling, deduplication, string cleaning, outlier detection, type validation |
| `data-prep` | Feature engineering: binning, encoding, scaling, pivoting, polynomial features, dimensionality reduction, Fit/Transform pairs, TD_SMOTE oversampling |
| `utility-functions` | TD_FillRowID, TD_NumApply, TD_RoundColumns, TD_StrApply |
| `text-analytics` | Text tokenization, classification, and entity extraction: TD_NgramSplitter, TD_NaiveBayesTextClassifier, TD_NERExtractor |
| `hypothesis-testing` | Statistical hypothesis tests: TD_ANOVA, TD_ChiSq, TD_FTest, TD_ZTest |
| `association-analysis` | Frequent itemset mining and collaborative filtering: TD_Apriori, TD_CFilter |
| `path-analysis` | Event sequence analysis: Attribution, Sessionize, nPath |
| `model-evaluation` | Model evaluation and explainability: TD_TrainTestSplit, TD_ClassificationEvaluator, TD_RegressionEvaluator, TD_ROC, TD_Silhouette, TD_SHAP |
| `ml-patterns` | End-to-end ML pipeline patterns: CTE prediction pipeline, elbow method, train/evaluate/retrain loop, class imbalance workflow, micromodeling |
| `vector-search` | Vector similarity search: TD_VectorDistance (exact), TD_HNSW/TD_HNSWPredict (approximate), KMeans IVF pattern |

## Reference
| Topic | Description |
|-------|-------------|
| `catalog-views` | DBC.* system views for schema discovery |
| `query-tuning` | EXPLAIN, PI design, collect stats, query rewrite tips |
| `authorization-objects` | CREATE/REPLACE/GRANT authorization objects for external service credentials (AI functions, external procedures) |
| `llm-providers` | LLM provider argument blocks for AI functions — Azure, AWS Bedrock, GCP, NVIDIA NIM, LiteLLM |

---

## Workflows — Start Here for Common Use Cases

Recommended topic reading order for common end-to-end tasks. Load these topics in sequence for full context.

| Use Case | Topic sequence |
|----------|---------------|
| **Classification (fraud, churn, risk)** | `data-exploration` → `data-cleaning` → `data-prep` → `fit-transform-pattern` → `ml-functions` → `model-evaluation` → `ml-patterns` |
| **Regression (price, demand, forecast)** | `data-exploration` → `data-cleaning` → `data-prep` → `ml-functions` → `model-evaluation` → `ml-patterns` |
| **Clustering (segmentation)** | `data-exploration` → `data-prep` → `ml-functions` → `ml-patterns` (elbow method) → `model-evaluation` (Silhouette) |
| **Operationalize a trained model** | `fit-transform-pattern` → `ml-patterns` (CTE prediction pipeline) |
| **Text classification / NLP** | `data-cleaning` → `text-analytics` → `model-evaluation` |
| **Imbalanced classes** | `data-prep` (TD_SMOTE) → `ml-patterns` (class imbalance workflow) → `model-evaluation` |
| **Micromodeling (per-segment models)** | `ml-functions` (TD_GLM) → `ml-patterns` (micromodeling) |

---
> **Adding topics:** Drop a new `.md` file into `src/tdsql_mcp/syntax/` and it appears here
> automatically — no code changes needed.
