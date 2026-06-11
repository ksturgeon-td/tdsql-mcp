# Teradata Open Table Format (OTF) — Iceberg and Delta Lake

Teradata Vantage supports reading and writing Apache Iceberg and Delta Lake tables stored in external object stores (S3, ADLS Gen2, GCS) via external catalog providers. OTF tables are accessed using a three-tier dot notation: `datalake.database.table`.

**Supported formats:** Apache Iceberg Version 2, Delta Lake Version 3.0

**Supported platforms:** VantageCloud Enterprise, VantageCloud Lake, VantageOnVMware

---

## CRITICAL: HELP Commands Are First-Class OTF Statements

`HELP DATALAKE`, `HELP DATABASE`, and `HELP TABLE` are the primary OTF metadata discovery commands — they query the external catalog directly. Do NOT rewrite them as `SELECT` queries. Pass them through `execute_query` as-is:

```sql
-- List databases in a datalake
HELP DATALAKE my_datalake;

-- List tables in a datalake database
HELP DATABASE my_datalake.my_db;

-- Describe columns of a datalake table (use this, NOT describe_table)
HELP TABLE my_datalake.my_db.my_table;
```

`describe_table` queries `DBC.ColumnsV`, which does not cover OTF tables. Always use `HELP TABLE` for OTF table schema inspection.

---

## Three-Tier Dot Notation

All OTF table references use three tiers. Database references use two tiers.

```sql
-- Table reference
<datalake_name>.<otf_database_name>.<otf_table_name>

-- Database reference
<datalake_name>.<otf_database_name>
```

Examples:
```sql
SELECT COUNT(*) FROM my_lake.sales_db.orders;
INSERT INTO my_lake.sales_db.orders VALUES (...);
DROP TABLE my_lake.sales_db.orders PURGE ALL;
HELP DATABASE my_lake.sales_db;
HELP TABLE my_lake.sales_db.orders;
```

---

## Supported Catalogs and Object Storage

### Iceberg — Catalog Support (Read/Write)

| Catalog | `catalog_type` | AWS | Azure | GCP |
|---|---|---|---|---|
| Apache Hive | `hive` | Yes/Yes | Yes/Yes | Yes/Yes |
| AWS Glue | `glue` | Yes/Yes | N/A | N/A |
| Databricks Unity | `unity` | Yes/Yes | Yes/Yes | Yes/Yes |
| REST (Polaris/Gravitino) | `rest` | Yes/Yes | Yes/Yes | No/No |
| Object Store (direct) | — | Yes/No | Yes/No | Yes/No |

### Delta Lake — Catalog Support (Read/Write)

| Catalog | `catalog_type` | AWS | Azure | GCP |
|---|---|---|---|---|
| AWS Glue | `glue` | Yes/Yes | N/A | N/A |
| Databricks Unity | `unity` | Yes/Yes | Yes/Yes | Yes/Yes |

### Object Storage
- Amazon S3
- Azure Data Lake Storage Gen2 (ADLS Gen2)
- Azure Blob Storage
- Google Cloud Storage

### File Formats
- Iceberg: Parquet (R/W), AVRO (R/W), ORC (read-only)
- Delta Lake: Parquet only

### Supported Auth Models

| CSP | Type |
|---|---|
| AWS | IAM User Credentials, Assume Role, Lake Formation |
| Azure | Azure AD Service Principal, Databricks Unity Service Principal |
| GCP | GCP Service Account, Databricks Unity Service Principal |

---

## CREATE AUTHORIZATION

Two AUTHORIZATION objects are required for each DATALAKE: one for the catalog connection, one for storage access. The same object can be used for both when credentials are shared.

### Simplified Auth (Recommended)

```sql
CREATE AUTHORIZATION user1.my_auth
USER '<access_key_id_or_client_id>'
PASSWORD '<secret_key_or_client_secret>';

-- Grant execute privilege to other users
GRANT EXECUTE ON user1.my_auth TO user2 WITH GRANT OPTION;
```

