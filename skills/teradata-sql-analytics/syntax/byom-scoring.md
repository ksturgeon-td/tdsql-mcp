# Teradata BYOM — Scoring Functions

Teradata Vantage BYOM scoring functions apply externally trained models to in-database data. All functions share a common two-table ON clause pattern (InputTable + ModelTable DIMENSION) and require `Accumulate`.

> **Prerequisites:** Models must be loaded into BLOB tables before scoring. See `byom-model-loading` topic for table schema and loading instructions.

## Common Patterns

**`Accumulate` is required** for all BYOM scoring functions. Use `'*'` to copy all InputTable columns.

**Single model in ModelTable:**
```sql
SELECT * FROM [schema.]ScoringFunction(
    ON db.input_data AS InputTable
    ON db.model_table AS ModelTable DIMENSION
    USING Accumulate('*')
) AS t;
```

**Multiple models in ModelTable — use WHERE to select one:**
```sql
SELECT * FROM [schema.]ScoringFunction(
    ON db.input_data AS InputTable
    ON (SELECT * FROM db.model_table WHERE model_id = 'my_model') AS ModelTable DIMENSION
    USING Accumulate('*')
) AS t;
```

**Model caching:** BYOM functions cache loaded models in node memory for up to 7 days. Use `OverwriteCachedModel` only when replacing an updated model — using it unnecessarily or in concurrent queries can cause OOM errors.

---

## Traditional ML Scoring

Functions for scoring PMML, H2O MOJO, ONNX (numeric/tabular), Dataiku, DataRobot, and MLeap models. These models are typically trained on structured/tabular data and return numeric predictions or class probabilities.


---

## PMMLPredict

Scores data using a PMML model stored in a Vantage BLOB table. Returns predictions and scoring output fields.

> **Default schema:** `mldb`. Specify an alternate schema if PMMLPredict is installed elsewhere.

```sql
SELECT * FROM [schema.]PMMLPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_identifier')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required; '*' copies all InputTable columns
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific PMML fields as columns instead of JSON
        [ OverwriteCachedModel('model_name'|'*'|'true'|'false') ]  -- only use when replacing an updated model
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**Input requirements:**
- InputTable must contain all columns the model requires, with matching names (case-insensitive) and compatible types
- Neither InputTable nor ModelTable may have a column named `dedicated` or `json_result`

**Compatible data types:**

| PMML type | Teradata types accepted |
|-----------|------------------------|
| Numeric | BYTEINT, SMALLINT, INTEGER, BIGINT, DECIMAL/NUMERIC, FLOAT/REAL/DOUBLE PRECISION, NUMBER |
| Categorical | CHAR, VARCHAR |

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `prediction` | VARCHAR | Present when the model result includes a `prediction` field; may be empty for classification models that return no predicted value |
| `json_report` | VARCHAR | JSON string of all scoring output fields; present only when `ModelOutputFields` is **not** specified |
| `model_output_field(s)` | VARCHAR or DOUBLE PRECISION | One column per field; present only when `ModelOutputFields` **is** specified; complex fields (array/map) returned as string |

> `json_report` and `ModelOutputFields` are mutually exclusive — specifying `ModelOutputFields` suppresses `json_report`.

**Example — full JSON output:**

```sql
SELECT * FROM PMMLPredict(
    ON db.iris_test AS InputTable
    ON (SELECT * FROM db.pmml_models WHERE model_id = 'iris_rf_model') AS ModelTable DIMENSION
    USING
        Accumulate('sample_id', 'species_actual')
) AS t;
```

**Example — specific output fields:**

```sql
SELECT * FROM PMMLPredict(
    ON db.iris_test AS InputTable
    ON (SELECT * FROM db.pmml_models WHERE model_id = 'iris_rf_model') AS ModelTable DIMENSION
    USING
        Accumulate('sample_id')
        ModelOutputFields('predicted_species', 'probability_setosa', 'probability_versicolor')
) AS t;
```

---

## H2OPredict

Scores data using an H2O MOJO model (open source or Driverless AI). Returns predictions, class probabilities, and optional explainability fields.

> **DAI license:** H2O Driverless AI models require a license key in the ModelTable or a separate license table. See `byom-model-loading` topic.

> **Default schema:** `mldb`.

```sql
SELECT * FROM [schema.]H2OPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_identifier')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required; '*' copies all InputTable columns; no BLOB/CLOB columns
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific fields as columns instead of JSON
        [ ModelType('DAI'|'OpenSource') ]               -- optional; specify model type explicitly
        [ EnableOptions('contributions','stageProbabilities','leafNodeAssignments') ]  -- add explainability fields to JSON
        [ OverwriteCachedModel('model_name'|'*'|'true'|'false') ]  -- only use when replacing an updated model
        [ UseCache('true') ]                            -- default true; set false if getting all-zero probabilities
        [ EnableMemoryCheck('true') ]                   -- default true; DAI models only; checks native memory before load
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**`EnableOptions` — explainability fields:**

