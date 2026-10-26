# Production GenAI Application Architecture

This document details the architectural blueprint of the enterprise RAG application, inspired by the ScriptForge AI production deployment topology and monitored via Splunk Observability Cloud standards.

---

## 1. End-to-End System Topology

```
+-------------------------------------------------------------------------------------------------+
|                                    SCRIPTFORGE AI DEPLOYMENT TOPOLOGY                           |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   [ Client Query ]                                                                              |
|          │                                                                                      |
|          ▼                                                                                      |
|   ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────────────────┐    |
|   │  AI Input    │────▶│ API Gateway  │────▶│ Application Load Balancer (ALB / App Gateway)│    |
|   └──────────────┘     └──────────────┘     └──────────────────────┬───────────────────────┘    |
|                                                                    │                            |
|                                                                    ▼                            |
|                                                     ┌──────────────────────────────┐            |
|                                                     │ Containerized Microservice   │            |
|                                                     │  (Azure Container Apps /     │            |
|                                                     │   Amazon ECS Fargate)        │            |
|                                                     └──────────────┬───────────────┘            |
|                                                                    │                            |
|          ┌─────────────────────────────────────────────────────────┴─────────────┐              |
|          ▼                                                                       ▼              |
|   ┌────────────────────────────────┐                             ┌───────────────────────────┐  |
|   │     Security & Guardrails      │                             │    RAG Retrieval System   │  |
|   │ 1. API Key / Bearer Auth       │                             │ 1. Document Loader (PDF)  │  |
|   │ 2. Sliding Window Rate Limiter │                             │ 2. Sliding Window Chunker │  |
|   │ 3. PII Redaction (SSN/Cards)   │                             │ 3. TF-IDF Dense Embedder  │  |
|   │ 4. Prompt Injection Defense    │                             │ 4. FAISS Inner Product DB │  |
|   └────────────────────────────────┘                             └───────────────┬───────────┘  |
|                                                                                  │              |
|                                                                                  ▼              |
|                                                                  ┌───────────────────────────┐  |
|                                                                  │   Grounded Synthesis Engine│ |
|                                                                  │ 1. Similarity Refusal Gate│  |
|                                                                  │ 2. Citation Formatter     │  |
|                                                                  │ 3. Token & Latency Meter  │  |
|                                                                  └───────────────┬───────────┘  |
|                                                                                  │              |
|          ┌───────────────────────────────────────────────────────────────────────┴──────────┐   |
|          ▼                                                                                  ▼   |
|   ┌────────────────────────────────┐                                        ┌────────────────┐  |
|   │ Observability & Telemetry      │                                        │   AI Output    │  |
|   │ 1. Splunk Cloud Metrics (/api) │                                        │ (JSON Response │  |
|   │ 2. Prometheus Scraper (/metrics│                                        │  with Sources) │  |
|   │ 3. JSON Logs with Request ID   │                                        └────────────────┘  |
|   │ 4. SQLite Audit & Feedback     │                                                            |
|   └────────────────────────────────┘                                                            |
|                                                                                                 |
|   ┌─────────────────────────────────────────────────────────────────────────────────────────┐   |
|   │                               DevOps & CI/CD Pipeline (GitHub Actions)                  │   |
|   │      Linting ──▶ Pytest Suite ──▶ RAG Eval Gate ──▶ Docker Build ──▶ Cloud Deploy       │   |
|   └─────────────────────────────────────────────────────────────────────────────────────────┘   |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Core Architectural Components

### 2.1 API Gateway & Network Ingress
- **Routing & Termination**: External HTTPS traffic is terminated at the cloud ingress point (Application Load Balancer on AWS or Azure Container Apps Environment Ingress).
- **Transport Security**: TLS 1.3 encryption is enforced.
- **Port Isolation**: Container runs on internal port `8000`, isolated from direct external access without traversing the security middleware.

### 2.2 Security Middleware & Defense-in-Depth
- **Authentication**: Validates incoming API keys via `X-API-Key` or `Authorization: Bearer <token>` headers.
- **DDoS Mitigation**: In-memory token bucket rate limiter restricts request frequency per client IP (default: 60 req/min).
- **PII Scrubbing**: Regular expression sanitizers redact sensitive PII (SSNs, credit cards, telephone numbers) before queries touch embeddings or vector memory.
- **Prompt Injection Defense**: Regex pattern matcher checks for override vectors, developer mode exploits, or jailbreak keywords.

### 2.3 RAG Retrieval System
- **Document Loading**: Supports text and PDF extraction using `pypdf`, preserving document name and page number metadata.
- **Semantic Chunking**: Splits text into 500-character windows with 50-character sliding overlaps, respecting natural word boundaries.
- **Vector Embedding**: Dense 384-dimensional normalized vector space with TF-IDF and English stop-word filtering.
- **FAISS Vector Store**: Uses `faiss.IndexFlatIP` (Exact Inner Product Search) corresponding to Cosine Similarity on normalized vectors.

### 2.4 Grounded LLM Synthesis & Refusal Guardrails
- **Refusal Guardrail**: Queries with top similarity scores below `0.15` automatically trigger safe refusals rather than generating hallucinations.
- **Provenance Attribution**: Valid answers include page-level citations (e.g. `[HR_Policy_Handbook.pdf (Page 2)]`).

### 2.5 Observability & Telemetry
- **Splunk Observability Cloud Formatting**: Provides metrics formatted for Splunk dashboards, including P50, P90, P99 latencies, error rates, token counts, and cache utilization.
- **Prometheus Exporter**: Exposes standard OpenMetrics gauges and counters at `/metrics`.
- **Structured JSON Logging**: All application events format as single-line JSON with distributed `X-Request-ID` correlation.
- **Persistence**: SQLite database tracks query audit history, evaluation benchmark runs, and human feedback.
