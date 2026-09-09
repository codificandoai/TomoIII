"""Modelos para Enterprise QA Driver basado en pilares de negocio, dominio y procesos."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ControlFlag(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class Pillar(str, Enum):
    BUSINESS_LOGIC = "BUSINESS_LOGIC"
    DOMAIN_LANGUAGE = "DOMAIN_LANGUAGE"
    PROCESS_LOGIC = "PROCESS_LOGIC"
    COMPLIANCE = "COMPLIANCE"


@dataclass
class TestCase:
    id: str = ""
    pillar: str = ""
    prompt: str = ""
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)
    required_sequence: List[str] = field(default_factory=list)
    llm_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pillar": self.pillar,
            "prompt": self.prompt,
            "expected_keywords": self.expected_keywords,
            "forbidden_keywords": self.forbidden_keywords,
            "required_sequence": self.required_sequence,
            "llm_response": self.llm_response,
        }


@dataclass
class KPIResult:
    test_id: str = ""
    pillar: str = ""
    kpi_name: str = ""
    score: float = 0.0
    flag: str = ""
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "pillar": self.pillar,
            "kpi_name": self.kpi_name,
            "score": self.score,
            "flag": self.flag,
            "details": self.details,
        }


@dataclass
class EscalationAction:
    flag: str = ""
    action: str = ""
    owner: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag": self.flag,
            "action": self.action,
            "owner": self.owner,
            "description": self.description,
        }


@dataclass
class QAReport:
    report_id: str = field(default_factory=lambda: f"qa-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    global_status: str = ""
    action: str = ""
    total_tests: int = 0
    red_flags: int = 0
    yellow_flags: int = 0
    green_flags: int = 0
    results: List[KPIResult] = field(default_factory=list)
    escalations: List[EscalationAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "global_status": self.global_status,
            "action": self.action,
            "total_tests": self.total_tests,
            "red_flags": self.red_flags,
            "yellow_flags": self.yellow_flags,
            "green_flags": self.green_flags,
            "results": [r.to_dict() for r in self.results],
            "escalations": [e.to_dict() for e in self.escalations],
        }
