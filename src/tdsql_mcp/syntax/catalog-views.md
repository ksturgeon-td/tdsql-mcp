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

## Listing Accessible Databases

Prefer the `list_databases` MCP tool — it calls `DBC.DatabasesV` which already filters to databases visible to the current session.

`DBC.DatabasesV` answers "what databases exist and are visible to me?"  
`DBC.AllRightsV` answers "what databases do I have explicit rights on?" (includes role-inherited grants)

Use `DBC.AllRightsV` when you need to know what rights a specific user holds:

```sql
-- Databases a user has rights on (includes role-inherited grants)
SELECT DISTINCT DatabaseName
FROM DBC.AllRightsV
WHERE UserName = 'some_user'
ORDER BY DatabaseName;

-- Full rights detail for a user
SELECT AccessRight, DatabaseName, TableName
FROM DBC.AllRightsV
WHERE UserName = 'some_user'
ORDER BY DatabaseName, TableName;
```

> **Do not use `DBC.UserRightsV` for database enumeration** — it shows only directly granted rights and misses role-inherited access. Use `DBC.AllRightsV` for a complete picture.

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

These views cover registered datalakes, external servers, and OTF statistics. They supplement the standard HELP commands (`HELP DATALAKE`, `HELP DATABASE`, `HELP TABLE`) — see `open-table-format` topic for HELP command syntax.

### DBC.DatalakeInfoV — Registered Datalakes

```sql
-- All registered datalakes and their properties
SELECT DatalakeName, CatalogType, CatalogURL,
       ObjectStoragePlatform, AuthorizationName, CommentString
FROM DBC.DatalakeInfoV
ORDER BY DatalakeName;
```

Columns include: `DatalakeName`, `CatalogType` (hive/glue/unity/rest/fabric), `CatalogURL`, `ObjectStoragePlatform` (S3/Azure/GCS), `AuthorizationName`, `CreateTimeStamp`, `CommentString`.

### DBC.ServerV — External Servers

```sql
-- All external server objects (includes datalakes)
SELECT ServerName, ServerType, AuthorizationName, CommentString
FROM DBC.ServerV
ORDER BY ServerType, ServerName;
```

### DBC.ManagedOTFTablesV — Managed OTF Tables

Lists OTF tables that Teradata has registered as managed (created via Vantage DDL rather than discovered from the catalog):

```sql
SELECT DatalakeName, DatabaseName, TableName, TableFormat,
       CreateTimeStamp, LastAlterTimeStamp
FROM DBC.ManagedOTFTablesV
ORDER BY DatalakeName, DatabaseName, TableName;
```

### DBC.OtfStatsV — OTF Statistics

Statistics collected on OTF table columns (via COLLECT STATISTICS with three-tier notation):

```sql
-- Statistics collected on OTF tables
SELECT DatabaseName, TableName, ColumnName, StatsType,
       LastCollectTimeStamp, SampleSize
FROM DBC.OtfStatsV
WHERE DatabaseName = 'my_lake'
ORDER BY TableName, ColumnName;
-- DatabaseName here is the datalake name
```

### DBC.AllStatsV — All Statistics (Teradata + OTF)

Combined view of statistics across both relational Teradata tables and OTF tables:

```sql
-- All stats (TD + OTF) for a database
SELECT DatabaseName, TableName, ColumnName, StatsType,
       LastCollectTimeStamp
FROM DBC.AllStatsV
WHERE DatabaseName = 'mydb'
ORDER BY TableName;
```

`DBC.StatsV` covers only relational tables. Use `DBC.AllStatsV` when you need a single view across both table types.