### AWS Assume Role

```sql
CREATE AUTHORIZATION assume_role_auth
USING
AUTHSERVICETYPE 'ASSUME_ROLE'
ROLENAME '<IAM_role_ARN>'
EXTERNAL_ID '<external_id_from_trust_policy>';
```

### Azure Active Directory Service Principal

```sql
CREATE AUTHORIZATION azure_auth
AS INVOKER TRUSTED
USER '<azure_ad_service_principal_client_id>'
PASSWORD '<azure_ad_service_principal_client_secret>';
```

---

## CREATE DATALAKE

All DATALAKE objects are created in `TD_SERVER_DB`. `TABLE FORMAT` is specified at the end (not inside the `USING` clause).

### Syntax

```sql
CREATE DATALAKE <datalake_name>
    EXTERNAL SECURITY [DEFINER TRUSTED | [INVOKER] TRUSTED] CATALOG <auth_name>,
    EXTERNAL SECURITY [DEFINER TRUSTED | [INVOKER] TRUSTED] STORAGE <auth_name>
USING
    catalog_type ('<type>')               -- Required: hive|glue|unity|rest|fabric
    [catalog_location ('<uri>')]          -- Required: hive (thrift://...), unity (https://...), rest
    [storage_location ('<uri>')]          -- Required: hive, glue; optional: unity on Azure
    [storage_region ('<region>')]         -- Required: glue, hive; e.g. 'us-west-2'
    [unity_catalog_name ('<name>')]       -- Required: unity
    [storage_account_name ('<name>')]     -- Required: unity/hive on Azure
    [tenant_id ('<guid>')]                -- Required: unity/hive on Azure
    [default_cluster_id ('<id>')]         -- Required: unity (needed for Iceberg Write via Spark)
    [catalog_name ('<name>')]             -- Required: REST/Polaris
    [idp_location ('<oauth_endpoint>')]   -- Required: REST catalogs (Gravitino/Polaris)
    [idp_token_scope ('<scope>')]         -- Required: Polaris/Gravitino; e.g. 'PRINCIPAL_ROLE:ALL'
    [project_id ('<id>')]                 -- Required: GCP
    [client_id ('<id>')]                  -- Required: GCP
    [client_email ('<email>')]            -- Required: GCP
    [lakeformation_enabled ('true')]      -- AWS Lake Formation integration
    [<other_custom_clauses>]
TABLE FORMAT iceberg | deltalake;
```

### Example: AWS Glue — Iceberg

```sql
CREATE DATALAKE my_iceberg_lake
EXTERNAL SECURITY CATALOG user1.my_auth,
EXTERNAL SECURITY STORAGE user1.my_auth
USING
    storage_location ('s3://my-bucket/iceberg/')
    storage_region ('us-west-2')
    catalog_type ('glue')
TABLE FORMAT iceberg;
```

### Example: AWS Glue — Delta Lake (AssumeRole)

```sql
CREATE AUTHORIZATION delta_assume_role
USING AUTHSERVICETYPE 'ASSUME_ROLE'
ROLENAME '<IAM_role_ARN>'
EXTERNAL_ID '<external_id>';

CREATE DATALAKE my_delta_lake
EXTERNAL SECURITY CATALOG delta_assume_role,
EXTERNAL SECURITY STORAGE delta_assume_role
USING
    catalog_type ('glue')
    storage_location ('s3://my-bucket/delta/')
    storage_region ('us-west-2')
TABLE FORMAT deltalake;
```

### Example: Hive Catalog (AWS S3)

```sql
CREATE AUTHORIZATION hive_catalog_auth AS INVOKER TRUSTED USER 'key' PASSWORD 'secret';
CREATE AUTHORIZATION s3_storage_auth   AS INVOKER TRUSTED USER 'key' PASSWORD 'secret';

CREATE DATALAKE my_hive_lake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG hive_catalog_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE s3_storage_auth
USING
    catalog_type ('hive')
    catalog_location ('thrift://<hostname>:<port>')
    storage_location ('s3://<bucket>/')
    storage_region ('us-west-2')
TABLE FORMAT iceberg;
```

