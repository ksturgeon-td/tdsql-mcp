# Teradata Vantage ML Functions

In-database machine learning via Vantage analytic functions. Models train and score directly in the database — no data movement needed.

> **Train/Predict pattern:** ML functions follow a two-phase pattern. The Train function learns a model from training data and outputs a model table. The Predict function takes that model table as a `DIMENSION` input and applies it to new data. Save the model output via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT` so it can be reused for scoring without retraining.

> **Tip:** Use `get_syntax_help("data-exploration")` for statistical prep, `get_syntax_help("data-prep")` for feature engineering, and `get_syntax_help("data-cleaning")` for imputation before training.

---

## TD_DecisionForest — Train/Predict

Ensemble algorithm for classification and regression using random decision forests (bagging of decision trees). Supports binary and multiclass classification and regression. Trees are built in parallel across AMPs.

**Constraints:**
- All input columns must be numeric — convert categoricals before calling
- Classification: `ResponseColumn` must be INTEGER/SMALLINT/BYTEINT; max 500 classes
- Rows with NULL in any input column are skipped — use `TD_SimpleImpute` first
- No `OUT TABLE` clause — capture the model via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`

### Train

```sql
SELECT * FROM TD_DecisionForest(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        InputColumns({ 'col' | col_range }[,...])    -- required; all numeric; no double-quoted names
        ResponseColumn('response_col')               -- required; classification: INTEGER/SMALLINT/BYTEINT only
        [ ModelType('Classification'|'Regression') ] -- default 'Regression'
        [ MaxDepth(5) ]                              -- default 5; non-negative integer; tree stops at this depth
        [ MinNodeSize(1) ]                           -- default 1; stop splitting when node has <= this many rows
        [ NumTrees(-1) ]                             -- default -1 (auto); max 65536; if specified, must be >= num AMPs
        [ TreeSize(-1) ]                             -- default -1 (auto); rows per tree input sample
        [ CoverageFactor(1.0) ]                      -- default 1.0 (100%); dataset coverage level per tree
        [ MinImpurity(0.0) ]                         -- default 0.0; stop splitting at or below this impurity
        [ Mtry(-1) ]                                 -- default -1 (all features); features evaluated per split
        [ MtrySeed(1) ]                              -- default 1; random seed for Mtry
        [ Seed(1) ]                                  -- default 1; random seed for reproducibility
) AS t;
```

> **NumTrees note:** When specified, actual tree count = `Num_AMPs_with_data × (NumTrees / Num_AMPs_with_data)`. Use `SELECT HASHAMP()+1;` to get AMP count. For small datasets, distribute data to one AMP by setting all rows to the same primary index value.

**Model output schema** (save this table for use in Predict):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP that produced this tree |
| `tree_num` | SMALLINT | Tree identifier within the AMP |
| `tree_order` | INTEGER | Sequence number for multi-row JSON chunks |
| `classification_tree` or `regression_tree` | VARCHAR(16000) | JSON decision tree; split across rows when > 16000 bytes |

### Predict

```sql
SELECT * FROM TD_DecisionForestPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier; cannot be NULL
        [ Detailed('false') ]                        -- default false; outputs per-tree task_index/tree_num detail
        [ OutputProb('false') ]                      -- default false; classification only; must be true if using Responses
        [ Responses('class1'[,...]) ]                -- classification only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]  -- input columns to copy to output
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Row identifier from InputTable |
| `prediction` | INTEGER (classification) / FLOAT (regression) | Predicted class or value |
| `confidence_lower` | FLOAT | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `confidence_upper` | FLOAT | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_<response>` | FLOAT | When `OutputProb('true')` and `Responses` specified; one column per response value |
| `tree_num` | VARCHAR(30) | When `Detailed('true')`; per-tree task/tree concatenation, or `'Final'` for overall prediction |
| `accumulate_column(s)` | same as input | Columns copied from InputTable |

---

## TD_GLM — Train/Predict

Generalized Linear Model supporting regression (Gaussian family) and binary classification (Binomial family / logistic regression). Uses Stochastic Gradient Descent (SGD) for optimization.

