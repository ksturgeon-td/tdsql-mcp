# Teradata Authorization Objects

Authorization objects store external service credentials securely inside Teradata, decoupling
secrets from SQL code. They are used by NOS table operators (`READ_NOS`, `WRITE_NOS`),
external object access via `CREATE FOREIGN TABLE` and `CREATE DATALAKE`, and AI inference
functions (`AI_TextEmbeddings` and others).

Rather than embedding credentials directly in SQL, you reference a named authorization object.
Credentials are stored once, managed centrally, and access is controlled via standard
Teradata permissions.

---

## CREATE / REPLACE AUTHORIZATION

```sql
{ CREATE | REPLACE } AUTHORIZATION [DatabaseName.]authorization_name
    [ AS { DEFINER | INVOKER } TRUSTED ]
    { user_password_auth | extended_auth }

-- Form 1: user_password_auth
USER     'user_value'
PASSWORD 'password_value'
[ SESSION_TOKEN 'session_token_value' ]

-- Form 2: extended_auth (AWS IAM role assumption only)
USING AUTHSERVICETYPE 'ASSUME_ROLE'
ROLENAME 'arn:aws:iam::account-id:role/role-name'
EXTERNALID 'external_id_value'
[ DURATION_SECONDS 'duration_in_seconds' ]
```

**`AS DEFINER` / `AS INVOKER` / `TRUSTED`:**

| Clause | Meaning |
|--------|---------|
| `AS DEFINER` | Shared access — usable by multiple users of the database. Can be created in any database. |
| `AS INVOKER` | **Default.** Exclusive access by the creating user. Must be created in the current user's own database. |
| `TRUSTED` | Required when the auth object is referenced in an `EXTERNAL SECURITY` clause (CREATE FOREIGN TABLE, CREATE FUNCTION MAPPING). |

**Form 2 — ASSUME_ROLE:**
- `AUTHSERVICETYPE` — only supported value is `'ASSUME_ROLE'`
- `ROLENAME` — ARN of the IAM role to assume
- `EXTERNALID` — external ID required by the IAM role trust policy
- `DURATION_SECONDS` — session duration 900–43200 seconds; default 3600; must not exceed the IAM role's max session duration

