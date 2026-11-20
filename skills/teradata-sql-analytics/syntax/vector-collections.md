# Teradata Vector Collections (TD_SYSAI Stored Procedures)

High-level RAG over Teradata tables through the Vector Store SQL interface: a handful of `TD_SYSAI.*` stored procedures that build the embeddings, the index, and the retrieval + answer-generation steps for you. Docs: *Teradata Vector Store User Guide → SQL Interface for Vector Store* (Release 20.00).

> **When to use this vs. the raw functions.** Use vector collections when the goal is "ask questions over the text in these tables" and you want embedding generation, indexing, refresh, access control and LLM answering managed in one object. Use `embeddings` + `vector-search` (`AI_TextEmbeddings`, `TD_HNSW`, `TD_VectorDistance`) when you need control over each pipeline step, a custom distance or index layout, or you are not generating answers with an LLM.

> **Verification key.** Behavior marked **(verified)** was run on Teradata 20.00.31.96 (VantageCloud 3.4) with AWS Bedrock. Everything else is **documented, unverified**.

---

## Workflow

```
CreateCollection  ->  CheckCollectionStatus (until 'ready')  ->  Ask                       (search + answer, one call)
                                                              ->  SimilaritySearch          (retrieval only)
                                                                  -> PrepareResponse         (answer from a context table)
UpdateCollection (data refresh / schema change) · DestroyCollection (drops all collection objects)
```

`CreateCollection` is synchronous for small tables: it returned `collection_status = 'ready'` directly **(verified)**. Still call `CheckCollectionStatus` for large tables.

---

## Reading results and errors

Every procedure returns a result set.

| Outcome | Result set columns | Notes |
|---------|--------------------|-------|
| Success (admin procs) | `collection_name, collection_status, status, message` (Create/Update); `status, message` (Destroy) | `status = 0` |
| Failure | `status, err_info` | `status = 1` invalid usage (bad JSON, bad value); `status = 2` SQL/model error (e.g. LLM call failed) |

**(verified)** Some SQL clients and MCP tools do not return a stored procedure's result set at all (rows come back empty even for failures). If a `CALL` returns nothing, confirm state with:

```sql
SELECT collection_name, collection_status, error_message
FROM TD_SYSAI.TD_CollectionsV;
```

or use a client that fetches procedure result sets (e.g. `teradatasql` with `cursor.nextset()`).

---

## CreateCollection

```sql
CALL TD_SYSAI.CreateCollection(
    'collection_name',
    'CONTENT-BASED',                -- collection type (see Limitations)
    'target_database',              -- database that receives the collection's index/model objects
    'description',
    '<collection_index_json>',      -- source data (required)
    '<collection_parameters_json>', -- embedding/chat models and tuning
    0                               -- debug: 1 writes to TD_SYSAI.vector_collection_logs
);
```

**collection_index_json (verified)** — each value is a **list**; `object_names` entries are qualified `db.table` names:

```json
{
  "object_names": ["demo_user.support_docs"],
  "key_columns": ["doc_id"],
  "metadata_columns": ["category"],
  "data_columns": ["doc_text"]
}
```

- `data_columns` are the text columns that are embedded. `metadata_columns` are returned with results and usable in filters; they are optional **(verified)**.
- Using `{"object_names": {"db": ["t"]}}` fails with `object_names must be a List`.

**collection_parameters_json (verified)** — minimal working example (AWS Bedrock):

```json
{
  "train_params": {"search_algorithm": "HNSW"},
  "embedding_model": {"model_provider": "aws", "model_id": "amazon.titan-embed-text-v2:0"},
  "chat_model": {"model_provider": "aws", "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0"}
}
```