**Two operating modes:**
- **PARTITION BY ANY** — trains a single model on the full dataset; supports LocalSGD for faster convergence on large clusters
- **PARTITION BY key (Micromodeling)** — trains one independent model per partition value in parallel; accepts optional per-partition `AttributeTable` (feature subset) and `ParameterTable` (parameter overrides)

**Constraints:**
- `AS InputTable` alias is mandatory
- All input columns must be numeric
- Classification (`Binomial`): response values must be 0 or 1
- No `OUT TABLE` for the model itself — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `MetaInformationTable` (training progress) available as `OUT TABLE` for PARTITION BY ANY only

### Train

**Mode 1 — PARTITION BY ANY (single model):**

```sql
SELECT * FROM TD_GLM(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')
        [ Family('Gaussian'|'Binomial') ]            -- default 'Gaussian'; Binomial = logistic regression
        [ BatchSize(10) ]                            -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                          -- default 300
        [ RegularizationLambda(0.02) ]               -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                              -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                      -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                         -- default 0.001; min loss improvement to continue
        [ Intercept('true') ]                        -- default true
        [ ClassWeights('0:1.0,1:1.0') ]              -- Binomial only; format 'class:weight,...'
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime' (Gaussian) / 'optimal' (Binomial)
        [ InitialEta(0.05) ]                         -- default 0.05; initial learning rate
        [ DecayRate(0.25) ]                          -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                            -- default 5; adaptive only
        [ Momentum(0) ]                              -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('true') ]                         -- default true; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                    -- default 0 (disabled); recommended 10 when enabled
        [ StepwiseDirection('forward'|'backward'|'both'|'bidirectional') ]
        [ MaxStepsNum(5) ]                           -- default 5; 0 = run until convergence
        [ InitialStepwiseColumns({ 'col' | col_range }[,...]) ]
) AS t;
```

**Mode 2 — PARTITION BY key (Micromodeling — one model per partition, trained in parallel):**

```sql
SELECT * FROM TD_GLM(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY partition_col [ ORDER BY id_col ]  -- ORDER BY ensures determinism when BatchSize < partition rows
    [ ON { db.table | db.view | (query) } AS AttributeTable
        PARTITION BY partition_col ]                    -- optional; per-partition feature subset
    [ ON { db.table | db.view | (query) } AS ParameterTable
        PARTITION BY partition_col ]                    -- optional; per-partition parameter overrides
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')
        [ PartitionColumn('partition_col') ]            -- required only if partition col uses unicode/foreign chars
        [ Family('Gaussian'|'Binomial') ]
        [ BatchSize(10) ]
        [ MaxIterNum(300) ]
        [ RegularizationLambda(0.02) ]
        [ Alpha(0.15) ]
        [ IterNumNoChange(50) ]
        [ Tolerance(0.001) ]
        [ Intercept('true') ]
        [ ClassWeights('0:1.0,1:1.0') ]
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]
        [ InitialEta(0.05) ]
        [ DecayRate(0.25) ]
        [ DecaySteps(5) ]
        [ Momentum(0) ]
        [ Nesterov('true') ]
        [ IterationMode('Batch'|'Epoch') ]              -- default 'Batch'; Micromodeling only
) AS t;
```

> `StepwiseDirection`, `MaxStepsNum`, `InitialStepwiseColumns`, and `LocalSGDIterations` are PARTITION BY ANY only. `IterationMode` is Micromodeling only.

**Model output — PARTITION BY ANY:**

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `SQUARED_ERROR`, `L2`) |

**Model output — Micromodeling** (partition column prepended):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `attribute` | SMALLINT | Same as above |
| `predictor` | VARCHAR | Same as above |
| `estimate` | FLOAT | Same as above |
| `value` | VARCHAR | Same as above |

**MetaInformationTable** (optional `OUT TABLE`, PARTITION BY ANY only):

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration number |
| `num_rows` | BIGINT | Rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |
| `Step` | INTEGER | [StepwiseDirection only] Step number |
| `SubStep` | INTEGER | [StepwiseDirection only] Feature sequence number |
| `Description` | VARCHAR | [StepwiseDirection only] Stage description; `+feature` = added, `-feature` = removed |
| `Score` | FLOAT | [StepwiseDirection only] Model score at each substep |
| `Model` | VARCHAR | [StepwiseDirection only] Variable names in model at this step |

