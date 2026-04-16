# Teradata UAF — Estimation and Regression

Stationarity transforms, model identification, ARIMA estimation and validation, and regression on ordered sequences. All functions use the standard `EXECUTE FUNCTION INTO [VOLATILE] ART(name)` execution pattern.

> **Read `uaf-concepts` first** for SERIES_SPEC, ART_SPEC, the execution pattern, and ART layers.

---

## ARIMA Modeling Workflow

### Which approach to use

**Use TD_AUTOARIMA when:**
- All input series share the same type (all seasonal at the same period, or all non-seasonal)
- Automatic model selection is acceptable — no need to compare candidate models manually
- Exploration or prototyping phase

**Use TD_ARIMAESTIMATE when:**
- You need explicit control over model order (p, d, q, P, D, Q)
- Input mixes series types or seasonal periods (TD_AUTOARIMA errors on mixed input)
- You want TD_ARIMAVALIDATE diagnostics to rigorously compare candidate models
- Production workflows where model choice must be auditable

### Manual ARIMA pipeline (non-seasonal series)

```sql
-- 1. Check for unit roots — see uaf-diagnostics for TD_DICKEY_FULLER
EXECUTE FUNCTION INTO VOLATILE ART(df_result)
TD_DICKEY_FULLER(SERIES_SPEC(TABLE_NAME(sales_ts), ...), ...);

-- 2. Difference to eliminate unit roots
EXECUTE FUNCTION INTO VOLATILE ART(diff_series)
TD_DIFF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(LAG(1), DIFFERENCES(1), SEASONAL_MULTIPLIER(0))
);

-- 3. Verify stationarity — re-run TD_DICKEY_FULLER on diff_series

-- 4. Identify AR/MA order using ACF and PACF
EXECUTE FUNCTION INTO VOLATILE ART(acf_art)
TD_ACF(SERIES_SPEC(TABLE_NAME(diff_series), ...), FUNC_PARAMS(MAXLAGS(20), ALPHA(0.05)));
EXECUTE FUNCTION INTO VOLATILE ART(pacf_art)
TD_PACF(SERIES_SPEC(TABLE_NAME(diff_series), ...), FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), ALPHA(0.05)));

-- 5. Estimate model (FIT_PERCENTAGE < 100 reserves holdout for validation)
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))),
    FUNC_PARAMS(
        NONSEASONAL(MODEL_ORDER(1,1,1)),
        ALGORITHM(MLE), CONSTANT(1),
        FIT_PERCENTAGE(80), FIT_METRICS(1), RESIDUALS(1)
    )
);

-- 6. Validate on holdout portion
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1))
);

-- 7. Inspect residuals with diagnostic tests — see uaf-diagnostics
-- (TD_DURBIN_WATSON, TD_PORTMAN, TD_DICKEY_FULLER on residuals)

-- 8. Forecast future periods — see uaf-forecasting
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(arima_val)), FUNC_PARAMS(FORECAST_PERIODS(12)));
SELECT * FROM forecast;
```

### Manual ARIMA pipeline (seasonal series with normalization)

When seasonal patterns create non-stationarity, normalize before modeling and restore scale after forecasting:

```sql
-- 1. Detect unit roots, then normalize to remove seasonal fluctuations
EXECUTE FUNCTION INTO VOLATILE ART(norm_series)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(TIMECODE(sale_date)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),              -- INTERVAL is required
    FUNC_PARAMS(SEASON_CYCLE(CYCLES("CAL_YEARS"), DURATION(1)))
);
-- ARTMETADATA layer stores per-interval mean and SD — needed by TD_UNNORMALIZE

-- 2. Verify stationarity on normalized series; estimate, validate, forecast as above

-- 3. After forecasting, restore original scale
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_UNNORMALIZE(
    SERIES_SPEC(TABLE_NAME(forecasted_norm), ROW_AXIS(TIMECODE(ROW_I)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),              -- must match TD_SEASONALNORMALIZE call
    ART_SPEC(TABLE_NAME(norm_series), LAYER(ARTMETADATA),
             PAYLOAD(FIELDS(MEAN_sales, SD_sales), CONTENT(MULTIVAR_REAL))),
    INPUT_FMT(INPUT_MODE(MATCH)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
```

### Auto ARIMA pipeline

```sql
-- 1. Auto-select best model and estimate
EXECUTE FUNCTION INTO ART(autoarima_art)
TD_AUTOARIMA(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MAX_PQ_NONSEASONAL(3,3), INFOR_CRITERIA(AIC), STEPWISE(0), RESIDUALS(1))
);

-- 2. Inspect selected model order (always generated in ARTICANDORDER layer)
EXECUTE FUNCTION INTO ART(model_order_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(autoarima_art), LAYER(ARTICANDORDER)));
SELECT * FROM model_order_art;   -- MODEL_ORDER: e.g. "ARIMA(1, 1, 3)"

-- 3. Forecast directly — TD_ARIMAVALIDATE is not valid on TD_AUTOARIMA output
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(autoarima_art)), FUNC_PARAMS(FORECAST_PERIODS(12)));
SELECT * FROM forecast;
```

---

## TD_DIFF

Performs non-seasonal differencing, seasonal differencing, or a combination. Used to transform a non-stationary series into a stationary series by removing trends and seasonality.