| Value | Description | Applies to |
|-------|-------------|------------|
| `contributions` | Feature contribution toward each prediction | Binomial and regression models |
| `stageProbabilities` | Prediction probabilities at each tree stage/iteration | Binomial, regression, multinomial, AnomalyDetection |
| `leafNodeAssignments` | Leaf node placement for each row across all trees | Binomial, regression, multinomial, AnomalyDetection |

> `EnableOptions` values appear inside `json_report` by default. To return them as separate columns, list them in `ModelOutputFields` as well.

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `prediction` | VARCHAR | Present when JSON has a single entry — typically regression; for classification, class probabilities appear in `json_report` instead |
| `json_report` | VARCHAR | All model output fields as JSON; present only when `ModelOutputFields` is **not** specified |
| `model_output_field(s)` | VARCHAR or DOUBLE PRECISION | One column per field; present only when `ModelOutputFields` **is** specified |

> `UseCache` defaults to `true` — unlike most BYOM functions. If you observe all-zero probabilities, set `UseCache('false')` to force a fresh model load from the table.

**Example — DAI model with contributions:**

```sql
SELECT * FROM H2OPredict(
    ON db.churn_test AS InputTable
    ON (SELECT model_id, model, license FROM db.h2o_models WHERE model_id = 'pipeline_model') AS ModelTable DIMENSION
    USING
        Accumulate('customer_id', 'actual_churn')
        ModelType('DAI')
        EnableOptions('contributions')
) AS t;
```

**Example — open source model, specific output fields:**

```sql
SELECT * FROM H2OPredict(
    ON db.loan_applications AS InputTable
    ON db.h2o_os_models AS ModelTable DIMENSION
    USING
        Accumulate('application_id')
        ModelType('OpenSource')
        ModelOutputFields('predict', 'p0', 'p1')
) AS t;
```

---

## ONNXPredict

Scores data using an ONNX model stored in a Vantage BLOB table. Supports flexible input tensor mapping and an inspect mode to verify column-to-tensor mappings before scoring. No tokenizer table required (unlike `ONNXEmbeddings`, `ONNXSeq2Seq`, and `ONNXClassification`).

> **Default schema:** `mldb`.

```sql
SELECT * FROM [schema.]ONNXPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_identifier')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required
        [ ModelInputFieldsMap('tensor=col_spec' [,...]) ] -- map InputTable columns to ONNX input tensors
        [ ShowModelInputFieldsMap('false') ]            -- default false; true = inspect mapping without scoring
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific fields as columns instead of JSON
        [ OverwriteCachedModel('model_name'|'*'|'true'|'false') ]  -- only use when replacing an updated model
        [ EnableMemoryCheck('true') ]                   -- default true; checks native memory before loading large models
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**`ModelInputFieldsMap` — column-to-tensor mapping:**

Maps InputTable columns to ONNX model input tensor names. Use when column names don't match tensor names or when mapping multiple columns to one tensor.

```sql
-- Named columns
ModelInputFieldsMap('input_tensor=col1,col2,col3')

-- Named range (inclusive endpoints)
ModelInputFieldsMap('input_tensor=col1:col5')

-- Index range (1-based; inclusive endpoints)
ModelInputFieldsMap('input_tensor=[1:4]')

-- Index range — open ends
ModelInputFieldsMap('input_tensor=[:4]')    -- columns 1 through 4
ModelInputFieldsMap('input_tensor=[4:]')    -- column 4 through last
ModelInputFieldsMap('input_tensor=[:]')     -- all columns

