"""Privacy-Preserving LLMOps Controller integrado en UC-703."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fine_tuning.privacy.crypto_vault_agent import CryptoVaultAgent, NetworkPolicyAgent
from fine_tuning.privacy.data_privacy_agent import (
    DataContractValidator,
    DataRetentionAgent,
    DeIdentificationAgent,
)
from fine_tuning.privacy.inference_audit_agents import (
    InferencePrivacyAgent,
    WORMAuditAgent,
)
from fine_tuning.privacy.models_privacy import (
    DataContract,
    DPTrainingConfig,
    NetworkPolicy,
    PrivacyPipelineState,
    WORMAuditEntry,
)
from fine_tuning.privacy.privacy_training_agents import (
    DPTrainingAgent,
    MembershipInferenceAttackAgent,
)


class PrivacyPreservingLLMOpsController:
    """
    Orquesta privacidad en el ciclo de vida LLMOps dentro de UC-703.

    No reemplaza a UC-324, UC-300, UC-290, UC-309 ni UC-075; se integra con ellos
    como capa de policy-as-code sobre el fine-tuning controller.
    """

    def __init__(
        self,
        deid_agent: Optional[DeIdentificationAgent] = None,
        contract_validator: Optional[DataContractValidator] = None,
        retention_agent: Optional[DataRetentionAgent] = None,
        dp_agent: Optional[DPTrainingAgent] = None,
        mi_agent: Optional[MembershipInferenceAttackAgent] = None,
        network_agent: Optional[NetworkPolicyAgent] = None,
        crypto_agent: Optional[CryptoVaultAgent] = None,
        inference_privacy: Optional[InferencePrivacyAgent] = None,
        audit_agent: Optional[WORMAuditAgent] = None,
    ) -> None:
        self.deid = deid_agent or DeIdentificationAgent()
        self.contract_validator = contract_validator or DataContractValidator()
        self.retention = retention_agent or DataRetentionAgent()
        self.dp = dp_agent or DPTrainingAgent()
        self.mi = mi_agent or MembershipInferenceAttackAgent()
        self.network = network_agent or NetworkPolicyAgent()
        self.crypto = crypto_agent or CryptoVaultAgent()
        self.inference_privacy = inference_privacy or InferencePrivacyAgent()
        self.audit = audit_agent or WORMAuditAgent()
        self._pipelines: Dict[str, PrivacyPipelineState] = {}

    def create_pipeline(self) -> PrivacyPipelineState:
        state = PrivacyPipelineState()
        self._pipelines[state.pipeline_id] = state
        return state

    def _new_state(self) -> PrivacyPipelineState:
        return self.create_pipeline()

    def _record(
        self,
        state: PrivacyPipelineState,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        compliance_tags: Optional[List[str]] = None,
    ) -> WORMAuditEntry:
        entry = self.audit.record(
            event_type=event_type,
            actor=actor,
            resource=resource,
            action=action,
            compliance_tags=compliance_tags or [],
        )
        state.audit_log.append(entry)
        return entry

    # ------------------------------------------------------------------
    # 1. Ingesta: contrato + desidentificación + retención
    # ------------------------------------------------------------------
    def apply_data_contract(
        self,
        samples: List[Dict[str, Any]],
        contract: DataContract,
    ) -> PrivacyPipelineState:
        state = self._new_state()
        state.contract = contract
        validation = self.contract_validator.validate(samples, contract)
        self._record(
            state,
            "data_contract_validation",
            "DataContractValidator",
            contract.contract_id,
            "validate" if validation["valid"] else "reject",
            compliance_tags=["GDPR_Art25", "CCPA", "minimization"],
        )
        state.status = "contract_valid" if validation["valid"] else "contract_violation"
        return state

    def deidentify_samples(
        self,
        pipeline_id: str,
        samples: List[Dict[str, Any]],
        text_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        text_fields = text_fields or ["instruction", "output"]
        results: List[Dict[str, Any]] = []
        total_findings = 0
        for idx, sample in enumerate(samples):
            for field in text_fields:
                if field in sample and isinstance(sample[field], str):
                    res = self.deid.deidentify(sample[field])
                    total_findings += len(res.findings)
                    sample = {**sample, field: res.anonymized_text}
            results.append(sample)
        state.deid = self.deid.deidentify("" if not samples else str(samples[0]))
        state.deid.findings = []  # placeholder; per-sample findings handled externally
        self._record(
            state,
            "deidentification",
            "DeIdentificationAgent",
            pipeline_id,
            f"processed_{len(samples)}_samples_{total_findings}_findings",
            compliance_tags=["GDPR_Art32", "HIPAA_164.312"],
        )
        return {"samples": results, "findings_count": total_findings}

    def apply_retention(
        self,
        pipeline_id: str,
        raw_data_uri: str,
        retention_hours: float,
        feature_extracted: bool = True,
    ) -> PrivacyPipelineState:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        decision = self.retention.apply_ttl(raw_data_uri, retention_hours, feature_extracted)
        state.retention = decision
        self._record(
            state,
            "data_retention",
            "DataRetentionAgent",
            raw_data_uri,
            decision.action,
            compliance_tags=["GDPR_Art5_storage_limitation", "CCPA_deletion"],
        )
        return state

    # ------------------------------------------------------------------
    # 2. Entrenamiento: DP + membership inference
    # ------------------------------------------------------------------
    def configure_dp_training(
        self,
        pipeline_id: str,
        dp_config: DPTrainingConfig,
    ) -> PrivacyPipelineState:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        state.dp_config = dp_config
        self._record(
            state,
            "dp_training_config",
            "DPTrainingAgent",
            dp_config.config_id,
            f"eps={dp_config.epsilon}_delta={dp_config.delta}",
            compliance_tags=["GDPR_Art32", "differential_privacy"],
        )
        return state

    def apply_dp_to_training(
        self,
        pipeline_id: str,
        run_id: str,
        dataset_size: int,
        steps: int,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.dp_config:
            raise ValueError("pipeline or dp_config not found")
        result = self.dp.apply(run_id, state.dp_config, dataset_size, steps)
        state.dp_result = result
        if result.privacy_budget_exceeded:
            state.status = "dp_budget_exceeded"
        self._record(
            state,
            "dp_training_applied",
            "DPTrainingAgent",
            run_id,
            f"epsilon_spent={result.epsilon_spent}",
            compliance_tags=["differential_privacy", "EU_AI_Act_high_risk"],
        )
        return result.to_dict()

    def validate_membership_inference(
        self,
        pipeline_id: str,
        run_id: str,
        members: List[Dict[str, Any]],
        non_members: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        report = self.mi.evaluate(run_id, members, non_members)
        state.mi_report = report
        if not report.passed:
            state.status = "membership_inference_failed"
        self._record(
            state,
            "membership_inference_validation",
            "MembershipInferenceAttackAgent",
            run_id,
            f"accuracy={report.attack_accuracy}_risk={report.exposure_risk}",
            compliance_tags=["memorization_risk", "EU_AI_Act_high_risk"],
        )
        return report.to_dict()

    # ------------------------------------------------------------------
    # 3. Infraestructura: red Zero Trust + cifrado
    # ------------------------------------------------------------------
    def enforce_network_policy(
        self,
        pipeline_id: str,
        policy: Optional[NetworkPolicy] = None,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        state.network_policy = policy or NetworkPolicyAgent.DEFAULT
        result = self.network.validate(state.network_policy)
        self._record(
            state,
            "network_policy_validation",
            "NetworkPolicyAgent",
            state.network_policy.policy_id,
            "enforce" if result["passed"] else "reject",
            compliance_tags=["zero_trust", "NIST_800-207"],
        )
        return result

    def issue_encryption_lease(
        self,
        pipeline_id: str,
        resource: str,
        ttl_seconds: float = 3600,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        result = self.crypto.issue_data_key(resource, ttl_seconds)
        state.crypto = result
        self._record(
            state,
            "encryption_lease_issued",
            "CryptoVaultAgent",
            resource,
            f"key={result.key_id}_tls={result.transit_tls_version}",
            compliance_tags=["encryption_at_rest", "tls_1.3", "key_management"],
        )
        return result.to_dict()

    # ------------------------------------------------------------------
    # 4. Inferencia: guardrails pre/post-vuelo
    # ------------------------------------------------------------------
    def preflight_inference(self, pipeline_id: str, request_id: str, prompt: str) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        report = self.inference_privacy.preflight(request_id, prompt)
        self._record(
            state,
            "inference_preflight",
            "InferencePrivacyAgent",
            request_id,
            "blocked" if report.blocked else "allowed",
            compliance_tags=["input_guardrail", "anti_extraction"],
        )
        return report.to_dict()

    def postflight_inference(
        self,
        pipeline_id: str,
        request_id: str,
        prompt: str,
        output: str,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        report = self.inference_privacy.postflight(request_id, prompt, output)
        self._record(
            state,
            "inference_postflight",
            "InferencePrivacyAgent",
            request_id,
            "blocked" if report.blocked else "allowed",
            compliance_tags=["output_guardrail", "PII_leakage"],
        )
        return report.to_dict()

    # ------------------------------------------------------------------
    # 5. Gobernanza: model cards + data sheets
    # ------------------------------------------------------------------
    def generate_model_card(
        self,
        pipeline_id: str,
        model_name: str,
        intended_use: str,
        privacy_controls: List[str],
        limitations: List[str],
        compliance_frameworks: List[str],
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        dp_epsilon = state.dp_result.epsilon_spent if state.dp_result else 0.0
        mi_risk = state.mi_report.exposure_risk if state.mi_report else "unknown"
        card = self.audit.generate_model_card(
            model_name=model_name,
            intended_use=intended_use,
            dp_epsilon=dp_epsilon,
            mi_risk=mi_risk,
            privacy_controls=privacy_controls,
            limitations=limitations,
            compliance_frameworks=compliance_frameworks,
        )
        state.model_card = card
        self._record(
            state,
            "model_card_generated",
            "WORMAuditAgent",
            model_name,
            f"dp_eps={dp_epsilon}_mi={mi_risk}",
            compliance_tags=["model_card", "EU_AI_Act_transparency"],
        )
        return card.to_dict()

    def generate_data_sheet(
        self,
        pipeline_id: str,
        dataset_id: str,
        source: str,
        sensitive_attributes: List[str],
        anonymization_method: str,
        retention_hours: float,
        purpose: str,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        sheet = self.audit.generate_data_sheet(
            dataset_id=dataset_id,
            source=source,
            sensitive_attributes=sensitive_attributes,
            anonymization_method=anonymization_method,
            retention_hours=retention_hours,
            purpose=purpose,
        )
        state.data_sheet = sheet
        self._record(
            state,
            "data_sheet_generated",
            "WORMAuditAgent",
            dataset_id,
            f"retention={retention_hours}h",
            compliance_tags=["data_sheet", "GDPR_Art30_record_of_processing"],
        )
        return sheet.to_dict()

    def generate_privacy_artifacts(
        self,
        pipeline_id: str,
        model_name: str,
        intended_use: str,
        privacy_controls: List[str],
        limitations: List[str],
        compliance_frameworks: List[str],
        data_source: str,
        sensitive_attributes: List[str],
        anonymization_method: str,
        retention_hours: float,
        purpose: str,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("pipeline not found")
        model_card = self.generate_model_card(
            pipeline_id,
            model_name,
            intended_use,
            privacy_controls,
            limitations,
            compliance_frameworks,
        )
        data_sheet = self.generate_data_sheet(
            pipeline_id,
            state.contract.contract_id if state.contract else "",
            data_source,
            sensitive_attributes,
            anonymization_method,
            retention_hours,
            purpose,
        )
        return {"model_card": model_card, "data_sheet": data_sheet}

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_pipeline(self, pipeline_id: str) -> Optional[PrivacyPipelineState]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self, status: Optional[str] = None) -> List[PrivacyPipelineState]:
        pipelines = list(self._pipelines.values())
        if status:
            pipelines = [p for p in pipelines if p.status == status]
        return pipelines

    def get_audit_log(self, pipeline_id: str) -> List[Dict[str, Any]]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            return []
        return [e.to_dict() for e in state.audit_log]