> **Workflow:** Detect unit roots with `TD_DICKEY_FULLER` (see `uaf-diagnostics`) → apply `TD_DIFF` → verify stationarity with a second `TD_DICKEY_FULLER` call.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(diff_results)
TD_DIFF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(...)) },
    FUNC_PARAMS(
        LAG(integer),
        DIFFERENCES(integer),
        SEASONAL_MULTIPLIER(integer)
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `LAG` | Yes | Zero or positive integer |
| `DIFFERENCES` | Yes | Zero or positive integer |
| `SEASONAL_MULTIPLIER` | Yes | Zero or positive integer — combined with LAG and DIFFERENCES to determine the differencing formula |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | INTEGER | NUMERICAL_SEQUENCE index |
| `OUT_<field>` | FLOAT | Differenced values; one column per payload field |

`REAL` input produces `REAL` output; `MULTIVAR_REAL` input produces `MULTIVAR_REAL` output.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(diff_results)
TD_DIFF(
    SERIES_SPEC(
        TABLE_NAME(ocean_buoys),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(Ocean_Name, BuoyID),
        PAYLOAD(FIELDS(SALINITY), CONTENT(REAL))
    ),
    FUNC_PARAMS(LAG(1), DIFFERENCES(2), SEASONAL_MULTIPLIER(0))
);

SELECT * FROM diff_results;
-- Returns: Ocean_Name, BuoyID, ROW_I, OUT_SALINITY
```

---

## TD_UNDIFF

Reverses a previous `TD_DIFF` operation, reconstructing the original series. Used during the forecasting phase to restore the original scale after modeling on a differenced series.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(undiff_results)
TD_UNDIFF(
    { SERIES_SPEC(differenced_series) | ART_SPEC(TABLE_NAME(...)) },
    [ SERIES_SPEC(original_series), ]             -- required if INITIAL_VALUES not provided
    FUNC_PARAMS(
        LAG(integer),
        DIFFERENCES(integer),
        SEASONAL_MULTIPLIER(integer)
        [, INITIAL_VALUES(float [, float ...]) ]   -- required if secondary SERIES_SPEC not provided
    ),
    INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),  -- required with two inputs
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]
);
```

### Two reconstruction modes

| Mode | Primary input | Initial values source |
|------|--------------|----------------------|
| Two-input | Differenced SERIES_SPEC or ART_SPEC | Secondary SERIES_SPEC referencing original series — function derives initial values |
| One-input | Differenced SERIES_SPEC or ART_SPEC | `INITIAL_VALUES` list: LAG=1 requires 1 value, LAG=2 requires 2 values, etc. |

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `LAG` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `DIFFERENCES` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `SEASONAL_MULTIPLIER` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `INITIAL_VALUES` | Conditional | Required when no secondary SERIES_SPEC is provided |

INPUT_FMT is mandatory when using two inputs. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | INTEGER | Index of result series |
| `OUT_<field>` | REAL | Restored values; one per payload field |

### Example: two-input mode

```sql
EXECUTE FUNCTION INTO VOLATILE ART(undiff_results)
TD_UNDIFF(
    SERIES_SPEC(TABLE_NAME(diff_results), SERIES_ID(BuoyId),
                ROW_AXIS(SEQUENCE(ROW_I)), PAYLOAD(FIELDS(MAG), CONTENT(REAL))),
    SERIES_SPEC(TABLE_NAME(buoy_data), SERIES_ID(BuoyId),
                ROW_AXIS(SEQUENCE(SeqNo)), PAYLOAD(FIELDS(Mag), CONTENT(REAL))),
    FUNC_PARAMS(LAG(1), DIFFERENCES(1), SEASONAL_MULTIPLIER(0)),
    INPUT_FMT(INPUT_MODE(MATCH))
);
```

---

## TD_SEASONALNORMALIZE

Normalizes a time series by dividing it into seasonal cycles and intervals, then averaging and normalizing each interval across all cycles. Produces a stationary series suitable for ARIMA modeling. Normalization formula: `(value − mean) / SD` per interval.

> **`INTERVAL` is required in SERIES_SPEC** — unlike most UAF functions where it is optional. The `ARTMETADATA` layer stores per-interval mean and SD that `TD_UNNORMALIZE` uses to reverse the transform.

> **Workflow:** `TD_DICKEY_FULLER` → `TD_SEASONALNORMALIZE` → `TD_DICKEY_FULLER` (verify) → estimate → validate → forecast → `TD_UNNORMALIZE`

```sql
EXECUTE FUNCTION INTO VOLATILE ART(norm_series)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(
        TABLE_NAME(table_name),
        ROW_AXIS(TIMECODE(timecode_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL)),
        INTERVAL(CAL_MONTHS(1))                    -- required; defines the interval size
    ),
    FUNC_PARAMS(
        SEASON_CYCLE(
            CYCLES("CAL_YEARS"),                   -- time-unit of one seasonal cycle
            DURATION(1)                            -- number of CYCLES units per season
        )
        [, SEASON_INFO({ 0 | 1 | 2 | 3 }) ]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `SEASON_CYCLE` | Yes | Groups CYCLES and DURATION to define the seasonal period |
| `CYCLES` | Yes | Time-unit of one seasonal cycle: `CAL_MONTHS`, `CAL_DAYS`, `WEEKS`, `DAYS`, `HOURS`, `MINUTES`, `SECONDS`, `MILLISECONDS`, `MICROSECONDS` |
| `DURATION` | Yes | Number of CYCLES units per seasonal cycle |
| `SEASON_INFO(0\|1\|2\|3)` | No | Extra columns: 0 = none (default), 1 = SEASON_NO, 2 = CYCLE_NO, 3 = both |

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output: two-layer ART

**Primary (ARTPRIMARY):**

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `SEASON_NO` | BIGINT | Season number within cycle; present when SEASON_INFO is 1 or 3 |
| `CYCLE_NO` | BIGINT | Cycle sequence number; present when SEASON_INFO is 2 or 3 |
| payload field | FLOAT | Normalized values |

**Secondary (ARTMETADATA):**

| Column | Type | Description |
|--------|------|-------------|
| `MEAN_<field>` | FLOAT | Mean for each interval (season) |
| `SD_<field>` | FLOAT | Standard deviation for each interval (season) |

### Example

```sql
-- Normalize store sales: monthly intervals, yearly seasonal cycle
EXECUTE FUNCTION INTO VOLATILE ART(norm_store_sales)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(TABLE_NAME(StoreSales), ROW_AXIS(TIMECODE(TD_TIMECODE)),
                SERIES_ID(StoreID), PAYLOAD(FIELDS(Sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),
    FUNC_PARAMS(SEASON_CYCLE(CYCLES("CAL_YEARS"), DURATION(1)), SEASON_INFO(3)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

-- Retrieve normalization metadata (consumed by TD_UNNORMALIZE)
EXECUTE FUNCTION INTO VOLATILE ART(norm_metadata)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(norm_store_sales), LAYER(ARTMETADATA)));
SELECT * FROM norm_metadata;
-- Returns: StoreID, ROW_I, MEAN_Sales, SD_Sales (one row per interval per series)
```

---

## TD_UNNORMALIZE

Reverses a previous `TD_SEASONALNORMALIZE` operation, restoring the original scale. Used at the end of the forecast pipeline to convert forecasted normalized values back to original units.

> **`INTERVAL` in the primary SERIES_SPEC must match the `INTERVAL` used in the originating `TD_SEASONALNORMALIZE` call.**

> The secondary ART_SPEC requires `LAYER(ARTMETADATA)` and `PAYLOAD` explicitly — unlike typical ART_SPEC usage where these are optional.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(unnorm_results)
TD_UNNORMALIZE(
    SERIES_SPEC(normalized_series, ..., INTERVAL(CAL_MONTHS(1))),  -- INTERVAL must match
    { SERIES_SPEC(metadata_table, ...)
    | ART_SPEC(TABLE_NAME(norm_art),
               LAYER(ARTMETADATA),
               PAYLOAD(FIELDS(MEAN_field, SD_field [, ...]), CONTENT(MULTIVAR_REAL))) },
    [FUNC_PARAMS(FIELDS(integer_list)),]       -- optional; 1-based positions to unnormalize
    INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FIELDS(integer_list)` | No | 1-based field positions to unnormalize; default = all payload fields |

### Output schema

Single-layer ART (ARTPRIMARY only). Output column names are the **original payload field names** — no `OUT_` prefix.

### Example: feeding ARTMETADATA directly from TD_SEASONALNORMALIZE ART

```sql
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_UNNORMALIZE(
    SERIES_SPEC(TABLE_NAME(forecasted_norm), SERIES_ID(StoreID),
                ROW_AXIS(TIMECODE(ROW_I)), PAYLOAD(FIELDS(Sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),
    ART_SPEC(TABLE_NAME(norm_store_sales),
             LAYER(ARTMETADATA),
             PAYLOAD(FIELDS(MEAN_Sales, SD_Sales), CONTENT(MULTIVAR_REAL))),
    INPUT_FMT(INPUT_MODE(MATCH)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

SELECT TOP 18 * FROM final_forecast;
-- Returns: StoreID, ROW_I (original timestamps), Sales (restored original values)
```

---

## TD_POWERTRANSFORM

Applies a power transform equation (log, Box-Cox, square root, etc.) to a series. Used to stabilize variance (heteroscedasticity), linearize exponential trends, or reduce distribution skewness before ARIMA modeling. The same function with `BACK_TRANSFORM(1)` restores the original scale after forecasting.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(trans_series)
TD_POWERTRANSFORM(
    SERIES_SPEC(
        TABLE_NAME(production_data),
        ROW_AXIS(TIMECODE(MYTIMECODE)),
        SERIES_ID(ProductID),
        PAYLOAD(FIELDS(BEER_SALES), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        BACK_TRANSFORM({ 0 | 1 }),    -- 0 = forward transform, 1 = back transform
        P(float),
        B(float),
        LAMBDA(float)
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `BACK_TRANSFORM(0\|1)` | Yes | 0 = forward (default); 1 = back transform |
| `P(float)` | Yes | Power value |
| `B(float)` | Yes | Logarithm base |
| `LAMBDA(float)` | Yes | Box-Cox parameter |

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Transform equation reference

Forward transforms (`BACK_TRANSFORM(0)`):

| Transform | P | B | LAMBDA |
|-----------|---|---|--------|
| Natural log | 0 | 0 | 0 |
| Log base b | 0 | positive | 0 |
| Box-Cox: `(Y^λ − 1) / λ` | 0 | 0 | nonzero |
| Power: `Y^p` | positive | 0 | 0 |
| Negative power: `−Y^p` | negative | 0 | 0 |

Well-known transforms and their P/B/LAMBDA values:

| Transform | P | B | LAMBDA |
|-----------|---|---|--------|
| Square root | 0.5 | 0 | 0 |
| Cube root | 0.333 | 0 | 0 |
| Natural log | 0 | 0 | 0 |
| Negative reciprocal | −1 | 0 | 0 |

Use the same P/B/LAMBDA values for `BACK_TRANSFORM(1)` to reverse the corresponding forward transform.

### Output schema

Single-layer ART (ARTPRIMARY only).

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `MAGNITUDE_<field>` | FLOAT | Transformed values; one per payload field |

### Workflow pattern

```sql
-- 1. Forward transform to stabilize variance
EXECUTE FUNCTION INTO VOLATILE ART(trans_series)
TD_POWERTRANSFORM(SERIES_SPEC(...), FUNC_PARAMS(BACK_TRANSFORM(0), P(0), B(0), LAMBDA(0)));

-- 2. Model and forecast the transformed series

-- 3. Back-transform forecast to original scale
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_POWERTRANSFORM(
    SERIES_SPEC(TABLE_NAME(forecast_art), ...),
    FUNC_PARAMS(BACK_TRANSFORM(1), P(0), B(0), LAMBDA(0))
);
```

---

## TD_SMOOTHMA

Applies a moving average smoothing function to a series, exposing the underlying trend. The smoothed trend series can be modeled directly, or subtracted from the original via `TD_BINARYSERIESOP` to isolate irregular fluctuations for separate modeling.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(ma_results)
TD_SMOOTHMA(
    SERIES_SPEC(
        TABLE_NAME(orders),
        SERIES_ID(OrderID),
        ROW_AXIS(SEQUENCE(SEQ)),
        PAYLOAD(FIELDS(Qty), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        MA({ CUMULATIVE | MEAN | MEDIAN | EXPONENTIAL }),
        [WINDOW(integer),]
        [ONE_SIDED({ 0 | 1 }),]
        [LAMBDA(float),]
        [PAD(float),]
        [WEIGHTS(float [, ...]),]
        [WELL_KNOWN("3MA" | "5MA" | "2x12MA" | "3x3MA" | "3x5MA" |
                    "S15MA" | "S21MA" | "H5MA" | "H9MA" | "H13MA" | "H23MA")]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Used with | Required | Description |
|-----------|-----------|----------|-------------|
| `MA` | All | Yes | Smoothing algorithm |
| `WINDOW` | MEAN, MEDIAN | Yes | Window size; odd = simple MA, even = centered MA |
| `ONE_SIDED(0\|1)` | MEAN | No | 0 = centered (default), 1 = trailing (no centering) |
| `LAMBDA` | EXPONENTIAL | Yes | Weighting decay factor; 0–1; higher = discount older values faster |
| `PAD` | MEAN, MEDIAN | Yes | Fill value for positions before window is filled |
| `WEIGHTS` | MEAN | No | Custom weight list; must sum to 1 and be symmetric; element count sets implied WINDOW; mutually exclusive with WELL_KNOWN |
| `WELL_KNOWN` | MEAN | No | Named weighted MA preset; mutually exclusive with WEIGHTS |

**WELL_KNOWN implied WINDOW values (if WINDOW not specified):**
`3MA` / `3x3MA` / `H5MA` → 5 | `3x5MA` → 7 | `H9MA` → 9 | `2x12MA` / `H13MA` → 13 | `S15MA` → 15 | `S21MA` → 21 | `H23MA` → 23

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output schema

Single-layer ART (ARTPRIMARY only).

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `MAGNITUDE_<field>` | REAL | Smoothed values; one per payload field |

### Examples

```sql
-- Simple MA with WELL_KNOWN preset
EXECUTE FUNCTION INTO VOLATILE ART(ma_results)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(Orders1_12), SERIES_ID(OrderID),
                ROW_AXIS(SEQUENCE(SEQ)), PAYLOAD(FIELDS(Qty1), CONTENT(REAL))),
    FUNC_PARAMS(WINDOW(5), PAD(4.5555), MA(MEAN), WELL_KNOWN("5MA"))
);

-- Exponential smoothing
EXECUTE FUNCTION INTO VOLATILE ART(exp_ma)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(sales_ts), SERIES_ID(store_id),
                ROW_AXIS(SEQUENCE(seq_no)), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MA(EXPONENTIAL), LAMBDA(0.3))
);

-- Two-payload multivariate with trailing (one-sided) window
EXECUTE FUNCTION INTO VOLATILE ART(ma_multi)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(Orders1_12mf), SERIES_ID(OrderID),
                ROW_AXIS(SEQUENCE(SEQ)), PAYLOAD(FIELDS(Qty1, Qty2), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(WINDOW(5), MA(MEAN), ONE_SIDED(1)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
```

---

## TD_ACF

Calculates autocorrelation (or autocovariance) coefficients for a time series at each lag up to MAXLAGS. Used to identify the moving-average (MA) order for ARIMA modeling and to detect non-stationarity.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(acf_results)
TD_ACF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(...)) },
    FUNC_PARAMS(
        [MAXLAGS(integer),]
        [FUNC_TYPE({ 0 | 1 }),]
        [QSTAT({ 0 | 1 }),]
        [ALPHA(float),]
        [DEMEAN({ 0 | 1 })]
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `MAXLAGS` | No | `10*log10(N)` | Maximum number of lags to compute |
| `FUNC_TYPE(0\|1)` | No | 0 | 0 = autocorrelation, 1 = autocovariance |
| `QSTAT(0\|1)` | No | 0 | 1 = add Ljung-Box Q-statistic columns (`QSTATVAL`, `PVALUE`) |
| `ALPHA(float)` | No | — | Confidence interval level (e.g., 0.05 for 95%); adds `CONF_OFF`, `CONF_LOW`, `CONF_HI` |
| `DEMEAN(0\|1)` | No | 1 | 0 = do not subtract mean before computing; **warning:** when `QSTAT(1)` is also set, DEMEAN(0) causes all PVALUE columns to be 0 |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | BIGINT | Lag index |
| `OUT_<field>` | FLOAT | ACF coefficient at each lag; one per payload field |
| `CONF_OFF_<field>` | FLOAT | Bartlett's formula critical value; present only if ALPHA set |
| `CONF_LOW_<field>` | FLOAT | Confidence lower bound; present only if ALPHA set |
| `CONF_HI_<field>` | FLOAT | Confidence upper bound; present only if ALPHA set |
| `QSTATVAL` | FLOAT | Ljung-Box Q-statistic; present only if QSTAT(1) |
| `PVALUE` | FLOAT | Q-statistic p-value; present only if QSTAT(1) |

Input: `REAL` or `MULTIVAR_REAL`. Output matches input dimensionality.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(acf_results)
TD_ACF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MAXLAGS(20), FUNC_TYPE(0), QSTAT(1), ALPHA(0.05), DEMEAN(1))
);

SELECT * FROM acf_results;
-- Returns: store_id, ROW_I (lag), OUT_sales, CONF_OFF_sales, CONF_LOW_sales, CONF_HI_sales,
--          QSTATVAL, PVALUE

-- Rename output columns using COLUMNS() syntax
EXECUTE FUNCTION COLUMNS(OUT_sales AS ACF_Coeff) INTO VOLATILE ART(acf_renamed)
TD_ACF(SERIES_SPEC(...), FUNC_PARAMS(MAXLAGS(20), ALPHA(0.05)));
```

---

## TD_PACF

Calculates partial autocorrelation coefficients at each lag, removing the effects of all intervening lags. Where TD_ACF identifies MA order, TD_PACF identifies the AR order. Can accept raw series data or pre-computed TD_ACF output as input.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(pacf_results)
TD_PACF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(acf_art)) },
    FUNC_PARAMS(
        ALGORITHM({ LEVINSON_DURBIN | OLS }),
        [INPUT_TYPE({ DATA_SERIES | ACF }),]
        [MAXLAGS(integer),]
        [UNBIASED({ 0 | 1 }),]
        [ALPHA(float)]
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `ALGORITHM` | Yes | — | `LEVINSON_DURBIN` or `OLS` |
| `INPUT_TYPE` | No | `DATA_SERIES` | `DATA_SERIES` = raw series input; `ACF` = pre-computed ACF from a TD_ACF ART |
| `MAXLAGS` | No | `10*log10(N)` | Maximum number of lags |
| `UNBIASED(0\|1)` | No | 0 | 0 = Jenkins & Watts denominator; 1 = Box & Jenkins denominator; only valid with `INPUT_TYPE(DATA_SERIES)` |
| `ALPHA(float)` | No | — | Confidence interval level; adds `CONF_OFF`, `CONF_LOW`, `CONF_HI` columns |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | BIGINT | Lag index |
| `OUT_<field>` | FLOAT | PACF coefficient at each lag |
| `CONF_OFF_<field>` | FLOAT | Bartlett's formula critical value; present only if ALPHA set |
| `CONF_LOW_<field>` | FLOAT | Confidence lower bound; present only if ALPHA set |
| `CONF_HI_<field>` | FLOAT | Confidence upper bound; present only if ALPHA set |

### Examples

```sql
-- From raw series
EXECUTE FUNCTION INTO VOLATILE ART(pacf_results)
TD_PACF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), MAXLAGS(10), ALPHA(0.05))
);

-- Chain from TD_ACF output — avoids reprocessing the raw series
EXECUTE FUNCTION INTO VOLATILE ART(pacf_from_acf)
TD_PACF(
    ART_SPEC(TABLE_NAME(acf_results)),
    FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), INPUT_TYPE(ACF), MAXLAGS(10), ALPHA(0.05))
);
```

---

## TD_ARIMAESTIMATE

Estimates the coefficients of an ARIMA model for seasonal and non-seasonal series. Supports the full Box-Jenkins seasonal ARIMA formula. The most complex estimation function in the UAF — outputs up to five ART layers. The resulting ART is consumed by `TD_ARIMAVALIDATE` and `TD_ARIMAFORECAST`.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(                                       -- primary: series to model
        TABLE_NAME(table_name),
        ROW_AXIS(SEQUENCE(seq_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL))
    ),
    [{ SERIES_SPEC(...) | ART_SPEC(...) },]            -- secondary: apply existing model
    FUNC_PARAMS(
        ALGORITHM({ OLE | MLE | MLE_CSS | CSS }),
        CONSTANT({ 0 | 1 }),
        NONSEASONAL(MODEL_ORDER(p, d, q)),
        [SEASONAL(MODEL_ORDER(P, D, Q), PERIOD(n)),]
        [FIT_PERCENTAGE(integer),]
        [COEFF_STATS({ 0 | 1 }),]
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    ),
    [INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),]   -- required only with two inputs
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]  -- ARTFITRESIDUALS and ARTVALDATA only
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `ALGORITHM` | Yes | — | `OLE` (ordinary least estimates), `MLE` (maximum likelihood), `MLE_CSS` (CSS start → MLE), `CSS` (conditional sum-of-squares) |
| `CONSTANT(0\|1)` | Yes | — | 1 = include intercept/constant term |
| `NONSEASONAL(MODEL_ORDER(p,d,q))` | Yes | — | AR order (p), differencing order (d), MA order (q) |
| `SEASONAL(MODEL_ORDER(P,D,Q), PERIOD(n))` | No | — | Seasonal AR (P), differencing (D), MA (Q); periods per season (n) |
| `FIT_PERCENTAGE(integer)` | No | 100 | % of series used for estimation; remainder is holdout for `TD_ARIMAVALIDATE`; must be < 100 to enable validation |
| `COEFF_STATS(0\|1)` | No | 0 | 1 = add STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB to primary layer |
| `FIT_METRICS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA layer |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS layer |

