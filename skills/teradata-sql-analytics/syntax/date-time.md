# Teradata Date & Time

## Data Types
| Type | Description | Example literal |
|------|-------------|-----------------|
| `DATE` | Date only | `DATE '2024-01-15'` |
| `TIME` | Time only | `TIME '14:30:00'` |
| `TIMESTAMP` | Date + time | `TIMESTAMP '2024-01-15 14:30:00'` |
| `INTERVAL` | Duration | `INTERVAL '3' MONTH` |

## Current Values
```sql
CURRENT_DATE          -- today's date
CURRENT_TIME          -- current time
CURRENT_TIMESTAMP     -- current date + time
```

## Date Arithmetic
```sql
-- Add/subtract days (integers)
CURRENT_DATE - 7                          -- 7 days ago
CURRENT_DATE + 30                         -- 30 days from now

-- Add/subtract using INTERVAL
CURRENT_DATE - INTERVAL '1' MONTH
CURRENT_DATE + INTERVAL '2' YEAR
CURRENT_TIMESTAMP + INTERVAL '4' HOUR
CURRENT_TIMESTAMP - INTERVAL '90' MINUTE

-- Difference between two dates (returns integer days)
end_date - start_date

-- Difference in months
MONTHS_BETWEEN(end_date, start_date)
```

## Formatting & Casting
```sql
-- Date to formatted string
CAST(order_date AS VARCHAR(10) FORMAT 'YYYY-MM-DD')
CAST(order_date AS VARCHAR(10) FORMAT 'MM/DD/YYYY')

-- String to date
CAST('2024-01-15' AS DATE FORMAT 'YYYY-MM-DD')

-- Timestamp to date
CAST(ts_col AS DATE)

-- Date to timestamp
CAST(date_col AS TIMESTAMP)

-- Extract components
EXTRACT(YEAR  FROM date_col)
EXTRACT(MONTH FROM date_col)
EXTRACT(DAY   FROM date_col)
EXTRACT(HOUR  FROM ts_col)
```

## Truncation
```sql
-- Truncate to start of month
CAST(CAST(date_col AS CHAR(7) FORMAT 'YYYY-MM') || '-01' AS DATE FORMAT 'YYYY-MM-DD')

-- Or using TD_SYSFNLIB helpers where available
TRUNC(date_col, 'MM')   -- start of month
TRUNC(date_col, 'YYYY') -- start of year
```

## Day of Week / Week of Year
```sql
-- Day of week: Sunday=1 ... Saturday=7
((date_col - DATE '1900-01-07') MOD 7) + 1

-- Using TD_DAY_OF_WEEK if available
TD_DAY_OF_WEEK(date_col)    -- 1=Sunday

-- Week number
TD_WEEK_OF_YEAR(date_col)
```

## Common Patterns
```sql
-- Last N days
WHERE event_date >= CURRENT_DATE - 30

-- Current month
WHERE EXTRACT(YEAR FROM event_date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM event_date) = EXTRACT(MONTH FROM CURRENT_DATE)

-- Between two dates (inclusive)
WHERE event_date BETWEEN DATE '2024-01-01' AND DATE '2024-03-31'

-- Convert Unix epoch (seconds) to timestamp
CAST(DATE '1970-01-01' AS TIMESTAMP) + INTERVAL '1' SECOND * epoch_col
```

## Format Tokens
| Token | Meaning |
|-------|---------|
| `YYYY` | 4-digit year |
| `YY` | 2-digit year |
| `MM` | Month (01–12) |
| `MMM` | Month abbreviation (Jan, Feb…) |
| `DD` | Day (01–31) |
| `HH` | Hour (00–23) |
| `MI` | Minute (00–59) |
| `SS` | Second (00–59) |
