# Teradata BYOM — Model Loading

Teradata Vantage BYOM (Bring Your Own Model) allows externally trained models to be stored in the database as BLOB columns and scored in-database using native table operators. No data leaves the platform — the model comes to the data.

## Supported Model Formats

| Format | Scoring function(s) | File type | License required |
|--------|--------------------|-----------|--------------------|
| PMML | `PMMLPredict`, `PMMLPredictRT` | `.pmml` | No |
| H2O MOJO (open source) | `H2OPredict` | `pipeline.mojo` | No |
| H2O Driverless AI (DAI) | `H2OPredict` | `pipeline.mojo` | Yes — H2O DAI license |
| ONNX (scoring) | `ONNXPredict`, `ONNXPredictRT` | `.onnx` | No |
| ONNX (embeddings) | `ONNXEmbeddings` | `.onnx` + tokenizer | No |
| ONNX (seq2seq) | `ONNXSeq2Seq` | `.onnx` + tokenizer | No |
| ONNX (classification) | `ONNXClassification` | `.onnx` + tokenizer | No |
| Dataiku | `DataikuPredict` | `.jar` | No |
| DataRobot | `DataRobotPredict` | `.jar` (Scoring Code) | DataRobot account |
| MLeap | `MLeapPredict` | MLeap bundle | No |

> See `byom-scoring` topic for scoring function syntax. See `embeddings` topic for `ONNXEmbeddings` pipeline patterns.

---

## Model Table Schema

All BYOM model formats (PMML, H2O, ONNX, Dataiku, DataRobot, MLeap) share the same base table schema:

```sql
CREATE SET TABLE db.model_table (
    model_id  VARCHAR(30),    -- required; used to SELECT the model at score time
    model     BLOB            -- the model file loaded as binary
)
PRIMARY INDEX (model_id);
```

> **VantageCloud Lake:** model tables must be created in the Native Data Store (NDS).

> **Sizing:** allocate permanent space = avg_model_size × (expected_rows / num_AMPs) × num_AMPs. Add equivalent spool space.

### H2O DAI — additional license column (Option 2)

If storing the DAI license key in the model table rather than a separate table:

```sql
ALTER TABLE db.h2o_models ADD license VARCHAR(2500);

-- Set license for all rows
UPDATE db.h2o_models SET license = '<license_key_text>';

-- Or set for a specific model
UPDATE db.h2o_models SET license = '<license_key_text>'
WHERE model_id = 'pipeline_model';
```

### H2O DAI — separate license table (Option 1, recommended)

```sql
CREATE TABLE db.h2o_dai_lic (
    id      INTEGER BETWEEN 1 AND 1,   -- enforces exactly one row
    license VARCHAR(2500)
) UNIQUE PRIMARY INDEX (id);

INSERT INTO db.h2o_dai_lic VALUES (1, '<license_key_text>');

-- Rotate an expired license:
UPDATE db.h2o_dai_lic SET license = '<new_license_key>' WHERE id = 1;
```

> The column must be named `license`. The ID must be 1. Only one license per table — create separate tables for multiple licenses.

---

## Sparse Map Tables (Large Models)

For large models, a sparse map table reduces permanent space allocation at the cost of some query performance:

```sql
-- Create a sparse map across 8 AMPs
CREATE MAP sparse_map_8Amps FROM td_map1 SPARSE ampcount=8;

-- Create the model table on that map
CREATE TABLE db.onnx_models_sparse,
MAP = sparse_map_8Amps
(
    model_id  VARCHAR(30),
    model     BLOB(2097088000)
)
PRIMARY INDEX (model_id);
```

When querying with a sparse map model table, add `EXECUTE MAP` to the BYOM function call:

```sql
SELECT * FROM ONNXEmbeddings(
    ON db.input_data AS InputTable
    ON (SELECT model_id, model FROM db.onnx_models_sparse WHERE model_id = 'bge-small-en-v1.5') AS ModelTable DIMENSION
    ON (SELECT tokenizer FROM db.embedding_tokenizers WHERE tokenizer_id = 'bge-small-en-v1.5') AS TokenizerTable DIMENSION
    EXECUTE MAP = sparse_map_8Amps
    USING
        Accumulate('id')
        ModelOutputTensor('sentence_embedding')
        OutputFormat('VECTOR')
) AS t;
```

---

## Tokenizer Table (ONNX embedding, seq2seq, and classification functions)

`ONNXEmbeddings`, `ONNXSeq2Seq`, and `ONNXClassification` require a separate tokenizer table in addition to the model table. `ONNXPredict` and `ONNXPredictRT` do not.

```sql
CREATE SET TABLE db.embedding_tokenizers (
    tokenizer_id  VARCHAR(30),
    tokenizer     BLOB
)
PRIMARY INDEX (tokenizer_id);
```

