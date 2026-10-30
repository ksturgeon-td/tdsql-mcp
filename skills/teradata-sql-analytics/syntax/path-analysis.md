# Teradata Path and Pattern Analysis Functions

Functions for analyzing sequences of events, user journeys, session boundaries,
and multi-touch attribution across time-ordered data.

---

## Attribution — Multi-Touch Attribution Analysis

Assigns weighted credit for conversion events to preceding events within a time/row window. Commonly used for web analytics (e.g., attributing a purchase to prior page views or ad impressions).

```sql
SELECT * FROM ATTRIBUTION(
    ON { db.table | db.view | (query) } [ AS InputTable1 ]
        PARTITION BY user_id_col
        ORDER BY time_col
    [ ON { db.table | db.view | (query) } [ AS InputTable2 ]   -- up to 5 input tables total
        PARTITION BY user_id_col
        ORDER BY time_col ]
    ON conversion_event_table  AS ConversionEventTable DIMENSION   -- required
    [ ON excluding_event_table AS ExcludedEventTable  DIMENSION ]  -- optional
    [ ON optional_event_table  AS OptionalEventTable  DIMENSION ]  -- optional
    ON model1_table            AS FirstModelTable     DIMENSION    -- required
    [ ON model2_table          AS SecondModelTable    DIMENSION ]  -- optional
    USING
        EventColumn('event_col')              -- required; column containing event names/IDs
        TimeColumn('time_col')                -- required; column containing event timestamps
        WindowSize('rows:10')                 -- required; window before conversion event:
                                              --   'rows:K'            — up to K preceding rows
                                              --   'seconds:K'         — up to K seconds before
                                              --   'rows:K&seconds:K2' — both; stricter applies
) ORDER BY user_id_col, time_col;
```

**Dimension table schemas:**

```sql
-- ConversionEventTable: target events that trigger attribution
CREATE TABLE conversion_events (conversion_event VARCHAR);

-- ExcludedEventTable: events excluded from receiving attribution credit
CREATE TABLE excluded_events (excluding_event VARCHAR);

-- OptionalEventTable: fallback events (credited only if no regular event available)
CREATE TABLE optional_events (optional_event VARCHAR);

-- FirstModelTable / SecondModelTable: model type and distribution
CREATE TABLE model_table (
    id     INTEGER,   -- row number starting at 0
    model  VARCHAR    -- row 0: model type; rows 1+: distribution spec
);
```

**Model types (row 0 of model table):**

| Model Type | Row 1+ Format | Description |
|------------|--------------|-------------|
| `SIMPLE` | `MODEL:PARAMETERS` | One distribution for all events |
| `EVENT_REGULAR` | `EVENT:WEIGHT:MODEL:PARAMETERS` | Per-event weights; weights must sum to 1.0 |
| `EVENT_OPTIONAL` | `EVENT:WEIGHT:MODEL:PARAMETERS` | Per-optional-event weights; weights must sum to 1.0 |
| `SEGMENT_ROWS` | `Ki:WEIGHT:MODEL:PARAMETERS` | Different model per row segment; Ki values must sum to K in `rows:K` |
| `SEGMENT_SECONDS` | `Ki:WEIGHT:MODEL:PARAMETERS` | Different model per time segment; Ki values must sum to K in `seconds:K` |

**Distribution models (MODEL field in row 1+):**

| MODEL | PARAMETERS | Description |
|-------|-----------|-------------|
| `LAST_CLICK` | `NA` | Full credit to most recent attributable event |
| `FIRST_CLICK` | `NA` | Full credit to first attributable event |
| `UNIFORM` | `NA` | Credit distributed equally across attributable events |
| `EXPONENTIAL` | `alpha,type` | Exponential decay; alpha ∈ (0,1); type = `ROW`, `SECOND`, `MINUTE`, `HOUR`, `DAY`, `MONTH`, `YEAR` |
| `WEIGHTED` | weight list | Explicit weights per event; extra events get 0; extra weights are renormalized |

**Valid FirstModelTable / SecondModelTable combinations:**

