# Native Object Store (NOS)

NOS lets Vantage read from and write to external object storage (S3, Azure Blob/ADLS Gen2, GCS, and on-premises S3-compatible stores) without moving data into Vantage first. Three mechanisms:

| Mechanism | Use case |
|---|---|
| `CREATE FOREIGN TABLE` | Persistent, schema-defined access to NOS data; queryable like a regular table |
| `READ_NOS` | Ad-hoc exploration — schema discovery, file listing, sampled reads |
| `WRITE_NOS` | Export Vantage data to object storage in Parquet or CSV |

**Supported platforms:** VantageCloud Enterprise, VantageCloud Lake, VantageOnVMware, VantageCore

**Supported object stores:** Amazon S3, Azure Blob Storage, Azure Data Lake Storage Gen2, Google Cloud Storage, and any on-premises S3-compatible store (e.g., Ceph, MinIO)

**Supported formats:** JSON (NOSREAD_RECORD: dot notation for attributes), CSV (structured fields), Parquet (columnar; best performance), Delta Lake (Parquet with Delta log, via MANIFEST + TABLE_FORMAT)

**Compression (read):** gzip, bzip2, deflate, snappy, lzo (auto-detected)

**Compression (write):** GZIP or SNAPPY (Parquet only)

---

## CRITICAL: describe_table Does Not Work for Foreign Tables

`describe_table` queries `DBC.ColumnsV`, which does not cover foreign tables. To inspect a foreign table's columns, use:

```sql
HELP TABLE [database_name.]foreign_table_name;
```

Or use `READ_NOS` with `RETURNTYPE('NOSREAD_SCHEMA')` to discover the schema of files directly.

---

## LOCATION URI Formats

```
-- Long form (all platforms)
/S3/<endpoint>/<bucket>/<prefix>
/AZ/<account>.<endpoint>/<container>/<prefix>
/GS/<endpoint>/<bucket>/<prefix>

-- Simplified form (S3, Azure, GCS)
s3://<bucket>/<prefix>
az://<account>.<endpoint>/<container>/<path>
gs://<bucket>/<prefix>
```

Examples:
```
/S3/s3.amazonaws.com/my-bucket/data/
/AZ/myaccount.blob.core.windows.net/mycontainer/data/
/GS/storage.googleapis.com/my-bucket/data/
```

---

## Authorization

**Authorization object (all platforms):**
```sql
CREATE AUTHORIZATION myauth
  AS DEFINER TRUSTED
  USER 'access_key_id'
  PASSWORD 'secret_key';
```

**Inline JSON credentials (S3, Azure, GCS):**
```json
{"Access_ID":"AKIA...", "Access_Key":"secret...", "Session_Token":"token..."}
```
Session_Token is optional (for temporary STS credentials only).

For AWS IAM role-based access (instance profile or task role), omit the AUTHORIZATION clause entirely.

---

## CREATE FOREIGN TABLE

A foreign table is a persistent, schema-aware virtual table that maps to files in object storage. Queries against it read directly from NOS at query time.

**Required privilege:** `CREATE TABLE` on the target database.

### Syntax

```sql
CREATE [MULTISET] FOREIGN TABLE [database_name.]foreign_table_name
[, FALLBACK]
[, MAP = map_name]
[EXTERNAL SECURITY { INVOKER | DEFINER } { TRUSTED | UNTRUSTED } authorization_object]
[( column_definitions )]          -- omit for auto-detection
USING (
  LOCATION         ('/connector/endpoint/bucket/prefix')
  [SCANPCT         ('scan_percent')]
  [PATHPATTERN     ('$var1/$var2/...')]
  [MANIFEST        ({ 'TRUE' | 'FALSE' })]
  [TABLE_FORMAT    ('DELTA')]
  [ROWFORMAT       ('{"field_delimiter":"fd","record_delimiter":"\n"}')]
  [STOREDAS        ({ 'JSON' | 'CSV' | 'PARQUET' })]
  [SNAPSHOT_LOCATION ('/connector/endpoint/bucket/manifest_path')]
  [HEADER          ({ 'TRUE' | 'FALSE' })]
  [STRIP_EXTERIOR_SPACES ({ 'TRUE' | 'FALSE' })]
  [STRIP_ENCLOSING_CHAR  ('char')]
)
[NO PRIMARY INDEX]
[PARTITION BY ( COLUMN [, col_name datatype [, ...]] )];
```

