# Teradata UAF — Concepts and Input Specifications

The Unbounded Array Framework (UAF) is a set of native Teradata table operators for **time series analysis, digital signal processing, and spatial analytics**. UAF functions operate on series (1D arrays), matrices (2D arrays), and Analytic Result Tables (ARTs) — not on ordinary row-oriented tables.

> **When to use UAF:** time series forecasting, ARIMA modeling, seasonal decomposition, regression on ordered sequences, Fourier transforms, digital filtering, image processing, spatial tracking. For cross-sectional ML, use the standard `ml-functions` and `data-prep` topics instead.

---

## Execution Pattern

Most UAF functions write results to an **Analytic Result Table (ART)** using the `EXECUTE FUNCTION INTO ART` wrapper. A small number of utility functions (TD_ISFINITE, TD_ISINF, TD_ISNAN, TD_SINFO, TD_MINFO) are called as scalar functions or normal table operators — these are noted in the utility section.

### Standard call form

```sql
EXECUTE FUNCTION INTO [VOLATILE] ART(art_name)
TD_FUNCTION_NAME(
    SERIES_SPEC(...) | MATRIX_SPEC(...) | ART_SPEC(...) | GENSERIES_SPEC(...),
    FUNC_PARAMS(...),
    [OUTPUT_FMT(...)]
);
```

- `INTO ART(name)` — creates a permanent ART table
- `INTO VOLATILE ART(name)` — creates a session-scoped ART; dropped automatically at session end; slightly faster than permanent

### Retrieve primary results

```sql
-- Direct SELECT (works for single-layer or ARTPRIMARY)
SELECT * FROM art_name;

-- Via TD_EXTRACT_RESULTS (any layer)
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(art_name), LAYER(ARTPRIMARY))
);
```

### Rename output columns before writing to ART

Use the optional `COLUMNS(...)` clause to rename output columns in the same statement:

```sql
EXECUTE FUNCTION COLUMNS(OUT_Magnitude AS Magnitude) INTO VOLATILE ART(result_art)
TD_BINARYSERIESOP(...);
-- OUT_Magnitude is stored as Magnitude in result_art
```

### Chain ART outputs as inputs

Results from one UAF function feed into the next via `ART_SPEC`. This is the standard pattern for multi-step pipelines:

```sql
-- Step 1: estimate ARIMA coefficients
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(TABLE_NAME(sales_ts), SERIES_ID(store_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))),
    FUNC_PARAMS(NONSEASONAL(MODEL_ORDER(1,0,1)),
        FIT_PERCENTAGE(70), FIT_METRICS(1), RESIDUALS(1))
);

-- Step 2: validate in-sample fit (takes ART from step 1)
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1))
);

-- Step 3: forecast (takes validated ART)
EXECUTE FUNCTION INTO VOLATILE ART(arima_fcst)
TD_ARIMAFORECAST(
    ART_SPEC(TABLE_NAME(arima_val)),
    FUNC_PARAMS(FORECAST_PERIODS(7))
);

-- Step 4: retrieve forecast results
SELECT * FROM arima_fcst;
```

---

## ART Layers

A multi-layer ART stores several result sets under one name. ARTPRIMARY can be queried with SELECT; auxiliary layers require TD_EXTRACT_RESULTS.

| Layer | Contents |
|-------|----------|
| `ARTPRIMARY` | Primary function results |
| `ARTFITRESIDUALS` | Residual series from fit |
| `ARTFITMETADATA` | Goodness-of-fit metrics |
| `ARTMODEL` | Validation model context |
| `ARTVALDATA` | Internal validation data |
| `ARTCPDATA` | Cumulative periodogram data |
| `ARTMETADATA` | Normalization metadata |
| `ARTSELMETRICS` | Model selection metrics |
| `ARTSTATSDATA` | Aggregate statistics (e.g., outlier counts from TD_IQR) |

### Which functions produce multi-layer ARTs

