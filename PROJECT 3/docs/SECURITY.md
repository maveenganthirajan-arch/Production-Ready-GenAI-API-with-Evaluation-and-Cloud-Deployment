# Enterprise Security & Least-Privilege Architecture

This document details the security model, secret management, threat mitigations, and compliance controls implemented in the Production GenAI RAG Application.

---

## 1. Threat Mitigation Matrix

| Threat Vector | Severity | Mitigation Strategy | Implemented Component |
| :--- | :--- | :--- | :--- |
| **Prompt Injection / Jailbreak** | High | Zero-trust regex filter intercepting override instructions | `app/security.py:detect_prompt_injection` |
| **Data Leakage (PII)** | Critical | Automated scrubbing of SSN, Credit Cards, and Phone numbers | `app/security.py:mask_pii` |
| **Unauthorized Access** | High | API Key & Bearer Token authentication | `app/security.py:verify_api_key` |
| **Denial of Service (DoS)** | High | Sliding-window token bucket rate limiter (60 rpm) | `app/security.py:InMemoryRateLimiter` |
| **Hallucination / Fabrication**| High | Cosine similarity threshold refusal (< 0.15 score) | `app/services/llm_service.py:generate_answer` |
| **Credential Exfiltration** | Critical | Secrets stored in Azure Key Vault / AWS Secrets Manager | `infra/azure/main.bicep`, `infra/aws/ecs-fargate.yml` |
| **Container Compromise** | Medium | Non-root execution (`appuser`, UID 10001) in Docker | `Dockerfile` |

---

## 2. Least-Privilege IAM Controls

### 2.1 Azure Managed Identity
- The application container does **not** store hardcoded Azure credentials.
- A **User-Assigned Managed Identity** is granted strictly:
  - `AcrPull` on the Azure Container Registry.
  - Secret `Get` and `List` permissions strictly on the `API-KEY` secret in Azure Key Vault.
- Container Apps fetches secrets natively at runtime without exposing them to host file systems.

### 2.2 AWS ECS Execution Role
- Amazon ECS tasks assume an IAM role granting only:
  - `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`
  - `secretsmanager:GetSecretValue` on the single secret ARN containing `API_KEY`
  - `logs:CreateLogStream`, `logs:PutLogEvents` in CloudWatch

---

## 3. PII Redaction Rules

Before queries are processed by the embedding service or vector store, all inputs pass through `mask_pii()`:
- **Social Security Numbers**: `\b\d{3}-\d{2}-\d{4}\b` replaced with `[REDACTED_SSN]`
- **Credit Cards**: `\b(?:\d{4}[ -]?){3}\d{4}\b` replaced with `[REDACTED_CARD]`
- **Phone Numbers**: E.164 and North American numbering formats replaced with `[REDACTED_PHONE]`

---

## 4. Audit Logging & Non-Repudiation

Every request processed by the API logs:
1. `request_id` (Correlation ID)
2. Client IP address
3. Masked input query
4. Retrieved chunk count and confidence score
5. Guardrail refusal decisions and prompt injection flags
6. End-to-end latency and token usage metrics
7. Persisted into SQLite table `query_audit_logs`.
