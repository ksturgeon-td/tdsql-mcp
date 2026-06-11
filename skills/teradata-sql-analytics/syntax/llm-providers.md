# Teradata AI Functions — LLM Provider Configuration

This file documents the provider argument blocks used by Teradata AI functions (`AI_TextEmbeddings` and others). Each AI function accepts one provider block in its `USING` clause. Load this topic alongside the specific AI function topic for full syntax.

> **Credentials:** Always prefer an `AUTHORIZATION` object over inline credentials. See `authorization-objects` topic for creation syntax and the field mapping per provider.

---

## Provider Quick Reference

| Provider | ApiType | Unique required args | Unique optional args |
|----------|---------|----------------------|----------------------|
| Azure | `'azure'` | `DeploymentId`, `ApiBase`+`ApiKey`+`ApiVersion` (inline) | `ModelName`, `ModelArgs` |
| AWS Bedrock | `'aws'` | `Region`, `ModelName`, `AccessKey`+`SecretKey` (inline) | `SessionKey`, `ModelOperation`, `BedrockKey`, `ModelArgs` |
| Google Cloud | `'gcp'` | `ModelName`, `AccessToken`+`Region`+`Project` (inline) | `EnableSafety`, `ModelArgs` |
| NVIDIA NIM | `'nim'` | `ApiBase`+`ApiKey` (inline) | `ModelName`, `ModelArgs` |
| LiteLLM | `'litellm'` | `ApiBase`+`ApiKey` (inline) | `ModelName`, `ModelArgs` |

---

## Azure

```sql
-- Using AUTHORIZATION object (preferred)
ApiType('azure')
AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
DeploymentId('<azure_deployment_id>')
[ ModelName('<azure-model-name>') ]
[ ModelArgs('{"Top_P": "0.9", "Top_K": "50"}') ]

-- Using inline credentials
ApiType('azure')
ApiBase('<azure_base_url>')        -- endpoint URL, e.g. https://myinstance.openai.azure.com/
ApiKey('<api_key>')
ApiVersion('<api_version>')        -- e.g. '2024-02-15-preview'
DeploymentId('<azure_deployment_id>')
[ ModelName('<azure-model-name>') ]
[ ModelArgs('{"Top_P": "0.9", "Top_K": "50"}') ]
```

**Azure argument reference:**

| Argument | Required | Description |
|----------|----------|-------------|
| `ApiType('azure')` | Yes | Identifies the provider |
| `AUTHORIZATION(...)` | Yes (if not inline) | Mutually exclusive with `ApiBase`, `ApiKey`, `ApiVersion` |
| `ApiBase` | Yes (if not AUTHORIZATION) | Azure endpoint base URL |
| `ApiKey` | Yes (if not AUTHORIZATION) | Azure API key |
| `ApiVersion` | Yes (if not AUTHORIZATION) | API version string (e.g. `'2024-02-15-preview'`) |
| `DeploymentId` | Yes | Deployment/engine name — set when model was deployed; may differ from `ModelName` |
| `ModelName` | No | Azure model name — defaults to the deployment name if omitted |
| `ModelArgs` | No | JSON string of inference parameters |

---

## AWS Bedrock

```sql
-- Using AUTHORIZATION object (preferred)
ApiType('aws')
AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
Region('<aws-region>')              -- e.g. 'us-east-1'
ModelName('<bedrock-model-id>')     -- e.g. 'amazon.titan-embed-text-v1'
[ ModelOperation('invoke'|'converse') ]
[ BedrockKey('<bedrock_key>') ]
[ ModelArgs('{"Top_P": "0.9"}') ]

-- Using inline credentials
ApiType('aws')
AccessKey('<aws_access_key>')
SecretKey('<aws_secret_key>')
[ SessionKey('<aws_session_key>') ]  -- optional; for temporary credentials
Region('<aws-region>')
ModelName('<bedrock-model-id>')
[ ModelOperation('invoke'|'converse') ]
[ BedrockKey('<bedrock_key>') ]
[ ModelArgs('{"Top_P": "0.9"}') ]
```

**AWS argument reference:**

| Argument | Required | Description |
|----------|----------|-------------|
| `ApiType('aws')` | Yes | Identifies the provider |
| `AUTHORIZATION(...)` | Yes (if not inline) | Mutually exclusive with `AccessKey`, `SecretKey`, `SessionKey` |
| `AccessKey` | Yes (if not AUTHORIZATION) | AWS access key |
| `SecretKey` | Yes (if not AUTHORIZATION) | AWS secret key |
| `SessionKey` | No | Temporary session token; used with short-lived credentials |
| `Region` | Yes | AWS Bedrock service region |
| `ModelName` | Yes | Bedrock model ID (case-sensitive) |
| `ModelOperation` | No | API mode: `'invoke'` (default) or `'converse'`; Claude 3.7 models default to `'converse'` |
| `BedrockKey` | No | AWS Bedrock key |
| `ModelArgs` | No | JSON string of inference parameters |

---

## Google Cloud (Vertex AI / Gemini)

