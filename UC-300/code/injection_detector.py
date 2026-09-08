"""
UC-300 — Detector de inyección de comandos y prompts.

Capa defensiva estática que inspecciona strings profundamente.
No reemplaza la validación estricta del esquema; la complementa.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Patrones de inyección de comandos/shell/SQL
# ---------------------------------------------------------------------------

COMMAND_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    (r";\s*DROP\s+TABLE", "sql_drop_table"),
    (r";\s*DELETE\s+FROM", "sql_delete_from"),
    (r";\s*INSERT\s+INTO", "sql_insert_into"),
    (r";\s*UPDATE\s+\w+\s+SET", "sql_update"),
    (r"--", "sql_comment"),
    (r"/\*", "sql_block_comment"),
    (r"\$\s*\(", "command_substitution"),
    (r"`", "backtick_command"),
    (r"\|\|", "shell_or"),
    (r"&&", "shell_and"),
    (r"\b(rm|del|mkfs|format)\s+", "destructive_command"),
    (r"[<>]\s*/(dev|proc|etc|var|bin|sbin|usr|opt|home|root|tmp)", "redirect_to_system_path"),
    (r"base64\s+--decode", "base64_decode"),
    (r"curl\s+", "curl_command"),
    (r"wget\s+", "wget_command"),
    (r"eval\s*\(", "eval_call"),
    (r"exec\s*\(", "exec_call"),
]

PROMPT_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    (r"ignore\s+previous\s+instructions", "ignore_previous_instructions"),
    (r"ignore\s+all\s+(prior|previous)\s+(instructions|rules)", "ignore_all_rules"),
    (r"you\s+are\s+now\s+", "role_override"),
    (r"system\s+prompt", "system_prompt_leak"),
    (r"new\s+system\s+instruction", "new_system_instruction"),
    (r"disregard\s+(?:safety|security|policy|policies)", "disregard_policy"),
    (r"DAN\b", "dan_jailbreak"),
    (r"jailbreak", "jailbreak_keyword"),
    (r"simulate\s+(?:no|without)\s+(?:safety|restrictions)", "simulate_no_restrictions"),
    (r"pretend\s+to\s+be", "pretend_role"),
]

# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class InjectionDetectionError(Exception):
    """Se detectó contenido potencialmente malicioso."""

    def __init__(self, message: str, matched: List[Dict[str, Any]]):
        super().__init__(message)
        self.matched = matched


def _inspect_string(value: str) -> List[Dict[str, Any]]:
    """Escanea un string contra todos los patrones."""
    matched: List[Dict[str, Any]] = []
    text_lower = value.lower()
    for pattern, category in COMMAND_INJECTION_PATTERNS + PROMPT_INJECTION_PATTERNS:
        for m in re.finditer(pattern, text_lower, re.IGNORECASE):
            matched.append({
                "category": category,
                "pattern": pattern,
                "matched_text": value[m.start():m.end()],
                "position": m.start(),
            })
    return matched


def inspect_value(value: Any, path: str = "") -> List[Dict[str, Any]]:
    """Inspecciona recursivamente un valor."""
    findings: List[Dict[str, Any]] = []
    if isinstance(value, str):
        for finding in _inspect_string(value):
            finding["path"] = path
            findings.append(finding)
    elif isinstance(value, dict):
        for k, v in value.items():
            findings.extend(inspect_value(v, f"{path}.{k}" if path else k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            findings.extend(inspect_value(v, f"{path}[{i}]"))
    return findings


def inspect_request(agent_id: str, action: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inspecciona una solicitud completa."""
    findings: List[Dict[str, Any]] = []
    findings.extend(inspect_value(agent_id, "agent_id"))
    findings.extend(inspect_value(action, "action"))
    findings.extend(inspect_value(params, "params"))
    return findings


def assert_clean(agent_id: str, action: str, params: Dict[str, Any]) -> None:
    """Lanza excepción si se detecta inyección."""
    findings = inspect_request(agent_id, action, params)
    if findings:
        categories = sorted({f["category"] for f in findings})
        raise InjectionDetectionError(
            f"Injection detected: {categories}",
            findings,
        )


def scan_output(output: Any) -> List[Dict[str, Any]]:
    """Escanea una salida sandbox en busca de fugas de datos sensibles."""
    findings: List[Dict[str, Any]] = []
    if isinstance(output, dict):
        for k, v in output.items():
            if isinstance(v, str):
                for finding in _inspect_string(v):
                    finding["path"] = k
                    findings.append(finding)
            else:
                findings.extend(scan_output(v))
    elif isinstance(output, str):
        findings.extend(_inspect_string(output))
    return findings