> **Credentials.** On the test system, `credentials` could be omitted entirely and embedding, search and `Ask` all worked **(verified)**. This is environment-dependent (the cluster had AWS access without per-collection keys); on other systems supply `credentials` inline or confirm the platform default with an administrator. Collection metadata (`GetCollectionInfo`, `TD_CollectionsV`) shows `credentials` as null even when supplied inline **(verified)**. Whether an authorization object (`authorization-objects` topic) can be referenced instead is **not yet confirmed**.

> **Never use `debug = 1` with inline credentials.** The debug log (`TD_SYSAI.vector_collection_logs`) records the full parameters JSON, including `api_key` and `api_secret`, in plaintext **(verified)**.

> **Chat model IDs go stale.** The documentation example `anthropic.claude-3-haiku-20240307-v1:0` fails with *"This model version has reached the end of its life"*; `anthropic.claude-3-5-haiku-20241022-v1:0` fails the same way. A current Bedrock inference-profile ID (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) worked **(verified)**. Check provider availability before copying IDs.

---

## CheckCollectionStatus / GetCollectionInfo / ListCollections

```sql
CALL TD_SYSAI.CheckCollectionStatus('c');         -- collection_status, status, message
CALL TD_SYSAI.GetCollectionInfo('c', 0);          -- basic: one row (name, status, type, description, target_database, permission, last_updated, status, message)
CALL TD_SYSAI.GetCollectionInfo('c', 1);          -- detailed: adds error_message, embedding_datatype, use_simd, object/key/metadata/data columns,
                                                  --   search_params, train_params, embedding_model, chat_model, search_strategy, collection_payload ...
CALL TD_SYSAI.ListCollections(0);                 -- every collection on the system; Permission = NO_ACCESS for ones you cannot use
CALL TD_SYSAI.ListCollections(1);                 -- only collections you are authorized for
```

All **(verified)**. States seen: `ready`, `initialized`, `update_failed`. Types seen in listings: `CONTENT-BASED`, `FILE-CONTENT-BASED`. A missing collection returns `status 1`, `err_info "Collection 'x' does not exist."`.

---

## SimilaritySearch (retrieval only)

```sql
CALL TD_SYSAI.SimilaritySearch(
    'collection_name',
    'natural language question',    -- or NULL when passing question_vector
    NULL,                           -- question_vector (NULL = embed the question with the collection's embedding model)
    NULL,                           -- similarity_search_request_json (NULL = collection defaults)
    0
);
```

Returns one row per hit: `score, DataBaseName, TableName, TD_ID, <key columns>, <metadata columns>, <data columns>`, highest score first **(verified)**. Default `top_k` returned up to 10 rows.

**Request JSON — filter, top_k, and persisted results (verified):**

```json
{
  "search_params": {"top_k": 2},
  "filter_params": {"condition": "category <> 'returns'", "style": "PRE-FILTERING"},
  "result_table_name": "demo_user.search_results"
}
```

- `style` is `PRE-FILTERING` or `POST-FILTERING` — **with a hyphen**. The documentation's underscore form (`PRE_FILTERING`) fails with `Unsupported filter style`.
- `condition` is a SQL predicate over the metadata columns.
- With `result_table_name` the hits are also written to that table (created as a NoPI table) and still returned.

---

## Ask (retrieval + answer)

```sql
CALL TD_SYSAI.Ask('collection_name', 'How long do I have to return an item?', NULL, NULL, 0);
```

Returns a single `response` column containing the LLM answer grounded in the retrieved rows **(verified)**. `Ask` does not create a result table **(verified)**.

The request JSON (4th argument) can override `search_params`, `chat_model`, etc. for this call (e.g. swap a retired chat model without recreating the collection). `search_strategy.search_type` **cannot** be changed per call; `hybrid_search` must be chosen when the collection is created **(verified error: "cannot be updated to hybrid_search")**.

---

## PrepareResponse (answer from your own context)

Generates an answer from a context table you supply — typically the `result_table_name` output of `SimilaritySearch`, optionally after re-ranking or filtering it yourself.

