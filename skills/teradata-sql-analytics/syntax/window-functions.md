# Teradata Window (OLAP) Functions

## Syntax Template
```sql
function() OVER (
    [PARTITION BY col1, col2]
    [ORDER BY col3 [ASC|DESC]]
    [ROWS|RANGE BETWEEN frame_start AND frame_end]
)
```

## Ranking Functions
```sql
ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC)  -- unique sequential rank
RANK()       OVER (PARTITION BY dept ORDER BY salary DESC)  -- gaps on ties
DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC)  -- no gaps on ties
PERCENT_RANK() OVER (ORDER BY col)                          -- 0.0 to 1.0 relative rank
CUME_DIST()    OVER (ORDER BY col)                          -- cumulative distribution
NTILE(4)       OVER (ORDER BY col)                          -- assign quartile (1–4)
```

## Offset Functions
```sql
LAG(col, n, default)  OVER (PARTITION BY ... ORDER BY ...)  -- previous row value
LEAD(col, n, default) OVER (PARTITION BY ... ORDER BY ...)  -- next row value
FIRST_VALUE(col)      OVER (PARTITION BY ... ORDER BY ...)
LAST_VALUE(col)       OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
```

## Running / Moving Aggregates
```sql
-- Running total
SUM(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)

-- Running average
AVG(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)

-- 7-day moving average (current row + 6 preceding)
AVG(amount) OVER (ORDER BY event_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)

-- Partition total (for % of total calculations)
SUM(amount) OVER (PARTITION BY dept)
```

## Frame Specifications
| Clause | Meaning |
|--------|---------|
| `ROWS UNBOUNDED PRECEDING` | From first row in partition to current |
| `ROWS BETWEEN n PRECEDING AND CURRENT ROW` | Rolling window of n+1 rows |
| `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` | Entire partition |
| `RANGE BETWEEN INTERVAL '7' DAY PRECEDING AND CURRENT ROW` | Date-based range window |

## QUALIFY — Filter on Window Results
Teradata's `QUALIFY` applies a filter on window function output without a subquery:
```sql
-- Keep only the most recent row per customer
SELECT *
FROM db.events
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ts DESC) = 1;

-- Top 3 products by revenue per category
SELECT category, product, revenue
FROM db.sales
QUALIFY RANK() OVER (PARTITION BY category ORDER BY revenue DESC) <= 3;

-- Flag rows where value jumps more than 10% from previous
SELECT *, value / LAG(value) OVER (PARTITION BY id ORDER BY dt) - 1 AS pct_chg
FROM db.series
QUALIFY ABS(pct_chg) > 0.10;
```

## Common Patterns

```sql
-- Deduplicate: keep latest record per key
SELECT * FROM db.t
QUALIFY ROW_NUMBER() OVER (PARTITION BY key_col ORDER BY updated_at DESC) = 1;

-- Running total that resets per partition
SELECT dept, month, sales,
       SUM(sales) OVER (PARTITION BY dept ORDER BY month ROWS UNBOUNDED PRECEDING) AS ytd
FROM db.monthly_sales;

-- Period-over-period comparison
SELECT dt, revenue,
       LAG(revenue, 1, 0) OVER (ORDER BY dt) AS prev_revenue,
       revenue - LAG(revenue, 1, 0) OVER (ORDER BY dt) AS delta
FROM db.daily_revenue;

-- Percentile bucket (decile)
SELECT *, NTILE(10) OVER (ORDER BY score) AS decile FROM db.scores;

-- Gap-and-island: number consecutive groups
SELECT id, dt,
       dt - ROW_NUMBER() OVER (PARTITION BY id ORDER BY dt) AS grp
FROM db.daily_activity;
```
