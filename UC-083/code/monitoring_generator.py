"""
UC-083 — Generador de configuraciones de observabilidad completa.

Produce artefactos para Prometheus, Grafana, Loki, Envoy y Alertmanager,
diseñados para monitorear y alertar sobre pipelines de inferencia batch.
"""

import json
from typing import Dict, List, Any

from incident_models import IncidentResponseConfig


class MonitoringGenerator:
    """
    Genera configuraciones de observabilidad para pipelines batch. Salida
compatible con Prometheus, Grafana, Loki, Envoy access logs y Alertmanager.
    """

    def __init__(self, config: IncidentResponseConfig = None):
        self.config = config or IncidentResponseConfig()

    def generate_prometheus_rules(self, pipeline_name: str = "batch_inference") -> str:
        """Genera reglas de alerta Prometheus en formato YAML."""
        return f"""\
groups:
  - name: {pipeline_name}_alerts
    interval: 30s
    rules:
      - alert: BatchInferenceMemoryPressure
        expr: memory_usage_percent{{job=\"{pipeline_name}\"}} >= {self.config.memory_threshold}
        for: 2m
        labels:
          severity: P1
          pipeline: {pipeline_name}
        annotations:
          summary: "Presión de memoria en {pipeline_name}"
          description: "El uso de memoria ha estado >= {self.config.memory_threshold}% por 2 minutos."
          runbook_url: "https://wiki.trackprice.ai/runbooks/out_of_memory"

      - alert: BatchInferenceCPUPressure
        expr: cpu_usage_percent{{job=\"{pipeline_name}\"}} >= {self.config.cpu_threshold}
        for: 5m
        labels:
          severity: P2
          pipeline: {pipeline_name}
        annotations:
          summary: "Presión de CPU en {pipeline_name}"
          description: "El uso de CPU ha estado >= {self.config.cpu_threshold}% por 5 minutos."

      - alert: BatchInferenceDurationExceeded
        expr: batch_job_duration_minutes{{job=\"{pipeline_name}\"}} > {self.config.duration_threshold_minutes}
        for: 0m
        labels:
          severity: P2
          pipeline: {pipeline_name}
        annotations:
          summary: "Duración de job excedida en {pipeline_name}"
          description: "El job lleva más de {self.config.duration_threshold_minutes} minutos."

      - alert: BatchInferenceInputVolumeAnomaly
        expr: abs((batch_input_rows - avg_over_time(batch_input_rows[1d])) / stddev_over_time(batch_input_rows[1d])) > {self.config.anomaly_zscore}
        for: 0m
        labels:
          severity: P1
          pipeline: {pipeline_name}
        annotations:
          summary: "Anomalía de volumen de entrada en {pipeline_name}"
          description: "El volumen de entrada se desvía más de {self.config.anomaly_zscore} desviaciones estándar del promedio diario."

      - alert: BatchInferenceValidationFailed
        expr: increase(batch_validation_failures{{job=\"{pipeline_name}\"}}[5m]) > 0
        for: 0m
        labels:
          severity: P1
          pipeline: {pipeline_name}
        annotations:
          summary: "Validación de datos falló en {pipeline_name}"
          description: "Se detectó al menos un fallo de validación en los últimos 5 minutos."

      - alert: BatchInferenceCheckpointsFailed
        expr: rate(checkpoints_failed{{job=\"{pipeline_name}\"}}[5m]) > 0
        for: 1m
        labels:
          severity: P1
          pipeline: {pipeline_name}
        annotations:
          summary: "Checkpoints fallando en {pipeline_name}"
          description: "Se detectaron checkpoints fallidos; requiere revisión del reprocesamiento."
          runbook_url: "https://wiki.trackprice.ai/runbooks/infrastructure"
"""

    def generate_prometheus_recording_rules(self, pipeline_name: str = "batch_inference") -> str:
        """Reglas de recording para dashboards y SLOs."""
        return f"""\
groups:
  - name: {pipeline_name}_recording
    interval: 1m
    rules:
      - record: batch_job:success_rate_5m
        expr: |
          sum(rate(batch_job_status{{job=\"{pipeline_name}\",status=\"success\"}}[5m]))
          /
          sum(rate(batch_job_status{{job=\"{pipeline_name}\"}}[5m]))

      - record: batch_worker:oom_rate_5m
        expr: sum(rate(oom_killed_total{{job=\"{pipeline_name}\"}}[5m]))

      - record: batch_worker:restart_rate_5m
        expr: sum(rate(worker_restarts_total{{job=\"{pipeline_name}\"}}[5m]))

      - record: batch_input:volume_zscore_1d
        expr: |
          (
            batch_input_rows{{job=\"{pipeline_name}\"}}
            - avg_over_time(batch_input_rows{{job=\"{pipeline_name}\"}}[1d])
          )
          /
          stddev_over_time(batch_input_rows{{job=\"{pipeline_name}\"}}[1d])
"""

    def generate_alertmanager_config(self, pipeline_name: str = "batch_inference") -> str:
        """Configuración básica de Alertmanager con routing a Slack/PagerDuty."""
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
        pipeline: {pipeline_name}
      receiver: 'pagerduty-batch'
      continue: true
    - match:
        severity: P2
        pipeline: {pipeline_name}
      receiver: 'slack-batch'

