# Teradata Data Preparation & Feature Engineering

## Normalization / Scaling

### Min-Max Scaling (0 to 1)
```sql
SELECT col,
       (col - MIN(col) OVER ()) / NULLIFZERO(MAX(col) OVER () - MIN(col) OVER ()) AS col_minmax
FROM db.table;
```

### Z-Score Standardization
```sql
SELECT col,
       (col - AVG(col) OVER ()) / NULLIFZERO(STDDEV_SAMP(col) OVER ()) AS col_zscore
FROM db.table;
```

### TD_ScaleFit / TD_ScaleTransform (Vantage)
```sql
-- Fit scaler on training data
SELECT * FROM TD_ScaleFit(
    ON (SELECT * FROM db.train_data)
    USING
        InputColumns('f1', 'f2', 'f3')
        ScaleMethod('ZSCORE')    -- or 'RANGE', 'MIDRANGE', 'MAXABS'
        OutputModelFile('my_scaler')
) AS t;

-- Apply to new data
SELECT * FROM TD_ScaleTransform(
    ON (SELECT * FROM db.score_data) AS InputTable
    ON (SELECT * FROM TD_ScaleModel WHERE ModelFile = 'my_scaler') AS ModelTable DIMENSION
) AS t;
```

---

## Binning

### Equal-Width Bins
```sql
SELECT id, amount,
       CASE
           WHEN amount < 100  THEN 'low'
           WHEN amount < 500  THEN 'medium'
           WHEN amount < 1000 THEN 'high'
           ELSE 'very_high'
       END AS amount_bin
FROM db.table;
```

### Equal-Frequency Bins (Quantile-Based)
```sql
SELECT id, amount,
       NTILE(4) OVER (ORDER BY amount) AS quartile,
       NTILE(10) OVER (ORDER BY amount) AS decile
FROM db.table;
```

### TD_Bincode (Vantage)
```sql
SELECT * FROM TD_Bincode(
    ON (SELECT * FROM db.table)
    USING
        InputColumns('amount')
        BincodingMethod('QUANTILE')
        NumBins('10')
) AS t;
```

---

## Encoding Categorical Variables

### One-Hot Encoding (Manual Pivot)
```sql
SELECT id,
       CASE WHEN category = 'A' THEN 1 ELSE 0 END AS cat_A,
       CASE WHEN category = 'B' THEN 1 ELSE 0 END AS cat_B,
       CASE WHEN category = 'C' THEN 1 ELSE 0 END AS cat_C
FROM db.table;
```

### Label Encoding
```sql
SELECT id, category,
       DENSE_RANK() OVER (ORDER BY category) - 1 AS category_encoded
FROM db.table;
```

### TD_OneHotEncode (Vantage)
```sql
SELECT * FROM TD_OneHotEncode(
    ON (SELECT * FROM db.table)
    USING
        InputColumns('category', 'region')
        OutputStyle('column')   -- 'column' creates one col per value
) AS t;
```

---

## Handling Missing Values

### Impute with Mean/Median
```sql
SELECT id,
       COALESCE(amount, AVG(amount) OVER ()) AS amount_imputed
FROM db.table;

-- Median imputation
SELECT id,
       COALESCE(amount, APPROX_PERCENTILE(amount, 0.5) OVER ()) AS amount_imputed
FROM db.table;
```

### TD_FillRowsWithMissing / TD_Impute (Vantage)
```sql
SELECT * FROM TD_Impute(
    ON (SELECT * FROM db.table)
    USING
        TargetColumns('col1', 'col2')
        ImputeType('mean')    -- 'mean', 'median', 'mode', 'literal'
) AS t;
```

---

## Reshaping

### Unpivot (Wide → Long)
```sql
-- Manual UNION approach
SELECT id, 'jan' AS month, jan_sales AS sales FROM db.t
UNION ALL
SELECT id, 'feb', feb_sales FROM db.t
UNION ALL
SELECT id, 'mar', mar_sales FROM db.t;

-- TD_Unpivot (Vantage)
SELECT * FROM TD_Unpivot(
    ON (SELECT * FROM db.wide_table)
    USING
        Unpivot('jan_sales', 'feb_sales', 'mar_sales')
        ColName('month')
        ValueName('sales')
        InputTypes('false')
) AS t;
```

### Pivot (Long → Wide)
```sql
SELECT id,
       SUM(CASE WHEN month = 'jan' THEN sales END) AS jan,
       SUM(CASE WHEN month = 'feb' THEN sales END) AS feb,
       SUM(CASE WHEN month = 'mar' THEN sales END) AS mar
FROM db.long_table
GROUP BY id;
```

---

## Feature Engineering Patterns

### Lag / Lead Features (Time Series)
```sql
SELECT id, dt, value,
       LAG(value, 1)  OVER (PARTITION BY id ORDER BY dt) AS value_lag1,
       LAG(value, 7)  OVER (PARTITION BY id ORDER BY dt) AS value_lag7,
       LEAD(value, 1) OVER (PARTITION BY id ORDER BY dt) AS value_next
FROM db.timeseries;
```

### Rolling Statistics
```sql
SELECT id, dt, value,
       AVG(value)    OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d_avg,
       STDDEV_SAMP(value) OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS rolling_30d_std
FROM db.timeseries;
```

### Ratio / Interaction Features
```sql
SELECT id,
       revenue / NULLIFZERO(visits)             AS revenue_per_visit,
       clicks / NULLIFZERO(impressions)         AS ctr,
       (revenue - cost) / NULLIFZERO(cost)      AS roi
FROM db.campaign;
```
