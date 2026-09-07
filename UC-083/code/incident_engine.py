"""
UC-083 — Motor de Respuesta a Incidentes de Inferencia Batch.

Orquesta el ciclo completo: detección, delimitación de impacto,
diagnóstico de causa raíz, mitigación segura, reprocesamiento y
postmortem con mejoras permanentes.
"""

import time
import os
from typing import Dict, List, Optional, Any

from incident_models import (
    Incident, IncidentSeverity, IncidentStatus, RootCause, RootCauseCategory,
    Mitigation, MitigationType, LogEntry, MetricSnapshot, ValidationReport,
    Postmortem, IncidentResponseConfig, IncidentResponseResult,
)
from log_analyzer import LogAnalyzer
from metrics_analyzer import MetricsAnalyzer
from data_validator import DataValidator
from checkpoint_manager import CheckpointManager
from reprocessor import Reprocessor
from alert_manager import AlertManager
from runbook_manager import RunbookManager
from ansible_generator import AnsibleGenerator
from monitoring_generator import MonitoringGenerator
from observability_083 import ObservabilityManager


class IncidentResponseEngine:
    """
    Motor principal de UC-083. Expone:
    - declare_incident(...)
    - triage()
    - diagnose()
    - mitigate()
    - reprocess()
    - generate_postmortem()
    """

    def __init__(
        self,
        pipeline_id: str,
        config: Optional[IncidentResponseConfig] = None,
        alert_manager: Optional[AlertManager] = None,
        runbook_manager: Optional[RunbookManager] = None,
        observability: Optional[ObservabilityManager] = None,
    ):
        self.pipeline_id = pipeline_id
        self.config = config or IncidentResponseConfig()
        self.log_analyzer = LogAnalyzer()
        self.metrics_analyzer = MetricsAnalyzer()
        self.data_validator = DataValidator(config=self.config)
        self.checkpoint_manager = CheckpointManager(pipeline_id=pipeline_id)
        self.reprocessor = Reprocessor(pipeline_id=pipeline_id, config=self.config, checkpoint_manager=self.checkpoint_manager)
        self.alert_manager = alert_manager or AlertManager(runbook_base_url="https://wiki.trackprice.ai/runbooks")
        self.runbook_manager = runbook_manager or RunbookManager(base_url="https://wiki.trackprice.ai/runbooks")
        self.observability = observability or ObservabilityManager()
        self.ansible_generator = AnsibleGenerator(hosts="batch_workers")
        self.monitoring_generator = MonitoringGenerator(config=self.config)
        self.incident: Optional[Incident] = None

    def declare_incident(
        self,
        title: str,
        description: str,
        severity: str = "P1",
        affected_partitions: Optional[List[str]] = None,
    ) -> Incident:
        self.incident = Incident(
            title=title,
            description=description,
            severity=IncidentSeverity(severity),
            status=IncidentStatus.TRIAGING,
            affected_partitions=affected_partitions or [],
        )
        self.observability.log(
            "CRITICAL",
            f"Incident declared: {title}",
            trace_id=self.incident.incident_id,
        )
        self.alert_manager.send(
            severity=severity,
            title=f"Incident declared: {title}",
            message=description,
            runbook_name="out_of_memory",
            metadata={"incident_id": self.incident.incident_id},
        )
        return self.incident

    def ingest_logs(self, raw_logs: str, source: str = "orchestrator") -> None:
        entries = self.log_analyzer.parse_raw_log(raw_logs, source=source)
        if self.incident:
            self.incident.logs.extend(entries)
        self.observability.log("INFO", f"Ingested {len(entries)} logs from {source}")

    def ingest_metrics(self, metrics: List[MetricSnapshot]) -> None:
        for m in metrics:
            self.metrics_analyzer.add(m)
        if self.incident:
            self.incident.metrics.extend(metrics)
        self.observability.log("INFO", f"Ingested {len(metrics)} metrics")

    def validate_data(
        self,
        file_path: str,
        expected_columns: Optional[List[str]] = None,
        historical_counts: Optional[List[int]] = None,
    ) -> List[ValidationReport]:
        reports = self.data_validator.validate(file_path, expected_columns=expected_columns)
        if historical_counts is not None:
            total_rows = self.data_validator._count_rows(file_path)
            reports.append(self.data_validator.baseline_comparison(total_rows, historical_counts))
        if self.incident:
            self.incident.validation_reports.extend(reports)
        return reports

    def triage(self) -> Dict[str, Any]:
        if not self.incident:
            raise ValueError("No incident declared")
        self.incident.status = IncidentStatus.MITIGATING
        impact = self._delimit_impact()
        return impact

    def _delimit_impact(self) -> Dict[str, Any]:
        if not self.incident:
            return {}
        return {
            "incident_id": self.incident.incident_id,
            "affected_partitions": self.incident.affected_partitions,
            "total_logs": len(self.incident.logs),
            "error_logs": sum(1 for l in self.incident.logs if l.level in ("ERROR", "CRITICAL", "FATAL")),
            "resource_findings": self.metrics_analyzer.diagnose_resource_pressure(
                memory_threshold=self.config.memory_threshold,
                cpu_threshold=self.config.cpu_threshold,
                duration_minutes=self.config.duration_threshold_minutes,
            ),
            "error_patterns": self.log_analyzer.find_error_patterns(),
        }

    def diagnose(self) -> List[RootCause]:
        if not self.incident:
            raise ValueError("No incident declared")
        root_causes = []

        patterns = self.log_analyzer.find_error_patterns()
        resource_findings = self.metrics_analyzer.diagnose_resource_pressure(
            memory_threshold=self.config.memory_threshold,
            cpu_threshold=self.config.cpu_threshold,
            duration_minutes=self.config.duration_threshold_minutes,
        )
        volume_anomaly = any(r.check_name in ("volume", "baseline_volume") and not r.passed for r in self.incident.validation_reports)
        schema_anomaly = any(r.check_name == "schema" and not r.passed for r in self.incident.validation_reports)
        completeness_anomaly = any(r.check_name == "completeness" and not r.passed for r in self.incident.validation_reports)

        if patterns.get("oom", 0) > 0 or any(f["type"] == "memory_pressure" for f in resource_findings):
            root_causes.append(RootCause(
                category=RootCauseCategory.OOM,
                confidence=0.9,
                description="Workers terminados por falta de memoria o presión de memoria sostenida.",
                evidence=[{"logs": patterns.get("oom", 0), "resource_findings": resource_findings}],
                recommended_mitigations=[
                    MitigationType.STOP_RETRIES,
                    MitigationType.CHUNKING,
                    MitigationType.DISTRIBUTED,
                    MitigationType.SCALE_UP,
                ],
            ))

        if patterns.get("timeout", 0) > 0 or any(f["type"] == "duration_exceeded" for f in resource_findings):
            root_causes.append(RootCause(
                category=RootCauseCategory.TIMEOUT,
                confidence=0.85,
                description="El job excedió la duración esperada.",
                evidence=[{"logs": patterns.get("timeout", 0), "resource_findings": resource_findings}],
                recommended_mitigations=[
                    MitigationType.CHUNKING,
                    MitigationType.DISTRIBUTED,
                    MitigationType.SCALE_UP,
                ],
            ))

        if volume_anomaly:
            root_causes.append(RootCause(
                category=RootCauseCategory.DATA_VOLUME,
                confidence=0.9,
                description="Volumen de entrada anómalo respecto al baseline o excede límite permitido.",
                evidence=[{"validation_reports": [r.to_dict() for r in self.incident.validation_reports if r.check_name in ("volume", "baseline_volume")]}],
                recommended_mitigations=[
                    MitigationType.STOP_RETRIES,
                    MitigationType.CHUNKING,
                    MitigationType.DISTRIBUTED,
                    MitigationType.FAIL_FAST,
                ],
            ))

        if schema_anomaly:
            root_causes.append(RootCause(
                category=RootCauseCategory.SCHEMA_DRIFT,
                confidence=0.9,
                description="El esquema de entrada no coincide con el esperado.",
                evidence=[{"validation_reports": [r.to_dict() for r in self.incident.validation_reports if r.check_name == "schema"]}],
                recommended_mitigations=[
                    MitigationType.STOP_RETRIES,
                    MitigationType.FAIL_FAST,
                ],
            ))

        if patterns.get("worker_death", 0) > 0 and not root_causes:
            root_causes.append(RootCause(
                category=RootCauseCategory.INFRASTRUCTURE,
                confidence=0.7,
                description="Workers fallan sin patrón claro de OOM/timeout; posible infraestructura.",
                evidence=[{"logs": patterns.get("worker_death", 0)}],
                recommended_mitigations=[
                    MitigationType.ROLLBACK,
                    MitigationType.REPROCESS,
                ],
            ))

        if not root_causes:
            root_causes.append(RootCause(
                category=RootCauseCategory.UNKNOWN,
                confidence=0.5,
                description="No se identificó causa raíz con confianza suficiente.",
                evidence=[{"patterns": patterns, "resource_findings": resource_findings}],
                recommended_mitigations=[MitigationType.STOP_RETRIES],
            ))

        self.incident.root_causes = root_causes
        return root_causes

    def mitigate(self) -> List[Mitigation]:
        if not self.incident:
            raise ValueError("No incident declared")
        mitigations = []
        categories = [rc.category for rc in self.incident.root_causes]

        # Stop retries first always
        mitigations.append(self._apply_mitigation(
            MitigationType.STOP_RETRIES,
            "Detener reintentos automáticos para evitar consumo adicional y duplicación.",
        ))

        if RootCauseCategory.OOM in categories or RootCauseCategory.DATA_VOLUME in categories:
            mitigations.append(self._apply_mitigation(
                MitigationType.CHUNKING,
                f"Dividir lote en chunks de {self.config.chunk_size_rows} filas.",
            ))
            mitigations.append(self._apply_mitigation(
                MitigationType.DISTRIBUTED,
                f"Procesar chunks con concurrencia controlada (max {self.config.max_concurrency}).",
            ))

        if RootCauseCategory.OOM in categories or RootCauseCategory.TIMEOUT in categories:
            mitigations.append(self._apply_mitigation(
                MitigationType.SCALE_UP,
                "Escalar temporalmente memoria/CPU de workers.",
            ))

        if RootCauseCategory.SCHEMA_DRIFT in categories:
            mitigations.append(self._apply_mitigation(
                MitigationType.FAIL_FAST,
                "Rechazar lote por schema drift y notificar Data Engineering.",
            ))

        if RootCauseCategory.INFRASTRUCTURE in categories:
            mitigations.append(self._apply_mitigation(
                MitigationType.ROLLBACK,
                "Rollback a workers sanos / reintentar en zona alternativa.",
            ))

        # Generate runbook
        primary = self.incident.root_causes[0].category
        runbook = self.runbook_manager.get(primary)
        self.incident.runbook_steps = runbook.get("diagnosis", []) + runbook.get("mitigation", [])

        # Generate alert
        self.alert_manager.send(
            severity=self.incident.severity.value,
            title=f"Mitigations applied for incident {self.incident.incident_id}",
            message=f"Root causes: {[rc.category.value for rc in self.incident.root_causes]}",
            runbook_name=primary.value,
            metadata={"mitigations": [m.mitigation_type.value for m in mitigations]},
        )

        self.incident.mitigations.extend(mitigations)
        return mitigations

    def _apply_mitigation(self, mitigation_type: MitigationType, description: str) -> Mitigation:
        return Mitigation(
            mitigation_type=mitigation_type,
            description=description,
            status="applied",
        )

    def reprocess(self, file_path: str) -> Dict[str, Any]:
        """Reprocesa particiones afectadas de forma segura."""
        if not self.incident:
            raise ValueError("No incident declared")
        result = self.reprocessor.reprocess(file_path)
        self.incident.checkpoints = self.reprocessor.checkpoint_manager.all_checkpoints()
        self.incident.status = IncidentStatus.RECOVERING
        return result

    def generate_postmortem(self) -> Postmortem:
        if not self.incident:
            raise ValueError("No incident declared")
        self.incident.status = IncidentStatus.POSTMORTEM
        self.incident.resolved_time = time.time()

        categories = [rc.category for rc in self.incident.root_causes]
        improvements = set()
        runbook_updates = []
        monitoring_updates = []
        ansible_updates = []

        for cat in categories:
            improvements.update(self.runbook_manager.generate_postmortem_improvements(cat))
            runbook_updates.append(f"Actualizar runbook {cat.value} con lecciones del incidente {self.incident.incident_id}")

        monitoring_updates.append("Agregar alertas predictivas de presión de memoria y duración del job.")
        monitoring_updates.append("Configurar alerta de volumen de entrada vs baseline P95.")
        ansible_updates.append(f"Generar playbook de remediación para causa(s) {[c.value for c in categories]}")
        ansible_updates.append("Automatizar escalamiento de workers y chunking distribuido.")

        # Generate monitoring config and ansible playbook
        monitoring_config = self.monitoring_generator.generate_all(self.pipeline_id)
        primary = categories[0] if categories else RootCauseCategory.UNKNOWN
        ansible_playbook = self.ansible_generator.generate(primary, self.pipeline_id, scale_memory_gb=8, scale_workers=6)

        postmortem = Postmortem(
            incident_id=self.incident.incident_id,
            summary=f"Incidente {self.incident.title} causado por {[c.value for c in categories]}. Recuperación mediante mitigaciones seguras y reprocesamiento con checkpoints.",
            root_cause_summary="; ".join(rc.description for rc in self.incident.root_causes),
            timeline=self._build_timeline(),
            improvements=list(improvements),
            runbook_updates=runbook_updates,
            monitoring_updates=monitoring_updates,
            ansible_updates=ansible_updates,
        )

        # Update runbook with learned improvements
        for cat in categories:
            for item in postmortem.improvements:
                self.runbook_manager.update_runbook(cat, "prevention", item)

        self.incident.postmortem = postmortem.to_dict()
        return postmortem

    def _build_timeline(self) -> List[Dict[str, Any]]:
        if not self.incident:
            return []
        return [
            {"time": self.incident.start_time, "event": "Incident declared", "status": "detected"},
            {"time": None, "event": "Triage completed", "status": "triaging"},
            {"time": None, "event": "Root cause diagnosed", "status": "mitigating"},
            {"time": None, "event": "Mitigations applied", "status": "mitigating"},
            {"time": self.incident.resolved_time, "event": "Resolved", "status": "resolved"},
        ]

    def run_full_response(
        self,
        title: str,
        description: str,
        severity: str,
        raw_logs: str,
        metrics: List[MetricSnapshot],
        file_path: str,
        expected_columns: Optional[List[str]] = None,
        historical_counts: Optional[List[int]] = None,
        affected_partitions: Optional[List[str]] = None,
    ) -> IncidentResponseResult:
        """Ejecuta el ciclo completo de respuesta a incidente."""
        start = time.time()
        self.declare_incident(title, description, severity, affected_partitions)
        self.ingest_logs(raw_logs, source="orchestrator")
        self.ingest_metrics(metrics)
        self.validate_data(file_path, expected_columns, historical_counts)
        self.triage()
        self.diagnose()
        self.mitigate()
        reprocess_result = self.reprocess(file_path)
        postmortem = self.generate_postmortem()
        duration = (time.time() - start) * 1000

        return IncidentResponseResult(
            incident=self.incident,
            postmortem=postmortem,
            runbook=self.runbook_manager.get(self.incident.root_causes[0].category),
            ansible_playbook=self.ansible_generator.generate(
                self.incident.root_causes[0].category,
                self.pipeline_id,
                scale_memory_gb=8,
                scale_workers=6,
            ),
            monitoring_config=self.monitoring_generator.generate_all(self.pipeline_id),
            duration_ms=duration,
        )

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "incident_id": self.incident.incident_id if self.incident else None,
            "status": self.incident.status.value if self.incident else None,
            "log_summary": self.log_analyzer.summarize(),
            "metric_summary": self.metrics_analyzer.summary(),
            "checkpoint_stats": self.checkpoint_manager.get_statistics(),
            "alert_stats": self.alert_manager.get_statistics(),
            "observability_summary": self.observability.get_summary(),
        }

    def reset(self) -> None:
        self.log_analyzer.reset()
        self.metrics_analyzer.reset()
        self.checkpoint_manager.reset()
        self.reprocessor.reset()
        self.alert_manager.reset()
        self.observability.reset()
        self.incident = None
