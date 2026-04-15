# Teradata UAF — Digital Signal Processing (DSP) and Spectral Analysis

Functions for Fourier transforms, wavelet transforms, convolution, spectral analysis, and symbolic representation.

---

## Quick Reference

| Function | Category | Dim | Purpose |
|----------|----------|-----|---------|
| `TD_DFFT` | Fourier | 1D | Forward FFT — time domain → frequency domain |
| `TD_DFFT2` | Fourier | 2D | Forward 2D FFT — matrices/images |
| `TD_IDFFT` | Fourier | 1D | Inverse FFT — frequency domain → time domain |
| `TD_IDFFT2` | Fourier | 2D | Inverse 2D FFT |
| `TD_DFFTCONV` | Fourier | 1D | Convert TD_DFFT result (raw↔human-readable, content type) |
| `TD_DFFT2CONV` | Fourier | 2D | Convert TD_DFFT2 result (raw↔human-readable, content type) |
| `TD_WINDOWDFFT` | Fourier | 1D | Apply window function then FFT in one call |
| `TD_DWT` | Wavelet | 1D | Forward Discrete Wavelet Transform |
| `TD_DWT2D` | Wavelet | 2D | Forward 2D DWT — matrices/images |
| `TD_IDWT` | Wavelet | 1D | Inverse DWT — reconstruct signal from wavelet coefficients |
| `TD_IDWT2D` | Wavelet | 2D | Inverse 2D DWT |
| `TD_CONVOLVE` | Convolution | 1D | Convolve time series with filter series |
| `TD_CONVOLVE2` | Convolution | 2D | Convolve matrix with filter matrix |
| `TD_POWERSPEC` | Spectral | 1D | Power spectrum estimate (Fourier-based); multiple algorithms + windowing |
| `TD_LINESPEC` | Spectral | 1D | Line spectrum — sinusoidal components; simpler than TD_POWERSPEC |
| `TD_GENSERIES4SINUSOIDS` | Spectral | 1D | Generate synthetic sinusoidal series at specified periodicities |
| `TD_SAX` | Symbolic | 1D | Symbolic Aggregate approXimation (PAA + SAX) |

---

## Key Pipelines

### Manual convolution (equivalent to TD_CONVOLVE)
```sql
EXECUTE FUNCTION INTO VOLATILE ART(dfftRes1) TD_DFFT(SERIES_SPEC(series1 ...), ...);
EXECUTE FUNCTION INTO VOLATILE ART(dfftRes2) TD_DFFT(SERIES_SPEC(series2 ...), ...);
EXECUTE FUNCTION INTO VOLATILE ART(freqRes)
  TD_BINARYSERIESOP(ART_SPEC(TABLE_NAME(dfftRes1)), ART_SPEC(TABLE_NAME(dfftRes2)),
    FUNC_PARAMS(MATHOP(MULTIPLY)), INPUT_FMT(INPUT_MODE(MATCH)));
EXECUTE FUNCTION INTO VOLATILE ART(convResult) TD_IDFFT(ART_SPEC(TABLE_NAME(freqRes)), ...);
-- Simpler: use TD_CONVOLVE instead
```

### Significant periodicities pipeline
```sql
-- 1. Spectral analysis with K_PERIODICITY
EXECUTE FUNCTION INTO VOLATILE ART(specRes)
  TD_POWERSPEC(SERIES_SPEC(...), FUNC_PARAMS(FREQ_STYLE('K_PERIODICITY')));
-- or TD_LINESPEC with FREQ_STYLE("K_PERIODICITY")

-- 2. Retrieve top periodicities
SELECT TOP 5 * FROM specRes ORDER BY SPECTRAL_DENSITY_field DESC;

-- 3. Test significance (use period values from step 2)
EXECUTE FUNCTION INTO VOLATILE ART(sigPeriodicities)
  TD_SIGNIF_PERIODICITIES(ART_SPEC(TABLE_NAME(residualsART), LAYER(ARTFITRESIDUALS)),
    FUNC_PARAMS(PERIODICITIES(p1, p2, p3, p4, p5)));
```

### Periodicity removal
```sql
-- 1. Identify dominant periods (K_PERIODICITY)
-- 2. Generate synthetic sinusoid series
EXECUTE FUNCTION INTO VOLATILE ART(sinusoids)
  TD_GENSERIES4SINUSOIDS(SERIES_SPEC(...), FUNC_PARAMS(PERIODICITIES(p1, p2)));
-- 3. Subtract from original
EXECUTE FUNCTION INTO VOLATILE ART(cleaned)
  TD_BINARYSERIESOP(SERIES_SPEC(original ...), ART_SPEC(TABLE_NAME(sinusoids)),
    FUNC_PARAMS(MATHOP(SUB)), INPUT_FMT(INPUT_MODE(MATCH)));
-- 4. Verify: TD_POWERSPEC on cleaned
```

