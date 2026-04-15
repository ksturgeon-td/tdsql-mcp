# Teradata UAF — Diagnostic Statistical Tests

Statistical tests for validating model assumptions and measuring fit quality. Most functions operate on residuals from a prior UAF model fitting step (TD_LINEAR_REGR, TD_MULTIVAR_REGR, TD_ARIMAESTIMATE, TD_ARIMAVALIDATE).

> **Read `uaf-concepts` first** for SERIES_SPEC, ART_SPEC, the execution pattern, and ART layer retrieval.

---

## Quick Reference

### What each test detects

| Function | Tests for | Typical timing |
|----------|-----------|----------------|
| `TD_DICKEY_FULLER` | Unit roots (stationarity) | **Before modeling** — verify series is stationary |
| `TD_DURBIN_WATSON` | Serial correlation in residuals | After regression |
| `TD_BREUSCH_GODFREY` | Serial correlation, multi-lag | After regression; more powerful than DW |
| `TD_PORTMAN` | White noise — 5 test variants | After ARIMA validation |
| `TD_WHITES_GENERAL` | Heteroscedasticity | After regression; no normality assumption required |
| `TD_BREUSCH_PAGAN_GODFREY` | Heteroscedasticity | After regression; Koenker studentized variant available |
| `TD_GOLDFELD_QUANDT` | Heteroscedasticity | After regression; requires raw Y+X data |
| `TD_CUMUL_PERIODOGRAM` | Periodicities, simultaneous Bartlett test | After ARIMA validation |
| `TD_SIGNIF_PERIODICITIES` | Specific candidate periodicities | After spectral analysis identifies peaks |
| `TD_SIGNIF_RESIDMEAN` | Non-zero residual mean (zero-mean test) | After ARIMA validation |
| `TD_FITMETRICS` | Goodness-of-fit metrics | Standalone metric calculator |
| `TD_SELECTION_CRITERIA` | AIC, BIC, HQIC, MLR, MSE | Comparing candidate models |

### Input type and ART_SPEC LAYER requirement

| Function | SERIES_SPEC content | ART_SPEC LAYER |
|----------|---------------------|----------------|
| `TD_DICKEY_FULLER` | REAL | TABLE_NAME only |
| `TD_DURBIN_WATSON` | REAL | TABLE_NAME only |
| `TD_BREUSCH_GODFREY` | MULTIVAR_REAL (residual, x1…xN) | TABLE_NAME only |
| `TD_PORTMAN` | REAL | TABLE_NAME + LAYER required |
| `TD_WHITES_GENERAL` | MULTIVAR_REAL (residual, x1…xN) | TABLE_NAME only |
| `TD_BREUSCH_PAGAN_GODFREY` | MULTIVAR_REAL (all payload fields) | TABLE_NAME only |
| `TD_GOLDFELD_QUANDT` | MULTIVAR_REAL (Y, x1…xN) — **SERIES_SPEC only** | N/A |
| `TD_CUMUL_PERIODOGRAM` | REAL | TABLE_NAME + LAYER required |
| `TD_SIGNIF_PERIODICITIES` | REAL | TABLE_NAME + LAYER required |
| `TD_SIGNIF_RESIDMEAN` | REAL | TABLE_NAME + LAYER required |
| `TD_FITMETRICS` | MULTIVAR_REAL (actual, calculated, residual) | TABLE_NAME + LAYER required |
| `TD_SELECTION_CRITERIA` | MULTIVAR_REAL (actual, calculated, residual) | TABLE_NAME only |

> Functions requiring LAYER use: `ART_SPEC(TABLE_NAME(art_name), LAYER(ARTFITRESIDUALS))`.
> Functions using TABLE_NAME only: `ART_SPEC(TABLE_NAME(art_name))`.

---

## TD_DICKEY_FULLER

Tests for unit roots in a time series. Used **before modeling** to verify stationarity — not on residuals. If unit roots are present, difference the series (TD_DIFF) or apply seasonal normalization (TD_SEASONALNORMALIZE) and re-run to verify.

> **NULL_HYP interpretation is inverted vs. most diagnostics:** ACCEPT = unit roots present (non-stationary — problem); REJECT = unit roots absent (may be stationary).

