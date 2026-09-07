"""
Codificando.AI
UC-083: Incident Response & Resilient Batch Inference — TrackPrice.ai.

Capa de respuesta a incidentes críticos de inferencia por lotes. Permite
diagnosticar, mitigar y aprender de fallas nocturnas en pipelines batch,
actualizando runbooks, playbooks Ansible y configuraciones de monitoreo.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

import csv
import os
import tempfile
from typing import List, Dict, Any, Optional

from incident_models import IncidentResponseConfig, MetricSnapshot, IncidentResponseResult
from incident_engine import IncidentResponseEngine


class UCIncidentResponseLayer:
    """Wrapper de alto nivel para UC-083."""

    def __init__(
        self,
        pipeline_id: str,
        config: Optional[IncidentResponseConfig] = None,
    ):
        self.engine = IncidentResponseEngine(
            pipeline_id=pipeline_id,
            config=config,
        )

    def declare(
        self,
        title: str,
        description: str,
        severity: str = "P1",
        affected_partitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        incident = self.engine.declare_incident(title, description, severity, affected_partitions)
        return incident.to_dict()

    def ingest_logs(self, raw_logs: str, source: str = "orchestrator") -> Dict[str, Any]:
        self.engine.ingest_logs(raw_logs, source=source)
        return {"ingested": len(self.engine.incident.logs) if self.engine.incident else 0}

    def ingest_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        snapshots = [
            MetricSnapshot(
                timestamp=m.get("timestamp") or __import__("time").time(),
                metric_name=m["metric_name"],
                value=m["value"],
                unit=m.get("unit", ""),
                source=m.get("source", ""),
            )
            for m in metrics
        ]
        self.engine.ingest_metrics(snapshots)
        return {"summary": self.engine.metrics_analyzer.summary()}

    def validate(self, file_path: str, expected_columns: Optional[List[str]] = None, historical_counts: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        reports = self.engine.validate_data(file_path, expected_columns, historical_counts)
        return [r.to_dict() for r in reports]

    def triage(self) -> Dict[str, Any]:
        return self.engine.triage()

    def diagnose(self) -> Dict[str, Any]:
        root_causes = self.engine.diagnose()
        return {"root_causes": [r.to_dict() for r in root_causes]}

    def mitigate(self) -> Dict[str, Any]:
        mitigations = self.engine.mitigate()
        return {
            "mitigations": [m.to_dict() for m in mitigations],
            "runbook_steps": self.engine.incident.runbook_steps,
        }

    def reprocess(self, file_path: str) -> Dict[str, Any]:
        return self.engine.reprocess(file_path)

    def postmortem(self) -> Dict[str, Any]:
        pm = self.engine.generate_postmortem()
        return {
            "postmortem": pm.to_dict(),
            "ansible_playbook": self.engine.ansible_generator.generate(
                self.engine.incident.root_causes[0].category,
                self.engine.pipeline_id,
                scale_memory_gb=8,
                scale_workers=6,
            ),
            "monitoring_config": self.engine.monitoring_generator.generate_all(self.engine.pipeline_id),
        }

    def full_response(
        self,
        title: str,
        description: str,
        severity: str,
        raw_logs: str,
        metrics: List[Dict[str, Any]],
        file_path: str,
        expected_columns: Optional[List[str]] = None,
        historical_counts: Optional[List[int]] = None,
        affected_partitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        snapshots = [
            MetricSnapshot(
                timestamp=m.get("timestamp") or __import__("time").time(),
                metric_name=m["metric_name"],
                value=m["value"],
                unit=m.get("unit", ""),
                source=m.get("source", ""),
            )
            for m in metrics
        ]
        result = self.engine.run_full_response(
            title=title,
            description=description,
            severity=severity,
            raw_logs=raw_logs,
            metrics=snapshots,
            file_path=file_path,
            expected_columns=expected_columns,
            historical_counts=historical_counts,
            affected_partitions=affected_partitions,
        )
        return result.to_dict()

    def stats(self) -> Dict[str, Any]:
        return self.engine.get_statistics()

    def reset(self) -> None:
        self.engine.reset()


def _create_sample_csv(row_count: int = 5000, oversize: bool = False) -> str:
    """Crea un archivo CSV temporal de ejemplo para demo."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["feature_1", "feature_2", "feature_3"])
        writer.writeheader()
        count = row_count * 3 if oversize else row_count
        for i in range(count):
            writer.writerow({
                "feature_1": str(i % 1000),
                "feature_2": str((i % 3) + 1),
                "feature_3": str(i),
            })
    return path


def demo() -> None:
    print("=" * 80)
    print("UC-083 — Incident Response & Resilient Batch Inference")
    print("=" * 80)

    layer = UCIncidentResponseLayer(
        pipeline_id="trackprice_nightly_inference",
        config=IncidentResponseConfig(
            max_allowed_rows=10_000,
            chunk_size_rows=500,
            max_concurrency=2,
            memory_threshold=85.0,
            anomaly_zscore=2.0,
        ),
    )

    # Crear archivo anómalo
    csv_path = _create_sample_csv(row_count=5000, oversize=True)

    raw_logs = """2024-01-15T02:10:00Z ERROR orchestrator trace_id=abc123 Worker killed by OOM
2024-01-15T02:11:00Z WARN orchestrator trace_id=abc123 Memory usage 96%
2024-01-15T02:12:00Z ERROR orchestrator trace_id=abc123 Retrying failed partition p-001
2024-01-15T02:13:00Z ERROR worker trace_id=abc123 Out of memory during inference
2024-01-15T02:14:00Z INFO orchestrator trace_id=abc123 Stopping automatic retries"""

    metrics = [
        {"metric_name": "memory_percent", "value": 55.0},
        {"metric_name": "memory_percent", "value": 78.0},
        {"metric_name": "memory_percent", "value": 94.0},
        {"metric_name": "memory_percent", "value": 96.0},
        {"metric_name": "memory_percent", "value": 97.0},
        {"metric_name": "cpu_percent", "value": 45.0},
        {"metric_name": "cpu_percent", "value": 88.0},
        {"metric_name": "cpu_percent", "value": 91.0},
        {"metric_name": "duration_minutes", "value": 150.0},
    ]

    historical_counts = [4000, 4200, 4100, 4300, 4500, 4600, 4700]

    print("\nRunning full incident response...")
    result = layer.full_response(
        title="Nightly inference OOM and price update failure",
        description="Workers terminated by OOM during nightly batch inference; downstream reports incomplete.",
        severity="P1",
        raw_logs=raw_logs,
        metrics=metrics,
        file_path=csv_path,
        expected_columns=["feature_1", "feature_2", "feature_3"],
        historical_counts=historical_counts,
        affected_partitions=["p-001", "p-002", "p-003"],
    )

    print(f"Incident ID: {result['incident']['incident_id']}")
    print(f"Status: {result['incident']['status']}")
    print(f"Root causes: {[rc['category'] for rc in result['incident']['root_causes']]}")
    print(f"Mitigations applied: {[m['mitigation_type'] for m in result['incident']['mitigations']]}")
    print(f"Reprocess stats: {result['incident']['postmortem']['summary'][:200]}...")
    print(f"Postmortem improvements: {result['postmortem']['improvements']}")
    print(f"Runbook URL: {result['postmortem']['runbook_updates'][0] if result['postmortem']['runbook_updates'] else 'N/A'}")

    # Cleanup
    try:
        os.remove(csv_path)
    except Exception:
        pass

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demo()
