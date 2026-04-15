# Teradata Hypothesis Testing Functions

Statistical hypothesis testing functions for comparing group means, distributions,
variances, and proportions.

---

## TD_ANOVA — One-Way Analysis of Variance

Tests whether the means of two or more groups are significantly different. Returns F-statistic, p-value, and pass/fail conclusion.

```sql
-- Mode 1: wide format (one column per group)
SELECT * FROM TD_ANOVA(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        GroupColumns('col_a', 'col_b', 'col_c')   -- required (Mode 1); column per group
                                                   -- list or range; supports Unicode
        [ Alpha(0.05) ]                            -- optional; significance level; default 0.05
                                                   -- valid range: [0, 1]
) AS t;

-- Mode 2: long format (group name + value columns)
SELECT * FROM TD_ANOVA(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        GroupNameColumn('group_col')               -- required (Mode 2); column of group labels
        GroupValueColumn('value_col')              -- required (Mode 2); column of numeric values
        GroupNames('group_a', 'group_b')           -- required (Mode 2); specify groups by name
                                                   --   GroupNames and NumGroups are mutually exclusive
                                                   --   Unicode and double quotes not supported
      | NumGroups(3)                               -- alternative to GroupNames; specify number of groups
        [ Alpha(0.05) ]
) AS t;
```

**Input format notes:**

| Mode | Format | Key argument |
|------|--------|-------------|
| Mode 1 | Wide — one column per group, rows are observations | `GroupColumns` |
| Mode 2 | Long — one row per observation with group label | `GroupNameColumn` + `GroupValueColumn` + `GroupNames`/`NumGroups` |

**Output columns** (one row per test):

| Column | Type | Description |
|--------|------|-------------|
| `sum_of_squares (between groups)` | DOUBLE | Variation between group means |
| `sum_of_squares (within groups)` | DOUBLE | Variation within groups |
| `Df (between groups)` | INTEGER | Degrees of freedom between groups (k-1) |
| `Df (within groups)` | INTEGER | Degrees of freedom within groups (N-k+1) |
| `mean_square (between groups)` | DOUBLE | Between-group SS / Df |
| `mean_square (within groups)` | DOUBLE | Within-group SS / Df |
| `F_statistic` | DOUBLE | Ratio of between/within mean squares; reject null when > `critical_f` |
| `alpha` | DOUBLE | Significance level used |
| `critical_f` | DOUBLE | Critical F value at (k-1, N-k) degrees of freedom |
| `p_value` | DOUBLE | Probability of observed F under null hypothesis; reject null when < `alpha` |
| `conclusion` | VARCHAR | Test result — null hypothesis rejected or not |

> **Notes:**
> - Assumes normally distributed data with approximately equal group variances
> - `GroupNames` and `NumGroups` are mutually exclusive
> - No `PARTITION BY` — function does not use it

---

## TD_ChiSq — Chi-Square Test for Independence

Performs Pearson's chi-squared test on a contingency table to determine if two categorical variables are statistically independent. Returns chi-square statistic, Cramer's V, degrees of freedom, and p-value.

```sql
SELECT * FROM TD_ChiSq(
    ON { db.table | db.view | (query) } AS CONTINGENCY   -- alias must be CONTINGENCY (not InputTable)
    [ OUT [ PERMANENT | VOLATILE ] TABLE EXPCOUNTS(db.expected_values_table) ]
    USING
        [ Alpha(0.05) ]                           -- optional; significance level; default 0.05
                                                  -- valid range: [0, 1]
) AS t;
```

**Input — contingency table format:**

The input must be a pre-aggregated cross-tabulation (contingency table). Each row is a label of category 1; each column (after the first) is a label of category 2, containing joint frequency counts.

```
gender    smoker    non_smoker
female    32        78
male      45        65
```

> - First column: category 1 labels (any type — INTEGER, LATIN, or UTF8)
> - Remaining columns: INTEGER frequency counts per category 2 label
> - Each observed frequency must be **≥ 5** for a valid test
> - Max 2046 unique labels for category 2; NULL values are ignored

**Output columns** (one row per test):

| Column | Type | Description |
|--------|------|-------------|
| `chi_square` | DOUBLE | Chi-squared statistic |
| `cramers_v` | DOUBLE | Cramer's V effect size statistic |
| `df` | INTEGER | Degrees of freedom |
| `alpha` | DOUBLE | Significance level used |
| `p_value` | DOUBLE | Probability under null hypothesis; reject null when < `alpha` |
| `criticalvalue` | DOUBLE | Critical chi-square value at given alpha and df |
| `conclusion` | VARCHAR | `'reject null hypothesis'` or `'fail to reject null hypothesis'` |

**EXPCOUNTS table** (only written when `OUT` clause is used):
Same schema as the CONTINGENCY input table, but all frequency columns are `DOUBLE PRECISION`. Contains expected frequencies under the null hypothesis.

> **Notes:**
> - No `PARTITION BY` — function does not use it
> - Input alias must be `CONTINGENCY`, not `InputTable`
> - Supported test types: one-tailed (upper), one-sample, unpaired

---

## TD_FTest — F-Test for Variance Comparison

Compares the variances of two samples to determine if they are drawn from populations with equal variance. Supports wide-format columns, long-format group-value input, or pre-computed variance values (no table required).

