# Teradata JSON — Data Type, Functions, and Operators

Teradata Vantage provides a native `JSON` data type with full SQL integration, binary storage formats, JSONPath extraction, shredding, and publishing capabilities. All functions reside in `TD_SYSFNLIB` unless noted.

---

## Quick Reference

### Methods (invoked as `json_expr.Method(...)`)

| Method | Returns | Description |
|--------|---------|-------------|
| `.AsBSON([STRICT\|LAX])` | BLOB | Convert to BSON; STRICT adds MongoDB key restrictions |
| `.AsJSONText()` | CLOB UNICODE | Convert binary JSON to text |
| `.Combine(json2 [,'ARRAY'\|'OBJECT'])` | JSON | Merge two JSON docs into array or object |
| `.ExistValue(JSONPath)` | 1/0/NULL | Test if a path exists |
| `.JSONExtract(JSONPath)` | JSON array | Extract all matches → JSON array; NULL if none |
| `.JSONExtractValue(JSONPath)` | VARCHAR 4K | Extract single scalar; warns on multi-match |
| `.JSONExtractLargeValue(JSONPath)` | CLOB | Same as JSONExtractValue for large results (>32K) |
| `.KEYCOUNT([depth])` | INTEGER | Count keys up to optional depth |
| `.METADATA()` | JSON | Doc stats: size, depth, keycnt, type counts |
| `.StorageSize([format])` | INTEGER | Bytes to store in LATIN_TEXT/UNICODE_TEXT/BSON/UBJSON |

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `ARRAY_TO_JSON(array)` | JSON | Vantage ARRAY → JSON array |
| `BSON_CHECK(bytes [,STRICT\|LAX])` | VARCHAR | Validate BSON: `'OK'` or `'INVALID: reason'` |
| `DataSize(json)` | BIGINT | Data length in bytes |
| `GeoJSONFromGeom(geom [,prec])` | JSON/VARCHAR/CLOB | ST_Geometry → GeoJSON |
| `GeomFromGeoJSON(geojson, srid)` | ST_Geometry | GeoJSON → ST_Geometry |
| `JSON_AGG(col [AS name],...)` | JSON | Aggregate rows → JSON array of objects |
| `JSON_CHECK(string)` | VARCHAR | Validate JSON text: `'OK'` or `'INVALID: reason'` |
| `JSON_COMPOSE(col [AS name],...)` | JSON | Scalar → JSON object; nest with JSON_AGG |
| `JSONGETVALUE(json, path AS type)` | typed | Extract value as specific SQL type; NULL on failure |
| `JSONMETADATA(json)` | JSON | Aggregate min/max/avg stats across rows |
| `NVP2JSON(nvp [,name_del, val_del [,ignore]])` | JSON | Name=value&pair string → JSON object |

### Table Operators

| Operator | Description |
|----------|-------------|
| `JSON_KEYS(ON (...) [USING DEPTH(n)] [USING QUOTES('Y'|'N')])` | List all key paths in a JSON doc |
| `JSON_TABLE(ON (...) USING ROWEXPR(...) COLEXPR(...))` | JSON → relational rows (JSONPath-based) |
| `TD_JSONSHRED(ON (...) USING ROWEXPR(...) COLEXPR(...) RETURNTYPES(...))` | JSON → relational rows (faster, CLOB input, no JSONPath) |
| `JSON_PUBLISH(ON (...) [USING DO_AGGREGATE(...) WRITE_ARRAY(...)])` | SQL rows → JSON doc (any format, >64K capable) |

### Stored Procedure

| Procedure | Description |
|-----------|-------------|
| `SYSLIB.JSON_SHRED_BATCH` | Shred JSON into existing tables (LATIN) |
| `SYSLIB.JSON_SHRED_BATCH_U` | Same, for UNICODE data |

---

## JSON Data Type — DDL