### Example: Databricks Unity (Azure)

```sql
CREATE AUTHORIZATION azure_unity_auth AS INVOKER TRUSTED
USER '<azure_ad_client_id>' PASSWORD '<azure_ad_client_secret>';

CREATE DATALAKE my_unity_lake
EXTERNAL SECURITY CATALOG azure_unity_auth,
EXTERNAL SECURITY STORAGE azure_unity_auth
USING
    catalog_type ('unity')
    catalog_location ('https://<workspace>.azuredatabricks.net/api/2.1/unity-catalog/iceberg')
    unity_catalog_name ('<catalog_name>')
    storage_account_name ('<adls2_storage_account>')
    tenant_id ('<tenant_guid>')
    default_cluster_id ('<cluster_id>')
TABLE FORMAT iceberg;
```

> **Unity + Iceberg Write:** Requires a running Databricks Spark cluster. OTF issues `MSCK REPAIR TABLE <table> SYNC METADATA` via Spark after Iceberg writes to keep Unity catalog in sync. If the cluster is stopped, OTF will attempt to start it and time out after 5 minutes.

### Example: Databricks Unity (GCP)

```sql
CREATE AUTHORIZATION gcs_catalog_auth USER '<dbx_client_id>' PASSWORD '<dbx_client_secret>';
CREATE AUTHORIZATION gcs_storage_auth USER '<gcp_private_key_id>' PASSWORD '<gcp_private_key>';

CREATE DATALAKE my_gcp_unity_lake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG gcs_catalog_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE gcs_storage_auth
USING
    catalog_type ('unity')
    catalog_location ('https://<workspace>.gcp.databricks.com/api/2.1/unity-catalog/iceberg')
    unity_catalog_name ('<catalog_name>')
    storage_location ('gs://<bucket>')
    project_id ('<gcp_project_id>')
    client_id ('<gcp_service_account_client_id>')
    client_email ('<gcp_service_account_email>')
    default_cluster_id ('<cluster_id>')
TABLE FORMAT iceberg;
```

### Example: Iceberg REST Catalog (Gravitino / Polaris)

```sql
CREATE AUTHORIZATION rest_catalog_auth USER '<oauth_client>' PASSWORD '<oauth_secret>';
CREATE AUTHORIZATION s3_storage_auth   USER '<s3_access_key>' PASSWORD '<s3_secret>';

CREATE DATALAKE my_polaris_lake
EXTERNAL SECURITY CATALOG rest_catalog_auth,
EXTERNAL SECURITY STORAGE s3_storage_auth
USING
    catalog_type ('rest')
    catalog_location ('http://hostname:port/api/catalog/')
    catalog_name ('my_polaris_catalog')         -- Required for Polaris; omit for Gravitino
    idp_location ('http://hostname:port/api/catalog/v1/oauth/tokens')
    idp_token_scope ('PRINCIPAL_ROLE:ALL')
    storage_region ('us-east-1')
    storage_location ('s3://my-polaris-bucket/')
TABLE FORMAT iceberg;
```

### Example: AWS Lake Formation

```sql
CREATE DATALAKE aws_lakeformation
EXTERNAL SECURITY CATALOG aws_assume_role_auth,
EXTERNAL SECURITY STORAGE aws_assume_role_auth
USING
    catalog_type ('glue')
    storage_location ('s3://my-lf-bucket/')
    storage_region ('us-west-2')
    lakeformation_enabled ('true')
    lakeformation_authorized_caller_session_tag ('tdotf')
TABLE FORMAT iceberg;
```

Lake Formation enforces fine-grained RBAC (column-level and row-level security). Authorized columns and row filter predicates are applied automatically at query time.

---

## REPLACE / ALTER / DROP DATALAKE

