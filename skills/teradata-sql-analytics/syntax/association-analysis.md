# Teradata Association Analysis Functions

Functions for discovering frequent itemsets, association rules, and
collaborative filtering recommendations from transactional data.

---

## TD_Apriori — Frequent Itemset Mining and Association Rules

Discovers frequent patterns (itemsets) and association rules in transactional data. Classic application is market basket analysis. Supports both dense (items in one delimited cell) and sparse (one row per item) input formats.

```sql
SELECT * FROM TD_Apriori(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    USING
        TargetColumn('item_col')                      -- required; column containing item data; max 1
        [ IDColumn('transaction_id_col') ]            -- required for sparse input; groups items into transactions
        [ PartitionColumns('region_col', 'store_col') ] -- optional; partition input and output; max 10
        [ MaxLen(2) ]                                 -- optional; max itemset size; default 2; max 20
        [ InputDelimiter(',') ]                       -- optional; delimiter for dense input; default ','
                                                      -- only applicable for dense input format
        [ OutputDelimiter(',') ]                      -- optional; delimiter in Itemset output column; default ','
        [ PatternsOrRules('Patterns') ]               -- optional; default 'Patterns'
                                                      --   'Patterns' — frequent itemsets only
                                                      --   'Rules'    — association rules with metrics
                                                      -- 'Both' is rejected (error 7810); run the function twice to get both outputs
        [ Support(0.01) ]                             -- optional; min itemset frequency as proportion
                                                      -- of total transactions; range (0,1]; default 0.01
                                                      -- threshold is inclusive (itemsets at exactly the threshold are returned)
) AS t;

-- TD_Apriori has no OUT TABLE clause (error 7810). To save the output, wrap the call in CREATE TABLE AS.
-- Use MULTISET so repeated rows are not dropped:
CREATE MULTISET TABLE db.pattern_table AS (
    SELECT * FROM TD_Apriori(
        ON db.baskets AS InputTable PARTITION BY ANY
        USING TargetColumn('item') IDColumn('txn') Support(0.2)
    ) AS t
) WITH DATA;
```

**Input formats:**

| Format | Description | IDColumn |
|--------|-------------|----------|
| Dense | One row per transaction; items in a single delimited cell in `TargetColumn` | Not used |
| Sparse | One row per item; `IDColumn` groups items into a transaction | Required |

> **Character set:** `TargetColumn` must be a LATIN column. Unicode input causes `Itemset` values to contain NUL characters between every letter (e.g. `CHAR_LENGTH('bread,milk')` returns 19 instead of 10). Convert Unicode columns first:
> ```sql
> SELECT * FROM TD_Apriori(
>     ON (SELECT TRANSLATE(items USING UNICODE_TO_LATIN) AS items FROM db.baskets) AS InputTable PARTITION BY ANY
>     USING TargetColumn('items') InputDelimiter(',') Support(0.2)
> ) AS t;
> ```
> This was observed on dense input. Sparse Unicode input was not tested.

> **Single-item itemsets:** Without `PartitionColumns`, `Patterns` output contains only itemsets of 2 to `MaxLen` items — single-item itemsets are not returned. With `PartitionColumns`, single items above the support threshold are included. To compute single-item support without a partition, use a separate query:
> ```sql
> SELECT item, COUNT(DISTINCT txn) * 1.0 / (SELECT COUNT(DISTINCT txn) FROM db.baskets) AS support
> FROM db.baskets GROUP BY item;
> ```

**Output — Patterns** (`PatternsOrRules('Patterns')`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Itemset` | VARCHAR | Comma-separated (or `OutputDelimiter`) set of items |
| `Support` | REAL | Proportion of transactions containing this itemset |

**Output — Rules** (`PatternsOrRules('Rules')`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Antecedent` | VARCHAR | The "if" item(s) in the rule |
| `Consequence` | VARCHAR | The "then" item(s) in the rule |
| `Ante_Item_Cnt` | INTEGER | Number of items in the antecedent |
| `Conse_Item_Cnt` | INTEGER | Number of items in the consequence |
| `cntb` | INTEGER | Co-occurrence count of antecedent and consequence |
| `Cnt_Antecedent` | INTEGER | Occurrence count of antecedent |
| `Cnt_Consequence` | INTEGER | Occurrence count of consequence |
| `Score` | REAL | `(cntb²) / (Cnt_Antecedent × Cnt_Consequence)` — product of conditional probabilities |
| `Support` | REAL | `cntb / tran_cnt` — proportion of transactions containing both items |
| `Confidence` | REAL | `cntb / Cnt_Antecedent` — proportion of antecedent transactions that also contain consequence |
| `Lift` | REAL | `support(A∩B) / (support(A) × support(B))` — >1 positive association, =1 independent, <1 negative |
| `Conviction` | REAL | `(1 - Cnt_Consequence/tran_cnt) / (1 - cntb/Cnt_Antecedent)` — implication strength |
| `Leverage` | REAL | Difference between observed co-occurrence and expected if independent |
| `Coverage` | REAL | `Cnt_Antecedent / tran_cnt` — antecedent support (proportion where rule applies) |
| `Chi_Square` | REAL | Chi-squared statistic testing independence of antecedent and consequence |

---

## TD_CFilter — Collaborative Filtering (Pairwise Item Affinity)

Computes co-occurrence statistics for every pair of items across transactions. Simpler than TD_Apriori — always produces pairwise results (no itemsets larger than 2, no rules mode). Typical use: product recommendation, market basket affinity scoring.

```sql
SELECT * FROM TD_CFilter(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    USING
        TargetColumn('item_col')                      -- required; item column; max 1
        TransactionIDColumns('txn_id_col')            -- required; column(s) grouping items into
                                                      -- a transaction; max 2047 columns
        [ PartitionColumns('region_col') ]            -- optional; partition input and output; max 10
                                                      -- output is nondeterministic unless each
                                                      -- partition_col is unique within TransactionIDColumns
        [ MaxDistinctItems(100) ]                     -- optional; maximum number of distinct items in one transaction; default 100
                                                      -- transactions with more items are silently excluded from all counts
) AS t;
```

**Output columns** (one row per item pair per partition):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `TD_item1` | VARCHAR | First item in the pair |
| `TD_item2` | VARCHAR | Second item in the pair |
| `cntb` | INTEGER | Co-occurrence count of both items |
| `cnt1` | INTEGER | Occurrence count of item1 |
| `cnt2` | INTEGER | Occurrence count of item2 |
| `score` | REAL | `(cntb²) / (cnt1 × cnt2)` — product of conditional probabilities |
| `support` | REAL | `cntb / tran_cnt` — proportion of transactions containing both items |
| `confidence` | REAL | `cntb / cnt1` — proportion of item1 transactions that also contain item2 |
| `lift` | REAL | `support(A∩B) / (support(A) × support(B))` — >1 positive, =1 independent, <1 negative |
| `z_score` | REAL | `(cntb - mean(cntb)) / population_sd(cntb)` — co-occurrence significance; not calculated if all `cntb` values are equal |

> **Notes:**
> - Always pairwise — unlike `TD_Apriori`, does not produce itemsets of size > 2 or association rules
> - `TransactionIDColumns` accepts multiple columns (composite transaction key)
> - **Each pair appears in both directions** — `(bread, milk)` and `(milk, bread)` are separate rows, with `cnt1`, `cnt2`, and `confidence` swapped; the guide's "one row per item pair" is inaccurate
> - `z_score` uses the **population** standard deviation (not sample); it is null/absent when all `cntb` values are equal (sd = 0)
