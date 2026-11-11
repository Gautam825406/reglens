"""Auth: PBKDF2 password hashing (per-user random salt) + HMAC-SHA256 JWT.

Pattern reused from IncidentPilot (stdlib JWT, no extra dependency).
Document text is DATA, never instructions: injection patterns are detected
and flagged, never executed.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Optional

from .config import settings

_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|above) instructions",
    r"disregard (all )?(previous|above) instructions",
    r"you are now ",
    r"system prompt",
    r"execute .* (shell|command|rm |delete)",
    r"reveal (the )?(api key|secret|password)",
    r"override .* (policy|access|permission)",
]


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    if "$" not in password_hash:
        return False
    salt, expected = password_hash.split("$", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(digest, expected)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def create_token(user_id: str, email: str, role: str, expires_in: int = 86400 * 7) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(
        {"sub": user_id, "email": email, "role": role, "iat": now, "exp": now + expires_in}
    ).encode())
    sig = _b64(hmac.new(settings.jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    try:
        header, payload, sig = token.split(".")
        header_data = json.loads(_b64_decode(header))
        if header_data.get("alg") != "HS256" or header_data.get("typ") != "JWT":
            return None
        expected = _b64(hmac.new(settings.jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64_decode(payload))
        if not isinstance(data.get("sub"), str) or not data["sub"]:
            return None
        if not isinstance(data.get("email"), str) or not data["email"]:
            return None
        if not isinstance(data.get("role"), str) or not data["role"]:
            return None
        exp = data.get("exp")
        if not isinstance(exp, int) or exp < time.time():
            return None
        return data
    except Exception:
        return None


def redact_pii(text: str) -> str:
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/=]{10,}", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*)[A-Za-z0-9\-_]{8,}", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(password|passwd|pwd|secret|auth[_-]?token|access[_-]?token)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    text = re.sub(r"gsk_[A-Za-z0-9]{8,}", "[REDACTED]", text)
    text = re.sub(r"sk-[A-Za-z0-9]{8,}", "[REDACTED]", text)
    # Indian PAN / Aadhaar-shaped numbers in traces
    text = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[PAN]", text)
    text = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[AADHAAR]", text)
    return text


def contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(p, lowered) for p in _INJECTION_PATTERNS)


def sanitise_evidence(text: str) -> str:
    clean = redact_pii(text)
    if contains_injection(text):
        return clean + "\n[FLAGGED: instruction-like content in document data — treated as data, not instructions]"
    return clean