```sql
-- Replace existing datalake definition (same syntax as CREATE)
REPLACE DATALAKE my_lake
EXTERNAL SECURITY CATALOG user1.my_auth,
EXTERNAL SECURITY STORAGE user1.my_auth
USING
    catalog_type ('glue')
    storage_location ('s3://new-bucket/')
    storage_region ('us-west-2')
TABLE FORMAT iceberg;

-- Alter: update authorization objects
ALTER DATALAKE my_lake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG new_catalog_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE new_storage_auth;

-- Alter: add or modify USING clauses
ALTER DATALAKE my_lake
ADD
    catalog_location ('thrift://new-host:9083')
    storage_region ('us-east-1');

-- Drop (removes reference only — no change to catalog or object storage contents)
DROP DATALAKE my_lake;

-- Comment and Show
COMMENT ON DATALAKE my_lake 'Production Iceberg data lake.';
SHOW DATALAKE my_lake;     -- returns the CREATE DATALAKE DDL
```

Note: `TABLE FORMAT` cannot be changed with `ALTER DATALAKE`.

---

## Data Discovery

### Catalog Views

```sql
-- List all registered datalakes
SELECT * FROM DBC.DatalakeInfoV;
-- Columns: DatalakeName, OTFTableFormat, CatalogType, CatalogLocation,
--          StorageLocation, StorageRegion, UnityCatalogName, StorageAccountName

-- Server-level view (includes auth metadata)
SELECT * FROM DBC.ServerV WHERE TableFormat = 'iceberg';
```

### HELP Commands

Use `execute_query` to run these — they query the external catalog, not DBC views.

```sql
-- List databases in a datalake
HELP DATALAKE [TD_SERVER_DB.]<datalake_name>;
-- Returns: DatabaseName, DatabaseProperties

-- List tables in a datalake database
HELP DATABASE <datalake_name>.<database_name>;
-- Returns: Table/View/Macro Name, Kind, OTF Table Format, TblProperties, ...

-- Describe columns of a datalake table
HELP TABLE <datalake_name>.<database_name>.<table_name>;
-- Returns: Column Name, Type, Nullable, OTF Type (native Iceberg/Delta type), OTF Table Format, ...
```

### Managed OTF Dictionary Views

```sql
SELECT * FROM DBC.ManagedOTFTablesV;              -- Teradata-managed OTF tables
SELECT * FROM DBC.ManagedOTFTablePropertiesV;      -- Properties of managed OTF tables
```

---

## SELECT Queries

OTF tables work in SELECT statements like regular Teradata tables.

```sql
-- Basic SELECT
SELECT COUNT(*) FROM my_lake.sales_db.orders;

-- Projection and predicates
SELECT c1, c2 FROM my_lake.sales_db.orders
WHERE order_date > DATE '2024-01-01' AND status = 'shipped';

-- Join OTF table with a local Teradata (BFS) table
SELECT * FROM my_lake.db1.t1 AS D
JOIN local_db.ref_table r ON r.make = D.make;

-- Join two OTF tables from different datalakes
WITH t1 AS (SELECT * FROM lake1.db1.t1),
     t2 AS (SELECT * FROM lake2.db2.t2)
SELECT TOP 5 * FROM t1, t2;

-- CTAS: create local Teradata table from OTF data
CREATE TABLE local_db.snapshot AS (SELECT * FROM my_lake.db1.t1 AS D) WITH DATA;
```

---

## Time Travel

Query OTF tables at a historical snapshot. Use `TD_SNAPSHOTS()` to find valid snapshot IDs or timestamps.

```sql
-- By snapshot ID (quoted numeric string)
SELECT * FROM my_lake.db1.t1 FOR SNAPSHOT AS OF '6373759902296319074';

-- By timestamp (picks snapshot AT OR BEFORE the given time)
SELECT * FROM my_lake.db1.t1 FOR SNAPSHOT AS OF TIMESTAMP '2024-06-15 00:08:01';

-- By date
SELECT * FROM my_lake.db1.t1 FOR SNAPSHOT AS OF DATE '2024-06-15';
```

