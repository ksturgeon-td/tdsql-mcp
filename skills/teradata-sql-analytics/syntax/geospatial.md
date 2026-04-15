# Teradata Geospatial — ST_Geometry Types and Functions

Teradata Vantage implements SQL/MM Spatial (ISO/IEC 13249-3) for storing, querying, and manipulating geospatial data. The core type is `ST_Geometry`, a UDT stored in `SYSUDTLIB`.

## Required Privileges

```sql
GRANT UDTUSAGE ON SYSUDTLIB TO username;
GRANT EXECUTE FUNCTION ON SYSSPATIAL TO username;
GRANT SELECT ON SYSSPATIAL TO username;
GRANT EXECUTE PROCEDURE ON SYSSPATIAL TO username;
```

---

## Geometry Types

| Type | Dimension | Description |
|------|-----------|-------------|
| `ST_Point` | 0D | Single location in 2D or 3D space |
| `ST_LineString` | 1D | Sequence of points with linear interpolation |
| `ST_Polygon` | 2D | One exterior ring + zero or more interior rings (holes) |
| `ST_GeomCollection` | — | Collection of ST_Geometry values |
| `ST_MultiPoint` | 0D | Collection of ST_Point values |
| `ST_MultiLineString` | 1D | Collection of ST_LineString values |
| `ST_MultiPolygon` | 2D | Collection of non-overlapping ST_Polygon values |
| `GeoSequence` | 1D | ST_LineString extension with timestamps and user fields (tracking data) |
| `MBR` | — | Minimum bounding rectangle (2D) |
| `MBB` | — | Minimum bounding box (3D) |

---

## Data Types

### ST_Geometry Column Definition

```sql
[SYSUDTLIB.] ST_GEOMETRY [ ( maxlength ) ] [ INLINE LENGTH integer ] [ attribute ]
```

- Default `maxlength`: ~16 MB (~1 million points)
- Default `INLINE LENGTH`: ~10,000 bytes — data ≤ inline length stored in row; larger stored as LOB
- Max 6 LOB columns per table applies to ST_Geometry columns stored as LOBs
- To avoid LOB overhead (better performance with UDFs): set `maxlength = INLINE LENGTH`

```sql
-- Examples
shape ST_Geometry                        -- default: 16MB max, 10KB inline
shape ST_Geometry(250000)                -- 250KB max, 10KB inline (LOB if >10KB)
shape ST_Geometry(8000)                  -- 8KB max, always inline (non-LOB)
shape ST_Geometry(8000) INLINE LENGTH 2000  -- 8KB max, LOB if >2KB
```

### MBR Column Definition

```sql
[SYSUDTLIB.] MBR
```

- Stored/returned as VARCHAR(256): `(xmin, ymin, xmax, ymax)`
- Cast: `CAST(shape_mbr AS VARCHAR(256))`
- Constructor: `NEW MBR(xmin, ymin, xmax, ymax)`

### MBB Column Definition

```sql
[SYSUDTLIB.] MBB
```

- Stored/returned as VARCHAR(340): `(xmin, ymin, zmin, xmax, ymax, zmax)`
- Constructor: `NEW MBB(xmin, ymin, zmin, xmax, ymax, zmax)`

---

## Data Formats

### Well-Known Text (WKT) — Default

WKT literals can be inserted directly into ST_Geometry columns:

