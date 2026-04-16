# Teradata String Functions

## Quick Reference

| Function | Syntax | Notes |
|----------|--------|-------|
| **Length** | `CHAR_LENGTH(str)` / `CHARACTER_LENGTH(str)` | ANSI; character count |
| | `LENGTH(str)` | TD extension; same result |
| | `OCTET_LENGTH(str)` | Byte count |
| **Extraction** | `SUBSTR(str, start [, len])` | 1-based; omit len → to end |
| | `LEFT(str, n)` | Leftmost N chars; also `TD_LEFT` |
| | `RIGHT(str, n)` | Rightmost N chars; also `TD_RIGHT` |
| **Position** | `POSITION(str1 IN str2)` | ANSI; returns 0 if not found |
| | `INDEX(str, substr)` | Teradata; returns 0 if not found |
| | `LOCATE(str1, str2 [, n])` | ANSI alt; optional start position |
| | `INSTR(src, search [, pos [, occur]])` | Oracle-style; negative pos = search from end |
| **Case** | `UPPER(str)` / `UCASE(str)` | |
| | `LOWER(str)` | |
| | `INITCAP(str)` | Capitalize first letter of each word |
| **Trim / Pad** | `TRIM([[LEADING\|TRAILING\|BOTH] char FROM] str)` | Default: trim spaces both ends |
| | `LTRIM(str [, chars])` | |
| | `RTRIM(str [, chars])` | |
| | `LPAD(str, len [, pad])` | |
| | `RPAD(str, len [, pad])` | |
| **Concat / Replace** | `str1 \|\| str2` / `CONCAT(a, b)` | |
| | `OREPLACE(str, from, to)` | Teradata; prefer over REPLACE |
| | `REVERSE(str)` | |
| **Char Codes** | `ASCII(str)` | First char → decimal code |
| | `CHR(n)` | Decimal → Latin ASCII char |
| | `CHAR2HEXINT(str)` | Char string → hex string |
| **Phonetic / Fuzzy** | `SOUNDEX(str)` | 4-char phonetic code |
| | `EDITDISTANCE(str1, str2 [, ci, cd, cs, ct])` | Edit distance with optional operation costs |
| | `NGRAM(str1, str2, len [, position])` | Count of matching n-grams |
| **Char Translation** | `OTRANSLATE(src, from, to)` | Character-by-character substitution |
| **Charset Conversion** | `TRANSLATE(str USING src TO tgt [WITH ERROR])` | Convert between LATIN/UNICODE/KANJI1 |
| | `TRANSLATE_CHK(str USING src TO tgt)` | 0 = ok; >0 = position of first error |
| | `VARGRAPHIC(str)` | Convert to VARGRAPHIC type |
| | `STRING_CS(str)` | Detect KANJI1 encoding (specialized) |
| **Parsing** | `NVP(str, name [, name_delim [, val_delim [, n]]])` | Extract value from name=value pairs |
| | `STRTOK(str, delim, n)` | Nth delimited token |
| | `FROM TABLE(CSV(...))` | Serialize columns to CSV string |
| | `FROM TABLE(CSVLD(...))` | Parse CSV string into columns |
| **RegEx** | `REGEXP_SIMILAR(str, pattern [, flags])` | Returns 1 (match) or 0 |
| | `REGEXP_SUBSTR(str, pattern [, pos [, occur [, flags]]])` | Extract matching substring |
| | `REGEXP_REPLACE(str, pattern, repl [, pos [, occur [, flags]]])` | Replace matching substring |

---

## String Extraction

```sql
-- SUBSTR: 1-based; omit length to extract to end of string
SELECT SUBSTR(name, 1, 3) FROM db.t;              -- first 3 chars
SELECT SUBSTR(name, 5) FROM db.t;                 -- from position 5 to end

-- LEFT / RIGHT
SELECT LEFT(name, 5) FROM db.t;                   -- leftmost 5 chars
SELECT RIGHT(name, 4) FROM db.t;                  -- rightmost 4 chars

-- LENGTH vs CHAR_LENGTH — equivalent for most purposes
SELECT LENGTH(name) FROM db.t;
SELECT CHAR_LENGTH(name) FROM db.t;               -- ANSI preferred form
```

