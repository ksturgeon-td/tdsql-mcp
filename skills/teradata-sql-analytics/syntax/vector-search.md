# Teradata Vector Search

Functions for computing vector distances and building approximate nearest-neighbor indexes. Used in retrieval-augmented generation (RAG), semantic search, recommendation, and anomaly detection pipelines.

> **Pre-processing tip:** Normalize embeddings to unit length with `TD_VectorNormalize(Approach('UNITVECTOR'))` before computing cosine distances or building an HNSW index. Unit-normalized vectors make cosine distance equivalent to dot product distance and improve index quality. See `data-prep` topic.

---

## TD_VectorDistance

Computes pairwise distances between vectors in a target table and vectors in a reference table. Supports three distance measures, optional TopK filtering, and both individual float columns and `VECTOR`/`Vector32`/`VARBYTE` column types.

```sql
SELECT * FROM TD_VectorDistance(
    ON { db.table | db.view | (query) } AS TargetTable PARTITION BY ANY
    [ ON { db.table | db.view | (query) } AS ReferenceTable DIMENSION ]
    USING
        TargetIDColumn('target_id_col')                                    -- required
        TargetFeatureColumns({ 'col' | col_range }[,...])                  -- required; see column types below
        [ RefIDColumn('ref_id_col') ]                                      -- required when ReferenceTable provided
        [ RefFeatureColumns({ 'col' | col_range }[,...]) ]                 -- required when ReferenceTable provided
        [ DistanceMeasure({ 'Cosine' | 'Euclidean' | 'Manhattan' }[,...]) ]  -- default: all three
        [ TopK(integer_value) ]                                            -- default 1024; -1 = all pairs
        [ UseSIMD('false') ]                                               -- default false; enable for performance
) AS t;
```

**TargetFeatureColumns / RefFeatureColumns accepted types:**
- Individual numeric columns: `BYTEINT`, `SMALLINT`, `INTEGER`, `BIGINT`, `DECIMAL`, `FLOAT`, `REAL`, `DOUBLE PRECISION`
- Single `VECTOR` or `Vector32` UDT column
- Single `VARBYTE` column

> **Column order and type must match** between `TargetFeatureColumns` and `RefFeatureColumns`. Maximum 2018 feature columns when using individual numeric columns.

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `Target_ID` | BIGINT | Identifier from `TargetIDColumn` |
| `Reference_ID` | BIGINT | Identifier from `RefIDColumn` |
| `DistanceType` | VARCHAR | Distance measure: `cosine`, `euclidean`, or `manhattan` |
| `Distance` | DOUBLE PRECISION | Distance between the target and reference vectors |

**Distance measure guide:**

| Measure | Range | Interpretation | Best for |
|---------|-------|----------------|----------|
| `Cosine` | [0, 2] | 0 = identical direction, 1 = orthogonal, 2 = opposite | Embeddings (direction matters, not magnitude); normalize first |
| `Euclidean` | [0, ∞) | Straight-line distance in feature space | Spatial data, clusters |
| `Manhattan` | [0, ∞) | Sum of absolute differences per dimension | Sparse features |

---

### Usage patterns

**Semantic search — find top K most similar documents to a query vector:**

```sql
-- query_embedding is a single-row table with the query vector
SELECT * FROM TD_VectorDistance(
    ON db.document_embeddings AS TargetTable PARTITION BY ANY
    ON db.query_embedding AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('doc_id')
        TargetFeatureColumns('embedding')    -- VECTOR column
        RefIDColumn('query_id')
        RefFeatureColumns('embedding')
        DistanceMeasure('Cosine')
        TopK(10)
) AS t
ORDER BY Distance ASC;
```

**All-pairs distance within a single table (no ReferenceTable):**

```sql
-- Omitting ReferenceTable computes distances between all pairs in TargetTable
SELECT * FROM TD_VectorDistance(
    ON db.item_embeddings AS TargetTable PARTITION BY ANY
    USING
        TargetIDColumn('item_id')
        TargetFeatureColumns('embedding')
        DistanceMeasure('Cosine')
        TopK(5)    -- return 5 nearest neighbors per item
) AS t;
```

**Multiple distance measures in one call:**

```sql
SELECT * FROM TD_VectorDistance(
    ON db.vectors AS TargetTable PARTITION BY ANY
    ON db.refs AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('id')
        TargetFeatureColumns('feat1', 'feat2', 'feat3')   -- individual float columns
        RefIDColumn('ref_id')
        RefFeatureColumns('feat1', 'feat2', 'feat3')
        DistanceMeasure('Cosine', 'Euclidean')            -- both measures in one pass
        TopK(20)
        UseSIMD('true')
) AS t;
```