> **EXTERNAL SECURITY — the reference must match how the auth object was created:**
>
> | Auth created as | `EXTERNAL SECURITY` reference | Qualified `db.auth` allowed? |
> |---|---|---|
> | Plain (no `AS` clause) | `EXTERNAL SECURITY <db>.<auth>` (no keywords) | **Yes** — verified for DATALAKE and FOREIGN TABLE |
> | `AS DEFINER TRUSTED` | `EXTERNAL SECURITY DEFINER TRUSTED <auth>` | **No** — Error 3706; auth must be in the same DB as the object |
> | `AS INVOKER TRUSTED` | `EXTERNAL SECURITY INVOKER TRUSTED <auth>` | No |
>
> A mismatch raises Error 6953 (`authorization definition does not match`) or Error 3706.
>
> **Elastic Compute:** For DATALAKE objects, the auth object must be in a GLOBAL database
> so it replicates across all CE instances. For NOS foreign tables, place it in the same
> local or global database as the table.
>
> **GRANT EXECUTE:** After creating an auth object, grant `EXECUTE` so roles and databases
> can use it — see [Permissions](#permissions) below.

---

## NOS and OTF External Security Authorization

Used with `CREATE FOREIGN TABLE`, `CREATE DATALAKE`, `READ_NOS`, and `WRITE_NOS`.
The `USER` and `PASSWORD` fields map to object storage credentials, not API keys.

### Field Mapping — Object Storage Providers

| Storage system | USER | PASSWORD | SESSION_TOKEN |
|---|---|---|---|
| AWS (IAM user) | Access Key ID | Access Key Secret | Session Token *(optional — STS temporary creds only)* |
| Azure Shared Key | Storage Account Name | Storage Account Key | — |
| Azure SAS | Storage Account Name | Account SAS Token | — |
| GCS (S3 interop mode) | Access Key ID | Access Key Secret | — |
| GCS (native) | Client Email | Private Key | — |
| On-premises object store | Access Key ID | Access Key Secret | — |
| Public bucket | `''` (empty string) | `''` (empty string) | — |

### Examples

```sql
-- AWS: plain auth for OTF DATALAKE (no AS clause — plain auth + qualified ref is verified)
CREATE AUTHORIZATION global_db.aws_glue_auth
    USER     '<aws_access_key_id>'
    PASSWORD '<aws_access_key_secret>';

-- AWS: ASSUME_ROLE for OTF DATALAKE or NOS
CREATE AUTHORIZATION global_db.aws_role_auth
    USING AUTHSERVICETYPE 'ASSUME_ROLE'
    ROLENAME '<arn:aws:iam::account-id:role/role-name>'
    EXTERNALID '<external_id>'
    DURATION_SECONDS '3600';

-- Azure Shared Key (Storage Account Name + Storage Account Key)
CREATE AUTHORIZATION global_db.azure_auth
    USER     '<storage_account_name>'
    PASSWORD '<storage_account_key>';

-- Azure SAS (Storage Account Name + Account SAS Token)
CREATE AUTHORIZATION global_db.azure_sas_auth
    USER     '<storage_account_name>'
    PASSWORD '<account_sas_token>';

-- GCS (S3 interop mode — Access Key ID + Secret)
CREATE AUTHORIZATION global_db.gcs_interop_auth
    USER     '<gcs_access_key_id>'
    PASSWORD '<gcs_access_key_secret>';

-- GCS (native — Client Email + Private Key)
CREATE AUTHORIZATION global_db.gcs_native_auth
    USER     '<client_email>'
    PASSWORD '<private_key>';

-- Public bucket (empty credentials)
CREATE AUTHORIZATION global_db.public_auth
    USER     ''
    PASSWORD '';

-- NOS FOREIGN TABLE: AS DEFINER TRUSTED, auth in same DB as table, unqualified reference
CREATE AUTHORIZATION mydb.s3_ft_auth
    AS DEFINER TRUSTED
    USER     '<aws_access_key_id>'
    PASSWORD '<aws_access_key_secret>';

CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
    EXTERNAL SECURITY DEFINER TRUSTED s3_ft_auth   -- unqualified; qualified raises Error 3706
    USING ( LOCATION ('/S3/s3.amazonaws.com/<bucket>/<prefix>/') STOREDAS ('PARQUET') )
NO PRIMARY INDEX;

-- OTF DATALAKE: plain auth in GLOBAL database, qualified reference, no keywords
CREATE DATALAKE my_lake
    EXTERNAL SECURITY CATALOG global_db.aws_glue_auth,
    EXTERNAL SECURITY STORAGE global_db.aws_glue_auth
USING catalog_type ('glue') ... TABLE FORMAT iceberg;
```

---

## AI Function Authorization

Used with `AI_TextEmbeddings`, `AI_Generate`, and other AI inference functions. The `USER`,
`PASSWORD`, and `SESSION_TOKEN` fields map to AI provider API credentials — **different
semantics from object storage auth above.**

### Field Mapping — AI Inference Providers

| Provider | USER | PASSWORD | SESSION_TOKEN |
|----------|------|----------|---------------|
| **AWS Bedrock** | Access Key ID | Access Key Secret | Session Token *(optional — STS only)* |
| **Azure OpenAI** | API Base URL (endpoint) | API Key | API Version *(required)* |
| **Google Cloud (Vertex)** | Project | Region | Access Token *(required)* |
| **NVIDIA NIM** | API Base URL | API Key | *(not used)* |
| **LiteLLM** | API Base URL | API Key | *(not used)* |

### Examples

```sql
-- AWS Bedrock (long-term IAM user — omit SESSION_TOKEN)
CREATE AUTHORIZATION db.td_gen_aws_auth
    USER     '<aws_access_key_id>'
    PASSWORD '<aws_access_key_secret>';

-- AWS Bedrock (STS temporary credentials — include SESSION_TOKEN)
CREATE AUTHORIZATION db.td_gen_aws_auth
    USER     '<aws_access_key_id>'
    PASSWORD '<aws_access_key_secret>'
    SESSION_TOKEN '<aws_session_token>';

-- AWS Bedrock via IAM role assumption
CREATE AUTHORIZATION db.td_gen_aws_role_auth
    USING AUTHSERVICETYPE 'ASSUME_ROLE'
    ROLENAME 'arn:aws:iam::123456789012:role/teradata-bedrock-role'
    EXTERNALID '<external_id>'
    DURATION_SECONDS '3600';

-- Azure OpenAI (SESSION_TOKEN = API version string — required)
CREATE AUTHORIZATION db.td_gen_azure_auth
    USER     '<api_base_url>'
    PASSWORD '<api_key>'
    SESSION_TOKEN '2024-02-15-preview';

-- Google Cloud Vertex AI (SESSION_TOKEN = Access Token — required)
CREATE AUTHORIZATION db.td_gen_gcp_auth
    USER     '<gcp_project>'
    PASSWORD '<gcp_region>'
    SESSION_TOKEN '<gcp_access_token>';

-- NVIDIA NIM
CREATE AUTHORIZATION db.td_gen_nim_auth
    USER     '<nim_api_base_url>'
    PASSWORD '<nim_api_key>';

-- LiteLLM
CREATE AUTHORIZATION db.td_gen_litellm_auth
    USER     '<litellm_base_url>'
    PASSWORD '<litellm_api_key>';

-- Rotate credentials without dropping (use REPLACE)
REPLACE AUTHORIZATION db.td_gen_aws_auth
    USER     '<new_access_key>'
    PASSWORD '<new_secret_key>';
```

---

## Permissions

### EXECUTE — allow a role or database to use an auth object

```sql
-- Grant to a role (preferred — access follows role membership)
GRANT EXECUTE ON db.my_auth TO analyst_role;
GRANT EXECUTE ON db.my_auth TO analyst_role WITH GRANT OPTION;

-- Grant at database level (covers all auth objects in the DB)
GRANT EXECUTE ON db TO analyst_role;

-- Revoke
REVOKE EXECUTE ON db.my_auth FROM analyst_role;
```

### CREATE / DROP AUTHORIZATION

```sql
GRANT CREATE AUTHORIZATION ON db TO dba_user;
GRANT DROP AUTHORIZATION ON db TO dba_user;
REVOKE CREATE AUTHORIZATION ON db FROM dba_user;
```

### Permissions Inheritance — Critical for Operational Pipelines

If a **view or macro in database B** references an auth object in **database A**, then
**database B must have `EXECUTE`** — not just the user running the query.

```sql
-- Works in dev (user has EXECUTE) but the operational view will fail without this:
GRANT EXECUTE ON credentials_db.my_auth TO operational_db;
--                                         ^^^^^^^^^^^^^^
--                             Grant to the DATABASE, not just the user
```

**Rule of thumb:** store auth objects in a dedicated credentials database, grant `EXECUTE`
to every database that references them, and grant to roles rather than individual users.

---

## DROP AUTHORIZATION

```sql
DROP AUTHORIZATION [DatabaseName.]authorization_name;
```

> Dropping an auth object immediately breaks any query, view, or procedure that references it.
> Prefer `REPLACE AUTHORIZATION` for credential rotation.