receivers:
  - name: 'default'
    slack_configs:
      - send_resolved: true
        title: 'UC-083 Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }} — {{ .Annotations.runbook_url }}{{ end }}'

  - name: 'slack-batch'
    slack_configs:
      - channel: '#mlops-alerts'
        send_resolved: true
        title: 'Batch Inference Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }} | runbook: {{ .Annotations.runbook_url }}{{ end }}'

  - name: 'pagerduty-batch'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'
        severity: critical
        description: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
"""

    def generate_grafana_dashboard(self, pipeline_name: str = "batch_inference") -> Dict[str, Any]:
        """Genera un dashboard JSON para Grafana."""
        return {
            "dashboard": {
                "id": None,
                "uid": f"uc-083-{pipeline_name}",
                "title": f"UC-083 {pipeline_name} — Resiliencia Batch",
                "tags": ["uc-083", "batch", "mlops", "trackprice"],
                "timezone": "UTC",
                "schemaVersion": 36,
                "refresh": "30s",
                "panels": [
                    {
                        "id": 1,
                        "title": "Uso de memoria (%)",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                        "targets": [
                            {"expr": f'memory_usage_percent{{job="{pipeline_name}"}}', "legendFormat": "memory"},
                        ],
                        "fieldConfig": {
                            "defaults": {
                                "custom": {"lineWidth": 2},
                                "thresholds": {
                                    "steps": [
                                        {"value": self.config.memory_threshold, "color": "red"},
                                    ],
                                },
                            },
                        },
                    },
                    {
                        "id": 2,
                        "title": "Uso de CPU (%)",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                        "targets": [
                            {"expr": f'cpu_usage_percent{{job="{pipeline_name}"}}', "legendFormat": "cpu"},
                        ],
                    },
                    {
                        "id": 3,
                        "title": "Duración del job (min)",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                        "targets": [
                            {"expr": f'batch_job_duration_minutes{{job="{pipeline_name}"}}', "legendFormat": "duration"},
                        ],
                    },
                    {
                        "id": 4,
                        "title": "Volumen de entrada (filas)",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                        "targets": [
                            {"expr": f'batch_input_rows{{job="{pipeline_name}"}}', "legendFormat": "input rows"},
                        ],
                    },
                    {
                        "id": 5,
                        "title": "Checkpoints completados / fallidos",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                        "targets": [
                            {"expr": f'sum(checkpoints_completed{{job="{pipeline_name}"}})', "legendFormat": "completed"},
                            {"expr": f'sum(checkpoints_failed{{job="{pipeline_name}"}})', "legendFormat": "failed"},
                        ],
                    },
                    {
                        "id": 6,
                        "title": "Tasa de éxito del job (5m)",
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
                        "targets": [
                            {"expr": f'batch_job:success_rate_5m{{job="{pipeline_name}"}}', "legendFormat": "success rate"},
                        ],
                    },
                    {
                        "id": 7,
                        "title": "Reinicios y OOM de workers",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
                        "targets": [
                            {"expr": f'batch_worker:oom_rate_5m{{job="{pipeline_name}"}}', "legendFormat": "OOM rate"},
                            {"expr": f'batch_worker:restart_rate_5m{{job="{pipeline_name}"}}', "legendFormat": "restart rate"},
                        ],
                    },
                    {
                        "id": 8,
                        "title": "Z-score volumen de entrada",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24},
                        "targets": [
                            {"expr": f'batch_input:volume_zscore_1d{{job="{pipeline_name}"}}', "legendFormat": "z-score"},
                        ],
                    },
                ],
                "templating": {
                    "list": [
                        {
                            "name": "pipeline",
                            "type": "constant",
                            "current": {"value": pipeline_name, "text": pipeline_name},
                        },
                    ],
                },
            },
            "overwrite": True,
        }

    def generate_loki_datasource_config(self, pipeline_name: str = "batch_inference") -> Dict[str, Any]:
        """Configuración de datasource de Loki para Grafana."""
        return {
            "datasources": [
                {
                    "name": "Loki",
                    "type": "loki",
                    "access": "proxy",
                    "url": "http://loki:3100",
                    "jsonData": {"maxLines": 1000},
                }
            ]
        }

    def generate_loki_queries(self, pipeline_name: str = "batch_inference") -> List[Dict[str, str]]:
        """Queries LogQL predefinidas para incidentes batch."""
        return [
            {
                "name": "OOM Killed",
                "query": f'{{job="{pipeline_name}"}} |= "Killed process" or "Out of memory" or "OOM"',
                "description": "Workers terminados por OOM",
            },
            {
                "name": "Worker Terminated",
                "query": f'{{job="{pipeline_name}",source="orchestrator"}} |= "worker terminated" or "worker died" or "exit code"',
                "description": "Workers detenidos por el orquestador",
            },
            {
                "name": "Validation Failed",
                "query": f'{{job="{pipeline_name}",source="orchestrator"}} |= "VOLUMEN EXCESO" or "schema drift" or "validation failed"',
                "description": "Fallos de validación de datos",
            },
            {
                "name": "Pipeline Start/End",
                "query": f'{{job="{pipeline_name}",source="orchestrator"}} |= "Pipeline started" or "Pipeline completed" or "Pipeline failed"',
                "description": "Inicio y fin de jobs",
            },
            {
                "name": "Errors by Trace ID",
                "query": f'{{job="{pipeline_name}"}} |= "ERROR" | json trace_id="trace_id"',
                "description": "Errores agrupables por trace_id",
            },
        ]

    def generate_envoy_config(self, pipeline_name: str = "batch_inference") -> Dict[str, Any]:
        """Configuración de Envoy para exponer métricas y access logs."""
        return {
            "static_resources": {
                "listeners": [
                    {
                        "name": f"listener_{pipeline_name}",
                        "address": {"socket_address": {"address": "0.0.0.0", "port_value": 8080}},
                        "filter_chains": [
                            {
                                "filters": [
                                    {
                                        "name": "envoy.filters.network.http_connection_manager",
                                        "typed_config": {
                                            "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                                            "stat_prefix": f"{pipeline_name}_ingress",
                                            "codec_type": "AUTO",
                                            "route_config": {
                                                "name": "local_route",
                                                "virtual_hosts": [
                                                    {
                                                        "name": "local_service",
                                                        "domains": ["*"],
                                                        "routes": [
                                                            {
                                                                "match": {"prefix": "/"},
                                                                "route": {"cluster": f"{pipeline_name}_service"},
                                                            }
                                                        ],
                                                    }
                                                ],
                                            },
                                            "http_filters": [
                                                {"name": "envoy.filters.http.router", "typed_config": {"@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"}}
                                            ],
                                            "access_log": [
                                                {
                                                    "name": "envoy.access_loggers.stdout",
                                                    "typed_config": {
                                                        "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StderrAccessLog",
                                                        "log_format": {
                                                            "json_format": {
                                                                "timestamp": "%START_TIME%",
                                                                "method": "%REQ(:METHOD)%",
                                                                "path": "%REQ(:PATH)%",
                                                                "status": "%RESPONSE_CODE%",
                                                                "duration_ms": "%DURATION%",
                                                                "trace_id": "%REQ(X-TRACE-ID)%",
                                                                "pipeline": pipeline_name,
                                                            }
                                                        },
                                                    },
                                                }
                                            ],
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "clusters": [
                    {
                        "name": f"{pipeline_name}_service",
                        "connect_timeout": "30s",
                        "type": "LOGICAL_DNS",
                        "lb_policy": "ROUND_ROBIN",
                        "load_assignment": {
                            "cluster_name": f"{pipeline_name}_service",
                            "endpoints": [
                                {
                                    "lb_endpoints": [
                                        {"endpoint": {"address": {"socket_address": {"address": "localhost", "port_value": 5083}}}}
                                    ]
                                }
                            ],
                        },
                    }
                ],
            },
            "admin": {
                "address": {"socket_address": {"address": "0.0.0.0", "port_value": 9901}}
            },
        }

    def generate_envoy_statsd_config(self, pipeline_name: str = "batch_inference") -> Dict[str, Any]:
        """Configuración de Envoy statsd sink hacia Prometheus StatsD exporter."""
        return {
            "stats_sinks": [
                {
                    "name": "envoy.stat_sinks.statsd",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.config.metrics.v3.StatsdSink",
                        "address": {"socket_address": {"address": "statsd-exporter", "port_value": 9125}},
                    }
                }
            ],
            "stats_config": {
                "stats_tags": [
                    {"tag_name": "pipeline", "fixed_value": pipeline_name},
                ],
            },
        }

    def generate_otel_collector_config(self, pipeline_name: str = "batch_inference") -> str:
        """Configuración del OpenTelemetry Collector para pipelines batch."""
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
        value: {pipeline_name}
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

    def generate_log_checks(self, pipeline_name: str = "batch_inference") -> List[Dict[str, Any]]:
        """Checks estructurados para agregador de logs."""
        return [
            {
                "name": "OOM_Killed",
                "pattern": "Killed process|Out of memory|OOM",
                "severity": "P1",
                "source": ["stdout", "stderr"],
                "pipeline": pipeline_name,
            },
            {
                "name": "Worker_Terminated",
                "pattern": "worker terminated|worker died|exit code",
                "severity": "P1",
                "source": ["orchestrator"],
                "pipeline": pipeline_name,
            },
            {
                "name": "Validation_Failed",
                "pattern": "VOLUMEN EXCESO|schema drift|validation failed",
                "severity": "P1",
                "source": ["orchestrator"],
                "pipeline": pipeline_name,
            },
        ]

    def generate_all(self, pipeline_name: str = "batch_inference") -> Dict[str, Any]:
        return {
            "prometheus_rules": self.generate_prometheus_rules(pipeline_name),
            "prometheus_recording_rules": self.generate_prometheus_recording_rules(pipeline_name),
            "alertmanager_config": self.generate_alertmanager_config(pipeline_name),
            "grafana_dashboard": self.generate_grafana_dashboard(pipeline_name),
            "loki_datasource": self.generate_loki_datasource_config(pipeline_name),
            "loki_queries": self.generate_loki_queries(pipeline_name),
            "envoy_config": self.generate_envoy_config(pipeline_name),
            "envoy_statsd_config": self.generate_envoy_statsd_config(pipeline_name),
            "otel_collector_config": self.generate_otel_collector_config(pipeline_name),
            "log_checks": self.generate_log_checks(pipeline_name),
        }

    def write_artifacts(self, pipeline_name: str = "batch_inference", output_dir: str = "observability") -> List[str]:
        """Escribe todos los artefactos de observabilidad a disco."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        artifacts = self.generate_all(pipeline_name)
        written = []
        mapping = {
            "prometheus_rules": "prometheus_rules.yml",
            "prometheus_recording_rules": "prometheus_recording_rules.yml",
            "alertmanager_config": "alertmanager.yml",
            "grafana_dashboard": "grafana_dashboard.json",
            "loki_datasource": "grafana_datasource_loki.json",
            "loki_queries": "loki_queries.json",
            "envoy_config": "envoy.json",
            "envoy_statsd_config": "envoy_statsd.json",
            "otel_collector_config": "otel_collector.yml",
            "log_checks": "log_checks.json",
        }
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
