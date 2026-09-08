"""
UC-308 — Generador de artefactos de monitorización.

Produce configuración Prometheus, reglas de alerta, dashboard de Grafana y
configuración de Alertmanager. No requiere librerías externas.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def generate_prometheus_yaml(target_host: str = "localhost", target_port: int = 5308) -> str:
    return f"""global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'uc308_drift_detector'
    metrics_path: '/api/v1/metrics'
    static_configs:
      - targets: ['{target_host}:{target_port}']
"""


def generate_alert_rules_yaml() -> str:
    return """groups:
  - name: uc308_agent_drift
    rules:
      - alert: UC308DriftCritical
        expr: |
          (
            uc308_run_status >= 3
            or
            uc308_success_rate < 0.6
          )
        for: 1m
        labels:
          severity: critical
          team: ai-operations
        annotations:
          summary: "UC-308: critical agent drift or environmental degradation detected"
          description: "The UC-308 nightly run reported critical status or success rate below 60%%. Manual intervention is required."

      - alert: UC308DriftDegraded
        expr: |
          (
            uc308_run_status >= 2
            or
            (uc308_success_rate < 0.8 and uc308_success_rate >= 0.6)
          )
        for: 2m
        labels:
          severity: degraded
          team: ai-operations
        annotations:
          summary: "UC-308: degraded agent performance"
          description: "The UC-308 run status is degraded or success rate is between 60%% and 80%%."

      - alert: UC308DriftWarning
        expr: |
          (
            uc308_run_status >= 1
            or
            (uc308_success_rate < 0.9 and uc308_success_rate >= 0.8)
            or
            (uc308_quality_score < 0.9 and uc308_quality_score >= 0.75)
          )
        for: 5m
        labels:
          severity: warning
          team: ai-operations
        annotations:
          summary: "UC-308: early drift warning"
          description: "Early signs of drift detected; monitor closely before it escalates."

      - alert: UC308ToolOperationalLatency
        expr: |
          (
            rate(uc308_latency_seconds_sum[5m])
            /
            rate(uc308_latency_seconds_count[5m])
          ) > 2
        for: 2m
        labels:
          severity: warning
          team: ai-operations
        annotations:
          summary: "UC-308: tool latency regression"
          description: "Average latency for tool {{ $labels.tool }} is above 2 seconds."

      - alert: UC308APIContractDrift
        expr: uc308_drift_status{drift_type=\"contract_api\"} >= 2
        for: 1m
        labels:
          severity: degraded
          team: ai-operations
        annotations:
          summary: "UC-308: API contract drift"
          description: "Detected contract/schema drift in {{ $labels.tool }}."

      - alert: UC308HTMLInterfaceDrift
        expr: uc308_drift_status{drift_type=\"html_interface\"} >= 2
        for: 1m
        labels:
          severity: degraded
          team: ai-operations
        annotations:
          summary: "UC-308: HTML interface drift"
          description: "Detected HTML/interface selector drift in {{ $labels.tool }}."

      - alert: UC308DataDistributionDrift
        expr: uc308_drift_score{drift_type=\"data_distribution\"} > 0.25
        for: 2m
        labels:
          severity: degraded
          team: ai-operations
        annotations:
          summary: "UC-308: data distribution drift"
          description: "Detected data distribution shift with PSI/JS above threshold."

      - alert: UC308BehavioralDrift
        expr: uc308_drift_status{drift_type=\"behavioral\"} >= 2
        for: 2m
        labels:
          severity: degraded
          team: ai-operations
        annotations:
          summary: "UC-308: behavioral drift"
          description: "Agent behavior (steps/retries/escalations) degraded."
"""


def generate_alertmanager_yaml() -> str:
    return """global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'degraded'
    equal: ['alertname']

receivers:
  - name: 'default'
    # El Alertmanager real debe configurar un webhook/email/Slack válido.
    # Este es un endpoint simulado/documental; UC-308 nunca auto-modifica.
    webhook_configs:
      - url: 'http://127.0.0.1:5308/api/v1/noop'
        send_resolved: false

  - name: 'critical'
    webhook_configs:
      - url: 'http://127.0.0.1:5308/api/v1/noop'
        send_resolved: false
"""


def generate_grafana_dashboard() -> str:
    dashboard: Dict[str, Any] = {
        "dashboard": {
            "id": None,
            "title": "UC-308 Agent Drift / Environmental Degradation",
            "tags": ["uc308", "agent-drift", "mlops"],
            "timezone": "utc",
            "schemaVersion": 38,
            "panels": [
                {
                    "id": 1,
                    "title": "Success Rate",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": "uc308_success_rate",
                            "legendFormat": "{{agent_id}}/{{environment}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                },
                {
                    "id": 2,
                    "title": "Quality Score",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": "uc308_quality_score",
                            "legendFormat": "{{agent_id}}/{{environment}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                },
                {
                    "id": 3,
                    "title": "Run Status",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "uc308_run_status",
                            "legendFormat": "status",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                },
                {
                    "id": 4,
                    "title": "Latency by Tool",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(uc308_latency_seconds_sum[5m]) / rate(uc308_latency_seconds_count[5m])",
                            "legendFormat": "{{tool}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                },
                {
                    "id": 5,
                    "title": "Task Results by Tool/Status",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(uc308_task_results_total[5m])) by (tool, status)",
                            "legendFormat": "{{tool}}-{{status}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
                },
                {
                    "id": 6,
                    "title": "Drift Score by Type",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "uc308_drift_score",
                            "legendFormat": "{{drift_type}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
                },
                {
                    "id": 7,
                    "title": "Drift Status by Type",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "uc308_drift_status",
                            "legendFormat": "{{drift_type}}-{{status}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24},
                },
            ],
            "time": {"from": "now-6h", "to": "now"},
        },
        "overwrite": False,
    }
    return json.dumps(dashboard, indent=2)


if __name__ == "__main__":
    print("=== prometheus.yml ===")
    print(generate_prometheus_yaml())
    print("=== alert_rules.yml ===")
    print(generate_alert_rules_yaml())
    print("=== alertmanager.yml ===")
    print(generate_alertmanager_yaml())
    print("=== grafana_dashboard.json ===")
    print(generate_grafana_dashboard())
