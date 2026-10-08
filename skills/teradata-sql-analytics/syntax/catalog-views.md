# Teradata Catalog Views (DBC.*)

DBC views expose the Teradata data dictionary. Always use the `V` (view) variants
(e.g. `DBC.TablesV`) over the base tables — they enforce access control properly.

## Databases & Users
```sql
-- List all accessible databases
SELECT DatabaseName, DBKind, CommentString
FROM DBC.DatabasesV
ORDER BY DatabaseName;
-- DBKind: 'D' = database, 'U' = user

-- List users
SELECT UserName, DefaultDatabase, CreateDate
FROM DBC.UsersV
ORDER BY UserName;
```

## Tables & Views
```sql
-- All tables in a database
SELECT TableName, TableKind, CreateTimeStamp, LastAlterTimeStamp
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
ORDER BY TableKind, TableName;
-- TableKind: 'T'=table, 'V'=view, 'O'=NoPI table, 'Q'=queue, 'E'=error, 'I'=join index

-- Search for tables by name pattern
SELECT DatabaseName, TableName, TableKind
FROM DBC.TablesV
WHERE TableName LIKE '%customer%'
ORDER BY DatabaseName, TableName;

-- View definition (DDL text)
SELECT RequestText FROM DBC.TablesV
WHERE DatabaseName = 'mydb' AND TableName = 'my_view';
```

## Columns
```sql
-- All columns for a table
SELECT ColumnId, ColumnName, ColumnType, ColumnLength,
       Nullable, DefaultValue, ColumnFormat, CommentString
FROM DBC.ColumnsV
WHERE DatabaseName = 'mydb' AND TableName = 'mytable'
ORDER BY ColumnId;

-- Find tables that contain a specific column
SELECT DatabaseName, TableName, ColumnName, ColumnType
FROM DBC.ColumnsV
WHERE ColumnName = 'customer_id'
ORDER BY DatabaseName, TableName;

-- Find columns matching a pattern across all databases
SELECT DatabaseName, TableName, ColumnName
FROM DBC.ColumnsV
WHERE ColumnName LIKE '%email%'
ORDER BY DatabaseName, TableName;
```

## Indexes & Primary Index
```sql
-- Indexes on a table
SELECT IndexName, IndexType, UniqueFlag, ColumnName, ColumnPosition
FROM DBC.IndicesV
WHERE DatabaseName = 'mydb' AND TableName = 'mytable'
ORDER BY IndexType, ColumnPosition;
-- IndexType: 'P'=primary, 'S'=secondary, 'U'=unique, 'J'=join index
```

## Table Size & Storage
```sql
-- Table sizes in a database (from collected stats — no full scan)
SELECT TableName,
       SUM(CurrentPerm) / 1024 / 1024 AS size_mb,
       SUM(PeakPerm) / 1024 / 1024 AS peak_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
GROUP BY TableName
ORDER BY size_mb DESC;

-- Database space summary
SELECT DatabaseName,
       SUM(MaxPerm) / 1024 / 1024 / 1024     AS max_gb,
       SUM(CurrentPerm) / 1024 / 1024 / 1024  AS used_gb
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
ORDER BY used_gb DESC;
```

## Statistics
```sql
-- Collected statistics on a table
SELECT ColumnName, StatsType, LastCollectTimeStamp, SampleSize
FROM DBC.StatsV
WHERE DatabaseName = 'mydb' AND TableName = 'mytable'
ORDER BY ColumnName;
```

## Access Rights
```sql
-- What access does the current user have on a database?
SELECT AccessRight, DatabaseName, TableName
FROM DBC.UserRightsV
WHERE UserName = USER
ORDER BY DatabaseName, TableName;
```

## Database Hierarchy
```sql
-- List direct children of a parent database (Elastic Compute: global databases)
-- DBC.ChildrenV columns are Child and Parent (NOT DatabaseName / ParentName)
SELECT Child AS DatabaseName FROM DBC.ChildrenV WHERE Parent = 'TD_GLOBAL';

-- Find all databases that are children of TD_PARENT (local/user databases)
SELECT Child AS DatabaseName FROM DBC.ChildrenV WHERE Parent = 'TD_PARENT';
```

## Common Lookup Patterns
```sql
-- Fully qualified table info in one query
SELECT
    c.DatabaseName,
    c.TableName,
    t.TableKind,
    c.ColumnName,
    c.ColumnType,
    c.Nullable
FROM DBC.ColumnsV c
JOIN DBC.TablesV t
    ON t.DatabaseName = c.DatabaseName AND t.TableName = c.TableName
WHERE c.DatabaseName = 'mydb'
ORDER BY c.TableName, c.ColumnId;
```

---

## Open Table Format (OTF) Catalog Views

Use these views to discover and inspect Iceberg tables, Delta Lake tables, datalake objects, and OTF statistics registered in Teradata Vantage. These cover metadata that cannot be queried via `DBC.TablesV` or `DBC.ColumnsV`.