| FirstModelTable | SecondModelTable |
|----------------|-----------------|
| `SIMPLE` | not allowed |
| `EVENT_REGULAR` | (none) or `EVENT_OPTIONAL` |
| `SEGMENT_ROWS` | (none) or `SEGMENT_SECONDS` (requires `rows:K&seconds:K2`) |
| `SEGMENT_SECONDS` | not allowed |

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | INTEGER/VARCHAR | User/entity identifier |
| `event` | VARCHAR | Event that received attribution credit |
| `time_stamp` | TIMESTAMP | Event timestamp |
| `attribution` | DOUBLE | Fraction of conversion credit attributed to this event |
| `time_to_conversion` | INTEGER | Elapsed time between this event and the conversion event |

**Example — EVENT_REGULAR model (email + impression):**

```sql
-- model_table contents:
-- id=0: EVENT_REGULAR
-- id=1: email:0.19:LAST_CLICK:NA
-- id=2: impression:0.81:UNIFORM:NA

SELECT * FROM ATTRIBUTION(
    ON clickstream AS InputTable1
        PARTITION BY user_id ORDER BY event_time
    ON conv_events   AS ConversionEventTable DIMENSION
    ON model_table   AS FirstModelTable      DIMENSION
    USING
        EventColumn('event_type')
        TimeColumn('event_time')
        WindowSize('rows:10')
) ORDER BY user_id, event_time;
```

> **Notes:**
> - Up to 5 input event tables; all must PARTITION BY the same user/entity column and ORDER BY time
> - MODEL values are case-sensitive
> - Excluded events cannot be conversion events; optional events cannot be conversion or excluded events

---

## Sessionize — Session Boundary Detection for Time-Ordered Events

Assigns a unique session identifier to each event in a time-ordered sequence, grouping events that occur within a defined inactivity timeout. Works for any time-ordered event stream partitioned by any entity — users, devices, customers, machines, etc.