```sql
INSERT INTO sample_shapes VALUES (1001, 'POINT(10 20)');
INSERT INTO sample_shapes VALUES (1002, 'POINT EMPTY');
INSERT INTO sample_shapes VALUES (1003, 'LINESTRING(1 1, 2 2, 3 3)');
INSERT INTO sample_shapes VALUES (1004, 'POLYGON((0 0, 0 20, 20 20, 20 0, 0 0),
                                            (5 5, 5 10, 10 10, 10 5, 5 5))');
INSERT INTO sample_shapes VALUES (1005, 'MULTIPOINT((1 1), (6 3), (20 1))');
INSERT INTO sample_shapes VALUES (1006, 'MULTILINESTRING((1 1, 1 3, 6 3),(10 5, 20 1))');
INSERT INTO sample_shapes VALUES (1007, 'MULTIPOLYGON(((1 1, 1 3, 6 3, 6 0, 1 1)),
                                                      ((10 5, 10 10, 20 10, 20 5, 10 5)))');
INSERT INTO sample_shapes VALUES (1008, 'GEOMETRYCOLLECTION(POINT(10 10),
                                                            LINESTRING(15 15, 20 20))');
-- GeoSequence: (points), (timestamps), (linkIDs), (count, user_fields...)
INSERT INTO sample_shapes VALUES (1009,
  'GEOSEQUENCE((10 20, 30 40, 50 60),
               (2007-08-22 12:05:23.56, 2007-08-22 12:08:25.14, 2007-08-22 12:11:41.52),
               (1, 2, 3),
               (2, 10, 12, 11, 18, 21, 19))');
```

3D geometries: add z coordinate to each point: `POINT(10 20 30)`, `LINESTRING(0 0 0, 1 1 1)`.

### Well-Known Binary (WKB)

WKB type codes: 1–7 for 2D (Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeomCollection), 1001–1007 for 3D, 200 for GeoSequence.

### Extended Formats (EWKT/EWKB) — SRID-aware

```
SRID=4326;POINT(10 20)
SRID=35234;LINESTRING(10 20, 40 50)
```

Requires a "SRID" transform group (`ST_WellKnownTextSRID`, `TD_GEO_VARCHAR_SRID`, etc.).

---

## Transform Groups

Controls how ST_Geometry is exported/imported to/from client applications.

| Transform Group | Import/Export Type | Format | Default |
|---|---|---|---|
| `ST_WellKnownText` | CLOB | WKT | **Yes** |
| `ST_WellKnownBinary` | BLOB | WKB | No |
| `TD_GEO_VARCHAR` | VARCHAR(64000) | WKT | No |
| `TD_GEO_VARBYTE` | VARBYTE(64000) | WKB | No |
| `ST_WellKnownTextSRID` | CLOB | EWKT (WKT + SRID) | No |
| `ST_WellKnownBinarySRID` | BLOB | EWKB (WKB + SRID) | No |
| `TD_GEO_VARCHAR_SRID` | VARCHAR(64000) | EWKT | No |
| `TD_GEO_VARBYTE_SRID` | VARBYTE(64000) | EWKB | No |

Override for session: `SET TRANSFORM GROUP FOR TYPE ST_Geometry TO TD_GEO_VARCHAR;`
Override for user: specify in `CREATE/MODIFY USER` or `CREATE/MODIFY PROFILE`.

Inspect current settings:
```sql
EXEC SYSUDTLIB.HelpCurrentSessionTransforms;
EXEC SYSUDTLIB.HelpCurrentUserTransforms;
EXEC SYSUDTLIB.HelpUserTransforms('username');
```

---

## Constructors

### ST_Geometry from WKT/WKB

```sql
-- VARCHAR form (max 64000 bytes)
NEW ST_Geometry('POINT(10 20)')
NEW ST_Geometry('LINESTRING(1 1, 2 2)', 4326)   -- optional SRID

-- CLOB form (up to ~16MB)
USING (a INTEGER, b CLOB(60000))
INSERT INTO sample_shapes VALUES (:a, NEW ST_Geometry(:b));

-- VARBYTE form (max 64000 bytes)
USING (a INTEGER, b VARBYTE(60000))
INSERT INTO sample_shapes VALUES (:a, NEW ST_Geometry(:b));

-- BLOB form (up to ~16MB)
USING (a INTEGER, b BLOB(60000))
INSERT INTO sample_shapes VALUES (:a, NEW ST_Geometry(:b));
```

**Rule:** Use CLOB/BLOB constructors when WKT/WKB > 64000 bytes. For WKT > 64000 bytes returned from ST_AsText, use WKB instead (ST_AsBinary).