```sql
-- Column definition syntax
col_name JSON [ (maxlength) ] [ INLINE LENGTH integer ]
         [ CHARACTER SET { LATIN | UNICODE } | STORAGE FORMAT { BSON | UBJSON } ]

-- Default max: 16776192 LATIN chars / 8388096 UNICODE chars / 16776192 bytes (binary)
-- CHARACTER SET and STORAGE FORMAT are mutually exclusive

-- Common column definitions
CREATE TABLE my_table (
    id    INTEGER,
    j1    JSON,                              -- LATIN, default max length
    j2    JSON(1000) CHARACTER SET UNICODE,  -- UNICODE, 1000 chars
    j3    JSON(500) STORAGE FORMAT BSON,     -- BSON binary, 500 bytes
    j4    JSON(500) STORAGE FORMAT UBJSON,   -- UBJSON binary, 500 bytes
    j5    JSON(100) INLINE LENGTH 100        -- non-LOB (inline=max), best perf
);
```

### LOB vs non-LOB Storage

- **non-LOB**: `INLINE LENGTH = maxlength` — data always in base row, no LOB overhead, best for UDFs
- **LOB**: `INLINE LENGTH < maxlength` — rows ≤4K stored inline; rows >4K in LOB subtable
- Default threshold: if `maxlength ≤ 64000 bytes` (32000 UNICODE chars), non-LOB; otherwise LOB with 4096-byte inline default

| Data Type | LOB min INLINE LENGTH |
|-----------|----------------------|
| LATIN text | 100 chars |
| UNICODE text | 50 chars |
| BSON / UBJSON | 100 bytes |

---

## Storage Formats

| Format | Insert speed | Retrieval speed | Space | Best for |
|--------|-------------|-----------------|-------|---------|
| Text (LATIN/UNICODE) | Fastest | Slowest | Largest | General use, simplicity |
| BSON | Slowest | Fastest (tied) | Variable | MongoDB exchange, rich type support |
| UBJSON | Middle | Fastest (tied) | Smallest | Numeric-heavy, compact storage |

- BSON and UBJSON store strings in UTF-8; exported as UNICODE text
- **UBJSON cannot be imported or exported directly** — only via SQL text → auto-convert
- Vantage stores numeric types in **little-endian** format for both binary formats (deviation from UBJSON spec)
- `BINARY STORAGE FORMAT` stores arrays at root as objects in BSON (known limitation)

### Migrate text → binary

```sql
-- Determine needed size first
SELECT MAX(j.StorageSize('BSON')) FROM source_table;

-- Create new table and copy
CREATE TABLE new_table (id INTEGER, j JSON(X) STORAGE FORMAT BSON);
INSERT INTO new_table SELECT * FROM source_table;
```

---

## NEW JSON Constructor

```sql
-- From text string
NEW JSON('{"name":"Cameron","age":24}')
NEW JSON('{"name":"Cameron","age":24}', LATIN)
NEW JSON('{"name":"Cameron","age":24}', UNICODE)

-- From binary (BYTE/VARBYTE/BLOB) — must specify format
NEW JSON('160000000268656C6C6F0006000000776F726C640000'xb, BSON)

-- Default (no args) — empty JSON, user's default charset
NEW JSON()
```

---

## Inserting JSON Data

```sql
-- Insert using constructor
INSERT INTO my_table VALUES (1, NEW JSON('{"name":"Cameron","age":24}'));

-- Insert as string literal (implicit cast)
INSERT INTO my_table VALUES (2, '{"name":"Justin","age":30}');

-- Simple shredding: INSERT JSON (text only, single-row, object root)
INSERT INTO my_table JSON '{"id":1,"name":"Cameron"}';

-- INSERT SELECT
INSERT INTO my_table2 SELECT * FROM my_table;

-- UPDATE (whole column only — cannot update individual JSON fields)
UPDATE my_table
SET j = NEW JSON('{"name":"Updated"}')
WHERE j.JSONExtractValue('$.name') = 'Cameron';
```

---

## Extracting JSON Data

