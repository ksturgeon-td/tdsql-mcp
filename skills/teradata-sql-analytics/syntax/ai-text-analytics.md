# Teradata Text Analytic AI Functions

Teradata provides a family of AI functions that call LLM endpoints to perform NLP tasks in-database. All functions share the same provider configuration pattern and are schema-qualified under `TD_SYSFNLIB`.

> **Prerequisites:** An authorization object and LLM provider must be configured before using these functions. See `authorization-objects` and `llm-providers` topics.

> **Schema qualifier required:** All functions use `TD_SYSFNLIB.<FunctionName>(...)`.

> **No PARTITION BY:** These functions manage parallelism internally. Do not add a PARTITION BY clause.

> **Provider block:** All functions accept the same provider configuration in their `USING` clause. See `llm-providers` topic for full syntax per provider. The provider block always contains `ApiType(...)` plus either an `AUTHORIZATION` object or inline credentials.

---

## Function Summary

| Function | Description |
|----------|-------------|
| `AI_AnalyzeSentiment` | Classifies text as positive, negative, or neutral |
| `AI_AskLLM` | Free-form LLM prompt against a text column |
| `AI_DetectLanguage` | Detects the language of input text |
| `AI_ExtractKeyPhrases` | Extracts key phrases from text |
| `AI_MaskPII` | Detects and masks personally identifiable information |
| `AI_RecognizeEntities` | Identifies named entities (people, places, organizations, etc.) |
| `AI_RecognizePIIEntities` | Identifies PII entities with type and position metadata |
| `AI_TextClassifier` | Classifies text into user-defined categories |
| `AI_TextSummarize` | Generates a summary of input text |
| `AI_TextTranslate` | Translates text from one language to another |

---

## AI_AnalyzeSentiment

Analyzes the sentiment of text in a specified column. Returns a sentiment label (typically `positive`, `negative`, or `neutral`) for each input row.

> **Note:** Sentiment label casing may vary by LLM provider. Normalize with `LOWER()` in downstream logic if consistent casing is required.

```sql
SELECT * FROM TD_SYSFNLIB.AI_AnalyzeSentiment(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Sentiment` | VARCHAR | Sentiment label: typically `positive`, `negative`, or `neutral`; casing may vary by provider |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**Input column types:** `TextColumn` accepts `VARCHAR`, `CHAR`, or `CLOB`. For `CLOB` input, effective text length is limited by the LLM provider's token limit.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_AnalyzeSentiment(
    ON db.customer_reviews AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('review_text')
        Accumulate('review_id', 'customer_id')
) AS t;
```

---

## AI_AskLLM

Applies a custom prompt to a text column, combining a question table and a context/data table. Enables free-form LLM queries against in-database content — useful for RAG-style question answering, document interrogation, and templated analysis.

> **Two-table input:** This function is unique among the AI_ family — it requires both an InputTable (questions) and a ContextTable (context data), co-partitioned by a shared key value.

> **DATAPOSITION is required** — it is missing from the Teradata documentation table but must be specified. Omitting it will cause an error.

```sql
SELECT * FROM TD_SYSFNLIB.AI_AskLLM(
    ON { db.question_table | (query) } AS InputTable PARTITION BY key_col
    ON { db.context_table  | (query) } AS ContextTable PARTITION BY key_col
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('question_col')                      -- required; question column from InputTable
        ContextColumn('context_col')                    -- required; data column from ContextTable
        Prompt('prompt text with #QUESTION# and #DATA# placeholders')  -- required; custom prompt template
        QUESTIONPOSITION('#QUESTION#')                  -- required; placeholder marker for question text in prompt
        DATAPOSITION('#DATA#')                          -- required (undocumented in Teradata docs — must be specified)
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns from InputTable to copy to output; '[0:]' = all
) AS t;
```

**How the join works:**

InputTable and ContextTable are co-partitioned on key value (not column name — the column names can differ). Rows where the key values match are processed together:

- One output row is produced **per question row**
- All ContextTable rows matching that key are **concatenated with escaped newlines** into the `#DATA#` placeholder
- Multiple questions can share a key, each producing its own output row with the same combined context

```
-- Example: questions table (qid, question)
1, 'What city is mentioned?'
1, 'What state is mentioned?'
2, 'What is the recipe about?'

-- Example: context table (cid, doc)
1, 'The fairest city in the United States is'
1, 'Saint Augustine, Florida'
2, 'How to make baloney'
2, 'sandwiches'

-- Output: 3 rows
-- qid=1, question 1 → context = both cid=1 rows concatenated
-- qid=1, question 2 → context = both cid=1 rows concatenated
-- qid=2, question 1 → context = both cid=2 rows concatenated
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as InputTable | Columns copied from InputTable (questions table) |
| `Output` | VARCHAR | LLM response for this question/context pair |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_AskLLM(
    ON (SELECT qid, question FROM db.questions) AS InputTable PARTITION BY qid
    ON (SELECT cid, doc      FROM db.documents) AS ContextTable PARTITION BY cid
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('question')
        ContextColumn('doc')
        Prompt('Answer the question using only the provided data.\nQuestion: #QUESTION#\nData: #DATA#')
        QUESTIONPOSITION('#QUESTION#')
        DATAPOSITION('#DATA#')
        Accumulate('qid', 'question')
) AS t;
```