-- Multiple tensors
ModelInputFieldsMap('tensor_a=[1:4]', 'tensor_b=[5:8]')
```

**`ShowModelInputFieldsMap` — inspect mode:**

When `true`, returns the fully expanded mapping as a string column without running scoring. Output columns that would normally contain scores are present but nulled out.

```sql
-- Use TOP 1 — one row is produced per AMP
SELECT TOP 1 * FROM ONNXPredict(
    ON db.iris_test AS InputTable
    ON db.onnx_models AS ModelTable DIMENSION
    USING
        Accumulate('*')
        ShowModelInputFieldsMap('true')
) AS t;
-- Returns: ModelInputFieldsMap('input=sepal_len,sepal_wid,petal_len,petal_wid')
```

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `json_report` | VARCHAR | All model output fields as JSON; present only when `ModelOutputFields` is **not** specified |
| `model_output_fields` | VARCHAR or DOUBLE | One column per field; present only when `ModelOutputFields` **is** specified |
| `model_input_fields_map` | STRING | Expanded mapping string; present only when `ShowModelInputFieldsMap('true')` |

> Unlike `PMMLPredict` and `H2OPredict`, `ONNXPredict` does not produce a `prediction` column — output is always via `json_report` or `ModelOutputFields`.

**Example:**

```sql
SELECT * FROM ONNXPredict(
    ON db.iris_test AS InputTable
    ON (SELECT * FROM db.onnx_models WHERE model_id = 'iris_onnx') AS ModelTable DIMENSION
    USING
        Accumulate('sample_id')
        ModelInputFieldsMap('float_input=[1:4]')
        ModelOutputFields('output_label', 'output_probability')
) AS t;
```

---

## DataikuPredict

Scores data using a Dataiku DSS model (Thin JAR) stored in a Vantage BLOB table.

> **`model_id` must be the fully qualified Java class name** from the Dataiku download dialog (e.g., `mypackage.MyModel`). See `byom-model-loading` topic for Dataiku naming rules.

> **Default schema:** `mldb`.

```sql
SELECT * FROM [schema.]DataikuPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'mypackage.MyModel')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific fields as columns instead of JSON
        [ OverwriteCachedModel('model_name'|'*') ]      -- only use when replacing an updated model
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `json_report` | VARCHAR | All model output fields as JSON; present only when `ModelOutputFields` is **not** specified |
| `model_output_fields` | VARCHAR or DOUBLE | One column per field; present only when `ModelOutputFields` **is** specified |

**Example:**

```sql
SELECT * FROM DataikuPredict(
    ON db.customer_features AS InputTable
    ON (SELECT * FROM db.dataiku_models WHERE model_id = 'com.mycompany.ChurnModel') AS ModelTable DIMENSION
    USING
        Accumulate('customer_id', 'segment')
        ModelOutputFields('prediction', 'proba_0', 'proba_1')
) AS t;
```

---

## DataRobotPredict

Scores data using a DataRobot Scoring Code model (JAR) stored in a Vantage BLOB table.

> **DataRobot explanations are not supported** by this function.

> **Date/timestamp columns must be cast to character** before scoring — see note below.

> **Default schema:** `mldb`.