> **TopK(-1):** returns all N² pairs — use only on small tables. For large-scale nearest-neighbor search, use `TD_HNSW` instead (approximate, but orders of magnitude faster). See below.

---

## Approximate Nearest Neighbor — HNSW

For large-scale similarity search, `TD_VectorDistance` with `TopK(-1)` computes exact distances but scales as O(N²). The HNSW family provides approximate nearest-neighbor search that scales to millions of vectors.

| Function | Role |
|----------|------|
| `TD_HNSW` | Build the HNSW graph index from input vectors; supports incremental Update and Delete |
| `TD_HNSWPredict` | Search the index — returns approximate top-K nearest neighbors for query vectors |
| `TD_HNSWSummary` | Inspect a built index — layer counts, node counts, graph statistics |

---

### TD_HNSW — Build Index

Constructs a Hierarchical Navigable Small World graph from input vectors. The graph is stored in the `OUT TABLE` as packed binary rows (`TD_HNSW_Nodes`). The primary output is a single status message row.

> **Always use `OUT TABLE`** — the primary output is only a status message. The graph itself is in the OUT TABLE.

```sql
-- Build (training operation)
SELECT * FROM TD_HNSW(
    ON { db.table | db.view | (query) } AS InputTable  -- no PARTITION BY, or PARTITION BY ANY [ORDER BY col]
    OUT [ PERMANENT | VOLATILE ] TABLE ModelTable(db.hnsw_model)  -- required; stores the graph
    USING
        IdColumn('id_col')                             -- required; unique row identifier
        VectorColumn('embedding_col')                  -- required; VECTOR, Vector32, VARBYTE, or BYTE column
        [ DistanceMeasure('euclidean'|'cosine'|'dotproduct') ]  -- default 'euclidean'; must match TD_HNSWPredict
        [ EfConstruction(32) ]                         -- neighbors searched during build; range [1, 1024]
        [ NumConnPerNode(32) ]                         -- connections added per new node; range [1, 1024]
        [ MaxNumConnPerNode(32) ]                      -- max connections per existing node; range [1, 1024]
        [ NumLayer(n) ]                                -- default computed from NumConnPerNode; range [1, 1024]
        [ EmbeddingSize(n) ]                           -- default computed from input data
        [ ApplyHeuristics('false') ]                   -- default false; true improves graph quality, increases build time
        [ Seed(seed_value) ]                           -- default random; set for reproducible graph
        [ UseSIMD('false') ]                           -- default false; enable for SIMD acceleration
) AS t;
```

**Output (primary):**

| Column | Type | Description |
|--------|------|-------------|
| `message` | VARCHAR(128) | Build status message |

**OUT TABLE schema:**

| Column | Type | Description |
|--------|------|-------------|
| `TD_HNSW_Nodes` | VARBYTE(64000) | Packed graph node data |

**Tuning guide:**

| Parameter | Default | Effect of increasing |
|-----------|---------|----------------------|
| `EfConstruction` | 32 | Better recall at search time; slower build |
| `NumConnPerNode` | 32 | More connections per node; better recall; larger index |
| `MaxNumConnPerNode` | 32 | Controls max fan-out; prevents over-connected nodes |
| `ApplyHeuristics` | false | Improves navigability; increases build time |

---

### TD_HNSW — Update and Delete

Insert new vectors into, or remove vectors from, an existing HNSW graph without rebuilding from scratch.

```sql
-- Update: insert new vectors into an existing graph
SELECT * FROM TD_HNSW(
    ON db.hnsw_model AS InputModelTable              -- existing graph (PARTITION BY ANY or no partition)
    ON { db.new_rows | (query) } AS InputTable DIMENSION  -- rows to insert
    OUT [ PERMANENT | VOLATILE ] TABLE ModelTable(db.hnsw_model_v2)
    USING
        IdColumn('id_col')
        VectorColumn('embedding_col')
        AlterOperation('update')
        [ UseSIMD('false') ]
) AS t;

-- Delete: remove vectors from an existing graph
SELECT * FROM TD_HNSW(
    ON db.hnsw_model AS InputModelTable
    ON { db.rows_to_delete | (query) } AS InputTable DIMENSION
    OUT [ PERMANENT | VOLATILE ] TABLE ModelTable(db.hnsw_model_v2)
    USING
        IdColumn('id_col')
        VectorColumn('embedding_col')
        AlterOperation('delete')
        [ DeleteMethod('reconstruction'|'deletenode') ]  -- default 'reconstruction'
        [ UseSIMD('false') ]
) AS t;
```