```sql
-- Mode 1: wide format (two columns in InputTable)
SELECT * FROM TD_FTest(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        FirstSampleColumn('col_a')                -- required (Mode 1); do not use with FirstSampleVariance
        SecondSampleColumn('col_b')               -- required (Mode 1); do not use with SecondSampleVariance
        [ AlternativeHypothesis('two-tailed') ]   -- optional; default 'two-tailed'
                                                  --   'lower-tailed' — H1: μ < μ0
                                                  --   'upper-tailed' — H1: μ > μ0
                                                  --   'two-tailed'   — H1: μ ≠ μ0
        [ Alpha(0.05) ]                           -- optional; significance level; default 0.05
) AS t;

-- Mode 2: long format (group name + value columns)
SELECT * FROM TD_FTest(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        SampleNameColumn('group_col')             -- required (Mode 2); column of group labels
        SampleValueColumn('value_col')            -- required (Mode 2); column of numeric values
        [ FirstSampleName('group_a') ]            -- optional; filter to first group by name
        [ SecondSampleName('group_b') ]           -- optional; filter to second group by name
        [ AlternativeHypothesis('two-tailed') ]
        [ Alpha(0.05) ]
) AS t;

-- Mode 3: pre-computed variances (no InputTable required)
SELECT * FROM TD_FTest(
    USING
        FirstSampleVariance(12.5)                 -- required (Mode 3); do not use with FirstSampleColumn
        SecondSampleVariance(9.3)                 -- required (Mode 3); do not use with SecondSampleColumn
        df1(49)                                   -- required (Mode 3); numerator degrees of freedom
        df2(49)                                   -- required (Mode 3); denominator degrees of freedom
        [ AlternativeHypothesis('two-tailed') ]
        [ Alpha(0.05) ]
) AS t;
```

**Output columns** (one row per test):

| Column | Type | Description |
|--------|------|-------------|
| `FirstSampleVariance` | DOUBLE | Variance of first sample |
| `SecondSampleVariance` | DOUBLE | Variance of second sample |
| `VarianceRatio` | DOUBLE | FirstSampleVariance / SecondSampleVariance |
| `DF1` | INTEGER | Degrees of freedom for first sample |
| `DF2` | INTEGER | Degrees of freedom for second sample |
| `CriticalValue` | DOUBLE | Critical F value at given alpha |
| `Alpha` | DOUBLE | Significance level used |
| `p_value` | DOUBLE | Probability under null hypothesis; reject null when < `Alpha` |
| `Conclusion` | VARCHAR | `'reject null hypothesis'` or `'fail to reject null hypothesis'` |

> **Notes:**
> - `ON InputTable` is optional — omit entirely when using Mode 3 (pre-computed variances)
> - `FirstSampleColumn`/`SecondSampleColumn` and `SampleNameColumn`/`SampleValueColumn` are mutually exclusive
> - If using columns to compute variance, do not also specify `FirstSampleVariance`/`SecondSampleVariance`
> - `df1`/`df2` are inferred from the data in Modes 1 and 2; required only in Mode 3

---

## TD_ZTest — Z-Test for Means

Tests whether one or two sample means are significantly different. Uses known population variance when provided; approximates from sample when n ≥ 30. Supports one-sample and two-sample tests.

```sql
-- Mode 1: wide format (one or two columns in InputTable)
SELECT * FROM TD_ZTest(
    ON { db.table | db.view | (query) }               -- note: no AS alias in this function
    USING
        FirstSampleColumn('col_a')                    -- required (Mode 1)
        [ SecondSampleColumn('col_b') ]               -- optional; omit for one-sample test
        [ FirstSampleVariance(25.0) ]                 -- required if n < 30; optional if n >= 30
        [ SecondSampleVariance(18.5) ]                -- required if SecondSampleColumn and n < 30
        [ AlternativeHypothesis('two-tailed') ]       -- optional; default 'two-tailed'
                                                      --   'upper-tailed' — H1: μ > μ0
                                                      --   'lower-tailed' — H1: μ < μ0
                                                      --   'two-tailed'   — H1: μ ≠ μ0
        [ MeanUnderH0(0) ]                            -- optional; null hypothesis mean; default 0
        [ Alpha(0.05) ]                               -- optional; significance level; default 0.05
) AS t;

-- Mode 2: long format (group name + value columns)
SELECT * FROM TD_ZTest(
    ON { db.table | db.view | (query) }
    USING
        SampleNameColumn('group_col')                 -- required (Mode 2)
        SampleValueColumn('value_col')                -- required (Mode 2)
        FirstSampleName('group_a')                    -- required (Mode 2)
        [ SecondSampleName('group_b') ]               -- optional; omit for one-sample test
        [ FirstSampleVariance(25.0) ]
        [ SecondSampleVariance(18.5) ]
        [ AlternativeHypothesis('two-tailed') ]
        [ MeanUnderH0(0) ]
        [ Alpha(0.05) ]
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `sample_column_1` | VARCHAR | First sample identifier |
| `sample_column_2` | VARCHAR | Second sample identifier — only present in two-sample test |
| `N1` | INTEGER | First sample size |
| `N2` | INTEGER | Second sample size — only present in two-sample test |
| `mean1` | DOUBLE | First sample mean |
| `mean2` | DOUBLE | Second sample mean — only present in two-sample test |
| `AlternativeHypothesis` | VARCHAR | H1 accepted if null is rejected |
| `z_score` | DOUBLE | Z-test statistic |
| `Alpha` | DOUBLE | Significance level used |
| `CriticalValue` | DOUBLE | Critical Z value at given alpha |
| `p_value` | DOUBLE | Probability under null hypothesis; reject null when < `Alpha` |
| `Conclusion` | VARCHAR | `'reject null hypothesis'` or `'fail to reject null hypothesis'` |

> **Notes:**
> - No `AS` alias on the `ON` clause — this function does not use an input alias
> - One-sample test: omit `SecondSampleColumn`/`SecondSampleName`
> - `FirstSampleVariance` is required when sample size < 30; for larger samples the function approximates variance from the data
> - Rejection confidence level is `1 - Alpha` when null hypothesis is rejected