### Choose the right method

| Need | Use |
|------|-----|
| Single scalar value | `JSONExtractValue` (VARCHAR 4K) or dot notation |
| Single scalar, large (>32K) | `JSONExtractLargeValue` (CLOB) |
| Multiple values → JSON array | `JSONExtract` |
| Type-safe extraction | `JSONGETVALUE(json, '$.path' AS INTEGER)` |
| Path existence check | `ExistValue('$.path')` → 1/0 |
| All key paths in a doc | `JSON_KEYS` table operator |

### JSONExtractValue — single scalar

```sql
-- Returns VARCHAR 4K (max 32K via JSON_AttributeSize DBS Control)
-- Returns NULL if path not found or JSON is null
-- Returns warning + '*** ERROR MULTI RESULT ***' if multiple matches
SELECT j.JSONExtractValue('$.name') FROM my_table;
SELECT j.JSONExtractValue('$.schools[1].type') FROM my_table;
SELECT j.JSONExtractValue('$..schools[?(@.type == "college")].name') FROM my_table;

-- Cast to use in comparisons or arithmetic
WHERE CAST(j.JSONExtractValue('$.age') AS INTEGER) > 23
```

### JSONExtract — multiple results

```sql
-- Returns JSON array of all matches, or NULL if none
SELECT j.JSONExtract('$..name') FROM my_table;
-- Result: ["Cameron","Lewis"]

SELECT j.JSONExtract('$.[?(@.age > 23)].firstName') FROM my_table;
-- Result: ["Cameron","Alex","David"]
```

### Dot notation (entity reference)

```sql
-- Child operator (.)
SELECT j.name FROM my_table;
SELECT j.address.city FROM my_table;

-- Recursive descent (..) — returns list
SELECT j..name FROM my_table;              -- all 'name' values anywhere in doc

-- Array element
SELECT j.items[0] FROM my_table;          -- first element
SELECT j.items[0].name FROM my_table;     -- field of first element

-- Wildcard — returns list
SELECT j.items[0].* FROM my_table;        -- all fields of first element

-- Named list — returns list
SELECT j[customer,orderID] FROM my_table;

-- Index list — returns list
SELECT j.items[0,1] FROM my_table;

-- Slice [start:end:step] — returns list
SELECT j.items[0:4:2] FROM my_table;      -- every other item, first 4

-- Dot notation in WHERE
WHERE j.JSONExtractValue('$.name') = 'Cameron'
WHERE 'disk' = ANY(j.items..name)          -- ANY/ALL for list results
WHERE 40 < ANY(j.items..amt)
```

> **Ambiguity rule:** `table.col` is interpreted as a column reference first. To force JSON dot notation, fully qualify: `db.table.jsonCol.field`.

### JSONPath operators summary

| Operator | Meaning | Example |
|----------|---------|---------|
| `$` | Root | `$.customer` |
| `@` | Current element | `$.items[(@.length-1)]` |
| `.` | Child | `$.items[0].name` |
| `..` | Recursive descent | `$..name` |
| `*` | Wildcard | `$.items[0].*` |
| `[n]` | Array index (0-based) | `$.items[2]` |
| `[a,b]` | List of indexes | `$.items[0,3]` |
| `[start:end:step]` | Slice | `$.items[0:4:2]` |
| `?(@.field op value)` | Filter | `$.items[?(@.amt<50)]` |
| `(@.LENGTH-1)` | Script expression | `$.items[(@.length-1)]` |

---

## Validation

```sql
-- Validate JSON text (CHAR/VARCHAR/CLOB)
SELECT JSON_CHECK('{"name":"Cameron"}');          -- 'OK'
SELECT JSON_CHECK('{"name":"Cameron"');            -- 'INVALID: ...'

-- Validate BSON binary (BYTE/VARBYTE/BLOB)
SELECT BSON_CHECK('160000000268656C6C6F...'xb);   -- 'OK' or 'INVALID: ...'
SELECT BSON_CHECK('...'xb, 'STRICT');             -- adds MongoDB key restrictions

-- Disable validation for trusted bulk loads (session-level)
SET SESSION JSON IGNORE ERRORS ON;
SET SESSION JSON IGNORE ERRORS OFF;
```