> OUTPUT_FMT applies only to ARTFITRESIDUALS and ARTVALDATA — not to the primary coefficients layer.

### Output: five-layer ART

| Layer | Retrieved by | Contents |
|-------|-------------|----------|
| `ARTPRIMARY` | `SELECT *` | Coefficients: INDEX, COEFF_NAME, COEFF_VALUE; +STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB if COEFF_STATS(1) |
| `ARTFITMETADATA` | `TD_EXTRACT_RESULTS` | Goodness-of-fit: R², adjusted R², F-statistic, AIC, MAE, MSE, MAPE |
| `ARTFITRESIDUALS` | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL per in-sample observation |
| `ARTMODEL` | `TD_EXTRACT_RESULTS` | Binary model context (VARBYTE 32000) — consumed by TD_ARIMAVALIDATE |
| `ARTVALDATA` | `TD_EXTRACT_RESULTS` | Holdout validation data (the FIT_PERCENTAGE remainder) |

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(
        TABLE_NAME(sales_ts),
        ROW_AXIS(SEQUENCE(seq_no)),
        SERIES_ID(store_id),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        NONSEASONAL(MODEL_ORDER(1,0,1)),
        ALGORITHM(MLE), CONSTANT(1),
        FIT_PERCENTAGE(70), FIT_METRICS(1), RESIDUALS(1)
    )
);

