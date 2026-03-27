# Teradata UAF — General Utility Functions

Utility functions support setup, inspection, and visualization tasks across the UAF framework. Unlike the core analytics functions, they use several different invocation patterns — noted for each function below.

> **Read `uaf-concepts` first** for SERIES_SPEC, MATRIX_SPEC, ART_SPEC syntax and the standard `EXECUTE FUNCTION INTO ART` execution pattern.

---

## Invocation Patterns in This File

| Pattern | Functions |
|---------|-----------|
| `EXECUTE FUNCTION INTO [VOLATILE] ART(name)` | TD_INPUTVALIDATOR, TD_MINFO, TD_SINFO, TD_TRACKINGOP |
| `EXECUTE FUNCTION` (returns result directly, no ART) | TD_MATRIX2IMAGE, TD_PLOT |
| `SELECT * FROM function(ON ... USING ...)` | TD_CONVERTTABLEFORUAF, TD_IMAGE2MATRIX |
| `CALL function(params)` | TD_COPYART, TD_FILTERFACTORY1D |
| `SELECT scalar_function(col)` | TD_ISFINITE, TD_ISINF, TD_ISNAN |

> TD_EXTRACT_RESULTS is covered in `uaf-concepts`.

---

## TD_SINFO

Returns one metadata row per series instance — index type, range, entry count, discreteness, sample interval, and payload magnitude statistics. Use before analysis to understand data shape and identify quality issues.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(sinfo_results)
TD_SINFO(
    SERIES_SPEC(
        TABLE_NAME(OCEAN_BUOYS),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(Ocean_Name, BuoyID),
        PAYLOAD(FIELDS(Salinity), CONTENT(REAL))
    )
);

SELECT * FROM sinfo_results;
```

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | BIGINT | Always 1 (one row per series) |
| `INDEX_DT` | VARCHAR(20) | Index data type: TIMESTAMP, DATE, INTEGER, FLOAT |
| `INDEX_BEGIN` | Varies | First index value |
| `INDEX_END` | Varies | Last index value |
| `NUM_ENTRIES` | INTEGER | Total number of series entries |
| `DISCRETE` | SMALLINT | 1 = regular/discrete; 0 = irregular |
| `SAMPLE_INTERVAL` | VARCHAR(30) | Sampling interval (or average if irregular) |
| `CONTENT` | VARCHAR(20) | Payload content type |
| `MIN_MAG_<field>` | FLOAT | Minimum payload magnitude per field |
| `MAX_MAG_<field>` | FLOAT | Maximum payload magnitude per field |
| `AVG_MAG_<field>` | FLOAT | Average payload magnitude per field |
| `RMS_MAG_<field>` | FLOAT | Root mean square of payload per field |
| `HAS_NULL_NAN_INF` | VARCHAR(5) | Whether series contains NULLs, NaNs, or Inf values |

---

## TD_MINFO

Returns one metadata row per matrix instance — same purpose as TD_SINFO but for 2D matrices. Reports row axis, column axis, and payload statistics separately.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(minfo_results)
TD_MINFO(
    MATRIX_SPEC(
        TABLE_NAME(OCEAN_BUOYS),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        COLUMN_AXIS(SEQUENCE(SPACE)),
        MATRIX_ID(Ocean_Name, BuoyID),
        PAYLOAD(FIELDS(Salinity), CONTENT(REAL))
    )
);

SELECT * FROM minfo_results;
```

### Output schema (key columns)

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from MATRIX_ID |
| `ROW_INDEX_DT` / `COLUMN_INDEX_DT` | VARCHAR | Index data types |
| `ROW_INDEX_BEGIN` / `COLUMN_INDEX_BEGIN` | Varies | First index values |
| `ROW_INDEX_END` / `COLUMN_INDEX_END` | Varies | Last index values |
| `ROW_INDEX_NUM_ENTRIES` | FLOAT | Entry count along row axis |
| `COLUMN_INDEX_NUM_ENTRIES` | INTEGER | Entry count along column axis |
| `ROW_INDEX_DISCRETE` / `COLUMN_INDEX_DISCRETE` | SMALLINT | 1 = regular; 0 = irregular |
| `ROW_INDEX_SAMPLE_INTERVAL` / `COLUMN_INDEX_SAMPLE_INTERVAL` | VARCHAR(30) | Interval (or average) |
| `CONTENT` | VARCHAR(20) | Payload content type |
| `MIN_MAG_<field>` / `MAX_MAG_<field>` / `AVG_MAG_<field>` / `RMS_MAG_<field>` | FLOAT | Payload magnitude stats per field |
| `HAS_NULL_NAN_INF` | VARCHAR(5) | Null/NaN/Inf indicator |
| `MAL_FORM_MATRIX` | VARCHAR(25) | `WELL_FORM` or `MAL_FORM` |

