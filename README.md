# tdsql-mcp

An MCP server that turns Teradata Vantage into a full-stack analytics agent platform — giving AI agents not just SQL execution, but a structured, hierarchical knowledge base of Teradata's native function ecosystem.

## What This Is

Most database MCP servers provide query execution. This one goes further: it equips agents with the knowledge they need to use Teradata *correctly and optimally* — not just to run arbitrary SQL, but to reach for the right native distributed function for each step of an analytics workflow.

Teradata Vantage includes hundreds of built-in table operators for ML, statistics, data preparation, text analytics, and vector search. These run distributed across all AMPs in parallel and consistently outperform equivalent hand-written SQL. The challenge for agents is *discovery* — knowing these functions exist, knowing which one to use, and knowing how to combine them into pipelines.

This server solves that with a structured syntax reference library and an agent guidance architecture that directs models toward native functions at every decision point.

---

## Why This Matters

The conventional pattern for AI-assisted analytics looks like this:

```
Agent pulls data → processes in Python / LLM context → returns result
```

This works at small scale but collapses under real-world conditions: the data transfer is expensive, the LLM context fills with raw data instead of insights, results are ephemeral and non-reproducible, and nothing produced is reusable at scale.

The in-database approach enabled by this server inverts that model:

```
Agent orchestrates SQL → analytics execute on the platform → only results returned
```

### Zero Data Movement

Native Teradata table operators execute where the data lives — across all AMPs in parallel. No rows are transferred to a client for processing. Whether the operation is computing summary statistics on a billion-row table, fitting a XGBoost model, or running a vector similarity search, the data stays on the platform. What crosses the wire is the result, not the input.

This isn't just a performance consideration. It eliminates a class of problems: no serialization overhead, no memory pressure on the client, no network bottleneck, no privacy risk from data leaving the platform boundary.

### Token and Context Efficiency

When an agent pulls raw data into its context window to analyze it, it burns tokens on data that a SQL function could process in a single pass. A table of a million rows passed to an LLM for statistical analysis is a context window catastrophe. The same analysis via `TD_UnivariateStatistics` returns a compact result set — a handful of rows — that the agent can reason about directly.

This means the agent's context stays clean: **the LLM reasons about results, not raw data**. Fewer tokens consumed. Longer, more coherent conversations. More headroom for complex multi-step workflows.

### AMP-Parallel Performance and Repeatability

Teradata's native analytics functions are not ordinary SQL — they are massively parallel table operators distributed across the AMP architecture. A `TD_XGBoost` training call, a `TD_KMeans` clustering run, or a `TD_ColumnTransformer` preprocessing pass all execute across every AMP simultaneously. The agent gets the benefit of the platform's full parallel compute without orchestrating any of it.

Repeatability follows naturally from this model. Fit functions persist their learned parameters to named tables. Model training persists model weights. The same `TD_ScaleTransform` applied with the same `ScaleFitTable` produces identical output every time — on training data, on new batches, or on a single incoming row. This is not incidental; it is a structural property of the Fit/Transform and Train/Predict patterns built into the library.

### From Agent Session to Operational Pipeline

The highest-value outcome of this architecture is not ad-hoc analysis — it is the transition from agent-assisted exploration to a production SQL pipeline that runs independently at any scale and concurrency.

The CTE prediction pipeline pattern captures this directly:

```sql
-- This query is a complete operational scoring pipeline.
-- It requires no Python, no client-side processing, no agent at runtime.
-- Any process with database access can call it.
WITH transformed AS (
    SELECT * FROM TD_ColumnTransformer(
        ON db.incoming_data AS InputTable
        ON db.impute_fit    AS ImputeFitTable        DIMENSION
        ON db.encode_fit    AS OneHotEncodingFitTable DIMENSION
        ON db.scale_fit     AS ScaleFitTable          DIMENSION
    ) AS t
)
SELECT * FROM TD_XGBoostPredict(
    ON transformed AS InputTable
    ON db.fraud_model AS ModelTable DIMENSION
    USING IDColumn('txn_id') Accumulate('amount', 'merchant')
) AS dt;
```