### USING Clause Parameters

| Parameter | Description |
|---|---|
| `LOCATION` | Required. URI of the object storage prefix. |
| `SCANPCT` | Percentage of objects to scan (0–100). Use for sampling large datasets. |
| `PATHPATTERN` | Filter expression using `$variable` path components; enables partition pruning. |
| `MANIFEST` | `'TRUE'` — read only objects listed in a manifest file at LOCATION; `'FALSE'` (default) — scan all objects at LOCATION. |
| `TABLE_FORMAT` | `'DELTA'` for Delta Lake tables (requires `MANIFEST('TRUE')`). |
| `ROWFORMAT` | CSV only. Specifies field and record delimiters: `'{"field_delimiter":"X","record_delimiter":"\n"}'`. Default delimiter is comma. |
| `STOREDAS` | File format: `'JSON'`, `'CSV'`, or `'PARQUET'`. Auto-detected if omitted. |
| `SNAPSHOT_LOCATION` | Path where NOS caches a manifest of scanned objects for performance. Deleted when the foreign table is dropped. |
| `HEADER` | CSV only. `'TRUE'` — first row contains column names (used for schema inference). |
| `STRIP_EXTERIOR_SPACES` | `'TRUE'` — remove leading and trailing spaces from field values. |
| `STRIP_ENCLOSING_CHAR` | Character used to enclose field values (e.g., `'"'` for double-quotes). Strip the enclosing character from values. |
| `PARTITION BY` | Maps path variables to virtual or actual columns. Required when path has no `$variable` components. |

### File Format Notes

**JSON:** Attributes accessed via dot notation on the auto-detected `payload` column (type `JSON`). Values are VARCHAR by default — cast to appropriate types in a view.

**CSV:**
- Columns auto-detected from first row if `HEADER('TRUE')`.
- All values are VARCHAR — cast to appropriate types.
- Default delimiter is comma; use `ROWFORMAT` for other delimiters.

**Parquet:** Best performance. Column types are mapped from Parquet to Teradata types automatically.

### Parquet Type Mapping (Parquet → Teradata)

| Parquet Type | Teradata Type |
|---|---|
| BOOLEAN | BYTEINT |
| INT32 | INTEGER |
| INT64 | BIGINT |
| INT96 | TIMESTAMP(6) |
| FLOAT | FLOAT |
| DOUBLE | FLOAT |
| FIXED_LEN_BYTE_ARRAY | BYTE(n) |
| BYTE_ARRAY (UTF-8) | VARCHAR(65535) UNICODE |
| BYTE_ARRAY (other) | VARBYTE(65535) |
| DECIMAL(p,s) | DECIMAL(p,s) or FLOAT |
| DATE | DATE |
| TIME (ms/µs) | TIME(3) / TIME(6) |
| TIMESTAMP (ms/µs) | TIMESTAMP(3) / TIMESTAMP(6) |
| LIST | (not supported — omit or CAST) |
| MAP | (not supported — omit or CAST) |

### Auto-Column Detection

If you omit the column list, NOS samples files to infer column names and types. Vantage adds a `Location` column of type `VARCHAR(2048) UNICODE` that contains the file path for each row.

```sql
-- Auto-detect columns from Parquet
CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
  EXTERNAL SECURITY DEFINER TRUSTED myauth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;
```

### Explicit Column Definition

Define columns explicitly to control types and avoid auto-detection overhead. Include `Location` as the first column.

```sql
CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
  EXTERNAL SECURITY DEFINER TRUSTED myauth
  (
    Location     VARCHAR(2048) CHARACTER SET UNICODE CASESPECIFIC,
    order_id     INTEGER,
    customer_id  INTEGER,
    order_date   DATE FORMAT 'YYYY-MM-DD',
    amount       DECIMAL(18,2)
  )
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;
```

