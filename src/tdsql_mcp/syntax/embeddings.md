# Teradata Embedding Functions

Teradata provides three approaches to generating vector embeddings in-database. Choosing the right approach depends on where the model lives and what the embedding represents.

## Approach Comparison

| Function | Model location | Use case | Provider config |
|----------|---------------|----------|-----------------|
| `AI_TextEmbeddings` | External REST endpoint (cloud or self-hosted) | Modern LLM embeddings via Azure, AWS Bedrock, GCP, NVIDIA NIM, or LiteLLM | See `llm-providers` topic |
| `ONNXEmbeddings` | In-database BLOB table (BYOM) | Open-source Hugging Face models in ONNX format; air-gapped or latency-sensitive deployments | Model loaded into DB; see `byom-model-loading` topic |
| `TD_WordEmbeddings` | Pre-trained word vector table (GloVe format) | Classical word/document embeddings; token- and doc-level similarity | See `text-analytics` topic |

> **Recommendation:** Use `AI_TextEmbeddings` when you have access to a hosted embedding model API. Use `ONNXEmbeddings` when you need the model to run fully in-database (no external calls). Use `TD_WordEmbeddings` for GloVe-style word vectors.

> **OutputFormat:** Always use `OutputFormat('VECTOR')` when the embeddings will be stored, indexed, or used for similarity search. The `VECTOR` type integrates directly with `TD_VectorDistance`, `TD_HNSW`, and `TD_VectorNormalize`. See `data-types-casting` and `vector-search` topics.

---

## AI_TextEmbeddings

Generates text embeddings by calling an external LLM embedding model endpoint. Supports Azure, AWS Bedrock, Google Cloud, NVIDIA NIM, and LiteLLM. Parallelism and throughput are managed internally by the function and the endpoint.

> **Schema:** `TD_SYSFNLIB.AI_TextEmbeddings` — the schema qualifier is required.

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextEmbeddings(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one):
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; column containing text to embed
        [ OutputFormat('VECTOR'|'VARCHAR'|'VARBYTE') ]  -- default 'VARCHAR'; use 'VECTOR' for downstream use
        [ OutputPrecision('DOUBLE'|'FLOAT') ]           -- default 'DOUBLE'; ignored when OutputFormat is 'VARCHAR'
        [ OutputCharset('Latin'|'Unicode') ]            -- VARCHAR output only; default follows input column charset
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
        [ isDebug('false') ]                            -- default false; enables error logging
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Embeddings` | VECTOR, VARCHAR, or VARBYTE | Generated embedding for each input row |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**Quick examples by provider:**

```sql
-- Azure (AUTHORIZATION object)
SELECT * FROM TD_SYSFNLIB.AI_TextEmbeddings(
    ON db.documents AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('text-embedding-ada-002')
        TextColumn('doc_text')
        OutputFormat('VECTOR')
        Accumulate('doc_id', 'doc_title')
) AS t;

-- AWS Bedrock (inline credentials)
SELECT * FROM TD_SYSFNLIB.AI_TextEmbeddings(
    ON db.documents AS InputTable
    USING
        ApiType('aws')
        AccessKey('{AWS_ACCESS_KEY}')
        SecretKey('{AWS_SECRET_KEY}')
        Region('us-east-1')
        ModelName('amazon.titan-embed-text-v1')
        TextColumn('doc_text')
        OutputFormat('VECTOR')
        Accumulate('doc_id')
) AS t;