| Function | Layers |
|----------|--------|
| `TD_LINEAR_REGR` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS |
| `TD_MULTIVAR_REGR` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS |
| `TD_ARIMAESTIMATE` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS, ARTMODEL, ARTVALDATA |
| `TD_ARIMAVALIDATE` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS, ARTMODEL |
| `TD_SEASONALNORMALIZE` | ARTPRIMARY, ARTMETADATA |
| `TD_CUMUL_PERIODOGRAM` | ARTPRIMARY, ARTCPDATA |
| `TD_MAMEAN` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS |
| `TD_SIMPLEEXP` | ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS |
| `TD_HOLT_WINTERS_FORECASTER` | ARTPRIMARY, ARTFITMETADATA, ARTSELMETRICS, ARTFITRESIDUALS |
| `TD_IQR` | ARTPRIMARY, ARTSTATSDATA |

---

## TD_EXTRACT_RESULTS

Retrieves any layer from a multi-layer ART.

```sql
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(
        TABLE_NAME([database.] art_name),
        LAYER(layer_name)
    )
);
```

### Examples

```sql
-- Retrieve goodness-of-fit metrics from a regression ART
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(lr_age_height_art), LAYER(ARTFITMETADATA))
);

-- Retrieve residuals
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(lr_age_height_art), LAYER(ARTFITRESIDUALS))
);
```

---

## Input Specifications

UAF functions accept four input types. The appropriate spec type depends on the function and the shape of the data.

| Spec type | Data shape | Typical use |
|-----------|-----------|-------------|
| `SERIES_SPEC` | 1D array (one value per index) | Time series, signals |
| `MATRIX_SPEC` | 2D array (rows × columns) | Correlation matrices, images |
| `ART_SPEC` | Reference to an existing ART | Chaining function outputs |
| `GENSERIES_SPEC` | Programmatically generated series | Synthetic test signals |

---

## SERIES_SPEC

References a 1D series in any Teradata table, view, derived table, or ART layer.

```sql
SERIES_SPEC(
    TABLE_NAME([database.] table_name),
    ROW_AXIS({TIMECODE | SEQUENCE}(field)),
    SERIES_ID(field [, field ...]),
    [ID_SEQUENCE(json_name_value_pairs),]
    PAYLOAD(
        FIELDS(field [, field ...]),
        CONTENT({REAL | COMPLEX | AMPL_PHASE | AMPL_PHASE_RADIANS |
                 AMPL_PHASE_DEGREES | MULTIVAR_REAL | MULTIVAR_COMPLEX |
                 MULTIVAR_ANYTYPE | MULTIVAR_AMPL_PHASE |
                 MULTIVAR_AMPL_PHASE_RADIANS | MULTIVAR_AMPL_PHASE_DEGREES})
    ),
    [LAYER(layer_name),]
    [INTERVAL({time_duration [, time_zero] | integer_or_float [, seq_zero]})]
)
```

### SERIES_SPEC parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `TABLE_NAME` | Yes | Source table, view, derived table, or ART |
| `ROW_AXIS` | Yes | Index type (`TIMECODE` for date/timestamp; `SEQUENCE` for integer/float) and the index field |
| `SERIES_ID` | Yes | One or more fields that identify each distinct series (wavelet group key) |
| `PAYLOAD` | Yes | The data field(s) and their numeric type |
| `ID_SEQUENCE` | No | JSON name-value pairs selecting specific series instances; used only with TD_PLOT |
| `LAYER` | No | ART layer to read from; required when TABLE_NAME references an ART (omit for ARTPRIMARY) |
| `INTERVAL` | No | Divides series into consecutive numbered intervals along the row axis |

### PAYLOAD CONTENT types

| Type | Description |
|------|-------------|
| `REAL` | Standard floating-point decimal |
| `COMPLEX` | Complex number (real + imaginary pair) |
| `AMPL_PHASE` | Complex in polar form (amplitude + phase, any unit) |
| `AMPL_PHASE_RADIANS` | Complex in polar form, phase in radians |
| `AMPL_PHASE_DEGREES` | Complex in polar form, phase in degrees |
| `MULTIVAR_REAL` | Vector of real numbers (multivariate) |
| `MULTIVAR_COMPLEX` | Vector of complex numbers |
| `MULTIVAR_AMPL_PHASE` | Vector of complex numbers in polar form |
| `MULTIVAR_AMPL_PHASE_RADIANS` | Vector of complex numbers, phase in radians |
| `MULTIVAR_AMPL_PHASE_DEGREES` | Vector of complex numbers, phase in degrees |
| `MULTIVAR_ANYTYPE` | Vector of mixed types |