### ST_Point Constructor (coordinate form)

```sql
NEW ST_Geometry('ST_POINT', 10.0, 20.0)           -- 2D, SRID=0
NEW ST_Geometry('ST_POINT', 10.0, 20.0, 1699)     -- 2D with SRID
NEW ST_Geometry('ST_POINT', 10.0, 20.0, 5.0, 1699) -- 3D (zcoord requires asrid)
```

### MBR / MBB Constructors

```sql
NEW MBR(xmin, ymin, xmax, ymax)
NEW MBB(xmin, ymin, zmin, xmax, ymax, zmax)

INSERT INTO sample_MBRs VALUES (0, NEW MBR(5, 5, 10, 10));
INSERT INTO sample_MBBs VALUES (0, NEW MBB(5, 5, 5, 10, 10, 10));
```

### CAST from WKT

```sql
INSERT INTO sample_shapes VALUES (1001, CAST('LINESTRING(1 1, 2 2)' AS ST_Geometry));
```

---

## ST_Geometry Instance Methods

All methods are called as `column.method()` or `NEW ST_Geometry('...').method()`.

**Performance note:** For 3D geometries, most methods drop z coordinates — use `Make_2D()` on results when z is not needed.

### Conversion and Inspection

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_AsText()` | CLOB | WKT representation |
| `ST_AsBinary()` | BLOB | WKB representation (max ~16MB) |
| `ST_GeometryType()` | VARCHAR(128) | `'ST_Point'`, `'ST_LineString'`, etc. |
| `ST_CoordDim()` | SMALLINT | 1/2/3 |
| `ST_Dimension()` | SMALLINT | 0/1/2, or -1 if empty |
| `ST_SRID([asrid])` | INTEGER or ST_Geometry | Getter (no arg) or setter |
| `ST_Is3D()` | INTEGER | 1 if has z coordinates |
| `ST_IsEmpty()` | INTEGER | 1 if empty set |
| `ST_IsSimple()` | INTEGER | 1 if no anomalous points |
| `ST_IsValid()` | INTEGER | 1 if well-formed |
| `ST_MinX/Y/Z()` | FLOAT | NULL if empty |
| `ST_MaxX/Y/Z()` | FLOAT | NULL if empty |
| `Make_2D([validate])` | ST_Geometry | Strip z; validate=1 checks well-formedness |

```sql
SELECT shape.ST_GeometryType() FROM sample_shapes;
SELECT shape.ST_AsText() FROM sample_shapes;
SELECT shape.ST_Is3D() FROM sample_shapes;
```

### Spatial Relationships (index-accelerated where noted)

| Method | Returns | Index | Notes |
|--------|---------|-------|-------|
| `ST_Contains(ageometry)` | INTEGER 0/1 | Yes | |
| `ST_Crosses(ageometry)` | INTEGER 0/1 | Yes | |
| `ST_Disjoint(ageometry)` | INTEGER 0/1 | No | |
| `ST_Equals(ageometry)` | INTEGER 0/1 | Yes | |
| `ST_Intersects(ageometry)` | INTEGER 0/1 | Yes | Excludes GeomCollection |
| `ST_Overlaps(ageometry)` | INTEGER 0/1 | Yes | Excludes GeomCollection |
| `ST_Relate(ageometry, amatrix)` | INTEGER 0/1 | Yes | DE-9IM 9-char matrix: T/F/0/1/2/* |
| `ST_Touches(ageometry)` | INTEGER 0/1 | Yes | |
| `ST_Within(ageometry)` | INTEGER 0/1 | Yes | |

```sql
-- Spatial join: streets within cities
SELECT streetName, cityName
FROM sample_cities, sample_streets
WHERE streetShape.ST_Within(cityShape) = 1
ORDER BY cityName;

