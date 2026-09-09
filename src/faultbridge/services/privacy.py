import hashlib
import hmac
import re

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?234|0)[\s-]?[789]\d(?:[\s-]?\d){8}(?!\w)")
_ACCOUNT = re.compile(
    r"\b(?:account|acct|subscriber|customer)\s*(?:number|no|id)?\s*[:#-]?\s*[A-Z0-9-]{6,}\b",
    re.IGNORECASE,
)


def redact_text(text: str) -> str:
    """Remove common contact and subscriber identifiers before persistence."""
    redacted = _EMAIL.sub("[EMAIL_REDACTED]", text)
    redacted = _PHONE.sub("[PHONE_REDACTED]", redacted)
    return _ACCOUNT.sub("[ACCOUNT_REDACTED]", redacted)


def pseudonymize_caller(caller_id: str, secret: str) -> str:
    """Create a stable, non-reversible caller reference for clustering."""
    if len(secret) < 16:
        raise ValueError("pseudonym secret must be at least 16 characters")
    digest = hmac.new(secret.encode(), caller_id.encode(), hashlib.sha256).hexdigest()
    return f"caller_{digest[:16]}"