SELECT * FROM arima_est;   -- primary: coefficient table (COEFF_NAME, COEFF_VALUE, ...)

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(arima_est), LAYER(ARTFITMETADATA)));
```

---

## TD_ARIMAVALIDATE

Performs in-sample forecasting (validation) on the holdout portion reserved by `TD_ARIMAESTIMATE`'s `FIT_PERCENTAGE` parameter. Provides goodness-of-fit metrics and residuals for model comparison. The output ART is consumed by `TD_ARIMAFORECAST`.

> **`FIT_PERCENTAGE` must have been less than 100 in the preceding `TD_ARIMAESTIMATE` call.** If FIT_PERCENTAGE was 100, there is no holdout to validate against.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),    -- TABLE_NAME only; no other ART_SPEC params
    FUNC_PARAMS(
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]  -- ARTFITRESIDUALS only
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `FIT_METRICS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS |

No INPUT_FMT options. OUTPUT_FMT applies only to ARTFITRESIDUALS.

### Output: four-layer ART

| Layer | Retrieved by | Contents |
|-------|-------------|----------|
| `ARTPRIMARY` | `SELECT *` | Model selection metrics: NUM_SAMPLES, VAR_COUNT, AIC, SBIC, HQIC, MLR, MSE |
| `ARTFITMETADATA` | `TD_EXTRACT_RESULTS` | Goodness-of-fit: R², adjusted R², ME, MAE, MSE, MAPE, F_STAT, NULL_HYPOTH |
| `ARTFITRESIDUALS` | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL per validation observation |
| `ARTMODEL` | `TD_EXTRACT_RESULTS` | Binary model context consumed by `TD_ARIMAFORECAST` |

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