-- DE-9IM: test if interiors intersect
WHERE streetShape.ST_Relate(NEW ST_Geometry('LINESTRING(2 2, 3 2, 4 1)'), '0********') = 1
```

### Distance (index-accelerated with `< constant`)

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_Distance(ageometry)` | FLOAT | Same SRS required; NULL if empty |
| `ST_3DDistance(ageometry)` | FLOAT | Z-aware; same SRS required |

```sql
-- Index used when distance < constant
WHERE shape.ST_Distance('LINESTRING(2 2, 3 2, 4 1)') < 1E0
WHERE shape.ST_3DDistance('POINT(10 20 30)') < 1E0
```

### Set Operations (result type varies by input; GeoSequence → ST_LineString)

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_Intersection(ageometry)` | ST_Geometry | Use `Make_2D` on 3D result |
| `ST_Union(ageometry)` | ST_Geometry | Use `Make_2D` on 3D result |
| `ST_Difference(ageometry)` | ST_Geometry | Use `Make_2D` on 3D result |
| `ST_SymDifference(ageometry)` | ST_Geometry | Use `Make_2D` on 3D result |

### Geometry Operations

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_Boundary()` | ST_Geometry | Next-lower dimension boundary |
| `ST_Buffer(adistance)` | ST_Geometry | Distance in SRS linear units |
| `ST_Centroid()` | ST_Point | Polygon/MultiPolygon only |
| `ST_ConvexHull()` | ST_Geometry | Use `Make_2D` on 3D result |
| `ST_Envelope()` | ST_Geometry | Bounding rectangle (2D) |
| `ST_MBR()` | MBR | 2D minimum bounding rectangle |
| `MBB()` | MBB | 3D minimum bounding box |
| `SimplifyPreserveTopology(tolerance)` | ST_Geometry | Lines/polygons only; always valid result |
| `ST_Transform([toSRSid,] toWktSRS, fromWktSRS)` | ST_Geometry | Reproject to different SRS |

```sql
-- Reproject using SPATIAL_REF_SYS
SELECT point.ST_Transform(3054, X.srtext, Y.srtext)
FROM customers,
     SYSSPATIAL.SPATIAL_REF_SYS X,
     SYSSPATIAL.SPATIAL_REF_SYS Y
WHERE X.AUTH_SRID = 32616 AND Y.AUTH_SRID = 4326;
```

---

## ST_Point Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_X([xcoord])` | FLOAT or ST_Geometry | Getter/setter |
| `ST_Y([ycoord])` | FLOAT or ST_Geometry | Getter/setter |
| `ST_Z([zcoord])` | FLOAT or ST_Geometry | Getter/setter; `ST_Z(val)` converts 2D → 3D |
| `ST_SphericalDistance(apoint)` | FLOAT | Haversine formula; meters |
| `ST_SpheroidalDistance(apoint [, semimajor, invflattening])` | FLOAT | WGS84 default; fails for antipodal points |
| `ST_SphericalBufferMBR(distance [, radius])` | MBR | Faster, less accurate; default radius 6371000m |
| `ST_SpheroidalBufferMBR(distance [, semimajor, invflattening])` | MBR | More accurate; WGS84 default |

**WGS84 defaults:** semimajor = 6,378,137.0 m, invflattening = 298.257223563.
**Antipodal points:** `ST_SpheroidalDistance` may fail — use `ST_SphericalDistance` instead.

```sql
-- Distance from Madison to Chicago
SELECT point1.ST_SpheroidalDistance(NEW ST_Geometry('POINT(-87.65 41.90)'))
FROM sample_points1;

-- 5km buffer MBR around a point
SELECT NEW ST_Geometry('POINT(100 30)').ST_SpheroidalBufferMBR(5000.0);
```

---