```sql
SELECT * FROM [schema.]DataRobotPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_identifier')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required; no BLOB/CLOB columns
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific fields as columns instead of JSON
        [ OverwriteCachedModel('model_name'|'*'|'true'|'false') ]  -- only use when replacing an updated model
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**Date/timestamp type requirement:**

DataRobot's scoring library requires date columns in the same character format used during model training. Cast any `DATE` or `TIMESTAMP` InputTable columns to character before passing them in:

```sql
SELECT * FROM DataRobotPredict(
    ON (
        SELECT
            customer_id,
            feature1,
            TO_CHAR(best_date, 'MM/DD/YYYY') AS best_date   -- match format used in DataRobot training
        FROM db.customer_features
    ) AS InputTable
    ON (SELECT * FROM db.dr_models WHERE model_id = 'churn_v3') AS ModelTable DIMENSION
    USING
        Accumulate('customer_id')
        ModelOutputFields('prediction', 'positive_probability')
) AS t;
```

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `json_report` | VARCHAR | All model output fields as JSON; present only when `ModelOutputFields` is **not** specified |
| `model_output_fields` | VARCHAR or DOUBLE | One column per field; present only when `ModelOutputFields` **is** specified |

---

## MLeapPredict

Scores data using an MLeap model bundle stored in a Vantage BLOB table. Supports column-to-input mapping like `ONNXPredict`.

> **Default schema:** `mldb`.

```sql
SELECT * FROM [schema.]MLeapPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_identifier')
       } AS ModelTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })              -- required
        [ ModelInputFieldsMap('input=col_spec' [,...]) ] -- map InputTable columns to MLeap model inputs
        [ ModelOutputFields('output_field' [,...]) ]    -- output specific fields as columns instead of JSON
        [ OverwriteCachedModel('model_name'|'*'|'true'|'false') ]  -- only use when replacing an updated model
        [ IsDebug('false') ]                            -- default false; requires trace table pre-created
) AS t;
```

**`ModelInputFieldsMap`:** Same column range syntax as `ONNXPredict` — named columns, named ranges (`col1:col5`), and index ranges (`[1:5]`, `[:4]`, `[4:]`, `[:]`). See ONNXPredict section above for full syntax reference.

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `json_report` | VARCHAR | All model output fields as JSON; present only when `ModelOutputFields` is **not** specified |
| `model_output_fields` | VARCHAR or DOUBLE | One column per field; present only when `ModelOutputFields` **is** specified |

**Supported model types** (classification and regression): Decision Tree, Gradient Boosted Tree, Logistic Regression, Naive Bayes, Random Forest, SVM, MLP, and more. See `byom-model-loading` topic for the full transformer support matrix.

**Example:**

```sql
SELECT * FROM MLeapPredict(
    ON db.loan_features AS InputTable
    ON (SELECT * FROM db.mleap_models WHERE model_id = 'loan_risk_v2') AS ModelTable DIMENSION
    USING
        Accumulate('loan_id', 'applicant_id')
        ModelOutputFields('prediction', 'probability')
) AS t;
```

---

## NLP / Transformer Model Scoring

Functions for scoring Hugging Face transformer models converted to ONNX format. These models operate on text input and output text or classification results. Both functions require a tokenizer table alongside the model table — see `byom-model-loading` topic.

> **Architecture distinction:** These functions run models entirely in-database (no external API call). For REST-based LLM text analytics, see `ai-text-analytics` topic instead.

---

## ONNXSeq2Seq

Applies a Hugging Face sequence-to-sequence ONNX model to text input — for tasks such as translation, summarization, and text generation. Both input and output are text strings.

> **Three-table input:** Requires InputTable, ModelTable DIMENSION, and TokenizerTable DIMENSION.

> **InputTable must have a column named `txt`** — the text to tokenize and score.

> **Output column name** is determined by the `ModelOutputTensor` argument — not a fixed name.

```sql
SELECT * FROM [schema.]ONNXSeq2Seq(
    ON { db.table | db.view | (query) } AS InputTable         -- must have a column named 'txt'
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_id')
       } AS ModelTable DIMENSION
    ON db.tokenizer_table AS TokenizerTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })                    -- required; no BLOB/CLOB columns
        ModelOutputTensor('tensor_name')                      -- required; determines output column name
        [ EncodeMaxLength(512) ]                              -- default 512; max encoded token length; variable-dimension models only
        [ OutputLength(1000) ]                                -- default 1000; max chars for VARCHAR output; auto-promotes to CLOB above 32000
        [ SkipSpecialTokens('true') ]                         -- default true; when false, special tokens appear in output
        [ ShowModelProperties('false') ]                      -- default false; true = show tensor properties only, no scoring
        [ UseCache('false') ]                                 -- default false; true = load/reuse from node cache
        [ OverwriteCachedModel('model_name'|'*') ]            -- only use when replacing an updated model
        [ EnableMemoryCheck('true') ]                         -- default true; checks native memory before loading large models
        [ Const_<constant_name>(value) ]                      -- optional; pass constant values to model inputs
) AS t;
```

**`Const_NAME` — model constants:**

Passes a constant value to a named model input tensor without adding it as a column to every input row. Reduces overhead for model inputs that don't vary per row:

```sql
-- Example: pass a fixed max_length constant to the model
Const_max_length(128)
Const_num_beams(4)
```

**`OutputLength`:** Sets the maximum VARCHAR output length in characters. Default is 1000. Unicode VARCHAR maximum is 32000 — if `OutputLength` exceeds this, the output column is automatically created as CLOB.

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| `<ModelOutputTensor>` | VARCHAR (or CLOB) | Generated sequence output; column name matches `ModelOutputTensor` value |
| `ModelProperties` | STRING | Tensor property info; present only when `ShowModelProperties('true')` |

**Example — translation:**

```sql
SELECT * FROM ONNXSeq2Seq(
    ON (SELECT doc_id, doc_text AS txt FROM db.french_docs) AS InputTable
    ON (SELECT * FROM db.onnx_models WHERE model_id = 'AventIQ-AI/t5-language-translation') AS ModelTable DIMENSION
    ON (SELECT tokenizer FROM db.embedding_tokenizers WHERE tokenizer_id = 'AventIQ-AI/t5-language-translation') AS TokenizerTable DIMENSION
    USING
        Accumulate('doc_id')
        ModelOutputTensor('output_text')
        OutputLength(2000)
        UseCache('true')
) AS t;
```

---

## ONNXClassification

Applies a Hugging Face classification ONNX model to text input. Returns raw scores, softmax probabilities, argmax results, or individually named classification columns — controlled by `ModelOutputFieldsMap` and `OutputFormat`.

> **Three-table input:** Requires InputTable, ModelTable DIMENSION, and TokenizerTable DIMENSION.

> **InputTable must have a column named `txt`** — alias your text column to `txt` if needed.

> **`ModelOutputFieldsMap` and `OutputFormat` are both required** and must have the same number of entries (one OutputFormat per mapping entry).

```sql
SELECT * FROM [schema.]ONNXClassification(
    ON { db.table | db.view | (query) } AS InputTable         -- must have a column named 'txt'
    ON { db.model_table |
        (SELECT * FROM db.model_table WHERE model_id = 'model_id')
       } AS ModelTable DIMENSION
    ON db.tokenizer_table AS TokenizerTable DIMENSION
    USING
        Accumulate({ 'col' [,...] | '*' })                    -- required; no BLOB/CLOB columns
        ModelOutputFieldsMap('mapping' [,...])                -- required; maps output tensors to columns
        OutputFormat('sql_type' [,...])                       -- required; one SQL type per mapping entry
        [ EncodeMaxLength(512) ]                              -- default 512; range 1–131072
        [ ShowModelProperties('false') ]                      -- default false; true = show tensor properties, no scoring
        [ SkipSpecialTokens('true') ]                         -- default true; false = include special tokens in output
        [ UseCache('false') ]                                 -- default false; true = load/reuse from node cache
        [ OverwriteCachedModel('model_name'|'*') ]            -- only use when replacing an updated model
        [ EnableMemoryCheck('true') ]                         -- default true; checks native memory before loading
        [ IsDebug('false') ]                                  -- default false; requires trace table pre-created
        [ Const_<constant_name>(value) ]                      -- optional; pass constant values to model inputs
) AS t;
```

**`ModelOutputFieldsMap` mapping types:**

The mapping syntax controls both the output column names and whether softmax/argmax transformations are applied.

| Mapping syntax | OutputFormat type | Output columns |
|----------------|-------------------|----------------|
| `'tensor'` | Non-array type | Single column named `tensor` |
| `'tensor'` | Array type | Multiple columns: `tensor_0`, `tensor_1`, ... |
| `'tensor=col'` | Non-array type | Single column named `col` |
| `'tensor=col'` | Array type | Multiple columns: `col_0`, `col_1`, ... |
| `'tensor=col1,col2,col3'` | Array type | Columns named `col1`, `col2`, `col3` |
| `'softmax(tensor)=col'` | Non-array type | Single softmax-computed column named `col` |
| `'softmax(tensor)=col'` | Array type | Multiple softmax columns: `col_0`, `col_1`, ... |
| `'softmax(tensor)=col1,col2,col3'` | Array type | Softmax columns with custom names |
| `'argmax(tensor)=col'` | Any | Two columns: `col_0` (index), `col_1` (value) |
| `'argmax(tensor)=idx,val'` | Any | Two columns named `idx` (index) and `val` (value) |
| `'argmax(softmax(tensor))=col'` | Any | Argmax applied to softmax values; same column structure as argmax |

**Example — sentiment classification with softmax probabilities:**

```sql
SELECT * FROM ONNXClassification(
    ON (SELECT review_id, review_text AS txt FROM db.reviews) AS InputTable
    ON (SELECT * FROM db.onnx_models WHERE model_id = 'lxyuan/distilbert-base-multilingual-cased-sentiments-student') AS ModelTable DIMENSION
    ON (SELECT tokenizer FROM db.embedding_tokenizers WHERE tokenizer_id = 'lxyuan/distilbert-base-multilingual-cased-sentiments-student') AS TokenizerTable DIMENSION
    USING
        Accumulate('review_id')
        ModelOutputFieldsMap('softmax(logits)=negative,neutral,positive')
        OutputFormat('FLOAT')
        UseCache('true')
) AS t;
-- Output columns: review_id, negative, neutral, positive (softmax probabilities)
```

**Example — argmax predicted class:**

```sql
SELECT * FROM ONNXClassification(
    ON (SELECT doc_id, doc_text AS txt FROM db.documents) AS InputTable
    ON db.onnx_classifiers AS ModelTable DIMENSION
    ON db.tokenizers AS TokenizerTable DIMENSION
    USING
        Accumulate('doc_id')
        ModelOutputFieldsMap('argmax(softmax(logits))=predicted_class_idx,predicted_class_score')
        OutputFormat('INTEGER')
        UseCache('true')
) AS t;
-- Output columns: doc_id, predicted_class_idx, predicted_class_score
```

**Output columns:**

| Column | Type | Condition |
|--------|------|-----------|
| `accumulate_col(s)` | same as InputTable | Always present |
| Mapping-determined columns | matches OutputFormat | Names and count determined by `ModelOutputFieldsMap`; see mapping types table above |
| `ModelProperties` | STRING | Present only when `ShowModelProperties('true')` |


