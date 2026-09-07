"""
UC-087 — Guardian de seguridad ML (MLSecOps / Defense in Depth).

Orquesta validación de provenance, filtrado de entradas, entrenamiento en
sandbox, evaluación de robustez, detección de backdoors, promoción/rollback
de modelos y escalación de alertas.
"""

import copy
import time
from typing import List, Dict, Any, Optional, Callable

from models_087 import (
    MLSecOpsConfig,
    DataPoint,
    SecurityDecision,
    DefenseAction,
    ModelPromotion,
    ThreatCategory,
    RobustnessReport,
    TriggerReport,
    ValidationReport,
    MLSecOpsResult,
)
from data_signing import DataSigning
from provenance_validator import ProvenanceValidator
from input_filter import InputFilter
from adversarial_generator import AdversarialGenerator
from sandbox_model import SandboxLogisticModel
from sandbox_trainer import SandboxTrainer
from robustness_evaluator import RobustnessEvaluator
from trigger_detector import TriggerDetector
from rollback_manager import RollbackManager
from alert_manager_087 import AlertManager087
from observability_087 import ObservabilityManager


class ModelSecurityGuardian:
    """
    Guardian externo que protege los modelos de UC-315 antes de aceptar
nuevos datos o promocionar un modelo reentrenado.
    """

    def __init__(
        self,
        config: Optional[MLSecOpsConfig] = None,
        rollback_manager: Optional[RollbackManager] = None,
        alert_manager: Optional[AlertManager087] = None,
    ):
        self.config = config or MLSecOpsConfig()
        self.signing = DataSigning()
        self.provenance_validator = ProvenanceValidator(self.signing)
        self.input_filter = InputFilter(
            outlier_threshold=self.config.outlier_threshold,
            squeeze_epsilon=self.config.feature_squeeze_epsilon,
        )
        self.adversarial_generator = AdversarialGenerator(
            epsilon=self.config.adversarial_epsilon,
            steps=self.config.adversarial_steps,
        )
        self.sandbox_trainer = SandboxTrainer(
            config=self.config,
            adversarial_generator=self.adversarial_generator,
            base_model=SandboxLogisticModel(),
        )
        self.robustness_evaluator = RobustnessEvaluator(
            generator=self.adversarial_generator,
            robustness_gap_threshold=self.config.robustness_gap_threshold,
        )
        self.trigger_detector = TriggerDetector(
            slice_drop_threshold=self.config.slice_drop_threshold,
            entropy_zscore=self.config.entropy_anomaly_zscore,
        )
        self.rollback_manager = rollback_manager or RollbackManager()
        self.alert_manager = alert_manager or AlertManager087()
        self.observability = ObservabilityManager()

    def validate_and_sanitize(
        self,
        data: List[DataPoint],
        expected_hash: Optional[str] = None,
        signature_envelope: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Valida provenance, filtra outliers y aplica feature squeezing."""
        report, _ = self._validate_and_clean(
            data, expected_hash, signature_envelope, source, allowed_sources
        )
        return report

    def _sanitize_data(self, data: List[DataPoint]) -> List[DataPoint]:
        """Aplica filtros de outliers y squeezing y retorna datos limpios."""
        clean, _ = self.input_filter.filter_outliers(data)
        if not clean:
            return []
        dummy_model = SandboxLogisticModel(dim=len(clean[0].features))
        dummy_model.fit(clean)
        clean, _, _ = self.input_filter.detect_squeezing_changes(clean, dummy_model.predict)
        return clean

    def _validate_and_clean(
        self,
        data: List[DataPoint],
        expected_hash: Optional[str] = None,
        signature_envelope: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
    ):
        """Valida provenance y retorna reporte + datos sanitizados."""
        # 1. Provenance
        report = self.provenance_validator.validate_batch(
            data, expected_hash, signature_envelope, source, allowed_sources
        )
        if not report.all_passed:
            return report, []

        # 2. Outlier filtering
        clean, dropped = self.input_filter.filter_outliers(data)
        report.outlier_dropped = dropped
        if not clean:
            report.all_passed = False
            report.provenance_checks.append(self._check("filtering", False, "Todos los puntos fueron eliminados como outliers"))
            return report, []

        # 3. Feature squeezing
        dummy_model = SandboxLogisticModel(dim=len(clean[0].features))
        dummy_model.fit(clean)
        _, squeezed_count, details = self.input_filter.detect_squeezing_changes(
            clean, dummy_model.predict
        )
        report.squeezed_differences = squeezed_count
        clean, _, _ = self.input_filter.detect_squeezing_changes(clean, dummy_model.predict)
        report.all_passed = True
        return report, clean

    def _check(self, name: str, passed: bool, message: str):
        from models_087 import ProvenanceCheck
        return ProvenanceCheck(check_name=name, passed=passed, message=message)

    def train_candidate(
        self,
        clean_data: List[DataPoint],
        attack: str = "pgd",
    ) -> SandboxLogisticModel:
        """Entrena un modelo candidato en sandbox."""
        return self.sandbox_trainer.train(clean_data, adversarial_fraction=0.5, attack=attack)

    def evaluate_robustness(
        self,
        model: SandboxLogisticModel,
        clean_data: List[DataPoint],
        attacks: List[str] = None,
    ) -> RobustnessReport:
        """Red teaming: evalúa robustez con múltiples ataques."""
        attacks = attacks or ["fgsm", "pgd"]
        worst = None
        for attack in attacks:
            report = self.robustness_evaluator.evaluate(model, clean_data, attack=attack)
            if worst is None or report.robustness_gap > worst.robustness_gap:
                worst = report
        return worst

    def detect_backdoors(
        self,
        model: SandboxLogisticModel,
        data: List[DataPoint],
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> TriggerReport:
        """Ejecuta detección de triggers/backdoors."""
        baseline = baseline_metrics or {"entropy": 0.5, "trigger_slice_acc": 0.85}
        return self.trigger_detector.evaluate(model, data, baseline)

    def decide(
        self,
        validation_report: ValidationReport,
        robustness_report: RobustnessReport,
        trigger_report: TriggerReport,
        candidate_model: SandboxLogisticModel,
    ) -> SecurityDecision:
        """Toma decisión: allow, quarantine, rollback, escalate."""
        categories = []
        action = DefenseAction.ALLOW
        promotion = ModelPromotion.PROMOTE
        justification_parts = []

        if not validation_report.all_passed:
            categories.append(ThreatCategory.DATA_POISONING)
            categories.append(ThreatCategory.ARTIFACT_TAMPERING)
            action = DefenseAction.QUARANTINE
            promotion = ModelPromotion.REJECT
            justification_parts.append("Validación de provenance/integridad falló.")

        if not robustness_report.passed:
            categories.append(ThreatCategory.ADVERSARIAL_EXAMPLE)
            action = DefenseAction.ESCALATE if action != DefenseAction.QUARANTINE else action
            promotion = ModelPromotion.REJECT
            justification_parts.append(
                f"Brecha de robustez {robustness_report.robustness_gap:.2%} supera umbral."
            )

        if trigger_report.slice_alerts or trigger_report.entropy_alert:
            categories.append(ThreatCategory.BACKDOOR)
            action = DefenseAction.ESCALATE
            promotion = ModelPromotion.REJECT
            justification_parts.append("Detectado posible backdoor o anomalía de entropía.")

        if not categories:
            justification_parts.append("Todas las comprobaciones de seguridad pasaron.")

        categories = list(set(categories))

        # Serializar modelo de forma segura (modelos externos pueden no tener to_dict)
        if hasattr(candidate_model, "to_dict"):
            model_state = candidate_model.to_dict()
        else:
            model_state = {
                "type": getattr(candidate_model, "__class__", object).__name__,
                "module": getattr(getattr(candidate_model, "__class__", object), "__module__", "unknown"),
            }

        # Guardar candidato según decisión
        version = None
        if promotion == ModelPromotion.PROMOTE:
            version = self.rollback_manager.save_candidate(
                model_state,
                is_canary=True,
                metrics={
                    "clean_acc": robustness_report.clean_accuracy,
                    "adv_acc": robustness_report.adversarial_accuracy,
                    "robustness_gap": robustness_report.robustness_gap,
                },
            )
        else:
            version = self.rollback_manager.save_candidate(
                model_state,
                is_canary=False,
                metrics={
                    "clean_acc": robustness_report.clean_accuracy,
                    "adv_acc": robustness_report.adversarial_accuracy,
                    "robustness_gap": robustness_report.robustness_gap,
                },
            )
            self.rollback_manager.reject(version.version_id, "; ".join(justification_parts))

        # Métricas de observabilidad por categoría de amenaza
        for cat in categories:
            self.observability.increment(f"mlsecops_threat_{cat.value}_total")
        self.observability.gauge("mlsecops_last_robustness_gap", robustness_report.robustness_gap)
        self.observability.gauge("mlsecops_squeezed_differences_total", float(validation_report.squeezed_differences))
        if version:
            self.observability.increment("mlsecops_model_versions_total")
            if promotion == ModelPromotion.PROMOTE:
                self.observability.increment("mlsecops_model_versions_promoted")
                self.observability.increment("mlsecops_models_approved_total")
            elif promotion == ModelPromotion.REJECT:
                self.observability.increment("mlsecops_model_versions_rejected")
                self.observability.increment("mlsecops_models_rejected_total")
            if version.is_canary:
                self.observability.increment("mlsecops_model_versions_canary")

        return SecurityDecision(
            action=action,
            promotion=promotion,
            threat_categories=categories,
            justification=" ".join(justification_parts),
            validation_report=validation_report,
            robustness_report=robustness_report,
            trigger_report=trigger_report,
            model_version=version,
        )

    def approve_canary(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Promociona una versión canary a producción. Requiere aprobación humana."""
        version = self.rollback_manager.promote(version_id)
        if version:
            self.alert_manager.send(
                ThreatCategory.MODEL_MANIPULATION,
                "Modelo promocionado a producción",
                f"Versión {version_id} promocionada tras aprobación canary.",
                DefenseAction.ALLOW,
            )
        return version.to_dict() if version else None

    def rollback(self, version_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Revierte a versión segura conocida."""
        version = self.rollback_manager.rollback(version_id)
        if version:
            self.alert_manager.send(
                ThreatCategory.MODEL_MANIPULATION,
                "Rollback ejecutado",
                f"Revertido a versión {version.version_id}.",
                DefenseAction.ROLLBACK,
            )
        return version.to_dict() if version else None

    def process_training_batch(
        self,
        data: List[DataPoint],
        expected_hash: Optional[str] = None,
        signature_envelope: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> MLSecOpsResult:
        """Flujo completo de validación + entrenamiento + decisión."""
        start = time.time()

        # 1. Validar y sanitizar
        validation, cleaned_data = self._validate_and_clean(
            data, expected_hash, signature_envelope, source, allowed_sources
        )
        if not validation.all_passed:
            decision = SecurityDecision(
                action=DefenseAction.QUARANTINE,
                promotion=ModelPromotion.REJECT,
                threat_categories=[ThreatCategory.DATA_POISONING, ThreatCategory.ARTIFACT_TAMPERING],
                justification="Batch rechazado por falla en validación de provenance/integridad.",
                validation_report=validation,
            )
            self.alert_manager.send(
                ThreatCategory.DATA_POISONING,
                "Batch de entrenamiento rechazado",
                decision.justification,
                DefenseAction.QUARANTINE,
            )
            self.observability.increment("mlsecops_batches_rejected_total")
            self.observability.log("WARN", "Batch rechazado por validación", extra=decision.to_dict())
            return MLSecOpsResult(
                decision=decision,
                duration_ms=(time.time() - start) * 1000,
            )

        # 2. Entrenar candidato en sandbox con datos sanitizados
        candidate = self.train_candidate(cleaned_data)

        # 3. Evaluar robustez
        robustness = self.evaluate_robustness(candidate, cleaned_data)

        # 4. Detectar backdoors sobre el batch original (modelo no ha visto triggers)
        trigger = self.detect_backdoors(candidate, data, baseline_metrics)

        # 5. Decidir
        decision = self.decide(validation, robustness, trigger, candidate)

        # 6. Emitir alertas según decisión
        if decision.action != DefenseAction.ALLOW:
            self.alert_manager.send(
                decision.threat_categories[0] if decision.threat_categories else ThreatCategory.UNKNOWN,
                "MLSecOps guardian detectó amenaza",
                decision.justification,
                decision.action,
                metadata={
                    "promotion": decision.promotion.value,
                    "robustness_gap": robustness.robustness_gap,
                    "slice_alerts": [a.to_dict() for a in trigger.slice_alerts],
                },
            )
            self.observability.increment("mlsecops_batches_rejected_total")
            self.observability.log("WARN", "Amenaza detectada", extra=decision.to_dict())
        else:
            self.observability.increment("mlsecops_batches_approved_total")
            self.observability.log("INFO", "Batch aprobado", extra=decision.to_dict())

        duration = (time.time() - start) * 1000
        self.observability.gauge("mlsecops_guardian_duration_ms", duration)
        self.observability.increment("mlsecops_batches_processed_total")

        return MLSecOpsResult(
            decision=decision,
            alerts=self.alert_manager.list_alerts(),
            duration_ms=duration,
        )

    def evaluate_external_model(
        self,
        data: List[DataPoint],
        candidate_model: Any,
        expected_hash: Optional[str] = None,
        signature_envelope: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, float]] = None,
        model_source: str = "UC-315",
    ) -> MLSecOpsResult:
        """
        Valida un modelo externo (por ejemplo, NeuralTransitionModel o
GPTransitionModel de UC-315) antes de que sea aceptado como conocimiento
seguro. Ejecuta los mismos gates de datos y de modelo sin reentrenarlo.
        """
        start = time.time()

        validation, cleaned_data = self._validate_and_clean(
            data, expected_hash, signature_envelope, source, allowed_sources
        )
        if not validation.all_passed:
            decision = SecurityDecision(
                action=DefenseAction.QUARANTINE,
                promotion=ModelPromotion.REJECT,
                threat_categories=[ThreatCategory.DATA_POISONING, ThreatCategory.ARTIFACT_TAMPERING],
                justification="Batch rechazado por falla en validación de provenance/integridad.",
                validation_report=validation,
            )
            self.alert_manager.send(
                ThreatCategory.DATA_POISONING,
                "Batch de validación rechazado",
                decision.justification,
                DefenseAction.QUARANTINE,
            )
            return MLSecOpsResult(
                decision=decision,
                duration_ms=(time.time() - start) * 1000,
            )

        # Robustez y backdoors del modelo externo usando datos limpios y originales
        robustness = self.evaluate_robustness(candidate_model, cleaned_data)
        trigger = self.detect_backdoors(candidate_model, data, baseline_metrics)

        decision = self.decide(validation, robustness, trigger, candidate_model)
        decision.justification = (
            f"[External model {model_source}] " + decision.justification
        )

        if decision.action != DefenseAction.ALLOW:
            self.alert_manager.send(
                decision.threat_categories[0] if decision.threat_categories else ThreatCategory.UNKNOWN,
                f"Modelo externo {model_source} rechazado por seguridad",
                decision.justification,
                decision.action,
                metadata={
                    "model_source": model_source,
                    "robustness_gap": robustness.robustness_gap,
                    "slice_alerts": [a.to_dict() for a in trigger.slice_alerts],
                },
            )
            self.observability.increment("mlsecops_external_models_rejected_total")
            self.observability.log("WARN", f"Modelo externo {model_source} rechazado", extra=decision.to_dict())
        else:
            self.observability.increment("mlsecops_external_models_approved_total")
            self.observability.log("INFO", f"Modelo externo {model_source} aprobado", extra=decision.to_dict())

        duration = (time.time() - start) * 1000
        self.observability.gauge("mlsecops_last_external_robustness_gap", robustness.robustness_gap)
        self.observability.increment("mlsecops_external_models_evaluated_total")
        self.observability.gauge("mlsecops_guardian_duration_ms", duration)

        return MLSecOpsResult(
            decision=decision,
            alerts=self.alert_manager.list_alerts(),
            duration_ms=duration,
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "versions": self.rollback_manager.list_versions(),
            "alerts": self.alert_manager.get_statistics(),
            "promoted_version": self.rollback_manager.get_promoted().to_dict() if self.rollback_manager.get_promoted() else None,
        }