### TRYCAST for Bad Numeric Values

NOS maps Parquet numeric types to Teradata numeric types by default. If a column contains unexpected string values (e.g., `"N/A"`), use TRYCAST to avoid conversion errors — returns NULL on failure instead of aborting the query:

```sql
SELECT TRYCAST(net_revenue AS DECIMAL(18,2)) AS net_revenue
FROM mydb.orders_ft;
```

---

## CREATE FOREIGN TABLE Examples

### JSON — Auto-Discovery

```sql
CREATE MULTISET FOREIGN TABLE mydb.river_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/river-data/')
    STOREDAS ('JSON')
  )
NO PRIMARY INDEX;

-- Access payload attributes via dot notation
SELECT payload.SiteNo, payload.GageHeight, payload.Flow
FROM mydb.river_ft;
```

### CSV — Auto-Discovery

```sql
CREATE MULTISET FOREIGN TABLE mydb.sales_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/sales/')
    STOREDAS ('CSV')
    HEADER ('TRUE')
  )
NO PRIMARY INDEX;
```

### Parquet — Auto-Discovery

```sql
CREATE MULTISET FOREIGN TABLE mydb.events_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/events/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;
```

### Delta Lake

```sql
CREATE MULTISET FOREIGN TABLE mydb.delta_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/delta-table/')
    MANIFEST ('TRUE')
    TABLE_FORMAT ('DELTA')
  )
NO PRIMARY INDEX;
```

### PATHPATTERN — Partition Pruning

Use `$variable` components to enable partition filtering. NOS generates the `PATHPATTERN` automatically when your path contains `$variable` names.

```sql
CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders/')
    PATHPATTERN ('$year/$month/$day')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX
PARTITION BY (COLUMN, year INTEGER, month INTEGER, day INTEGER);

-- Query with partition pruning — only files under 2024/01/ are read
SELECT * FROM mydb.orders_ft
WHERE year = 2024 AND month = 1;
```

**Variable vs non-variable paths:**
- Path contains `$variable` names → PATHPATTERN is auto-generated by NOS; Vantage creates virtual columns from the variables.
- Path has no `$variable` names → must specify `PARTITION BY` explicitly if you want any path-based filtering.

### Latin Character Set

```sql
CREATE MULTISET FOREIGN TABLE mydb.latin_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  (
    Location  VARCHAR(2048) CHARACTER SET LATIN CASESPECIFIC,
    col1      VARCHAR(256)  CHARACTER SET LATIN NOT CASESPECIFIC,
    col2      INTEGER
  )
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/latin-data/')
    STOREDAS ('CSV')
    HEADER ('TRUE')
  )
NO PRIMARY INDEX;
```

### Copy Foreign Table Definition (WITH NO DATA)

```sql
CREATE MULTISET FOREIGN TABLE mydb.orders_ft_copy
  LIKE mydb.orders_ft
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders-copy/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;
```

### Copy Data Directly to Permanent Table (WITH DATA)

```sql
CREATE MULTISET TABLE mydb.orders_perm
AS (
  SELECT * FROM mydb.orders_ft
) WITH DATA
PRIMARY INDEX (order_id);
```

### Explicit Parquet Schema

```sql
CREATE MULTISET FOREIGN TABLE mydb.readings_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  (
    Location     VARCHAR(2048) CHARACTER SET UNICODE CASESPECIFIC,
    site_id      INTEGER,
    reading_dt   TIMESTAMP(6),
    temperature  FLOAT,
    humidity     DECIMAL(5,2),
    sensor_id    VARCHAR(64) CHARACTER SET UNICODE
  )
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/readings/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;
```

---

## Foreign Table Usage Details

### SHOW TABLE

```sql
-- Default output
SHOW TABLE mydb.orders_ft;

-- XML output (full DDL)
SHOW TABLE mydb.orders_ft IN XML;
```

### Non-Default CSV Delimiters

**TSV (tab-separated):** NOS auto-detects tab-separated files with `.tsv` extension. For explicit control:

