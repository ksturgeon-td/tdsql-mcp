# Teradata UAF — Data Preparation and Anomaly Detection

Transforms, combines, and validates series and matrix data before analysis. All functions in this file use the standard `EXECUTE FUNCTION INTO [VOLATILE] ART(name)` execution pattern.

> **Read `uaf-concepts` first** for SERIES_SPEC, MATRIX_SPEC, ART_SPEC, GENSERIES_SPEC syntax and the execution pattern.

---

## TD_RESAMPLE

Transforms an irregular time series into a regular time series by resampling at a fixed interval. Most UAF analysis functions assume discrete (regular) indexing — run TD_RESAMPLE first if your source data has varying intervals.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(resampled)
TD_RESAMPLE(
    SERIES_SPEC(
        TABLE_NAME(ProductionData),
        ROW_AXIS(TIMECODE(MYTIMECODE)),
        SERIES_ID(ProductID),
        PAYLOAD(FIELDS(BEER_SALES), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        TIMECODE(                                          -- use SEQUENCE(...) for integer-indexed series
            START_VALUE(TIMESTAMP '2022-02-28 00:00:00'),
            DURATION(CAL_DAYS(1))
        ),
        INTERPOLATE(LINEAR)                               -- LINEAR | LAG | LEAD | WEIGHTED | SPLINE
    ),
    OUTPUT_FMT(INDEX_STYLE(NUMERICAL_SEQUENCE))          -- default is FLOW_THROUGH (unlike most UAF functions)
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `TIMECODE(START_VALUE(...), DURATION(...))` | Yes (if TIMECODE-indexed) | Starting timestamp and sampling interval; mutually exclusive with SEQUENCE |
| `SEQUENCE(START_VALUE(...), DURATION(...))` | Yes (if SEQUENCE-indexed) | Starting index and step; mutually exclusive with TIMECODE |
| `INTERPOLATE` | Yes | Fill method: `LINEAR`, `LAG` (carry forward), `LEAD` (carry back), `WEIGHTED`, `SPLINE` |
| `WEIGHT(float)` | If WEIGHTED | Weight value for weighted interpolation |
| `SPLINE_PARAMS(METHOD(...), YP1(float), YPN(float))` | If SPLINE | Spline method: `NATURAL`, `CLAMPED`, `NOT_A_KNOT` (default); YP1/YPN = first-derivative boundary conditions for CLAMPED |

> **Default OUTPUT_FMT is FLOW_THROUGH** — not NUMERICAL_SEQUENCE as in most other UAF functions. Specify explicitly if you need integer row indexing.

### Spline example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(resample_art)
TD_RESAMPLE(
    SERIES_SPEC(
        TABLE_NAME(ProductionData),
        SERIES_ID(BuoyID),
        ROW_AXIS(SEQUENCE(TD_SEQ)),
        PAYLOAD(FIELDS(WINE_SALES), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        SEQUENCE(START_VALUE(0), DURATION(1)),
        INTERPOLATE(SPLINE),
        SPLINE_PARAMS(METHOD(CLAMPED), YP1(1.2), YPN(5.2))
    ),
    OUTPUT_FMT(INDEX_STYLE(NUMERICAL_SEQUENCE))
);
```

---

## TD_IQR

Detects anomalies in a series using the interquartile range (IQR) rule. A value is flagged as an outlier if it falls more than 1.5 × IQR below Q1 or above Q3.

Produces a two-layer ART:
- **Primary (ARTPRIMARY):** all input rows with anomaly flag per row
- **Secondary (ARTSTATSDATA):** total outlier count per series

> **Anomaly flag convention:** `1 = normal`, `-1 = anomaly` (inverted from what you might expect)

```sql
-- Run anomaly detection
EXECUTE FUNCTION INTO VOLATILE ART(iqr_results)
TD_IQR(
    SERIES_SPEC(
        TABLE_NAME(REAL_VALUES),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(ID),
        PAYLOAD(FIELDS(VAL), CONTENT(REAL))
    ),
    FUNC_PARAMS(STAT_METRICS(1))     -- 1 = generate secondary ARTSTATSDATA layer; 0 = primary only
);

-- Primary layer: per-row anomaly flags
SELECT * FROM iqr_results;
-- Returns: series_id, ROW_I, VAL, VAL_Anomaly (1=normal, -1=outlier)

-- Secondary layer: outlier count
EXECUTE FUNCTION INTO ART(iqr_stats)
TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(iqr_results), LAYER(ARTSTATSDATA))
);
SELECT * FROM iqr_stats;
-- Returns: series_id, ROW_I, VAL_NUM_OUTLIERS
```

### Output schema

**Primary layer (ARTPRIMARY):**

| Column | Type | Description |
|--------|------|-------------|
| `derived_series_identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Row index |
| `Payload_n` | Varies | Original payload values passed through |
| `Payload_n_Anomaly` | INTEGER | `1` = normal; `-1` = anomaly |

**Secondary layer (ARTSTATSDATA):**

| Column | Type | Description |
|--------|------|-------------|
| `Payload_n_NUM_OUTLIERS` | INTEGER | Total count of anomalies in the series |

---

## TD_BINARYSERIESOP

Performs point-wise arithmetic (add, subtract, multiply, divide) on two series of equal length. Primary use cases: detrending (subtract a fitted trend series from an observed series), restoring trends before forecasting, and as a building block for DSP pipelines (e.g., frequency-domain convolution via DFFT → BINARYSERIESOP MUL → IDFFT).

The result series always inherits the SERIES_ID of the **primary** (first) input.

```sql
-- Detrend: subtract smoothed trend from observed series (ONE2ONE)
EXECUTE FUNCTION COLUMNS(OUT_Magnitude AS Magnitude) INTO VOLATILE ART(DETREND_STOCK)
TD_BINARYSERIESOP(
    SERIES_SPEC(
        TABLE_NAME(StockDataSet),
        SERIES_ID(DataSetID),
        ROW_AXIS(SEQUENCE(SeqNo)),
        PAYLOAD(FIELDS(Magnitude), CONTENT(REAL))
    ) WHERE DataSetID=556 AND SeqNo BETWEEN 3 AND 50,

    SERIES_SPEC(
        TABLE_NAME(SMOOTH_SERIES),
        SERIES_ID(DataSetID),
        ROW_AXIS(SEQUENCE(ROW_I)),
        PAYLOAD(FIELDS(Magnitude), CONTENT(REAL))
    ) WHERE DataSetID=556 AND ROW_I BETWEEN 2 AND 49,

    FUNC_PARAMS(MATHOP(SUB)),
    INPUT_FMT(INPUT_MODE(ONE2ONE))
);
```

> **COLUMNS() renaming:** `EXECUTE FUNCTION COLUMNS(OUT_col AS alias)` renames output columns before writing to the ART. Output payload columns are prefixed `OUT_` by default.

### FUNC_PARAMS and INPUT_FMT reference

| Parameter | Options | Description |
|-----------|---------|-------------|
| `MATHOP` | `SUB`, `ADD`, `MUL`, `DIV` | Operation: secondary is subtracted from / added to / multiplied by / divided into primary |
| `INPUT_MODE` | `ONE2ONE` | Both specs include a WHERE clause identifying a single series instance |
| | `MANY2ONE` | Primary has many series; secondary WHERE clause identifies one — reused for each primary instance |
| | `MATCH` | Series instances are matched by SERIES_ID value; unmatched instances are skipped |

> **Content type rule:** both inputs must be of the same high-level classification (both real, both complex, or both amplitude-phase). Univariate + multivariate combinations are supported — the univariate is reused to match the multivariate's width.

### DSP convolution pipeline pattern

```sql
-- Frequency-domain convolution using BINARYSERIESOP as the building block:
-- Step 1: FFT of both series
EXECUTE FUNCTION INTO VOLATILE ART(dfft1) TD_DFFT(SERIES_SPEC(TABLE_NAME(series1),...), ...);
EXECUTE FUNCTION INTO VOLATILE ART(dfft2) TD_DFFT(SERIES_SPEC(TABLE_NAME(series2),...), ...);

-- Step 2: Point-wise multiply in frequency domain
EXECUTE FUNCTION INTO VOLATILE ART(freq_product)
TD_BINARYSERIESOP(
    SERIES_SPEC(TABLE_NAME(dfft1),...),
    SERIES_SPEC(TABLE_NAME(dfft2),...),
    FUNC_PARAMS(MATHOP(MUL)),
    INPUT_FMT(INPUT_MODE(ONE2ONE))
);

-- Step 3: Inverse FFT to get convolved result
EXECUTE FUNCTION INTO VOLATILE ART(convolved) TD_IDFFT(ART_SPEC(TABLE_NAME(freq_product)), ...);
```

---

## TD_BINARYMATRIXOP

Performs element-wise arithmetic on two matrices of identical dimensions. The matrix equivalent of TD_BINARYSERIESOP — same MATHOP, INPUT_MODE, and content type rules apply.

```sql
-- Element-wise addition (MANY2ONE: all primary matrices vs single secondary)
EXECUTE FUNCTION INTO VOLATILE ART(MATHEXAMPLE)
TD_BINARYMATRIXOP(
    MATRIX_SPEC(
        TABLE_NAME(BINARYM_COMPLEX_LEFT),
        ROW_AXIS(SEQUENCE(SEQ)),
        COLUMN_AXIS(SEQUENCE(TICK)),
        MATRIX_ID(ID),
        PAYLOAD(FIELDS(REAL_VAL, IMAGINARY_VAL), CONTENT(COMPLEX))
    ),
    MATRIX_SPEC(
        TABLE_NAME(BINARYM_COMPLEX_RIGHT),
        ROW_AXIS(SEQUENCE(SEQ)),
        COLUMN_AXIS(SEQUENCE(TICK)),
        MATRIX_ID(ID),
        PAYLOAD(FIELDS(REAL_VAL, IMAGINARY_VAL), CONTENT(COMPLEX))
    ) WHERE ID=1,
    FUNC_PARAMS(MATHOP(ADD)),
    INPUT_FMT(INPUT_MODE(MANY2ONE))
);

SELECT * FROM MATHEXAMPLE;
```

> Same MATHOP options (SUB/ADD/MUL/DIV), same INPUT_MODE options (ONE2ONE/MANY2ONE/MATCH), same content type rules as TD_BINARYSERIESOP. Result inherits MATRIX_ID from the primary matrix.

---

## TD_MATRIXMULTIPLY

Performs matrix multiplication (dot product) of two matrices. The number of columns in the primary matrix must equal the number of rows in the secondary matrix. INPUT_FMT is mandatory.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(MatrixProduct)
TD_MATRIXMULTIPLY(
    MATRIX_SPEC(
        TABLE_NAME(Mtx1),
        MATRIX_ID(BuoyID),
        ROW_AXIS(SEQUENCE(row_I)),
        COLUMN_AXIS(SEQUENCE(column_I)),
        PAYLOAD(FIELDS(speed1), CONTENT(REAL))
    ) WHERE BUOYID = 35,
    MATRIX_SPEC(
        TABLE_NAME(Mtx2),
        MATRIX_ID(BuoyID),
        ROW_AXIS(SEQUENCE(row_I)),
        COLUMN_AXIS(SEQUENCE(column_I)),
        PAYLOAD(FIELDS(speed2), CONTENT(REAL))
    ) WHERE BUOYID = 35,
    INPUT_FMT(INPUT_MODE(ONE2ONE))    -- mandatory; same ONE2ONE | MANY2ONE | MATCH options
);

SELECT * FROM MatrixProduct;
-- Returns: BUOYID, ROW_I, COLUMN_I, speed1 (output column named from primary payload)
```

> Result dimensions: rows = primary matrix rows, columns = secondary matrix columns. Output payload column inherits the primary matrix's payload field name.

---

## TD_GENSERIES4FORMULA

Applies a mathematical formula to generate a new time series. The formula is expressed as `Y = f(X1, X2, ...)` where X1, X2, etc. are the payload fields of the input series.

Common workflow: fit a trend with TD_LINEAR_REGR, extract coefficients, build a FORMULA string from those coefficients, generate the trend series with TD_GENSERIES4FORMULA, then subtract it from the original with TD_BINARYSERIESOP.

```sql
-- Generate a series by applying a formula (FLOW_THROUGH preserves original timestamps)
EXECUTE FUNCTION INTO VOLATILE ART(GEN_SERIES)
TD_GENSERIES4FORMULA(
    SERIES_SPEC(
        TABLE_NAME(ProductionData),
        ROW_AXIS(TIMECODE(MYTIMECODE)),
        SERIES_ID(ProductID),
        PAYLOAD(FIELDS(BEER_SALES), CONTENT(REAL))
    ),
    FUNC_PARAMS(FORMULA('Y = 2.0*X1 + SIN(X1)')),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
```

> See `uaf-formula-rules` for the full formula syntax — supported operators, functions (SIN, COS, EXP, LOG, POW, etc.), and variable naming conventions (X1, X2... for payload fields).

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FORMULA('Y = expression')` | Yes | Mathematical expression; `X1`, `X2`, ... reference payload fields in order |
| `ESTIMATE_MODE(0\|1)` | No | `1` = include input parameters alongside results; `0` = results only (default) |

> If GENSERIES_SPEC is used instead of SERIES_SPEC, the formula may reference only one explanatory variable (X1), and the function assigns the generated start value to it.

### Output schema

| Column | Description |
|--------|-------------|
| `derived-series-identifier` | Inherited from SERIES_ID |
| `ROW_I` | Integer index (NUMERICAL_SEQUENCE) or original timestamp (FLOW_THROUGH) |
| `ESTIMATE_MODE columns` | Input parameters, present only when ESTIMATE_MODE(1) |
| `MAGNITUDE` | Generated series values |
