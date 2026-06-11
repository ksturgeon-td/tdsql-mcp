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
