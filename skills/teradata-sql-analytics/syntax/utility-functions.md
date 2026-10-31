# Teradata Utility Functions

General-purpose column-level utility functions for adding row IDs, applying
numeric and string operators, and rounding values.

---

## TD_FillRowID — Add Unique Row Identifiers

Adds a column of unique row identifiers to the input table.

```sql
SELECT * FROM TD_FillRowID(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY order_col                                -- optional: no effect on the IDs was observed
    -- The IDs are unique but not sequential and not ordered by any column.
    -- For 1..N in a defined order use ROW_NUMBER() OVER (ORDER BY order_col) instead.
    USING
        RowIDColumnName('row_id')                     -- optional: name for the new row ID column
                                                      -- default: 'row_id'
) AS t;
```

---

## TD_NumApply — Apply Numeric Operator to Columns

Applies a specified numeric operator to each value in the target columns.

```sql
-- Basic usage: apply operator in-place (default)
SELECT * FROM TD_NumApply(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    ORDER BY order_col
    USING
        TargetColumns('col1', 'col2')                 -- required; explicit columns or range e.g. '[1:5]'
        ApplyMethod('LOG')                            -- required; options:
                                                      --   EXP      — e^x
                                                      --   LOG      — natural logarithm of x (LOG of 10 returns 2.3026; for base 10 use the SQL LOG() function)
                                                      --   SIGMOID  — sigmoid function (see SigmoidStyle)
                                                      --   SININV   — inverse sine (arcsine) in degrees; 0.5 returns 30.0; input outside [-1, 1] returns NULL
                                                      --   TANH     — hyperbolic tangent
        InPlace('true')                               -- optional: overwrite target columns; default 'true'
) AS t;

-- Add output columns alongside originals (InPlace false)
SELECT * FROM TD_NumApply(
    ON { db.table | db.view | (query) } AS InputTable
    PARTITION BY ANY
    USING
        TargetColumns('col1', 'col2')
        ApplyMethod('SIGMOID')
        SigmoidStyle('logit')                         -- optional with SIGMOID; default: 'logit'
                                                      -- options: 'logit' (0.7311 at x=1), 'modifiedlogit' (0.4621),
                                                      --          'tanh' (0.7616 at x=1)
        InPlace('false')                              -- returns new columns; original columns are returned
                                                      -- only if listed in Accumulate
        OutputColumns('col1_sigmoid', 'col2_sigmoid') -- optional: default is operator_target_column (e.g. TANH_x)
                                                      -- required if operator_target_column > 128 chars
        Accumulate('id_col', 'col1', 'col2')          -- include target columns here to keep them beside the new ones
) AS t;
```

---

## TD_RoundColumns — Round Column Values

Rounds values in each target column to a specified number of decimal places.

```sql
SELECT * FROM TD_RoundColumns(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2')                 -- required; explicit columns or range e.g. '[1:5]'
        PrecisionDigit(2)                             -- optional: decimal places to round to
                                                      -- positive = right of decimal (e.g. 2 → 3.14)
                                                      -- negative = left of decimal  (e.g. -2 → 300)
                                                      -- default: 0
        -- Accumulate('id_col', 'date_col')           -- optional: columns or range to pass through
) AS t;
```

---

## TD_StrApply — Apply String Operator to Columns

Applies a specified string operator to each value in the target columns.

```sql
-- Basic usage: apply operator in-place (default)
SELECT * FROM TD_StrApply(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        TargetColumns('col1', 'col2')                 -- required; explicit columns or range e.g. '[1:5]'
        StringOperation('TOUPPER')                    -- required; see operator list below
        InPlace('true')                               -- optional: overwrite target columns; default 'true'
) AS t;

-- Add output columns alongside originals (InPlace false)
SELECT * FROM TD_StrApply(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        TargetColumns('col1', 'col2')
        StringOperation('TOUPPER')
        InPlace('false')                              -- returns new columns; original columns are returned
                                                      -- only if listed in Accumulate
        OutputColumns('col1_upper', 'col2_upper')     -- optional: default is operator_target_column (e.g. TOUPPER_col1)
                                                      -- required if operator_target_column > 128 chars
        Accumulate('id_col')                          -- optional: columns or range to pass through
) AS t;

-- Operators requiring String argument:
--   STRINGCON    — concatenate:   String('_suffix')
--   STRINGINDEX  — find index:    String('search_term'), IsCaseSpecific('true')
--   STRINGLIKE   — pattern match: String('%pattern%'), EscapeString('\'), IgnoreTrailingBlank('false')
--   STRINGPAD    — pad value:     String(' '), StringLength(20), OperatingSide('Right')
--   STRINGTRIM   — trim value:    String('prefix_'), OperatingSide('Left')
SELECT * FROM TD_StrApply(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        TargetColumns('col1')
        StringOperation('STRINGPAD')
        String(' ')                                   -- pad character
        StringLength(20)                              -- target padded length
        OperatingSide('Right')                        -- optional: 'Left' (default) or 'Right'
) AS t;

-- Operators requiring StringLength and/or StartIndex:
--   GETNCHARS  — get N chars:  StringLength(5), OperatingSide('Left')
--   SUBSTRING  — substring:    StartIndex('1'), StringLength(10)
SELECT * FROM TD_StrApply(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        TargetColumns('col1')
        StringOperation('SUBSTRING')
        StartIndex('1')                               -- required with SUBSTRING: start position
        StringLength(10)                              -- required with SUBSTRING: length
) AS t;

-- Full operator reference:
--   CHARTOHEXINT  — convert to hex representation
--   GETNCHARS     — return N chars (OperatingSide, StringLength)
--   INITCAP       — capitalize first letter of each word
--   STRINGCON     — concatenate String to value
--   STRINGINDEX   — index of first occurrence of String (IsCaseSpecific)
--   STRINGLIKE    — match pattern (String, EscapeString, IsCaseSpecific, IgnoreTrailingBlank)
--   STRINGPAD     — pad to StringLength with String (OperatingSide)
--   STRINGREVERSE — reverse character order
--   STRINGTRIM    — trim String from value (OperatingSide)
--   SUBSTRING     — extract substring (StartIndex, StringLength)
--   TOLOWER       — to lowercase
--   TOUPPER       — to uppercase
--   TRIMSPACES    — trim leading and trailing spaces
--   UNICODESTRING — convert LATIN to UNICODE
```
