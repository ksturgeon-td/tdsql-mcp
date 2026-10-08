# Teradata Authorization Objects

Authorization objects store external service credentials securely inside Teradata, decoupling secrets from SQL code. They are used by AI functions (`AI_TextEmbeddings` and others), external stored procedures, and any feature that connects to an outside service.

Rather than embedding API keys or access tokens directly in a function call, you reference a named authorization object. Credentials are stored once, managed centrally, and access is controlled via standard Teradata permissions.

---

## CREATE / REPLACE AUTHORIZATION

Three forms are supported: standard user/password credentials, credentials with a DEFINER or INVOKER execution context, and IAM role assumption (AWS only).

```sql
{ CREATE | REPLACE } AUTHORIZATION [DatabaseName.]authorization_name
    [ AS { DEFINER | INVOKER } TRUSTED ]
    { user_password_auth | extended_auth }

-- Form 1: user_password_auth (all providers)
USER     'user_value'
PASSWORD 'password_value'
[ SESSION_TOKEN 'session_token_value' ]

-- Form 2: extended_auth (AWS IAM role assumption only)
USING AUTHSERVICETYPE 'ASSUME_ROLE'
ROLENAME 'arn:aws:iam::account-id:role/role-name'
EXTERNALID 'external_id_value'
[ DURATION_SECONDS 'duration_in_seconds' ]
```

**`AS DEFINER` vs `AS INVOKER` vs `TRUSTED`:**

| Clause | Meaning |
|--------|---------|
| `AS DEFINER` | Shared access — the authorization object can be used by multiple users of the database in which it resides. Can be created in any database. |
| `AS INVOKER` | Exclusive access by the creating user. Typically must be created in the current user's own database; exact privilege requirements may vary. |
| `TRUSTED` | Required when the authorization object is referenced in an `EXTERNAL SECURITY` clause (CREATE FOREIGN TABLE, CREATE FUNCTION MAPPING). |

