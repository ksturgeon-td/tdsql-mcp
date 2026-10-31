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
-- No native approximate percentile function found on Teradata 20.00.30.76.
```

## Distinct Count
```sql
COUNT(DISTINCT col)
-- No native APPROX_COUNT_DISTINCT found on Teradata 20.00.30.76.
```

## String Aggregation
```sql
-- Concatenate values into one delimited string: aggregate, cast, and trim the trailing comma
-- Note: wrapping with XMLELEMENT keeps XML tags in output — use TRIM + CAST instead
SELECT dept,
       TRIM(TRAILING ',' FROM CAST(XMLAGG(TRIM(col) || ',' ORDER BY col) AS VARCHAR(1000))) AS vals
FROM db.t
GROUP BY dept;
-- LISTAGG and STRING_AGG are not available on Teradata 20.00.30.76.
```

## GROUP BY Variants
```sql
-- Standard
SELECT dept, SUM(salary) FROM db.t GROUP BY dept;

-- Multiple grouping sets in one pass
GROUP BY GROUPING SETS ((dept), (region), (dept, region), ())

-- CUBE produces the same result as the four-set GROUPING SETS example above
GROUP BY CUBE(dept, region)     -- all combinations + grand total

-- ROLLUP is smaller: (dept, region), (dept), and the grand total () only
GROUP BY ROLLUP(dept, region)   -- all prefixes + grand total

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
MAX(CASE WHEN category = 'A' THEN "value" END)   -- value is a reserved word; must be quoted
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