SELECT * FROM arima_val;    -- primary: model selection metrics (AIC, SBIC, MSE...)

EXECUTE FUNCTION INTO VOLATILE ART(residuals_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(arima_val), LAYER(ARTFITRESIDUALS)));
SELECT * FROM residuals_art;   -- ACTUAL_VALUE, CALC_VALUE, RESIDUAL
```

---

## TD_AUTOARIMA

Automatically searches for and fits the best ARIMA model based on an information criterion. Eliminates the manual TD_ARIMAESTIMATE → TD_ARIMAVALIDATE comparison cycle. `TD_ARIMAFORECAST` accepts TD_AUTOARIMA output directly.

> **Restrictions — read before using:**
> - Do not mix seasonal and non-seasonal series in one input
> - Do not mix seasonal series with different period attributes in one input
> - `PERIOD` must be explicitly specified for seasonal data — the function cannot infer it from the data; incorrect PERIOD produces inaccurate model selection
> - **Do not run TD_ARIMAVALIDATE on a TD_AUTOARIMA ART** — this returns an error; the returned model is already the best per the chosen criterion
> - Max p+q+P+Q = 5 when `STEPWISE(0)` (grid search)

```sql
EXECUTE FUNCTION INTO ART(autoarima_art)
TD_AUTOARIMA(
    SERIES_SPEC(
        TABLE_NAME(table_name),
        ROW_AXIS(SEQUENCE(seq_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        [MAX_PQ_NONSEASONAL(p, q),]            -- default (5,5)
        [MAX_PQ_SEASONAL(P, Q),]               -- default (2,2)
        [START_PQ_NONSEASONAL(p, q),]          -- default (0,0); STEPWISE(1) only
        [START_PQ_SEASONAL(P, Q),]             -- default (0,0); STEPWISE(1) only
        [d(integer),]                          -- default -1 (auto search)
        [Ds(integer),]                         -- default -1 (auto search)
        [MAX_d(integer),]                      -- default 2
        [MAX_Ds(integer),]                     -- default 1
        [PERIOD(integer),]                     -- default 1 (non-seasonal)
        [STATIONARY({ 0 | 1 }),]               -- default 0
        [SEASONAL({ 0 | 1 }),]                 -- default 1 (search all models including seasonal)
        [CONSTANT({ 0 | 1 }),]                 -- default 1 (include intercept)
        [ALGORITHM({ CSS_MLE | MLE | CSS }),]  -- default MLE
        [FIT_PERCENTAGE(integer),]             -- default 100
        [INFOR_CRITERIA({ AIC | AICC | BIC }),] -- default AIC
        [STEPWISE({ 0 | 1 }),]                 -- default 0 (grid search)
        [NMODELS(integer),]                    -- default 94; stepwise only
        [MAX_ITERATIONS(integer),]             -- default 100
        [COEFF_STATS({ 0 | 1 }),]              -- adds STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 }),]
        [ARMA_ROOTS({ 0 | 1 }),]               -- generates ARTARMAROOTS layer
        [TEST_NONSEASONAL(ADF),]               -- only ADF supported
        [TEST_SEASONAL(OCSB)]                  -- only OCSB supported
    )
);
```

### Output: up to six-layer ART

| Layer | Generated when | Retrieved by | Contents |
|-------|---------------|-------------|----------|
| `ARTPRIMARY` | Always | `SELECT *` | Best-model coefficients: INDEX, COEFF_NAME, COEFF_VALUE; +stats if COEFF_STATS(1) |
| `ARTFITMETADATA` | FIT_METRICS(1) | `TD_EXTRACT_RESULTS` | Same goodness-of-fit schema as TD_ARIMAESTIMATE |
| `ARTFITRESIDUALS` | RESIDUALS(1) | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL |
| `ARTMODEL` | Always | `TD_EXTRACT_RESULTS` | Binary model context (VARBYTE 64000) — consumed by TD_ARIMAFORECAST |
| `ARTICANDORDER` | Always | `TD_EXTRACT_RESULTS` | AIC, SBIC, HQIC, MLR, MSE, MODEL_ORDER (e.g. `"ARIMA(1, 1, 3)"`) |
| `ARTARMAROOTS` | ARMA_ROOTS(1) | `TD_EXTRACT_RESULTS` | ROOTS_NAME, REAL, IMAG, UNIT_CIRCLE — no roots should appear outside the unit circle |

### Two post-AUTOARIMA forecast paths

```sql
-- Path 1: Forecast directly (simplest — no validation step needed or allowed)
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(autoarima_art)), FUNC_PARAMS(FORECAST_PERIODS(12)));