```sql
-- Pipe-delimited
USING (
  LOCATION ('/S3/...')
  STOREDAS ('CSV')
  ROWFORMAT ('{"field_delimiter":"|","record_delimiter":"\n"}')
)
```

### STRIP Options Behavior

| STRIP_EXTERIOR_SPACES | STRIP_ENCLOSING_CHAR | Field `  "hello"  ` → result |
|---|---|---|
| FALSE | (none) | `  "hello"  ` |
| TRUE | (none) | `"hello"` |
| FALSE | `"` | `  hello  ` |
| TRUE | `"` | `hello` |

Strip operations are applied in order: exterior spaces first, then enclosing character.

### PARTITION BY — Virtual vs Actual Columns

PARTITION BY determines whether partition values appear in the data:

- **Actual column:** value is stored in the file AND in the path → column appears in SELECT results with real data values
- **Virtual column:** value is in the path only, not in the file itself → column appears in SELECT results derived from path parsing

The `INCLUDE_ORDERING` parameter on `WRITE_NOS` controls whether data is written with the partition column included. When reading back:
- If written with `INCLUDE_ORDERING('TRUE')` → use actual column in PARTITION BY
- If written with `INCLUDE_ORDERING('FALSE')` → use virtual column in PARTITION BY

### SNAPSHOT_LOCATION

Caches a manifest of the files at LOCATION to avoid repeated object listing:

```sql
-- Create with SNAPSHOT_LOCATION
CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders/')
    STOREDAS ('PARQUET')
    SNAPSHOT_LOCATION ('/S3/s3.amazonaws.com/my-bucket/snapshots/orders_snap.json')
  )
NO PRIMARY INDEX;

-- Add SNAPSHOT_LOCATION to an existing foreign table
ALTER TABLE mydb.orders_ft
  USING (
    SNAPSHOT_LOCATION ('/S3/s3.amazonaws.com/my-bucket/snapshots/orders_snap.json')
  );
```

The snapshot manifest is deleted automatically when the foreign table is dropped. Delete and recreate the foreign table to refresh the snapshot.

---

## Import Workflow

Standard pattern to land NOS data into a permanent Teradata table:

```sql
-- Step 1: Create foreign table
CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
  EXTERNAL SECURITY DEFINER TRUSTED aws_auth
  USING (
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/orders/')
    STOREDAS ('PARQUET')
  )
NO PRIMARY INDEX;

-- Step 2: Create a typed view (cast JSON/CSV values to proper types)
REPLACE VIEW mydb.v_orders AS
SELECT
  CAST(payload.order_id   AS INTEGER)          AS order_id,
  CAST(payload.customer   AS VARCHAR(100))     AS customer,
  CAST(payload.order_date AS DATE FORMAT 'YYYY-MM-DD') AS order_date,
  CAST(payload.amount     AS DECIMAL(18,2))    AS amount
FROM mydb.orders_ft;

-- Step 3: Load into permanent table
CREATE MULTISET TABLE mydb.orders_perm
AS (SELECT * FROM mydb.v_orders)
WITH DATA
PRIMARY INDEX (order_id);

-- Or insert into existing table
INSERT INTO mydb.orders_perm
SELECT * FROM mydb.v_orders;
```

---

## READ_NOS

READ_NOS is a table operator for ad-hoc NOS access without defining a foreign table. Use it to:
- List files at a location (`NOSREAD_KEYS`)
- Discover schema (`NOSREAD_SCHEMA`, `NOSREAD_PARQUET_SCHEMA`)
- Query data directly (`NOSREAD_RECORD`, the default)
- Sample a percentage of records (`SAMPLE_PERC`)

### Calling Forms — Both Are Valid

READ_NOS can be called in two equivalent forms:

**Explicit form (use this when writing new SQL):**
```sql
SELECT * FROM READ_NOS (
  USING
    LOCATION ('...')
    AUTHORIZATION (auth_object)
    RETURNTYPE ('NOSREAD_KEYS')
) AS d;
```

**Implicit shorthand (you may encounter this in existing SQL — do not rewrite it):**
```sql
SELECT * FROM (
  LOCATION='...'
  AUTHORIZATION=auth_object
  RETURNTYPE='NOSREAD_KEYS'
) AS d;
```

