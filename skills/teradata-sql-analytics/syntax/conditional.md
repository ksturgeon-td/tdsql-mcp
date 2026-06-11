# Teradata Conditional Expressions

## CASE
```sql
-- Searched CASE
CASE
    WHEN score >= 90 THEN 'A'
    WHEN score >= 80 THEN 'B'
    WHEN score >= 70 THEN 'C'
    ELSE 'F'
END

-- Simple CASE (equality test)
CASE status
    WHEN 'A' THEN 'Active'
    WHEN 'I' THEN 'Inactive'
    ELSE 'Unknown'
END
```

## Null-Handling Functions
```sql
COALESCE(a, b, c)       -- first non-NULL value; ANSI standard
NULLIF(a, b)            -- returns NULL if a = b, otherwise a
ZEROIFNULL(expr)        -- Teradata shorthand: NULL → 0
NULLIFZERO(expr)        -- Teradata shorthand: 0 → NULL

-- Examples
COALESCE(preferred_email, work_email, personal_email)
NULLIF(status, 'N/A')                       -- treat 'N/A' as NULL
revenue / NULLIFZERO(units)                 -- safe division
SUM(ZEROIFNULL(adjustment)) + base_amount   -- null-safe sum
```

## IIF / Inline IF
Teradata does not have a native `IIF()`. Use CASE instead:
```sql
-- Instead of IIF(condition, true_val, false_val):
CASE WHEN condition THEN true_val ELSE false_val END

-- One-liner shorthand is fine
CASE WHEN is_active = 1 THEN 'Yes' ELSE 'No' END AS active_flag
```

## IN / NOT IN
```sql
WHERE status IN ('A', 'B', 'C')
WHERE region NOT IN ('West', 'East')

-- Subquery form
WHERE id IN (SELECT id FROM db.exclusions)
```

## EXISTS / NOT EXISTS
```sql
WHERE EXISTS (
    SELECT 1 FROM db.orders o WHERE o.customer_id = c.id
)
```

## BETWEEN
```sql
WHERE amount BETWEEN 100 AND 500          -- inclusive
WHERE event_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31'
```

## Conditional Aggregation
```sql
-- Count rows meeting a condition
SUM(CASE WHEN type = 'credit' THEN 1 ELSE 0 END) AS credit_count

-- Conditional sum
SUM(CASE WHEN region = 'North' THEN amount ELSE 0 END) AS north_total

-- Pivot pattern: turn row values into columns
SUM(CASE WHEN month = 1 THEN amount END) AS jan,
SUM(CASE WHEN month = 2 THEN amount END) AS feb,
SUM(CASE WHEN month = 3 THEN amount END) AS mar
```

## GREATEST / LEAST
```sql
GREATEST(a, b, c)   -- maximum of the values (ignores NULLs if any non-NULL present)
LEAST(a, b, c)      -- minimum of the values
```
