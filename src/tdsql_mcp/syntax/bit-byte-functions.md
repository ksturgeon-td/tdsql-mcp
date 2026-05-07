# Teradata Bit and Byte Manipulation Functions

All functions in this file are Teradata extensions to ANSI SQL. They are embedded services scalar functions located in `TD_SYSFNLIB` (prefix is optional). All return NULL if any argument is NULL unless noted otherwise.

---

## Bit and Byte Numbering Model

Teradata uses a **big-endian** model. The most significant byte is on the left; within each byte the most significant bit has the highest bit number.

| Type | Width | Bit range |
|------|-------|-----------|
| `BYTEINT` | 1 byte | Bit 7 (MSB) → Bit 0 (LSB) |
| `SMALLINT` | 2 bytes | Bit 15 (MSB) → Bit 0 (LSB) |
| `INTEGER` | 4 bytes | Bit 31 (MSB) → Bit 0 (LSB) |
| `BIGINT` | 8 bytes | Bit 63 (MSB) → Bit 0 (LSB) |
| `BYTE(n)` / `VARBYTE(n)` | n bytes | Bit (8n−1) (MSB) → Bit 0 (LSB) |

> **Bit 0 is the least significant bit (rightmost).** Functions like `GETBIT` and `SETBIT` use 0-based indexing from the LSB — `GETBIT(23, 2)` returns the third bit from the right, not the third from the left.

**Example — BYTEINT 40 = `00101000`:**
- Bit 5 = 1, Bit 3 = 1, all other bits = 0

---

## Hex Byte Literal Syntax

```sql
'XXYY'XB           -- 2-byte hex literal
'01020304'XB        -- 4-byte hex literal
'112233'XB          -- 3-byte literal — RIGHT-padded to 4 bytes: '11223300'XB
```

> **Hex literals are right-padded with zeros** when extended to match a required byte size. This is the **opposite** of operand padding (see below).

---

## Mismatched-Length Operands (BITAND / BITOR / BITXOR only)

When `target_arg` and `bit_mask_arg` have different lengths, they are **aligned on the LSB** and the shorter argument is **left-padded with zeros**:

```sql
-- 'FFFF'XB (2 bytes) vs INTEGER (4 bytes)
-- Effective operation: '0000FFFF'XB AND '11223344'XB
SELECT BITAND(287454020, 'FFFF'XB);   -- masks lower 2 bytes only
-- Result: 0x3344 = 13124
```

> Left-padding for operands vs right-padding for literals — they go in opposite directions. Always visualize the alignment on the **least significant byte**.

---

## Quick Reference

| Function | Syntax | Description |
|----------|--------|-------------|
| `BITAND` | `BITAND(target, mask)` | Bitwise AND — 1 only where both bits are 1 |
| `BITOR` | `BITOR(target, mask)` | Bitwise OR — 1 where either bit is 1 |
| `BITXOR` | `BITXOR(target, mask)` | Bitwise XOR — 1 where bits differ |
| `BITNOT` | `BITNOT(target)` | Bitwise complement — flips all bits |
| `COUNTSET` | `COUNTSET(target [, 0\|1])` | Count bits set to 1 (default) or 0 |
| `GETBIT` | `GETBIT(target, bit_pos)` | Get value of bit at position (0=LSB) |
| `SETBIT` | `SETBIT(target, bit_pos [, 0\|1])` | Set bit at position to 1 (default) or 0 |
| `SHIFTLEFT` | `SHIFTLEFT(target, n)` | Shift left n bits; MSBs lost, LSBs zero-filled |
| `SHIFTRIGHT` | `SHIFTRIGHT(target, n)` | Shift right n bits; LSBs lost, MSBs zero-filled |
| `ROTATELEFT` | `ROTATELEFT(target, n)` | Rotate left n bits; MSBs wrap to LSB |
| `ROTATERIGHT` | `ROTATERIGHT(target, n)` | Rotate right n bits; LSBs wrap to MSB |
| `SUBBITSTR` | `SUBBITSTR(target, pos, n)` | Extract n bits starting at pos; returns VARBYTE |
| `TO_BYTE` | `TO_BYTE(target)` | Convert numeric to fixed BYTE representation |