```sql
EXECUTE FUNCTION INTO VOLATILE ART(df_art)
TD_DICKEY_FULLER(
    SERIES_SPEC(
        TABLE_NAME(sales_ts),
        SERIES_ID(store_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))
    ),
    FUNC_PARAMS(ALGORITHM('NONE'))    -- NONE | DRIFT | DRIFTNTREND | SQUARED
);

SELECT * FROM df_art;
-- If NULL_HYP = ACCEPT: apply TD_DIFF or TD_SEASONALNORMALIZE, then rerun
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `ALGORITHM` | Yes | Regression type: `NONE` (random walk), `DRIFT` (+ drift term), `DRIFTNTREND` (+ drift + trend), `SQUARED` (+ drift + trend + quadratic) |
| `MAXLAGS` | No | Maximum lag (0–100); default `0` |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES` | Total sample points |
| `ALGORITHM` | Requested regression mode |
| `T_STAT` | Dickey-Fuller τ statistic |
| `P_VALUE` | p-value |
| `NULL_HYP` | `ACCEPT` (unit roots present, non-stationary) / `REJECT` (unit roots absent, may be stationary) / `INCONCLUSIVE` |

---

## TD_FITMETRICS

Computes goodness-of-fit metrics from any (actual, calculated, residual) triple. Produces the same metrics embedded in ARTFITMETADATA layers of regression functions, but as a standalone function applicable to any model output or custom pipeline.

```sql
-- From a UAF regression ART (LAYER required)
EXECUTE FUNCTION INTO VOLATILE ART(fm_art)
TD_FITMETRICS(
    ART_SPEC(TABLE_NAME(arima_val_art), LAYER(ARTFITRESIDUALS)),
    FUNC_PARAMS(VAR_COUNT(3), FSTAT(1), SIGNIFICANCE_LEVEL(0.05))
);

-- From a SERIES_SPEC (actual → calculated → residual, MULTIVAR_REAL)
EXECUTE FUNCTION INTO VOLATILE ART(fm_art)
TD_FITMETRICS(
    SERIES_SPEC(
        TABLE_NAME(model_residuals),
        SERIES_ID(id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(actual_val, calc_val, residual), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(VAR_COUNT(5), FSTAT(1), SIGNIFICANCE_LEVEL(0.05))
);

SELECT * FROM fm_art;
```

> **SERIES_SPEC payload order:** actual value → calculated value → residual (MULTIVAR_REAL).

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `VAR_COUNT` | Yes | Number of explanatory variables including the constant |
| `FSTAT` | No | `1` = include F-test columns in output; default `0` |
| `SIGNIFICANCE_LEVEL` | If FSTAT(1) | Required only when FSTAT(1) |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `VAR_COUNT` | Sample size and variable count |
| `R_SQUARE`, `R_ADJ_SQUARE` | R² and adjusted R² |
| `STD_ERROR`, `STD_ERROR_DF` | Standard error and degrees of freedom |
| `ME`, `MAE`, `MSE`, `MPE`, `MAPE` | Error metrics |
| `FSTAT_CALC`, `P_VALUE` | F-statistic and p-value (meaningful when FSTAT(1)) |
| `NUM_DF`, `DENOM_DF`, `SIGNIFICANCE_LEVEL` | F-test degrees of freedom and significance level |
| `F_CRITICAL`, `F_CRITICAL_P`, `NULL_HYPOTH` | Critical value, p-value, and test result |

> `NULL_HYPOTH`: `ACCEPT` = all slope coefficients are zero; `REJECT` = non-zero slope coefficients.

---

## TD_SELECTION_CRITERIA

Computes model selection criteria to compare candidate models. Returns five metrics — no hypothesis test. Lower AIC/SBIC/HQIC indicates a better fit-to-complexity tradeoff.

