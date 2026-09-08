"""Generate local monitoring artifacts (Loki, Tempo, Prometheus) without network side effects."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from exporters_309 import Exporter, to_loki_lines, to_tempo_spans, to_prometheus_text
from trace_store import TraceStore
from metrics_aggregator import MetricsAggregator


class MonitoringGenerator:
    def __init__(self, store: TraceStore, metrics: MetricsAggregator, output_dir: str = "."):
        self.store = store
        self.metrics = metrics
        self.output_dir = output_dir
        self.exporter = Exporter(metrics)

    def generate(self) -> Dict[str, str]:
        """Write current traces/metrics to local files and return paths."""
        events = self.store.get_all_events(role="auditor")
        os.makedirs(self.output_dir, exist_ok=True)

        loki_path = os.path.join(self.output_dir, "uc309_loki_logs.jsonl")
        self.exporter.export_loki_file(events, loki_path)

        tempo_path = os.path.join(self.output_dir, "uc309_tempo_spans.json")
        spans = to_tempo_spans(events)
        with open(tempo_path, "w", encoding="utf-8") as f:
            json.dump(spans, f, default=str, ensure_ascii=True, indent=2)

        prom_path = os.path.join(self.output_dir, "uc309_metrics.prom")
        with open(prom_path, "w", encoding="utf-8") as f:
            f.write(to_prometheus_text(self.metrics))

        return {
            "loki_jsonl": loki_path,
            "tempo_spans": tempo_path,
            "prometheus_text": prom_path,
        }

    def generate_uc308_feed(self) -> Dict[str, Any]:
        """Return a JSON-serializable telemetry feed compatible with UC-308 longitudinal analysis."""
        events = self.store.get_all_events(role="auditor")
        return {
            "source": "UC-309",
            "generated_at": time_ns(),
            "metrics": self.metrics.to_dict(),
            "traces": len(self.store.list_traces(role="auditor")),
            "events": len(events),
            "loki_lines_sample": to_loki_lines(events)[:10],
            "tempo_spans_sample": to_tempo_spans(events)[:10],
        }


def time_ns() -> int:
    import time
    return int(time.time() * 1e9)
