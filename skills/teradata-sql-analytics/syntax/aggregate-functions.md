# Teradata Aggregate Functions

## Standard Aggregates
```sql
COUNT(*)               -- count all rows
COUNT(col)             -- count non-NULL values
COUNT(DISTINCT col)    -- count distinct non-NULL values
SUM(col)
AVG(col)
MIN(col)
MAX(col)
```

## Statistical Aggregates
```sql
STDDEV_POP(col)        -- population standard deviation
STDDEV_SAMP(col)       -- sample standard deviation
VAR_POP(col)           -- population variance
VAR_SAMP(col)          -- sample variance
```

## Percentile / Quantile
```sql
-- Exact (sorts all data — can be slow on large sets)
PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)    -- median
PERCENTILE_DISC(0.25) WITHIN GROUP (ORDER BY col)   -- 25th percentile (discrete)

-- Approximate (fast, uses HLL sketch — Vantage)
APPROX_PERCENTILE(col, 0.5)
APPROX_PERCENTILE(col, 0.95)
```

## Approximate Count Distinct
```sql
-- HyperLogLog-based — much faster than COUNT(DISTINCT) on large data
APPROX_COUNT_DISTINCT(col)
```

## String Aggregation
```sql
-- Concatenate values into one string (XML-based, common pattern)
XMLAGG(XMLELEMENT(NAME x, col || ',') ORDER BY col)

-- Cleaner alternative using TD_SYSFNLIB.XMLAGG or custom UDF
```

## GROUP BY Variants
```sql
-- Standard
SELECT dept, SUM(salary) FROM db.t GROUP BY dept;

-- Multiple grouping sets in one pass
GROUP BY GROUPING SETS ((dept), (region), (dept, region), ())

-- Equivalent shorthand
GROUP BY ROLLUP(dept, region)   -- all prefixes + grand total
GROUP BY CUBE(dept, region)     -- all combinations

-- Identify which grouping a row belongs to
GROUPING(dept)     -- 1 if dept is aggregated away, 0 if not
```

## HAVING
```sql
SELECT dept, COUNT(*) AS cnt
FROM db.employees
GROUP BY dept
HAVING COUNT(*) > 10;
```

## Conditional Aggregation
```sql
-- Count rows meeting a condition
SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count

-- Average only non-zero values
AVG(NULLIFZERO(amount))

-- Max of a filtered subset
MAX(CASE WHEN category = 'A' THEN value END)
```

## Common Patterns
```sql
-- Frequency distribution
SELECT val, COUNT(*) AS freq,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM db.t
GROUP BY val
ORDER BY freq DESC;

-- Running total (use window function instead of aggregate)
SUM(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)
```