---

## Inspection Methods

```sql
-- Count keys (optional depth limit)
SELECT j.KEYCOUNT() FROM my_table;           -- all keys
SELECT j.KEYCOUNT(1) FROM my_table;          -- top-level keys only

-- Document metadata
SELECT j.METADATA() FROM my_table;
-- Returns: {"size":61,"depth":1,"keycnt":3,"objcnt":1,"arycnt":0,
--           "strcnt":3,"nbrcnt":0,"boolcnt":0,"nullcnt":0,
--           "keylen":{"min":4,"max":11,"avg":8},"strvallen":{...}}

-- Storage size for a given format
SELECT j.StorageSize() FROM my_table;                    -- current format
SELECT j.StorageSize('BSON') FROM my_table;
SELECT j.StorageSize('UBJSON') FROM my_table;
SELECT j.StorageSize('UNICODE_TEXT') FROM my_table;
SELECT j.StorageSize('LATIN_TEXT') FROM my_table;

-- Raw byte size of the JSON value
SELECT TD_SYSFNLIB.DataSize(j) FROM my_table;

-- Aggregate metadata across all rows
SELECT JSONMETADATA(j) FROM my_table;
-- Returns: {"doc_count":4,"size":{"min":...,"max":...,"avg":...},...}
```

---

## Format Conversion

```sql
-- Any format → BSON (as BLOB)
SELECT j.AsBSON() FROM my_table;            -- LAX validation (default)
SELECT j.AsBSON('STRICT') FROM my_table;   -- + MongoDB restrictions

-- Any format → text (as CLOB UNICODE)
SELECT j.AsJSONText() FROM my_table;

-- CAST between formats
SELECT CAST(j AS JSON STORAGE FORMAT BSON) FROM my_table;
SELECT CAST(j AS JSON(100) CHARACTER SET UNICODE) FROM my_table;
SELECT CAST('{"hello":"world"}' AS JSON STORAGE FORMAT BSON);
SELECT CAST(binary_col AS JSON STORAGE FORMAT BSON);  -- BYTE/VARBYTE → BSON

-- Combine two JSON docs
SELECT j1.Combine(j2) FROM my_table;                 -- auto: objects→merge, mixed→array
SELECT j1.Combine(j2, 'ARRAY') FROM my_table;        -- force array result
SELECT j1.Combine(j2, 'OBJECT') FROM my_table;       -- force object (both must be objects)
```

---

## Type-safe Extraction

```sql
-- JSONGETVALUE — returns NULL on conversion failure (safer than CAST + JSONExtractValue)
SELECT JSONGETVALUE(j, '$.age' AS INTEGER) FROM my_table;
SELECT JSONGETVALUE(j, '$.price' AS DECIMAL) FROM my_table;
SELECT JSONGETVALUE(j, '$.name' AS VARCHAR(50)) FROM my_table;
SELECT JSONGETVALUE(j, '$.created' AS DATE) FROM my_table;

-- Supported types: BYTEINT, SMALLINT, INT, BIGINT, FLOAT, DECIMAL, NUMBER,
--   VARCHAR(LATIN/UNICODE), CHAR(LATIN/UNICODE), DATE, TIME, TIMESTAMP,
--   TIME/TIMESTAMP WITH TIME ZONE, all INTERVAL types
```

---

## Key Discovery

