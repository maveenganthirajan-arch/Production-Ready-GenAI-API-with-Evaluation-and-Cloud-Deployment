"""
Enterprise Security, Authentication, Rate Limiting, and Guardrails.
Implements:
1. API Key & Bearer Token Authentication (Least-Privilege)
2. Token Bucket Rate Limiter (DDoS Mitigation)
3. Prompt Injection Defense (Zero-Trust Input Sanitization)
4. PII Data Masking (Privacy Compliance)
"""

import re
import time
from typing import Optional, Dict
from fastapi import Header, HTTPException, Security, Request, status
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# -------------------------------------------------------------
# 1. Authentication & Least-Privilege Verification
# -------------------------------------------------------------

def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Validates API key from either X-API-Key header or Authorization: Bearer <token>.
    Raises HTTP 401 Unauthorized if invalid.
    """
    token = x_api_key if isinstance(x_api_key, str) else None
    if not token and isinstance(authorization, str):
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # In development/test mode without API_KEY set, bypass
    if not settings.API_KEY:
        return "authorized_dev"

    if not token or token != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide valid 'X-API-Key' or 'Authorization: Bearer <token>' header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return "authorized_client"


# -------------------------------------------------------------
# 2. Token Bucket Rate Limiter
# -------------------------------------------------------------

class InMemoryRateLimiter:
    """Sliding-window token bucket rate limiter per client IP."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests: Dict[str, list] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - 60.0

        if client_ip not in self.requests:
            self.requests[client_ip] = [now]
            return True

        # Purge timestamps outside sliding window
        valid_timestamps = [t for t in self.requests[client_ip] if t > window_start]
        self.requests[client_ip] = valid_timestamps

        if len(valid_timestamps) >= self.rpm:
            return False

        self.requests[client_ip].append(now)
        return True


rate_limiter = InMemoryRateLimiter(requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


def check_rate_limit(request: Request):
    """FastAPI dependency to enforce client rate limits."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({settings.RATE_LIMIT_PER_MINUTE} requests/minute). Please slow down."
        )


# -------------------------------------------------------------
# 3. Prompt Injection Defense
# -------------------------------------------------------------

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+(override|prompt|bypass)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?guardrails", re.IGNORECASE),
    re.compile(r"output\s+your\s+(secret|api\s*key|password|system\s*prompt)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE)
]


def detect_prompt_injection(text: str) -> bool:
    """Checks whether text contains adversarial prompt injection patterns."""
    if not settings.ENABLE_PROMPT_INJECTION_DEFENSE or not text:
        return False
    return any(p.search(text) for p in PROMPT_INJECTION_PATTERNS)


# -------------------------------------------------------------
# 4. PII Data Masker
# -------------------------------------------------------------

SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

def mask_pii(text: str) -> str:
    """Redacts sensitive PII before vector search or LLM processing."""
    if not settings.MASK_PII_DATA or not text:
        return text
    masked = SSN_PATTERN.sub("[REDACTED_SSN]", text)
    masked = CARD_PATTERN.sub("[REDACTED_CARD]", masked)
    masked = PHONE_PATTERN.sub("[REDACTED_PHONE]", masked)
    return masked
