# Teradata Authorization Objects

Authorization objects store external service credentials securely inside Teradata, decoupling secrets from SQL code. They are used by AI functions (`AI_TextEmbeddings` and others), external stored procedures, and any feature that connects to an outside service.

Rather than embedding API keys or access tokens directly in a function call, you reference a named authorization object. Credentials are stored once, managed centrally, and access is controlled via standard Teradata permissions.

---

## CREATE / REPLACE AUTHORIZATION

```sql
{ CREATE | REPLACE } AUTHORIZATION [DatabaseName.]auth_object_name
    USER     'user_value'
    PASSWORD 'password_value'
    [ SESSION_TOKEN 'session_token_value' ];
```

- **`CREATE`** — creates a new authorization object; fails if it already exists
- **`REPLACE`** — creates or replaces; use this to rotate credentials without dropping first
- **`SESSION_TOKEN`** — required for Azure (ApiVersion) and GCP (AccessToken); optional for AWS; not used for NIM or LiteLLM

---

## Field Mapping by Provider

The three fields (`USER`, `PASSWORD`, `SESSION_TOKEN`) map to different provider-specific credentials:

| Provider | USER | PASSWORD | SESSION_TOKEN |
|----------|------|----------|---------------|
| **AWS Bedrock** | AccessKey | SecretKey | SessionKey *(optional)* |
| **Azure** | ApiBase (endpoint URL) | ApiKey | ApiVersion *(required)* |
| **Google Cloud (GCP)** | Project | Region | AccessToken *(required)* |
| **NVIDIA NIM** | ApiBase (endpoint URL) | ApiKey | *(not used)* |
| **LiteLLM** | ApiBase (endpoint URL) | ApiKey | *(not used)* |

---

## Examples

```sql
-- AWS Bedrock (SessionKey optional — omit for long-term credentials)
CREATE AUTHORIZATION db.td_gen_aws_auth
    USER     '{AWS_ACCESS_KEY}'
    PASSWORD '{AWS_SECRET_KEY}'
    SESSION_TOKEN '{AWS_SESSION_TOKEN}';

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