---

## Position Functions

Four functions find substrings — use the one that matches your style or requirement:

| Function | Syntax | ANSI? | Notes |
|----------|--------|-------|-------|
| `POSITION` | `POSITION(str1 IN str2)` | Yes | Preferred for ANSI conformance |
| `INDEX` | `INDEX(str, substr)` | No | Classic Teradata; same as POSITION |
| `LOCATE` | `LOCATE(str1, str2 [, n])` | Yes | Adds optional start position |
| `INSTR` | `INSTR(src, search [, pos [, occur]])` | No | Oracle-style; negative pos, occurrence |

```sql
-- All return 0 if not found, 1-based position if found
SELECT POSITION('@' IN email) FROM db.t;
SELECT INDEX(email, '@') FROM db.t;              -- same result
SELECT LOCATE('@', email) FROM db.t;             -- same result
SELECT LOCATE('@', email, 5) FROM db.t;          -- start search at position 5

-- INSTR: negative position searches from end of string
SELECT INSTR(filepath, '/', -1) FROM db.t;       -- position of last '/'
-- INSTR: find 2nd occurrence
SELECT INSTR(str, '.', 1, 2) FROM db.t;          -- position of 2nd '.'
```

---

## Character Code Functions

```sql
-- ASCII: first character → decimal code (reflects string character set)
SELECT ASCII('A') FROM db.t;                     -- returns 65
SELECT ASCII(name) FROM db.t;                    -- code of first char of name

-- CHR: decimal code → Latin ASCII character (code mod 256 if > 255)
SELECT CHR(65) FROM db.t;                        -- returns 'A'
SELECT CHR(ASCII(name)) FROM db.t;               -- round-trip: char → code → char

-- CHAR2HEXINT: character string → hexadecimal string
SELECT CHAR2HEXINT('AB') FROM db.t;              -- returns hex representation
-- Not supported for CLOB columns
```

---

## Case Conversion

```sql
SELECT UPPER(name) FROM db.t;
SELECT LOWER(name) FROM db.t;

-- INITCAP: first letter of each word uppercase, rest lowercase
-- Words are delimited by whitespace or non-alphanumeric characters
SELECT INITCAP('hello world') FROM db.t;         -- returns 'Hello World'
SELECT INITCAP('O''BRIEN, JOHN') FROM db.t;      -- returns 'O''Brien, John'
```

---

## Phonetic and Fuzzy Matching

```sql
-- SOUNDEX: 4-character phonetic code (letter + 3 digits)
-- Same or similar sounds → same code; useful for name matching
SELECT SOUNDEX('Smith') FROM db.t;               -- returns 'S530'
SELECT SOUNDEX('Smythe') FROM db.t;              -- also returns 'S530'
SELECT * FROM db.customers
WHERE SOUNDEX(last_name) = SOUNDEX('Thompson');  -- phonetic search

-- EDITDISTANCE: minimum edit operations to transform str1 into str2
-- Operations: insertion (ci), deletion (cd), substitution (cs), transposition (ct)
-- All costs default to 1; lower = more similar
SELECT EDITDISTANCE('kitten', 'sitting') FROM db.t;          -- returns 3
SELECT EDITDISTANCE('abc', 'abd', 1, 1, 1, 1) FROM db.t;    -- explicit costs
-- Use for fuzzy deduplication or typo tolerance:
SELECT * FROM db.names
WHERE EDITDISTANCE(LOWER(name), LOWER('teradata')) <= 2;

-- NGRAM: count of matching n-grams (substrings of length n)
-- Higher count = more similar strings
SELECT NGRAM('teradata', 'terablata', 3) FROM db.t;   -- trigram match count
-- Optional position argument: positional n-gram (position matters, not just existence)
SELECT NGRAM('hello', 'world', 2, 1) FROM db.t;       -- positional bigram
```

---

## Trim, Replace, and Translation