**`DeleteMethod` options:**

| Value | Behavior |
|-------|----------|
| `reconstruction` (default) | Graph is rebuilt after deletion — better graph quality |
| `deletenode` | Nodes removed in place, no rebuild — faster, but may degrade search quality |

---

### TD_HNSWPredict

Searches an HNSW graph index to find the approximate top-K nearest neighbors for each query vector. Returns one row per neighbor per query vector.

> **ON clause note:** `ModelTable` is the first ON (the large graph); `InputTable` is `DIMENSION` (the small set of query vectors). This is the reverse of the typical Predict pattern.

```sql
SELECT * FROM TD_HNSWPredict(
    ON db.hnsw_model AS ModelTable             -- graph built by TD_HNSW; PARTITION BY ANY or no partition
    ON { db.table | db.view | (query) } AS InputTable DIMENSION  -- query vectors
    USING
        IdColumn('id_col')                     -- required; unique identifier in InputTable
        VectorColumn('embedding_col')          -- required; VECTOR, Vector32, VARBYTE, or BYTE column
        [ EfSearch(32) ]                       -- default 32; candidates considered during search; range [1, 1024]
        [ TopK(10) ]                           -- default 10; nearest neighbors to return per query; range [1, 1024]
        [ OutputSimilarity('false') ]          -- default false; false = distance column, true = similarity column
        [ OutputNearestVector('false') ]       -- default false; true = include neighbor's vector in output
        [ Accumulate({ 'col' | col_range }[,...]) ]  -- columns to copy from InputTable to output
        [ SingleInputRow('false') ]            -- default false; set true when InputTable has exactly one row
        [ UseSIMD('false') ]                   -- default false; enable for SIMD acceleration
) AS t;
```

> **DistanceMeasure is inherited from the index** — it is not specified at search time. The measure used at build time (TD_HNSW) is encoded in the graph and automatically applied here.

**Output columns** (one row per nearest neighbor per query vector):

| Column | Type | Description |
|--------|------|-------------|
| `id_col` | same as InputTable | Query vector identifier |
| `nearest_neighbor_id` | INTEGER | ID of the nearest neighbor from the index |
| `nearest_neighbor_distance` | REAL | Distance to neighbor — present when `OutputSimilarity('false')` (default) |
| `nearest_neighbor_similarity` | REAL | Similarity to neighbor — present when `OutputSimilarity('true')` |
| `nearest_neighbor_vector` | VECTOR/Vector32/VARBYTE | Neighbor's vector — present when `OutputNearestVector('true')` |
| `accumulate_col(s)` | any | Columns copied from InputTable |

**EfSearch vs recall trade-off:**

| EfSearch | Behavior |
|----------|----------|
| Low (e.g. 16) | Fast search; lower recall — some true nearest neighbors may be missed |
| Default (32) | Balanced |
| High (e.g. 128+) | Slower; higher recall; approaches exact search quality |

> Set `EfSearch >= TopK` — searching fewer candidates than you want to return degrades recall significantly.

**Semantic search example:**

```sql
-- Find top 5 nearest documents for each query vector
SELECT * FROM TD_HNSWPredict(
    ON db.document_index AS ModelTable
    ON db.query_vectors AS InputTable DIMENSION
    USING
        IdColumn('query_id')
        VectorColumn('embedding')
        TopK(5)
        EfSearch(64)
        OutputSimilarity('true')
        Accumulate('query_text')
) AS t
ORDER BY query_id, nearest_neighbor_similarity DESC;
```

---

### TD_HNSWSummary

Inspects a built HNSW index — returns one row per graph node with layer assignments, neighbor connections, and model build metadata. No `USING` arguments; takes only a `ModelTable`.

```sql
SELECT * FROM TD_HNSWSummary(
    ON db.hnsw_model AS ModelTable   -- PARTITION BY ANY or no partition
) AS t;
```

**Output columns** (one row per node in the graph):