### TD_IDFFT raw format constraint
If TD_IDFFT input is not via ART_SPEC, it **must** be in RAW format:
```sql
-- Convert human-readable TD_DFFT output to raw before TD_IDFFT
EXECUTE FUNCTION INTO VOLATILE ART(rawResult)
  TD_DFFTCONV(ART_SPEC(TABLE_NAME(hrDfftResult)),
    FUNC_PARAMS(CONV(HR_TO_RAW), FREQ_STYLE(K_INTEGRAL)));
-- Same constraint for TD_IDFFT2 — use TD_DFFT2CONV
```

---

## Shared Reference: Wavelet Families

Used by TD_DWT, TD_DWT2D, TD_IDWT, TD_IDWT2D. **WAVELET names are case-sensitive.**

| Family | Names |
|--------|-------|
| Daubechies | `db1` (= `haar`), `db2` – `db38` |
| Coiflets | `coif1` – `coif17` |
| Symlets | `sym2` – `sym20` |
| Discrete Meyer | `dmey` |
| Biorthogonal | `bior1.1`, `bior1.3`, `bior1.5`, `bior2.2`, `bior2.4`, `bior2.6`, `bior2.8`, `bior3.1`, `bior3.3`, `bior3.5`, `bior3.7`, `bior3.9`, `bior4.4`, `bior5.5`, `bior6.8` |
| Reverse Biorthogonal | `rbio1.1`, `rbio1.3`, `rbio1.5`, `rbio2.2`, `rbio2.4`, `rbio2.6`, `rbio2.8`, `rbio3.1`, `rbio3.3`, `rbio3.5`, `rbio3.7`, `rbio3.9`, `rbio4.4`, `rbio5.5`, `rbio6.8` |

**Signal extension modes** (MODE — case-insensitive):
`symmetric`/`sym`/`symh` · `reflect`/`symw` · `smooth`/`spd`/`sp1` · `constant`/`sp0` · `zero`/`zpd` · `periodic`/`ppd` · `periodization`/`per` · `antisymmetric`/`asym`/`asymh` · `antireflect`/`asymw`

---

## Shared Reference: FFT Parameters

Used by TD_DFFT, TD_DFFT2, TD_DFFTCONV, TD_DFFT2CONV, TD_WINDOWDFFT.

| Parameter | Options | Default | Notes |
|-----------|---------|---------|-------|
| `ZERO_PADDING_OK` | 1 \| 0 | 1 | Add zeros for efficient FFT size; use default |
| `FREQ_STYLE` | K_INTEGRAL, K_SAMPLE_RATE, K_RADIANS, K_HERTZ | K_INTEGRAL | K_HERTZ requires HERTZ_SAMPLE_RATE |
| `HERTZ_SAMPLE_RATE` | FLOAT | — | Required with K_HERTZ only |
| `ALGORITHM` | COOLEY_TUKEY \| SINGLETON | internal planner | Omit for best performance |
| `HUMAN_READABLE` | 1 \| 0 | 1 | 1 = symmetric around 0 (−3,−2,−1,0,1,2,3); 0 = sequential from 0 (0,1,2,3) |

**OUTPUT_FMT CONTENT options** (TD_DFFT, TD_DFFT2, TD_IDFFT, TD_IDFFT2, TD_DFFTCONV, TD_DFFT2CONV, TD_WINDOWDFFT):

| Series type | CONTENT options | Default |
|-------------|-----------------|---------|
| Univariate | COMPLEX, AMPL_PHASE_RADIANS, AMPL_PHASE_DEGREES | COMPLEX |
| Multivariate | MULTIVAR_COMPLEX, MULTIVAR_AMPL_PHASE, MULTIVAR_AMPL_PHASE_RADIANS, MULTIVAR_AMPL_PHASE_DEGREES | MULTIVAR_COMPLEX |

Output columns per content type:
- `COMPLEX` / `MULTIVAR_COMPLEX` → `REAL_PayloadName` + `IMAGINARY_PayloadName`
- `AMPL_PHASE*` / `MULTIVAR_AMPL_PHASE*` → `AMPLITUDE_PayloadName` + `PHASE_PayloadName`

---

## Fourier Transform

### TD_DFFT / TD_DFFT2

Forward FFT — transforms time/spatial domain signal to frequency domain.

| | TD_DFFT | TD_DFFT2 |
|---|---------|----------|
| **Primary input** | `SERIES_SPEC` or `ART_SPEC` | `MATRIX_SPEC` or `ART_SPEC` |
| **Payload content** | REAL, MULTIVAR_REAL | REAL, COMPLEX, MULTIVAR_REAL, MULTIVAR_COMPLEX |
| **Output axes** | ROW_I | ROW_I + COLUMN_I (both INTEGER or FLOAT per FREQ_STYLE) |
| **OUTPUT_FMT extra** | — | `ROW_MAJOR(1\|0)` |
| **No INPUT_FMT** | ✓ | ✓ |

FUNC_PARAMS: see Shared FFT Parameters. TD_POWERSPEC and TD_LINESPEC add `K_PERIODICITY` to FREQ_STYLE; TD_DFFT/TD_DFFT2 do **not** support K_PERIODICITY.