An agent builds and validates this pipeline. Once it works, it is promoted to a view, a stored procedure, or a scheduled job. The agent is no longer in the loop at inference time. The pipeline runs in-situ, at the platform's full scale and concurrency, against whatever volume of incoming data the business requires.

This is the progression this server is designed to enable: **exploration → validation → operationalization** — entirely within Teradata, without the data ever leaving the platform.

---

## The Syntax Reference Library

The `get_syntax_help` tool (and the `teradata://syntax/{topic}` resources) expose a comprehensive, agent-optimized reference library covering the full Teradata Vantage analytics stack.

### Coverage

| Domain | Functions / Patterns |
|--------|----------------------|
| **Data Exploration** | TD_ColumnSummary, TD_UnivariateStatistics, TD_Histogram, TD_QQNorm, TD_MovingAverage, TD_Correlation |
| **Data Cleaning** | TD_OutlierFilterFit/Transform, TD_SimpleImputeFit/Transform, TD_GetRowsWithMissingValues, TD_GetRowsWithoutMissingValues, TD_GetFutileColumns, TD_ConvertTo, StringSimilarity |
| **Data Preparation** | TD_ScaleFit/Transform, TD_BinCodeFit/Transform, TD_OneHotEncodingFit/Transform, TD_OrdinalEncodingFit/Transform, TD_TargetEncodingFit/Transform, TD_PolynomialFeaturesFit/Transform, TD_NonLinearCombineFit/Transform, TD_FunctionFit/Transform, TD_RandomProjectionFit/Transform, TD_RowNormalizeFit/Transform, TD_Pivoting, TD_Unpivoting, TD_ColumnTransformer, TD_SMOTE, TD_VectorNormalize, and more |
| **Machine Learning** | TD_XGBoost, TD_DecisionForest, TD_GLM, TD_KMeans, TD_KNN, TD_SVM, TD_OneClassSVM, TD_NaiveBayes — all with Train/Predict pairs |
| **Model Evaluation** | TD_TrainTestSplit, TD_ClassificationEvaluator, TD_RegressionEvaluator, TD_ROC, TD_Silhouette, TD_SHAP |
| **Text Analytics** | TD_NgramSplitter, TD_NaiveBayesTextClassifier, TD_NERExtractor, TD_SentimentExtractor, TD_TextParser, TD_TextMorph, TD_TextTagger, TD_TFIDF, TD_WordEmbeddings |
| **LLM-Powered Text Analytics** | AI_AnalyzeSentiment, AI_AskLLM, AI_DetectLanguage, AI_ExtractKeyPhrases, AI_MaskPII, AI_RecognizeEntities, AI_RecognizePIIEntities, AI_TextClassifier, AI_TextSummarize, AI_TextTranslate |
| **Embeddings & AI Integration** | AI_TextEmbeddings (Azure/AWS/GCP/NIM/LiteLLM REST), ONNXEmbeddings (in-database BYOM), authorization objects, LLM provider config |
| **Vector Search** | VECTOR/Vector32 types, TD_VectorDistance, TD_HNSW/TD_HNSWPredict/TD_HNSWSummary, KMeans IVF pattern |
| **Statistical Testing** | TD_ANOVA, TD_ChiSq, TD_FTest, TD_ZTest |
| **Association & Path Analysis** | TD_Apriori, TD_CFilter, Sessionize, nPath, Attribution |
| **ML Pipeline Patterns** | CTE prediction pipeline, elbow method, train/evaluate/retrain loop, class imbalance workflow, micromodeling |
| **BYOM Model Loading** | PMML, H2O MOJO (open source + DAI), ONNX, Dataiku, DataRobot, MLeap — table schema, loading via BTEQ/Python, ONNX conversion workflow, sparse map tables, DAI license management |
| **BYOM Scoring** | PMMLPredict, H2OPredict, ONNXPredict, DataikuPredict, DataRobotPredict, MLeapPredict; NLP transformers: ONNXSeq2Seq, ONNXClassification |
| **UAF — Time Series** | ARIMA (estimate/validate/forecast), linear/multivariate regression, Holt-Winters, MAMEAN, SimpleExp, ACF/PACF, differencing, seasonal normalization, smoothing |
| **UAF — Diagnostics** | Dickey-Fuller, Durbin-Watson, Breusch-Godfrey, Breusch-Pagan-Godfrey, White's General, Goldfeld-Quandt, Portman, FITMETRICS, SELECTION_CRITERIA, cumulative periodogram, significant periodicities |
| **UAF — DSP & Spatial** | DFFT/DFFT2, IDFFT/IDFFT2, convolution, DWT/IDWT (1D/2D), power spectrum, line spectrum, SAX, windowed DFFT, geospatial tracking |
| **UAF — Utilities** | Series/matrix inspection (TD_SINFO, TD_MINFO), input validation, image↔matrix conversion, in-database charting (TD_PLOT), FIR filter factory, table format conversion |
| **Geospatial** | ST_Geometry, MBR/MBB, WKT/WKB formats, spatial relationships (ST_Within, ST_Contains, ST_Distance, ST_Intersects, etc.), spherical/spheroidal distance, geospatial indexes, AggGeom, GeometryToRows, PolygonSplit, GeoSequence tracking, tessellation, MGRS conversion, SYSSPATIAL metadata |
| **Core SQL** | SELECT, CTEs, joins, window functions, date/time, aggregation, conditional logic, data types |