The tokenizer file (`tokenizer.json`) is produced alongside the model when converting with `optimum-cli` (see ONNX section below). Load it using the same BTEQ or Python method as the model file.

---

## Loading Models

BYOM model loading is a one-time setup operation performed outside the MCP server. Use BTEQ, Teradata Studio, or the `teradatasql` Python package.

### BTEQ

Create a pipe-delimited text file mapping model IDs to file paths:

```
iris_rf_model|iris_rf_model.pmml
churn_model|churn_model.pmml
```

Then run in BTEQ:

```bteq
.import vartext file load_models.txt
.repeat *
USING (c1 VARCHAR(30), c2 BLOB AS DEFERRED BY NAME) INSERT INTO db.pmml_models(:c1, :c2);
```

Same pattern for all formats — only the file name changes.

### Python (teradatasql)

```python
import teradatasql

host     = 'your-teradata-host'
user     = 'your-user'
password = 'your-password'

model_id   = 'iris_rf_model'
model_file = 'iris_rf_model.pmml'   # replace with .pmml, .mojo, .onnx, .jar as needed
table      = 'db.pmml_models'

with teradatasql.connect(host=host, user=user, password=password) as con:
    with open(model_file, 'rb') as f:
        model_bytes = f.read()
    with con.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table} (model_id, model) VALUES (?, ?)",
            [model_id, model_bytes]
        )
    print(f"Loaded {model_id} into {table}")
```

Use the same script for tokenizer files — change the table name and variable names accordingly.

### Teradata Studio

```sql
INSERT INTO db.pmml_models VALUES ('iris_rf_model', ?);
```

The `?` opens a file browser GUI to select the model file. Suitable for ad-hoc loads; BTEQ or Python is preferred for automation.

---

## Model-Specific Notes

### PMML

Supported model types include: Anomaly Detection, Association Rules, Cluster, Decision Tree, General Regression, k-Nearest Neighbors, Multiple Models, Naive Bayes, Neural Network, Random Forest, Regression, Ruleset, Scorecard, Vector Machine.

File format: `.pmml`. No license required. PMML models may be generated directly by some tools or converted from other formats.

### H2O MOJO (Open Source and Driverless AI)

File format: `pipeline.mojo` (extracted from the downloaded zip — load only this file, not the full zip).

**For Driverless AI (DAI) models:**
1. In the DAI interface, select the experiment and download the MOJO scoring pipeline
2. Unzip the download
3. Load only `pipeline.mojo` into the model table
4. Load a license key using Option 1 (separate table) or Option 2 (column in model table) — see schema section above

H2O open source MOJO models do not require a license. Teradata recommends keeping DAI models in a separate table from open source models when using the license table approach (Option 1).

### ONNX (Scoring — ONNXPredict / ONNXPredictRT)

File format: `.onnx`. No tokenizer table required. Models can be exported natively from PyTorch, Caffe2, and Chainer, or converted from scikit-learn, TensorFlow, Keras, XGBoost, H2O, and Spark ML via the ONNX conversion toolkits.

### ONNX Embedding Models (ONNXEmbeddings / ONNXSeq2Seq / ONNXClassification)

Requires both a model table and a tokenizer table. Use the conversion workflow below to prepare models from Hugging Face.

**Step 1 — Convert to ONNX with optimum-cli:**

```bash
optimum-cli export onnx --opset 16 --trust-remote-code -m BAAI/bge-small-en-v1.5 bge-small-en-v1.5-onnx
```

This produces `model.onnx` and `tokenizer.json` in the output directory.

**Step 2 — Fix dimensions and opset for Vantage compatibility:**

```python
import onnx
import onnxruntime as rt

op = onnx.OperatorSetIdProto()
op.version = 16

model = onnx.load('bge-small-en-v1.5-onnx/model.onnx')

# Pin to IR version 8 with compatible opset
model_fixed = onnx.helper.make_model(model.graph, ir_version=8, opset_imports=[op])

# Fix variable dimension sizes
rt.tools.onnx_model_utils.make_dim_param_fixed(model_fixed.graph, 'batch_size', 1)
rt.tools.onnx_model_utils.make_dim_param_fixed(model_fixed.graph, 'sequence_length', 512)
rt.tools.onnx_model_utils.make_dim_param_fixed(model_fixed.graph, 'Divsentence_embedding_dim_1', 384)

# Remove token_embeddings output (not needed, reduces I/O)
for node in model_fixed.graph.output:
    if node.name == 'token_embeddings':
        model_fixed.graph.output.remove(node)
        break

onnx.save(model_fixed, 'bge-small-en-v1.5-onnx/model_fixed.onnx')
```

> Adjust `sequence_length` and `Divsentence_embedding_dim_1` to match the model's input tokens and output dimensions. See the validated models table below.

**Step 3 — Load model and tokenizer:**

