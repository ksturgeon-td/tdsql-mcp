# Teradata Text Analytic Functions

Native analytic table operator functions for tokenizing, classifying, and
extracting entities from text data. Inputs should typically be pre-tokenized
before passing to classifier and extraction functions.

---

## TD_NgramSplitter — Tokenize Text into N-grams

Splits input text into n-grams (sequences of N consecutive tokens). Commonly
used as a pre-processing step before classification or TF-IDF functions.

```sql
SELECT * FROM TD_NgramSplitter(
    ON { db.table | db.view | (query) }               -- no AS InputTable alias
    PARTITION BY ANY
    USING
        TextColumn('text_col')                        -- required; column containing input text
        Grams(2)                                      -- required; n-gram size(s):
                                                      --   single:   Grams(2)
                                                      --   multiple: Grams(1, 2, 3)
                                                      --   range:    Grams('1-3')
        [ Delimiter('\s+') ]                          -- optional; regex separating tokens; default '\s+'
        [ Punctuation('[`~#^&*()-]') ]                -- optional; regex of chars to strip; default '[`~#^&*()-]'
        [ Reset('[.?!]') ]                            -- optional; regex of sentence-boundary chars; default '[.?!]'
        [ OverLapping('true') ]                       -- optional; default 'true'
        [ ConvertToLowerCase('true') ]                -- optional; default 'true'
        [ OutputTotalGramCount('false') ]             -- optional; default 'false'
        [ NGramColName('ngram') ]                     -- optional; override output column name for ngram text
        [ NColName('n') ]                             -- optional; override output column name for gram size
        [ FrequencyColName('frequency') ]             -- optional; override output column name for count
        [ TotalGramCountColName('totalcnt') ]         -- optional; override output column name for total count
        [ Accumulate('id_col', 'cat_col') ]           -- optional; columns or range to pass through
) AS t;
```

> **Default output columns:** `ngram`, `n`, `frequency` (+ `totalcnt` if `OutputTotalGramCount('true')`)

---

## TD_NaiveBayesTextClassifierTrainer — Train a Text Classifier

Trains a Naive Bayes text classification model from pre-tokenized input.
Output is a model result set that can be stored for use with
`TD_NaiveBayesTextClassifierPredict`. Follows the Trainer/Predict pattern
(equivalent to Fit/Transform — see `fit-transform-pattern`).

> **Note:** Input must be pre-tokenized. Use `TD_NgramSplitter` or
> `TD_TextParser` to tokenize text before passing to this function.

```sql
-- Train and persist model to a table
CREATE TABLE db.my_nb_model AS (
    SELECT * FROM TD_NaiveBayesTextClassifierTrainer(
        ON { db.table | db.view | (query) } AS InputTable
        USING
            TokenColumn('token_col')                  -- required; column of individual tokens
            DocCategoryColumn('category_col')         -- required; column of document labels/classes
            [ ModelType('Multinomial') ]              -- optional; 'Multinomial' (default) or 'Bernoulli'
            [ DocIDColumn('doc_id_col') ]             -- required when ModelType is 'Bernoulli'
    ) AS t
) WITH DATA;