## ST_LineString and GeoSequence Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_StartPoint()` | ST_Geometry | Returns z if 3D |
| `ST_EndPoint()` | ST_Geometry | Returns z if 3D; NULL if empty |
| `ST_PointN(aposition)` | ST_Geometry | 1-based; returns z if 3D |
| `ST_NumPoints()` | INTEGER | |
| `ST_Length()` | FLOAT | LineString, GeoSequence, MultiLineString |
| `ST_3DLength()` | DOUBLE PRECISION | Z-aware; 0 if empty |
| `ST_IsClosed()` | INTEGER | 1 if start = end |
| `ST_3DIsClosed()` | INTEGER | Z-aware; errors if not 3D |
| `ST_IsRing()` | INTEGER | 1 if simple AND closed |
| `ST_Line_Interpolate_Point(proportion)` | ST_Point | proportion: 0.0–1.0 |

GeoSequence-specific methods:

| Method | Returns | Notes |
|--------|---------|-------|
| `GetInitT()` | TIMESTAMP | First point timestamp |
| `GetFinalT()` | TIMESTAMP | Last point timestamp |
| `GetUserFld(fldIndex, index)` | FLOAT | Both 1-based |
| `GetUserFldCount()` | INTEGER | User fields per point |
| `HeadingN(index)` | FLOAT | Degrees clockwise from North; 1-based |
| `LinkID(index [, linkID])` | DECIMAL(18,0) or ST_Geometry | Getter/setter |
| `SpeedN({index \| iBegin, iEnd})` | FLOAT | Coordinate units/hour |
| `Clip(startT, endT)` | GeoSequence | Subset by timestamp range |

---

## ST_Polygon and ST_MultiPolygon Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_Area()` | FLOAT | Sum for MultiPolygon; ignores z |
| `ST_Perimeter()` | FLOAT | Boundary length; ignores z |
| `ST_ExteriorRing([acurve])` | ST_LineString or ST_Polygon | Getter/setter |
| `ST_InteriorRingN([aposition])` | ST_LineString | 1-based |
| `ST_NumInteriorRing()` | INTEGER | |
| `ST_PointOnSurface()` | ST_Geometry | Guaranteed to intersect the polygon |

---

## ST_GeomCollection, ST_Multi* Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_GeometryN(aposition)` | ST_Geometry | 1-based; works on all Multi types |
| `ST_NumGeometries()` | INTEGER | Component count |

---

## MBR and MBB Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `MBR.XMin/YMin/XMax/YMax()` | FLOAT | Coordinate accessors |
| `MBB.XMin/YMin/ZMin/XMax/YMax/ZMax()` | FLOAT | 3D coordinate accessors |
| `MBR.Intersects(other)` | INTEGER 0/1 | Tests MBR-to-MBR intersection |
| `MBB.Intersects(other)` | INTEGER 0/1 | Tests MBB-to-MBB intersection |

---

## Filtering Methods

Use these for spatial filtering — index-accelerated for geospatial NUSIs.

| Method | Input | Returns | Notes |
|--------|-------|---------|-------|
| `MBR_Filter(othergeom)` | 2D ST_Geometry | INTEGER 0/1 | MBR-to-MBR test; ignores z |
| `MBB_Filter(othergeom)` | 3D ST_Geometry | INTEGER 0/1 | MBB-to-MBB test; errors if 2D |
| `Intersects_MBB(aMBB)` | 3D Point/MultiPoint/LineString/MultiLineString | INTEGER 0/1 | Geometry vs MBB; errors if 2D |
| `Within_MBB(aMBB)` | 3D ST_Geometry | INTEGER 0/1 | Geometry within MBB; errors if 2D |

```sql
SELECT shape.MBR_Filter(NEW ST_Geometry('POLYGON((0 0, 20 0, 20 20, 0 20, 0 0))'))
FROM sample_shapes;

SELECT shape.Within_MBB(NEW MBB(0,0,0,20,20,20))
FROM sample_shapes;
```

---

## Geospatial Indexes

Create a NUSI on an ST_Geometry column to enable optimizer use:

```sql
CREATE TABLE sample_shapes (skey INTEGER, shape ST_Geometry) INDEX (shape);
-- Or as part of CREATE TABLE:
CREATE TABLE t (a INT, sp ST_GEOMETRY) INDEX(sp);
```

