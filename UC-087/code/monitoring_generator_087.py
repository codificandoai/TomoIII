"""
UC-087 — Generador de configuraciones de observabilidad para Grafana Stack.

Produce artefactos para Prometheus, Grafana, Loki, Alertmanager,
OpenTelemetry Collector y Pyroscope, orientados a detectar y reportar
ataques adversarios y manipulación de modelos AGI.
"""

import json
import os
from typing import Dict, List, Any


class MonitoringGenerator087:
    """Genera dashboards, reglas, queries y configuraciones del Grafana Stack."""

    def __init__(self, pipeline_name: str = "uc087_mlsecops"):
        self.pipeline_name = pipeline_name

    def generate_prometheus_rules(self) -> str:
        """Reglas de alerta Prometheus para ataques y anomalías MLSecOps."""
        return f"""\
groups:
  - name: {self.pipeline_name}_alerts
    interval: 30s
    rules:
      - alert: MLSecOpsDataPoisoningDetected
        expr: increase(mlsecops_threat_data_poisoning_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P1
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Data poisoning detectado en {{ $labels.pipeline }}"
          description: "Se detectó un intento de envenenamiento de datos de entrenamiento."
          runbook_url: "https://wiki.trackprice.ai/runbooks/data_poisoning"

      - alert: MLSecOpsBackdoorDetected
        expr: increase(mlsecops_threat_backdoor_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P1
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Backdoor detectado en {{ $labels.pipeline }}"
          description: "Se detectó una caída de performance en un slice, posible backdoor."
          runbook_url: "https://wiki.trackprice.ai/runbooks/backdoor"

      - alert: MLSecOpsAdversarialAttack
        expr: increase(mlsecops_threat_adversarial_example_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P2
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Ataque adversarial detectado en {{ $labels.pipeline }}"
          description: "Feature squeezing o robustness gap indica entrada adversarial."
          runbook_url: "https://wiki.trackprice.ai/runbooks/adversarial_example"

      - alert: MLSecOpsModelRejected
        expr: increase(mlsecops_models_rejected_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P2
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Modelo rechazado por seguridad en {{ $labels.pipeline }}"
          description: "Un modelo candidato o externo no pasó los gates de seguridad."
          runbook_url: "https://wiki.trackprice.ai/runbooks/model_rejected"

      - alert: MLSecOpsRollbackExecuted
        expr: increase(mlsecops_rollbacks_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P1
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Rollback ejecutado en {{ $labels.pipeline }}"
          description: "Se revirtió a una versión de modelo segura tras anomalía."
          runbook_url: "https://wiki.trackprice.ai/runbooks/rollback"

      - alert: MLSecOpsProvenanceFailed
        expr: increase(mlsecops_batches_rejected_total{{pipeline=\"{self.pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P1
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Provenance falló en {{ $labels.pipeline }}"
          description: "Hash, firma o fuente de datos de entrenamiento no válida."
          runbook_url: "https://wiki.trackprice.ai/runbooks/provenance_failed"

      - alert: MLSecOpsRobustnessGapHigh
        expr: mlsecops_last_robustness_gap{{pipeline=\"{self.pipeline_name}\"}} > 0.15
        for: 0m
        labels:
          severity: P2
          pipeline: {self.pipeline_name}
        annotations:
          summary: "Brecha de robustez alta en {{ $labels.pipeline }}"
          description: "Clean accuracy vs adversarial accuracy excede el umbral configurado."
          runbook_url: "https://wiki.trackprice.ai/runbooks/adversarial_example"
"""

    def generate_grafana_dashboard(self) -> Dict[str, Any]:
        """Dashboard JSON para Grafana con paneles de ataques y seguridad ML."""
        base = self.pipeline_name
        panels = [
            {
                "id": 1,
                "title": "Batches procesados vs rechazados",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "targets": [
                    {"expr": f'sum(rate(mlsecops_batches_processed_total{{pipeline="{base}"}}[5m]))', "legendFormat": "processed"},
                    {"expr": f'sum(rate(mlsecops_batches_rejected_total{{pipeline="{base}"}}[5m]))', "legendFormat": "rejected"},
                ],
            },
            {
                "id": 2,
                "title": "Ataques detectados por categoría",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "targets": [
                    {"expr": f'sum(rate(mlsecops_threat_data_poisoning_total{{pipeline="{base}"}}[5m]))', "legendFormat": "data_poisoning"},
                    {"expr": f'sum(rate(mlsecops_threat_backdoor_total{{pipeline="{base}"}}[5m]))', "legendFormat": "backdoor"},
                    {"expr": f'sum(rate(mlsecops_threat_adversarial_example_total{{pipeline="{base}"}}[5m]))', "legendFormat": "adversarial"},
                    {"expr": f'sum(rate(mlsecops_threat_model_manipulation_total{{pipeline="{base}"}}[5m]))', "legendFormat": "model_manipulation"},
                ],
            },
            {
                "id": 3,
                "title": "Robustness gap (último valor)",
                "type": "stat",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "targets": [
                    {"expr": f'mlsecops_last_robustness_gap{{pipeline="{base}"}}', "legendFormat": "robustness_gap"},
                ],
                "fieldConfig": {
                    "defaults": {
                        "thresholds": {
                            "steps": [
                                {"value": 0.0, "color": "green"},
                                {"value": 0.15, "color": "red"},
                            ],
                        },
                    },
                },
            },
            {
                "id": 4,
                "title": "Alertas por severidad",
                "type": "piechart",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "targets": [
                    {"expr": f'sum by (severity) (mlsecops_alerts_total{{pipeline="{base}"}})', "legendFormat": "{{severity}}"},
                ],
            },
            {
                "id": 5,
                "title": "Versiones de modelo (promoted / rejected / canary)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                "targets": [
                    {"expr": f'mlsecops_model_versions_promoted{{pipeline="{base}"}}', "legendFormat": "promoted"},
                    {"expr": f'mlsecops_model_versions_rejected{{pipeline="{base}"}}', "legendFormat": "rejected"},
                    {"expr": f'mlsecops_model_versions_canary{{pipeline="{base}"}}', "legendFormat": "canary"},
                ],
            },
            {
                "id": 6,
                "title": "Entradas adversariales detectadas (feature squeezing)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
                "targets": [
                    {"expr": f'sum(rate(mlsecops_squeezed_differences_total{{pipeline="{base}"}}[5m]))', "legendFormat": "squeezing_mismatches"},
                ],
            },
            {
                "id": 7,
                "title": "Rollbacks ejecutados",
                "type": "stat",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
                "targets": [
                    {"expr": f'sum(rate(mlsecops_rollbacks_total{{pipeline="{base}"}}[5m]))', "legendFormat": "rollbacks"},
                ],
            },
            {
                "id": 8,
                "title": "Latencia del guardian (ms)",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24},
                "targets": [
                    {"expr": f'mlsecops_guardian_duration_ms{{pipeline="{base}"}}', "legendFormat": "duration"},
                ],
            },
        ]
        return {
            "dashboard": {
                "id": None,
                "uid": f"{base}-security",
                "title": f"UC-087 {base} — MLSecOps Security",
                "tags": ["uc-087", "mlsecops", "adversarial", "agi"],
                "timezone": "UTC",
                "schemaVersion": 36,
                "refresh": "30s",
                "panels": panels,
                "templating": {
                    "list": [
                        {
                            "name": "pipeline",
                            "type": "constant",
                            "current": {"value": base, "text": base},
                        },
                    ],
                },
            },
            "overwrite": True,
        }

    def generate_loki_queries(self) -> List[Dict[str, str]]:
        """Queries LogQL para investigar ataques adversarios."""
        return [
            {
                "name": "Ataques adversariales detectados",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "Amenaza detectada" or "adversarial"',
            },
            {
                "name": "Backdoors / triggers",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "backdoor" or "trigger"',
            },
            {
                "name": "Data poisoning / provenance",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "provenance" or "poisoning"',
            },
            {
                "name": "Modelos rechazados",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "rechazado" or "rejected"',
            },
            {
                "name": "Rollbacks",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "Rollback ejecutado"',
            },
            {
                "name": "Decisiones del guardian",
                "query": f'{{pipeline="{self.pipeline_name}",component="uc087_mlsecops"}} |= "decision_id"',
            },
        ]

    def generate_alertmanager_config(self) -> str:
        """Configuración de Alertmanager para MLSecOps."""
        return f"""\
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@trackprice.ai'

route:
  receiver: 'default'
  group_by: ['alertname', 'severity', 'pipeline']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h
  routes:
    - match:
        severity: P1
        pipeline: {self.pipeline_name}
      receiver: 'pagerduty-mlsecops'
      continue: true
    - match:
        severity: P2
        pipeline: {self.pipeline_name}
      receiver: 'slack-mlsecops'

receivers:
  - name: 'default'
    slack_configs:
      - send_resolved: true
        title: 'MLSecOps Alert'
        text: '{{{{ range .Alerts }}}}{{{{ .Annotations.summary }}}} — {{{{ .Annotations.runbook_url }}}}{{{{ end }}}}'

  - name: 'slack-mlsecops'
    slack_configs:
      - channel: '#mlsecops-alerts'
        send_resolved: true
        title: 'MLSecOps Security Alert'
        text: '{{{{ range .Alerts }}}}{{{{ .Annotations.description }}}} | runbook: {{{{ .Annotations.runbook_url }}}}{{{{ end }}}}'

  - name: 'pagerduty-mlsecops'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'
        severity: critical
        description: '{{{{ range .Alerts }}}}{{{{ .Annotations.summary }}}}{{{{ end }}}}'
"""

    def generate_otel_collector_config(self) -> str:
        """OpenTelemetry Collector: OTLP → Prometheus/Loki/Jaeger."""
        return f"""\
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  resource:
    attributes:
      - key: pipeline
        value: {self.pipeline_name}
        action: upsert
      - key: component
        value: uc087_mlsecops
        action: upsert

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [loki]
    traces:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [jaeger]
"""

    def generate_pyroscope_config(self) -> str:
        """Configuración básica para enviar perfiles a Pyroscope."""
        return f"""\
server:
  http_listen_port: 4040

scrape_configs:
  - job_name: '{self.pipeline_name}'
    static_configs:
      - targets: ['localhost:5050']
    profiling_config:
      pprof_config:
        memory:
          enabled: true
        cpu:
          enabled: true
        goroutine:
          enabled: true
"""

    def generate_grafana_datasource_config(self) -> Dict[str, Any]:
        """Datasources para Grafana: Prometheus, Loki, Jaeger, Tempo, Pyroscope."""
        return {
            "datasources": [
                {
                    "name": "Prometheus-MLSecOps",
                    "type": "prometheus",
                    "access": "proxy",
                    "url": "http://prometheus:9090",
                },
                {
                    "name": "Loki-MLSecOps",
                    "type": "loki",
                    "access": "proxy",
                    "url": "http://loki:3100",
                },
                {
                    "name": "Jaeger-MLSecOps",
                    "type": "jaeger",
                    "access": "proxy",
                    "url": "http://jaeger:16686",
                },
                {
                    "name": "Pyroscope-MLSecOps",
                    "type": "pyroscope",
                    "access": "proxy",
                    "url": "http://pyroscope:4040",
                },
            ]
        }

    def generate_attack_profile(self) -> Dict[str, Any]:
        """Perfil de ataque ML: metadatos para dashboards y alertas."""
        return {
            "pipeline": self.pipeline_name,
            "threat_categories": [
                "data_poisoning",
                "backdoor",
                "adversarial_example",
                "model_manipulation",
                "artifact_tampering",
            ],
            "metrics": [
                "mlsecops_batches_processed_total",
                "mlsecops_batches_rejected_total",
                "mlsecops_batches_approved_total",
                "mlsecops_models_rejected_total",
                "mlsecops_models_approved_total",
                "mlsecops_rollbacks_total",
                "mlsecops_last_robustness_gap",
                "mlsecops_threat_data_poisoning_total",
                "mlsecops_threat_backdoor_total",
                "mlsecops_threat_adversarial_example_total",
                "mlsecops_threat_model_manipulation_total",
                "mlsecops_threat_artifact_tampering_total",
                "mlsecops_squeezed_differences_total",
                "mlsecops_guardian_duration_ms",
            ],
            "logs": {
                "service_name": "uc087_mlsecops",
                "level_key": "level",
                "message_key": "message",
                "trace_id_key": "trace_id",
            },
        }

    def generate_all(self) -> Dict[str, Any]:
        return {
            "prometheus_rules": self.generate_prometheus_rules(),
            "grafana_dashboard": self.generate_grafana_dashboard(),
            "grafana_datasources": self.generate_grafana_datasource_config(),
            "loki_queries": self.generate_loki_queries(),
            "alertmanager_config": self.generate_alertmanager_config(),
            "otel_collector_config": self.generate_otel_collector_config(),
            "pyroscope_config": self.generate_pyroscope_config(),
            "attack_profile": self.generate_attack_profile(),
        }

    def write_artifacts(self, output_dir: str = "observability_087") -> List[str]:
        """Escribe todos los artefactos de observabilidad a disco."""
        os.makedirs(output_dir, exist_ok=True)
        artifacts = self.generate_all()
        mapping = {
            "prometheus_rules": "prometheus_rules.yml",
            "grafana_dashboard": "grafana_dashboard.json",
            "grafana_datasources": "grafana_datasources.json",
            "loki_queries": "loki_queries.json",
            "alertmanager_config": "alertmanager.yml",
            "otel_collector_config": "otel_collector.yml",
            "pyroscope_config": "pyroscope.yml",
            "attack_profile": "attack_profile.json",
        }
        written = []
        for key, filename in mapping.items():
            path = os.path.join(output_dir, filename)
            content = artifacts[key]
            if isinstance(content, str):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(content, f, indent=2)
            written.append(path)
        return written


if __name__ == "__main__":
    mg = MonitoringGenerator087()
    for path in mg.write_artifacts():
        print(path)