```sql
-- TRIM: remove leading/trailing characters
SELECT TRIM(name) FROM db.t;                          -- trim spaces both ends
SELECT TRIM(LEADING '0' FROM account_num) FROM db.t;  -- remove leading zeros
SELECT TRIM(TRAILING '.' FROM str) FROM db.t;

-- OREPLACE: replace all occurrences (preferred over REPLACE in Teradata)
SELECT OREPLACE(phone, '-', '') FROM db.t;
SELECT OREPLACE(str, ' ', '_') FROM db.t;

-- OTRANSLATE: character-by-character substitution (like Unix tr)
-- Each character in from_string is replaced by the corresponding char in to_string
-- If to_string is shorter, excess from_string chars are deleted
-- If to_string is NULL or empty, all from_string chars are removed
SELECT OTRANSLATE('hello world', 'aeiou', '*****') FROM db.t;  -- 'h*ll* w*rld'
SELECT OTRANSLATE(str, 'ABC', 'abc') FROM db.t;                -- fold specific chars to lower
SELECT OTRANSLATE(str, '0123456789', '') FROM db.t;            -- remove all digits
```

---

## Character Set Conversion (TRANSLATE / TRANSLATE_CHK)

`TRANSLATE` converts between Teradata server character sets (LATIN, UNICODE, KANJI1). This is different from `OTRANSLATE` which does character substitution.

```sql
-- Convert LATIN string to UNICODE
SELECT TRANSLATE(name USING LATIN_TO_UNICODE) FROM db.t;

-- Convert UNICODE to LATIN (WITH ERROR replaces bad chars instead of failing)
SELECT TRANSLATE(name USING UNICODE_TO_LATIN WITH ERROR) FROM db.t;

-- TRANSLATE_CHK: test before converting — returns 0 if safe, or position of first problem char
SELECT name,
       TRANSLATE_CHK(name USING UNICODE_TO_LATIN) AS chk
FROM db.t;

-- Filter to only safely translatable rows
SELECT TRANSLATE(name USING UNICODE_TO_LATIN) AS latin_name
FROM db.t
WHERE TRANSLATE_CHK(name USING UNICODE_TO_LATIN) = 0;

-- VARGRAPHIC: convert character string to VARGRAPHIC type
SELECT VARGRAPHIC(name) FROM db.t;
```

> **TRANSLATE vs OTRANSLATE:** `TRANSLATE` converts character sets (LATIN ↔ UNICODE ↔ KANJI1). `OTRANSLATE` substitutes specific characters within a string. They solve different problems — do not confuse them.

---

## Name-Value Pair Parsing (NVP)

Extracts a value from a string of name-value pairs. Default delimiters match URL query string format (`&` between pairs, `=` between name and value).

```sql
-- Basic usage: extract 'city' from a key=value string
SELECT NVP('name=John&city=Dallas&state=TX', 'city') FROM db.t;
-- returns: 'Dallas'

-- Custom delimiters: semicolons between pairs, colon between name and value
SELECT NVP('name:John;city:Dallas', 'city', ';', ':') FROM db.t;
-- returns: 'Dallas'

-- Multiple occurrences: get the 2nd value for 'tag'
SELECT NVP('tag=red&tag=blue&tag=green', 'tag', '&', '=', 2) FROM db.t;
-- returns: 'blue'

-- Parse URL query string columns directly (defaults match URL encoding)
SELECT NVP(query_string, 'utm_source') AS utm_source FROM db.web_events;
```

---

## CSV Serialization and Parsing

Both are table functions invoked with `FROM TABLE(...)` syntax and require a `RETURNS` clause.

```sql
-- CSV: serialize multiple columns into a single delimited string
-- Supports up to 8 column values; use NEW VARIANT_TYPE to pass heterogeneous types
SELECT * FROM TABLE(
    CSV(NEW VARIANT_TYPE(dt.id, dt.name, dt.amount), ',', '"')
    RETURNS (op VARCHAR(64000) CHARACTER SET LATIN)
) AS t;
-- Returns: '1,"John Smith","99.50"'

-- Omit quote character to suppress quoting of string columns
SELECT * FROM TABLE(
    CSV(NEW VARIANT_TYPE(dt.id, dt.name), ',', '')
    RETURNS (op VARCHAR(32000) CHARACTER SET UNICODE)
) AS t;

-- CSVLD: parse a CSV string back into typed columns
-- Number of RETURNS columns must match the number of values in the CSV string
SELECT * FROM TABLE(
    CSVLD(load_table.csv_col, ',', '"')
    RETURNS (col1 VARCHAR(100), col2 VARCHAR(100), col3 VARCHAR(100))
) AS t;

-- Typical round-trip pattern
-- Serialize: use CSV to pack row columns → store in staging
-- Deserialize: use CSVLD to unpack → use RETURNS to name/type the output columns
```