**Multivariate note:** lower size limit than univariate — if exceeded, split into individual single-field queries.

**Quote style:** TD_DFFT examples use double quotes `FREQ_STYLE("K_INTEGRAL")`; TD_DFFT2 examples omit quotes `FREQ_STYLE(K_INTEGRAL)` — both work.

**TD_DFFT2 HERTZ_SAMPLE_RATE** applies to both ROW_I and COLUMN_I axes.

```sql
-- TD_DFFT
EXECUTE FUNCTION INTO VOLATILE ART(DfftRes)
TD_DFFT(
  SERIES_SPEC(TABLE_NAME(genData), SERIES_ID(ID),
    ROW_AXIS(SEQUENCE(ROW_I)),
    PAYLOAD(FIELDS(MAGNITUDE), CONTENT(REAL))),
  FUNC_PARAMS(FREQ_STYLE("K_INTEGRAL"), HUMAN_READABLE(1)),
  OUTPUT_FMT(CONTENT(AMPL_PHASE_RADIANS))
);
SELECT * FROM DfftRes WHERE AMPLITUDE_MAGNITUDE > 1.0;

-- TD_DFFT2
EXECUTE FUNCTION INTO VOLATILE ART(DFFT2Res)
TD_DFFT2(
  MATRIX_SPEC(TABLE_NAME(imgTable), MATRIX_ID(BuoyID),
    ROW_AXIS(SEQUENCE(ROW_I)), COLUMN_AXIS(SEQUENCE(COLUMN_I)),
    PAYLOAD(FIELDS(MAGNITUDE), CONTENT(REAL))),
  FUNC_PARAMS(FREQ_STYLE(K_INTEGRAL), HUMAN_READABLE(0)),
  OUTPUT_FMT(CONTENT(COMPLEX))
);
SELECT * FROM DFFT2Res;
```

---

### TD_IDFFT / TD_IDFFT2

Inverse FFT — reconstructs time/spatial domain signal from Fourier coefficients.

| | TD_IDFFT | TD_IDFFT2 |
|---|----------|-----------|
| **Primary input** | `SERIES_SPEC` or `ART_SPEC` | `MATRIX_SPEC` or `ART_SPEC` |
| **RAW constraint** | Input not via ART_SPEC must be RAW; use `TD_DFFTCONV(CONV(HR_TO_RAW))` first | Same — use `TD_DFFT2CONV` |
| **Output axes** | ROW_I | ROW_I + COLUMN_I |
| **OUTPUT_FMT** | None | CONTENT options + `ROW_MAJOR(1\|0)` |
| **No INPUT_FMT** | ✓ | ✓ |

FUNC_PARAMS: `HUMAN_READABLE` and `ALGORITHM` only (no ZERO_PADDING_OK or FREQ_STYLE).

**TD_IDWT LEVEL doc inconsistency:** LEVEL appears in the FUNC_PARAMS table for TD_IDFFT but not in the syntax block — likely supported.

```sql
-- TD_IDFFT via ART_SPEC (no RAW conversion needed)
EXECUTE FUNCTION INTO VOLATILE ART(ORIG_SERIES)
TD_IDFFT(
  ART_SPEC(TABLE_NAME(DFFT_RESULTS),
    PAYLOAD(FIELDS(REAL_MAGNITUDE1, IMAG_MAGNITUDE1), CONTENT(COMPLEX))),
  FUNC_PARAMS(HUMAN_READABLE(1))
);
SELECT * FROM ORIG_SERIES;

-- TD_IDFFT2 round-trip (both with HUMAN_READABLE(0) avoids conversion)
EXECUTE FUNCTION INTO VOLATILE ART(IDFFT2)
TD_IDFFT2(
  MATRIX_SPEC(TABLE_NAME(DFFT2), MATRIX_ID(BuoyID),
    ROW_AXIS(SEQUENCE(ROW_I)), COLUMN_AXIS(SEQUENCE(COLUMN_I)),
    PAYLOAD(FIELDS(REAL_MAGNITUDE, IMAG_MAGNITUDE), CONTENT(COMPLEX))),
  FUNC_PARAMS(HUMAN_READABLE(0))
);
SELECT * FROM IDFFT2;
```

---

### TD_DFFTCONV / TD_DFFT2CONV

Convert a TD_DFFT / TD_DFFT2 result to a different form — more efficient than re-running FFT; original input not needed.

| | TD_DFFTCONV | TD_DFFT2CONV |
|---|------------|--------------|
| **Input** | `ART_SPEC` or `SERIES_SPEC` | `ART_SPEC` or `MATRIX_SPEC` |
| **Output axes** | ROW_I | ROW_I + COLUMN_I |
| **CONV** | Required | Required |

**FUNC_PARAMS:**