**Accepted types for all functions:** `BYTEINT`, `SMALLINT`, `INTEGER`, `BIGINT`, `VARBYTE(n)` (max 8192 bytes).
`BITAND` also accepts `DECIMAL` / `NUMBER` (implicitly converted to `NUMBER(38,0)`).

---

## Bitwise Logic

```sql
-- BITAND: 1 only where both bits are 1
SELECT BITAND(23, 20);        -- 00010111 AND 00010100 = 00010100 = 20

-- BITOR: 1 where either bit is 1
SELECT BITOR(23, 45);         -- 00010111 OR 00101101 = 00111111 = 63

-- BITXOR: 1 where bits differ
SELECT BITXOR(12, 45);        -- 00001100 XOR 00101101 = 00100001 = 33

-- BITNOT: flip all bits (ones' complement)
SELECT BITNOT(2);             -- BYTEINT 00000010 → 11111101 = -3
```

**Common bitmask patterns:**

```sql
-- Test whether a specific flag bit is set (bit 3 = value 8)
SELECT col, BITAND(flags_col, 8) AS bit3_set FROM db.t;

-- Set a flag bit without disturbing others (OR with the bit mask)
SELECT BITOR(flags_col, 8) AS flags_with_bit3 FROM db.t;

-- Clear a flag bit (AND with NOT of the bit mask)
SELECT BITAND(flags_col, BITNOT(CAST(8 AS INTEGER))) AS flags_without_bit3 FROM db.t;

-- Toggle a bit (XOR with the bit mask)
SELECT BITXOR(flags_col, 8) AS toggled FROM db.t;

-- Mask lower 2 bytes of an INTEGER using a hex literal
SELECT BITAND(some_int_col, 'FFFF'XB) AS lower_two_bytes FROM db.t;
-- 'FFFF'XB is left-padded to '0000FFFF'XB to match INTEGER width
```

---

## Bit Counting and Inspection

```sql
-- COUNTSET: count bits set to 1 (default)
SELECT COUNTSET(23);          -- 00010111 has four 1-bits → returns 4

-- Count bits set to 0
SELECT COUNTSET(23, 0);       -- 00010111 has four 0-bits → returns 4

-- GETBIT: get value of a single bit (0 = LSB, n-1 = MSB)
SELECT GETBIT(23, 2);         -- bit 2 of 00010111 = 1 → returns BYTEINT 1
SELECT GETBIT(23, 4);         -- bit 4 of 00010111 = 1 → returns BYTEINT 1
SELECT GETBIT(23, 5);         -- bit 5 of 00010111 = 0 → returns BYTEINT 0

-- Check if a specific bit is set across a table
SELECT col, GETBIT(flags_col, 3) AS bit3 FROM db.t;
```

---

## Bit Setting

```sql
-- SETBIT: set a bit to 1 (default)
SELECT SETBIT(23, 2);         -- bit 2 already 1 → no change → 23

-- Set a bit to 0 (clear)
SELECT SETBIT(23, 2, 0);      -- clear bit 2 of 00010111 → 00010011 = 19

-- Set a bit to 1 explicitly
SELECT SETBIT(16, 0, 1);      -- set bit 0 of 00010000 → 00010001 = 17
```

---

## Bit Substring Extraction

`SUBBITSTR` extracts a bit substring and returns `VARBYTE`. The result is **right-justified** within a zero-filled byte boundary.

```sql
-- Extract 3 bits starting at bit position 2 from BYTEINT 20 (00010100)
SELECT SUBBITSTR(20, 2, 3);
-- Bits at positions 2,3,4 = 101 → right-justified in VARBYTE(1) = 00000101 = 5

-- Extract 8 bits starting at bit 4 from an INTEGER
SELECT SUBBITSTR(some_int_col, 4, 8) FROM db.t;   -- returns VARBYTE(1)

-- Extract 12 bits — rounded up to 2-byte VARBYTE
SELECT SUBBITSTR(some_int_col, 8, 12) FROM db.t;  -- returns VARBYTE(2), right-justified
```

