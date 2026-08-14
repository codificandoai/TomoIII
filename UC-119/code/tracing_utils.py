"""
Codificando.AI - UC-119
Trazabilidad distribuida con OpenTelemetry, exportando a Grafana Tempo
mediante OTLP/HTTP.

El uso de OpenTelemetry es opcional: si el paquete no está instalado o
`TRACING_ENABLED=false`, el sistema degrada de forma transparente a un
"tracer" nulo (no-op) que no rompe el pipeline ni los tests.
"""

import logging
from contextlib import contextmanager

from config import CONFIG

logger = logging.getLogger(__name__)

_tracer = None


class _NoOpSpan:
    def set_attribute(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _NoOpTracer:
    @contextmanager
    def start_as_current_span(self, name, **kwargs):
        yield _NoOpSpan()


def get_tracer():
    """Devuelve un tracer de OpenTelemetry configurado hacia Tempo,
    o un tracer no-op si la trazabilidad está deshabilitada o no
    disponible."""
    global _tracer
    if _tracer is not None:
        return _tracer

    if not CONFIG.tracing.enabled:
        _tracer = _NoOpTracer()
        return _tracer

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        resource = Resource.create({"service.name": CONFIG.tracing.service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{CONFIG.tracing.otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(CONFIG.tracing.service_name)
        logger.info(f"Tracing OTLP habilitado -> {CONFIG.tracing.otlp_endpoint}")
    except Exception as e:  # pragma: no cover - depende de infra externa
        logger.warning(f"No se pudo inicializar OpenTelemetry, usando no-op tracer: {e}")
        _tracer = _NoOpTracer()

    return _tracer