| Parameter | Options | Default |
|-----------|---------|---------|
| `CONV` | `HR_TO_RAW` \| `RAW_TO_HR` | none — **required** |
| `FREQ_STYLE` | K_INTEGRAL, K_SAMPLE_RATE, K_RADIANS, K_HERTZ | K_INTEGRAL |
| `HERTZ_SAMPLE_RATE` | FLOAT | — (required with K_HERTZ) |

Same OUTPUT_FMT CONTENT options as TD_DFFT. No INPUT_FMT.

**TD_DFFT2CONV COLUMN_I doc error:** description says "ROW_I is the integral..." — copy-paste error; COLUMN_I follows the same logic for the column axis.

```sql
-- Convert raw TD_DFFT result to human-readable AMPL_PHASE
EXECUTE FUNCTION INTO VOLATILE ART(DFFTCONV_HR_OUT)
TD_DFFTCONV(
  ART_SPEC(TABLE_NAME(DFFT_RAW_OUT)),
  FUNC_PARAMS(CONV(RAW_TO_HR), FREQ_STYLE(K_INTEGRAL)),
  OUTPUT_FMT(CONTENT(AMPL_PHASE_RADIANS))
);
SEL TOP 18 * FROM DFFTCONV_HR_OUT ORDER BY ID, ROW_I;
```

---

### TD_WINDOWDFFT

Apply a window function to a series before running FFT — reduces noise and spectral leakage.

**FUNC_PARAMS structure is unique:** two named sub-groups — `DFFT(...)` and `WINDOW(...)` — each specified as separate entries within FUNC_PARAMS.

**DFFT sub-params:** same as Shared FFT Parameters (no K_PERIODICITY).

**WINDOW sub-params:**

| Parameter | Required? | Description | Default |
|-----------|-----------|-------------|---------|
| `SIZE(NUM(n))` | Yes (one of) | Window size in data points; > 0 | — |
| `SIZE(PERC(f))` | Yes (one of) | Window size as % of series; > 0 | — |
| `OVERLAP(n)` | No | Points window slides per FFT; must be < window size | 0 |
| `IS_SYMMETRIC(1\|0)` | No | 1 = symmetric; 0 = periodic. **Doc typo:** syntax shows `IS_SYMETRIC` (one M) | 1 |
| `SCALE(DENSITY\|SPECTRUM)` | No | Spectral density normalization applied to result values | — |
| `TYPE(window_name)` | No | Window type — 21 options (see below) | — |

**21 window types:**
BARTHANN · BARTLETT · BLACKMAN · BLACKMANHARRIS · BOHMAN · BOXCAR · COSINE · EXPONENTIAL · FLATTOP · GAUSSIAN · GENERAL_COSINE · GENERAL_GAUSSIAN · GENERAL_HAMMING · HAMMING · HANN · KAISER · NUTTALL · PARZEN · TAYLOR · TRIANG · TUKEY

**Window-specific parameters:**

| Window | Required params | Optional params (with defaults) |
|--------|-----------------|----------------------------------|
| `EXPONENTIAL` | — | `CENTER(FLOAT)` default=(size−1)/2, `TAU(FLOAT)` |
| `GAUSSIAN` | `STD(FLOAT)` | — |
| `GENERAL_COSINE` | `COEFF(FLOAT array)` | — |
| `GENERAL_GAUSSIAN` | `SHAPE(FLOAT)`, `SIGMA(FLOAT)` | — |
| `GENERAL_HAMMING` | `ALPHA(FLOAT)` | — |
| `KAISER` | `BETA(FLOAT)` | — |
| `TAYLOR` | — | `NUM_SIDELOBES(int)` default=4, `SIDELOBE_SUPPRESSION(FLOAT)` default=30, `NORM(1\|0)` default=1 |
| `TUKEY` | `ALPHA(FLOAT)` — 0=rectangular window, 1=Hann window | — |