> **Output size:** always rounded up to the next byte boundary. 3 bits requested → 1-byte VARBYTE. 9 bits requested → 2-byte VARBYTE. Excess bits are zero-filled on the left.

---

## Shift and Rotate

### SHIFTLEFT / SHIFTRIGHT

Bits fall off the end and are lost; vacated positions are zero-filled.

```sql
-- SHIFTLEFT: LSBs filled with 0; MSBs lost
SELECT SHIFTLEFT(3, 2);       -- 00000011 << 2 = 00001100 = 12
SELECT SHIFTLEFT(3, 6);       -- 00000011 << 6 = 11000000 = -64  (signed overflow!)

-- SHIFTRIGHT: MSBs filled with 0; LSBs lost
SELECT SHIFTRIGHT(3, 2);      -- 00000011 >> 2 = 00000000 = 0
SELECT SHIFTRIGHT(192, 1);    -- 11000000 >> 1 = 01100000 = 96
```

> **Error if `num_bits_arg` exceeds the width of `target_arg`** — unlike ROTATE functions which use MOD. Negative `num_bits_arg` reverses direction.

### ROTATELEFT / ROTATERIGHT

Bits wrap around rather than being lost.

```sql
-- ROTATELEFT: MSBs wrap to LSB positions
SELECT ROTATELEFT(16, 2);     -- 00010000 rotated left 2 = 01000000 = 64
SELECT ROTATELEFT(64, 3);     -- 01000000 rotated left 3 = 00000010 = 2 (wrapped)

-- ROTATERIGHT: LSBs wrap to MSB positions
SELECT ROTATERIGHT(32, 2);    -- 00100000 rotated right 2 = 00001000 = 8
SELECT ROTATERIGHT(4, 4);     -- 00000100 rotated right 4 = 01000000 = 64 (wrapped)
```

> If `num_bits_arg > sizeof(target_arg)`, the effective rotation is `num_bits_arg MOD sizeof(target_arg)` — no error. Negative `num_bits_arg` reverses direction.

**Shift vs Rotate comparison:**

| | SHIFTLEFT / SHIFTRIGHT | ROTATELEFT / ROTATERIGHT |
|---|---|---|
| Bits that fall off the end | Lost (replaced with 0) | Wrapped to opposite end |
| `num_bits > type width` | **Error** | Uses MOD, no error |
| Negative `num_bits` | Reverses direction | Reverses direction |

---

## Type Conversion

```sql
-- TO_BYTE: convert numeric to fixed BYTE type (big-endian representation)
SELECT TO_BYTE(23);           -- BYTEINT 23 → BYTE(1) = '17'XB
SELECT TO_BYTE(287454020);    -- INTEGER  → BYTE(4) = '11223344'XB

-- Useful for inspecting the hex value of a numeric result
SELECT TO_BYTE(CAST(BITAND(some_col, 'FFFF'XB) AS INTEGER)) FROM db.t;
```

| Input type | Output type |
|------------|-------------|
| `BYTEINT` | `BYTE(1)` |
| `SMALLINT` | `BYTE(2)` |
| `INTEGER` | `BYTE(4)` |
| `BIGINT` | `BYTE(8)` |

---

## Notes

- **All functions are Teradata-specific** — there are no ANSI SQL equivalents. Standard SQL has no bitwise function syntax; do not use `&`, `|`, `^`, `~` operators.
- **Signed integer overflow:** shifting or rotating a bit into the MSB (Bit 7/15/31/63) makes the result negative — all integers in Vantage are signed. This is expected behavior, not an error.
- **UDF implicit type conversion rules** are stricter than normal Vantage rules. If an argument type doesn't match exactly, use explicit `CAST`. Example: `BITAND(CAST(some_col AS INTEGER), '0000FFFF'XB)`.
- **`TD_SYSFNLIB.` prefix** is optional but can be included for clarity: `TD_SYSFNLIB.BITAND(...)`.
- **VARBYTE max size** for all functions is 8192 bytes.
- **DECIMAL inputs to BITAND** are implicitly converted to `NUMBER(38,0)`. BITNOT does not support DECIMAL/NUMBER.