```sql
-- From a TD_ARIMAESTIMATE ART (use log-likelihood for ARIMA models)
EXECUTE FUNCTION INTO VOLATILE ART(selcrt_art)
TD_SELECTION_CRITERIA(
    ART_SPEC(TABLE_NAME(arima_est_art)),       -- TABLE_NAME only
    FUNC_PARAMS(VAR_COUNT(4), CONSTANT(1), USE_LIKELIHOOD(1))
);

-- From a SERIES_SPEC (actual → calculated → residual, MULTIVAR_REAL)
EXECUTE FUNCTION INTO VOLATILE ART(selcrt_art)
TD_SELECTION_CRITERIA(
    SERIES_SPEC(
        TABLE_NAME(residuals_table),
        SERIES_ID(id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(actual_val, calc_val, residual), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(VAR_COUNT(4), CONSTANT(1))
);

SELECT * FROM selcrt_art;
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `VAR_COUNT` | Yes | Total number of model parameters |
| `CONSTANT` | Yes | `1` if model includes a constant/intercept; `0` otherwise |
| `USE_LIKELIHOOD` | No | `0` = RSS-based (default); `1` = log-likelihood-based. Only valid when input is ART_SPEC from TD_ARIMAESTIMATE |

> `USE_LIKELIHOOD(1)` produces different AIC/SBIC/HQIC/MLR values than `USE_LIKELIHOOD(0)` — MSE is unchanged.

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `VAR_COUNT` | Sample size and parameter count |
| `AIC` | Akaike Information Criterion |
| `SBIC` | Schwarz Bayesian Information Criterion |
| `HQIC` | Hannan-Quinn Information Criterion |
| `MLR` | Maximum Likelihood Rule (log-likelihood value) |
| `MSE` | Mean Squared Error |

---

## TD_DURBIN_WATSON

Tests for serial correlation in regression residuals. DW statistic ranges 0–4: ~2 = no correlation; 0–2 = positive autocorrelation; 2–4 = negative autocorrelation. Upper/lower bound critical values (DU/DL) define an inconclusive region.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(dw_art)
TD_DURBIN_WATSON(
    ART_SPEC(TABLE_NAME(lr_art)),             -- TABLE_NAME only; must have ARTFITRESIDUALS
    FUNC_PARAMS(
        EXPLANATORY_COUNT(1),                 -- required; used for DW critical value table lookup
        INCLUDE_CONSTANT(1),                  -- 1=regression had intercept
        METHOD(DW_FORMULA),                   -- DW_FORMULA | ACR_LAG1
        SIGNIFICANCE_LEVEL(0.05)
    )
);

SELECT * FROM dw_art;
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `EXPLANATORY_COUNT` | Yes | Number of explanatory variables in original regression; needed for DW critical value table lookup |
| `INCLUDE_CONSTANT` | No | `1` if original regression had a constant; `0` otherwise |
| `METHOD` | Yes | `DW_FORMULA` (full summation formula) or `ACR_LAG1` (autocorrelation at lag 1) |
| `SIGNIFICANCE_LEVEL` | Yes | Significance level for the test |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `EXPLANATORY_COUNT`, `CONSTANT`, `METHOD` | Test configuration |
| `DW_VALUE` | Durbin-Watson statistic (0–4; ~2 = no serial correlation) |
| `DL_VALUE`, `DU_VALUE` | Lower/upper critical bounds from internal DW tables |
| `SIGNIFICANCE_LEVEL` | Significance level used |
| `NULL_HYPOTH` | `ACCEPT` (no serial correlation) / `REJECT` (serial correlation present) / `INCONCLUSIVE` |

---

## TD_BREUSCH_GODFREY

Tests for serial correlation (autocorrelation) in regression residuals using multi-lag auxiliary regression. More powerful than TD_DURBIN_WATSON for detecting higher-order autocorrelation.

**Typical workflow:** TD_LINEAR_REGR or TD_MULTIVAR_REGR (with RESIDUALS(1)) → TD_BREUSCH_GODFREY.

```sql
-- From a UAF regression ART (TABLE_NAME only)
EXECUTE FUNCTION INTO VOLATILE ART(bg_art)
TD_BREUSCH_GODFREY(
    ART_SPEC(TABLE_NAME(lr_art)),
    FUNC_PARAMS(
        EXPLANATORY_COUNT(2),
        RESIDUAL_MAXLAGS(1),
        SIGNIFICANCE_LEVEL(0.05)
    )
);

