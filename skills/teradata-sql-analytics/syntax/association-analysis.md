# Teradata Association Analysis Functions

Functions for discovering frequent itemsets, association rules, and
collaborative filtering recommendations from transactional data.

---

## TD_Apriori — Frequent Itemset Mining and Association Rules

Discovers frequent patterns (itemsets) and association rules in transactional data. Classic application is market basket analysis. Supports both dense (items in one delimited cell) and sparse (one row per item) input formats.

```sql
SELECT * FROM TD_Apriori(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    [ OUT TABLE OutputTable('db.pattern_table') ]     -- optional; writes output to a named table
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
                                                      --   'Both'     — patterns and rules
        [ Support(0.01) ]                             -- optional; min itemset frequency as proportion
                                                      -- of total transactions; range (0,1]; default 0.01
) AS t;
```

**Input formats:**

| Format | Description | IDColumn |
|--------|-------------|----------|
| Dense | One row per transaction; items in a single delimited cell in `TargetColumn` | Not used |
| Sparse | One row per item; `IDColumn` groups items into a transaction | Required |

**Output — Patterns** (`PatternsOrRules('Patterns')` or `'Both'`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Itemset` | VARCHAR | Comma-separated (or `OutputDelimiter`) set of items |
| `Support` | REAL | Proportion of transactions containing this itemset |

**Output — Rules** (`PatternsOrRules('Rules')` or `'Both'`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Antecedent` | VARCHAR | The "if" item(s) in the rule |
| `Consequence` | VARCHAR | The "then" item(s) in the rule |
| `Ante_ItemCnt` | — | Item count for antecedent (undocumented in source) |
| `Conse_Item_Cnt` | — | Item count for consequence (undocumented in source) |
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
        [ MaxDistinctItems(100) ]                     -- optional; max item set size; default 100
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
| `z_score` | REAL | `(cntb - mean(cntb)) / sd(cntb)` — co-occurrence significance; not calculated if all `cntb` values are equal |

> **Notes:**
> - Always pairwise — unlike `TD_Apriori`, does not produce itemsets of size > 2 or association rules
> - `TransactionIDColumns` accepts multiple columns (composite transaction key)
> - `z_score` is null/absent when all `cntb` values are equal (sd = 0)