**Keyword index:** Iceberg, Delta Lake, Open Table Format, OTF, datalake, external catalog, Hive metastore, AWS Glue, Databricks Unity Catalog, Polaris, Gravitino, Lake Formation, OTF statistics, managed tables, external servers, `HELP DATALAKE`, `HELP DATABASE`, `HELP TABLE`.

These views supplement the HELP commands — see `open-table-format` topic for full DDL/DML syntax and HELP command usage.

### DBC.DatalakeInfoV — Registered Datalakes (Iceberg / Delta Lake catalogs)

> **Access note:** On some systems, `DBC.DatalakeInfoV` raises **Error 3523** (not accessible)
> even for `TD_CREATOR` / `TD_ADMIN` users. If you get Error 3523 or an empty result set,
> fall back to `DBC.ServerV` and `SHOW DATALAKE <name>` for discovery.

```sql
SELECT DatalakeName, OTFTableFormat, CatalogType, CatalogLocation,
       StorageLocation, StorageEndPoint, StorageRegion,
       UnityCatalogName, StorageAccountName
FROM DBC.DatalakeInfoV
ORDER BY DatalakeName;
```

Columns include: `DatalakeName`, `OTFTableFormat` (ICEBERG/DELTA), `CatalogType`
(hive/glue/unity/rest/fabric/biglake), `CatalogLocation` (catalog URL / AWS region),
`StorageLocation`, `StorageEndPoint`, `StorageRegion`, `UnityCatalogName`, `StorageAccountName`.

### DBC.ServerV — External Servers (primary discovery path)

Use `DBC.ServerV` as the primary fallback when `DBC.DatalakeInfoV` is inaccessible or
returns no rows. It lists all registered foreign servers, including OTF datalakes.

```sql
SELECT ServerName, DataBaseName, AuthorizationName, AuthorizationType,
       CatalogAuthName, TableFormat
FROM DBC.ServerV
ORDER BY ServerName;
-- DataBaseName: the database this server is registered in (usually TD_SERVER_DB)
-- TableFormat: ICEBERG, DELTA, or blank for non-OTF servers
-- AuthorizationType: type of the auth object (S = standard, etc.)
```

> **Note:** `DBC.ServerV` does not have `ServerType` or `CommentString` columns.

### DBC.ManagedOTFTablesV — Managed OTF Tables

```sql
SELECT DatalakeName, DatabaseName, TableName, TableFormat,
       CreateTimeStamp, LastAlterTimeStamp
FROM DBC.ManagedOTFTablesV
ORDER BY DatalakeName, DatabaseName, TableName;
```

### DBC.OtfStatsV — OTF Statistics

```sql
SELECT DatabaseName, TableName, ColumnName, StatsType,
       LastCollectTimeStamp, SampleSize
FROM DBC.OtfStatsV
WHERE DatabaseName = 'my_lake'
ORDER BY TableName, ColumnName;
```

### DBC.AllStatsV — All Statistics (Teradata + OTF)

```sql
SELECT DatabaseName, TableName, ColumnName, StatsType,
       LastCollectTimeStamp
FROM DBC.AllStatsV
WHERE DatabaseName = 'mydb'
ORDER BY TableName;
```

`DBC.StatsV` covers only relational tables. Use `DBC.AllStatsV` when you need a single view across both table types.

---

## Alternate OTF Discovery Path — TD_SERVER_DB and HELP FOREIGN SERVER

`TD_SERVER_DB` is a system database that holds all foreign server registrations, including DATALAKE objects and QueryGrid foreign servers. Use this path when `DBC.DatalakeInfoV` returns no rows or you need to enumerate all foreign servers to find which ones are OTF datalakes.

### Step 1 — List all foreign servers

```sql
HELP DATABASE TD_SERVER_DB;
```

Returns a row per object. Rows with `Kind = 'K'` are foreign servers. These can be either QueryGrid foreign servers or DATALAKE objects — the next step distinguishes them.

### Step 2 — Inspect a foreign server

```sql
HELP FOREIGN SERVER TD_SERVER_DB.<foreign_server_name>;
```

- If the object is an **OTF DATALAKE**, this returns the databases inside it — equivalent to `HELP DATALAKE <datalake_name>`.
- If it is a QueryGrid foreign server, the output will reflect that server's structure instead.

### Full discovery workflow

```sql
-- Step 1: find all foreign server entries
HELP DATABASE TD_SERVER_DB;
-- Look for rows where Kind = 'K'

-- Step 2: for each Kind='K' entry, inspect it
HELP FOREIGN SERVER TD_SERVER_DB.my_lake_name;
-- If OTF: returns list of databases inside the datalake
-- Then use HELP DATABASE and HELP TABLE to drill down:
HELP DATABASE my_lake_name.my_otf_database;
HELP TABLE my_lake_name.my_otf_database.my_table;
```

> **When to use this path:** Use `TD_SERVER_DB` + `HELP FOREIGN SERVER` when the user asks about available external data, Iceberg catalogs, or datalake objects and you do not already know the datalake name. Start here to enumerate what exists, then use `HELP DATALAKE` / `HELP DATABASE` / `HELP TABLE` to drill into specifics.
