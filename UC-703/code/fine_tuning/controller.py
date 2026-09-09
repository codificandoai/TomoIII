"""
UC-703 fine_tuning — FineTuningController.

Orquesta el ciclo de vida completo de fine-tuning delegando la ejecución en los
adapters de UC-703 (Temporal, StackStorm, n8n, local) y respetando los gates de
aprobación.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.data_agents import (
    DataCurationAgent,
    DatasetVersionRegistry,
    LeakageAuditAgent,
)
from fine_tuning.evaluation_agents import AlignmentAgent, EvaluationAgent, PromotionGate
from fine_tuning.models_ft import (
    ClosedLoopCycle,
    CurationResult,
    DatasetVersion,
    Deployment,
    DriftReport,
    EvaluationReport,
    FeedbackItem,
    LeakageReport,
    ModelBundle,
    ResourcePlan,
    TrainingRunConfig,
)
from fine_tuning.serving_agents import (
    CanaryMonitor,
    DeploymentAgent,
    DriftHallucinationAgent,
    FeedbackLoopAgent,
)
from fine_tuning.privacy.models_privacy import PrivacyPipelineState as PrivacyState
from fine_tuning.privacy.privacy_controller import PrivacyPreservingLLMOpsController
from fine_tuning.training_agents import (
    HyperparameterSearchAgent,
    ResourcePlannerAgent,
    TrainingSREAgent,
)


@dataclass
class FineTuningPipelineState:
    pipeline_id: str = field(default_factory=lambda: f"ftpipe-{uuid.uuid4().hex[:8]}")
    dataset_version: Optional[DatasetVersion] = None
    curation: Optional[CurationResult] = None
    leakage: Optional[LeakageReport] = None
    resource_plan: Optional[ResourcePlan] = None
    training_config: Optional[TrainingRunConfig] = None
    evaluation: Optional[EvaluationReport] = None
    bundle: Optional[ModelBundle] = None
    deployment: Optional[Deployment] = None
    drift: Optional[DriftReport] = None
    closed_loop: Optional[ClosedLoopCycle] = None
    privacy_state: Optional[PrivacyState] = None
    status: str = "pending"
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "dataset_version": self.dataset_version.to_dict() if self.dataset_version else None,
            "curation": self.curation.to_dict() if self.curation else None,
            "leakage": self.leakage.to_dict() if self.leakage else None,
            "resource_plan": self.resource_plan.to_dict() if self.resource_plan else None,
            "training_config": self.training_config.to_dict() if self.training_config else None,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "bundle": self.bundle.to_dict() if self.bundle else None,
            "deployment": self.deployment.to_dict() if self.deployment else None,
            "drift": self.drift.to_dict() if self.drift else None,
            "closed_loop": self.closed_loop.to_dict() if self.closed_loop else None,
            "privacy_state": self.privacy_state.to_dict() if self.privacy_state else None,
            "status": self.status,
            "logs": self.logs,
        }


class FineTuningController:
    """
    Controlador del ciclo de vida de fine-tuning sobre el runtime AGI UC-703.

    No entrena ni despliega él mismo; percibe, decide, coordina y aprende,
    delegando la ejecución a los adapters.
    """

    def __init__(
        self,
        curation_agent: Optional[DataCurationAgent] = None,
        leakage_agent: Optional[LeakageAuditAgent] = None,
        registry: Optional[DatasetVersionRegistry] = None,
        resource_planner: Optional[ResourcePlannerAgent] = None,
        training_sre: Optional[TrainingSREAgent] = None,
        hp_search: Optional[HyperparameterSearchAgent] = None,
        evaluator: Optional[EvaluationAgent] = None,
        promotion_gate: Optional[PromotionGate] = None,
        alignment: Optional[AlignmentAgent] = None,
        deployer: Optional[DeploymentAgent] = None,
        canary: Optional[CanaryMonitor] = None,
        drift_agent: Optional[DriftHallucinationAgent] = None,
        feedback_loop: Optional[FeedbackLoopAgent] = None,
        privacy_controller: Optional[PrivacyPreservingLLMOpsController] = None,
    ) -> None:
        self.curation = curation_agent or DataCurationAgent()
        self.leakage = leakage_agent or LeakageAuditAgent()
        self.registry = registry or DatasetVersionRegistry()
        self.resource_planner = resource_planner or ResourcePlannerAgent()
        self.training_sre = training_sre or TrainingSREAgent()
        self.hp_search = hp_search or HyperparameterSearchAgent()
        self.evaluator = evaluator or EvaluationAgent()
        self.promotion = promotion_gate or PromotionGate()
        self.alignment = alignment or AlignmentAgent()
        self.deployer = deployer or DeploymentAgent()
        self.canary = canary or CanaryMonitor()
        self.drift_agent = drift_agent or DriftHallucinationAgent()
        self.feedback_loop = feedback_loop or FeedbackLoopAgent()
        self.privacy = privacy_controller
        self._pipelines: Dict[str, FineTuningPipelineState] = {}

    # ------------------------------------------------------------------
    # 1. Gestión y calidad de datos
    # ------------------------------------------------------------------
    def curate_and_register(
        self,
        dataset_id: str,
        raw_samples: List[Dict[str, Any]],
        prompt_template: str,
        seed: int = 42,
        train_eval_samples: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        privacy_contract: Optional[Any] = None,
        apply_deidentification: bool = False,
        deid_text_fields: Optional[List[str]] = None,
    ) -> FineTuningPipelineState:
        state = FineTuningPipelineState(status="curating")
        self._pipelines[state.pipeline_id] = state

        # Privacy by Design: si se provee un privacy controller, se ejecuta primero.
        if self.privacy is not None and privacy_contract is not None:
            pstate = self.privacy.apply_data_contract(raw_samples, privacy_contract)
            if pstate.status == "contract_violation":
                state.privacy_state = pstate
                state.status = "blocked_privacy_contract"
                state.logs.append(f"Privacy contract violation: {pstate.contract.contract_id}")
                return state
            if apply_deidentification:
                deid_result = self.privacy.deidentify_samples(
                    pstate.pipeline_id, raw_samples, text_fields=deid_text_fields
                )
                state.logs.append(
                    f"De-identified {deid_result['samples_count'] if 'samples_count' in deid_result else len(raw_samples)} "
                    f"samples, findings={deid_result.get('findings_count', 0)}"
                )
            state.privacy_state = pstate

        # Curación
        samples_to_curate = raw_samples
        if self.privacy is not None and apply_deidentification and state.privacy_state:
            deid_result = self.privacy.deidentify_samples(
                state.privacy_state.pipeline_id, raw_samples, text_fields=deid_text_fields
            )
            samples_to_curate = deid_result.get("samples", raw_samples)
        curation = self.curation.curate(samples_to_curate, dataset_id=dataset_id)
        state.curation = curation
        state.logs.append(f"Curated {curation.cleaned_samples} samples, removed {curation.duplicates_removed} duplicates")

        # Versionado atómico
        splits = {"train": curation.output_uri + "/train", "eval": curation.output_uri + "/eval"}
        dataset_version = self.registry.register(
            dataset_id=dataset_id,
            prompt_template=prompt_template,
            seed=seed,
            splits=splits,
            num_samples=curation.cleaned_samples,
            version="v1",
        )
        state.dataset_version = dataset_version
        state.logs.append(f"Registered dataset version {dataset_version.version} with hash {dataset_version.audit_hash}")

        # Auditoría de leakage
        if train_eval_samples:
            leakage = self.leakage.audit(
                train_eval_samples.get("train", []),
                train_eval_samples.get("eval", []),
                dataset_id=dataset_id,
            )
            state.leakage = leakage
            state.logs.append(f"Leakage audit passed={leakage.passed} ngram={leakage.ngram_overlap_score:.3f}")
            if not leakage.passed:
                state.status = "blocked_leakage"
                return state

        state.status = "curated"
        return state

    # ------------------------------------------------------------------
    # 2. Computación e infraestructura
    # ------------------------------------------------------------------
    def plan_resources(
        self,
        pipeline_id: str,
        model_size_b: float,
        budget_usd: float,
        deadline_hours: float,
        prefer_reliability: bool = False,
    ) -> FineTuningPipelineState:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.dataset_version:
            raise ValueError("Pipeline not found or dataset not curated")
        plan = self.resource_planner.plan(
            model_size_b=model_size_b,
            dataset_samples=state.dataset_version.num_samples,
            budget_usd=budget_usd,
            deadline_hours=deadline_hours,
            prefer_reliability=prefer_reliability,
        )
        state.resource_plan = plan
        state.logs.append(f"Resource plan: {plan.strategy} on {plan.instance_type}, spot={plan.use_spot}")
        return state

    # ------------------------------------------------------------------
    # 3. HP search + entrenamiento simulado
    # ------------------------------------------------------------------
    def run_hp_search(self, pipeline_id: str) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state:
            raise ValueError("Pipeline not found")
        trials = self.hp_search.suggest_trials()
        # Simular evaluación de trials determinística.
        for t in trials:
            import random
            random.seed(t.trial_id)
            loss = random.uniform(0.4, 1.5)
            spike = loss > 1.2
            self.hp_search.report_trial_result(t.trial_id, loss, spike)
        best = self.hp_search.best_trial()
        state.logs.append(f"HP search best trial: {best.trial_id if best else 'none'}")
        return {"trials": len(trials), "best": best.to_dict() if best else None}

    def create_training_config(
        self,
        pipeline_id: str,
        base_model: str,
        hyperparams: Optional[Dict[str, Any]] = None,
        dp_config: Optional[Any] = None,
    ) -> FineTuningPipelineState:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.resource_plan:
            raise ValueError("Pipeline or resource plan missing")
        config = TrainingRunConfig(
            dataset_id=state.dataset_version.dataset_id if state.dataset_version else "",
            base_model=base_model,
            resource_plan=state.resource_plan,
            hyperparams=hyperparams or {"learning_rate": 5e-5, "batch_size": 8, "lora_r": 16},
        )
        state.training_config = config
        self.training_sre.register_job(config)

        if self.privacy is not None and dp_config is not None:
            pstate = self.privacy.configure_dp_training(
                state.privacy_state.pipeline_id if state.privacy_state else self.privacy._new_state().pipeline_id,
                dp_config,
            )
            if not state.privacy_state:
                state.privacy_state = pstate
            state.logs.append(f"DP training configured: eps={dp_config.epsilon}, delta={dp_config.delta}")

        state.logs.append(f"Training config created: {config.run_id}")
        return state

    def simulate_training_step(
        self,
        pipeline_id: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.training_config:
            raise ValueError("Pipeline or training config missing")
        self.training_sre.emit_metric(state.training_config.run_id, metrics)
        diag = self.training_sre.diagnose(state.training_config.run_id)
        if diag["action"] != "continue":
            self.training_sre.apply_recovery(state.training_config.run_id)
        state.logs.append(f"Training step: action={diag['action']}, reason={diag['reason']}")
        return diag

    # ------------------------------------------------------------------
    # 4. Evaluación y alineación
    # ------------------------------------------------------------------
    def evaluate(
        self,
        pipeline_id: str,
        domain_results: List[Dict[str, Any]],
        general_results: List[Dict[str, Any]],
        baseline_general_score: float = 0.80,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.training_config:
            raise ValueError("Pipeline or training config missing")
        report = self.evaluator.evaluate(
            run_id=state.training_config.run_id,
            domain_results=domain_results,
            general_results=general_results,
            baseline_general_score=baseline_general_score,
        )
        state.evaluation = report
        decision = self.promotion.decide(report)
        state.logs.append(f"Evaluation domain={report.domain_score}, forgetting={report.catastrophic_forgetting_score}, passed={decision['passed']}")
        if not decision["passed"]:
            state.status = "blocked_evaluation"
        return decision

    def recommend_alignment(
        self,
        pipeline_id: str,
        domain: str,
        risk_profile: str,
        has_human_preferences: bool,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.dataset_version:
            raise ValueError("Pipeline or dataset missing")
        rec = self.alignment.recommend(
            domain=domain,
            risk_profile=risk_profile,
            dataset_size=state.dataset_version.num_samples,
            has_human_preferences=has_human_preferences,
        )
        state.logs.append(f"Alignment recommendation: {rec['recommended_method']}")
        return rec

    # ------------------------------------------------------------------
    # 5. Despliegue y servicio
    # ------------------------------------------------------------------
    def build_and_deploy_canary(
        self,
        pipeline_id: str,
        adapter_uri: str,
        generation_params: Dict[str, Any],
        traffic_percent: float = 10.0,
        serving_mode: str = "lora_fused",
        enforce_network_policy: bool = False,
    ) -> FineTuningPipelineState:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.training_config or not state.dataset_version:
            raise ValueError("Pipeline missing training or dataset")

        if self.privacy is not None and enforce_network_policy:
            if state.privacy_state is None:
                state.privacy_state = self.privacy.create_pipeline()
            policy_result = self.privacy.enforce_network_policy(state.privacy_state.pipeline_id)
            if not policy_result["passed"]:
                state.status = "blocked_network_policy"
                state.logs.append(f"Network policy failed: {policy_result['findings']}")
                return state

        bundle = self.deployer.build_bundle(
            base_model=state.training_config.base_model,
            adapter_uri=adapter_uri,
            prompt_template=state.dataset_version.prompt_template,
            generation_params=generation_params,
            dataset_version_id=state.dataset_version.dataset_id,
            training_run_id=state.training_config.run_id,
        )
        state.bundle = bundle
        deployment = self.deployer.deploy_canary(
            bundle=bundle,
            traffic_percent=traffic_percent,
            serving_mode=serving_mode,
        )
        state.deployment = deployment
        state.status = "canary"
        state.logs.append(f"Deployed canary {deployment.deployment_id} with {traffic_percent}% traffic")
        return state

    # ------------------------------------------------------------------
    # 5.1 Privacy-preserving controls
    # ------------------------------------------------------------------
    def configure_privacy_dp(self, pipeline_id: str, dp_config: Any) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None:
            raise ValueError("pipeline or privacy controller missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        pstate = self.privacy.configure_dp_training(state.privacy_state.pipeline_id, dp_config)
        state.privacy_state = pstate
        state.logs.append(f"DP configured: eps={dp_config.epsilon}, delta={dp_config.delta}")
        return pstate.dp_config.to_dict() if pstate.dp_config else {}

    def apply_dp_to_training(self, pipeline_id: str, dataset_size: int, steps: int) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None or not state.training_config:
            raise ValueError("pipeline, privacy controller or training config missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        result = self.privacy.apply_dp_to_training(
            state.privacy_state.pipeline_id,
            state.training_config.run_id,
            dataset_size,
            steps,
        )
        if state.privacy_state.dp_result and state.privacy_state.dp_result.privacy_budget_exceeded:
            state.status = "blocked_dp_budget"
        state.logs.append(f"DP result: epsilon_spent={result.get('epsilon_spent')}")
        return result

    def validate_membership_inference_privacy(
        self,
        pipeline_id: str,
        members: List[Dict[str, Any]],
        non_members: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None or not state.training_config:
            raise ValueError("pipeline, privacy controller or training config missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        report = self.privacy.validate_membership_inference(
            state.privacy_state.pipeline_id,
            state.training_config.run_id,
            members,
            non_members,
        )
        if state.privacy_state.mi_report and not state.privacy_state.mi_report.passed:
            state.status = "blocked_membership_inference"
        state.logs.append(f"MI validation: risk={report.get('exposure_risk')}, passed={report.get('passed')}")
        return report

    def enforce_network_policy_privacy(self, pipeline_id: str, policy: Optional[Any] = None) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None:
            raise ValueError("pipeline or privacy controller missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        result = self.privacy.enforce_network_policy(state.privacy_state.pipeline_id, policy)
        if not result["passed"]:
            state.status = "blocked_network_policy"
        state.logs.append(f"Network policy: passed={result['passed']}")
        return result

    def preflight_inference_privacy(self, pipeline_id: str, request_id: str, prompt: str) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None:
            raise ValueError("pipeline or privacy controller missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        return self.privacy.preflight_inference(state.privacy_state.pipeline_id, request_id, prompt)

    def postflight_inference_privacy(
        self,
        pipeline_id: str,
        request_id: str,
        prompt: str,
        output: str,
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or self.privacy is None:
            raise ValueError("pipeline or privacy controller missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        return self.privacy.postflight_inference(state.privacy_state.pipeline_id, request_id, prompt, output)

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
        if not state or self.privacy is None:
            raise ValueError("pipeline or privacy controller missing")
        if state.privacy_state is None:
            state.privacy_state = self.privacy.create_pipeline()
        model_card = self.privacy.generate_model_card(
            state.privacy_state.pipeline_id,
            model_name,
            intended_use,
            privacy_controls,
            limitations,
            compliance_frameworks,
        )
        data_sheet = self.privacy.generate_data_sheet(
            state.privacy_state.pipeline_id,
            state.dataset_version.dataset_id if state.dataset_version else "",
            data_source,
            sensitive_attributes,
            anonymization_method,
            retention_hours,
            purpose,
        )
        return {"model_card": model_card, "data_sheet": data_sheet}

    def assess_canary(self, pipeline_id: str, canary_metrics: Dict[str, float], baseline_metrics: Dict[str, float]) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.deployment:
            raise ValueError("Pipeline or deployment missing")
        assessment = self.canary.assess(canary_metrics, baseline_metrics)
        if assessment["passed"]:
            self.deployer.promote(state.deployment.deployment_id)
            state.status = "stable"
        else:
            self.deployer.rollback(state.deployment.deployment_id)
            state.status = "rolled_back"
        state.logs.append(f"Canary assessment: {assessment}")
        return assessment

    # ------------------------------------------------------------------
    # 6. Observabilidad y cierre del ciclo
    # ------------------------------------------------------------------
    def detect_drift(
        self,
        pipeline_id: str,
        recent_inputs: List[str],
        recent_outputs: List[str],
        reference_contexts: List[str],
    ) -> Dict[str, Any]:
        state = self._pipelines.get(pipeline_id)
        if not state or not state.deployment:
            raise ValueError("Pipeline or deployment missing")
        drift = self.drift_agent.analyze(
            deployment_id=state.deployment.deployment_id,
            recent_inputs=recent_inputs,
            recent_outputs=recent_outputs,
            reference_contexts=reference_contexts,
        )
        state.drift = drift
        if drift.threshold_violated:
            cycle = self.feedback_loop.trigger_from_drift(state.deployment.deployment_id, drift)
            state.closed_loop = cycle
            state.status = "retrain_scheduled"
            state.logs.append(f"Drift detected; closed-loop cycle {cycle.cycle_id} created")
        return drift.to_dict()

    def ingest_feedback(self, pipeline_id: str, item: FeedbackItem) -> Dict[str, Any]:
        self.feedback_loop.ingest(item)
        cycle = self.feedback_loop.should_trigger_retrain(item.deployment_id)
        state = self._pipelines.get(pipeline_id)
        if state and cycle:
            state.closed_loop = cycle
            state.status = "retrain_scheduled"
            state.logs.append(f"Feedback triggered closed-loop cycle {cycle.cycle_id}")
        return {"feedback_ingested": True, "cycle": cycle.to_dict() if cycle else None}

    def approve_retrain_cycle(self, cycle_id: str) -> Optional[ClosedLoopCycle]:
        return self.feedback_loop.approve_cycle(cycle_id)

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_pipeline(self, pipeline_id: str) -> Optional[FineTuningPipelineState]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self, status: Optional[str] = None) -> List[FineTuningPipelineState]:
        pipelines = list(self._pipelines.values())
        if status:
            pipelines = [p for p in pipelines if p.status == status]
        return pipelines
