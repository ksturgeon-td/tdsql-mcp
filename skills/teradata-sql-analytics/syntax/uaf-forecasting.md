# Teradata UAF — Forecasting Functions

Forecasting and time series similarity functions. All use the standard `EXECUTE FUNCTION INTO [VOLATILE] ART(name)` execution pattern unless noted.

> **Read `uaf-concepts` first** for SERIES_SPEC, ART_SPEC, the execution pattern, and ART layer retrieval.

---

## TD_ARIMAFORECAST

Generates out-of-sample forecasts from a fitted ARIMA model. Consumes the ART produced by TD_ARIMAESTIMATE (with FIT_PERCENTAGE(100)) or TD_ARIMAVALIDATE.

> **Input is ART_SPEC only** — no SERIES_SPEC. Use TABLE_NAME only; do not specify LAYER or PAYLOAD.
>
> **Canonical pipeline:** TD_ARIMAESTIMATE → TD_ARIMAVALIDATE → TD_ARIMAFORECAST (manual ARIMA). For AUTOARIMA: TD_AUTOARIMA → TD_ARIMAFORECAST directly — TD_ARIMAVALIDATE errors on AUTOARIMA output.

```sql
-- Using output of TD_ARIMAVALIDATE (recommended for manual ARIMA)
EXECUTE FUNCTION INTO VOLATILE ART(forecast_art)
TD_ARIMAFORECAST(
    ART_SPEC(TABLE_NAME(arima_val)),
    FUNC_PARAMS(
        FORECAST_PERIODS(12),
        PREDICTION_INTERVALS(BOTH)        -- NONE | 80 | 95 | BOTH; default BOTH
    )
);

SELECT * FROM forecast_art;
-- Returns: series-id, ROW_I, FORECAST_VALUE, LO_80, HI_80, LO_95, HI_95
```

> **FIT_PERCENTAGE constraint:** If using TD_ARIMAESTIMATE output directly (skipping TD_ARIMAVALIDATE), the estimate ART must have been created with FIT_PERCENTAGE(100). Otherwise use TD_ARIMAVALIDATE as the intermediate step.

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FORECAST_PERIODS` | Yes | Number of future periods to forecast (integer) |
| `PREDICTION_INTERVALS` | No | Confidence bands: `NONE`, `80`, `95`, or `BOTH` (default `BOTH`) |

### Output schema (ARTPRIMARY — single layer)

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from the source series SERIES_ID |
| `ROW_I` | BIGINT | Integer index for each forecast period |
| `FORECAST_VALUE` | FLOAT | Forecasted value |
| `LO_80` | FLOAT | Lower bound of 80% prediction interval |
| `HI_80` | FLOAT | Upper bound of 80% prediction interval |
| `LO_95` | FLOAT | Lower bound of 95% prediction interval |
| `HI_95` | FLOAT | Upper bound of 95% prediction interval |

> ARTPRIMARY contains **only forecast rows** — no historical observed values. To see both the in-sample fit and the forecast in one result, use TD_ARIMAVALIDATE before forecasting (ARTPRIMARY of TD_ARIMAVALIDATE contains fitted values for the historical period).

---

## TD_HOLT_WINTERS_FORECASTER

Triple exponential smoothing with optional seasonality and trend. Handles additive and multiplicative seasonal patterns. Simultaneously fits the model and generates forecasts.

> **REAL series only** — does not accept MULTIVAR_REAL or complex content types.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(hw_art)
TD_HOLT_WINTERS_FORECASTER(
    SERIES_SPEC(
        TABLE_NAME(sales_ts),
        SERIES_ID(store_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        FORECAST_PERIODS(12),
        MODEL(ADDITIVE),                          -- required: ADDITIVE | MULTIPLICATIVE
        SEASONAL_PERIODS(4),                      -- number of periods per season
        PREDICTION_INTERVALS(BOTH),               -- NONE | 80 | 95 | BOTH; default BOTH
        FIT_METRICS(1),
        SELECTION_METRICS(1),
        RESIDUALS(1)
    ),
    OUTPUT_FMT(INDEX_STYLE(NUMERICAL_SEQUENCE))   -- default NUMERICAL_SEQUENCE
);

-- Primary results (historical fit + forecast)
SELECT * FROM hw_art;

-- Retrieve smoothing parameters and fit quality
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(hw_art), LAYER(ARTFITMETADATA))
);

-- Retrieve model selection criteria
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(hw_art), LAYER(ARTSELMETRICS))
);

-- Retrieve residuals with component decomposition
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(hw_art), LAYER(ARTFITRESIDUALS))
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FORECAST_PERIODS` | Yes | Number of future periods to forecast |
| `MODEL` | Yes | Seasonal component type: `ADDITIVE` (default) or `MULTIPLICATIVE`; trend is always additive |
| `ALPHA` | No | Level smoothing factor (0–1); estimated from data if omitted |
| `BETA` | No | Trend smoothing factor (0–1); estimated from data if omitted |
| `GAMMA` | No | Seasonal smoothing factor (0–1); estimated from data if omitted; only applies when `SEASONAL_PERIODS > 1` |
| `SEASONAL_PERIODS` | No | Number of periods in one seasonal cycle; must be > 1 if GAMMA is specified |
| `INIT(LEVEL_0, TREND_0, SEASON_0(...))` | No | Initial state values; `SEASON_0(float, float, ...)` requires SEASONAL_PERIODS |
| `PREDICTION_INTERVALS` | No | `NONE`, `80`, `95`, or `BOTH` (default `BOTH`) |
| `FIT_METRICS` | No | `1` = generate ARTFITMETADATA layer; default `0` |
| `SELECTION_METRICS` | No | `1` = generate ARTSELMETRICS layer; default `0` |
| `RESIDUALS` | No | `1` = generate ARTFITRESIDUALS layer; default `0` |
| `FIT_PERCENTAGE` | No | Percent of series used for fitting (default `100`) |