**Output:** same columns as TD_DFFT plus **COLUMN_I** (window index). Same OUTPUT_FMT CONTENT options. No INPUT_FMT.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(res1)
TD_WINDOWDFFT(
  SERIES_SPEC(TABLE_NAME(t1), SERIES_ID(id),
    ROW_AXIS(SEQUENCE(row_i)),
    PAYLOAD(FIELDS(v2), CONTENT(REAL))),
  FUNC_PARAMS(
    WINDOW(SIZE(NUM(15))),
    WINDOW(OVERLAP(2)),
    WINDOW(TYPE(BOHMAN)),
    WINDOW(IS_SYMMETRIC(1)),
    WINDOW(SCALE(SPECTRUM)),
    DFFT(ALGORITHM(SINGLETON)),
    DFFT(ZERO_PADDING_OK(1)),
    DFFT(FREQ_STYLE(K_INTEGRAL)),
    DFFT(HUMAN_READABLE(0))
  ),
  OUTPUT_FMT(CONTENT(COMPLEX))
);
SELECT id, row_i, column_i, ROUND(REAL_v2,6), ROUND(IMAG_v2,6)
FROM res1 ORDER BY 1, 3, 2;
```

---

## Wavelet Transform

### TD_DWT / TD_DWT2D

Forward Discrete Wavelet Transform — decomposes signal into approximation and detail components.

| | TD_DWT | TD_DWT2D |
|---|--------|----------|
| **Primary input** | `SERIES_SPEC` | `MATRIX_SPEC` |
| **Custom filter** | Optional 2nd `SERIES_SPEC` (lo/hi fields, MULTIVAR_REAL) | Optional `SERIES_SPEC` (same) |
| **PART param** | `'a'` (approx only) \| `'d'` (detail only) | Not supported |
| **Output axes** | ROW_I | ROW_I + COLUMN_I |
| **Output columns** | `A_PayloadName` (approx) + `D_PayloadName` (detail) | `AA_` (approx of approx) + `DA_` (detail of approx) + `AD_` (approx of detail) + `DD_` (detail of detail) |
| **Algorithm direction** | — | Vertical (column) first, then horizontal |

**FUNC_PARAMS:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `WAVELET(name)` | Wavelet family name (see Shared Wavelet Families); **required** if no filter series | — |
| `MODE(name)` | Signal extension mode (see Shared Wavelet Families) | — |
| `LEVEL(n)` | Decomposition level; range [1, 15] | 1 |
| `PART('a'\|'d')` | TD_DWT only — output approx or detail only | both |

**INPUT_FMT:** required when using two input series — `ONE2ONE`, `MANY2ONE`, `MATCH`.

**Output:** RETURNS TABLE only — no additional ART layers. Display with SELECT.

```sql
-- TD_DWT with known wavelet
EXECUTE FUNCTION INTO VOLATILE ART(tmpTable)
TD_DWT(
  SERIES_SPEC(TABLE_NAME(dataTable1), SERIES_ID(id),
    ROW_AXIS(SEQUENCE(rowi)),
    PAYLOAD(FIELDS(v), CONTENT(REAL))),
  FUNC_PARAMS(WAVELET('haar'))
);

-- TD_DWT with custom filter (MANY2ONE: many data series, one filter)
EXECUTE FUNCTION INTO VOLATILE ART(tmpTable)
TD_DWT(
  SERIES_SPEC(TABLE_NAME(dataTable1), SERIES_ID(id),
    ROW_AXIS(SEQUENCE(rowi)),
    PAYLOAD(FIELDS(v), CONTENT(REAL))),
  SERIES_SPEC(TABLE_NAME(filterTable), SERIES_ID(id),
    ROW_AXIS(SEQUENCE(seq)),
    PAYLOAD(FIELDS(lo, hi), CONTENT(MULTIVAR_REAL)))
  WHERE id = 1,
  INPUT_FMT(INPUT_MODE(MANY2ONE))
);

-- TD_DWT2D
EXECUTE FUNCTION INTO ART(a1)
TD_DWT2D(
  MATRIX_SPEC(TABLE_NAME(dataTable1), MATRIX_ID(id),
    ROW_AXIS(SEQUENCE(y)), COLUMN_AXIS(SEQUENCE(x)),
    PAYLOAD(FIELDS(v), CONTENT(REAL))),
  FUNC_PARAMS(WAVELET('haar'))
);
```

---

### TD_IDWT / TD_IDWT2D

Inverse DWT — reconstructs original signal from wavelet decomposition coefficients.

| | TD_IDWT | TD_IDWT2D |
|---|---------|-----------|
| **Primary input** | `SERIES_SPEC` (approx + detail fields, MULTIVAR_REAL) | `ART_SPEC` (from TD_DWT2D) — syntax shows MATRIX_SPEC but examples use ART_SPEC |
| **Custom filter** | Optional 2nd `SERIES_SPEC` | Optional `SERIES_SPEC` |
| **Output axes** | ROW_I | ROW_I (doc likely incomplete — probably ROW_I + COLUMN_I) |
| **Output column** | `MAGNITUDE` (reconstructed signal) | `MAGNITUDE` |
| **Algorithm direction** | — | Horizontal (row) first, then vertical — reverse of TD_DWT2D |
| **LEVEL param** | Listed in param table but absent from syntax block — doc inconsistency | Not present |
| **PART param** | Supported | Not supported |
| **No LEVEL in syntax** | — | — |

**FUNC_PARAMS:** WAVELET, MODE, PART — same options as TD_DWT. No LEVEL in syntax block.

**TD_IDWT2D input note:** Syntax block shows `MATRIX_SPEC` but both examples use `ART_SPEC(TABLE_NAME(a1))` taking the TD_DWT2D output ART directly — ART_SPEC chaining is the intended pattern.

**TD_IDWT2D output schema note:** Shows only ROW_I (not ROW_I + COLUMN_I) — likely a doc gap for 2D output.

**INPUT_FMT:** required when using two input series.

Output: RETURNS TABLE only — no additional ART layers.

```sql
-- TD_IDWT with known wavelet (input: approx + detail from TD_DWT)
EXECUTE FUNCTION INTO ART(tmpTable)
TD_IDWT(
  SERIES_SPEC(TABLE_NAME(dataTable1), SERIES_ID(id),
    ROW_AXIS(SEQUENCE(rowi)),
    PAYLOAD(FIELDS(approx, detail), CONTENT(MULTIVAR_REAL))),
  FUNC_PARAMS(WAVELET('haar'))
);