```sql
-- Using AUTHORIZATION object (preferred)
ApiType('gcp')
AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
ModelName('<gemini-model-name>')    -- e.g. 'textembedding-gecko@003'
[ EnableSafety('TRUE'|'FALSE') ]   -- default TRUE
[ ModelArgs('{"Temperature": "0.2", "top_p": "0.8"}') ]

-- Using inline credentials
ApiType('gcp')
AccessToken('<gcp_access_token>')
Region('<gcp_region>')              -- e.g. 'us-central1'
Project('<gcp_project_name>')
ModelName('<gemini-model-name>')
[ EnableSafety('TRUE'|'FALSE') ]
[ ModelArgs('{"Temperature": "0.2", "top_p": "0.8"}') ]
```

**GCP argument reference:**

| Argument | Required | Description |
|----------|----------|-------------|
| `ApiType('gcp')` | Yes | Identifies the provider |
| `AUTHORIZATION(...)` | Yes (if not inline) | Mutually exclusive with `AccessToken`, `Region`, `Project` |
| `AccessToken` | Yes (if not AUTHORIZATION) | GCP session/access token |
| `Region` | Yes (if not AUTHORIZATION) | GCP service region |
| `Project` | Yes (if not AUTHORIZATION) | GCP project name |
| `ModelName` | Yes | Gemini / Vertex AI model name (case-sensitive) |
| `EnableSafety` | No | Enable GCP safety filters; default `'TRUE'` |
| `ModelArgs` | No | JSON string of inference parameters |

---

## NVIDIA NIM

```sql
-- Using AUTHORIZATION object (preferred)
ApiType('nim')
AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
[ ModelName('<nim-model-name>') ]   -- e.g. 'nvidia/nv-embedqa-e5-v5'
[ ModelArgs('{}') ]

-- Using inline credentials
ApiType('nim')
ApiBase('<nim_base_url>')           -- full NIM service URL
ApiKey('<nim_api_key>')
[ ModelName('<nim-model-name>') ]
[ ModelArgs('{}') ]
```

**NIM argument reference:**

| Argument | Required | Description |
|----------|----------|-------------|
| `ApiType('nim')` | Yes | Identifies the provider |
| `AUTHORIZATION(...)` | Yes (if not inline) | Mutually exclusive with `ApiBase`, `ApiKey` |
| `ApiBase` | Yes (if not AUTHORIZATION) | Full NIM service endpoint URL |
| `ApiKey` | Yes (if not AUTHORIZATION) | NIM API key |
| `ModelName` | No | NIM model name (case-sensitive) |
| `ModelArgs` | No | JSON string of inference parameters |

---

## LiteLLM

LiteLLM is a proxy that provides a unified interface to many LLM providers. Configuration is identical in structure to NIM.

```sql
-- Using AUTHORIZATION object (preferred)
ApiType('litellm')
AUTHORIZATION([DatabaseName.]AuthorizationObjectName)
[ ModelName('<litellm-model-name>') ]
[ ModelArgs('{}') ]

-- Using inline credentials
ApiType('litellm')
ApiBase('<litellm_base_url>')       -- LiteLLM proxy URL
ApiKey('<litellm_api_key>')
[ ModelName('<litellm-model-name>') ]
[ ModelArgs('{}') ]
```

**LiteLLM argument reference:**

| Argument | Required | Description |
|----------|----------|-------------|
| `ApiType('litellm')` | Yes | Identifies the provider |
| `AUTHORIZATION(...)` | Yes (if not inline) | Mutually exclusive with `ApiBase`, `ApiKey` |
| `ApiBase` | Yes (if not AUTHORIZATION) | LiteLLM proxy endpoint URL |
| `ApiKey` | Yes (if not AUTHORIZATION) | LiteLLM API key |
| `ModelName` | No | Model name as configured in the LiteLLM proxy (case-sensitive) |
| `ModelArgs` | No | JSON string of inference parameters |

---

## ModelArgs — Common Inference Parameters

`ModelArgs` accepts a JSON string of model-specific inference parameters. Keys and valid values vary by model and provider. Common parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `Temperature` | Sampling temperature; higher = more random | `"Temperature": "0.7"` |
| `Top_P` | Nucleus sampling probability mass | `"Top_P": "0.9"` |
| `Top_K` | Top-K sampling cutoff | `"Top_K": "50"` |
| `MaxTokens` | Maximum output tokens | `"MaxTokens": "512"` |

```sql
-- Example with multiple parameters
ModelArgs('{"Temperature": "0.2", "Top_P": "0.9", "MaxTokens": "256"}')
```

> **Embedding models** typically ignore `Temperature`, `Top_P`, and `Top_K` — these parameters apply to generative/completion models. For embedding functions, `ModelArgs` is usually omitted or left as `'{}'`.

---

## Using This Reference

Each AI function topic (e.g. `embeddings`) shows the full function syntax with a placeholder for the provider block. Replace the placeholder with one of the blocks above. Example structure:

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextEmbeddings(
    ON db.documents AS InputTable
    USING
        -- paste one provider block here --
        ApiType('azure')
        AUTHORIZATION(db.td_gen_azure_auth)
        DeploymentId('text-embedding-ada-002')
        -- end provider block --
        TextColumn('doc_text')
        OutputFormat('VECTOR')
) AS t;
```