-- Inline (no persistence)
SELECT * FROM TD_NaiveBayesTextClassifierTrainer(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TokenColumn('token_col')
        DocCategoryColumn('category_col')
) AS t;
```

---

## TD_NaiveBayesTextClassifierPredict — Score Documents with a Trained Model

Applies a trained Naive Bayes model to pre-tokenized documents. Takes the
model output from `TD_NaiveBayesTextClassifierTrainer` as a DIMENSION input.

> **Note:** Input must be pre-tokenized. Use `TD_NgramSplitter` or
> `TD_TextParser` to tokenize text before passing to this function.

```sql
SELECT * FROM TD_NaiveBayesTextClassifierPredict(
    ON { db.table | db.view | (query) } AS PredictorValues
        PARTITION BY doc_id_col               -- PARTITION BY the document ID column (not PARTITION BY ANY)
    ON { db.table | db.view | (query) } AS Model DIMENSION
    USING
        InputTokenColumn('token_col')         -- required; column of individual tokens
        DocIDColumns('doc_id_col')            -- required; document ID column(s)
        [ ModelType('Multinomial') ]          -- optional; default 'Multinomial'; must match Trainer
        [ TopK(3) ]                           -- optional; return top K predicted categories
                                              --   TopK and Responses are mutually exclusive
        [ Responses('cat1', 'cat2') ]         -- optional; return scores for specific categories only
        [ OutputProb('false') ]               -- optional; include probability scores; default 'false'
        [ ModelTokenColumn('col') ]           -- optional; all three ModelXxxColumn args must be
        [ ModelCategoryColumn('col') ]        --   provided together, or all omitted
        [ ModelProbColumn('col') ]            --   defaults: 1st, 2nd, 3rd columns of Model table
        [ Accumulate('id_col', 'date_col') ]  -- optional; columns or range to pass through
) AS t;
```

---

## TD_SentimentExtractor — Sentiment Analysis

Extracts sentiment (positive, negative, or neutral) from each document or sentence using a built-in WordNet dictionary. Supports custom and additional dictionaries. English only.

```sql
SELECT * FROM TD_SentimentExtractor(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    [ ON { db.table | db.view | (query) } AS CustomDictionaryTable    DIMENSION ]
    [ ON { db.table | db.view | (query) } AS AdditionalDictionaryTable DIMENSION ]
    [ OUT PERMANENT TABLE OutputDictionaryTable(db.output_dict_table) ]
    USING
        TextColumn('text_col')                -- required
        [ AnalysisType('DOCUMENT') ]          -- optional; 'DOCUMENT' (default) or 'SENTENCE'
        [ Priority('NONE') ]                  -- optional; default 'NONE'
                                              --   'NEGATIVE_RECALL'    — maximize negative results returned
                                              --   'NEGATIVE_PRECISION' — high-confidence negatives only
                                              --   'POSITIVE_RECALL'    — maximize positive results returned
                                              --   'POSITIVE_PRECISION' — high-confidence positives only
        [ OutputType('ALL') ]                 -- optional; 'ALL' (default), 'POS', 'NEG', 'NEU'
        [ Accumulate('id_col', 'date_col') ]  -- optional; columns or range to pass through
) AS t;
```

**Output columns:**

| Column | Description |
|--------|-------------|
| `content` | Extracted sentence text — only present when `AnalysisType('SENTENCE')` |
| `polarity` | `'POS'`, `'NEG'`, or `'NEU'` |
| `sentiment_score` | `0` = neutral, `1` = above neutral, `2` = highest |
| `sentiment_words` | Total pos/neg scores + matched words with their polarity strength and frequency |

**Custom/Additional dictionary schema** (column names required as shown):

```sql
CREATE TABLE sentiment_dict (
    sentiment_word    VARCHAR(128),  -- sentiment term (max 128 chars)
    polarity_strength INTEGER        -- sentiment strength value
);
```

> **Notes:**
> - English only
> - Negation handling: `not happy` → flips polarity; `not very happy` (1 word between) → flips; `not saying I am happy` (2+ words between) → does not flip
> - `OUT PERMANENT TABLE OutputDictionaryTable(...)` writes the dictionary used to a table — useful for inspecting which terms drove results
> - `CustomDictionaryTable` replaces the default dictionary; `AdditionalDictionaryTable` extends either the custom or default dictionary

---

## TD_WordEmbeddings — Word and Document Embeddings

Maps tokens or documents to real-valued vectors using a pre-trained GloVe-format model. Supports embedding generation and similarity computation.

> **Note:** TD_WordEmbeddings uses static pre-trained word vectors (GloVe/Word2Vec format). Newer AI model-based embedding functions using transformer models are available in Teradata Vantage and may produce higher-quality embeddings for most use cases. See the AI/ML functions documentation for alternatives.

```sql
SELECT * FROM TD_WordEmbeddings(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                        -- required; unique row identifier
        ModelVectorColumns('[v1:v300]')            -- required; vector columns in ModelTable (list or range)
        ModelTextColumn('word_col')               -- required; column in ModelTable containing the token
        PrimaryColumn('text_col')                 -- required; input column containing text
        [ SecondaryColumn('text_col2') ]          -- optional; required for token2token-similarity
                                                  -- and doc2doc-similarity operations
        [ Operation('token-embedding') ]          -- optional; default 'token-embedding'
                                                  --   'token-embedding'        — vector per token
                                                  --   'doc-embedding'          — combined vector per document
                                                  --   'token2token-similarity' — similarity score between tokens
                                                  --   'doc2doc-similarity'     — similarity score between documents
        [ RemoveStopWords('false') ]              -- optional; default 'false'
                                                  -- not applicable for token2token-similarity
        [ ConvertToLowerCase('true') ]            -- optional; default 'true'
        [ StemTokens('false') ]                   -- optional; default 'false'
        [ Accumulate('id_col', 'date_col') ]      -- optional; not applicable with token-embedding
) AS t;
```

**Output columns (vary by Operation):**

| Column | Present when | Description |
|--------|-------------|-------------|
| `IDColumn` | always | Unique row identifier |
| `tokenColumn` | `token-embedding` only | Individual token from input text |
| `v1`, `v2`, ... `vN` | `token-embedding`, `doc-embedding` | Vector coordinates (one column per dimension) |
| `similarity` | `token2token-similarity`, `doc2doc-similarity` | Similarity score between primary and secondary text |

**Model table format** (GloVe format — one token per row):

```
word_col    v1        v2        v3        v4
assisted    0.10058   0.1914    0.28125   0.17382
by         -0.11572  -0.03149   0.15917   0.13867
delicious  -0.18164  -0.13281   0.03906   0.31445
```

> **Notes:**
> - Model must be in GloVe format; to convert Word2Vec, delete the first header row
> - `SecondaryColumn` is required for `token2token-similarity` and `doc2doc-similarity`
> - `Accumulate` is not supported with `token-embedding`
> - `RemoveStopWords` is not applicable for `token2token-similarity`

---

## TD_TFIDF — Term Frequency-Inverse Document Frequency

Computes TF-IDF scores for terms across a document corpus. Output vectors can be fed into clustering and classification algorithms (cosine similarity, K-means, K-NN, LDA, etc.).

> **Note:** Input must be pre-tokenized — use `TD_TextParser` or `TD_NgramSplitter` to produce one token per row before passing to this function.

```sql
SELECT * FROM TD_TFIDF(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY
    USING
        DocIdColumn('doc_id_col')             -- required; document identifier column
        TokenColumn('token_col')              -- required; column of individual tokens
        [ TFNormalization('NORMAL') ]         -- optional; default 'NORMAL'
                                              --   'BOOL'    — 1 if term present, else 0
                                              --   'COUNT'   — raw frequency f(t,d)
                                              --   'NORMAL'  — f(t,d) / total terms in doc
                                              --   'LOG'     — 1 + log(f(t,d))
                                              --   'AUGMENT' — 0.5 + 0.5 * f(t,d) / max_freq_in_doc
        [ IDFNormalization('LOG') ]           -- optional; default 'LOG'
                                              --   'UNARY'   — idf = 1 (disables IDF)
                                              --   'LOG'     — log(N / Nt)
                                              --   'LOGNORM' — 1 + log(N / Nt)
                                              --   'SMOOTH'  — 1 + log((1+N) / (1+Nt))
        [ Regularization('NONE') ]            -- optional; default 'NONE'
                                              --   'NONE' — tf * idf
                                              --   'L2'   — Euclidean: divide by sqrt(sum of squared tf*idf)
                                              --   'L1'   — Manhattan: divide by sum of abs(tf*idf)
        [ Accumulate('id_col', 'date_col') ]  -- optional; columns or range to pass through
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `doc_id_col` | INTEGER/BIGINT | Document identifier (name matches `DocIdColumn`) |
| `token_col` | CHAR/VARCHAR | Term (name matches `TokenColumn`) |
| `TD_TF` | FLOAT | Term frequency score |
| `TD_IDF` | FLOAT | Inverse document frequency score |
| `TD_TF_IDF` | FLOAT | Final TF-IDF score (`TD_TF * TD_IDF`, optionally regularized) |

---

## TD_TextTagger — Rule-Based Text Tagging

Tags text documents by evaluating user-defined rules using text-processing and logical operators. Rules can be specified inline or via a Rules dimension table.

```sql
SELECT * FROM TD_TextTagger(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    [ ON { db.table | db.view | (query) } AS Rules DIMENSION ]
    USING
        TaggingRules('rule AS tag' [,...])    -- required if no Rules table; disallowed if Rules table present
                                              -- max 2000 rules
        [ InputLanguage('en') ]               -- optional; default 'en'; English only
                                              -- required when Tokenize('true')
        [ Tokenize('false') ]                 -- optional; default 'false'
                                              -- tokenizes input text before evaluating rules
        [ OutputByTag('false') ]              -- optional; default 'false'
                                              --   'false' — one row per document; matched tags comma-separated
                                              --   'true'  — one row per matched tag per document
        [ TagDelimiter(',') ]                 -- optional; default ','
                                              -- separator for multiple tags in output
                                              -- error if OutputByTag('true')
        [ Accumulate('id_col', 'date_col') ]  -- optional; columns or range to pass through
) AS t;
```

**Output columns:**

| Column | Description |
|--------|-------------|
| `tag` | Matched tag name(s); empty string if no match. Multiple tags comma-separated when `OutputByTag('false')` |

**Rules table schema** (column names `tagname` and `definition` are required):

```sql
CREATE TABLE tagger_rules (
    tagname    VARCHAR CHARACTER SET LATIN,   -- tag label
    definition VARCHAR CHARACTER SET LATIN    -- rule expression (see operators below)
);
```

**Tagging rule operators:**

| Operation | Returns true when... |
|-----------|----------------------|
| `equal(col, op1)` | text in `col` equals `op1` |
| `contain(col, op1, lower, upper)` | `op1` appears in `col` between `lower` and `upper` times (either bound optional) |
| `dist(col, op1, op2, lower, upper)` | word distance between `op1` and `op2` in `col` is in `[lower, upper]` |
| `superdist(col, op1, op2, con1, op3, con2)` | `op1` satisfies context rules `con1`/`con2` relative to `op2`/`op3` (see below) |
| `op1 and op2` | both operations are true |
| `op1 or op2` | either operation is true |
| `not op` | operation is false |

**`superdist` context values (`con1`, `con2`):**

| Value | Inclusion meaning | Exclusion meaning |
|-------|------------------|------------------|
| `nwn` | `op2` within n words of `op1` | `op3` not within n words of `op1` |
| `nrn` | `op2` within n words after `op1` | `op3` not within n words after `op1` |
| `para` | `op2` in same paragraph as `op1` | `op3` not in same paragraph |
| `sent` | `op2` in same sentence as `op1` | `op3` not in same sentence |

> **Notes:**
> - Operands: string literals use double quotes (`"word"`); regex uses `regex"pattern"` (Java regex)
> - Lists of operands separated by semicolons: `"good;bad"` or `regex"invest[\w];risk[\w]"`
> - In `TaggingRules`: backslashes in regex must be doubled (`regex"from\\s+"`)
> - In Rules table: backslashes are not doubled (`regex"from\s+"`)
> - String literal matching is case-insensitive; regex matching is case-sensitive

**Example:**

```sql
-- Inline rules
SELECT * FROM TD_TextTagger(
    ON reviews AS InputTable PARTITION BY ANY
    USING
        TaggingRules(
            'contain(review_text, "excellent", 1,) AS positive',
            'contain(review_text, "terrible", 1,) AS negative'
        )
        OutputByTag('true')
        Accumulate('review_id')
) AS t;

-- Rules table
SELECT * FROM TD_TextTagger(
    ON reviews AS InputTable PARTITION BY ANY
    ON tagger_rules AS Rules DIMENSION
    USING
        OutputByTag('true')
        Accumulate('review_id')
) AS t;
```

---

## TD_TextParser — Text Tokenization and Parsing

Tokenizes input text into individual tokens (words/stems). Commonly used as a pre-processing step for classification, TF-IDF, and other text analytic functions.

```sql
SELECT * FROM TD_TextParser(
    ON { db.table | db.view | (query) } AS InputTable     -- no PARTITION BY
    [ ON { db.table | db.view | (query) } AS StopWordsTable DIMENSION ]
    USING
        TextColumn('text_col')                    -- required; column containing input text
        [ ConvertToLowerCase('true') ]            -- optional; default 'true'
                                                  -- forced 'true' when StemTokens is 'true'
        [ StemTokens('false') ]                   -- optional; default 'false'
                                                  -- reduces tokens to root forms
        [ RemoveStopWords('false') ]              -- optional; default 'false'
                                                  -- requires StopWordsTable if 'true'
        [ Delimiter(' \t\n\f\r') ]                -- optional; single-character delimiters
                                                  -- default: ' \t\n\f\r'
        [ DelimiterRegex('regex') ]               -- optional; PCRE regex as token delimiter
                                                  -- alternative to Delimiter; no default
        [ Punctuation('!#$%&()*+,-./:;?@\^_`{|}~') ]
                                                  -- optional; chars replaced with space
        [ TokenColName('token') ]                 -- optional; output column name; default 'token'
        [ DocIDColumn('doc_id_col') ]             -- optional; unique row identifier
                                                  -- required when OutputByWord('true') AND
                                                  -- ListPositions or TokenFrequency is 'true'
        [ ListPositions('false') ]                -- optional; default 'false'
                                                  -- outputs comma-separated positions per token
                                                  -- ignored when OutputByWord('false')
        [ TokenFrequency('false') ]               -- optional; default 'false'
                                                  -- outputs total occurrence count per token
                                                  -- ignored when OutputByWord('false')
        [ OutputByWord('true') ]                  -- optional; default 'true'
                                                  --   'true'  — one row per token
                                                  --   'false' — all tokens in a single cell (space-separated)
        [ Accumulate('id_col', 'date_col') ]      -- optional; columns or range to pass through
                                                  -- default: all input columns copied to output
) AS t;
```

**Output columns:**

| Column | Present when | Description |
|--------|-------------|-------------|
| `doc_id_col` | `DocIDColumn` provided | Always first column if present |
| `token` | always (name via `TokenColName`) | Individual token |
| `frequency` | `TokenFrequency('true')` | Total occurrences of the token |
| `locations` | `ListPositions('true')` | Comma-separated positions (ascending); BIGINT per-row when `ListPositions('false')` + `OutputByWord('true')` |
| `tokens` | `OutputByWord('false')` | Space-separated list of all tokens in a single cell |

**StopWordsTable schema** (column name `words` is required):

```sql
CREATE TABLE stop_words (
    words VARCHAR CHARACTER SET LATIN   -- or CHAR, CLOB, or UNICODE
);
```

> **Notes:**
> - No `PARTITION BY` — this function does not use it
> - `Delimiter` and `DelimiterRegex` are alternatives; `DelimiterRegex` takes a PCRE pattern while `Delimiter` takes literal single characters
> - When `OutputByWord('false')`: `ListPositions` and `TokenFrequency` are ignored; all tokens output as one space-separated cell

---

## TD_TextMorph — Lemmatization (Morphological Reduction)

Generates the standard/dictionary form (lemma) of input tokens using an English dictionary. Optionally filters or tags by part of speech.

```sql
SELECT * FROM TD_TextMorph(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY
    USING
        WordColumn('word_col')                  -- required; column of tokens to lemmatize
                                                -- max 1 column; English only (LATIN or UNICODE)
        [ POSTagColumn('pos_tag_col') ]         -- optional; column of POS tags for each word
                                                -- if provided, morphs are generated per POS tag
        [ SingleOutput('true') ]                -- optional; default 'true'
                                                --   'true'  — one morph per word (first by precedence)
                                                --   'false' — all morphs for each word
        [ POS('noun', 'verb') ]                 -- optional; filter output to specific POS
                                                --   values: 'noun', 'verb', 'adj', 'adv'
                                                --   precedence order: noun > verb > adj > adv
                                                --   default: all parts of speech
        [ Accumulate('id_col', 'date_col') ]    -- optional; columns or range to pass through
) AS t;
```

**Output columns:**

| Column | Description |
|--------|-------------|
| `word_column` | Input token (same name as the `WordColumn` argument) |
| `TD_Morph` | Standard/dictionary form of the token |
| `POS` | Part of speech: `'noun'`, `'verb'`, `'adj'`, or `'adv'` |

> **Notes:**
> - No `PARTITION BY` — this function does not use it
> - The function uses all possible POS for a word from the dictionary — it does not infer POS from context
> - With `SingleOutput('true')` and `POS(...)`, only the first matching POS by precedence is returned

---

## TD_NERExtractor — Named Entity Recognition

Extracts named entities from text by matching against dictionary terms or
regular expression patterns. Supports both rule-based (regex) and
dictionary-based matching simultaneously.

```sql
SELECT * FROM TD_NERExtractor(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    [ ON { db.table | db.view | (query) } AS Dict  DIMENSION ]   -- dictionary terms
    [ ON { db.table | db.view | (query) } AS Rules DIMENSION ]   -- regex patterns
    USING
        TextColumn('text_col')                    -- required; max 1 column
        [ InputLanguage('en') ]                   -- optional; default 'en' (English)
        [ ShowContext(3) ]                        -- optional; number of context words
                                                  -- before/after each match
        [ Accumulate('id_col', 'date_col') ]      -- optional; columns or range to pass through
) AS t;
```

**Output columns** (always present):

| Column | Description |
|--------|-------------|
| `entity` | Matched text |
| `"type"` | Entity label (from `type_ner` in Dict or Rules) — reserved word, requires quoting |
| `start` | Start word position of match |
| `end` | End word position of match |
| `context` | Surrounding words (controlled by `ShowContext`) |
| `approach` | `'RULE'` or `'DICT'` — which table produced the match |

**Dict table schema** (`type_ner` and `dict` column names are required):

```sql
CREATE MULTISET TABLE ner_dict (
    type_ner  VARCHAR(500),   -- entity label
    dict      VARCHAR(500)    -- dictionary term OR regex pattern
);
```

**Rules table schema** (`type_ner` and `regex` column names are required):

```sql
CREATE MULTISET TABLE ner_rules (
    type_ner  VARCHAR(500),   -- entity label
    regex     VARCHAR(500)    -- regular expression pattern
);
```

> **Notes:**
> - Dict matching trims leading/trailing whitespace and is case-insensitive;
>   dict entries can also contain regex patterns
> - `start`/`end` are word positions, not character offsets
> - Either or both of Dict and Rules can be omitted
> - Regex escaping: most special characters need one backslash (`\$`, `\.`, `\+`, etc.) —
>   double-escaping is not required

**Example:**

```sql
SELECT id, entity, "type", "start", "end", context, approach
FROM TD_NERExtractor(
    ON ner_input        AS InputTable PARTITION BY ANY
    ON ner_dict         AS Dict  DIMENSION
    ON ner_rules        AS Rules DIMENSION
    USING
        TextColumn('txt')
        InputLanguage('en')
        ShowContext(3)
        Accumulate('id')
) AS t
ORDER BY id, "start";
```