> For single exponential smoothing (level only, no trend or seasonality), use TD_SIMPLEEXP instead.

### Output layers

**ARTPRIMARY** — historical fit and forecast values:

| Column | Description |
|--------|-------------|
| `OBSERVED_VALUE` | Historical values; NULL for forecast rows |
| `FORECAST_VALUE` | Fitted (in-sample) and forecast (out-of-sample) values |
| `LO_80`, `HI_80` | 80% prediction interval |
| `LO_95`, `HI_95` | 95% prediction interval |

**ARTFITMETADATA** (requires `FIT_METRICS(1)`) — model parameters and fit quality:

| Column | Description |
|--------|-------------|
| `R_SQUARE` | R² goodness-of-fit |
| `ALPHA`, `BETA`, `GAMMA` | Smoothing parameters used (estimated or supplied) |
| `ME`, `MAE`, `MSE`, `MAPE` | Error metrics |
| `FSTAT_CALC`, `NULL_HYPOTH` | F-statistic and hypothesis test result |

**ARTSELMETRICS** (requires `SELECTION_METRICS(1)`) — model selection criteria:

| Column | Description |
|--------|-------------|
| `AIC`, `SBIC`, `HQIC` | Information criteria |
| `MLR`, `MSE` | Maximum likelihood ratio and mean squared error |

**ARTFITRESIDUALS** (requires `RESIDUALS(1)`) — in-sample residuals with decomposition:

| Column | Description |
|--------|-------------|
| `ACTUAL_VALUE` | Original observed values |
| `CALC_LEVEL`, `CALC_TREND`, `CALC_SEASONAL` | Decomposed model components |
| `CALC_VALUE` | Model-fitted value |
| `RESIDUAL` | Difference between ACTUAL_VALUE and CALC_VALUE |

---

## TD_MAMEAN

Flat forecaster using moving average, mean, or naive (random walk) algorithm. All forecast periods beyond the last observation receive the same forecast value. Three-layer ART.

> **Flat forecaster:** the forecast for any period beyond t+1 equals the forecast for t+1. Suitable for short-horizon forecasts of stationary series with no trend or seasonality.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(mamean_art)
TD_MAMEAN(
    SERIES_SPEC(
        TABLE_NAME(orders_ts),
        SERIES_ID(store_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        FORECAST_PERIODS(8),
        ALGORITHM(MA),                          -- MA | MEAN | NAIVE
        K_ORDER(3),                             -- required for ALGORITHM(MA): window size
        PREDICTION_INTERVALS(BOTH),             -- NONE | 80 | 95 | BOTH; default BOTH
        FIT_METRICS(1),
        RESIDUALS(1)
    )
    -- No INPUT_FMT or OUTPUT_FMT options
);

SELECT * FROM mamean_art;

EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(mamean_art), LAYER(ARTFITRESIDUALS))
);

EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(mamean_art), LAYER(ARTFITMETADATA))
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FORECAST_PERIODS` | Yes | Number of future periods to forecast (1–32000) |
| `ALGORITHM` | Yes | `MA` (moving average), `MEAN` (overall mean), `NAIVE` (random walk — last observed value) |
| `K_ORDER` | If MA | Window size for moving average (1–32000); required when ALGORITHM(MA), ignored otherwise |
| `PREDICTION_INTERVALS` | No | `NONE`, `80`, `95`, or `BOTH` (default `BOTH`) |
| `FIT_METRICS` | No | `1` = generate ARTFITMETADATA layer; default `0` |
| `RESIDUALS` | No | `1` = generate ARTFITRESIDUALS layer; default `0` |

### Output layers

**ARTPRIMARY:**

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES` | Number of historical sample points used |
| `OBSERVED_VALUE` | Historical values; NULL for forecast rows |
| `FORECAST_VALUE` | Fitted (in-sample) and forecast values |
| `LO_80`, `HI_80`, `LO_95`, `HI_95` | Prediction intervals |

**ARTFITRESIDUALS** (requires `RESIDUALS(1)`):

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES` | Number of sample points |
| `ACTUAL_VALUE`, `CALC_VALUE`, `RESIDUAL` | Per-row residuals |

**ARTFITMETADATA** (requires `FIT_METRICS(1)`):

| Column | Description |
|--------|-------------|
| `VAR_COUNT`, `R_SQUARE`, `R_ADJ_SQUARE` | Model structure and fit quality |
| `STD_ERROR`, `STD_ERROR_DF` | Standard error and degrees of freedom |
| `ME`, `MSE`, `MAE`, `MPE`, `MAPE` | Error metrics |
| `FSTAT_CALC`, `P_VALUE`, `NULL_HYPOTH` | Significance test result |
| `NUM_DF`, `DENOM_DF`, `SIGNIFICANCE_LEVEL` | F-test degrees of freedom and significance level |
| `F_CRITICAL`, `F_CRITICAL_P` | Critical value and corresponding p-value |

---

## TD_SIMPLEEXP

Simple (single) exponential smoothing — models level only; no trend or seasonality. Uses a configurable ALPHA smoothing parameter. All forecast periods receive the same value (flat forecaster). Three-layer ART.

> **Use TD_HOLT_WINTERS_FORECASTER** when your series has trend or seasonality.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(simpleexp_art)
TD_SIMPLEEXP(
    SERIES_SPEC(
        TABLE_NAME(inflation_ts),
        SERIES_ID(country_id),
        ROW_AXIS(TIMECODE(year_recorded)),
        PAYLOAD(FIELDS(inflation_rate), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        FORECAST_PERIODS(4),
        FORECAST_STARTING_VALUE('MEAN'),          -- FIRST (default) | MEAN
        ALPHA(0.1),                               -- smoothing factor; default 1.0 (no smoothing)
        PREDICTION_INTERVALS(80),                 -- NONE | 80 | 95 | BOTH; default BOTH
        FIT_METRICS(1),
        RESIDUALS(1)
    ),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))         -- default FLOW_THROUGH
);

SELECT * FROM simpleexp_art;

EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(simpleexp_art), LAYER(ARTFITMETADATA))
);

EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(simpleexp_art), LAYER(ARTFITRESIDUALS))
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FORECAST_PERIODS` | Yes | Number of future periods to forecast (1–32000) |
| `FORECAST_STARTING_VALUE` | No | Initial smoothed value: `FIRST` (default, uses first observation) or `MEAN` (uses series mean) |
| `ALPHA` | No | Smoothing factor (float, 0–1); higher values weight recent observations more heavily; default `1.0` (no smoothing — each in-sample forecast equals the prior observation) |
| `PREDICTION_INTERVALS` | No | `NONE`, `80`, `95`, or `BOTH` (default `BOTH`) |
| `FIT_METRICS` | No | `1` = generate ARTFITMETADATA layer; default `0` |
| `RESIDUALS` | No | `1` = generate ARTFITRESIDUALS layer; default `0` |

### Output layers

**ARTPRIMARY:**