### Library Architecture

The library is structured in three layers, matching how agents reason about analytics problems:

```
guidelines.md          ← "What native function covers this operation?"
                          Canonical mapping of 50+ common operations to native functions.
                          Agents consult this first, before writing any SQL.

index.md               ← Topic directory + Workflows section
                          Maps common use cases (fraud detection, clustering, NLP, etc.)
                          to ordered topic sequences. Agents load topics in the right order.

<topic>.md files       ← Detailed syntax for each function or domain
                          Full argument reference, output schemas, usage patterns,
                          and complete pipeline examples.
```

An agent tackling a fraud detection problem can navigate this hierarchy:
1. Load `guidelines` — confirms `TD_XGBoost`, `TD_ScaleFit`, `TD_SMOTE`, `TD_ClassificationEvaluator` are the right tools
2. Load `index` — finds the Classification workflow topic sequence
3. Load `data-prep`, `ml-functions`, `model-evaluation` in order
4. Assemble the pipeline using the CTE prediction pipeline pattern from `ml-patterns`

### Pipeline Patterns

A key capability is the **CTE prediction pipeline** — a fully encapsulated scoring pipeline that applies all preprocessing and scoring in a single SQL query, with no intermediate tables:

```sql
WITH transformed AS (
    SELECT id, feat1, feat2, feat3_encoded, feat4_scaled, target_col
    FROM TD_ColumnTransformer(
        ON db.new_data AS InputTable
        ON db.impute_fit     AS ImputeFitTable        DIMENSION
        ON db.encoding_fit   AS OneHotEncodingFitTable DIMENSION
        ON db.scale_fit      AS ScaleFitTable          DIMENSION
    ) AS t
)
SELECT * FROM TD_XGBoostPredict(
    ON transformed AS InputTable
    ON db.my_model AS ModelTable DIMENSION
    USING IDColumn('id') Accumulate('target_col')
) AS dt;
```

The saved FitTables and model table are built once at training time and reused indefinitely — enabling reproducible, versioned inference pipelines entirely in-database.

---

## Tools

| Tool | Description |
|------|-------------|
| `get_syntax_help` | **Start here.** Returns syntax reference for a topic. Use `topic="guidelines"` for the native-functions mapping, `topic="index"` to browse all topics. |
| `execute_query` | Run a SELECT query; returns JSON with rows, row count, and truncation flag |
| `execute_statement` | Run DDL/DML (INSERT, UPDATE, CREATE, etc.); disabled in read-only mode |
| `explain_query` | Validate SQL syntax and preview the execution plan via Teradata EXPLAIN |
| `describe_table` | Get column definitions for a table or view |
| `list_tables` | List tables and views in a given database |
| `list_databases` | List all accessible databases/schemas |