-- Path 2: Extract order → re-estimate with TD_ARIMAESTIMATE → full manual pipeline
EXECUTE FUNCTION INTO ART(model_order_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(autoarima_art), LAYER(ARTICANDORDER)));
SELECT MODEL_ORDER FROM model_order_art;  -- e.g. "ARIMA(1, 1, 3)"
-- Use p=1, d=1, q=3 in TD_ARIMAESTIMATE for full validation and auditable results
```

### Example

```sql
EXECUTE FUNCTION INTO ART(myart)
TD_AUTOARIMA(
    SERIES_SPEC(TABLE_NAME(covid_confirm), ROW_AXIS(SEQUENCE(row_axis)),
                SERIES_ID(city), PAYLOAD(FIELDS(cnumber), CONTENT(REAL))),
    FUNC_PARAMS(
        MAX_PQ_NONSEASONAL(3,3),
        STATIONARY(0), STEPWISE(0),
        RESIDUALS(1), ARMA_ROOTS(1)
    )
);

SELECT * FROM myart;   -- coefficients for selected best model
```

---

## TD_LINEAR_REGR

Fits a simple linear regression model: one response variable against one explanatory variable, with optional weighting. The resulting coefficients can drive `TD_GENSERIES4FORMULA` for prediction on new data.

> **Typical workflow:** `TD_LINEAR_REGR` → extract COEFF_VALUE → build formula string → `TD_GENSERIES4FORMULA` to predict response values for new explanatory inputs.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(lr_result)
TD_LINEAR_REGR(
    SERIES_SPEC(
        TABLE_NAME(house_values),
        ROW_AXIS(SEQUENCE(s_no)),
        SERIES_ID(cid),
        PAYLOAD(FIELDS(HOUSE_VALUE, SALARY), CONTENT(MULTIVAR_REAL))
        --        ^response    ^explanatory  (^weights if WEIGHTS(1))
    ),
    FUNC_PARAMS(
        [VARIABLES_COUNT({ 2 | 3 }),]   -- 2 = no weights (default), 3 = with weights
        WEIGHTS({ 0 | 1 }),             -- 0 = no weight field (default), 1 = third field is weights
        FORMULA('Y = B0 + B1*X1'),      -- follows Formula Rules; see uaf-formula-rules
        ALGORITHM({ 'QR' | 'PSI' }),
        [COEFF_STATS({ 0 | 1 }),]
        [CONF_INT_LEVEL(float),]        -- 0–1; only with COEFF_STATS(1); default 0.90
        [MODEL_STATS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
);
```