```sql
-- List all key paths in all rows (with quotes — safe for dot notation)
SELECT * FROM JSON_KEYS(
    ON (SELECT j FROM my_table)
    USING DEPTH(1)          -- optional: top-level only
    QUOTES('Y')             -- default: "key"."subkey" (safe for SQL)
) AS k;

-- Without quotes — useful for building JSONPath expressions
SELECT * FROM JSON_KEYS(
    ON (SELECT j FROM my_table)
    USING QUOTES('N')
) AS k;

-- Unique keys across all documents (schema discovery)
SELECT DISTINCT JSONKeys FROM JSON_KEYS(
    ON (SELECT j FROM my_table)
    USING QUOTES('N')
) AS k ORDER BY 1;

-- Extract all values using keys as paths
SELECT CAST(JSONKeys AS VARCHAR(50)),
       T.j.JSONExtractValue('$.' || JSONKeys)
FROM my_table T,
     JSON_KEYS(ON (SELECT j FROM my_table WHERE id=1) USING QUOTES('N')) AS k
WHERE T.id = 1;
```

---

## Publishing — SQL to JSON

### SELECT AS JSON (simplest)

```sql
-- Each row → one JSON object; output column named "JSON"
SELECT AS JSON pkey, val FROM my_table;
SELECT AS JSON pkey, val FROM my_table ORDER BY pkey ASC;  -- must sort explicitly
```

### JSON_AGG — aggregate function

```sql
-- All rows → JSON array of objects
SELECT JSON_AGG(empID, company, empName, empAge) FROM emp_table;
-- Result: [{"empID":1,"company":"company1","empName":"Cameron","empAge":24},...]

-- With aliases
SELECT JSON_AGG(empID AS id, empName AS name, empAge AS age) FROM emp_table;

-- With GROUP BY — one array per group
SELECT JSON_AGG(empID AS id, empName AS name) FROM emp_table
GROUP BY company, empAge;

-- RETURNS clause to control output size/charset (default: JSON(32000) UNICODE)
SELECT (JSON_AGG(empID, empName) RETURNS JSON(10000) CHARACTER SET LATIN)
FROM emp_table;
```

### JSON_COMPOSE — scalar function (wraps JSON_AGG)

```sql
-- Flat object from column values (per row)
SELECT JSON_COMPOSE(empID AS id, empName AS name) FROM emp_table;

-- Hierarchical: use JSON_AGG in subquery, nest in JSON_COMPOSE
SELECT JSON_COMPOSE(T.company, T.employees)
FROM (
    SELECT company,
           JSON_AGG(empID AS id, empName AS name, empAge AS age) AS employees
    FROM emp_table
    GROUP BY company
) AS T;
-- Result per company: {"company":"company1","employees":[{"id":1,...},{"id":2,...}]}

-- Multi-level nesting: JSON_COMPOSE → JSON_AGG → JSON_AGG
SELECT JSON_COMPOSE(T.customer, T.JA AS orders)
FROM (
    SELECT O.customer,
           JSON_AGG(O.orderID, O.price, I.JA AS items) AS JA
    FROM order_table O,
         (SELECT orderID, JSON_AGG(itemID AS ID, itemName AS name) AS JA
          FROM item_table GROUP BY orderID) AS I
    WHERE O.orderID = I.orderID
    GROUP BY O.customer
) AS T;
```

### JSON_PUBLISH — table operator (best for large/binary output)

```sql
-- All rows → single JSON array (default: aggregated)
SELECT * FROM JSON_PUBLISH(
    ON (SELECT * FROM emp_table)
) AS j;

-- One JSON doc per row (no aggregation)
SELECT * FROM JSON_PUBLISH(
    ON (SELECT * FROM emp_table)
    USING DO_AGGREGATE('N')
) AS j;

-- Without top-level array wrapper
SELECT * FROM JSON_PUBLISH(
    ON (SELECT * FROM emp_table)
    RETURNS (col1 JSON CHARACTER SET UNICODE)
    USING WRITE_ARRAY('N') DO_AGGREGATE('N')
) AS j;

-- Full parallel aggregation (two-pass for true global aggregate)
SELECT data..record[*] FROM JSON_PUBLISH(
    ON (SELECT data AS record, 1 AS p FROM JSON_PUBLISH(
            ON (SELECT * FROM emp_table)
        ) AS L
    ) PARTITION BY p
) AS G;
```