```sql
CALL TD_SYSAI.PrepareResponse('collection_name', 'When can I call support?', 'demo_user.search_results', NULL, 0);
```

Returns a single `response` column **(verified)** using a `SimilaritySearch` result table as context. The 4th argument is the same request JSON (e.g. a `chat_model` override).

---

## UpdateCollection

```sql
CALL TD_SYSAI.UpdateCollection(
    'collection_name',
    'new description',     -- or NULL
    NULL,                  -- collection_index_json (alter_operation ADD|DELETE, update_style MINOR|MAJOR, metadata_operation ADD|DELETE|MODIFY)
    NULL,                  -- collection_parameters_json
    NULL,                  -- New_Collection_Name
    1,                     -- Data_Refresh: INTEGER, 1 = re-embed new/changed source rows
    0
);
```

- `Data_Refresh` is numeric; passing `'true'` fails with a string-to-numeric conversion error **(verified)**.
- After inserting a row into the source table, `Data_Refresh = 1` made it searchable (it became the top hit for a matching question) **(verified)**. Rows added **without** a refresh are not found **(verified)**.
- Description-only update **(verified)**.
- MINOR vs MAJOR `update_style`, index alterations, and rename are **documented, unverified**.

---

## DestroyCollection

```sql
CALL TD_SYSAI.DestroyCollection('collection_name', 0);
```

Drops the collection and all objects it created in `target_database` (index table, HNSW model, views) **(verified)**. Your source tables and any `result_table_name` tables are **not** dropped.

---

## Permissions

```sql
CALL TD_SYSAI.ListCollectionPermissions('collection_name');   -- User_Name, Permission   (verified: creator = ADMIN)
CALL TD_SYSAI.ModifyCollectionPermissions('collection_name',
    '{"user_names": ["alice","bob"], "actions": ["GRANT","REVOKE"], "permissions": ["USER","ADMIN"]}', 0);
```

The three arrays in the JSON are parallel (alice is granted USER, bob has ADMIN revoked). `ModifyCollectionPermissions` is **documented, unverified** — full action/permission lists unconfirmed.

---

## Parameter reference (collection_parameters_json blocks)

| Block | Keys |
|-------|------|
| `embedding_model` | `model_provider` (`aws`\|`azure`\|`gcp`\|`nim`\|`custom`; mandatory on 3.5), `model_id`, `model_modality` (`text`; `multimodal` not on 3.4), `embedding_dims`, `base_url`, `credentials{api_key, api_secret, access_token, project_id, region, arn_role_name, bucket_name}` |
| `onnx_model` | `model_table, tokenizer_table, model_column, tokenizer_column, model_id_column, tokenizer_id_column, model_id, tokenizer_id` (in-database ONNX embeddings instead of a remote provider) |
| `chat_model` | `model_provider, model_id, model_modality` (`LLM`; `VLM` not on 3.4), `base_url, max_tokens, prompt, temperature, credentials` |
| `train_params` | `search_algorithm` (`FLAT`\|`IVF_FLAT`\|`HNSW`), `metric` (`COSINE`\|`EUCLIDEAN`\|`DOTPRODUCT`); IVF_FLAT: `initial_centroids_method` (`RANDOM`\|`KMEANS++`), `train_numcluster, max_iternum, stop_threshold, num_init`; HNSW: `num_layer, ef_construction, num_connPerNode, maxNum_connPerNode, num_NodesPerGraph, apply_heuristics`; `seed` |
| `search_params` | `top_k` **or** `search_threshold` (not both), `search_numcluster` (IVF_FLAT), `ef_search` (HNSW) |
| `search_strategy` | `search_type` (`semantic_search`\|`relevance_search`\|`hybrid_search`), `relevance_top_k, relevance_search_threshold`, `scoring_method` (`weighted_sum`\|`rrf`\|`weighted_rrf`), `sparse_weight, rrf_normalizer, maximal_marginal_relevance, lambda_multiplier, mmr_threshold` |
| top level | `embedding_datatype` (`VECTOR`\|`VECTOR32`), `use_simd, ignore_embedding_errors, batch, enable_inference_profile` |

