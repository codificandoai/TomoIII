"""Privacy, redaction, pseudonymization and safety limits for UC-309 events."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Secret/credential/credential-like redaction patterns (case-insensitive)
SENSITIVE_KEY_PATTERNS = (
    r"(?i)(secret|token|api[_-]?key|password|credential|auth|private[_-]?key|"
    r"passwd|apikey|access[_-]?token|bearer|api_secret|client_secret|secret_key|"
    r"session|cookie|password_hash|otp|pin|cvv|cert|key_material)"
)
SENSITIVE_VALUE_PATTERNS = (
    r"(?i)(sk-[a-zA-Z0-9]{20,}|\b[A-Za-z0-9_\-]{30,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b|"
    r"\b(?:[A-Fa-f0-9]{32,64})\b)"
)

# PII detection patterns (light, deterministic only)
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+"),
    "phone": re.compile(r"\b\+?\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}\b"),
    "ssn_like": re.compile(r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b"),
}

# Strict allowlist for event top-level fields
ALLOWED_TOP_FIELDS: Set[str] = {
    "trace_id", "span_id", "parent_span_id", "execution_id", "session_id",
    "agent_id", "agent_version", "step", "event_type", "timestamp_ns",
    "model_request_meta", "model_completion_meta", "structured_reasoning_summary",
    "action_proposed", "action_proposed_hash", "uc300", "uc290", "uc324",
    "tool_name", "tool_call_id", "tool_result_status", "observation_summary",
    "observed_action_hash", "error", "final_outcome", "evidence_refs",
    "dossier_refs", "latency_ms", "input_tokens", "output_tokens",
    "estimated_cost_usd", "retries", "loop_count", "labels",
    "redaction_findings", "pii_pseudonyms", "allowlist_violations",
    "previous_event_hash", "event_hash",
}

# Allowed label keys to enforce controlled cardinality
ALLOWED_LABEL_KEYS: Set[str] = {
    "tool_name", "agent_id", "agent_version", "event_type", "status",
    "model_provider", "outcome", "uc300_verdict", "uc290_escalation",
}

DEFAULT_PII_KEY = os.environ.get("UC309_PII_KEY", "").encode() or b"uc309-change-me-in-production"


def _derive_key(salt: bytes = b"uc309", key: bytes = DEFAULT_PII_KEY) -> bytes:
    return hmac.new(key, salt, hashlib.sha256).digest()


def pseudonymize(value: str, key: bytes = DEFAULT_PII_KEY) -> str:
    """Stable HMAC-based pseudonym for a PII value."""
    digest = hmac.new(_derive_key(key=key), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"pii_{digest[:16]}"


# Telemetry/known safe keys that contain sensitive-looking substrings but are not secrets
NON_SECRET_KEYS: Set[str] = {"input_tokens", "output_tokens", "max_tokens", "estimated_cost_usd"}


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    if key in NON_SECRET_KEYS:
        return False
    return bool(re.search(SENSITIVE_KEY_PATTERNS, key))


def _looks_like_secret_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.search(SENSITIVE_VALUE_PATTERNS, value))


def redact(
    value: Any,
    path: str = "",
    findings: Optional[List[str]] = None,
    pii: Optional[Dict[str, str]] = None,
    pii_key: bytes = DEFAULT_PII_KEY,
) -> Any:
    """Recursively redact secrets and pseudonymize PII."""
    if findings is None:
        findings = []
    if pii is None:
        pii = {}

    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            child = f"{path}.{k}" if path else k
            if _is_secret_key(k):
                if not _already_redacted(v):
                    findings.append(f"redacted_secret_key:{child}")
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v, child, findings, pii, pii_key)
        return out

    if isinstance(value, list):
        return [redact(i, f"{path}[]", findings, pii, pii_key) for i in value]

    if isinstance(value, str):
        # PII pseudonymization first, then secret value redaction
        text = value
        for pii_name, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(text):
                orig = match.group(0)
                token = pseudonymize(orig, pii_key)
                pii[token] = pii_name
                text = text.replace(orig, token)
        if _looks_like_secret_value(text) and not any(text.startswith(prefix) for prefix in ("pii_", "[REDACTED")):
            findings.append(f"redacted_secret_value:{path}")
            return "[REDACTED]"
        return text

    return value


def _already_redacted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("[REDACTED")


def enforce_allowlist(event: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Remove any top-level fields not in the canonical allowlist and report."""
    violations = [k for k in event if k not in ALLOWED_TOP_FIELDS]
    return {k: v for k, v in event.items() if k in ALLOWED_TOP_FIELDS}, violations