**Payload field order matters:** first field = response variable, second field = explanatory variable, third field = weights (when WEIGHTS(1)).

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `VARIABLES_COUNT` | No | 2 | Total payload fields: 2 = response + explanatory; 3 = + weights |
| `WEIGHTS(0\|1)` | Yes | 0 | 1 = third payload field is weights for weighted least-squares |
| `FORMULA` | Yes | — | Regression formula string; conforms to Formula Rules |
| `ALGORITHM` | Yes | — | `'QR'` (QR decomposition) or `'PSI'` (SVD pseudo-inverse) |
| `COEFF_STATS(0\|1)` | No | 0 | 1 = add STD_ERROR, TSTAT_VALUE, TSTAT_PROB, SIGNIF_RATING, CONF_INT_LOW/HIGH |
| `CONF_INT_LEVEL` | No | 0.90 | Confidence interval level; requires COEFF_STATS(1) |
| `MODEL_STATS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA layer |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS layer |

No INPUT_FMT. No OUTPUT_FMT.

### Output: three-layer ART

**Primary (ARTPRIMARY):**

| Column | Condition | Description |
|--------|-----------|-------------|
| `ROW_I` | Always | Coefficient index (position in formula) |
| `COEFF_NAME` | Always | Coefficient name |
| `COEFF_VALUE` | Always | Calculated coefficient value |
| `STD_ERROR` | COEFF_STATS(1) | Standard error of coefficient |
| `TSTAT_VALUE` | COEFF_STATS(1) | t-statistic |
| `TSTAT_PROB` | COEFF_STATS(1) | Probability if coefficient = 0 |
| `SIGNIF_RATING` | COEFF_STATS(1) | Confidence range label |
| `CONF_INT_LOW` / `CONF_INT_HIGH` | COEFF_STATS(1) | Confidence interval bounds |

**Secondary (ARTFITMETADATA):** MULTIPLE_R_SQUARED, ADJUSTED_R_SQUARED, FSTATISTIC, STD_ERROR2, STD_ERROR_DF, EXPLAINED_DF, UNEXPLAINED_DF, PROB_VALUE

**Tertiary (ARTFITRESIDUALS):** X1, ACTUAL_VALUE, CALC_VALUE, RESIDUAL

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(lr_result)
TD_LINEAR_REGR(
    SERIES_SPEC(TABLE_NAME(HOUSE_VALUES), ROW_AXIS(SEQUENCE(S_NO)),
                SERIES_ID(CID), PAYLOAD(FIELDS(HOUSE_VALUE, SALARY), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(
        VARIABLES_COUNT(2), WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1'), ALGORITHM('QR'),
        COEFF_STATS(1), MODEL_STATS(1), RESIDUALS(1)
    )
);

SELECT * FROM lr_result;   -- B0 (intercept), B1 (slope) with confidence intervals

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(lr_result), LAYER(ARTFITRESIDUALS)));
-- Returns: CID, ROW_I, X1 (SALARY), ACTUAL_VALUE (HOUSE_VALUE), CALC_VALUE, RESIDUAL
```