-- TD_IDWT2D chained from TD_DWT2D ART
EXECUTE FUNCTION INTO ART(a2)
TD_IDWT2D(
  ART_SPEC(TABLE_NAME(a1)),
  FUNC_PARAMS(WAVELET('haar'))
);
```

---

## Convolution

### TD_CONVOLVE / TD_CONVOLVE2

Convolve a signal with a filter. Equivalent to the manual TD_DFFT → TD_BINARYSERIESOP → TD_IDFFT pipeline but in one call.

| | TD_CONVOLVE | TD_CONVOLVE2 |
|---|------------|--------------|
| **Input** | Two `SERIES_SPEC` | Two `MATRIX_SPEC` |
| **Input order** | First = signal to filter; second = filter | Order doesn't matter |
| **FUNC_PARAMS** | `ALGORITHM(CONV_SUMMATION\|CONV_DFFT)` — optional | None — auto-selects |
| **Auto algorithm** | CONV_SUMMATION for REAL/MULTIVAR_REAL only; auto-upgrades to CONV_DFFT if first input > 64 or second > 63 entries | Summation for result < 128×128; DFFT for larger |
| **Result inherits** | SERIES_ID from primary | MATRIX_ID from primary |

**INPUT_FMT is mandatory** for both — `ONE2ONE`, `MANY2ONE`, `MATCH`. No OUTPUT_FMT.

**Supported input content types:** REAL, COMPLEX, MULTIVAR_REAL, MULTIVAR_COMPLEX.
Mixing: MULTIVAR_REAL + REAL (one of each) is allowed.

**Output content type:**
- Both inputs REAL or COMPLEX → output COMPLEX
- Either input MULTIVAR → output MULTIVAR_COMPLEX

**Output schema:**
- TD_CONVOLVE: derived-series-identifier + ROW_I + `REAL_PayloadName` + `IMAGINARY_PayloadName`
- TD_CONVOLVE2: derived-matrix-identifier + ROW_I + COLUMN_I + REAL/IMAG or AMPLITUDE/PHASE columns

ARTPRIMARY — display with SELECT. No additional layers.

**TD_CONVOLVE2 doc typo:** syntax elements section header says `TD_CONVOVLE2` (transposed letters).

**TD_CONVOLVE ALGORITHM quote style in examples:** `ALGORITHM("CONV_SUMMATION")` — double quotes.

```sql
-- TD_CONVOLVE (MATCH mode)
EXECUTE FUNCTION INTO VOLATILE ART(ConvRes)
TD_CONVOLVE(
  SERIES_SPEC(TABLE_NAME(timeSeries), SERIES_ID(ID),
    ROW_AXIS(SEQUENCE(SEQ)),
    PAYLOAD(FIELDS(A_REAL, A_IMAG), CONTENT(MULTIVAR_REAL))),
  SERIES_SPEC(TABLE_NAME(filterSeries), SERIES_ID(ID),
    ROW_AXIS(SEQUENCE(SEQ)),
    PAYLOAD(FIELDS(A_REAL, A_IMAG), CONTENT(COMPLEX))),
  FUNC_PARAMS(ALGORITHM("CONV_SUMMATION")),
  INPUT_FMT(INPUT_MODE(MATCH))
);
SELECT * FROM ConvRes;