## Resources

| URI | Contents |
|-----|----------|
| `teradata://syntax/{topic}` | Same content as `get_syntax_help` — accessible as MCP resources |

---

## Configuration

Connection is specified as a single URI via the `DATABASE_URI` environment variable or `--uri` CLI flag.

### URI format

```
teradata://user:password@host[:port][/database][?param=value&...]
```

| Part | Required | Description |
|------|----------|-------------|
| `user` | Yes | Database username |
| `password` | Yes | Database password (URL-encode special characters, e.g. `@` → `%40`) |
| `host` | Yes | Teradata server hostname or IP |
| `port` | No | Database port (default: 1025) |
| `/database` | No | Default database/schema |
| `?...` | No | Any additional `teradatasql` connection parameters |

### Environment variables

| Env var | CLI flag | Description |
|---------|----------|-------------|
| `DATABASE_URI` | `--uri` | Teradata connection URI |
| `TD_READ_ONLY` | `--read-only` | Set to `true` to disable write operations |
| — | `--transport` | `stdio` (default) or `streamable-http` |
| — | `--host` | Bind host for HTTP transport (default: `127.0.0.1`) |
| — | `--port` | Bind port for HTTP transport (default: `8000`) |

### Common extra parameters

Any [teradatasql connection parameter](https://github.com/Teradata/python-driver#connection-parameters)
can be appended as a query-string argument:

| Parameter | Example | Description |
|-----------|---------|-------------|
| `logmech` | `logmech=LDAP` | Auth method: TD2 (default), LDAP, KRB5, BROWSER, JWT, etc. |
| `encryptdata` | `encryptdata=true` | Encrypt data in transit |
| `sslmode` | `sslmode=VERIFY-FULL` | TLS: DISABLE, ALLOW, PREFER, REQUIRE, VERIFY-CA, VERIFY-FULL |
| `logon_timeout` | `logon_timeout=30` | Logon timeout in seconds |
| `connect_timeout` | `connect_timeout=5000` | TCP connection timeout in milliseconds |
| `reconnect_count` | `reconnect_count=5` | Max session reconnect attempts |
| `tmode` | `tmode=ANSI` | Transaction mode: DEFAULT, ANSI, TERA |
| `cop` | `cop=false` | Disable COP discovery (useful for single-node dev systems) |

### Multiple parameters example

```
# LDAP + encryption + full TLS + timeouts
teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&encryptdata=true&sslmode=VERIFY-FULL&logon_timeout=30&connect_timeout=5000

# Default auth + encryption + custom port + session reconnect
teradata://myuser:mypassword@myhost:1025/mydb?encryptdata=true&reconnect_count=5&reconnect_interval=10

# LDAP + ANSI transaction mode + no COP discovery (single-node dev system)
teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&tmode=ANSI&cop=false
```

See [.env.example](.env.example) for more annotated examples.

---

## Two Ways to Use This

| | MCP Server | Skill |
|---|---|---|
| **What it provides** | Live SQL execution + syntax library | Syntax library only |
| **Teradata credentials required** | Yes | No |
| **Works with** | Claude Desktop, Claude Code | Claude Code |
| **Use when** | You have Teradata access and want to run queries | You already have a DB connection, or just want SQL writing assistance |

You can use either one independently, or both together. When combined, the MCP server handles query execution and the skill loads the native function guidelines at the start of every session.

---

## Setup

### Option 1 — MCP Server (SQL execution + syntax library)

#### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb"
      }
    }
  }
}
```

With extra parameters (LDAP auth + encryption):

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb?logmech=LDAP&encryptdata=true"
      }
    }
  }
}
```

Using a local virtual environment (instead of `uvx`):