---

## TD_MULTIVAR_REGR

Fits a multivariate linear regression model: one response variable against multiple explanatory variables, with optional weighting. Same structure as `TD_LINEAR_REGR` extended to N explanatory variables.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(mv_result)
TD_MULTIVAR_REGR(
    SERIES_SPEC(
        TABLE_NAME(house_values),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(CITYID),
        PAYLOAD(FIELDS(HOUSE_VAL, SALARY, MORTGAGE), CONTENT(MULTIVAR_REAL))
        --        ^response  ^X1       ^X2      (last field = weights if WEIGHTS(1))
    ),
    FUNC_PARAMS(
        VARIABLES_COUNT(3),              -- required; 1 response + 2 explanatory here
        WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1 + B2*X2'),
        ALGORITHM('QR'),
        [COEFF_STATS({ 0 | 1 }),]
        [CONF_INT_LEVEL(float),]
        [MODEL_STATS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
);
```

**Payload field order:** first = response variable; second through (n−1) = explanatory variables; last = weights (when WEIGHTS(1)).

### Differences from TD_LINEAR_REGR

| Aspect | TD_LINEAR_REGR | TD_MULTIVAR_REGR |
|--------|---------------|-----------------|
| Explanatory variables | 1 (X1) | 2 or more (X1, X2, ...) |
| `VARIABLES_COUNT` | Optional; default 2 | Required; must reflect total payload field count |
| ARTFITRESIDUALS | `X1` only | `X1, X2, X3, ...` (one column per explanatory variable) |
| Formula | `Y = B0 + B1*X1` | `Y = B0 + B1*X1 + B2*X2 + ...` |

All other FUNC_PARAMS, output layers (ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS), schemas, and behavior are identical to `TD_LINEAR_REGR`.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(mv_result)
TD_MULTIVAR_REGR(
    SERIES_SPEC(TABLE_NAME(HOUSE_VALUES), ROW_AXIS(TIMECODE(TD_TIMECODE)),
                SERIES_ID(CITYID),
                PAYLOAD(FIELDS(HOUSE_VAL, SALARY, MORTGAGE), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(
        VARIABLES_COUNT(3), WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1 + B2*X2'),
        ALGORITHM('QR'), COEFF_STATS(1), MODEL_STATS(1), RESIDUALS(1)
    )
);

SELECT * FROM mv_result;    -- B0 (intercept), B1 (SALARY coeff), B2 (MORTGAGE coeff)

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(mv_result), LAYER(ARTFITRESIDUALS)));
-- Returns: CITYID, ROW_I, X1 (SALARY), X2 (MORTGAGE), ACTUAL_VALUE, CALC_VALUE, RESIDUAL
```