---

## AI_DetectLanguage

Detects the language of text in a specified column. Returns a language label for each input row.

> **Note:** Output language label format (name vs. ISO code) may vary by LLM provider. The `Lang` argument can bias detection toward specific languages when the input is ambiguous.

```sql
SELECT * FROM TD_SYSFNLIB.AI_DetectLanguage(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ Lang('Language1,Language2,...') ]             -- optional; comma-separated list of language names to prioritize
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Language` | VARCHAR | Detected language; format (name or ISO code) may vary by provider |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`Lang` argument:** Specifies languages to give priority when detection is ambiguous. Pass a comma-separated list of language names (e.g., `'French,Dutch'`). Does not restrict detection — other languages can still be returned if the model is confident.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_DetectLanguage(
    ON db.support_tickets AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('ticket_text')
        Lang('French,Dutch,German')
        Accumulate('ticket_id', 'region')
) AS t;
```

---

## AI_ExtractKeyPhrases

Extracts key phrases from text in a specified column. Returns a comma-separated list of phrases for each input row.

```sql
SELECT * FROM TD_SYSFNLIB.AI_ExtractKeyPhrases(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Key_Phrases` | VARCHAR | Comma-and-space-delimited list of extracted key phrases (e.g., `'supply chain, lead time, inventory risk'`) |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_ExtractKeyPhrases(
    ON db.news_articles AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('article_body')
        Accumulate('article_id', 'publish_date')
) AS t;
```

> **Parsing tip:** To expand `Key_Phrases` into individual rows for aggregation or frequency analysis, use `STRTOK_SPLIT_TO_TABLE` (row-per-token output). To split into separate named columns, use `Unpack` with `Delimiter(', ')` — see `data-cleaning` topic for `Unpack` syntax.

---

## AI_MaskPII

Detects and masks personally identifiable information (PII) in a text column. Returns both a structured entity list and a masked version of the original text.

```sql
SELECT * FROM TD_SYSFNLIB.AI_MaskPII(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `PII_Entities` | VARCHAR | Structured list of detected PII entities with type, value, position, and length |
| `Masked_Phrase` | VARCHAR | Original text with each PII value replaced by `*` characters of equal length |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`PII_Entities` format:**

Each detected entity is a tuple of the form `('type'='value', 'start_position'=N, 'length'=N)`, with multiple entities comma-separated:

```
('Name'='Parker Doe', 'start_position'=0, 'length'=10),
('address'='Brazil', 'start_position'=27, 'length'=6),
('date/time'='2020 04 25', 'start_position'=78, 'length'=10),
('contact numbers'='555 555 5555', 'start_position'=103, 'length'=12),
('serial numbers'='SSN'='859 98 0987', 'start_position'=-1, 'length'=17)
```

> `start_position=-1` indicates the position could not be determined (may occur for compound or multi-token entities). Entity types are provider-generated and may vary (e.g., `Name`, `address`, `date/time`, `contact numbers`, `serial numbers`, `CPF`).

**`Masked_Phrase` format:**

PII values are replaced in-place with `*` characters matching the original character length, preserving the structure of the surrounding text:

```
-- Original:
Parker Doe originally from Brazil has successfully cleared all their loans by 2020 04 25

-- Masked:
********** originally from ****** has successfully cleared all their loans by **********
```

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_MaskPII(
    ON db.customer_notes AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('note_text')
        Accumulate('note_id', 'created_date')
) AS t;
```

---

## AI_RecognizeEntities

Identifies named entities in text (people, places, dates, quantities, etc.) and returns them as labeled tuples. General-purpose NER — for PII-specific detection with masking, use `AI_MaskPII` or `AI_RecognizePIIEntities` instead.

```sql
SELECT * FROM TD_SYSFNLIB.AI_RecognizeEntities(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Labeled_Entities` | VARCHAR | Comma-separated list of `(value, type)` tuples |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`Labeled_Entities` format:**

Each entity is a `(value, type)` tuple, with multiple entities comma-separated:

```
(Parker Doe, people), (Brazil, places), (2020-04-25, date/time),
(555-555-5555, quantities), (859-98-0987, quantities), (99821486568, quantities)
```

> Entity type labels are provider-generated and may vary. Common types include `people`, `places`, `date/time`, `quantities`, `organizations`.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_RecognizeEntities(
    ON db.news_articles AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('article_text')
        Accumulate('article_id', 'publish_date')
) AS t;
```

---

## AI_RecognizePIIEntities

Detects personally identifiable information (PII) in text and returns structured entity metadata — type, value, position, and length. Unlike `AI_MaskPII`, this function identifies entities only; it does not produce a masked version of the text.

| Need | Function |
|------|----------|
| Detect PII + get masked text | `AI_MaskPII` |
| Detect PII + get structured metadata only | `AI_RecognizePIIEntities` |
| General named entity recognition (non-PII) | `AI_RecognizeEntities` |

```sql
SELECT * FROM TD_SYSFNLIB.AI_RecognizePIIEntities(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `PII_Entities` | VARCHAR | Structured list of detected PII entities with type, value, position, and length |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`PII_Entities` format:**

Each entity is a tuple of `('type'='value', 'start_position'=N, 'length'=N)`, comma-separated:

```
('Name'='Parker Doe', 'start_position'=0, 'length'=10),
('country'='Brazil', 'start_position'=27, 'length'=6),
('date/time'='2020 04 25', 'start_position'=78, 'length'=10),
('contact number'='555 555 5555', 'start_position'=103, 'length'=12),
('SSN'='859 98 0987', 'start_position'=129, 'length'=11),
('ID number'='998214865 68', 'start_position'=169, 'length'=12)
```

> Entity type labels are provider-generated and may vary slightly across models. `start_position` is zero-indexed character offset from the start of the input text.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_RecognizePIIEntities(
    ON db.customer_notes AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('note_text')
        Accumulate('note_id', 'created_date')
) AS t;
```

---

## AI_TextClassifier

Classifies text into user-defined categories. Supports both single-label (one best match) and multi-label (all matching categories) classification.

> **`Labels` name collision:** `Labels` is both a required USING argument (the category list) and the name of the output column (the assigned label(s)). They are distinct — the argument is the input list; the output column is the result.

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextClassifier(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        Labels('[Label1, Label2, Label3, ...]')         -- required; Python-style list as a string
        [ MultiLabel('false') ]                         -- default false; true = assign all matching labels
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Labels` | VARCHAR | Assigned label(s); single value when `MultiLabel('false')`, comma-separated when `MultiLabel('true')` |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`Labels` argument format:** A Python-style list passed as a string. Spaces after commas are allowed:

```sql
Labels('[news, sports, politics, entertainment]')
Labels('[Medical, hospital, healthcare, historical-news, Environment, technology, Games]')
```

**`MultiLabel` behavior:**
- `MultiLabel('false')` *(default)* — returns the single best-matching label
- `MultiLabel('true')` — returns all labels that apply, comma-separated (e.g., `'Medical, healthcare'`)

**Example — single-label:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextClassifier(
    ON db.support_tickets AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('ticket_text')
        Labels('[billing, technical, shipping, returns, account]')
        Accumulate('ticket_id', 'submitted_date')
) AS t;
```

**Example — multi-label:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextClassifier(
    ON db.research_abstracts AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('abstract_text')
        Labels('[climate, energy, policy, economics, technology, public-health]')
        MultiLabel('true')
        Accumulate('paper_id', 'journal')
) AS t;
```

---

## AI_TextSummarize

Generates a summary of text in a specified column. Supports multi-level summarization where each level runs the summarizer again on the previous output, producing progressively more compressed results.

> **`levels` is lowercase** — unlike most USING arguments which use mixed case, this argument is all lowercase.

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextSummarize(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ levels('1') ]                                 -- default '1'; range '1'-'5'; integer passed as string
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Summary` | VARCHAR | Summarized text |
| `Count` | INTEGER | Character count of the summary |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`levels` behavior:** Each level feeds the output of the previous summarization pass back in as input. Higher levels produce shorter, more compressed summaries:

| levels | Behavior |
|--------|----------|
| `'1'` | Single summarization pass (default) |
| `'2'` | Summarize → summarize the summary |
| `'3'`–`'5'` | Additional passes; each produces a progressively more compressed result |

> Use `Count` to verify output length and compare compression across levels without retrieving the full summary text.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextSummarize(
    ON db.research_papers AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('full_text')
        levels('2')
        Accumulate('paper_id', 'title')
) AS t;
```

---

## AI_TextTranslate

Translates text in a specified column to a target language. Defaults to English if no target language is specified.

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextTranslate(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        -- Provider config block (required — choose one)
        -- See llm-providers topic for full syntax per provider
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
        -- ... provider-specific args ...

        TextColumn('text_col')                          -- required; VARCHAR, CHAR, or CLOB
        [ TargetLang('english') ]                       -- default 'english'; specify target language by name
        [ isDebug('false') ]                            -- default false; enables error logging
        [ Accumulate({ 'col' | col_range }[,...]) ]     -- columns to copy to output
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `accumulate_col(s)` | same as input | Columns copied from InputTable |
| `Translation` | VARCHAR | Translated text in the target language |
| `Message` | VARCHAR | Error message from the LLM endpoint, if any |

**`TargetLang`:** Specify the target language by name (e.g., `'french'`, `'spanish'`, `'japanese'`). Language name casing is not sensitive. Defaults to `'english'` when omitted. Supported languages depend on the LLM provider and model.

**Example:**

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextTranslate(
    ON db.product_descriptions AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('gpt-4o')
        TextColumn('description_text')
        TargetLang('french')
        Accumulate('product_id', 'sku')
) AS t;
```
