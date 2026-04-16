# Teradata Numeric Functions

## Rounding & Truncation
```sql
ROUND(expr, n)          -- round to n decimal places
TRUNC(expr, n)          -- truncate (no rounding) to n decimal places
FLOOR(expr)             -- largest integer <= expr
CEILING(expr) / CEIL(expr) -- smallest integer >= expr
```

## Absolute Value & Sign
```sql
ABS(expr)               -- absolute value
SIGN(expr)              -- -1, 0, or 1
```

## Modulo
```sql
expr MOD divisor        -- Teradata keyword form
MOD(expr, divisor)      -- function form
-- Example: even/odd
id MOD 2 = 0            -- even rows
```

## Power & Roots
```sql
expr ** n               -- raise to power (Teradata operator)
POWER(expr, n)          -- same, ANSI form
SQRT(expr)              -- square root
EXP(expr)               -- e^expr
```

## Logarithms
```sql
LN(expr)                -- natural log
LOG(expr)               -- log base 10
-- Custom base: LOG(expr) / LOG(base)
```

## Trigonometry
```sql
SIN(expr)  COS(expr)  TAN(expr)
ASIN(expr) ACOS(expr) ATAN(expr) ATAN2(y, x)
-- Input/output in radians
-- Degrees to radians: expr * ACOS(-1) / 180
```

## Null-Safe Arithmetic
```sql
ZEROIFNULL(expr)        -- replace NULL with 0
NULLIFZERO(expr)        -- replace 0 with NULL (useful for avoiding divide-by-zero)

-- Safe division
numerator / NULLIFZERO(denominator)
```

## Numeric Formatting
```sql
-- Cast to fixed decimal
CAST(expr AS DECIMAL(10, 2))

-- Format as string with commas / specific format
CAST(expr AS VARCHAR(20) FORMAT 'Z,ZZ9.99')
```

## Random Numbers
```sql
-- Pseudo-random float in [0, 1)
RANDOM(0, 100)          -- random integer between 0 and 100 inclusive
```

## Statistical Functions (aggregate context)
```sql
SUM(col)
AVG(col)
MIN(col) / MAX(col)
STDDEV_POP(col)         -- population standard deviation
STDDEV_SAMP(col)        -- sample standard deviation
VAR_POP(col)            -- population variance
VAR_SAMP(col)           -- sample variance

-- Approximate percentile (TD Vantage)
APPROX_PERCENTILE(col, 0.5)   -- median
APPROX_PERCENTILE(col, 0.95)  -- 95th percentile
```

## Type Conversion
```sql
CAST(expr AS INTEGER)
CAST(expr AS BIGINT)
CAST(expr AS DECIMAL(15, 4))
CAST(expr AS FLOAT)
CAST('3.14' AS DECIMAL(10, 4))
```