---

## TD_INPUTVALIDATOR

Validates series or matrix data before analysis. Identifies instances with non-discrete indexing (duplicates, inconsistent intervals) and optionally flags NULL/NaN/Inf payload values.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(validation_results)
TD_INPUTVALIDATOR(
    SERIES_SPEC(
        TABLE_NAME(BuoyData_Mix),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(OceanName, BuoyId),
        PAYLOAD(FIELDS(Salinity), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        FAILURE_MODE('FUNC_FIRST'),   -- FUNC_FIRST: first bad row only; FUNC_ALL: all bad rows
        VALIDATE_PAYLOAD(1)           -- 0 = skip payload check (default); 1 = check for NULL/NaN/Inf
    )
);
```

### Output schema

| Column | Description |
|--------|-------------|
| `derived-series-identifier` | Inherited from SERIES_ID or MATRIX_ID |
| `ROW_I` / `COLUMN_I` | Index of the invalid row |
| `payload-field-name` | Payload field values at the invalid row |
| `ERROR_INFO` | Error message: duplicate row, inconsistent interval, malformed matrix, infinite index value, etc. |

---

## TD_CONVERTTABLEFORUAF

Converts a regular Teradata table into UAF-compatible series or matrix format. Use this when source data exists in a standard row-oriented table and needs to be passed to UAF functions.

**Invocation:** SQL-MR table operator (`SELECT * FROM function(ON ... USING ...)`)

```sql
-- Convert to COMPLEX matrix
SELECT * FROM TD_CONVERTTABLEFORUAF(
    ON source_table AS INPUTTABLE
    USING
        TABLETYPE('MATRIX')     -- 'MATRIX' or 'SERIES'
        CONTENT('COMPLEX')      -- see content types below
        ID(1)                   -- optional: series/matrix identifier column number
) AS t;
```

### CONTENT options

| Value | Description |
|-------|-------------|
| `REAL` | Real floating-point numbers |
| `COMPLEX` | Complex numbers (real + imaginary pair); output columns prefixed `REAL_`, `IMG_` |
| `AMPLPHASE` | Polar complex (amplitude + phase); output columns prefixed `AMPL_`, `PHASE_` |
| `MULTIVARREAL` | Vector of real numbers; columns prefixed `REAL_` |
| `MULTIVARCOMPLEX` | Vector of complex numbers; columns prefixed `REAL_`, `IMG_` |
| `MULTIVARAMPLPHASE` | Vector of polar complex; columns prefixed `AMPL_`, `PHASE_` |
| `ADHOC` | Arbitrary non-LOB data; no column renaming |

> Matrix output has columns: identifier, ROW_ID, COL_ID, content columns.
> Series output has columns: identifier, ROW_ID, content columns.

---

## TD_COPYART

Creates a copy of an existing ART. Standard `CREATE TABLE AS` cannot be used on ARTs because they can be multi-layered.

**Invocation:** `CALL`

```sql
CALL TD_COPYART(
    'source_db',        -- SRC_DATABASENAME
    'source_art',       -- SRC_TABLENAME
    'dest_db',          -- DST_DATABASENAME
    'dest_art',         -- DST_TABLENAME
    'dest_map',         -- DST_MAPNAME (MAP name for destination)
    'true'              -- DST_ISPERMTABLE: 'true' = permanent; 'false' = volatile
);
```

---

## TD_FILTERFACTORY1D

Creates finite impulse response (FIR) filter coefficients and writes them into an existing table. The table is then referenced by TD_CONVOLVE or TD_WINDOWDFFT in the DSP functions.

**Invocation:** `CALL`

The target table must already exist with columns: `ID BIGINT`, `ROW_I BIGINT`, `MAG FLOAT`, `DESCRIPTION VARCHAR`.

```sql
CALL MyDB.TD_FILTERFACTORY1D(
    'mydb',             -- DATABASENAME
    'filters',          -- TABLENAME (must exist; rows are inserted)
    102,                -- FILTERID
    'HIGHPASS',         -- FILTERTYPE: LOWPASS | HIGHPASS | BANDPASS | BANDSTOP
    NULL,               -- WINDOWTYPE (optional): BLACKMAN | HAMMING | BARTLETT | HANNING
    401,                -- FILTERLENGTH (optional; overrides TRANSITIONBANDWIDTH)
    NULL,               -- TRANSITIONBANDWIDTH (optional; FLOAT > 0)
    NULL,               -- LOWCUTOFF (optional; required for BANDPASS/BANDSTOP)
    85.0,               -- HIGHCUTOFF (optional; required for BANDPASS/BANDSTOP)
    200,                -- SAMPLINGFREQUENCY (required; FLOAT > 0)
    'HIGHPASS filter at 85Hz'  -- FILTERDESCRIPTION (optional)
);
```

### FILTERTYPE guide

| Type | Removes | Requires |
|------|---------|----------|
| `LOWPASS` | Frequencies above HIGHCUTOFF | HIGHCUTOFF |
| `HIGHPASS` | Frequencies below LOWCUTOFF | LOWCUTOFF |
| `BANDPASS` | Below LOWCUTOFF and above HIGHCUTOFF | Both cutoffs |
| `BANDSTOP` | Between LOWCUTOFF and HIGHCUTOFF | Both cutoffs |

> Output: one row per coefficient (`ROW_I` 0..N), with `MAG` = coefficient value and `DESCRIPTION` on row 0 only.

---

## TD_IMAGE2MATRIX

Converts JPEG or PNG images stored as BLOBs into matrix format for UAF processing. Maximum 16MB per image, 4,000,000 pixels.

**Invocation:** SQL-MR table operator

```sql
-- Grayscale output (Y, X, GRAY columns)
CREATE TABLE matrix_table AS (
    SELECT * FROM TD_IMAGE2MATRIX(
        ON (SELECT id, image FROM image_table)
        USING OUTPUT('gray')    -- 'gray' (default) or 'rgb'
    ) t
) WITH DATA PRIMARY INDEX (id, y, x);

-- RGB output (Y, X, RED, GREEN, BLUE columns)
CREATE TABLE matrix_table AS (
    SELECT * FROM TD_IMAGE2MATRIX(
        ON (SELECT id, image FROM image_table)
        USING OUTPUT('rgb')
    ) t
) WITH DATA PRIMARY INDEX (id, y, x);
```

> Use a multi-column primary index `(id, y, x)` to reduce hash conflicts.

---

## TD_MATRIX2IMAGE

Converts a UAF matrix back to a JPEG, PNG, or SVG image using colormaps. Supports grayscale, RGB (three-payload), and colormap rendering. Returns a BLOB.

```sql
-- Grayscale with fixed range
EXECUTE FUNCTION TD_MATRIX2IMAGE(
    MATRIX_SPEC(
        TABLE_NAME(matrix_table),
        MATRIX_ID(id),
        ROW_AXIS(SEQUENCE(y)),
        COLUMN_AXIS(SEQUENCE(x)),
        PAYLOAD(FIELDS(GRAY), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        IMAGE('PNG'),           -- PNG (default) | JPG | SVG
        TYPE('GRAY'),           -- GRAY | RGB | COLORMAP
        RANGE(0, 255)           -- clip range for GRAY/COLORMAP (default: data min/max)
    )
);

-- RGB image (three payloads)
EXECUTE FUNCTION TD_MATRIX2IMAGE(
    MATRIX_SPEC(
        TABLE_NAME(matrix_table),
        MATRIX_ID(id),
        ROW_AXIS(SEQUENCE(y)),
        COLUMN_AXIS(SEQUENCE(x)),
        PAYLOAD(FIELDS(RED, GREEN, BLUE), CONTENT(MULTIVAR_REAL))
    ),
    FUNC_PARAMS(
        RED(0, 255), GREEN(0, 255), BLUE(0, 255)
    )
);
```

### FUNC_PARAMS reference

| Parameter | Description |
|-----------|-------------|
| `IMAGE` | Output format: `PNG` (default), `JPG`, `SVG` |
| `TYPE` | `GRAY` (single payload), `RGB` (three payloads), `COLORMAP` (single payload, false-color) |
| `COLORMAP` | Colormap name when TYPE = COLORMAP (default: `viridis`); case-sensitive |
| `RANGE(min, max)` | Payload value range for GRAY/COLORMAP scaling |
| `RED/GREEN/BLUE(min, max)` | Per-channel range for RGB type |
| `FLIPX(0\|1)` | Flip image horizontally |
| `FLIPY(0\|1)` | Flip image vertically |

> Output: single row with `ROW_I=0`, `COLUMN_I=0`, `IMAGE BLOB`.

---

## TD_PLOT

Generates charts in-database and returns a BLOB (PNG, JPG, or SVG). No data leaves the platform — the visualization is built entirely on the AMPs.

Supported chart types: `line`, `scatter`, `bar`, `mesh`, `wiggle` (seismic), `geometry`. Supports up to 1024 series per plot and composite multi-panel layouts.

```sql
-- Simple line chart
EXECUTE FUNCTION TD_PLOT(
    SERIES_SPEC(
        TABLE_NAME(OCEAN_BUOYS),
        ROW_AXIS(SEQUENCE(Salinity)),
        SERIES_ID(BuoyID),
        PAYLOAD(FIELDS(Temperature), CONTENT(REAL))
    ) WHERE BuoyID = 33,
    FUNC_PARAMS(
        TITLE('Temperature vs Salinity'),
        PLOTS[(
            TYPE('line'),
            FORMAT('r--')       -- matplotlib format string
        )],
        WIDTH(1024),
        HEIGHT(768)
    )
);
```

### Key FUNC_PARAMS

| Parameter | Description |
|-----------|-------------|
| `TITLE` | Chart title |
| `IMAGE` | `PNG` (default), `JPG`, `SVG` |
| `WIDTH` / `HEIGHT` | Pixels; range 400–4096; total ≤ 4,000,000 pixels |
| `DPI` | Dots per inch |
| `LAYOUT(cols, rows)` | Enable composite multi-panel layout |
| `PLOTS[(...)]` | Array of plot entries (required for composite layouts) |
| `TYPE` | `line`, `scatter`, `bar`, `mesh`, `wiggle`, `geometry`, `corr` |
| `XLABEL` / `YLABEL` | Axis labels |
| `XRANGE` / `YRANGE` | Axis ranges |
| `LEGEND` | Legend position: `upper right`, `lower left`, `best`, etc. |
| `COLORMAP(NAME(...), COLORBAR(0\|1), RANGE(min, max))` | Mesh/geometry color settings |
| `WIGGLE(FILL(0\|1), SCALE(float))` | Seismic wiggle settings |

> Color values follow matplotlib conventions: hex (`#ff1122`), CSS4 names, `xkcd:tan`, `tab:blue`, `C0`–`C9`.
> Output: one row per series with `IMAGE BLOB`.

---

## TD_TRACKINGOP

Tracks an object's movement using geospatial coordinates and computes distance, speed, and time metrics. Designed for fleet, vessel, and individual tracking use cases.

The PAYLOAD must have exactly these first three fields in order:
1. Arrival time (TIMESTAMP or TIMESTAMP WITH TIME ZONE)
2. Departure time (TIMESTAMP or TIMESTAMP WITH TIME ZONE)
3. Location (geospatial type — POINT)

```sql
EXECUTE FUNCTION INTO VOLATILE ART(tracking_results)
TD_TRACKINGOP(
    SERIES_SPEC(
        TABLE_NAME(TrainTracking),
        ROW_AXIS(TIMECODE(ArrivalTime)),
        SERIES_ID(train_id, schedule_date),
        PAYLOAD(
            FIELDS(ArrivalTime, DepartureTime, geoTag),
            CONTENT(MULTIVAR_ANYTYPE)
        )
    ),
    FUNC_PARAMS(
        DISTANCE(1),        -- 1 = compute total track distance
        SPEED(1),           -- 1 = compute min/avg/max speed
        TIME_SPENT(1),      -- 1 = compute run time and trip time
        METRIC(1)           -- 1 = kilometers; 0 = miles (default)
    )
);

SELECT * FROM tracking_results;
```

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Row index starting at 0 |
| `TRACK_DISTANCE` | FLOAT | Total trip distance (km or miles) |
| `TRACK_PATH` | LINESTRING | Series of geospatial points along the route |
| `MIN_SPEED` | FLOAT | Minimum speed during trip |
| `AVG_SPEED` | FLOAT | Average speed during trip |
| `MAX_SPEED` | FLOAT | Maximum speed during trip |
| `RUN_TIME` | FLOAT | Actual movement time in minutes |
| `TRIP_TIME` | FLOAT | Total elapsed trip time in minutes |

---

## TD_ISFINITE / TD_ISINF / TD_ISNAN

Scalar predicates for validating floating-point values. Use in WHERE clauses or SELECT lists to detect bad values before feeding data into UAF functions.

**Invocation:** `SELECT` (standard scalar function call)

```sql
-- Check individual values
SELECT StoreID, SEQ, TD_ISFINITE(sales) AS is_finite FROM orders1;

-- Filter to clean rows only
SELECT * FROM orders1 WHERE TD_ISFINITE(sales) = 1;

-- Count bad values
SELECT COUNT(*) FROM orders1 WHERE TD_ISFINITE(sales) = 0;
```

| Function | Returns 1 when | Returns 0 when |
|----------|---------------|----------------|
| `TD_ISFINITE(x)` | x is a normal finite float | x is NaN or ±Infinity |
| `TD_ISINF(x)` | x is ±Infinity | x is finite or NaN |
| `TD_ISNAN(x)` | x is NaN (Not a Number) | x is finite or infinite |

> Input: FLOAT. These are typically used to gate data before passing it to `EXECUTE FUNCTION INTO ART` pipelines.
