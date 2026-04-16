# Teradata UAF — Formula Syntax Rules

User-defined formula syntax used by UAF functions that accept a `FORMULA(...)` parameter.

**Functions that use formulas:**
- `TD_GENSERIES4FORMULA` (uaf-data-prep) — generate a series by applying a formula to input payload fields
- `TD_LINEAR_REGR` (uaf-estimation) — simple linear regression formula
- `TD_MULTIVAR_REGR` (uaf-estimation) — multivariate regression formula
- `TD_BREUSCH_PAGAN_GODFREY` (uaf-diagnostics) — optional formula for auxiliary regression

---

## Formula Structure

A formula is a `VARCHAR(64000)` string passed to `FUNC_PARAMS(FORMULA(...))`. Rules:

- Enclosed in single or double quotation marks.
- Must start with `Y =` (or `y =`).
- `Y` is the **response variable** (dependent variable) and corresponds to the **first field** in `SERIES_SPEC(PAYLOAD(FIELDS(...)))`.
- The expression after `Y =` is a SQL arithmetic expression composed of coefficients, explanatory variables, numeric constants, operators, math functions, and parentheses.

### Variable naming

**Explanatory variables** (the Xn inputs):
- The **nth explanatory variable** corresponds to the **nth field** in `PAYLOAD(FIELDS(...))`.
- Can appear in the formula any number of times.
- Must have a valid Teradata name label.

**Coefficients** — appear immediately before `*` and an explanatory variable:
- **Numeric constant coefficients:** literal values (e.g., `6`, `2.99`, `89`) — value is fixed.
- **Numeric variable coefficients:** named variables (e.g., `a`, `B0`, `B1`) — value is **estimated by the function**.
  - Must appear exactly once in the formula.
  - Names are case-insensitive.
  - Must be valid Teradata UNICODE object names with no escape characters or quotation marks.

### Examples

```sql
-- Numeric variable coefficients (a, b, c, d are estimated by the function)
FORMULA('Y = d + a*X1 + b*X2 + c*(exp(X3) * cos(X2))')

-- Numeric constant coefficients (all values fixed)
FORMULA('Y = 89 + 6*X1 + 2.99*X1**2 + exp(X2)')

-- Linear regression formulas (B0, B1, B2 are estimated)
FORMULA('Y = B0 + B1*X1')
FORMULA('Y = B0 + B1*X1 + B2*X2')
```

---

## Operator Precedence

Evaluation order (highest to lowest precedence):

| Precedence | Operators |
|------------|-----------|
| 1 (highest) | Unary `+` and unary `-` |
| 2 | Exponentiation `**` |
| 3 | Multiplication `*` and division `/` |
| 4 (lowest) | Addition `+` and subtraction `-` |

- Expressions in parentheses are evaluated first.
- Operators of equal precedence are evaluated left to right.

---

## Arithmetic Operators

| Operator | Operation |
|----------|-----------|
| `**` | Exponentiate |
| `*` | Multiply |
| `/` | Divide |
| `+` | Add |
| `-` | Subtract |
| `+` | Unary plus |
| `-` | Unary minus |

---

## Math Functions

| Function | Description |
|----------|-------------|
| `ABS(x)` | Absolute value |
| `CEILING(x)` | Smallest integer ≥ x |
| `EXP(x)` | e raised to the power x (e ≈ 2.71828) |
| `FLOOR(x)` | Largest integer ≤ x |
| `LN(x)` | Natural logarithm (base e) |
| `LOG(x)` | Base-10 logarithm |
| `NANIFZERO(x)` | Converts 0 to NaN — avoids division-by-zero errors; **FORMULA parameter only** |
| `POWER(base, exp)` | base raised to the power of exp |
| `RANDOM` | Random integer per result row |
| `ROUND(x, n)` | x rounded to n decimal places |
| `SIGN(x)` | Sign of x: −1, 0, or 1 |
| `SQRT(x)` | Square root |
| `TRUNC(x, n)` | x truncated to n decimal places |
| `ZEROIFNAN(x)` | Converts NaN to 0 — avoids NaN propagation errors; **FORMULA parameter only** |

---

## Trigonometric Functions

All angles are in radians unless converted with DEGREES/RADIANS.

| Function | Description |
|----------|-------------|
| `SIN(x)` | Sine; result in [−1, 1] |
| `COS(x)` | Cosine; result in [−1, 1] |
| `TAN(x)` | Tangent |
| `ASIN(x)` | Arcsine; result in [−π/2, π/2] |
| `ACOS(x)` | Arccosine; result in [0, π] |
| `ATAN(x)` | Arctangent; result in [−π/2, π/2] |
| `ATAN2(x, y)` | Four-quadrant arctangent; result in (−π, π]; positive = counterclockwise from x-axis |
| `SINH(x)` | Hyperbolic sine |
| `COSH(x)` | Hyperbolic cosine |
| `TANH(x)` | Hyperbolic tangent |
| `ASINH(x)` | Inverse hyperbolic sine |
| `ACOSH(x)` | Inverse hyperbolic cosine |
| `ATANH(x)` | Inverse hyperbolic tangent |
| `DEGREES(x)` | Convert radians to degrees |
| `RADIANS(x)` | Convert degrees to radians |