**AttributeTable schema** (Micromodeling):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `attribute_column` | VARCHAR | Feature column names for this partition; column must be named `attribute_column`; no duplicates |

**ParameterTable schema** (Micromodeling):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `parameter_column` | VARCHAR | Parameter name (column must be named `parameter_column`) |
| `value_column` | VARCHAR | Parameter value (column must be named `value_column`) |

### Predict

**Mode 1 — PARTITION BY ANY:**

```sql
SELECT * FROM TD_GLMPredict(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ Family('Gaussian'|'Binomial') ]            -- must match Family used in TD_GLM training
        [ OutputProb('false') ]                      -- default false; Binomial only
        [ Responses('0'[,'1']) ]                     -- Binomial only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Mode 2 — Micromodeling:**

```sql
SELECT * FROM TD_GLMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY partition_col
    ON { db.table | db.view | (query) } AS ModelTable PARTITION BY partition_col  -- PARTITION BY, not DIMENSION
    USING
        IDColumn('id_col')
        [ PartitionColumn('partition_col') ]         -- required only if partition col uses unicode/foreign chars
        [ Family('Gaussian'|'Binomial') ]
        [ OutputProb('false') ]
        [ Responses('0'[,'1']) ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Unique observation identifier |
| `partition_by_column` | varies | [Micromodeling only] Model identifier |
| `prediction` | FLOAT | Predicted value |
| `prob` | FLOAT | [When `OutputProb('true')` and no `Responses`] Probability of predicted class (Binomial only) |
| `prob_0` | FLOAT | [When `Responses` specified] Probability of class 0 |
| `prob_1` | FLOAT | [When `Responses` specified] Probability of class 1 |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---

## TD_KMeans — Train/Predict

Unsupervised clustering algorithm that groups observations into k clusters by minimizing total within-cluster sum of squares (WCSS). Supports random or KMeans++ centroid initialization, Vector32 UDT input, and SIMD-accelerated distance computation.

**Constraints:**
- InputTable: no PARTITION BY column; PARTITION BY ANY (with optional ORDER BY) is allowed
- `NumClusters` and `InitialCentroidsTable` are mutually exclusive — provide one or the other
- Rows with NULL in any TargetColumn are skipped
- Model persisted via `OUT TABLE ModelTable(...)` clause

> **Elbow method:** `TD_WITHINSS_KMEANS` and `Total_WithinSS` (in `TD_MODELINFO_KMEANS`) expose WCSS per cluster and overall. Run multiple `TD_KMeans` calls with different `NumClusters` values combined with `UNION ALL` to collect WCSS across K values in a single query — then plot WCSS vs K to find the elbow. See `ml-patterns` topic for a full example.

### Train

```sql
SELECT * FROM TD_KMeans(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY column; PARTITION BY ANY allowed
    [ ON { db.table | db.view | (query) } AS InitialCentroidsTable DIMENSION ]
    [ OUT [ PERMANENT | VOLATILE ] TABLE ModelTable(db.model_table) ]
    USING
        IdColumn('id_col')                               -- required; unique row identifier
        TargetColumns({ 'col' | col_range }[,...])       -- required; all numeric; NULLs skipped
        [ NumClusters(k) ]                               -- required if no InitialCentroidsTable; mutually exclusive with it
        [ InitialCentroidsMethod('random'|'kmeans++') ]  -- default 'random'; ignored if InitialCentroidsTable provided
        [ NumInit(1) ]                                   -- default 1; repeat with different seeds, return model with lowest WCSS
        [ Seed(seed) ]                                   -- non-negative integer; ignored if InitialCentroidsTable provided
        [ MaxIterNum(10) ]                               -- default 10
        [ StopThreshold(0.0395) ]                        -- default 0.0395; stop when centroid movement < this value
        [ OutputClusterAssignment('false') ]             -- default false; true = row-level assignment output (see below)
        [ DistanceMeasure('Euclidean'|'Cosine') ]        -- default 'Euclidean'
        [ NormalizedVectors('false') ]                   -- default false; only applies when DistanceMeasure='Cosine'
        [ UseSIMD('false') ]                             -- default false; SIMD acceleration for vector distance ops
) AS t;
```

**Output — `OutputClusterAssignment('false')` (default) — centroid-level:**

| Column | Type | Description |
|--------|------|-------------|
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster identifier |
| `<TargetColumns>` | REAL | Centroid value for each feature |
| `TD_SIZE_KMEANS` | BIGINT | Number of points in this cluster |
| `TD_WITHINSS_KMEANS` | REAL | Within-cluster sum of squares for this cluster |
| `<id_column>` | BYTEINT | Copied from InputTable; always NULL in centroid output |
| `TD_MODELINFO_KMEANS` | VARCHAR(128) | Model summary: Converged, NumIterations, NumClusters, Total_WithinSS, Between_SS, InitialCentroidsMethod |

**Output — `OutputClusterAssignment('true')` — row-level assignment:**

| Column | Type | Description |
|--------|------|-------------|
| `<id_column>` | any | Row identifier from InputTable |
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster assigned to this row |

**InitialCentroidsTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `Initial_Clusterid_Column` | BYTEINT/SMALLINT/INTEGER/BIGINT | Unique centroid identifier |
| `<TargetColumns>` | numeric | Initial centroid values; must match TargetColumns in InputTable |

### Predict

```sql
SELECT * FROM TD_KMeansPredict(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY column; PARTITION BY ANY allowed
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION  -- must be DIMENSION; no PARTITION BY column
    USING
        [ OutputDistance('false') ]                      -- default false; include distance to assigned centroid
        [ Accumulate({ 'col' | col_range }[,...]) ]
        [ UseSIMD('false') ]                             -- default false; match UseSIMD used in TD_KMeans
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `<id_column>` | any | Row identifier; carried through from model — no IDColumn argument needed |
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster assigned to this row |
| `TD_DISTANCE_KMEANS` | REAL | Distance to assigned cluster centroid; only when `OutputDistance('true')` |
| `<accumulate_column(s)>` | any | Columns copied from InputTable |

---

## TD_KNN — K-Nearest Neighbors

Supervised classification and regression using nearest neighbors. **Does not follow the Train/Predict pattern** — KNN is a lazy learner that stores no model. The TrainingTable is passed directly as a DIMENSION input at prediction time; all distance computation happens then. There is no model table to save or reuse.

**Constraints:**
- `InputColumns` must match by **name and datatype** in both TestTable and TrainingTable
- `IDColumn` must be unique in both tables
- `ResponseColumn` class labels must be numeric; required for Classification/Regression; invalid for Neighbors
- `EmitNeighbors` cannot be set to false for `Neighbors` model type
- `OutputProb` and `Responses` are Classification only

```sql
SELECT * FROM TD_KNN(
    ON { db.table | db.view | (query) } AS TestTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS TrainingTable DIMENSION  -- training data passed directly; no model table
    USING
        IDColumn('id_col')                               -- required; unique identifier in both tables
        InputColumns({ 'col' | col_range }[,...])        -- required; must match by name AND datatype in both tables
        [ ModelType('Classification'|'Regression'|'Neighbors') ]  -- default 'Classification'
        [ K(5) ]                                         -- default 5; range 1–100
        [ ResponseColumn('response_col') ]               -- required for Classification/Regression; invalid for Neighbors
        [ VotingWeight(0) ]                              -- default 0 (uniform); weight = 1/distance^voting_weight
        [ Tolerance(0.0000001) ]                         -- default 0.0000001; distance floor when VotingWeight > 0
        [ OutputProb('false') ]                          -- default false; Classification only
        [ Responses('class1'[,...]) ]                    -- when OutputProb('true'); integer class labels; max 1000
        [ EmitNeighbors('false') ]                       -- default false; always true for Neighbors model type
        [ EmitDistances('false') ]                       -- default false
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as TestTable IDColumn | Test row identifier |
| `prediction` | same as ResponseColumn | Predicted value (Classification/Regression only) |
| `prob` | DOUBLE PRECISION | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_k` | DOUBLE PRECISION | When `Responses` specified; one column per response class |
| `neighbor_idk` | same as TrainingTable IDColumn | ID of neighbor k; when `EmitNeighbors('true')` |
| `neighbor_distk` | DOUBLE PRECISION | Euclidean distance of neighbor k; when `EmitDistances('true')` |
| `accumulate_column(s)` | same as input | Columns copied from TestTable |

---

## TD_NaiveBayes — Train/Predict

Probabilistic classifier based on Bayes' theorem. Assumes input variables are conditionally independent given the outcome. Supports both numeric and categorical inputs in dense (one column per feature) or sparse (attribute name/value pairs) format.

**Constraints:**
- Dense: at least one of `NumericInputs` or `CategoricalInputs` required
- Sparse: `AttributeNameColumn` + `AttributeValueColumn` required, plus one of `NumericAttributes`, `CategoricalAttributes`, or `AttributeType`
- No `OUT TABLE` clause — capture model via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`

### Train

**Dense input (one column per feature):**

```sql
SELECT * FROM TD_NaiveBayes(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        ResponseColumn('response_col')
        [ NumericInputs({ 'col' | col_range }[,...]) ]       -- at least one of NumericInputs or
        [ CategoricalInputs({ 'col' | col_range }[,...]) ]   -- CategoricalInputs required for dense
) AS t;
```

**Sparse input (attribute name/value pairs):**

```sql
SELECT * FROM TD_NaiveBayes(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        ResponseColumn('response_col')
        AttributeNameColumn('attr_name_col')                 -- required for sparse
        AttributeValueColumn('attr_value_col')               -- required for sparse
        { [ NumericAttributes('attr1'[,...]) ]               -- name specific numeric attributes
          [ CategoricalAttributes('attr1'[,...]) ]           -- name specific categorical attributes
        | AttributeType('ALLNUMERIC'|'ALLCATEGORICAL')       -- or declare all as one type
        }
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `class` | VARCHAR | Response value |
| `variable` | VARCHAR | Attribute name |
| `type` | VARCHAR | `'NUMERIC'` or `'CATEGORICAL'` |
| `category` | VARCHAR | NULL for NUMERIC; category value for CATEGORICAL |
| `cnt` | BIGINT | Observation count for this class/variable/category |
| `sum` | REAL | NUMERIC: sum of variable values; CATEGORICAL: NULL |
| `sumsq` | REAL | NUMERIC: sum of squared values; CATEGORICAL: NULL |
| `totalcnt` | BIGINT | Total observation count |
| `smoothingfactor` | REAL | NUMERIC: NULL; CATEGORICAL: smoothing factor |

### Predict

**Dense input:**

```sql
SELECT * FROM TD_NaiveBayesPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                                   -- required
        [ Responses('response1'[,...]) ]
        [ OutputProb('false') ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
        [ NumericInputs({ 'col' | col_range }[,...]) ]       -- at least one of NumericInputs or
        [ CategoricalInputs({ 'col' | col_range }[,...]) ]   -- CategoricalInputs required for dense
) AS t;
```

**Sparse input:**

```sql
SELECT * FROM TD_NaiveBayesPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')
        [ Responses('response1'[,...]) ]
        [ OutputProb('false') ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
        AttributeNameColumn('attr_name_col')                 -- required for sparse
        AttributeValueColumn('attr_value_col')               -- required for sparse
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Row identifier |
| `Prediction` | VARCHAR | Predicted class |
| `Loglik` | REAL | When no `Responses`; log likelihood of predicted value |
| `Prob` | REAL | When no `Responses` and `OutputProb('true')`; probability of predicted value |
| `Loglik_<response_i>` | REAL | When `Responses` specified; log likelihood per response value |
| `Prob_<response_i>` | REAL | When `Responses` specified and `OutputProb('true')`; probability per response value |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---

## TD_OneClassSVM — Train/Predict

Linear SVM for anomaly/novelty detection. All training data is assumed to belong to a single class (value 1) — no `ResponseColumn` needed. At predict time, outputs `1` (normal) or `0` (outlier). Uses the same Minibatch SGD engine as TD_GLM; see TD_GLM for SGD parameter details.

**Constraints:**
- `AS InputTable` alias is mandatory
- PARTITION BY ANY only — no micromodeling support
- No `ResponseColumn` — one-class training only
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `Nesterov` defaults to `false` here (unlike TD_GLM which defaults to `true`)

### Train

```sql
SELECT * FROM TD_OneClassSVM(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])     -- required; no ResponseColumn needed
        [ BatchSize(10) ]                             -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                           -- default 300
        [ RegularizationLambda(0.02) ]                -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                               -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                       -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                          -- default 0.001
        [ Intercept('true') ]                         -- default true
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime'
        [ InitialEta(0.05) ]                          -- default 0.05
        [ DecayRate(0.25) ]                           -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                             -- default 5; adaptive only
        [ Momentum(0) ]                               -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('false') ]                         -- default false; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                     -- default 0 (disabled); recommended 10 when enabled
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `HINGE` for LossFunction, `L2` for Regularization) |

**MetaInformationTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration (epoch) number |
| `num_rows` | BIGINT | Total rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |

### Predict

```sql
SELECT * FROM TD_OneClassSVMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ OutputProb('false') ]                      -- default false
        [ Responses('0'[,'1']) ]                     -- requires OutputProb('true'); 0 = outlier, 1 = normal
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Unique observation identifier |
| `prediction` | FLOAT | `0` = outlier, `1` = normal observation |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_0` | FLOAT | When `Responses` specified; probability of class 0 (outlier) |
| `prob_1` | FLOAT | When `Responses` specified; probability of class 1 (normal) |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---

## TD_SVM — Train/Predict

Linear SVM for binary classification (hinge loss) and regression (epsilon-insensitive loss). Uses the same Minibatch SGD engine as TD_GLM and TD_OneClassSVM. Classification supports binary response only (0 or 1).

**Constraints:**
- `AS InputTable` alias is mandatory
- PARTITION BY ANY only — no micromodeling support
- Classification: response values must be 0 or 1 (binary only)
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `Nesterov` defaults to `false` (unlike TD_GLM which defaults to `true`)
- `ModelType` must match between Train and Predict

### Train

```sql
SELECT * FROM TD_SVM(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')               -- required; classification: 0 or 1 only
        [ ModelType('Classification'|'Regression') ] -- default 'Classification'
        [ Epsilon(0.1) ]                             -- default 0.1; Regression only; epsilon-insensitive loss threshold
        [ BatchSize(10) ]                            -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                          -- default 300
        [ RegularizationLambda(0.02) ]               -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                              -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                      -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                         -- default 0.001
        [ Intercept('true') ]                        -- default true
        [ ClassWeights('0:1.0,1:1.0') ]              -- Classification only; format 'class:weight,...'
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime' (Regression) / 'optimal' (Classification)
        [ InitialEta(0.05) ]                         -- default 0.05
        [ DecayRate(0.25) ]                          -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                            -- default 5; adaptive only
        [ Momentum(0) ]                              -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('false') ]                        -- default false; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                    -- default 0 (disabled); recommended 10 when enabled
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `HINGE` for Classification, `EPSILON_INSENSITIVE` for Regression, `L2` for Regularization) |

**MetaInformationTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration (epoch) number |
| `num_rows` | BIGINT | Total rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |

### Predict

```sql
SELECT * FROM TD_SVMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ ModelType('Classification'|'Regression') ] -- default 'Classification'; must match TD_SVM training
        [ OutputProb('false') ]                      -- default false; Classification only
        [ Responses('0'[,'1']) ]                     -- requires OutputProb('true'); values 0 or 1
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Unique observation identifier |
| `prediction` | SMALLINT (Classification) / FLOAT (Regression) | Predicted class or value |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_0` | FLOAT | When `Responses` specified; probability of class 0 |
| `prob_1` | FLOAT | When `Responses` specified; probability of class 1 |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---

## TD_XGBoost — Train/Predict

Gradient boosted decision tree ensemble for classification and regression. Builds multiple boosted trees in parallel across AMPs. Supports multiclass classification (max 500 classes) and regression.

**Constraints:**
- InputTable: no PARTITION BY column; PARTITION BY ANY allowed
- All input columns must be numeric; no double-quoted column names
- Classification: `ResponseColumn` must be INTEGER/BIGINT/SMALLINT/BYTEINT
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `NumParallelTrees` and `CoverageFactor` are mutually exclusive
- `ModelType` must match between Train and Predict

### Train

```sql
SELECT * FROM TD_XGBoost(
    ON { db.table | db.view | (query) } AS INPUTTABLE [ PARTITION BY ANY ]  -- no PARTITION BY column
    [ OUT [ PERMANENT | VOLATILE ] TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])    -- required; all numeric; no double-quoted names
        ResponseColumn('response_col')               -- required; classification: INTEGER/BIGINT/SMALLINT/BYTEINT only
        [ ModelType('Classification'|'Regression') ] -- default 'Regression'
        [ MaxDepth(5) ]                              -- default 5; tree depth stopping criterion
        [ MinNodeSize(1) ]                           -- default 1; min node size stopping criterion
        [ NumParallelTrees(-1) ]                     -- default -1 (= num AMPs with data); range 1–10000
                                                     -- also accepts legacy name NumBoostedTrees
                                                     -- mutually exclusive with CoverageFactor
        [ CoverageFactor(1.0) ]                      -- default 1.0 (100%); mutually exclusive with NumParallelTrees
        [ NumBoostRounds(10) ]                       -- default 10; boosting iterations; range 1–100000
                                                     -- also accepts legacy name IterNum
        [ LearningRate(0.5) ]                        -- default 0.5; per-step shrinkage; range (0, 1]
                                                     -- also accepts legacy name ShrinkageFactor
        [ RegularizationLambda(1) ]                  -- default 1; L2 regularization; range [0, 100000]; 0 = none
        [ ColumnSampling(1.0) ]                      -- default 1.0; feature fraction per boost; range (0, 1]
        [ MinImpurity(0.0) ]                         -- default 0.0; stop splitting below this impurity
        [ TreeSize(-1) ]                             -- default -1 (auto); rows per tree input sample
        [ BaseScore(0) ]                             -- default 0 (Regression); 0.5 (Classification, must be in range (0,1))
        [ Seed(1) ]                                  -- default 1; random seed for column sampling
) AS t;
```

> **Small datasets / imbalanced classes:** Redistribute input to one AMP so each tree trains on a representative sample. Add a new column (e.g., `pi_col`) populated with a constant value and define it as the primary index — do not repurpose an existing column. For large clusters with small datasets, or classification with imbalanced classes, this redistribution significantly improves model quality.

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP that produced this tree |
| `tree_num` | SMALLINT | Boosted tree identifier |
| `iter` | SMALLINT | Boosting round number |
| `class_num` | SMALLINT | [Classification only] Class index; range [0, K-1] for K classes |
| `tree_order` | SMALLINT | Sequence number for multi-chunk JSON |
| `regression_tree` or `classification_tree` | VARCHAR(32000) | JSON decision tree per chunk |

**MetaInformationTable schema** (OUT TABLE — training accuracy per iteration):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP identifier |
| `iter` | SMALLINT | Boosting round number |
| `tree_num` | SMALLINT | Boosted tree identifier |
| `mse` / `accuracy` | DOUBLE | Regression: MSE per iteration; Classification: accuracy per iteration |
| `average residuals` / `deviance` | DOUBLE | Regression: avg residuals; Classification: deviance |

### Predict

```sql
SELECT * FROM TD_XGBoostPredict(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn({ 'id_col' | id_col_range })        -- required; no double-quoted names
        [ ModelType('Classification'|'Regression') ] -- default: DOUBLE output; 'Classification' = INTEGER output
        [ NumParallelTrees(1000) ]                   -- default 1000; limits trees loaded; fewer = faster but less accurate
                                                     -- also accepts legacy name NumBoostedTrees
        [ NumBoostRounds(10) ]                       -- default 10; limits iterations per tree; fewer = faster but less accurate
                                                     -- also accepts legacy name IterNum
        [ OutputProb('false') ]                      -- default false; Classification only
        [ Responses('response'[,...]) ]              -- Classification only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

> **Performance note:** `NumParallelTrees` and `NumBoostRounds` limit how much of the model is loaded at predict time — reducing either speeds up prediction but may reduce accuracy. When the model exceeds available memory, trees are cached in local spool, further impacting performance.

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Unique row identifier |
| `prediction` | DOUBLE PRECISION (default) / INTEGER (when `ModelType('Classification')`) | Predicted value or class |
| `confidence_lower` | DOUBLE PRECISION | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `confidence_upper` | DOUBLE PRECISION | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `prob` | DOUBLE PRECISION | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_response` | DOUBLE PRECISION | When `OutputProb('true')` and `Responses` specified; one column per response value |
| `accumulate_column(s)` | same as input | Columns copied from InputTable |