-- TD_CONVOLVE2 (MATCH mode)
EXECUTE FUNCTION INTO VOLATILE ART(ConvRes2D)
TD_CONVOLVE2(
  MATRIX_SPEC(TABLE_NAME(imageTable), MATRIX_ID(ID),
    ROW_AXIS(SEQUENCE(ROW_SEQ)), COLUMN_AXIS(SEQUENCE(COL_SEQ)),
    PAYLOAD(FIELDS(A), CONTENT(REAL))),
  MATRIX_SPEC(TABLE_NAME(filterMatrix), MATRIX_ID(ID),
    ROW_AXIS(SEQUENCE(ROW_SEQ)), COLUMN_AXIS(SEQUENCE(COL_SEQ)),
    PAYLOAD(FIELDS(A), CONTENT(REAL))),
  INPUT_FMT(INPUT_MODE(MATCH))
);
SELECT * FROM ConvRes2D;
```

---

## Spectral Analysis

### TD_POWERSPEC

Estimates the power spectrum — how much energy/power is present at each frequency.

**Input:** Single SERIES_SPEC; REAL, COMPLEX, MULTIVAR_REAL, or MULTIVAR_COMPLEX.

**FUNC_PARAMS:**

| Parameter | Options | Default |
|-----------|---------|---------|
| `FREQ_STYLE` | K_INTEGRAL, K_SAMPLE_RATE, K_RADIANS, K_HERTZ, **K_PERIODICITY** | K_INTEGRAL |
| `HERTZ_SAMPLE_RATE` | FLOAT | — (required with K_HERTZ) |
| `ZERO_PADDING_OK` | 1 \| 0 | 1 |
| `ALGORITHM` | AUTOCORR, AUTOCOV, FOURIER, INCRFOURIER | auto |
| `INCRFOURIER_PARAM` | `INTERVAL_LENGTH(n), SPACING_INTERVAL(k)` | — (required with INCRFOURIER) |
| `WINDOW` | `WINDOW_NAME(TUKEY\|BARTLETT\|PARZEN\|WELCH\|NONE)` | NONE |
| `WINDOW_PARAM` | INTEGER (alpha) | — (required with TUKEY only) |

No INPUT_FMT or OUTPUT_FMT.

**Output:** derived-series-identifier + ROW_I + `SPECTRAL_DENSITY_PayloadName`
- REAL/MULTIVAR_REAL input → field name = payload field name
- COMPLEX/MULTIVAR_COMPLEX input → `SPECTRAL_DENSITY_PAYLOAD1`, `SPECTRAL_DENSITY_PAYLOAD2`, ...
- Output type: REAL (from REAL/COMPLEX), MULTIVAR_REAL (from MULTIVAR)

**Quote style in examples:** single quotes — `FREQ_STYLE ('K_PERIODICITY')`.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(PowerSpecResults)
TD_POWERSPEC(
  SERIES_SPEC(TABLE_NAME(TestRiver), SERIES_ID(BuoyID),
    ROW_AXIS(SEQUENCE(N_SeqNo)),
    PAYLOAD(FIELDS(MAGNITUDE), CONTENT(REAL))),
  FUNC_PARAMS(
    FREQ_STYLE ('K_PERIODICITY'),
    ALGORITHM ('AUTOCORR'),
    WINDOW(WINDOW_NAME ('BARTLETT'))
  )
);
SELECT TOP 5 * FROM PowerSpecResults ORDER BY SPECTRAL_DENSITY_MAGNITUDE DESC;
```

---

### TD_LINESPEC

Estimates the line spectrum by computing sinusoidal component magnitudes. Simpler than TD_POWERSPEC (no algorithm or windowing options); unique `INCLUDE_COEFF` flag.

**Input:** Single SERIES_SPEC; REAL, COMPLEX, MULTIVAR_REAL, or MULTIVAR_COMPLEX.

**FUNC_PARAMS:**

| Parameter | Options | Default |
|-----------|---------|---------|
| `FREQ_STYLE` | K_INTEGRAL, K_SAMPLE_RATE, K_RADIANS, K_HERTZ, K_PERIODICITY | K_INTEGRAL |
| `HERTZ_SAMPLE_RATE` | FLOAT | — (required with K_HERTZ) |
| `ZERO_PADDING_OK` | 1 \| 0 | 1 |
| `INCLUDE_COEFF` | 1 \| 0 | 0 — include αk and βk coefficient columns in output |

**Formula:** magnitude at frequency k = `(n/2) × (αk² + βk²)`

Same output schema as TD_POWERSPEC (SPECTRAL_DENSITY_PayloadName), same output type logic. No INPUT_FMT or OUTPUT_FMT.

**Quote style in examples:** double quotes — `FREQ_STYLE("K_PERIODICITY")`.

**TD_POWERSPEC vs TD_LINESPEC:** use TD_POWERSPEC when algorithm control or windowing is needed; TD_LINESPEC for simpler line spectrum or when αk/βk coefficients are wanted.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(LineSpecResults)
TD_LINESPEC(
  SERIES_SPEC(TABLE_NAME(TestRiver), SERIES_ID(BuoyID),
    ROW_AXIS(SEQUENCE(N_SeqNo)),
    PAYLOAD(FIELDS(MAGNITUDE), CONTENT(REAL))),
  FUNC_PARAMS(FREQ_STYLE("K_PERIODICITY"))
);
SELECT * FROM LineSpecResults WHERE SPECTRAL_DENSITY_MAGNITUDE > 6000.0;
```

---

### TD_GENSERIES4SINUSOIDS

Generates a synthetic series containing only the specified sinusoidal periodicities. Subtract from the original to remove those periodicities.

**Input:** Single SERIES_SPEC; **REAL only** (univariate only).

**FUNC_PARAMS:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `PERIODICITIES(f [,...])` | Yes | Comma-separated FLOAT periodicity values — from TD_LINESPEC/TD_POWERSPEC K_PERIODICITY output |

**OUTPUT_FMT:** `INDEX_STYLE(NUMERICAL_SEQUENCE | FLOW_THROUGH)`; default NUMERICAL_SEQUENCE.

**Output:** derived-series-identifier + ROW_I + `MAGNITUDE_PayloadName` (e.g., `MAGNITUDE_BEER_SALES`).
REAL output. ARTPRIMARY — display with SELECT.

**Doc typo:** syntax shows `FUNC PARAMS` (space) — should be `FUNC_PARAMS`.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(GEN_SERIES)
TD_GENSERIES4SINUSOIDS(
  SERIES_SPEC(TABLE_NAME(ProductionData),
    ROW_AXIS(TIMECODE(TD_TIMECODE)),
    SERIES_ID(ProductID),
    PAYLOAD(FIELDS(BEER_SALES), CONTENT(REAL))),
  FUNC_PARAMS(PERIODICITIES(0.523, 1.4367)),
  OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
SELECT * FROM GEN_SERIES;
-- Then subtract: TD_BINARYSERIESOP with MATHOP(SUB) to remove these periodicities
```

