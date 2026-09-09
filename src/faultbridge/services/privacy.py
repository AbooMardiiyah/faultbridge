import hashlib
import hmac
import re
from dataclasses import dataclass

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?234|0)[\s-]?[789]\d(?:[\s-]?\d){8}(?!\w)")
_ACCOUNT = re.compile(
    r"\b(?:account|acct|subscriber|customer)\s*(?:number|no|id)?\s*[:#-]?\s*[A-Z0-9-]{6,}\b",
    re.IGNORECASE,
)
_CARD_OR_GOVERNMENT_ID = re.compile(r"(?<!\w)(?:\d[\s-]?){10,16}(?!\w)", re.IGNORECASE)

_PII_PATTERNS = (
    ("email", _EMAIL, "[EMAIL_REDACTED]"),
    ("phone", _PHONE, "[PHONE_REDACTED]"),
    ("account", _ACCOUNT, "[ACCOUNT_REDACTED]"),
    ("numeric_identifier", _CARD_OR_GOVERNMENT_ID, "[NUMERIC_IDENTIFIER_REDACTED]"),
)


@dataclass(frozen=True, slots=True)
class PIIMatch:
    pii_type: str
    start: int
    end: int
    replacement: str


def find_pii(text: str) -> tuple[PIIMatch, ...]:
    """Return deterministic, non-overlapping PII spans in priority order."""
    selected: list[PIIMatch] = []
    for pii_type, pattern, replacement in _PII_PATTERNS:
        for match in pattern.finditer(text):
            if any(
                match.start() < item.end and match.end() > item.start
                for item in selected
            ):
                continue
            selected.append(PIIMatch(pii_type, match.start(), match.end(), replacement))
    return tuple(sorted(selected, key=lambda item: item.start))


def redact_text(text: str) -> str:
    """Remove common contact and subscriber identifiers before persistence."""
    redacted = text
    for match in reversed(find_pii(text)):
        redacted = redacted[: match.start] + match.replacement + redacted[match.end :]
    return redacted


def pseudonymize_caller(caller_id: str, secret: str) -> str:
    """Create a stable, non-reversible caller reference for clustering."""
    if len(secret) < 16:
        raise ValueError("pseudonym secret must be at least 16 characters")
    digest = hmac.new(secret.encode(), caller_id.encode(), hashlib.sha256).hexdigest()
    return f"caller_{digest[:16]}"