---

## NVP / Array Conversion

```sql
-- Name-value pair string → JSON object (default delimiters: & and =)
SELECT NVP2JSON('name=will&occupation=engineer&hair=blonde');
-- {"name":"will","occupation":"engineer","hair":"blonde"}

-- Custom delimiters
SELECT NVP2JSON('name->will+occupation->engineer', '+', '->');

-- Strip leading characters from key names
SELECT NVP2JSON('_name=will&!age=24', '&', '=', '!_');
-- {"name":"will","age":"24"}

-- Vantage ARRAY → JSON array
SELECT (ARRAY_TO_JSON(arr_col) RETURNS JSON(100) CHARACTER SET LATIN) FROM t;
SELECT pos, ARRAY_TO_JSON(ARRAY_AGG(age ORDER BY empId, NEW intarr5()))
FROM emp_table GROUP BY pos;
-- Result: {"engineer":[24,34,25,21],...}
```

---

## Geospatial Conversion

```sql
-- ST_Geometry → GeoJSON (text formats only; binary must be cast first)
SELECT (GeoJSONFromGeom(new ST_Geometry('Point(45.12 85.67)'))
        RETURNS JSON(2000) CHARACTER SET LATIN);
-- {"type":"Point","coordinates":[45.12,85.67]}

SELECT (GeoJSONFromGeom(new ST_Geometry('LineString(10 20, 50 80)'))
        RETURNS VARCHAR(2000));

-- GeoJSON → ST_Geometry (second arg = SRID)
SELECT GeomFromGeoJSON('{"type":"Point","coordinates":[100.0,0.0]}', 4326);
-- POINT (100 0)

-- Supported geometry types: Point, MultiPoint, LineString, MultiLineString,
--   Polygon, MultiPolygon, GeometryCollection
-- Precision (decimal places): default 15, specify as second arg to GeoJSONFromGeom
```

---

## Shredding — JSON to Relational

### INSERT JSON (simplest — single object, text only)

```sql
-- Shred JSON root object keys into matching table columns
INSERT INTO my_table JSON '{"id":1,"name":"Cameron","age":24}';

-- Extra JSON keys go to AUTO COLUMN (if defined)
CREATE TABLE my_table (id INTEGER, name VARCHAR(20),
                       overflow JSON AUTO COLUMN);
INSERT INTO my_table JSON '{"id":1,"name":"Cameron","extra":"data"}';
-- overflow: {"extra":"data"}
```

### JSON_TABLE (JSONPath-based, 16MB limit, no CLOB output)

```sql
-- Each JSON object in rowexpr array → one output row
SELECT * FROM JSON_TABLE(
    ON (SELECT id, jsonCol FROM my_table)
    USING ROWEXPR('$.schools[*]')
         COLEXPR('[
             {"jsonpath":"$.name",  "type":"CHAR(20)"},
             {"jsonpath":"$.type",  "type":"VARCHAR(20)"},
             {"jsonpath":"$.name",  "type":"VARCHAR(20)", "fromRoot":true}
         ]')
) AS JT(id, schoolName, schoolType, studentName);

-- Extra pass-through columns
SELECT * FROM JSON_TABLE(
    ON (SELECT id, jsonCol, 'CA' AS state FROM my_table)
    USING ROWEXPR('$.schools[*]')
         COLEXPR('[{"jsonpath":"$.name","type":"CHAR(20)"},
                  {"jsonpath":"$.type","type":"VARCHAR(20)"}]')
) AS JT(id, name, type, State);

-- Ordinal column (row sequence number)
COLEXPR('[{"ordinal":true}, {"jsonpath":"$.name","type":"CHAR(20)"}]')
```

### TD_JSONSHRED (faster, CLOB input up to 2GB, no JSONPath — use simplified dot notation)

