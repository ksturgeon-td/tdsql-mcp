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

-- Difference in months (returns a fractional value, not an integer count)
MONTHS_BETWEEN(end_date, start_date)
```

## Formatting & Casting
```sql
-- Date to formatted string: apply FORMAT to the date first, then cast to VARCHAR
-- CAST(date AS VARCHAR FORMAT '...') fails with Error 3617 — FORMAT must target the date type
CAST(CAST(order_date AS FORMAT 'YYYY-MM-DD') AS VARCHAR(10))
CAST(CAST(order_date AS FORMAT 'MM/DD/YYYY') AS VARCHAR(10))

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
-- Simplest: TRUNC (verified on Teradata 20.x)
TRUNC(date_col, 'MM')   -- start of month
TRUNC(date_col, 'YYYY') -- start of year

-- Arithmetic alternative (no format handling needed)
date_col - (EXTRACT(DAY FROM date_col) - 1)   -- start of month

-- Format-based method (nested form required — outer CAST to VARCHAR then to DATE)
CAST(CAST(CAST(date_col AS FORMAT 'YYYY-MM') AS CHAR(7)) || '-01' AS DATE FORMAT 'YYYY-MM-DD')
```

## Day of Week / Week of Year
```sql
-- Day of week: Sunday=1 ... Saturday=7
((date_col - DATE '1900-01-07') MOD 7) + 1

-- Using TD_DAY_OF_WEEK (verified on Teradata 20.x)
TD_DAY_OF_WEEK(date_col)    -- 1=Sunday

-- Week number (not ISO-8601: ISO week 3 may return week 2, etc.)
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
TO_TIMESTAMP(epoch_col)   -- simplest; verified on Teradata 20.x (UTC session)

-- Interval fallback: keep each multiplier under 100 to avoid INTERVAL overflow (Error 7453)
-- INTERVAL '1' SECOND * large_epoch overflows — decompose instead:
CAST(DATE '1970-01-01' + epoch_col / 86400 AS TIMESTAMP(0))
  + ((epoch_col MOD 86400) / 3600) * INTERVAL '1' HOUR
  + ((epoch_col MOD 3600) / 60)   * INTERVAL '1' MINUTE
  + (epoch_col MOD 60)            * INTERVAL '1' SECOND
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
| `B` | Literal space — use `B` not ` ` (a literal space in a FORMAT string is silently dropped) |

> **Note:** A format string cannot repeat a field — `'YYYY/YY'` raises Error 3530.
