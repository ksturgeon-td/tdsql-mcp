# Teradata SQL Syntax Reference — Topic Index

Use `get_syntax_help(topic="<name>")` to load any topic below.

## Core SQL
| Topic | Description |
|-------|-------------|
| `sql-basics` | SELECT syntax, TOP N, SAMPLE, QUALIFY, CTEs, joins |
| `data-types-casting` | Data types and CAST / type conversion patterns |
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
| `data-prep` | Feature engineering: binning, encoding, scaling, pivoting, polynomial features, dimensionality reduction, Fit/Transform pairs |
| `utility-functions` | TD_FillRowID, TD_NumApply, TD_RoundColumns, TD_StrApply |
| `text-analytics` | Text tokenization, classification, and entity extraction: TD_NgramSplitter, TD_NaiveBayesTextClassifier, TD_NERExtractor |

## Reference
| Topic | Description |
|-------|-------------|
| `catalog-views` | DBC.* system views for schema discovery |
| `query-tuning` | EXPLAIN, PI design, collect stats, query rewrite tips |

---
> **Adding topics:** Drop a new `.md` file into `src/tdsql_mcp/syntax/` and it appears here
> automatically — no code changes needed.