Delta Lake: use version number as the snapshot ID (e.g. `'2'` for version 2).

---

## OTF Metadata Functions

Syntax: `[TD_SYSFNLIB.]FUNCTION_NAME( ON ( <datalake>.<db>.<table> ) ) <alias>`

### TD_SNAPSHOTS() — snapshot/version history

```sql
SELECT * FROM TD_SNAPSHOTS(ON (my_lake.db1.t1)) D;
```

Iceberg columns: `snapshotId`, `snapshotTimestamp`, `timestampMSecs`, `manifestList`, `summary`

Delta Lake columns: `snapshotVersion`, `lastCommitTimestamp`, `lastCommitTimestampMSecs`, `metadata`, `logPath`, `summary`

### TD_MANIFESTS() — manifest file info (Iceberg only)

```sql
SELECT * FROM TD_MANIFESTS(ON (my_lake.db1.t1)) D;
-- Returns error 3706 for Delta Lake tables
```

Columns: `snapshotId`, `snapshotTimestamp`, `manifestList`, `manifestFile`, `manifestFileLength`, `datafilecount`, `totalrowcount`

### TD_PARTITIONS() — partition columns

```sql
SELECT * FROM TD_PARTITIONS(ON (my_lake.db1.t1)) D;
-- Returns: id, name
```

### TD_HISTORY() — snapshot ID and timestamp list

```sql
SELECT * FROM TD_HISTORY(ON (my_lake.db1.t1)) D;
-- Returns: id, timestamp
```

---

## OTF Database and Table DDL

### CREATE / DROP DATABASE

```sql
-- Two-tier notation: datalake.database
CREATE DATABASE my_lake.my_db
    DBPROPERTIES ('create_date'='2024-01-01', 'owner'='admin');

-- Drop (database must be empty first)
DROP DATABASE my_lake.my_db;
```

### CREATE TABLE

```sql
CREATE TABLE my_lake.my_db.my_table
    ( c1 VARCHAR(50) NOT NULL,
      c2 INT,
      dt  TIMESTAMP(6),
      country VARCHAR(50) )
PARTITIONED BY (YEAR(dt), country, BUCKET(16, c2))
SORTED BY c1 ASC, c2 DESC
TBLPROPERTIES (
    'write.format.default'='parquet',
    'write.parquet.compression-codec'='snappy');
```

**Partition transforms:** `IDENTITY(col)`, `BUCKET(n, col)`, `TRUNCATE(n, col)`, `YEAR(col)`, `MONTH(col)`, `DAY(col)`, `HOUR(col)`, `NULL(col)`

**Not allowed:** SET/MULTISET/VOLATILE table kinds, MAP, FALLBACK, INDEX, JOURNAL, ON COMMIT, NOT CASESPECIFIC (OTF tables are always case-specific)

**VARCHAR tip:** Always specify an explicit length. Default of 32000 wastes storage and slows joins/group-by.

**Delta Lake:** Partition transforms and SORTED BY are not supported.

**Unity (Iceberg/Delta Write):** Single-quoted database names cause Spark parse errors — use unquoted or double-quoted names only.

### CREATE TABLE AS

```sql
-- From OTF table (format must match: Iceberg→Iceberg or Delta→Delta)
CREATE TABLE my_lake.my_db.tab_copy
PARTITIONED BY (id)
AS (SELECT * FROM my_lake.my_db.tab_source AS D) WITH DATA;

-- From local Teradata BFS table
CREATE TABLE my_lake.my_db.tab1
AS (SELECT id, name FROM local_db.source_table WHERE region = 'US') WITH DATA;
```

### ALTER TABLE