```bteq
-- model
.import vartext file load_model.txt
.repeat *
USING (c1 VARCHAR(30), c2 BLOB AS DEFERRED BY NAME) INSERT INTO db.onnx_models(:c1, :c2);

-- tokenizer
.import vartext file load_tokenizer.txt
.repeat *
USING (c1 VARCHAR(30), c2 BLOB AS DEFERRED BY NAME) INSERT INTO db.embedding_tokenizers(:c1, :c2);
```

Where `load_model.txt` contains: `bge-small-en-v1.5|bge-small-en-v1.5-onnx/model_fixed.onnx`
And `load_tokenizer.txt` contains: `bge-small-en-v1.5|bge-small-en-v1.5-onnx/tokenizer.json`

**Pre-converted models:** Teradata-validated ONNX embedding models are available at [https://huggingface.co/Teradata](https://huggingface.co/Teradata). These are pre-converted and ready to load without the optimum-cli conversion step.

### Validated ONNX Embedding Models

| Model | License | Language | Parameters (M) | Input tokens | Output dims | ONNX size (fp32, MB) |
|-------|---------|----------|----------------|--------------|-------------|----------------------|
| bge-small-en-v1.5 | MIT | English | 33 | 512 | 384 | 127 |
| bge-base-en-v1.5 | MIT | English | 109 | 512 | 768 | 416 |
| bge-large-en-v1.5 | MIT | English | 335 | 512 | 1024 | 1275 |
| bge-m3 | MIT | Multi | 568 | 8192 | 1024 | — |
| distiluse-base-multilingual-cased-v1 | Apache-2.0 | Multi | 135 | 512 | 512 | 516 |
| gte-base-en-v1.5 | Apache-2.0 | English | 137 | 8192 | 768 | 530 |
| gte-large-en-v1.5 | Apache-2.0 | English | 434 | 8192 | 1024 | 1665 |
| gte-multilingual-base | Apache-2.0 | Multi | 305 | 8192 | 768 | 1197 |
| jina-embeddings-v2-small-en | Apache-2.0 | English | 33 | 8192 | 512 | 124 |
| jina-embeddings-v2-base-en | Apache-2.0 | English | 137 | 8192 | 768 | 522 |
| multilingual-e5-small | MIT | Multi | 118 | 512 | 384 | 449 |
| multilingual-e5-base | MIT | Multi | 278 | 514 | 768 | 1059 |
| multilingual-e5-large | MIT | Multi | 560 | 514 | 1024 | — |
| snowflake-arctic-embed-m-v2.0 | Apache-2.0 | Multi | 305 | 8192 | 768 | 1169 |
| snowflake-arctic-embed-l-v2.0 | Apache-2.0 | Multi | 568 | 8192 | 1024 | — |

> **Choosing a model:** smaller models (bge-small, jina-small) load faster and use less AMP memory; larger models produce richer embeddings. For multilingual content, use a Multi-language model. Output dimensions must match the `VECTOR(n)` byte size used in your embedding table (see `data-types-casting` and `embeddings` topics).

### Validated ONNXSeq2Seq Models

| Model |
|-------|
| JulesBelveze/t5-small-headline-generator |
| AventIQ-AI/t5-language-translation |
| google-t5/t5-small |
| google-t5/t5-base |
| Salesforce/codet5-small |
| google/flan-t5-base |
| utrobinmv/t5_translate_en_ru_zh_base_200 |

### Validated ONNXClassification Models

| Model |
|-------|
| lxyuan/distilbert-base-multilingual-cased-sentiments-student |
| j-hartmann/emotion-english-distilroberta-base |

### Dataiku

File format: `.jar` (Thin JAR — downloaded via Actions → Download as "thin" jar in Dataiku DSS).

**Naming rules:** The `model_id` in the model table must be the fully qualified Java class name from the Dataiku download dialog (e.g., `mypackage.MyModel`).

Package name rules:
- Lowercase letters, numbers, and dots only
- Cannot start or end with a dot, or have a number after a dot
- Cannot use Java reserved keywords (e.g., `new`, `case`, `class`)

Class name rules:
- Must start with an uppercase letter
- Uppercase and lowercase letters and numbers only
- Cannot start with a number or consist only of numbers

> Qualified class names are truncated if they exceed the `model_id` column size — size the column accordingly.

### DataRobot

File format: `.jar` (Scoring Code — Java). Download from:
- **Leaderboard:** Models → Leaderboard → select model → Predict → Portable Predictions → Scoring Code → Java → Prepare and download
- **Deployments:** Deployments → select deployment → Action menu → Get Scoring Code

> Downloading Scoring Code counts against your DataRobot billable deployments.

### MLeap

File format: MLeap bundle (zip). Same BLOB table schema as other formats. Supports Spark, MLeap, scikit-learn, and TensorFlow transformers for classification and regression — see `byom-scoring` topic for supported transformer list.