### INTERVAL time-duration values
`CAL_YEARS`, `CAL_MONTHS`, `CAL_DAYS`, `WEEKS`, `DAYS`, `HOURS`, `MINUTES`, `SECONDS`, `MILLISECONDS`, `MICROSECONDS`

---

## MATRIX_SPEC

References a 2D matrix in any Teradata table, view, derived table, or ART layer.

```sql
MATRIX_SPEC(
    TABLE_NAME([database.] table_name),
    ROW_AXIS({TIMECODE | SEQUENCE}(field)),
    COLUMN_AXIS({TIMECODE | SEQUENCE}(field)),
    MATRIX_ID(field [, field ...]),
    [ID_SEQUENCE(json_name_value_pairs),]
    PAYLOAD(
        FIELDS(field [, field ...]),
        CONTENT({REAL | COMPLEX | AMPL_PHASE | AMPL_PHASE_RADIANS |
                 AMPL_PHASE_DEGREES | MULTIVAR_REAL | MULTIVAR_COMPLEX |
                 MULTIVAR_ANYTYPE | MULTIVAR_AMPL_PHASE |
                 MULTIVAR_AMPL_PHASE_RADIANS | MULTIVAR_AMPL_PHASE_DEGREES})
    ),
    [LAYER(layer_name)]
)
```

### MATRIX_SPEC parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `TABLE_NAME` | Yes | Source table, view, derived table, or ART |
| `ROW_AXIS` | Yes | Row index type and field |
| `COLUMN_AXIS` | Yes | Column index type and field |
| `MATRIX_ID` | Yes | One or more fields identifying each distinct matrix |
| `PAYLOAD` | Yes | Data fields and their numeric type (same CONTENT types as SERIES_SPEC) |
| `ID_SEQUENCE` | No | JSON name-value pairs for TD_PLOT |
| `LAYER` | No | ART layer; required when TABLE_NAME references an ART |

> **Row-major vs column-major:** row-major matrices group by MATRIX_ID + ROW_AXIS and order by COLUMN_AXIS; column-major matrices group by MATRIX_ID + COLUMN_AXIS and order by ROW_AXIS.

---

## ART_SPEC

Simplified reference to an existing ART — the primary way to chain UAF function outputs. Not all functions accept ART_SPEC input; check the individual function's syntax.

```sql
ART_SPEC(
    TABLE_NAME([database.] art_name),
    [ID_SEQUENCE(json_name_value_pairs),]
    [PAYLOAD(
        FIELDS(field [, field ...]),
        CONTENT({...})
    ),]
    [LAYER(layer_name)]
)
```

### ART_SPEC parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `TABLE_NAME` | Yes | An ART produced by a prior UAF function call |
| `LAYER` | Conditional | Required by some functions; specifies which ART layer to pass in |
| `PAYLOAD` | Conditional | Required by some functions; see individual function docs |
| `ID_SEQUENCE` | No | JSON name-value pairs for TD_PLOT |

> If `LAYER` is omitted, the entire ART is passed. The default data layer is ARTPRIMARY.

### Functions that accept ART_SPEC input

See the ART Specifications section — the full compatibility table maps each accepting function to the ART producer functions whose output it can consume.

---

## GENSERIES_SPEC

Passes a programmatically generated series directly to a UAF function — no pre-existing table required. Useful for synthetic test signals and formula-driven inputs. Can only be used with functions that accept a single series as input.

Generated series are indexed starting at 0, incrementing by 1.

```sql
GENSERIES_SPEC(
    INSTANCE_NAMES(json_name_value_pairs),
    DT(datatype [, datatype ...]),
    GEN_PAYLOAD(
        start_value,
        offset_value,
        num_entries
    )
)
```

### GENSERIES_SPEC parameters

| Parameter | Description |
|-----------|-------------|
| `INSTANCE_NAMES` | JSON object — series identifier column names and their values |
| `DT` | Data types of the identifier columns (any Teradata type except LOB and UDT) |
| `GEN_PAYLOAD` | `start_value` (FLOAT), `offset_value` (FLOAT), `num_entries` (INTEGER) — defines an arithmetic sequence of payload values |