> **EXTERNAL SECURITY clause — qualified vs unqualified name:**
> - **FOREIGN TABLE:** `EXTERNAL SECURITY DEFINER TRUSTED <auth_name>` — **unqualified name only.**
>   Using a qualified `db.auth_name` raises Error 3706. The auth object must be in the **same
>   database as the foreign table**.
> - **DATALAKE:** `EXTERNAL SECURITY DEFINER TRUSTED CATALOG <db>.<auth_name>` — qualified
>   name is correct and expected.
>
> **Elastic Compute:** For DATALAKE objects, the auth object must be in a **GLOBAL database**
> so it replicates across all CE instances alongside the datalake. See `ec-setup-skill` for
> the full replication model. For NOS foreign tables, the auth object stays in the same
> local or global database as the table.
>
> **GRANT EXECUTE:** After creating an auth object, grant `EXECUTE` so roles and databases
> can use it. See the [Permissions](#permissions) section below.

**Form 1 — user_password_auth:**
- **`CREATE`** — creates a new authorization object; fails if it already exists
- **`REPLACE`** — creates or replaces; use this to rotate credentials without dropping first
- **`SESSION_TOKEN`** — required for Azure (ApiVersion) and GCP (AccessToken); optional for AWS (SessionKey); not used for NIM or LiteLLM

**Form 2 — extended_auth (ASSUME_ROLE):**
- **`AUTHSERVICETYPE`** — only supported value is `'ASSUME_ROLE'`
- **`ROLENAME`** — ARN of the AWS IAM role to assume
- **`EXTERNALID`** — external ID value required by the IAM role trust policy (prevents confused deputy attacks in cross-account setups)
- **`DURATION_SECONDS`** — session duration in seconds; range 900–43200; default 3600; must not exceed the maximum session duration configured on the IAM role itself

---

## Field Mapping by Provider

### Form 1 — user_password_auth

The three fields (`USER`, `PASSWORD`, `SESSION_TOKEN`) map to different provider-specific credentials:

| Provider | USER | PASSWORD | SESSION_TOKEN |
|----------|------|----------|---------------|
| **AWS Bedrock / S3** | AccessKey | SecretKey | SessionToken *(optional — for STS temporary credentials only)* |
| **Azure** | ApiBase (endpoint URL) | ApiKey | ApiVersion *(required)* |
| **Google Cloud (GCP)** | Project | Region | AccessToken *(required)* |
| **NVIDIA NIM** | ApiBase (endpoint URL) | ApiKey | *(not used)* |
| **LiteLLM** | ApiBase (endpoint URL) | ApiKey | *(not used)* |

### Form 2 — extended_auth (AWS ASSUME_ROLE only)

| Field | Description |
|-------|-------------|
| `ROLENAME` | Full ARN of the IAM role to assume (`arn:aws:iam::account-id:role/role-name`) |
| `EXTERNALID` | External ID value defined in the IAM role's trust policy |
| `DURATION_SECONDS` | Session duration 900–43200 seconds; default 3600; must not exceed the IAM role's max session duration |

---

## Examples

```sql
-- NOS / OTF: DEFINER TRUSTED (shared service account — all users get same access)
CREATE AUTHORIZATION mydb.s3_definer_auth
    AS DEFINER TRUSTED
    USER     '{AWS_ACCESS_KEY}'
    PASSWORD '{AWS_SECRET_KEY}';
-- Optional: add SESSION_TOKEN for temporary AWS credentials (STS-issued)
--   SESSION_TOKEN '{AWS_SESSION_TOKEN}'

-- NOS / OTF: INVOKER TRUSTED (per-invoker runtime check)
CREATE AUTHORIZATION mydb.s3_invoker_auth
    AS INVOKER TRUSTED
    USER     '{AWS_ACCESS_KEY}'
    PASSWORD '{AWS_SECRET_KEY}';

-- How they appear in EXTERNAL SECURITY clauses:
-- (NOS foreign table — auth must be in the SAME database as the table;
--  reference by UNQUALIFIED name only — qualified db.auth raises Error 3706)
CREATE AUTHORIZATION mydb.s3_definer_auth        -- same db as the table
    AS DEFINER TRUSTED
    USER '{AWS_ACCESS_KEY}' PASSWORD '{AWS_SECRET_KEY}';

CREATE MULTISET FOREIGN TABLE mydb.orders_ft,
    EXTERNAL SECURITY DEFINER TRUSTED s3_definer_auth   -- unqualified name
    USING ( LOCATION ('/S3/s3.amazonaws.com/my-bucket/') STOREDAS ('PARQUET') )
NO PRIMARY INDEX;

-- (OTF DATALAKE — auth in a GLOBAL database; qualified name is correct here)
CREATE DATALAKE my_lake
    EXTERNAL SECURITY DEFINER TRUSTED CATALOG global_db.s3_auth,
    EXTERNAL SECURITY DEFINER TRUSTED STORAGE global_db.s3_auth
USING catalog_type ('glue') ... TABLE FORMAT iceberg;
```

### AI Function Authorization (no AS DEFINER/INVOKER)

```sql
-- AWS Bedrock (SESSION_TOKEN optional — include only for STS-issued temporary credentials)
CREATE AUTHORIZATION db.td_gen_aws_auth
    USER     '{AWS_ACCESS_KEY}'
    PASSWORD '{AWS_SECRET_KEY}'
    SESSION_TOKEN '{AWS_SESSION_TOKEN}'; -- omit for long-term IAM user credentials

-- Azure (SESSION_TOKEN = ApiVersion — required)
CREATE AUTHORIZATION db.td_gen_azure_auth
    USER     '{API_BASE_URL}'
    PASSWORD '{API_KEY}'
    SESSION_TOKEN '2024-02-15-preview';

-- Google Cloud (SESSION_TOKEN = AccessToken — required)
CREATE AUTHORIZATION db.td_gen_gcp_auth
    USER     '{GCP_PROJECT}'
    PASSWORD '{GCP_REGION}'
    SESSION_TOKEN '{GCP_ACCESS_TOKEN}';

-- NVIDIA NIM (no SESSION_TOKEN)
CREATE AUTHORIZATION db.td_gen_nim_auth
    USER     '{NIM_API_BASE_URL}'
    PASSWORD '{NIM_API_KEY}';

-- LiteLLM (no SESSION_TOKEN)
CREATE AUTHORIZATION db.td_gen_litellm_auth
    USER     '{LITELLM_BASE_URL}'
    PASSWORD '{LITELLM_API_KEY}';

-- Replace existing object to rotate credentials
REPLACE AUTHORIZATION db.td_gen_aws_auth
    USER     '{NEW_ACCESS_KEY}'
    PASSWORD '{NEW_SECRET_KEY}';

-- AWS Bedrock — IAM role assumption (ASSUME_ROLE)
-- Use when Teradata nodes run with an instance profile that has STS AssumeRole permission
CREATE AUTHORIZATION db.td_gen_aws_role_auth
    USING AUTHSERVICETYPE 'ASSUME_ROLE'
    ROLENAME 'arn:aws:iam::123456789012:role/teradata-bedrock-role'
    EXTERNALID '{EXTERNAL_ID}'
    DURATION_SECONDS '3600';
```

---

## Permissions

### EXECUTE — allow a user or role to use an authorization object

```sql
-- Grant
GRANT EXECUTE ON db.td_gen_aws_auth TO analyst_role;
GRANT EXECUTE ON db.td_gen_aws_auth TO analyst_role WITH GRANT OPTION;

-- Revoke
REVOKE EXECUTE ON db.td_gen_aws_auth FROM analyst_role;
```

### CREATE AUTHORIZATION — allow a user to create objects in a database

```sql
GRANT CREATE AUTHORIZATION ON db TO dba_user;
GRANT CREATE AUTHORIZATION ON db TO dba_user WITH GRANT OPTION;

REVOKE CREATE AUTHORIZATION ON db FROM dba_user;
```

### DROP AUTHORIZATION — allow a user to drop objects in a database

```sql
GRANT DROP AUTHORIZATION ON db TO dba_user;
REVOKE DROP AUTHORIZATION ON db FROM dba_user;
```

---

## Permissions Inheritance — Critical for Operational Pipelines

Teradata permissions follow standard inheritance rules. If a **view or macro in database B** references an authorization object in **database A**, then **database B must have `EXECUTE` on the authorization object** — not just the user running the query.

This is the most common production failure pattern: a scoring view is created in an operational database that references an auth object in a shared credentials database, and the view silently fails because only the developer's user account has `EXECUTE`, not the database itself.

```sql
-- Developer's account has EXECUTE — works in dev session
GRANT EXECUTE ON credentials_db.td_gen_aws_auth TO developer_user;

-- Operational view in a different database will fail without this:
GRANT EXECUTE ON credentials_db.td_gen_aws_auth TO operational_db;
--                                                  ^^^^^^^^^^^^^^
--                                    Grant to the DATABASE, not just the user
```

**Rule of thumb for operational pipelines:**
1. Store authorization objects in a dedicated credentials database (e.g., `ai_credentials`)
2. Grant `EXECUTE` to every database that hosts views, macros, or procedures that reference them
3. Grant `EXECUTE` to application roles, not individual users, so access follows role membership

---

## DROP AUTHORIZATION

```sql
DROP AUTHORIZATION [DatabaseName.]auth_object_name;
```

> Dropping an authorization object immediately breaks any function call, view, or procedure that references it. Prefer `REPLACE AUTHORIZATION` for credential rotation.