Both forms are syntactically valid and produce identical results. Agents should generate the explicit `READ_NOS(USING(...))` form. If you see the implicit shorthand in user-provided SQL, recognize it as valid and do not "fix" it.

### READ_NOS Syntax (Explicit Form)

```sql
SELECT [column_list | *]
FROM READ_NOS (
  [ON { [database_name.]table_name | (subquery) }]
  USING
    LOCATION         ('/connector/endpoint/bucket/prefix')
    [AUTHORIZATION   ( { [DatabaseName.]AuthObjectName |
                         '{"Access_ID":"id","Access_Key":"key"}' } )]
    [RETURNTYPE      ({ 'NOSREAD_RECORD' | 'NOSREAD_KEYS' | 'NOSREAD_SCHEMA' | 'NOSREAD_PARQUET_SCHEMA' })]
    [SAMPLE_PERC     ('percent')]
    [STOREDAS        ({ 'JSON' | 'CSV' | 'PARQUET' })]
    [MANIFEST        ({ 'TRUE' | 'FALSE' })]
    [TABLE_FORMAT    ('DELTA')]
    [ROWFORMAT       ('{"field_delimiter":"fd","record_delimiter":"\n"}')]
    [HEADER          ({ 'TRUE' | 'FALSE' })]
    [SCANPCT         ('scan_percent')]
) AS alias [(column_aliases)];
```

### RETURNTYPE Values

| RETURNTYPE | Returns |
|---|---|
| `NOSREAD_RECORD` | One row per record; payload as JSON or structured columns |
| `NOSREAD_KEYS` | One row per file; columns: `Location` (path), `ObjectLength` (bytes) |
| `NOSREAD_SCHEMA` | Inferred schema from files; columns: `Name`, `DataType`, `Description` |
| `NOSREAD_PARQUET_SCHEMA` | Parquet file schema in raw Parquet notation |

### Examples

**List files at a location:**
```sql
SELECT Location, ObjectLength
FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/data/')
    AUTHORIZATION (aws_auth)
    RETURNTYPE ('NOSREAD_KEYS')
) AS d
ORDER BY Location;
```

**Query JSON records:**
```sql
SELECT payload.SiteNo, CAST(payload.GageHeight AS FLOAT) AS gage_height
FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/river-data/')
    AUTHORIZATION (aws_auth)
    STOREDAS ('JSON')
    RETURNTYPE ('NOSREAD_RECORD')
) AS d
WHERE CAST(payload.GageHeight AS FLOAT) > 5.0;
```

**Discover schema (JSON/CSV):**
```sql
SELECT Name, DataType, Description
FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/data/')
    AUTHORIZATION (aws_auth)
    RETURNTYPE ('NOSREAD_SCHEMA')
) AS d;
```

**Discover Parquet schema:**
```sql
SELECT *
FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/parquet-data/')
    AUTHORIZATION (aws_auth)
    STOREDAS ('PARQUET')
    RETURNTYPE ('NOSREAD_PARQUET_SCHEMA')
) AS d;
```

**Query CSV:**
```sql
SELECT *
FROM READ_NOS (
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/sales/')
    AUTHORIZATION (aws_auth)
    STOREDAS ('CSV')
    HEADER ('TRUE')
    RETURNTYPE ('NOSREAD_RECORD')
) AS d
SAMPLE 100;
```

**Inline GCS credentials:**
```sql
SELECT payload.col1, payload.col2
FROM READ_NOS (
  USING
    LOCATION ('/GS/storage.googleapis.com/my-bucket/data/')
    AUTHORIZATION ('{"Access_ID":"client@project.iam.gserviceaccount.com",
                    "Access_Key":"-----BEGIN RSA PRIVATE KEY-----\n..."}')
    STOREDAS ('JSON')
) AS d;
```

---

## WRITE_NOS

WRITE_NOS exports data from a Vantage table or subquery to external object storage.

**Required privilege:** `EXECUTE FUNCTION` on `TD_SYSFNLIB.WRITE_NOS`.