-- From a SERIES_SPEC (residual first, then explanatory variables)
EXECUTE FUNCTION INTO VOLATILE ART(bg_art)
TD_BREUSCH_GODFREY(
    SERIES_SPEC(
        TABLE_NAME(residuals_table),
        SERIES_ID(city_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual, x1, x2), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(EXPLANATORY_COUNT(2), RESIDUAL_MAXLAGS(1), SIGNIFICANCE_LEVEL(0.05))
);

SELECT * FROM bg_art;
```

> **SERIES_SPEC payload order:** residual column first, then explanatory variables.

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `EXPLANATORY_COUNT` | Yes | Number of explanatory variables in original regression |
| `RESIDUAL_MAXLAGS` | Yes | Maximum lag for auxiliary regression; determines degrees of freedom |
| `SIGNIFICANCE_LEVEL` | No | Default `0.05` |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `EXPLANATORY_COUNT`, `RESIDUAL_MAXLAGS` | Test configuration |
| `BG_VALUE` | Breusch-Godfrey chi-squared test statistic |
| `P_VALUE`, `CRITICAL_VALUE`, `CRITICAL_P` | Test statistics and critical values |
| `SIGNIFICANCE_LEVEL` | Significance level used |
| `NULL_HYPOTHESIS` | `ACCEPT` (no serial correlation) / `REJECT` (serial correlation present) |

---

## TD_PORTMAN

Portmanteau white noise test — five statistical test variants that determine if the residual series is white noise. All are chi-squared based.

> **ART_SPEC requires LAYER:** `ART_SPEC(TABLE_NAME(art), LAYER(ARTFITRESIDUALS))`
>
> **Typical workflow:** TD_ARIMAVALIDATE (RESIDUALS(1)) → TD_PORTMAN.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(portman_art)
TD_PORTMAN(
    SERIES_SPEC(
        TABLE_NAME(arima_validate_residuals),
        SERIES_ID(dataset_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual), CONTENT(REAL))
    ) WHERE dataset_id = 552,
    FUNC_PARAMS(
        MAXLAG(2),
        TEST(LB),                   -- BP | LB | LM | MQ | ML
        DEGREES_FREEDOM(1),         -- model order (p+q for ARIMA); subtracted from MAXLAG
        SIGNIFICANCE_LEVEL(0.05)
    )
);

SELECT * FROM portman_art;
```

### TEST variants

| Code | Name | Algorithm | Notes |
|------|------|-----------|-------|
| `BP` | Box-Pierce | Basic ACF-based | Simplest variant |
| `LB` | Ljung-Box | Asymptotic variance adjusted | Most common; recommended default |
| `LM` | Li-McLeod | Conservative adjustment | More conservative than LB |
| `MQ` | Monti Q | PACF-based | Add `PACF_METHOD(LEVINSON_DURBIN\|OLS)` if needed |
| `ML` | McLeod-Li | Squares residuals → ACF | Detects ARCH/volatility clustering effects |

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `MAXLAG` | Yes | Maximum lag for autocorrelation testing |
| `TEST` | Yes | Test variant (see table above) |
| `DEGREES_FREEDOM` | Yes | Model order (p+q for ARIMA); subtracted from MAXLAG to get effective df |
| `SIGNIFICANCE_LEVEL` | Yes | Significance level for the test |
| `PACF_METHOD` | No | `LEVINSON_DURBIN` or `OLS`; only applicable when TEST(MQ) |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES` | Sample points |
| `DEGREES_FREEDOM` | Effective df = MAXLAG − model DEGREES_FREEDOM input |
| `PORTMAN_VALUE` | Portmanteau test statistic |
| `P_VALUE`, `CHISQUARE_VALUE`, `CRITICAL_P` | Test statistics and critical values |
| `NULL_HYPOTH` | `ACCEPT` (white noise, model adequate) / `REJECT` (not white noise — model missing structure) |

---

## TD_WHITES_GENERAL

Tests for heteroscedasticity (non-constant error variance) in regression residuals. Does not require data reordering (unlike TD_GOLDFELD_QUANDT) and is not sensitive to normality assumption (unlike TD_BREUSCH_PAGAN_GODFREY). Can also detect omitted variables and functional form misspecification.

```sql
-- From a UAF regression ART (TABLE_NAME only)
EXECUTE FUNCTION INTO VOLATILE ART(wg_art)
TD_WHITES_GENERAL(
    ART_SPEC(TABLE_NAME(multivar_regr_art)),
    FUNC_PARAMS(VARIABLES_COUNT(3), SIGNIFICANCE_LEVEL(0.05))
);

-- From a SERIES_SPEC (residual first, then explanatory variables)
EXECUTE FUNCTION INTO VOLATILE ART(wg_art)
TD_WHITES_GENERAL(
    SERIES_SPEC(
        TABLE_NAME(residuals_table),
        SERIES_ID(id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual, x1, x2, x3), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(VARIABLES_COUNT(3), SIGNIFICANCE_LEVEL(0.05))
);

SELECT * FROM wg_art;
```

> **SERIES_SPEC payload order:** residual column first, then explanatory variables.

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `VARIABLES_COUNT` | Yes | Number of explanatory variables in the payload (not counting the residual column) |
| `SIGNIFICANCE_LEVEL` | Yes | Significance level for the test |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `AUX_COUNT` | Sample size and variable combinations in auxiliary regression |
| `AUX_RSS`, `DEGREES_FREEDOM` | Auxiliary regression residual sum of squares and df |
| `WG_VALUE` | White's General test statistic |
| `P_VALUE`, `CHISQUARED_VALUE`, `CRITICAL_P` | Test statistics and critical values |
| `NULL_HYPOTH` | `ACCEPT` (homoscedastic) / `REJECT` (heteroscedastic) |

---

## TD_BREUSCH_PAGAN_GODFREY

Tests for heteroscedasticity in regression residuals. Supports the Koenker studentized version (STUDENTIZE(1)), which is more robust when residuals are not normally distributed.

```sql
-- From a UAF regression ART (TABLE_NAME only)
EXECUTE FUNCTION INTO VOLATILE ART(bpg_art)
TD_BREUSCH_PAGAN_GODFREY(
    ART_SPEC(TABLE_NAME(multivar_regr_art)),
    FUNC_PARAMS(
        VARIABLES_COUNT(4),
        STUDENTIZE(1),
        SIGNIFICANCE_LEVEL(0.05)
    )
);

-- From a SERIES_SPEC
EXECUTE FUNCTION INTO VOLATILE ART(bpg_art)
TD_BREUSCH_PAGAN_GODFREY(
    SERIES_SPEC(
        TABLE_NAME(ols_residuals),
        SERIES_ID(id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(x1, x2, x3, residual), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(VARIABLES_COUNT(4), STUDENTIZE(1), SIGNIFICANCE_LEVEL(0.05))
);

SELECT * FROM bpg_art;
```

> **VARIABLES_COUNT = total fields in PAYLOAD** (explanatory variables + residual column). Example: PAYLOAD(FIELDS(x1, x2, x3, residual)) → VARIABLES_COUNT(4).

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `VARIABLES_COUNT` | Yes | Total payload fields (explanatory variables + residual column) |
| `FORMULA` | No | Custom formula for auxiliary regression |
| `STUDENTIZE` | No | `0` = standard BPG test (default); `1` = Koenker studentized version (more robust to non-normality) |
| `SIGNIFICANCE_LEVEL` | No | Default `0.05` |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `EXPLANATORY_COUNT` | Sample size and explanatory variable count |
| `RSS_ORIG`, `MLE_VARIANCE`, `AUX_ESS` | Residual and auxiliary regression statistics |
| `DEGREES_FREEDOM` | Auxiliary regression degrees of freedom |
| `BPG_VALUE` | Breusch-Pagan-Godfrey test statistic |
| `P_VALUE`, `CHISQUARE_VALUE`, `CRITICAL_P` | Test statistics and critical values |
| `NULL_HYPOTHESIS` | `ACCEPT` (homoscedastic) / `REJECT` (heteroscedastic) |

---

## TD_GOLDFELD_QUANDT

Tests for heteroscedasticity by splitting the data into two subsets and comparing their residual variances via F-test. Requires raw dependent + explanatory variable data — not pre-computed residuals. **SERIES_SPEC only; no ART_SPEC.**

> **SERIES_SPEC payload order:** dependent variable Y first, then explanatory variables — unlike other heteroscedasticity tests which take residuals.
>
> The function internally performs regression on two data subsets separated by OMIT central observations, then F-tests the variance ratio.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(gq_art)
TD_GOLDFELD_QUANDT(
    SERIES_SPEC(
        TABLE_NAME(regression_data),
        SERIES_ID(series_id),
        ROW_AXIS(SEQUENCE(x1)),
        PAYLOAD(FIELDS(y1, x1), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(
        CONST_TERM(1),               -- optional: 1=include intercept (default)
        OMIT(2),                     -- required: central points to omit; <1=fraction, >1=count
        SIGNIFICANCE_LEVEL(0.05),
        TEST('GREATER'),             -- optional: GREATER | LESS | TWOSIDED (default GREATER)
        ALGORITHM('QR')              -- optional: QR (default) | PSI
    )
);

SELECT * FROM gq_art;
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `OMIT` | Yes | Central observations to exclude; `<1` = fraction of total, `>1` = absolute count |
| `SIGNIFICANCE_LEVEL` | Yes | Significance level for the test |
| `CONST_TERM` | No | `1` = include Y-intercept (default); `0` = regression through origin |
| `START_IDX` | No | Split-point index; `<1` = fraction, `>1` = absolute; default = (total − OMIT) / 2 |
| `TEST` | No | `GREATER` (default), `LESS`, or `TWOSIDED` — which tail(s) to evaluate |
| `ALGORITHM` | No | `QR` decomposition (default) or `PSI` (pseudo-inverse via SVD) |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `TOTAL_NUM_SAMPLES`, `VARIABLES_COUNT` | Total samples and variable count |
| `NUM_SAMPLES1`, `NUM_SAMPLES2`, `OMITTED` | Subset sizes and omitted point count |
| `DEGREES_FREEDOM_1`, `DEGREES_FREEDOM_2` | F-test degrees of freedom |
| `GQ_STATISTIC`, `GQ_PVALUE` | Goldfeld-Quandt F-statistic and p-value |
| `F_CRITICAL_VALUE_HI` | Upper F-critical (NULL when TEST=LESS) |
| `F_CRITICAL_VALUE_LOW` | Lower F-critical (NULL when TEST=GREATER) |
| `TEST` | Test variant used |
| `NULL_HYPOTHESIS` | `ACCEPT HYPOTH:MEANING THERE IS HOMOSCEDASTIC VARIANCE` / `REJECT HYPOTH:MEANING THERE IS HETEROSCEDASTIC VARIANCE` |

---

## TD_CUMUL_PERIODOGRAM

Bartlett's cumulative periodogram test — simultaneously tests whether any periodicities (seasonal cycles) exist in the residual series. Two-layer ART: ARTPRIMARY (test result) and ARTCPDATA (per-frequency data for plotting with TD_PLOT).

> **ART_SPEC requires LAYER:** `ART_SPEC(TABLE_NAME(art), LAYER(ARTFITRESIDUALS))`
>
> **SIGNIFICANCE_LEVEL limited to 0.05 or 0.01 only** — not a free-float.
>
> **vs. TD_SIGNIF_PERIODICITIES:** CUMUL_PERIODOGRAM tests all periodicities simultaneously without requiring a candidate list; SIGNIF_PERIODICITIES tests a provided list of candidate periods individually.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(cp_art)
TD_CUMUL_PERIODOGRAM(
    SERIES_SPEC(
        TABLE_NAME(arima_validate_residuals),
        SERIES_ID(dataset_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual), CONTENT(REAL))
    ),
    FUNC_PARAMS(SIGNIFICANCE_LEVEL(0.05))     -- 0.05 or 0.01 only
);

-- Primary result: Bartlett test statistics
SELECT * FROM cp_art;

-- Secondary layer: per-frequency values for plotting
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(cp_art), LAYER(ARTCPDATA))
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `SIGNIFICANCE_LEVEL` | No | `0.05` (default) or `0.01` only |

### Output layers

**ARTPRIMARY:**

| Column | Description |
|--------|-------------|
| `Bartlett_TEST_STATS` | Maximum deviation of cumulative periodogram from reference line y = 2x |
| `P_VALUE` | Test p-value |
| `SIGNIFICANCE_LEVEL` | Significance level used |
| `TEST_RESULT` | `ACCEPT:No Significant Periodicity Encountered` / `Significant Periodicity Present` |

**ARTCPDATA** (retrieve with TD_EXTRACT_RESULTS; use with TD_PLOT):

| Column | Description |
|--------|-------------|
| `INDEX_K`, `NUM_SAMPLES` | Frequency index and sample count |
| `GAMMAK_SQUARE`, `ALPHA_K`, `BETA_K`, `G_K` | Intermediate periodogram values |
| `MIDDLE_SIGNIF_LINE`, `UPPER_SIGNIF_BAND`, `LOWER_SIGNIF_BAND` | Reference line and confidence band for plotting |

---

## TD_SIGNIF_PERIODICITIES

Tests a provided list of candidate periodicities for statistical significance in the residual series. Returns **one row per tested periodicity**. Typically used after TD_LINESPEC or TD_POWERSPEC identifies spectral peaks.

> **ART_SPEC requires LAYER:** `ART_SPEC(TABLE_NAME(art), LAYER(ARTFITRESIDUALS))`
>
> **Default SIGNIFICANCE_LEVEL is 0.1** — more lenient than the 0.05 default in other functions.
>
> **One row per periodicity tested** — ROW_I increments for each candidate; output includes a PERIODICITY column.

```sql
-- Step 1: identify candidate periodicities via spectral analysis
-- SELECT TOP 4 * FROM linespec_art ORDER BY SPECTRAL_DENSITY DESC;

-- Step 2: test the candidates
EXECUTE FUNCTION INTO VOLATILE ART(sp_art)
TD_SIGNIF_PERIODICITIES(
    SERIES_SPEC(
        TABLE_NAME(arima_validate_residuals),
        SERIES_ID(dataset_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        PERIODICITIES(2.0, 6.0, 8.0),    -- comma-delimited list of candidate periods
        SIGNIFICANCE_LEVEL(0.05)
    )
);

SELECT * FROM sp_art;
-- Returns three rows: one per candidate periodicity
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `PERIODICITIES` | Yes | Comma-delimited float list of periodicity values to test |
| `SIGNIFICANCE_LEVEL` | No | Default `0.1` |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `ROW_I` | 0-based index; increments per tested periodicity |
| `PERIODICITY` | Actual tested period (may differ slightly from input due to discrete frequency adjustment) |
| `NUM_SAMPLES` | Sample points |
| `GAMMAK_SQUARE`, `RHO` | Periodogram calculation values |
| `FSTAT_CALC`, `P_VALUE` | F-statistic and p-value |
| `FSTAT_CRITICAL`, `FSTAT_CRITICAL_P` | Critical value and p-value |
| `NULL_HYPOTH` | `ACCEPT:No Significant Periodicity Encountered` / `REJECT` |

---

## TD_SIGNIF_RESIDMEAN

Tests whether the mean of a residual series is significantly different from zero using a T-test. The simplest diagnostic — one required parameter. If residuals have non-zero mean, the model is misspecified or biased.

> **ART_SPEC requires LAYER:** `ART_SPEC(TABLE_NAME(art), LAYER(ARTFITRESIDUALS))`

```sql
EXECUTE FUNCTION INTO VOLATILE ART(resid_mean_art)
TD_SIGNIF_RESIDMEAN(
    SERIES_SPEC(
        TABLE_NAME(arima_validate_residuals),
        SERIES_ID(dataset_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(residual), CONTENT(REAL))
    ),
    FUNC_PARAMS(SIGNIFICANCE_LEVEL(0.05))
);

SELECT * FROM resid_mean_art;
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `SIGNIFICANCE_LEVEL` | Yes | Significance level for the T-test |

### Output schema (ARTPRIMARY, single layer)

| Column | Description |
|--------|-------------|
| `NUM_SAMPLES`, `SIGNIFICANCE_LEVEL` | Sample count and significance level |
| `RESID_MEAN`, `RESID_VARIANCE` | Calculated residual mean and variance |
| `TSTAT_CALC`, `P_VALUE` | T-statistic and p-value |
| `TSTAT_CRITICAL`, `TSTAT_CRITICAL_P` | Critical T-value and corresponding p-value |
| `NULL_HYPOTH` | `ACCEPT` (mean ≈ 0, consistent with white noise) / `REJECT` (non-zero mean) |
