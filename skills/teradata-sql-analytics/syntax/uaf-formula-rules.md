# Teradata UAF — Formula Syntax Rules

User-defined formula syntax used by UAF functions that accept a `FORMULA(...)` parameter.

**Functions that use formulas:**
- `TD_GENSERIES4FORMULA` (uaf-data-prep) — generate a series by applying a formula to input payload fields
- `TD_LINEAR_REGR` (uaf-estimation) — linear combinations only; math functions are rejected (error 9153)
- `TD_MULTIVAR_REGR` (uaf-estimation) — linear combinations only; math functions are rejected (error 9153); requires at least 3 payload fields (response + 2 explanatory)
- `TD_BREUSCH_PAGAN_GODFREY` (uaf-diagnostics) — optional formula for auxiliary regression

---

## Formula Structure

A formula is a `VARCHAR(64000)` string passed to `FUNC_PARAMS(FORMULA(...))`. Rules:

- Enclosed in single quotation marks. Double quotation marks fail with error 3706 ("Could not convert value for 'FORMULA'").
- Must start with `Y =` (or `y =`).
- `Y` is the **response variable** (dependent variable) and corresponds to the **first field** in `SERIES_SPEC(PAYLOAD(FIELDS(...)))`.
- The expression after `Y =` is a SQL arithmetic expression composed of coefficients, explanatory variables, numeric constants, operators, math functions, and parentheses.

### Variable naming

**Explanatory variables** (the Xn inputs):
- The **nth explanatory variable** corresponds to the **nth field** in `PAYLOAD(FIELDS(...))`.
- In `TD_GENSERIES4FORMULA`, can appear any number of times. In the regression functions each Xn may appear only once (error 9153, "Xn is specified more than once"); supply derived terms such as X1² as separate payload fields.
- Must have a valid Teradata name label.

**Coefficients** — appear immediately before `*` and an explanatory variable:
- **Numeric constant coefficients:** literal values (e.g., `6`, `2.99`, `89`) — value is fixed.
- **Numeric variable coefficients:** named variables (e.g., `B0`, `B1`) — value is **estimated by the function**.
  Supported only by the regression functions; `TD_GENSERIES4FORMULA` rejects them (error 9153) and accepts only X1, X2, … XN and numeric constants.
  - Must appear exactly once in the formula.
  - Names are case-insensitive.
  - Must be valid Teradata UNICODE object names with no escape characters or quotation marks.

### Examples

```sql
-- TD_GENSERIES4FORMULA: numeric constant coefficients only (math functions supported, named coefficients rejected)
FORMULA('Y = 89 + 6*X1 + 2.99*X1**2 + exp(X2)')

-- TD_LINEAR_REGR / TD_MULTIVAR_REGR: estimated coefficients (math functions rejected, each Xn once only)
FORMULA('Y = B0 + B1*X1')
FORMULA('Y = B0 + B1*X1 + B2*X2')
```

---

## Operator Precedence

Evaluation order (highest to lowest precedence):

| Precedence | Operators |
|------------|-----------|
| 1 (highest) | Exponentiation `**` (so `-X1**2` means `-(X1**2)`, not `(-X1)**2`) |
| 2 | Unary `+` and unary `-` |
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
| `SIGN(x)` | Sign of x: −1, 0, or 1 (formula returns 0 for SIGN(0); Teradata SQL `SIGN` on a FLOAT zero may return 1 — do not validate formula results against SQL for this edge case) |
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
