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
| `bit-byte-functions` | Bit/byte manipulation: BITAND, BITOR, BITXOR, BITNOT, SHIFTLEFT/RIGHT, ROTATELEFT/RIGHT, GETBIT, SETBIT, COUNTSET, SUBBITSTR, TO_BYTE |
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
| `embeddings` | Embedding generation: AI_TextEmbeddings (cloud/NIM REST), ONNXEmbeddings (in-database BYOM), TD_WordEmbeddings; store → normalize → index → search pipeline |
| `ai-text-analytics` | LLM-powered text analytics: AI_AnalyzeSentiment, AI_AskLLM, AI_DetectLanguage, AI_ExtractKeyPhrases, AI_MaskPII, AI_RecognizeEntities, AI_RecognizePIIEntities, AI_TextClassifier, AI_TextSummarize, AI_TextTranslate |

## Unbounded Array Framework (UAF)
| Topic | Description |
|-------|-------------|
| `uaf-concepts` | **Start here for UAF** — SERIES_SPEC, MATRIX_SPEC, ART_SPEC, GENSERIES_SPEC, EXECUTE FUNCTION INTO ART, ART layers, TD_EXTRACT_RESULTS |
| `uaf-utility` | UAF general utility functions: TD_CONVERTTABLEFORUAF, TD_COPYART, TD_SINFO, TD_MINFO, TD_ISFINITE/ISINF/ISNAN, TD_INPUTVALIDATOR, TD_PLOT, TD_IMAGE2MATRIX, TD_MATRIX2IMAGE, TD_TRACKINGOP, TD_FILTERFACTORY1D |
| `uaf-data-prep` | UAF data preparation and anomaly detection: TD_RESAMPLE, TD_BINARYSERIESOP, TD_BINARYMATRIXOP, TD_GENSERIES4FORMULA, TD_MATRIXMULTIPLY, TD_IQR |
| `uaf-estimation` | UAF model preparation and parameter estimation: TD_ACF, TD_PACF, TD_DIFF, TD_UNDIFF, TD_SEASONALNORMALIZE, TD_UNNORMALIZE, TD_LINEAR_REGR, TD_MULTIVAR_REGR, TD_ARIMAESTIMATE, TD_ARIMAVALIDATE, TD_AUTOARIMA, TD_POWERTRANSFORM, TD_SMOOTHMA |
| `uaf-forecasting` | UAF series forecasting: TD_ARIMAFORECAST, TD_HOLT_WINTERS_FORECASTER, TD_MAMEAN, TD_SIMPLEEXP, TD_DTW |
| `uaf-diagnostics` | UAF diagnostic statistical tests: TD_DICKEY_FULLER, TD_DURBIN_WATSON, TD_BREUSCH_GODFREY, TD_BREUSCH_PAGAN_GODFREY, TD_WHITES_GENERAL, TD_GOLDFELD_QUANDT, TD_PORTMAN, TD_FITMETRICS, TD_SELECTION_CRITERIA, TD_CUMUL_PERIODOGRAM, TD_SIGNIF_PERIODICITIES, TD_SIGNIF_RESIDMEAN |
| `uaf-dsp` | UAF digital signal processing and spatial: TD_DFFT/DFFT2, TD_IDFFT/IDFFT2, TD_DFFTCONV/DFFT2CONV, TD_CONVOLVE/CONVOLVE2, TD_DWT/DWT2D, TD_IDWT/IDWT2D, TD_POWERSPEC, TD_LINESPEC, TD_GENSERIES4SINUSOIDS, TD_SAX, TD_WINDOWDFFT |
| `uaf-formula-rules` | UAF formula syntax: operators, precedence, math and trigonometric functions, variable naming conventions for FORMULA(...) parameters |

## Geospatial
| Topic | Description |
|-------|-------------|
| `geospatial` | ST_Geometry, MBR/MBB types, WKT/WKB formats, spatial relationships (ST_Within, ST_Contains, ST_Distance, etc.), geospatial indexes, tessellation, AggGeom, GeometryToRows, PolygonSplit, MGRS conversion, SYSSPATIAL metadata |

## Reference
| Topic | Description |
|-------|-------------|
| `catalog-views` | DBC.* system views for schema discovery |
| `query-tuning` | EXPLAIN, PI design, hash functions (HASHROW/HASHBUCKET/HASHAMP/HASHBAKAMP), skew detection, collect stats, query rewrite tips |
| `authorization-objects` | CREATE/REPLACE/GRANT authorization objects for external service credentials (AI functions, external procedures) |
| `llm-providers` | LLM provider argument blocks for AI functions — Azure, AWS Bedrock, GCP, NVIDIA NIM, LiteLLM |
| `byom-model-loading` | Loading PMML, H2O MOJO, ONNX, Dataiku, DataRobot, and MLeap models into Teradata BYOM tables; conversion workflow for ONNX embedding models |
| `byom-scoring` | BYOM scoring: PMMLPredict, H2OPredict, ONNXPredict, DataikuPredict, DataRobotPredict, MLeapPredict; NLP transformers: ONNXSeq2Seq, ONNXClassification |

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
| **LLM-powered text analytics** | `authorization-objects` → `llm-providers` → `ai-text-analytics` |
| **PII detection / masking** | `authorization-objects` → `llm-providers` → `ai-text-analytics` (AI_MaskPII, AI_RecognizePIIEntities) |
| **Imbalanced classes** | `data-prep` (TD_SMOTE) → `ml-patterns` (class imbalance workflow) → `model-evaluation` |
| **Micromodeling (per-segment models)** | `ml-functions` (TD_GLM) → `ml-patterns` (micromodeling) |
| **Semantic search / RAG embeddings** | `authorization-objects` → `llm-providers` → `embeddings` → `vector-search` |
| **In-database ONNX inference** | `byom-model-loading` → `embeddings` (ONNXEmbeddings) → `vector-search` |
| **Time series forecasting (ARIMA)** | `uaf-concepts` → `uaf-data-prep` → `uaf-estimation` → `uaf-forecasting` → `uaf-diagnostics` |
| **Regression on ordered series** | `uaf-concepts` → `uaf-data-prep` → `uaf-estimation` (TD_LINEAR_REGR / TD_MULTIVAR_REGR) → `uaf-diagnostics` |
| **Frequency / spectral analysis** | `uaf-concepts` → `uaf-dsp` (TD_DFFT, TD_POWERSPEC, TD_LINESPEC) |
| **Digital signal filtering** | `uaf-concepts` → `uaf-utility` (TD_FILTERFACTORY1D) → `uaf-dsp` (TD_CONVOLVE) |

---
> **Adding topics:** Drop a new `.md` file into `src/tdsql_mcp/syntax/` and it appears here
> automatically — no code changes needed.