**Index-accelerated predicates:** `ST_Contains`, `ST_Crosses`, `ST_Distance`, `ST_3DDistance`, `ST_Equals`, `ST_Intersects`, `ST_Overlaps`, `ST_Touches`, `ST_Within`, `MBR_Filter`, `MBB_Filter`, `Within_MBB`, `Intersects_MBB`, `ST_Relate`.

**Single-table predicate form (= 1 required):**
```sql
WHERE shape.ST_Within(NEW ST_Geometry('POLYGON(...)')) = 1
```

**Distance predicate form (< constant required):**
```sql
WHERE shape.ST_Distance('POINT(10 20)') < 100.0
```

**Join predicate:** optimizer considers nested join; at least one side must have a geospatial index.
```sql
SELECT * FROM T1 INNER JOIN T2 ON T1.GeoCol.ST_Within(T2.Geom) = 1;
```

**Geospatial index restrictions:**
- Single-column NUSIs only
- Not on volatile or global temporary tables
- Not on join indexes
- Collect statistics for better optimizer decisions (same syntax as regular COLLECT STATISTICS)

---

## System Functions (TD_SYSFNLIB)

Prefer these over UDFs — system functions take priority when names conflict.

### DataSize

```sql
SELECT TD_SYSFNLIB.DataSize(shape) FROM sample_shapes;
```

Returns BIGINT bytes for ST_Geometry, JSON, XML, DATASET columns.

### MGRS Conversion

```sql
-- Point → MGRS string (precision 0=100km to 5=1m; truncates, does not round)
SELECT TO_MGRS(
  NEW ST_GEOMETRY('ST_POINT', 30, 45),
  (SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE SRID = 1619),
  5);
-- Returns: '36TTQ6355387329'

-- MGRS string → ST_Point
SELECT FROM_MGRS(
  '36TTQ6355387329',
  (SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE SRID = 1619),
  1619);
```

Note: MGRS-Old lettering for Bessel/Clarke 1866/1880 ellipsoids; MGRS-New for all others.

### GeoSequence Conversion Table Functions

```sql
-- Rows → GeoSequence (PARTITION BY in_key ORDER BY ts required)
SELECT T.trip_id, R.geom
FROM trip_data T,
     TABLE(GeoSequenceFromRows(T.trip_id, T.pcount, T.seq,
           T.x, T.y, T.t, T.link_id,
           T.speed, T.accel, T.heading,
           NULL, NULL, NULL, NULL, NULL, NULL, NULL)) R
WHERE R.out_key = T.trip_id;

-- GeoSequence → rows (out_key, point_index, x, y, ts, Link_id, UserFld1-10)
SELECT out_key, point_index, x, y, ts, Link_id, UserFld1, UserFld2
FROM TABLE(GeoSequenceToRows(9601., sample_shapes.shape)) AS ts;
```

### AggGeom — Aggregate Union or Intersection

```sql
-- Union by zip code (parallel — one row per partition value)
SELECT zipcode, geom
FROM AggGeom(
  ON (SELECT geom, zipcode FROM geom_table)
  PARTITION BY zipcode
  USING Operation('Union')
) L;

-- Global union (two-call pattern for parallel local then global aggregation)
SELECT *
FROM AggGeom(
  ON (SELECT L.*, 1 AS p
      FROM AggGeom(ON (SELECT geom FROM geom_table) USING Operation('Union')) L)
  PARTITION BY p
) G;
```

**Notes:** Non-empty GeomCollections not supported (intermediate or final). Row order can vary — results are equivalent but not identical across runs.

### GeometryToRows — Explode Geometry to Point Rows

```sql
SELECT PointsTable.*
FROM GeometryToRows(ON (SELECT geom_id, geom FROM geo_table))
AS PointsTable (geom_id1, element_id, ring_id, point_id, geomType, x, y, z)
ORDER BY 1, 2, 3, 4;
```