-- NVIDIA NIM (AUTHORIZATION object)
SELECT * FROM TD_SYSFNLIB.AI_TextEmbeddings(
    ON db.documents AS InputTable
    USING
        ApiType('nim')
        AUTHORIZATION(db.td_gen_nim_auth)
        ModelName('nvidia/nv-embedqa-e5-v5')
        TextColumn('doc_text')
        OutputFormat('VECTOR')
        Accumulate('doc_id')
) AS t;
```

> For full provider argument reference, see `llm-providers` topic.
> For AUTHORIZATION object creation, see `authorization-objects` topic.

---

## ONNXEmbeddings

Generates embeddings using an ONNX-format model stored as a BLOB in a Teradata table. No external API calls — the model runs entirely in-database. Uses Hugging Face open-source models converted to ONNX format, paired with a JSON tokenizer table.

> **Schema:** `[schema.]ONNXEmbeddings` — schema qualifier optional depending on installation.

> **BYOM architecture:** The model and tokenizer live in the database as BLOB columns. For model loading instructions, see `byom-model-loading` topic.

### Single model in ModelTable

```sql
SELECT * FROM ONNXEmbeddings(
    ON { db.table | db.view | (query) } AS InputTable   -- must have a column named 'txt'
    ON db.model_table AS ModelTable DIMENSION            -- single ONNX model as BLOB
    ON db.tokenizer_table AS TokenizerTable DIMENSION    -- JSON tokenizer as BLOB
    USING
        Accumulate('col1', 'col2')                       -- required; use '*' for all columns
        ModelOutputTensor('last_hidden_state')           -- required; valid output tensor name for the model
        [ EncodeMaxLength(512) ]                         -- default 512; max token length; only for variable-dimension models
        [ OutputFormat('VECTOR') ]                       -- default VARBYTE(3072); see format options below
        [ OutputColumnPrefix('emb_') ]                   -- default 'emb_'; prefix for FLOAT32 output columns
        [ ShowModelProperties('false') ]                 -- default false; true = show tensor properties only, no scoring
        [ UseCache('false') ]                            -- default false; true = load/reuse model from node cache
        [ OverwriteCachedModel('model_name') ]           -- use ONLY when replacing an updated model; see warning below
        [ EnableMemoryCheck('true') ]                    -- default true; verifies native memory before loading large models
) AS t;
```

### Multiple models in ModelTable

When the model table contains more than one model, use a `WHERE` clause to select exactly one — passing the full table without filtering causes an error.

```sql
SELECT * FROM ONNXEmbeddings(
    ON db.documents AS InputTable
    ON (SELECT * FROM db.model_table WHERE model_id = 'minilm-l6-v2') AS ModelTable DIMENSION
    ON db.tokenizer_table AS TokenizerTable DIMENSION
    USING
        Accumulate('*')
        ModelOutputTensor('last_hidden_state')
        OutputFormat('VECTOR')
) AS t;
```

**InputTable requirement:** the text column must be named `txt`.

**OutputFormat options:**

| Value | Description | Default size |
|-------|-------------|--------------|
| `VARBYTE(n)` | Packed binary; n = byte count | `VARBYTE(3072)` |
| `VECTOR` | Packed VECTOR type; n = byte count (must be divisible by 8) | 32000 bytes |
| `VECTOR(n)` | VECTOR with explicit byte size; n must be divisible by 8 | — |
| `FLOAT32` | Individual FLOAT32 columns; n = number of output columns | — |
| `VARCHAR(n)` | Text representation | — |
| `BLOB(n)` | Binary large object | — |

> **VECTOR byte size vs dimensions:** `VECTOR(3072)` means 3072 bytes, not 3072 dimensions. At DOUBLE precision (8 bytes/value), 3072 bytes = 384 dimensions. At FLOAT32 (4 bytes/value), 3072 bytes = 768 dimensions.

> **FLOAT32 output:** produces individual columns named `emb_0`, `emb_1`, ..., `emb_N` (or with custom prefix). A 384-dimension model with `OutputFormat('FLOAT32')` produces 384 float columns. Use `VECTOR` instead unless you specifically need column-per-dimension output.

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as InputTable | Columns specified in Accumulate |
| `sentence_embedding` | VARBYTE, VECTOR, FLOAT32, VARCHAR | Generated embedding; column name and type follow OutputFormat |
| `ModelProperties` | STRING | Tensor property info; only present when `ShowModelProperties('true')` |

**Model caching:**

ONNXEmbeddings caches loaded models in node memory for up to 7 days. Subsequent queries using the same model reuse the cache, avoiding reload cost.

```sql
-- Production: enable cache for repeated use
UseCache('true')

