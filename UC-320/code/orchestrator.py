"""UC-320 — Orchestrator: integra HF Gateway, Skills, Benchmark, Training, UC-324 Gates."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from benchmark import ModelBenchmark
from contracts import ContractBuilder, SecureContract
from hf_gateway import HuggingFaceModelGateway
from hf_services import (
    DatasetManager,
    EvaluateService,
    HFServices,
    InferenceEndpointManager,
    ModelCardData,
    ModelCardService,
    PEFTConfig,
    PEFTService,
    SpaceManager,
    TrainerService,
    TrainingConfig,
)
from model_catalog import ModelCatalog
from skills import (
    ClassificationResult,
    EmbeddingResult,
    MarketSentimentSkill,
    SemanticEmbeddingSkill,
    SentimentEvidence,
    ZeroShotClassificationSkill,
)
from templates import TemplateRegistry
from training import TrainingManager, TrainingStatus
from uc324_gates import ContainmentDecision, UC324GateIntegrator, Verdict


@dataclass
class OrchestratorResult:
    """Resultado completo de una operación del orquestador."""

    request_id: str
    operation: str
    allowed: bool
    verdict: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    evidence: Optional[Dict[str, Any]] = None
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "allowed": self.allowed,
            "verdict": self.verdict,
            "issues": self.issues,
            "warnings": self.warnings,
            "evidence": self.evidence,
            "audit_log": self.audit_log,
            "latency_ms": round(self.latency_ms, 2),
        }


class UC320Orchestrator:
    """Orquestador central de UC-320.

    Flujo integrado de inferencia:
      1. UC-315 define contexto y pregunta de dominio.
      2. UC-317 + HF Gateway ejecuta inferencia.
      3. UC-324 valida con gates PRE/EXEC/POST.
      4. UC-315 interpreta resultado como evidencia (no como orden).
    """

    def __init__(
        self,
        catalog: Optional[ModelCatalog] = None,
        gateway: Optional[HuggingFaceModelGateway] = None,
        gates: Optional[UC324GateIntegrator] = None,
        training: Optional[TrainingManager] = None,
        templates: Optional[TemplateRegistry] = None,
        hf_services: Optional[HFServices] = None,
    ) -> None:
        self.catalog = catalog or ModelCatalog()
        self.gateway = gateway or HuggingFaceModelGateway(catalog=self.catalog, backend="mock")
        self.gates = gates or UC324GateIntegrator()
        self.training = training or TrainingManager()
        self.templates = templates or TemplateRegistry()
        self.benchmark = ModelBenchmark(self.gateway)
        self.hf = hf_services or HFServices(backend="mock")

    # --- Inferencia de sentimiento ---
    def sentiment(
        self,
        ticker: str,
        article: str,
        model_id: str = "mock/sentiment-mock",
    ) -> OrchestratorResult:
        contract = ContractBuilder.sentiment_inference(ticker, article, model_id, self.gateway.catalog.get(model_id).provider if self.gateway.catalog.get(model_id) else "mock")
        return self._run_inference(contract, lambda: MarketSentimentSkill(self.gateway, model_id).run(ticker, article, contract.request_id))

    # --- Embeddings ---
    def embedding(
        self,
        text: str,
        model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> OrchestratorResult:
        entry = self.gateway.catalog.get(model_id)
        provider = entry.provider if entry else "mock"
        contract = ContractBuilder.embedding(text, model_id, provider)
        return self._run_inference(contract, lambda: SemanticEmbeddingSkill(self.gateway, model_id).run(text, contract.request_id))

    # --- Clasificación zero-shot ---
    def classify(
        self,
        text: str,
        candidate_labels: Optional[List[str]] = None,
        model_id: str = "facebook/bart-large-mnli",
    ) -> OrchestratorResult:
        entry = self.gateway.catalog.get(model_id)
        provider = entry.provider if entry else "mock"
        contract = SecureContract(
            operation="zero_shot_classification",
            model_id=model_id,
            provider=provider,
            input={"text": text, "candidate_labels": candidate_labels or []},
            output_schema="ClassificationResult.v1",
        )
        return self._run_inference(
            contract,
            lambda: ZeroShotClassificationSkill(self.gateway, model_id).run(text, candidate_labels, contract.request_id),
        )

    # --- Benchmark de modelos ---
    def run_benchmark(
        self,
        prompt: str,
        models: Optional[List] = None,
    ) -> Dict[str, Any]:
        return self.benchmark.compare(prompt, models)

    # --- Training ---
    def submit_training(
        self,
        base_model: str,
        dataset_id: str,
        dataset_revision: str,
        objective: str,
    ) -> Dict[str, Any]:
        contract = ContractBuilder.training(base_model, dataset_id, dataset_revision, objective)
        decision = self.gates.evaluate(contract.to_gate_dict(estimated_cost=5.0, estimated_latency=600000))
        if not decision.allowed:
            return {
                "allowed": False,
                "issues": decision.issues,
                "message": "Training blocked by UC-324 gates",
            }
        job = self.training.submit(base_model, dataset_id, dataset_revision, f"artifacts/{base_model.split('/')[-1]}", objective)
        return {"allowed": True, "job_id": job.job_id, "status": job.status.value}

    def run_training(self, job_id: str) -> Dict[str, Any]:
        job = self.training.run(job_id, approved=True)
        return job.to_dict()

    def promote_model(self, job_id: str, human_approved: bool) -> Dict[str, Any]:
        job = self.training.get(job_id)
        if not job:
            return {"promoted": False, "reason": f"Job {job_id} not found"}
        contract = ContractBuilder.model_promotion(job_id, job.checkpoint_hash)
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"promoted": False, "issues": decision.issues}
        return self.training.promote(job_id, human_approved)

    # --- Templates ---
    def list_templates(self) -> List[Dict[str, Any]]:
        return self.templates.list_templates()

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        t = self.templates.get(template_id)
        return t.to_dict() if t else None

    # --- HF Services ---

    def hf_status(self) -> Dict[str, Any]:
        return self.hf.status()

    # Inference Endpoints
    def create_endpoint(self, name: str, model_id: str, **kwargs) -> Dict[str, Any]:
        contract = SecureContract(
            operation="create_endpoint",
            model_id=model_id,
            action_class="execute",
            risk_level="high",
            requires_human_approval=True,
            input={"name": name, **kwargs},
        )
        decision = self.gates.evaluate(contract.to_gate_dict(allowed_models=self.catalog.allowed_models()))
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        ep = self.hf.endpoints.create(name=name, model_id=model_id, **kwargs)
        return {"allowed": True, "endpoint": ep.to_dict()}

    def list_endpoints(self) -> List[Dict[str, Any]]:
        return self.hf.endpoints.list_endpoints()

    def stop_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        return self.hf.endpoints.stop(endpoint_id)

    def delete_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        contract = SecureContract(
            operation="delete_endpoint",
            action_class="delete",
            risk_level="critical",
            requires_human_approval=True,
            input={"endpoint_id": endpoint_id},
        )
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        return self.hf.endpoints.delete(endpoint_id)

    def endpoint_health(self, endpoint_id: str) -> Dict[str, Any]:
        return self.hf.endpoints.health_check(endpoint_id)

    # Datasets
    def load_dataset(self, dataset_id: str, revision: str = "main", split: str = "train",
                     pii_checked: bool = False, contamination_checked: bool = False) -> Dict[str, Any]:
        contract = SecureContract(
            operation="load_dataset",
            model_id=dataset_id,
            action_class="read",
            risk_level="medium",
            input={"dataset_id": dataset_id, "revision": revision, "split": split},
        )
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        record = self.hf.datasets.load(dataset_id, revision, split, pii_checked, contamination_checked)
        return {"allowed": True, "dataset": record.to_dict()}

    def list_datasets(self) -> List[Dict[str, Any]]:
        return self.hf.datasets.list_datasets()

    def validate_dataset(self, dataset_id: str, revision: str, split: str) -> Dict[str, Any]:
        return self.hf.datasets.validate_for_training(dataset_id, revision, split)

    def transform_dataset(self, dataset_id: str, revision: str, split: str,
                          fn_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.hf.datasets.transform(dataset_id, revision, split, fn_name, params)

    # Trainer
    def train_model(self, config: TrainingConfig, approved: bool = True) -> Dict[str, Any]:
        contract = ContractBuilder.training(
            config.base_model, config.dataset_id, config.dataset_revision, config.objective
        )
        decision = self.gates.evaluate(contract.to_gate_dict(estimated_cost=5.0, estimated_latency=600000))
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        result = self.hf.trainer.train(config, self.hf.datasets, approved=approved)
        return {"allowed": True, **result}

    def list_trainer_jobs(self) -> List[Dict[str, Any]]:
        return self.hf.trainer.list_jobs()

    # PEFT
    def create_peft_adapter(self, config: PEFTConfig) -> Dict[str, Any]:
        contract = SecureContract(
            operation="create_peft_adapter",
            model_id=config.base_model,
            action_class="execute",
            risk_level="medium",
            input=config.to_dict(),
        )
        decision = self.gates.evaluate(contract.to_gate_dict(allowed_models=self.catalog.allowed_models()))
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        result = self.hf.peft.create_adapter(config)
        return {"allowed": True, **result}

    def list_peft_adapters(self) -> List[Dict[str, Any]]:
        return self.hf.peft.list_adapters()

    def save_peft_adapter(self, adapter_id: str, repo_id: str) -> Dict[str, Any]:
        return self.hf.peft.save_adapter(adapter_id, repo_id)

    # Evaluate
    def compute_metrics(self, metric_name: str, predictions: List, references: List) -> Dict[str, Any]:
        return self.hf.evaluate.compute(metric_name, predictions, references)

    def compare_models_metrics(self, metric_name: str, candidates: Dict) -> Dict[str, Any]:
        return self.hf.evaluate.compare(metric_name, candidates)

    def list_eval_results(self) -> List[Dict[str, Any]]:
        return self.hf.evaluate.list_results()

    # Spaces
    def create_space(self, name: str, sdk: str = "gradio", model_id: str = "",
                     hardware: str = "cpu-basic", description: str = "", public: bool = False) -> Dict[str, Any]:
        contract = SecureContract(
            operation="create_space",
            model_id=model_id,
            action_class="execute",
            risk_level="medium",
            requires_human_approval=False,
            input={"name": name, "sdk": sdk, "public": public},
        )
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        space = self.hf.spaces.create(name=name, sdk=sdk, model_id=model_id,
                                       hardware=hardware, description=description, public=public)
        return {"allowed": True, "space": space.to_dict()}

    def list_spaces(self) -> List[Dict[str, Any]]:
        return self.hf.spaces.list_spaces()

    def stop_space(self, space_id: str) -> Dict[str, Any]:
        return self.hf.spaces.stop(space_id)

    def delete_space(self, space_id: str) -> Dict[str, Any]:
        contract = SecureContract(
            operation="delete_space",
            action_class="delete",
            risk_level="critical",
            requires_human_approval=True,
            input={"space_id": space_id},
        )
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        return self.hf.spaces.delete(space_id)

    # Model Cards
    def create_model_card(self, data: ModelCardData) -> Dict[str, Any]:
        card = self.hf.model_cards.create(data)
        return {"created": True, "model_card": card.to_dict()}

    def get_model_card(self, model_id: str) -> Optional[Dict[str, Any]]:
        card = self.hf.model_cards.get(model_id)
        return card.to_dict() if card else None

    def get_model_card_markdown(self, model_id: str) -> Optional[str]:
        return self.hf.model_cards.get_markdown(model_id)

    def approve_model_card(self, model_id: str, approved_by: str, red_team_passed: bool) -> Dict[str, Any]:
        return self.hf.model_cards.approve(model_id, approved_by, red_team_passed)

    def push_model_card(self, model_id: str, repo_id: str) -> Dict[str, Any]:
        contract = SecureContract(
            operation="push_model_card",
            action_class="execute",
            risk_level="high",
            requires_human_approval=True,
            input={"model_id": model_id, "repo_id": repo_id},
        )
        decision = self.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return {"allowed": False, "issues": decision.issues}
        return self.hf.model_cards.push_to_hub(model_id, repo_id)

    def list_model_cards(self) -> List[Dict[str, Any]]:
        return self.hf.model_cards.list_cards()

    # --- Interno ---
    def _run_inference(self, contract: SecureContract, executor) -> OrchestratorResult:
        started = time.perf_counter()
        entry = self.gateway.catalog.get(contract.model_id)
        gate_input = contract.to_gate_dict(
            allowed_models=self.catalog.allowed_models(),
            estimated_cost=entry.cost_per_1k if entry else 0.0,
            estimated_latency=entry.latency_ms if entry else 500.0,
        )

        # Gate PRE
        pre_results = self.gates.gate_pre(gate_input)
        pre_issues = [r.message for r in pre_results if r.verdict.value == "block"]
        if pre_issues:
            audit = [r.to_dict() for r in pre_results]
            self.gates.audit_log.extend(audit)
            return OrchestratorResult(
                request_id=contract.request_id,
                operation=contract.operation,
                allowed=False,
                verdict="block",
                issues=pre_issues,
                audit_log=audit,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        # Gate EXEC
        exec_results = self.gates.gate_exec(gate_input)
        exec_issues = [r.message for r in exec_results if r.verdict.value == "block"]
        if exec_issues:
            audit = [r.to_dict() for r in pre_results + exec_results]
            self.gates.audit_log.extend(audit)
            return OrchestratorResult(
                request_id=contract.request_id,
                operation=contract.operation,
                allowed=False,
                verdict="block",
                issues=exec_issues,
                audit_log=audit,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        # Ejecutar inferencia
        try:
            evidence = executor()
            evidence_dict = evidence.model_dump() if hasattr(evidence, "model_dump") else vars(evidence)
        except Exception as exc:
            return OrchestratorResult(
                request_id=contract.request_id,
                operation=contract.operation,
                allowed=False,
                verdict="block",
                issues=[f"Execution error: {exc}"],
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        # Gate POST
        post_results = self.gates.gate_post(gate_input, evidence_dict)
        post_issues = [r.message for r in post_results if r.verdict.value == "block"]

        all_results = pre_results + exec_results + post_results
        all_audit = [r.to_dict() for r in all_results]
        self.gates.audit_log.extend(all_audit)
        all_issues = pre_issues + exec_issues + post_issues

        allowed = len(all_issues) == 0
        return OrchestratorResult(
            request_id=contract.request_id,
            operation=contract.operation,
            allowed=allowed,
            verdict="allow" if allowed else "block",
            issues=all_issues,
            audit_log=all_audit,
            evidence=evidence_dict,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