```json
{
  "mcpServers": {
    "teradata": {
      "command": "/path/to/tdsql-mcp/.venv/bin/tdsql-mcp",
      "args": [],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb"
      }
    }
  }
}
```

Replace `/path/to/tdsql-mcp` with the absolute path to where you cloned the repo. The `.venv/bin/tdsql-mcp` script is created automatically when you run `pip install -e .` inside the venv.

For read-only mode, add `--read-only` to `args`:

```json
"args": ["--read-only"]
```

#### Claude Code

Add the MCP server to your Claude Code settings (`.claude/settings.json` or via `claude mcp add`):

```bash
claude mcp add teradata -- uvx tdsql-mcp
# then set DATABASE_URI in your environment or .env file
```

Or add it manually to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uvx",
      "args": ["tdsql-mcp"],
      "env": {
        "DATABASE_URI": "teradata://myuser:mypassword@myhost/mydb"
      }
    }
  }
}
```

#### Running directly

```bash
# Install
pip install tdsql-mcp

# Via environment variable
DATABASE_URI="teradata://me:secret@myhost/mydb" tdsql-mcp

# Via CLI flag
tdsql-mcp --uri "teradata://me:secret@myhost/mydb"

# With extra connection parameters
tdsql-mcp --uri "teradata://me:secret@myhost/mydb?logmech=LDAP&sslmode=VERIFY-FULL"

# Read-only
tdsql-mcp --uri "teradata://me:secret@myhost/mydb" --read-only
```

#### Streamable-HTTP transport

The server also supports `streamable-http` transport for remote or multi-client use — e.g. a shared server on a team machine, or an agent framework that connects over HTTP rather than spawning a subprocess.

```bash
# Start in HTTP mode (binds to localhost:8000 by default)
tdsql-mcp --uri "teradata://me:secret@myhost/mydb" --transport streamable-http

# Custom host/port
tdsql-mcp --uri "teradata://me:secret@myhost/mydb" --transport streamable-http --host 0.0.0.0 --port 8080
```

The MCP endpoint is available at `http://<host>:<port>/mcp`.

To connect Claude Code to an HTTP transport server, add it to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "teradata": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

> **Note:** The HTTP transport has no built-in authentication. For anything beyond localhost, put the server behind a reverse proxy with appropriate access controls.

#### Install from source (with virtual environment)

```bash
# Clone the repository
git clone https://github.com/ksturgeon-td/tdsql-mcp.git
cd tdsql-mcp

# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install in editable mode
# Code and syntax file changes take effect immediately — no reinstall needed
pip install -e .

# Set up your connection credentials
cp .env.example .env
# Edit .env and set DATABASE_URI to your Teradata connection string

# Run the server
tdsql-mcp
```

To deactivate the virtual environment when you're done:

```bash
deactivate
```

To install from the pinned `requirements.txt` snapshot instead of resolving fresh dependencies:

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

---

### Option 2 — Skill (syntax library, no credentials required)

The skill loads the native function guidelines and full syntax topic index into any Claude Code session. No Teradata connection or credentials are required — it's a read-only knowledge library.

**What you get:** Type `/teradata-sql-analytics` at the start of a session to load the guidelines and topic index. Claude will check for an available database connection tool and confirm whether it can execute queries or work in SQL-writing-only mode.

#### Installation — Claude Code (CLI / IDE extensions)

```bash
# Clone the repository
git clone https://github.com/ksturgeon-td/tdsql-mcp.git
cd tdsql-mcp

# Install the skill — copies SKILL.md and creates a symlink to the syntax library
mkdir -p ~/.claude/teradata-sql-analytics
cp skills/teradata-sql-analytics/SKILL.md ~/.claude/teradata-sql-analytics/SKILL.md
ln -sf "$(pwd)/src/tdsql_mcp/syntax" ~/.claude/teradata-sql-analytics/syntax
```

To get syntax library updates later, just `git pull` in the repo directory — the symlink means your installed skill picks up changes automatically.

If you prefer a standalone copy with no repo dependency:

```bash
# Copy all files directly (no ongoing repo dependency)
cp -rL tdsql-mcp/skills/teradata-sql-analytics ~/.claude/teradata-sql-analytics
```

#### Installation — Claude Desktop & Claude.ai (ZIP upload)

Skills can be uploaded as a ZIP file via **Customize > Skills** in both the Claude Desktop app and Claude.ai web app.

> **Prerequisite:** Code execution must be enabled in **Settings > Capabilities** before Skills become accessible.

Build the ZIP:

```bash
# Clone the repository
git clone https://github.com/ksturgeon-td/tdsql-mcp.git
cd tdsql-mcp

# Build a self-contained skill folder (follows symlinks so syntax files are included)
rsync -rL skills/teradata-sql-analytics/ /tmp/teradata-sql-analytics/

# Zip it
cd /tmp && zip -r teradata-sql-analytics.zip teradata-sql-analytics/
```

Then upload:
1. Open Claude Desktop or Claude.ai
2. Go to **Customize > Skills**
3. Click **+** → **Upload a skill**
4. Select `teradata-sql-analytics.zip`

The skill will appear in your Skills list and can be toggled on/off. Uploaded skills are private to your account. Enterprise admins can provision skills organization-wide via **Organization settings > Skills**.

#### Usage

**Claude Code** — type this at the start of any session:

```
/teradata-sql-analytics
```

**Claude Desktop / Claude.ai** — enable the skill via **Customize > Skills**, then start a new conversation. The skill activates automatically.

Claude will load the native function guidelines and topic index, check for a database connection, and confirm it's ready. From there, ask it to write, review, or optimize any Teradata SQL — or load a specific syntax topic with `get_syntax_help(topic="...")` if you also have the MCP server running.

#### Recommended project/session instructions

For best results, add the following as project instructions (Claude Desktop: **Project > Instructions**, Claude.ai: **Project > Custom instructions**) or paste at the start of a session. This tells the agent to use the skill proactively rather than waiting to be asked:

```
You are working with a Teradata Vantage database.

IMPORTANT: Always prefer native Teradata table operators over hand-written SQL equivalents.
Teradata Vantage has built-in distributed functions for analytics, ML, data preparation,
text processing, and vector search. These run across all AMPs in parallel and outperform
equivalent hand-written SQL. Do NOT write manual SQL for operations like scaling, encoding,
binning, statistics, clustering, classification, or similarity search when a native function exists.

Before writing any analytics, transformation, or ML SQL:
  (1) use the /teradata-sql-analytics skill (syntax/guidelines.md) to see the canonical
      mapping of common operations to native Teradata functions,
  (2) use the /teradata-sql-analytics skill (syntax/index.md) to discover all available topics,
  (3) load the relevant topic(s) for exact syntax.

Use available MCP tools to explore the schema.
```

---

## Extending the Syntax Library

The library is designed to grow. To add a new topic:

1. Create `src/tdsql_mcp/syntax/<topic>.md`
2. Add an entry to `index.md`
3. Add relevant mappings to `guidelines.md`

No code changes needed — the tool auto-discovers `.md` files at call time. Topics planned for future addition include `time-series-patterns.md`, `json-functions.md`, and `object-store.md` (READ_NOS, foreign tables, Iceberg/Delta query patterns).

---

## Result format

`execute_query` returns:

```json
{
  "rows": [{"col1": "val", "col2": 42}, ...],
  "row_count": 100,
  "truncated": true
}
```

`truncated: true` means more rows were available beyond the `max_rows` limit. Increase `max_rows` or add a `TOP N` / `WHERE` clause to your query.

## Notes

- The server establishes a persistent connection on startup and automatically reconnects on failure.
- `execute_query` defaults to `max_rows=100` to keep token usage manageable. Maximum is 10,000.
- Use `explain_query` before running unfamiliar queries — Teradata's EXPLAIN validates syntax and shows the execution plan without actually running the query.
- All logging goes to stderr; stdout is reserved for the MCP JSON-RPC protocol.