| Column | Description |
|--------|-------------|
| `OBSERVED_VALUE` | Historical values; NULL for forecast rows |
| `FORECAST_VALUE` | Smoothed fitted values and flat forecast |
| `LO_80`, `HI_80`, `LO_95`, `HI_95` | Prediction intervals |

> **OUTPUT_FMT default is FLOW_THROUGH** — ROW_I inherits the original index type and values. Specify `INDEX_STYLE(NUMERICAL_SEQUENCE)` to get integer row numbers.

**ARTFITMETADATA** (requires `FIT_METRICS(1)`):

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `VAR_COUNT` | Sample size and variable count |
| `R_SQUARE`, `R_ADJ_SQUARE` | Fit quality |
| `STD_ERROR`, `STD_ERROR_DF` | Standard error and degrees of freedom |
| `ME`, `MSE`, `MAE`, `MPE`, `MAPE` | Error metrics |
| `FSTAT_CALC`, `P_VALUE`, `NULL_HYPOTH` | Significance test result |
| `NUM_DF`, `DENOM_DF`, `SIGNIFICANCE_LEVEL` | F-test structure |
| `F_CRITICAL`, `F_CRITICAL_P` | Critical value and corresponding p-value |

**ARTFITRESIDUALS** (requires `RESIDUALS(1)`):

| Column | Description |
|--------|-------------|
| `ACTUAL_VALUE`, `CALC_VALUE`, `RESIDUAL` | Per-row residuals |

---

## TD_DTW

Dynamic Time Warping (DTW) distance between two time series. Measures similarity by finding the optimal elastic alignment between series that may be shifted or warped in time. Uses the FastDTW approximation algorithm. Not a forecasting function — use for similarity search, shape comparison, or as a distance metric in clustering.

> **NOT recommended for large datasets.** FastDTW scales better than classic DTW, but remains computationally intensive for long series.
>
> **INPUT_FMT is mandatory** — unlike most UAF functions.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(dtw_art)
TD_DTW(
    SERIES_SPEC(
        TABLE_NAME(series_table),
        SERIES_ID(series_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(value), CONTENT(REAL))
    ) WHERE series_id = 1,

    SERIES_SPEC(
        TABLE_NAME(series_table),
        SERIES_ID(series_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(value), CONTENT(REAL))
    ) WHERE series_id = 2,

    FUNC_PARAMS(
        RADIUS(10),                              -- FastDTW search radius (0–1000); default 10
        DISTANCE(Euclidean),                     -- Euclidean | Manhattan | Binary; default Euclidean
        WARPPATH(0)                              -- 0=distance only; 1=+integer indices; 2=+original ROW_I; 3=all
    ),
    INPUT_FMT(INPUT_MODE(ONE2ONE))               -- mandatory; ONE2ONE | MANY2ONE | MATCH
);

SELECT * FROM dtw_art;
```

> **Series order does not affect DTW distances** — distance between A and B equals distance between B and A.

> TD_DTW can also be called without `INTO ART` for direct result retrieval: `EXECUTE FUNCTION TD_DTW(...);`

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `RADIUS` | No | FastDTW search radius (0–1000); controls the warping window constraint; default `10` |
| `DISTANCE` | No | Distance metric: `Euclidean` (default), `Manhattan`, or `Binary` |
| `WARPPATH` | No | Controls warp path output columns (default `0`): `0` = DTW_DISTANCE only; `1` = + WarpX/WarpY (integer warp path indices); `2` = + WarpX_I/WarpY_I (original ROW_I values); `3` = all warp path columns |

### INPUT_FMT reference

| Mode | Description |
|------|-------------|
| `ONE2ONE` | Both specs identify a single series instance (via WHERE clause) |
| `MANY2ONE` | Primary has many series; secondary WHERE selects one reference series compared against all |
| `MATCH` | Series instances matched by SERIES_ID value; unmatched instances skipped |

> Both series must use the same content type — both `REAL` or both `MULTIVAR_REAL`.

### Output schema (ARTPRIMARY)

| Column | Description |
|--------|-------------|
| `derived-series-identifier` | From the primary (first) SERIES_SPEC |
| `DTW_DISTANCE` | Overall DTW distance between the two series |
| `WarpX`, `WarpY` | Integer warp path indices; present when WARPPATH ≥ 1 |
| `WarpX_I`, `WarpY_I` | Original ROW_I values at each warp path step; present when WARPPATH ≥ 2 |