**Important:** WRITE_NOS does NOT overwrite existing data objects. If a file with the same path already exists, WRITE_NOS stops, returns an error, and does not create a manifest even if `MANIFESTFILE` was specified. Any partially written files must be removed manually before retrying.

### Syntax

```sql
SELECT [NodeId, AmpId, Sequence, ObjectName, ObjectSize, RecordCount | *]
FROM WRITE_NOS (
  ON { [database_name.]table_name | (subquery) }
     [ PARTITION BY col [,...] ORDER BY col [,...]
     | HASH BY col [,...] LOCAL ORDER BY col [,...]
     | LOCAL ORDER BY col [,...] ]
  USING
    LOCATION         ('/connector/endpoint/bucket/prefix')
    [AUTHORIZATION   ( { [DatabaseName.]AuthObjectName |
                         '{"Access_ID":"id","Access_Key":"key","Session_Token":"tok"}' } )]
    STOREDAS         ({ 'PARQUET' | 'CSV' })
    [NAMING          ({ 'DISCRETE' | 'RANGE' })]
    [HEADER          ({ 'TRUE' | 'FALSE' })]
    [ROWFORMAT       ('{"field_delimiter":"fd","record_delimiter":"\n"}')]
    [MANIFESTFILE    ('/connector/endpoint/bucket/path/manifest.json')]
    [MANIFESTONLY    ('TRUE')]
    [OVERWRITE       ({ 'TRUE' | 'FALSE' })]
    [INCLUDE_ORDERING ({ 'TRUE' | 'FALSE' })]
    [INCLUDE_HASHBY  ({ 'TRUE' | 'FALSE' })]
    [MAXOBJECTSIZE   ('n')]
    [COMPRESSION     ({ 'GZIP' | 'SNAPPY' })]
) AS alias;
```

### USING Clause Parameters

| Parameter | Description |
|---|---|
| `LOCATION` | Required. URI where files will be written. |
| `AUTHORIZATION` | Auth object name or inline JSON credentials. |
| `STOREDAS` | Required. Output format: `'PARQUET'` or `'CSV'`. |
| `NAMING` | `'DISCRETE'` — object names include exact partition values. `'RANGE'` — object names include min and max partition values. |
| `HEADER` | CSV only. `'TRUE'` writes column names as first row. |
| `ROWFORMAT` | CSV only. Field and record delimiters. |
| `MANIFESTFILE` | Full path where manifest file is written listing all output objects. |
| `MANIFESTONLY` | `'TRUE'` — write only a manifest, no data. Used for recovery from failed writes. Must be combined with `MANIFESTFILE`. |
| `OVERWRITE` | Controls whether an existing manifest file is overwritten. Applies only to the manifest, never to data objects. |
| `INCLUDE_ORDERING` | `'TRUE'` — partition column values are written into the data objects (becomes actual column in foreign table). `'FALSE'` — partition column values appear in path names only (becomes virtual column in foreign table). |
| `INCLUDE_HASHBY` | Same semantics as INCLUDE_ORDERING but for HASH BY columns. |
| `MAXOBJECTSIZE` | Maximum output file size in MB (4–16). Default: `DefaultRowGroupSize` in DBS Control. |
| `COMPRESSION` | Parquet only. `'GZIP'` or `'SNAPPY'`. Compression occurs within Parquet row groups; file extension remains `.parquet`. |

### Distribution Clauses

| Clause | Behavior |
|---|---|
| `PARTITION BY col ORDER BY col` | One file per partition per AMP. Column names in PARTITION BY must match ORDER BY. |
| `HASH BY col LOCAL ORDER BY col` | One file per AMP. Column names in HASH BY must match LOCAL ORDER BY. |
| `LOCAL ORDER BY col` | Orders data on each AMP before writing. Use instead of PARTITION BY when partition columns have few distinct values (to avoid data skew). |

Maximum 10 columns for any of the above. ORDER BY and LOCAL ORDER BY column restrictions: types limited to BYTEINT, SMALLINT, INTEGER, BIGINT, DATE, VARCHAR (≤128 chars, alphanumeric + `- _ ! * ' ( )` only).

