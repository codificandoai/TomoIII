"""Ledger WORM de auditoría de inferencia con hash chain."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from compliance_as_code.models_compliance import (
    ArtifactBundle,
    InferenceAuditRecord,
)


class InferenceAuditLedger:
    """
    Ledger inmutable (WORM) de auditoría de inferencia.
    Cada registro incluye input/output redactados, artefacto compuesto exacto,
    decisión de acceso y hash chain.
    """

    def __init__(self) -> None:
        self._records: List[InferenceAuditRecord] = []

    def record(
        self,
        request_id: str,
        session_id: str,
        requester_id: str,
        requester_roles: List[str],
        artifact_bundle: ArtifactBundle,
        input_text: str,
        output_text: str,
        access_decision: str,
        policies_applied: List[str],
        pii_detected: bool = False,
        guardrail_violations: Optional[List[str]] = None,
        e_discovery_tag: str = "",
    ) -> InferenceAuditRecord:
        prev_hash = self._records[-1].hash_chain if self._records else "genesis"
        payload = {
            "request_id": request_id,
            "session_id": session_id,
            "requester_id": requester_id,
            "requester_roles": requester_roles,
            "artifact_bundle": artifact_bundle.to_dict(),
            "input_redacted": input_text,
            "output_redacted": output_text,
            "access_decision": access_decision,
            "policies_applied": policies_applied,
            "pii_detected": pii_detected,
            "guardrail_violations": guardrail_violations or [],
            "e_discovery_tag": e_discovery_tag,
            "timestamp": time.time(),
            "prev_hash": prev_hash,
        }
        hash_chain = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        rec = InferenceAuditRecord(
            request_id=request_id,
            session_id=session_id,
            requester_id=requester_id,
            requester_roles=list(requester_roles),
            artifact_bundle=artifact_bundle,
            input_redacted=input_text,
            output_redacted=output_text,
            access_decision=access_decision,
            policies_applied=list(policies_applied),
            pii_detected=pii_detected,
            guardrail_violations=guardrail_violations or [],
            hash_chain=hash_chain,
            e_discovery_tag=e_discovery_tag,
            timestamp=payload["timestamp"],
        )
        self._records.append(rec)
        return rec

    def query_by_request(self, request_id: str) -> List[InferenceAuditRecord]:
        return [r for r in self._records if r.request_id == request_id]

    def query_by_session(self, session_id: str) -> List[InferenceAuditRecord]:
        return [r for r in self._records if r.session_id == session_id]

    def query_by_requester(self, requester_id: str) -> List[InferenceAuditRecord]:
        return [r for r in self._records if r.requester_id == requester_id]

    def query_by_tag(self, tag: str) -> List[InferenceAuditRecord]:
        return [r for r in self._records if r.e_discovery_tag == tag]

    def verify_chain(self) -> bool:
        for i, rec in enumerate(self._records):
            prev_hash = self._records[i - 1].hash_chain if i > 0 else "genesis"
            payload = {
                "request_id": rec.request_id,
                "session_id": rec.session_id,
                "requester_id": rec.requester_id,
                "requester_roles": rec.requester_roles,
                "artifact_bundle": rec.artifact_bundle.to_dict() if rec.artifact_bundle else None,
                "input_redacted": rec.input_redacted,
                "output_redacted": rec.output_redacted,
                "access_decision": rec.access_decision,
                "policies_applied": rec.policies_applied,
                "pii_detected": rec.pii_detected,
                "guardrail_violations": rec.guardrail_violations,
                "e_discovery_tag": rec.e_discovery_tag,
                "timestamp": rec.timestamp,
                "prev_hash": prev_hash,
            }
            expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if rec.hash_chain != expected:
                return False
        return True

    def list_records(self) -> List[InferenceAuditRecord]:
        return list(self._records)