| Column | Type | Description |
|--------|------|-------------|
| `amp_id` | INTEGER | AMP on which this node resides |
| `graph_id` | INTEGER | Graph ID for the HNSW graph on this AMP |
| `node_id` | BIGINT | Internal node ID assigned during build |
| `layer_id` | INTEGER | Layer in the HNSW hierarchy (higher = sparser, longer-range connections) |
| `input_row_id` | BIGINT | Original ID from the InputTable used in TD_HNSW build |
| `node_vector` | VECTOR | Embedding vector for this node |
| `num_neighbors` | INTEGER | Number of neighbor connections for this node |
| `neighbor_node_id` | VECTOR | Packed array of neighbor node IDs |
| `model_info` | VARCHAR(64000) | Build metadata (parameters, graph statistics) |

> **Output size:** one row per node across all layers and AMPs — can be very large for big indexes. Use aggregation to summarize:

```sql
-- Graph summary: nodes per layer, avg neighbor count
SELECT layer_id,
       COUNT(*)            AS node_count,
       AVG(num_neighbors)  AS avg_neighbors,
       MAX(num_neighbors)  AS max_neighbors
FROM TD_HNSWSummary(
    ON db.hnsw_model AS ModelTable
) AS t
GROUP BY layer_id
ORDER BY layer_id DESC;

-- Check model build parameters (model_info from any one row)
SELECT TOP 1 model_info
FROM TD_HNSWSummary(ON db.hnsw_model AS ModelTable) AS t;
```

---

## KMeans IVF Pattern — Scalable Approximate Search

For very large vector tables where even HNSW build time is prohibitive, the Inverted File Index (IVF) pattern uses `TD_KMeans` to partition the vector space into clusters, then restricts search to only the nearest clusters at query time.

**Concept:** cluster all vectors into K groups by their embedding centroids. At search time, find the Y nearest cluster centroids to the query vector, then run exact similarity search only within those clusters — a small fraction of the total dataset.

```sql
-- Step 1: cluster all vectors into K groups (run once, save centroids + assignments)
CREATE TABLE db.vector_clusters AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.normalized_embeddings AS InputTable PARTITION BY ANY
        ON (
            SELECT * FROM TD_KMeans(
                ON db.normalized_embeddings AS InputTable
                USING
                    IdColumn('doc_id')
                    TargetColumns('embedding')
                    NumClusters(100)              -- K; tune based on dataset size
                    MaxIterNum(300)
                    DistanceMeasure('cosine')
            ) AS t
        ) AS ModelTable DIMENSION
        USING
            IdColumn('doc_id')
            TargetColumns('embedding')
    ) AS t
) WITH DATA;

-- Step 2: at search time, find the Y nearest cluster centroids to the query vector
-- (run TD_VectorDistance against the centroid table — small, fast)
CREATE VOLATILE TABLE nearest_clusters AS (
    SELECT Reference_ID AS cluster_id
    FROM TD_VectorDistance(
        ON db.query_vector AS TargetTable PARTITION BY ANY
        ON db.cluster_centroids AS ReferenceTable DIMENSION
        USING
            TargetIDColumn('query_id')
            TargetFeatureColumns('embedding')
            RefIDColumn('cluster_id')
            RefFeatureColumns('embedding')
            DistanceMeasure('Cosine')
            TopK(5)                               -- Y nearest clusters to search
    ) AS t
) WITH DATA ON COMMIT PRESERVE ROWS;

-- Step 3: exact similarity search within only the nearest clusters
SELECT * FROM TD_VectorDistance(
    ON (
        SELECT e.*
        FROM db.normalized_embeddings e
        JOIN db.vector_clusters c ON e.doc_id = c.doc_id
        WHERE c.TD_ClusterID IN (SELECT cluster_id FROM nearest_clusters)
    ) AS TargetTable PARTITION BY ANY
    ON db.query_vector AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('doc_id')
        TargetFeatureColumns('embedding')
        RefIDColumn('query_id')
        RefFeatureColumns('embedding')
        DistanceMeasure('Cosine')
        TopK(10)
) AS t
ORDER BY Distance ASC;
```

**When to use IVF vs HNSW:**

| | HNSW | KMeans IVF |
|---|------|------------|
| Build | One-time graph build | Cluster once; centroids reusable |
| Search | Single function call | Two-step (centroid lookup → cluster search) |
| Recall | High (tunable via EfSearch) | Depends on Y clusters searched |
| Best for | Moderate-to-large datasets; online search | Very large datasets; batch search |
| Update | Incremental (TD_HNSW AlterOperation) | Re-cluster periodically |

> **Tip:** increase Y (clusters searched in Step 2) to improve recall at the cost of search time. A good starting point is Y = sqrt(K).
