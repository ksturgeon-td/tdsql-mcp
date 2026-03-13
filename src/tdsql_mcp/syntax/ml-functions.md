# Teradata Vantage ML Functions

Teradata Vantage includes in-database ML via the `TD_SYSFNLIB` and Analytics Database
function sets. Models train and score directly in the database — no data movement needed.

> **Tip:** Use `get_syntax_help("data-exploration")` for statistical prep functions,
> and `get_syntax_help("data-prep")` for feature engineering before training.

---

## Supervised Learning

### TD_XGBoost (Gradient Boosted Trees)
```sql
-- Train
SELECT * FROM TD_XGBoost(
    ON (SELECT * FROM db.train_data)
    USING
        InputColumns('feature1', 'feature2', 'feature3')
        ResponseColumn('label')
        NumBoostedTrees('100')
        MaxDepth('6')
        MinNodeSize('10')
        LearningRate('0.1')
        ObjectiveFunction('binary:logistic')   -- or 'reg:squarederror', 'multi:softprob'
        OutputModelFile('my_xgb_model')
) AS t;

-- Score
SELECT * FROM TD_XGBoostPredict(
    ON (SELECT * FROM db.score_data) AS InputTable
    ON (SELECT * FROM TD_XGBoostModel WHERE ModelFile = 'my_xgb_model') AS ModelTable DIMENSION
    USING
        OutputProb('true')
        OutputResponses('0', '1')
) AS t;
```

### TD_DecisionForest (Random Forest)
```sql
-- Train
SELECT * FROM TD_DecisionForest(
    ON (SELECT * FROM db.train_data)
    USING
        InputColumns('feature1', 'feature2')
        ResponseColumn('label')
        NumTrees('100')
        TreeType('CLASSIFICATION')   -- or 'REGRESSION'
        MaxDepth('10')
        MinNodeSize('5')
        OutputModelFile('my_rf_model')
) AS t;

-- Score
SELECT * FROM TD_DecisionForestPredict(
    ON (SELECT * FROM db.score_data) AS InputTable
    ON (SELECT * FROM TD_DecisionForestModel WHERE ModelFile = 'my_rf_model') AS ModelTable DIMENSION
    USING OutputProb('true')
) AS t;
```

### TD_LogisticRegression
```sql
-- Train
SELECT * FROM TD_LogisticRegression(
    ON (SELECT * FROM db.train_data)
    USING
        InputColumns('feature1', 'feature2')
        ResponseColumn('label')
        MaxIterNum('100')
        StopThreshold('0.01')
        Regularization('L2')
        Lambda('0.01')
) AS t;
```

### TD_LinearRegression
```sql
SELECT * FROM TD_LinearRegression(
    ON (SELECT * FROM db.train_data)
    USING
        InputColumns('feature1', 'feature2')
        ResponseColumn('target')
) AS t;
```

---

## Unsupervised Learning

### TD_KMeans
```sql
-- Train
SELECT * FROM TD_KMeans(
    ON (SELECT * FROM db.data)
    USING
        InputColumns('x', 'y', 'z')
        NumClusters('5')
        MaxIterNum('100')
        StopThreshold('0.01')
        OutputModelFile('my_kmeans_model')
) AS t;

-- Score (assign cluster membership)
SELECT * FROM TD_KMeansPredict(
    ON (SELECT * FROM db.score_data) AS InputTable
    ON (SELECT * FROM TD_KMeansModel WHERE ModelFile = 'my_kmeans_model') AS ModelTable DIMENSION
) AS t;
```

### TD_PCA (Principal Component Analysis)
```sql
-- Train
SELECT * FROM TD_PCA(
    ON (SELECT * FROM db.data)
    USING
        InputColumns('f1', 'f2', 'f3', 'f4')
        NumComponents('3')
        OutputModelFile('my_pca_model')
) AS t;

-- Transform
SELECT * FROM TD_PCATransform(
    ON (SELECT * FROM db.data) AS InputTable
    ON (SELECT * FROM TD_PCAModel WHERE ModelFile = 'my_pca_model') AS ModelTable DIMENSION
) AS t;
```

---

## Model Evaluation

### TD_ROC (ROC / AUC)
```sql
SELECT * FROM TD_ROC(
    ON (SELECT actual_label, predicted_prob FROM db.predictions)
    USING
        ProbabilityColumn('predicted_prob')
        ObservationColumn('actual_label')
        PositiveClass('1')
        NumThresholds('100')
) AS t;
```

### TD_ConfusionMatrix
```sql
SELECT * FROM TD_ConfusionMatrix(
    ON (SELECT actual_label, predicted_label FROM db.predictions)
    USING
        ObservationColumn('actual_label')
        PredictedColumn('predicted_label')
) AS t;
```

### TD_RegressionEvaluator
```sql
SELECT * FROM TD_RegressionEvaluator(
    ON (SELECT actual, predicted FROM db.predictions)
    USING
        ObservationColumn('actual')
        PredictionColumn('predicted')
        Metrics('MSE', 'RMSE', 'MAE', 'R2')
) AS t;
```

---

## Time Series / Sequences

### TD_ARIMA
```sql
SELECT * FROM TD_ARIMA(
    ON (SELECT period, value FROM db.timeseries ORDER BY period) AS InputTable
    USING
        TimeColumn('period')
        ValueColumns('value')
        P('1') D('1') Q('1')
        IncludeMean('true')
) AS t;
```

---

## Notes
- Model files persist in the database and can be reused for scoring new data
- All TD_ ML functions use the table operator `ON ... USING` syntax, not standard SQL
- Use `EXPLAIN` on ML queries to estimate resource usage before running on large data
- Models can be called inline in larger SQL pipelines without exporting data