### Return Columns

| Column | Type | Description |
|---|---|---|
| `NodeId` | INTEGER | Database engine node that wrote the object |
| `AmpId` | INTEGER | AMP that wrote the object |
| `Sequence` | BIGINT | Unique sequence to avoid name conflicts |
| `ObjectName` | VARCHAR(1024) | Full object path: `/connector/endpoint/bucket/prefix/[partition/]object_<Node>_<AMP>_<Seq>.parquet` |
| `ObjectSize` | BIGINT | Object size in bytes |
| `RecordCount` | BIGINT | Number of records in the object |

### Examples

**Write with partitioning:**
```sql
SELECT NodeId, AmpId, Sequence, ObjectName, ObjectSize, RecordCount
FROM WRITE_NOS (
  ON (SELECT * FROM mydb.river_flow)
  PARTITION BY SiteNo ORDER BY SiteNo
  USING
    AUTHORIZATION (aws_auth)
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/river-flow/')
    STOREDAS ('PARQUET')
    NAMING ('DISCRETE')
    MANIFESTFILE ('/S3/s3.amazonaws.com/my-bucket/river-flow/manifest.json')
    INCLUDE_ORDERING ('TRUE')
    MAXOBJECTSIZE ('16')
    COMPRESSION ('SNAPPY')
) AS d
ORDER BY AmpId;
```

**Generate destination path name in subquery:**
```sql
SELECT ObjectName FROM WRITE_NOS (
  ON (SELECT c1, c2, c3, c4,
             CONCAT('year=', SUBSTR(c4, 1, 4)) AS YearPath
      FROM mydb.mytable)
  PARTITION BY c1, c3, YearPath ORDER BY c1, c3, YearPath
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/output/')
    AUTHORIZATION (aws_auth)
    NAMING ('DISCRETE')
    INCLUDE_ORDERING ('FALSE')
    STOREDAS ('PARQUET')
) AS d;
-- Object paths will include: /year=1999/, /year=2010/, etc.
```

**Recovery — create manifest from existing files after a failed write:**
```sql
SELECT * FROM WRITE_NOS (
  ON (
    SELECT Location, ObjectLength
    FROM READ_NOS (
      USING
        LOCATION ('/S3/s3.amazonaws.com/my-bucket/output/')
        AUTHORIZATION (aws_auth)
        RETURNTYPE ('NOSREAD_KEYS')
    ) AS d1
  )
  USING
    MANIFESTFILE ('/S3/s3.amazonaws.com/my-bucket/output/manifest.json')
    MANIFESTONLY ('TRUE')
    OVERWRITE ('TRUE')
) AS d;
```

### WRITE_NOS Type Limitations

Not all Teradata column types can be written to Parquet or CSV. Support varies by Vantage version. Unsupported types (e.g., PERIOD, some INTERVAL types) will cause errors. Check Teradata documentation for your version's type support matrix. For unsupported types, CAST to a supported type (e.g., VARCHAR) in the subquery before passing to WRITE_NOS.

---

## Best Practices

- **Reduce scan volume:** Specify a more specific `LOCATION` path, or use `PATHPATTERN` variables in the SQL statement so Vantage can prune which files it reads.

- **Encapsulate path filtering in views:** Have the DBA create a view over the foreign table that captures path filtering with appropriate CAST expressions. Expose the view to end users instead of the raw foreign table. This ensures consistent predicate push-down and type safety.

- **Cast JSON/CSV values for aggregation:** JSON attribute values and CSV fields are VARCHAR by default. Casting to narrower types (INTEGER, DECIMAL, DATE, etc.) before GROUP BY or ORDER BY improves performance significantly.

- **Collect statistics on join columns:** When joining a foreign table to a relational table or another foreign table on a payload attribute, collect statistics on that attribute to enable the optimizer to choose an efficient join strategy.

- **Cast to narrow types to reduce spool:** When NOS data is spooled (e.g., for joins or aggregations), smaller types produce smaller spool. Cast early — in the foreign table view or in the query — rather than working with wide VARCHAR columns throughout.