---

## Symbolic Representation

### TD_SAX

Transforms time series to symbols using Piecewise Aggregate Approximation (PAA) + Symbolic Aggregate approXimation (SAX). Useful for motif discovery, anomaly detection, and dimensionality reduction.

**Input:** REAL or MULTIVAR_REAL only.

**FUNC_PARAMS:**

| Parameter | Applies to | Description | Default |
|-----------|-----------|-------------|---------|
| `WINDOW_TYPE(GLOBAL\|SLIDING)` | Both | GLOBAL: one mean/std for entire series; SLIDING: recomputes per window | GLOBAL |
| `OUTPUT_TYPE(STRING\|BITMAP\|O_CHARS)` | Both | Symbol output format | STRING |
| `ALPHABET_SIZE(n)` | Both | Symbol count; range [2, 20]; alphabet is letters a–t | 4 (abcd) |
| `MEAN(f [,...])` | Both | Pre-supply global mean per payload; nth value → nth payload; single value → all payloads | computed |
| `STD_DEV(f [,...])` | Both | Pre-supply global std dev per payload | computed |
| `BREAKPOINTS(f [,...])` | Both | Custom SAX breakpoints | — |
| `CODE_STATS(1\|0)` | Both | Include Mean_PayloadName + Std_dev_PayloadName in output | 0 |
| `POINTS_PER_SYMBOL(n)` | GLOBAL only | Data points compressed to one SAX symbol; > 0 | 1 |
| `BITMAP_LEVEL(1-4)` | BITMAP only | Consecutive symbols per bitmap entry (level 1 = 'a','b'; level 2 = 'aa','ab',...) | 2 |
| `WINDOW_SIZE(n)` | SLIDING only | Window size in data points; **required** if SLIDING; max 64000 | — |
| `SYMBOLS_PER_WINDOW(n)` | SLIDING only | SAX symbols generated per window; > 0 | 1 |
| `OUTPUT_FREQUENCY(n)` | SLIDING only | Points window slides between successive outputs; > 0 | 1 |

**Output columns:**

| OUTPUT_TYPE | Column name | Data type |
|-------------|-------------|-----------|
| STRING | `SAX_Code_PayloadName` | VARCHAR(64000) |
| BITMAP | `SAX_BITMAP_PayloadName` | VARCHAR(64000) JSON |
| O_CHARS | `SAX_SYMBOL_PayloadName` | CHAR(2) UNICODE |

With `CODE_STATS(1)`: also adds `Mean_PayloadName` (FLOAT) + `Std_dev_PayloadName` (FLOAT).

**OUTPUT_FMT:** `INDEX_STYLE(NUMERICAL_SEQUENCE)` only. ARTPRIMARY — display with SELECT.

```sql
-- GLOBAL window: pre-supply mean/std, multiple payload fields
EXECUTE FUNCTION INTO VOLATILE ART(outstr)
TD_SAX(
  SERIES_SPEC(TABLE_NAME(finance_data3), ROW_AXIS(SEQUENCE(period)),
    SERIES_ID(id),
    PAYLOAD(FIELDS(expenditure, income, investment), CONTENT(MULTIVAR_REAL)))
  WHERE id = 3,
  FUNC_PARAMS(
    WINDOW_TYPE(GLOBAL),
    OUTPUT_TYPE(STRING),
    POINTS_PER_SYMBOL(2),
    ALPHABET_SIZE(10),
    CODE_STATS(1),
    MEAN(2045.166666, 2387.416666, 759.083333),
    STD_DEV(256.612489, 317.496587, 113.352594)
  )
);
SELECT * FROM outstr;
-- Output: SAX_Code_expenditure, SAX_Code_income, SAX_Code_investment
--       + Mean_expenditure, Std_dev_expenditure, ...

-- SLIDING window
EXECUTE FUNCTION INTO VOLATILE ART(outstr)
TD_SAX(
  SERIES_SPEC(TABLE_NAME(finance_data3), ROW_AXIS(SEQUENCE(period)),
    SERIES_ID(id),
    PAYLOAD(FIELDS(expenditure, income, investment), CONTENT(MULTIVAR_REAL)))
  WHERE id = 3,
  FUNC_PARAMS(
    WINDOW_TYPE(SLIDING),
    WINDOW_SIZE(4),
    SYMBOLS_PER_WINDOW(5),
    CODE_STATS(1)
  )
);
SELECT * FROM outstr;
-- One output row per window slide (OUTPUT_FREQUENCY default=1)
```