```sql
-- Add columns
ALTER TABLE my_lake.my_db.t1 ADD c3 INT NULL, ADD c4 VARCHAR(100) NULL;

-- Drop columns
ALTER TABLE my_lake.my_db.t1 DROP c3, DROP c4;

-- Rename column
ALTER TABLE my_lake.my_db.t1 RENAME c2 TO new_name;

-- Modify column type
ALTER TABLE my_lake.my_db.t1 MODIFY c3 VARCHAR(255);

-- Modify nullability
ALTER TABLE my_lake.my_db.t1 MODIFY c3 NULL;

-- Add column comment
ALTER TABLE my_lake.my_db.t1 MODIFY c3 COMMENT 'description here';

-- Reorder: AFTER or BEFORE (Iceberg only)
ALTER TABLE my_lake.my_db.t1 ADD (c7, c8) AFTER c6;

-- Partition evolution (Iceberg only)
ALTER TABLE my_lake.my_db.t1 ADD PARTITIONED BY c3;
ALTER TABLE my_lake.my_db.t1 DROP PARTITIONED BY c3;

-- Sort order (must drop and re-add to change)
ALTER TABLE my_lake.my_db.t1 ADD SORTED BY c2 ASC, c3 DESC;
ALTER TABLE my_lake.my_db.t1 DROP SORTED BY;

-- Add/update table property
ALTER TABLE my_lake.my_db.t1 ADD TBLPROPERTIES ('write.merge.mode'='copy-on-write');

-- Remove table property
ALTER TABLE my_lake.my_db.t1 DROP TBLPROPERTIES ('write.merge.mode'='copy-on-write');
```

**ALTER restrictions — all OTF:** Cannot combine different alter operations in one statement (e.g. add + modify). Type change and nullability/comment change cannot be in the same statement.

**Delta Lake ALTER restrictions:**
- No partition evolution (ADD/DROP PARTITIONED BY returns error)
- No column reorder (BEFORE/AFTER not supported)
- No SORTED BY
- No schema evolution on Unity catalog
- Column rename/drop requires enabling column mapping first:
  ```sql
  ALTER TABLE my_lake.my_db.t1 ADD TBLPROPERTIES ('delta.columnMapping.mode'='name');
  ```

### DROP TABLE

```sql
-- Remove table entry AND data files from object storage
DROP TABLE my_lake.my_db.t1 PURGE ALL;

-- Remove table entry from catalog only (data files remain — useful for shared catalogs)
DROP TABLE my_lake.my_db.t1 NO PURGE;
```

`PURGE ALL` or `NO PURGE` is required — omitting either is a syntax error.

---

## DML: Insert, Update, Delete

### INSERT — single row

```sql
INSERT INTO my_lake.my_db.t1 VALUES ('value1', 42, CURRENT_DATE, 'France');
```

Not supported: non-positional inserts, ORC data file writes in Iceberg, CLOB columns.

### INSERT INTO ... SELECT — bulk copy

```sql
-- From OTF table
INSERT INTO my_lake.my_db.t2
    SELECT * FROM my_lake.my_db.t1 WHERE country = 'France';

-- From local Teradata BFS/OFS table
INSERT INTO my_lake.my_db.t2
    SELECT id, name FROM local_db.source_table WHERE region = 'US';
```

### UPDATE

```sql
UPDATE my_lake.my_db.t1
SET c1 = 'new_value', c2 = 42
WHERE country = 'France';
```

**SET clause:** supports `column = literal` only. Also supported: `col = NULL`, `col = DATE`, `col = CURRENT_TIME`, `col = CURRENT_TIMESTAMP`. No arithmetic, no subqueries.

**WHERE clause restrictions:** No multiplication/division operators; `LIKE` allows `%` wildcard only (not `_`); no functions (LOWER, UPPER, ABS, TRIM, EXTRACT, etc.); no CAST; no subqueries; no FROM clause.

**Case sensitivity:** VARCHAR comparisons are always case-specific — `'Mark' ≠ 'MARK'`.

### DELETE

```sql
DELETE FROM my_lake.my_db.t1 WHERE country = 'France';
DELETE FROM my_lake.my_db.t1 ALL;
```

Same WHERE clause restrictions as UPDATE. Case-specific behavior applies.

---

## Alias Tables