```sql
SELECT * FROM SESSIONIZE(
    ON { db.table | db.view | (query) }         -- no AS alias
        PARTITION BY entity_col [, ...]          -- any grouping identifier: user, device, customer, etc.
        ORDER BY time_col [, ...]
    USING
        TimeColumn('time_col')                   -- required; must also appear in ORDER BY
                                                 -- types: TIME, TIMESTAMP, DATE, INTEGER, BIGINT, SMALLINT
                                                 -- integer types are treated as milliseconds
        TimeOut(1800.0)                          -- required; DOUBLE PRECISION seconds of inactivity
                                                 -- that define a session boundary
        [ ClickLag(0.2) ]                        -- optional; DOUBLE PRECISION minimum seconds between
                                                 -- events for the entity to be considered legitimate
                                                 -- (not a bot/automated process); sessions where any
                                                 -- gap is below this threshold are excluded
                                                 -- default: no sessions excluded
        [ EmitNull('false') ]                    -- optional; default 'false'
                                                 -- 'true' — include rows where time_col is NULL
                                                 --          (sessionid and clicklag will be NULL)
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| *(all input columns)* | same as input | Every input column is copied to output |
| `sessionid` | INTEGER/BIGINT | Session identifier assigned by the function |
| `clicklag` | BYTEINT | `1` if the gap between this event and the previous exceeded `ClickLag`; `0` otherwise |

> **Notes:**
> - No `AS` alias on the `ON` clause
> - `TimeColumn` value must also appear in `ORDER BY`
> - No input column may be named `sessionid` or `clicklag` — these are reserved output column names
> - `PARTITION BY` defines the entity whose events are sessionized — commonly user ID, but equally applicable to device ID, customer ID, machine ID, or any other grouping
> - `ClickLag` is useful for filtering automated or bot-like activity; any entity whose inter-event gaps fall below the threshold is excluded entirely
> - `TimeOut` defines inactivity — if two consecutive events for the same entity are more than `TimeOut` seconds apart, the second event starts a new session
> - Output is commonly used as input to `nPath` for path pattern analysis

**Example — sessionize IoT device events:**

```sql
SELECT * FROM SESSIONIZE(
    ON device_events
        PARTITION BY device_id
        ORDER BY event_time
    USING
        TimeColumn('event_time')
        TimeOut(300.0)        -- new session after 5 minutes of inactivity
        ClickLag(0.05)        -- ignore devices firing faster than 50ms (anomalous)
) AS t;
```

---

## nPath — Flexible Sequence Pattern Matching

Scans time-ordered rows within a partition, finds sequences matching a user-defined pattern, and returns one output row per match. Applicable to any ordered event stream: web clickstreams, IoT sensor data, healthcare records, financial transactions, supply chain events, and more.

> **Transformer/LLM pipeline note:** nPath's `ACCUMULATE` output produces ordered event sequences (e.g., products added to a cart, pages visited, steps in a process). These sequences can be passed directly to tokenizers and transformer models for next-item prediction, anomaly detection, or sequence classification — enabling in-database feature engineering for LLM pipelines.

```sql
SELECT * FROM nPath(
    ON { db.table | db.view | (query) }
        PARTITION BY partition_col
        ORDER BY order_col [ ASC | DESC ] [,...]
    [ ON { db.table | db.view | (query) }          -- optional additional tables
        [ PARTITION BY partition_col | DIMENSION ]  -- DIMENSION not allowed if table has CLOB columns
        ORDER BY order_col [ ASC | DESC ] ]
    USING
        Mode({ OVERLAPPING | NONOVERLAPPING })      -- required
        Pattern('pattern')                          -- required; see Pattern Operators below
        Symbols(                                    -- required; define symbol predicates
            col_expr = predicate AS SYMBOL [,...]
        )
        [ Filter(                                   -- optional; applied after pattern match
            FIRST(col_expr OF ANY(SYM,...)) operator FIRST(col_expr OF ANY(SYM,...))
        ) ]
        Result(                                     -- required; define output columns
            aggregate_fn(col_expr OF symbol_list) AS alias [,...]
        )
) AS t;
```

**Mode:**

| Mode | Description |
|------|-------------|
| `OVERLAPPING` | Find every occurrence of the pattern; a row can match multiple symbols across overlapping matches |
| `NONOVERLAPPING` | After a match, next search starts at the row following the last matched row |

**Symbols:**

Each symbol maps a predicate to a short identifier used in `Pattern` and `Result`:

```sql
Symbols(
    pagetype = 'home'                          AS H,    -- exact match
    pagetype <> 'home' AND pagetype <> 'exit'  AS P,    -- compound predicate
    TRUE                                       AS A,    -- matches every row
    price > LAG(price, 1, 0)                   AS UP    -- LAG/LEAD comparison (no OR allowed)
)
```

> - Symbols are case-insensitive (`A` = `a`); one or two uppercase letters recommended for readability
> - NULL rows match no symbol and are ignored
> - For multiple input tables, qualify ambiguous columns: `table.column = value AS SYM`
> - `LAG`/`LEAD` predicates: `current_expr operator LAG(prev_expr, n [, default])` — cannot use `OR` in same symbol definition; if input is a subquery, it must have an alias

**Pattern operators** (in decreasing precedence):

| Operator | Description |
|----------|-------------|
| `A` | Matches exactly one row satisfying symbol A |
| `A?` | Matches 0 or 1 rows satisfying A |
| `A*` | Matches 0 or more rows satisfying A (greedy) |
| `A+` | Matches 1 or more rows satisfying A (greedy) |
| `A.B` | A followed immediately by B (concatenation) |
| `A\|B` | Matches one row satisfying either A or B |
| `^A` | Pattern must start with a row satisfying A |
| `A$` | Pattern must end with a row satisfying A |
| `(X){n}` | Exactly n occurrences of subpattern X |
| `(X){n,}` | At least n occurrences of subpattern X |
| `(X){n,m}` | Between n and m occurrences of subpattern X |

> - nPath uses **greedy** matching — always finds the longest available match
> - Use parentheses to enforce precedence: `A.(B|C)+.D` is clearer than relying on operator order
> - `A.B+` = `A.(B+)` · `A|B*` = `A|(B*)` · `A.B|C` = `(A.B)|C`

**Filter:**

Optional post-match constraints using `FIRST`/`LAST` of a symbol's column values:

```sql
Filter(
    FIRST(clicktime + INTERVAL '10' MINUTE OF ANY(home)) >
    FIRST(clicktime OF ANY(checkout))
)
```

> - Multiple filter expressions are AND-ed together
> - Syntax: `{ FIRST | LAST }(col_expr OF [ANY](symbol[,...])) comparison_op { FIRST | LAST }(...)`
> - Use `Filter` when the constraint spans a variable number of rows (LAG/LEAD cannot handle this)

**Result functions:**

| Function | Description |
|----------|-------------|
| `COUNT(* OF sym_list)` | Total matched rows |
| `COUNT([DISTINCT] col OF sym_list)` | Count (or distinct count) of col values |
| `FIRST(col OF sym_list)` | Value from first matched row |
| `LAST(col OF sym_list)` | Value from last matched row |
| `NTH(col, n OF sym_list)` | Value from nth matched row; negative n counts from end; NULL if n > match count |
| `FIRST_NOTNULL(col OF sym_list)` | First non-null value |
| `LAST_NOTNULL(col OF sym_list)` | Last non-null value |
| `MAX_CHOOSE(qty_col, desc_col OF sym_list)` | `desc_col` from the row with the highest `qty_col` |
| `MIN_CHOOSE(qty_col, desc_col OF sym_list)` | `desc_col` from the row with the lowest `qty_col` |
| `AVG / MAX / MIN / SUM(col OF sym_list)` | Standard aggregates over matched rows |
| `DUPCOUNT(col OF sym_list)` | Duplicate count vs immediately preceding matched row |
| `DUPCOUNTCUM(col OF sym_list)` | Cumulative duplicate count across all preceding matched rows |
| `ACCUMULATE(col OF sym_list [DELIMITER 'x'])` | Concatenated ordered list of values; optionally DISTINCT or CDISTINCT (consecutive distinct) |

> - `symbol_list` is either a single symbol or `ANY(sym1, sym2, ...)` to aggregate across multiple symbols
> - `ACCUMULATE` returns VARCHAR (≤64000 chars LATIN / ≤32000 UNICODE) or CLOB for larger sizes
> - `ACCUMULATE` is the primary way to produce ordered sequences for downstream NLP/transformer pipelines

**Example 1 — web path to checkout (with Filter):**

```sql
SELECT * FROM nPath(
    ON clickstream PARTITION BY userid ORDER BY clicktime
    USING
        Mode(NONOVERLAPPING)
        Pattern('home.clickview*.checkout')
        Symbols(
            pagetype = 'home'                                    AS home,
            pagetype <> 'home' AND pagetype <> 'checkout'        AS clickview,
            pagetype = 'checkout'                                AS checkout
        )
        Filter(
            FIRST(clicktime + INTERVAL '10' MINUTE OF ANY(home)) >
            FIRST(clicktime OF ANY(checkout))
        )
        Result(
            FIRST(userid    OF ANY(home, clickview, checkout))   AS userid,
            FIRST(sessionid OF ANY(home, clickview, checkout))   AS sessionid,
            COUNT(*         OF ANY(home, clickview, checkout))   AS cnt,
            FIRST(clicktime OF ANY(home))                        AS first_home,
            LAST(clicktime  OF ANY(checkout))                    AS last_checkout
        )
) AS t;
```

**Example 2 — product sequence for transformer pipeline:**

```sql
-- Build ordered product sequences from grocery basket events
-- Output can be tokenized and passed to a transformer for next-item prediction
SELECT * FROM nPath(
    ON basket_events PARTITION BY customer_id ORDER BY event_time
    USING
        Mode(NONOVERLAPPING)
        Pattern('A+')
        Symbols(TRUE AS A)
        Result(
            FIRST(customer_id  OF A)                         AS customer_id,
            FIRST(session_id   OF A)                         AS session_id,
            ACCUMULATE(product_name OF A DELIMITER ' ')      AS product_sequence,
            COUNT(*            OF A)                         AS sequence_length
        )
) AS t;
-- product_sequence: "bread milk eggs butter cheese"
-- Ready for tokenization and transformer model input
```

**Example 3 — job transition path (LAG in symbol, greedy matching):**

```sql
SELECT job_path, COUNT(*) AS path_count
FROM nPath(
    ON career_history PARTITION BY employee_id ORDER BY start_date
    USING
        Mode(NONOVERLAPPING)
        Pattern('CEO.ENGR.OTHER*')
        Symbols(
            job_title LIKE '%Software Eng%'     AS ENGR,
            job_title LIKE 'Chief Exec Officer' AS CEO,
            TRUE                                AS OTHER
        )
        Result(
            ACCUMULATE(job_title OF ANY(CEO, ENGR, OTHER)) AS job_path
        )
) AS dt
GROUP BY 1 ORDER BY 2 DESC;
```