Returns columns: `id1, [id2,] element_id, ring_id, point_id, geomType, x, y, z`.
- `element_id`: which element within a Multi type (1-based)
- `ring_id`: ring within polygon (1=exterior, 2+=interior holes); NULL for non-polygons
- `point_id`: ordering within the element (1-based)
- First and last points of a polygon ring are identical

### PolygonSplit — Split Large Polygons

```sql
SELECT *
FROM PolygonSplit(ON (
  SELECT poly_id, geom, CAST(400 AS INTEGER) AS max_vertices
  FROM feature_tbl
  WHERE poly_id = 100
)) AS SplitTable(poly_id, sub_poly_id, splitGeom)
ORDER BY 1, 2;
```

- Recursively splits into quadrants until each sub-polygon < `max_vertices` (default 300, min 10)
- Non-polygon geometries returned unchanged
- Sub-polygon areas may not sum exactly to original (floating-point rounding)
- Output: `out_polygon_ID, sub_polygon_ID` (0-based), `split_geom`

---

## UDFs (SYSSPATIAL Schema)

Prefer instance methods or system functions over these. Qualify with `SYSSPATIAL.` to avoid ambiguity.

```sql
-- Spherical distance (Haversine) — lat/lon as separate args
SELECT SYSSPATIAL.SphericalDistance(10, 20, 20, 30);

-- Spheroidal distance — WGS84 default; fails for antipodal points
SELECT SYSSPATIAL.SpheroidalDistance(-89.39, 43.09, -87.65, 41.90);
SELECT SYSSPATIAL.SpheroidalDistance(-89.39, 43.09, -87.65, 41.90, 6378137, 298.257223563);

-- Construct from WKT VARCHAR (max 64000 bytes; prefer constructor for performance)
SELECT SYSSPATIAL.ST_GeomFromText('POINT(10 20)', 4326);

-- Construct from WKB VARBYTE (max 64000 bytes)
SELECT SYSSPATIAL.ST_GeomFromWKB(:wkb_value, 4326);
```

**GeoJSON conversion (JSON Data Type):**
```sql
GeomFromGeoJSON  -- JSON GeoJSON document → ST_Geometry
GeoJSONFromGeom  -- ST_Geometry → JSON GeoJSON document
```

---

## Tessellation (Grid-Based Spatial Indexing)

Tessellation provides an alternative spatial index approach using a multilevel grid. It is used with a pre-built index table rather than a geospatial NUSI.

### Tessellate_Index Method (on ST_Geometry)

Generates cell IDs for indexing a geometry. Call this during INSERT to populate an index table.

```sql
CREATE TABLE cities_index (skey INTEGER, cellid INTEGER);

INSERT INTO cities_index
SELECT skey,
       cityShape.Tessellate_Index(
         -180, 0, 0, 90,   -- universe: u_xmin, u_ymin, u_xmax, u_ymax
         500, 500,          -- grid: g_nx, g_ny
         1,                 -- levels
         0.01,              -- scale (must be 0 < scale < 1)
         0)                 -- shift (0=none, 1=four shifted grids per level)
FROM sample_cities;
```

### Tessellate_Search UDF (SYSSPATIAL)

Table function that returns all cell IDs at each grid level that contain a given bounding rectangle. Use the same universe/grid parameters as `Tessellate_Index`. Join on `cellid` to find candidate matches.

```sql
SYSSPATIAL.Tessellate_Search (
  in_key,                          -- DECIMAL(18,0) — passed back as out_key
  o_xmin, o_ymin, o_xmax, o_ymax, -- object bounding rectangle (FLOAT)
  u_xmin, u_ymin, u_xmax, u_ymax, -- universe (FLOAT) — must match index
  g_nx, g_ny,                      -- grid divisions (INTEGER)
  levels,                           -- 1–15 (INTEGER)
  scale,                            -- 0 < scale < 1.0 (FLOAT)
  shift                             -- 0 or 1 (INTEGER)
)
```