def enforce_label_cardinality(labels: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Drop unknown/high-cardinality labels (trace/session IDs are never labels)."""
    if not labels:
        return {}
    safe: Dict[str, str] = {}
    for k, v in labels.items():
        if k not in ALLOWED_LABEL_KEYS:
            continue
        # Sanitize value to a short, controlled token
        safe_v = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", str(v))[:48]
        if k in ("trace_id", "span_id", "session_id", "execution_id"):
            continue
        safe[k] = safe_v
    return safe


class PrivacyGuard:
    def __init__(
        self,
        pii_key: Optional[bytes] = None,
        max_event_bytes: int = 256 * 1024,
        max_trace_bytes: int = 4 * 1024 * 1024,
        sample_rate: float = 0.5,
        forced_capture: bool = True,
        secret_patterns: Optional[List[str]] = None,
    ):
        self.pii_key = pii_key or DEFAULT_PII_KEY
        self.max_event_bytes = max_event_bytes
        self.max_trace_bytes = max_trace_bytes
        self.sample_rate = max(0.0, min(1.0, sample_rate))
        self.forced_capture = forced_capture
        self.secret_patterns = secret_patterns or [SENSITIVE_KEY_PATTERNS]

    def should_capture(self, event: Dict[str, Any]) -> bool:
        """Sampling: keep normal traces with probability; always capture risk/error/anomaly."""
        if isinstance(event, dict):
            event = event
        elif hasattr(event, "to_dict"):
            event = event.to_dict()
        else:
            return True
        if not self.forced_capture:
            return True
        if event.get("event_type") in ("error", "uc300_block", "uc290_escalation", "uc324_containment"):
            return True
        if event.get("error"):
            return True
        uc290 = event.get("uc290") or {}
        if uc290.get("escalation") or uc290.get("override"):
            return True
        uc300 = event.get("uc300") or {}
        if uc300.get("authorized") is False:
            return True
        import random
        return random.random() < self.sample_rate

    def sanitize(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Apply full privacy pipeline to a raw event dict."""
        # 1. Size guard
        payload = json.dumps(event, default=str).encode("utf-8")
        if len(payload) > self.max_event_bytes:
            raise ValueError(f"event exceeds max_event_bytes: {len(payload)} > {self.max_event_bytes}")

        # 2. Redact secrets and pseudonymize PII
        findings: List[str] = []
        pii: Dict[str, str] = {}
        redacted = redact(event, findings=findings, pii=pii, pii_key=self.pii_key)

        # 3. Reject/ transform private chain-of-thought
        raw_thought = redacted.get("structured_reasoning_summary", "") or ""
        if any(k in json.dumps(redacted, default=str).lower() for k in ("chain_of_thought", "raw_thought")):
            findings.append("private_reasoning_transformed")
            redacted = _strip_private_reasoning(redacted)
        if "raw:" in raw_thought.lower():
            redacted["structured_reasoning_summary"] = "[SUMMARY_ONLY]"
            findings.append("raw_reasoning_rejected")

        # 4. Allowlist
        allowed, violations = enforce_allowlist(redacted)
        allowed["redaction_findings"] = findings
        allowed["pii_pseudonyms"] = pii
        allowed["allowlist_violations"] = violations

        # 5. Label cardinality
        allowed["labels"] = enforce_label_cardinality(allowed.get("labels"))

        return allowed

    def pseudonym_for(self, value: str) -> str:
        return pseudonymize(value, self.pii_key)


def _strip_private_reasoning(event: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any chain-of-thought-like fields and keep only a structured summary."""
    event = {k: v for k, v in event.items() if k not in ("chain_of_thought", "raw_thought", "internal_thought")}
    if "structured_reasoning_summary" in event and event["structured_reasoning_summary"]:
        event["structured_reasoning_summary"] = "[SUMMARY_ONLY]"
    return event