**Defaults observed on 20.00.31.96 (verified):** `VECTOR32`, `use_simd` 0, `COSINE`, `top_k` 10, `relevance_top_k` 60, `semantic_search`; HNSW `num_layer` -1 (auto), `ef_construction` 32, `num_connPerNode` 32, `maxNum_connPerNode` 32, `apply_heuristics` true, `seed` 0; chat `max_tokens` 4096, `temperature` 0.2. `embedding_dims` is filled in from the model (1024 for `amazon.titan-embed-text-v2:0`). These differ from some values shown in the documentation's detailed-info sample; trust `GetCollectionInfo(name, 1)` on your system.

---

## Limitations

| | Cloud 3.5 (20.00.32.xx) | Cloud 3.4 (20.00.31.xx) |
|---|---|---|
| Collection types | `CONTENT-BASED`, `EMBEDDING-BASED` | same |
| `model_provider` | mandatory | accepted |
| Ranking model, guardrails, telemetry | not supported | not supported |
| `image_columns` / `image_columns_info` | supported | not supported |
| Embedding `model_modality: multimodal` | supported | not supported |
| Chat `model_modality: VLM` | supported | not supported |
| `batch` | supported | not supported |
| Inference profile | supported | not supported |

---

## Documentation issues to know about

- JSON templates in the docs are **not literal JSON**: they contain `/* */` comments, `a | b` alternatives, missing quotes/commas (`"EUCLIDEAN | "DOTPRODUCT"`, after `apply_heuristics`), and trailing commas. Build the JSON yourself from this topic.
- Filter style is `PRE-FILTERING` / `POST-FILTERING` (hyphen), not the underscore form shown.
- The documented chat model example is retired on Bedrock (see above).
- `image_column` appears in the procedure signature while limitations say `image_columns`.
- `FILE-CONTENT-BASED` collections appear in `ListCollections` but are not listed as a supported creation type (an existing one on the test system was created outside this SQL interface; the creation path is unconfirmed).
- Undocumented procedures exist in `TD_SYSAI` (`RenameCollection`, `GenerateEmbeddings`, `CreateBM25Model`, `GrantCollectionAccess`, `RevokeCollectionAccess`, ...). Do not call them; use the documented ones above.

---

## End-to-end example

```sql
-- 1. Create
CALL TD_SYSAI.CreateCollection('support_kb', 'CONTENT-BASED', 'demo_user', 'Support policies',
  '{"object_names": ["demo_user.support_docs"], "key_columns": ["doc_id"], "metadata_columns": ["category"], "data_columns": ["doc_text"]}',
  '{"train_params": {"search_algorithm": "HNSW"},
    "embedding_model": {"model_provider": "aws", "model_id": "amazon.titan-embed-text-v2:0"},
    "chat_model": {"model_provider": "aws", "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0"}}', 0);

-- 2. Ready?
CALL TD_SYSAI.CheckCollectionStatus('support_kb');

-- 3a. One-call answer
CALL TD_SYSAI.Ask('support_kb', 'How long do I have to return an item?', NULL, NULL, 0);

-- 3b. Or retrieve, then answer from the retrieved rows
CALL TD_SYSAI.SimilaritySearch('support_kb', 'When can I call support?', NULL,
  '{"search_params": {"top_k": 3}, "result_table_name": "demo_user.kb_hits"}', 0);
CALL TD_SYSAI.PrepareResponse('support_kb', 'When can I call support?', 'demo_user.kb_hits', NULL, 0);

-- 4. Refresh after the source table changes
CALL TD_SYSAI.UpdateCollection('support_kb', NULL, NULL, NULL, NULL, 1, 0);

-- 5. Clean up
CALL TD_SYSAI.DestroyCollection('support_kb', 0);
```
