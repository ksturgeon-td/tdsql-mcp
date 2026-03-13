# Teradata Data Types & Casting

## Numeric Types
| Type | Size | Range |
|------|------|-------|
| `BYTEINT` | 1 byte | -128 to 127 |
| `SMALLINT` | 2 bytes | -32,768 to 32,767 |
| `INTEGER` / `INT` | 4 bytes | ±2.1 billion |
| `BIGINT` | 8 bytes | ±9.2 × 10^18 |
| `DECIMAL(n, m)` / `NUMERIC(n, m)` | Variable | n total digits, m after decimal |
| `NUMBER` | Variable | Oracle-compatible variable precision |
| `FLOAT` / `REAL` / `DOUBLE PRECISION` | 8 bytes | IEEE 754 |

## Character Types
| Type | Description |
|------|-------------|
| `CHAR(n)` | Fixed-length, padded with spaces. Max 64,000 bytes |
| `VARCHAR(n)` | Variable-length. Max 64,000 bytes (32,000 Unicode) |
| `CLOB` | Character large object. Up to 2GB |
| `CHAR(n) CHARACTER SET UNICODE` | Unicode fixed-length |
| `VARCHAR(n) CHARACTER SET UNICODE` | Unicode variable-length |

## Date & Time Types
| Type | Description |
|------|-------------|
| `DATE` | Date only (YYYY-MM-DD) |
| `TIME [(n)]` | Time with optional fractional seconds precision |
| `TIMESTAMP [(n)]` | Date + time with optional fractional seconds |
| `INTERVAL YEAR TO MONTH` | Year/month duration |
| `INTERVAL DAY TO SECOND` | Day/time duration |

## Binary Types
| Type | Description |
|------|-------------|
| `BYTE(n)` | Fixed-length binary |
| `VARBYTE(n)` | Variable-length binary |
| `BLOB` | Binary large object. Up to 2GB |

## CAST Syntax
```sql
CAST(expression AS target_type [FORMAT 'fmt'])
```

## Common Cast Patterns
```sql
-- Numeric conversions
CAST(str_col AS INTEGER)
CAST(str_col AS DECIMAL(10, 2))
CAST(int_col AS FLOAT)
CAST(num_col AS VARCHAR(20))

-- Date conversions
CAST('2024-01-15' AS DATE FORMAT 'YYYY-MM-DD')
CAST('01/15/2024' AS DATE FORMAT 'MM/DD/YYYY')
CAST(ts_col AS DATE)
CAST(date_col AS TIMESTAMP)
CAST(date_col AS VARCHAR(10) FORMAT 'YYYY-MM-DD')

-- Timestamp conversions
CAST('2024-01-15 14:30:00' AS TIMESTAMP FORMAT 'YYYY-MM-DDBHH:MI:SS')

-- String to number
CAST('3.14' AS DECIMAL(10, 4))
CAST('42' AS INTEGER)
```

## FORMAT Clause
The `FORMAT` clause controls display and parsing format for dates and numerics:
```sql
-- Date formats
FORMAT 'YYYY-MM-DD'
FORMAT 'MM/DD/YYYY'
FORMAT 'YYYYMMDD'
FORMAT 'MMM DD, YYYY'    -- e.g. Jan 15, 2024

-- Numeric formats
FORMAT 'ZZZ,ZZ9.99'      -- suppress leading zeros, add comma, 2 decimal places
FORMAT '999,999,990.00'  -- fixed-width with comma grouping
```

## Implicit Conversion Gotchas
- `CHAR` comparisons pad with spaces: `'abc' = 'abc   '` is TRUE
- Date arithmetic returns `INTEGER` (number of days): `end_date - start_date`
- Mixing `CHAR` and `VARCHAR` in UNION requires explicit CAST
- `NULL` comparisons: always use `IS NULL` / `IS NOT NULL`, never `= NULL`