-- Inspect model tensor properties without scoring (no rows processed)
ShowModelProperties('true')
```

> **`OverwriteCachedModel` warning:** only use this argument when you have updated the model in the model table and need to evict the old cached version. Using it on unmodified models, in concurrent queries, or repeatedly in a short window can cause OOM errors from garbage collection lag. Default behavior (no argument) is safe.

---

## TD_WordEmbeddings

GloVe-style word and document embeddings using a pre-loaded word vector table. Supports token-embedding, doc-embedding, and similarity operations.

> See `text-analytics` topic for full syntax and usage patterns. Cross-reference: best for classical NLP pipelines; for modern semantic search use `AI_TextEmbeddings` or `ONNXEmbeddings` instead.

---

## Embedding Pipeline Patterns

### Pattern 1 — Generate and store embeddings

Generate embeddings once and persist them to a typed VECTOR table for reuse.

```sql
-- Step 1: generate embeddings and store as VECTOR
CREATE TABLE db.document_embeddings AS (
    SELECT doc_id, doc_title, Embeddings AS embedding
    FROM TD_SYSFNLIB.AI_TextEmbeddings(
        ON db.documents AS InputTable
        USING
            ApiType('azure')
            AUTHORIZATION(db.td_gen_azure_auth)
            DeploymentId('text-embedding-ada-002')
            TextColumn('doc_text')
            OutputFormat('VECTOR')
            Accumulate('doc_id', 'doc_title')
    ) AS t
) WITH DATA;

-- Step 2: normalize for cosine similarity (do once at storage time)
CREATE TABLE db.document_embeddings_norm AS (
    SELECT * FROM TD_VectorNormalize(
        ON db.document_embeddings AS InputTable PARTITION BY ANY
        USING
            IDColumns('doc_id')
            TargetColumns('embedding')
            Approach('UNITVECTOR')
            Accumulate('doc_title')
    ) AS t
) WITH DATA;
```

### Pattern 2 — Build HNSW index for fast search

```sql
-- Build the index on normalized embeddings
SELECT * FROM TD_HNSW(
    ON db.document_embeddings_norm AS InputTable
    OUT PERMANENT TABLE ModelTable(db.document_hnsw_index)
    USING
        IdColumn('doc_id')
        VectorColumn('embedding')
        DistanceMeasure('cosine')
        EfConstruction(64)
        ApplyHeuristics('true')
) AS t;
```

### Pattern 3 — Query pipeline (generate query embedding → search)

```sql
-- Embed the query, normalize, search — all in one query
WITH query_embedded AS (
    SELECT query_id, Embeddings AS embedding
    FROM TD_SYSFNLIB.AI_TextEmbeddings(
        ON (SELECT 1 AS query_id, 'find documents about supply chain risk' AS txt) AS InputTable
        USING
            ApiType('azure')
            AUTHORIZATION(db.td_gen_azure_auth)
            DeploymentId('text-embedding-ada-002')
            TextColumn('txt')
            OutputFormat('VECTOR')
            Accumulate('query_id')
    ) AS t
),
query_normalized AS (
    SELECT * FROM TD_VectorNormalize(
        ON query_embedded AS InputTable PARTITION BY ANY
        USING IDColumns('query_id') TargetColumns('embedding') Approach('UNITVECTOR')
    ) AS t
)
SELECT * FROM TD_HNSWPredict(
    ON db.document_hnsw_index AS ModelTable
    ON query_normalized AS InputTable DIMENSION
    USING
        IdColumn('query_id')
        VectorColumn('embedding')
        TopK(10)
        EfSearch(64)
        OutputSimilarity('true')
) AS t
ORDER BY nearest_neighbor_similarity DESC;
```

> **End-to-end:** documents are embedded and indexed once. At query time, only the query text hits the endpoint — the search runs entirely in-database against the HNSW index. See `vector-search` topic for full HNSW syntax.
