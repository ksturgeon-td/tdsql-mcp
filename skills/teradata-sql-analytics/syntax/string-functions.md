# Teradata String Functions

## Quick Reference

| Function | Syntax | Notes |
|----------|--------|-------|
| Length | `CHAR_LENGTH(str)` or `CHARACTER_LENGTH(str)` | Character count |
| Byte length | `OCTET_LENGTH(str)` | Byte count |
| Substring | `SUBSTR(str, start, length)` | 1-based index |
| Position | `INDEX(str, substring)` | Returns 0 if not found (not INSTR) |
| Concatenate | `str1 \|\| str2` or `CONCAT(a, b)` | |
| Upper/Lower | `UPPER(str)` / `LOWER(str)` | |
| Trim | `TRIM([[LEADING\|TRAILING\|BOTH] char FROM] str)` | Default trims spaces both sides |
| Left trim | `LTRIM(str [, chars])` | |
| Right trim | `RTRIM(str [, chars])` | |
| Replace | `OREPLACE(str, from, to)` | Teradata-specific; use instead of REPLACE |
| Pad left | `LPAD(str, length [, pad_char])` | |
| Pad right | `RPAD(str, length [, pad_char])` | |
| Repeat | `STRTOK_SPLIT_TO_TABLE` / manual CTE | No simple REPEAT function |
| Reverse | `REVERSE(str)` | |
| RegEx match | `REGEXP_SIMILAR(str, pattern)` | Returns 1 (match) or 0 |
| RegEx extract | `REGEXP_SUBSTR(str, pattern [, pos [, occur [, flags]]])` | |
| RegEx replace | `REGEXP_REPLACE(str, pattern, replacement [, pos [, occur [, flags]]])` | |

## Examples

```sql
-- Substring: extract first 3 characters
SELECT SUBSTR(name, 1, 3) FROM db.t;

-- Find position of substring (returns 0 if not found)
SELECT INDEX(email, '@') FROM db.t;

-- Replace a substring (Teradata uses OREPLACE, not REPLACE)
SELECT OREPLACE(phone, '-', '') FROM db.t;

-- Trim specific characters
SELECT TRIM(LEADING '0' FROM account_number) FROM db.t;

-- Pad a number to 8 digits
SELECT LPAD(CAST(id AS VARCHAR(8)), 8, '0') FROM db.t;

-- Concatenate with separator
SELECT first_name || ' ' || last_name AS full_name FROM db.t;

-- Case-insensitive search using UPPER
SELECT * FROM db.t WHERE UPPER(name) LIKE '%SMITH%';

-- Extract domain from email
SELECT SUBSTR(email, INDEX(email, '@') + 1) AS domain FROM db.t;

-- RegEx: check if value looks like a US zip code
SELECT REGEXP_SIMILAR(zip, '^[0-9]{5}(-[0-9]{4})?$') FROM db.t;

-- RegEx: extract area code from phone number
SELECT REGEXP_SUBSTR(phone, '[0-9]{3}', 1, 1) AS area_code FROM db.t;
```

## Tokenization
```sql
-- Split a delimited string into rows using STRTOK_SPLIT_TO_TABLE
SELECT token_num, tokenval
FROM TABLE(STRTOK_SPLIT_TO_TABLE(1, 'a,b,c', ',')
           RETURNS (outkey INTEGER, token_num INTEGER, tokenval VARCHAR(100))
          ) AS t;

-- Get Nth token from a delimited string
SELECT STRTOK(col, ',', 2) FROM db.t;   -- 2nd comma-delimited token
```

## Notes
- Teradata strings are 1-indexed
- `CHAR` columns are padded with spaces; use `TRIM` when comparing
- `OREPLACE` is preferred over `REPLACE` in Teradata dialects