> **CSV and CSVLD are paired functions.** CSV serializes, CSVLD deserializes. Both accept up to 1024 output columns. The delimiter and quote character must match between the two calls.

---

## Tokenization

```sql
-- STRTOK: get Nth token from a delimited string (1-based)
SELECT STRTOK(col, ',', 1) FROM db.t;    -- first token
SELECT STRTOK(col, ',', 2) FROM db.t;    -- second token
SELECT STRTOK(col, '|', 3) FROM db.t;    -- pipe-delimited, third token

-- STRTOK_SPLIT_TO_TABLE: split a delimited string into one row per token
SELECT token_num, tokenval
FROM TABLE(
    STRTOK_SPLIT_TO_TABLE(1, 'a,b,c', ',')
    RETURNS (outkey INTEGER, token_num INTEGER, tokenval VARCHAR(100))
) AS t;
```

---

## Regular Expressions

```sql
-- REGEXP_SIMILAR: does the string match the pattern? Returns 1 or 0
SELECT REGEXP_SIMILAR(zip, '^[0-9]{5}(-[0-9]{4})?$') FROM db.t;

-- REGEXP_SUBSTR: extract the matching portion
SELECT REGEXP_SUBSTR(phone, '[0-9]{3}', 1, 1) AS area_code FROM db.t;
-- Args: (string, pattern, start_pos, occurrence, flags)

-- REGEXP_REPLACE: replace matching portion
SELECT REGEXP_REPLACE(col, '[^a-zA-Z0-9]', '', 1, 0, 'i') FROM db.t;
-- Flags: 'i' = case-insensitive, 'g' = global (all occurrences), 'n' = newline-sensitive
```

---

## Practical Examples

```sql
-- Extract domain from email address
SELECT SUBSTR(email, INDEX(email, '@') + 1) AS domain FROM db.t;

-- Pad a number to 8 digits with leading zeros
SELECT LPAD(CAST(id AS VARCHAR(8)), 8, '0') FROM db.t;

-- Full name from parts
SELECT first_name || ' ' || last_name AS full_name FROM db.t;

-- Normalize a phone number by removing all non-digits
SELECT OTRANSLATE(OREPLACE(phone, '-', ''), '() ', '') AS clean_phone FROM db.t;

-- Phonetic name matching
SELECT a.name, b.name
FROM db.names a JOIN db.names b
ON SOUNDEX(a.name) = SOUNDEX(b.name) AND a.id <> b.id;

-- Find close-match duplicates using edit distance
SELECT a.id, b.id, a.name, b.name,
       EDITDISTANCE(LOWER(a.name), LOWER(b.name)) AS dist
FROM db.customers a JOIN db.customers b
ON a.id < b.id
WHERE EDITDISTANCE(LOWER(a.name), LOWER(b.name)) <= 2;

-- Parse URL query string parameter
SELECT NVP(query_string, 'campaign') AS campaign FROM db.web_log;

-- Safely convert to LATIN, skip untranslatable rows
SELECT TRANSLATE(name USING UNICODE_TO_LATIN) AS latin_name
FROM db.contacts
WHERE TRANSLATE_CHK(name USING UNICODE_TO_LATIN) = 0;
```

---

## Notes

- Teradata strings are **1-indexed**
- `CHAR` columns are blank-padded; use `TRIM` when comparing `CHAR` to `VARCHAR`
- `OREPLACE` is preferred over `REPLACE` in Teradata SQL
- Use `POSITION ... IN` (ANSI) rather than `INDEX` for portability
- `TD_SYSFNLIB.` prefix is optional for embedded services functions but can be included for clarity
- `LEFT` and `RIGHT` may conflict with ODBC parsing — use `TD_LEFT` / `TD_RIGHT` aliases when connecting via ODBC
- **`TRANSLATE` ≠ `OTRANSLATE`**: TRANSLATE converts character sets; OTRANSLATE substitutes individual characters