Alias tables provide a two-part name shortcut to datalake tables, compatible with all client tools. Read-only.

```sql
-- Create alias: maps local two-part name to a datalake table
CREATE ALIAS TABLE db1.orders,
DATALAKE = my_lake,
DATALAKE TABLE = sales_db.orders;

-- Query via alias (read-only; also supports time travel)
SELECT * FROM db1.orders WHERE country = 'France';

-- Drop alias (does NOT affect the underlying OTF table or data)
DROP ALIAS TABLE db1.orders;
```

`HELP TABLE db1.orders` returns column info as if called on the underlying datalake table. `SHOW TABLE db1.orders` returns the alias CREATE syntax.

---

## Database Views for OTF Tables

Views over OTF tables are supported but **are not auto-refreshed** when the underlying OTF table schema changes. After schema evolution, manually run `REPLACE VIEW`.

```sql
CREATE VIEW v1 AS SELECT * FROM my_lake.db1.t1;
SELECT * FROM v1;

-- After schema changes to the OTF table, refresh the view:
REPLACE VIEW v1 AS SELECT * FROM my_lake.db1.t1;
```

Views work with joins across OTF, BFS, and OFS tables. CTAS using a view as source is supported.

---

## Statistics on OTF Tables

OTF stats are stored in `DBC.StatsTbl` with `StatsType = 'O'` and `RefObjects = "datalake"."database"."table"`.

```sql
-- Collect stats
COLLECT STATISTICS COLUMN(col1) ON my_lake.my_db.t1;
COLLECT STATISTICS COLUMN(col1, col2) ON my_lake.my_db.t1;         -- multi-column stats entry
COLLECT STATISTICS COLUMN(col1), COLUMN(col2) ON my_lake.my_db.t1; -- two separate entries

-- Drop stats
DROP STATISTICS COLUMN(col1) ON my_lake.my_db.t1;
DROP STATISTICS ON my_lake.my_db.t1;   -- drop all stats for table

-- Help stats (shows unique value counts per entry)
HELP STATISTICS ON my_lake.my_db.t1;

-- Show stats (returns executable COLLECT STATS statements)
SHOW STATISTICS ON my_lake.my_db.t1;
SHOW STATISTICS VALUES ON my_lake.my_db.t1;   -- includes VALUES clause with histogram data

-- Copy stats from a Teradata BFS/OFS table to an OTF table
COLLECT STATISTICS COLUMN(col1), COLUMN(col2) ON my_lake.my_db.t1
FROM local_source_table;

-- Stats recommendations via EXPLAIN
Diagnostic HELPSTATS ON FOR SESSION;
EXPLAIN SELECT * FROM my_lake.db1.t1 WHERE col3 = 4;
-- Recommended COLLECT STATISTICS statements appear at the end of the EXPLAIN output
```

**OTF stats views:**
- `DBC.OtfStatsV` — OTF stats only; includes `CatalogName` (= datalake name)
- `DBC.AllStatsV` — all stats (regular + OTF); `CatalogName = 'TD_Local'` for non-OTF

**COPY STATS rules:**
- OTF → TD (target is BFS): not supported via FROM clause syntax; use COLLECT on the TD table directly
- TD → OTF (OTF is target, TD is source): supported with matching column data types
- OTF → OTF: not supported (syntax error)
- `CT AS ... WITH STATS` where target is OTF: syntax error (stats cannot be copied to OTF via CTAS)
- `CT AS ... WITH STATS` where source is OTF, target is BFS: succeeds with warning 6962 (stats not copied)

**Not supported for OTF stats:** AS clause, expression stats, SUMMARY stats, SAMPLE stats, partition stats, `HELP/SHOW CURRENT STATS`, LOB/VarByte columns.

---

## Observability