Returns: `out_key` DECIMAL(18,0), `cellID` INTEGER.
- `cellID / 16` → cell number
- `cellID MOD 16` → grid level

```sql
-- Proximity join using tessellate index
SELECT c.skey, c.cityName, s.streetName
FROM sample_cities c
    ,cities_index ci
    ,(SELECT streetName, skey, streetShape,
             streetShape.ST_MBR_Xmin(), streetShape.ST_MBR_Ymin(),
             streetShape.ST_MBR_Xmax(), streetShape.ST_MBR_Ymax()
      FROM sample_streets)
      AS s (streetName, skey, streetShape, xmin, ymin, xmax, ymax)
    ,TABLE(SYSSPATIAL.Tessellate_Search(
             s.skey,
             s.xmin, s.ymin, s.xmax, s.ymax,
             -180, 0, 0, 90,
             500, 500,
             1, 0.01, 0)) AS t
WHERE c.skey = ci.skey
  AND ci.cellid = t.cellid
  AND t.out_key = s.skey;
```

---

## Metadata (SYSSPATIAL Database)

### GEOMETRY_COLUMNS

Tracks ST_Geometry columns and their spatial reference systems.

```sql
-- Register a new ST_Geometry column (2D)
CALL SYSSPATIAL.AddGeometryColumn(
  '',            -- catalog (empty string for Teradata)
  'mydb',        -- schema/database
  'lakes',       -- table
  'shore',       -- column
  4326,          -- SRID
  'ST_Polygon',  -- geometry type
  -180.0, -90.0, 180.0, 90.0  -- UxMin, UyMin, UxMax, UyMax (universe MBR)
);

-- Register a 3D column (adds dimensions parameter)
CALL SYSSPATIAL.AddGeometryColumn_3D('', 'mydb', 'lakes', 'shore', 3, 4326,
     'ST_Polygon', -180.0, -90.0, 180.0, 90.0);

-- Drop geometry metadata
CALL SYSSPATIAL.DropGeometryColumn('', 'mydb', 'lakes', 'shore');
```

### SPATIAL_REF_SYS

Populated by DIP during installation. Key columns: `SRID`, `AUTH_SRID`, `SRTEXT` (WKT SRS definition).

```sql
-- Look up WKT for a known SRID
SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE AUTH_SRID = 4326;  -- WGS84
SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE AUTH_SRID = 32616; -- UTM Zone 16N
```

---

## Common Patterns

### Proximity search (within distance)
```sql
SELECT skey FROM sample_shapes
WHERE shape.ST_Distance(NEW ST_Geometry('POINT(10 20)')) < 50.0;
```

### Point-in-polygon join
```sql
SELECT streetName, cityName
FROM sample_cities, sample_streets
WHERE streetShape.ST_Within(cityShape) = 1;
```

### Compute area and centroid
```sql
SELECT cityName,
       cityShape.ST_Area()     AS area_sq_units,
       cityShape.ST_Centroid() AS centroid
FROM sample_cities;
```

### Real-world distance between two points (WGS84)
```sql
SELECT point1.ST_SpheroidalDistance(point2)
FROM sample_points1, sample_points2;
```

### Convert to/from WKT and WKB
```sql
SELECT shape.ST_AsText()   FROM sample_shapes;  -- → CLOB WKT
SELECT shape.ST_AsBinary() FROM sample_shapes;  -- → BLOB WKB
```

### Find minimum bounding rectangle
```sql
INSERT INTO sample_MBRs SELECT skey, shape.ST_MBR() FROM sample_shapes;
```

### Aggregate all geometries into one union
```sql
SELECT *
FROM AggGeom(
  ON (SELECT L.*, 1 AS p
      FROM AggGeom(ON (SELECT geom FROM geom_table) USING Operation('Union')) L)
  PARTITION BY p
) G;
```

### Split a large polygon for performance
```sql
SELECT * FROM PolygonSplit(
  ON (SELECT poly_id, geom FROM feature_tbl)
) AS t ORDER BY 1, 2;
```