```sql
-- Basic shred
SELECT * FROM TD_JSONSHRED(
    ON (SELECT id, j FROM my_table)
    USING
        ROWEXPR('items')                          -- simplified dot, no $ prefix
        COLEXPR('name', 'price')
        RETURNTYPES('VARCHAR(20)', 'DECIMAL(10,2)')
) AS t;

-- Nested arrays: shred inner first, then outer
SELECT * FROM TD_JSONSHRED(
    ON (SELECT * FROM TD_JSONSHRED(
            ON (SELECT id, j FROM my_table)
            USING ROWEXPR('students')
                  COLEXPR('name','schools')
                  RETURNTYPES('VARCHAR(15)','VARCHAR(150)')
        ) AS d1
    )
    USING ROWEXPR('')           -- empty = entire input is the JSON
          COLEXPR('sname','stype')
          RETURNTYPES('VARCHAR(25)','VARCHAR(25)')
) AS d2;

-- NOCASE(1) for case-insensitive matching; TRUNCATE(0) to fail instead of truncate
```

> **Choose between JSON_TABLE and TD_JSONSHRED:**
> - Use **JSON_TABLE** when you need JSONPath expressions, filter predicates, or non-string output types beyond VARCHAR/CLOB
> - Use **TD_JSONSHRED** for large documents (>16MB → CLOB input), faster performance, or nested array extraction via nesting

### JSON_SHRED_BATCH (stored proc — shred into existing tables)

```sql
CALL SYSLIB.JSON_SHRED_BATCH(
    'SELECT id, empJson, site FROM json_table',     -- id col, JSON col, optional pass-throughs
    '[{
        "rowexpr"  : "$.employees.info[*]",
        "colexpr"  : [
            {"col1" : "$.id",               "type" : "INTEGER"},
            {"col2" : "$.employees.company","type" : "VARCHAR(15)", "fromRoot" : true},
            {"col3" : "$.name",             "type" : "VARCHAR(20)"}
        ],
        "queryexpr": [{"site" : "VARCHAR(20)"}],   -- data types for pass-through cols
        "tables"   : [{
            "mydb.emp_table" : {
                "metadata" : { "operation" : "insert" },
                "columns"  : {
                    "empID"   : "col1*100",          -- SQL expression
                    "company" : "col2",
                    "empName" : "col3",
                    "site"    : "site",
                    "hireDate": "CURRENT_DATE",
                    "docID"   : "JSONID",            -- original id column
                    "rowIdx"  : "ROWINDEX"           -- sequential row index
                }
            }
        }]
    }]',
    :result_code
);
-- Use JSON_SHRED_BATCH_U for UNICODE data
-- Operations: "insert" | "update" | "merge" | "delete"
-- keys: [...] — join columns for update/merge; primary index must be in keys for MERGE
```

---

## Restrictions and Gotchas

- JSON columns **cannot** appear in: `ORDER BY`, `GROUP BY`, `PARTITION BY`, `WHERE` (direct), `HAVING`, `QUALIFY`, `IN`, `DISTINCT`, `CUBE`, `GROUPING SETS`, `ROLLUP`
- Use `JSONExtractValue` / dot notation to isolate scalar portions for comparison
- **Cannot update partial JSON** — SET clause must assign entire column value
- No direct string operations on JSON values — cast to VARCHAR/CLOB first
- **LOB JSON columns cannot be part of an index** — non-LOB JSON can appear in a join index (not as primary index)
- `COLLECT STATISTICS COLUMN j.name ON my_table` — stats on extracted portions only
- Default ordering: joins between JSON columns are not supported; use extracted portions
- `CHARACTER SET` and `STORAGE FORMAT` are mutually exclusive in a column definition
- **Binary formats: BSON arrays at root are stored as objects** — nested arrays are fine
- `JSON_CHECK` works on text only; use `BSON_CHECK` for binary validation
- `GeoJSONFromGeom` / `GeomFromGeoJSON` require text format — cast binary JSON first