```sql
-- Count of OTF queries run in the system
SELECT CAST(FeatureName AS CHAR(50)) AS FeatureName, FeatureUseCount
FROM DBC.QryLogFeatureUseCountV
WHERE FeatureName LIKE '%OTF%'
ORDER BY 2 DESC, 1 ASC;

-- DBQL query log: OTFQUERY = 'J' (Java engine) or 'N' (Native engine)
SELECT * FROM DBC.QryLogV WHERE OTFQUERY = 'J';
SELECT * FROM DBC.QryLogV_SZ WHERE OTFQUERY = 'N';   -- Zones variant

-- VantageCloud Lake systems only
SELECT * FROM PDCRINFO.DBQLogTbl WHERE OTFQUERY = 'J';
SELECT * FROM PDCRINFO.DBQLogTbl_Hst WHERE OTFQUERY = 'J';
```

---

## Type Mappings

### Teradata → Iceberg

| Teradata | Iceberg | R/W |
|---|---|---|
| BYTEINT | BOOLEAN | R/W |
| SMALLINT / INTEGER | INTEGER | R/W |
| BIGINT | LONG | R/W |
| REAL | DOUBLE | R/W |
| DATE | DATE | R/W |
| DECIMAL(p,s) | DECIMAL | R/W |
| TIME | TIME | R/W |
| TIMESTAMP | TIMESTAMP | R/W |
| TIMESTAMP WITH TIME ZONE | TIMESTAMP_WTZ | R/W |
| BYTE(n) | FIXED(n) | R/W |
| BLOB | BINARY | R/W |
| VARCHAR(n ≤ 32000) | STRING | R/W |
| VARCHAR(n ≤ 32000) | LIST / MAP / STRUCT | Read only |
| INTERVAL types | STRING | Write only |

Note: TIME is not supported by Iceberg on Unity catalog.

### Teradata → Delta Lake

| Teradata | Delta Lake | R/W |
|---|---|---|
| BYTEINT | BOOLEAN | R/W |
| SMALLINT | SMALLINT | R/W |
| INTEGER | INTEGER | R/W |
| BIGINT | BIGINT | R/W |
| REAL | DOUBLE | R/W |
| DATE | DATE | R/W |
| DECIMAL(p,s) | DECIMAL | R/W |
| TIMESTAMP | TIMESTAMP | R/W |
| BYTE(n) / BLOB | BINARY | R/W |
| VARCHAR(n ≤ 32000) | STRING | R/W |
| VARCHAR(n ≤ 32000) | ARRAY / MAP / STRUCT | Read only |
| INTERVAL types | STRING | Write only |

**Delta decimal limitations:** Reading decimal values in partition columns may fail with precision rescaling issues. Workaround: ensure precision is defined generously in the Delta schema.

---

## Limitations

### General

- **No transaction rollback** — manually delete external data files if needed
- Not supported: `DELETE DATABASE`, `MODIFY DATABASE`, `RENAME TABLE`, `SHOW TABLE` (use `HELP TABLE`), `UPSERT`, `MERGE`, Stored Procedures for OTF DDL/DML, Macros for OTF writes, multi-statement requests
- AWS: `catalog_location` and `storage_location` must be in the same AWS region
- Write operations are always case-specific (parquet is case-sensitive)
- No merge-on-read write mode (copy-on-write only for writes)

### Iceberg

- Read: handles both merge-on-read and copy-on-write data
- Write: copy-on-write only
- `TD_MANIFESTS()` supported; not supported for Delta Lake (returns error 3706)
- ORC write not supported

### Delta Lake

- Read and Write: copy-on-write only
- No partition transforms in CREATE/ALTER TABLE
- No SORTED BY
- No partition evolution (cannot ADD/DROP PARTITIONED BY)
- No column reorder (BEFORE/AFTER)
- No BLOB partition columns
- Column rename/drop requires `delta.columnMapping.mode = name`
- No schema evolution or partition evolution on Unity catalog
- Reading TIMESTAMP partition columns not supported (Delta Kernel limitation)
- DATE/TIMESTAMP values in WHERE clause for UPDATE/DELETE may cause errors
- DECIMAL partition columns: reading in expressions not supported; writing values must fit declared precision/scale
