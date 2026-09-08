"""
UC-162 — API REST Flask para LLMOps.

Expone el guardian LLMOps como servicio REST.
Puerto por defecto: 5162
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, List

from models_162 import LLMOpsConfig, CorpusDocument, DocumentMetadata
from llmops_guardian import LLMOpsGuardian

app = Flask(__name__)

_guardian: LLMOpsGuardian = LLMOpsGuardian()

INPUT_CARDS = {
    "POST /api/v1/process-corpus": {
        "description": "Procesa un corpus: verifica sesgo, registra linaje, decide.",
        "parameters": {
            "documents": {
                "type": "array",
                "required": True,
                "description": "Lista de {id, text, metadata: {fuente, fuente_tipo, fecha_creacion, categoria_tema, genero_autor, region_geografica, perspectiva_tematica, idioma, periodo_temporal, nivel_confianza}}.",
            },
            "source": {"type": "string", "required": False, "default": "unknown"},
        },
    },
    "POST /api/v1/evaluate-response": {
        "description": "Evalúa una respuesta del LLM: detecta hallucination.",
        "parameters": {
            "response": {"type": "string", "required": True, "description": "Texto de la respuesta del LLM."},
            "retrieved_chunks": {"type": "array", "required": True, "description": "Lista de chunks recuperados por RAG."},
            "prompt_version": {"type": "string", "required": False, "default": ""},
            "model": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/check-drift": {
        "description": "Verifica drift conceptual para un concepto.",
        "parameters": {
            "concept_name": {"type": "string", "required": True},
            "current_contexts": {"type": "array", "required": True, "description": "Lista de contextos actuales del concepto."},
            "current_co_occurrences": {"type": "array", "required": False, "description": "Lista de listas de términos co-ocurrentes."},
        },
    },
    "POST /api/v1/set-baseline": {
        "description": "Establece un baseline conceptual para drift detection.",
        "parameters": {
            "concept_name": {"type": "string", "required": True},
            "contexts": {"type": "array", "required": True},
            "co_occurrences": {"type": "array", "required": False},
        },
    },
    "POST /api/v1/register-prompt": {
        "description": "Registra una nueva versión de prompt template.",
        "parameters": {
            "template": {"type": "string", "required": True},
            "version": {"type": "string", "required": False, "default": ""},
            "tags": {"type": "array", "required": False},
        },
    },
    "POST /api/v1/approve-prompt": {
        "description": "Aprueba una versión de prompt (compliance).",
        "parameters": {
            "prompt_id": {"type": "string", "required": True},
            "approved_by": {"type": "string", "required": False, "default": "compliance_officer"},
        },
    },
    "POST /api/v1/evaluate-prompt": {
        "description": "Asigna un score de evaluación a un prompt.",
        "parameters": {
            "prompt_id": {"type": "string", "required": True},
            "score": {"type": "number", "required": True, "description": "Score 0-1."},
        },
    },
    "POST /api/v1/reset": {
        "description": "Reinicia el guardian con configuración opcional.",
        "parameters": {
            "config": {"type": "object", "required": False},
        },
    },
    "GET /api/v1/status": {
        "description": "Estado del guardian: config, schema, lineage, prompts, baselines.",
        "parameters": {},
    },
    "GET /api/v1/schema": {
        "description": "INPUT/OUTPUT cards de la API.",
        "parameters": {},
    },
    "GET /api/v1/prompts": {
        "description": "Lista todos los prompts registrados.",
        "parameters": {},
    },
    "GET /api/v1/lineage": {
        "description": "Retorna el grafo de linaje semántico completo.",
        "parameters": {},
    },
    "GET /metrics": {
        "description": "Métricas Prometheus del guardian.",
        "parameters": {},
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/process-corpus": {
        "fields": {
            "trace_id": "string",
            "decision": "string (approve|flag|reject|escalate)",
            "bias_report": "object",
            "lineage_graph": "object",
            "issues": "array",
            "duration_ms": "float",
        },
    },
    "POST /api/v1/evaluate-response": {
        "fields": {
            "trace_id": "string",
            "decision": "string",
            "hallucination_report": "object",
            "lineage_graph": "object",
            "issues": "array",
            "duration_ms": "float",
        },
    },
    "POST /api/v1/check-drift": {
        "fields": {
            "trace_id": "string",
            "decision": "string",
            "drift_report": "object",
            "issues": "array",
            "duration_ms": "float",
        },
    },
    "POST /api/v1/set-baseline": {"fields": {"status": "string"}},
    "POST /api/v1/register-prompt": {"fields": {"id": "string", "version": "string", "approved": "boolean"}},
    "POST /api/v1/approve-prompt": {"fields": {"id": "string", "version": "string", "approved": "boolean", "approved_by": "string"}},
    "POST /api/v1/evaluate-prompt": {"fields": {"id": "string", "version": "string", "evaluation_score": "float"}},
    "POST /api/v1/reset": {"fields": {"status": "string"}},
    "GET /api/v1/status": {"fields": {"config": "object", "schema": "object", "lineage_nodes": "int", "prompts_registered": "int", "prompts_approved": "int", "baselines": "array", "observability": "object"}},
    "GET /api/v1/schema": {"fields": {"input_cards": "object", "output_cards": "object"}},
    "GET /api/v1/prompts": {"fields": {"prompts": "array"}},
    "GET /api/v1/lineage": {"fields": {"trace_id": "string", "node_count": "int", "edge_count": "int", "nodes": "array", "edges": "array"}},
    "GET /metrics": {"fields": {"text": "string"}},
}


def _to_documents(items: List[Dict[str, Any]]) -> List[CorpusDocument]:
    docs = []
    for item in items:
        meta = item.get("metadata", {})
        metadata = DocumentMetadata(
            id_documento=meta.get("id_documento", item.get("id", "")),
            fuente=meta.get("fuente", ""),
            fuente_tipo=meta.get("fuente_tipo", ""),
            fecha_creacion=meta.get("fecha_creacion", ""),
            categoria_tema=meta.get("categoria_tema", ""),
            genero_autor=meta.get("genero_autor", ""),
            region_geografica=meta.get("region_geografica", ""),
            perspectiva_tematica=meta.get("perspectiva_tematica", ""),
            idioma=meta.get("idioma", "es"),
            variante_regional=meta.get("variante_regional", ""),
            contexto_cultural=meta.get("contexto_cultural", ""),
            nivel_confianza=meta.get("nivel_confianza", 0.5),
            periodo_temporal=meta.get("periodo_temporal", ""),
        )
        docs.append(CorpusDocument(
            id=item.get("id", ""),
            text=item.get("text", ""),
            metadata=metadata,
        ))
    return docs


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-162 LLMOps Guardian"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-162 — LLMOps Guardian",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/process-corpus"},
            {"method": "POST", "path": "/api/v1/evaluate-response"},
            {"method": "POST", "path": "/api/v1/check-drift"},
            {"method": "POST", "path": "/api/v1/set-baseline"},
            {"method": "POST", "path": "/api/v1/register-prompt"},
            {"method": "POST", "path": "/api/v1/approve-prompt"},
            {"method": "POST", "path": "/api/v1/evaluate-prompt"},
            {"method": "POST", "path": "/api/v1/reset"},
            {"method": "GET", "path": "/api/v1/status"},
            {"method": "GET", "path": "/api/v1/prompts"},
            {"method": "GET", "path": "/api/v1/lineage"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/process-corpus", methods=["POST"])
def process_corpus():
    data = request.get_json(force=True)
    docs = _to_documents(data.get("documents", []))
    result = _guardian.process_corpus(docs, source=data.get("source", "unknown"))
    return jsonify(result.to_dict())


@app.route("/api/v1/evaluate-response", methods=["POST"])
def evaluate_response():
    data = request.get_json(force=True)
    result = _guardian.evaluate_response(
        response=data.get("response", ""),
        retrieved_chunks=data.get("retrieved_chunks", []),
        prompt_version=data.get("prompt_version", ""),
        model=data.get("model", ""),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/check-drift", methods=["POST"])
def check_drift():
    data = request.get_json(force=True)
    result = _guardian.check_drift(
        concept_name=data.get("concept_name", ""),
        current_contexts=data.get("current_contexts", []),
        current_co_occurrences=data.get("current_co_occurrences"),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/set-baseline", methods=["POST"])
def set_baseline():
    data = request.get_json(force=True)
    _guardian.set_baseline(
        concept_name=data.get("concept_name", ""),
        contexts=data.get("contexts", []),
        co_occurrences=data.get("co_occurrences"),
    )
    return jsonify({"status": "ok"})


@app.route("/api/v1/register-prompt", methods=["POST"])
def register_prompt():
    data = request.get_json(force=True)
    result = _guardian.register_prompt(
        template=data.get("template", ""),
        version=data.get("version", ""),
        tags=data.get("tags"),
    )
    return jsonify(result)


@app.route("/api/v1/approve-prompt", methods=["POST"])
def approve_prompt():
    data = request.get_json(force=True)
    result = _guardian.approve_prompt(
        prompt_id=data.get("prompt_id", ""),
        approved_by=data.get("approved_by", "compliance_officer"),
    )
    if result is None:
        return jsonify({"error": "prompt not found"}), 404
    return jsonify(result)


@app.route("/api/v1/evaluate-prompt", methods=["POST"])
def evaluate_prompt():
    data = request.get_json(force=True)
    result = _guardian.evaluate_prompt(
        prompt_id=data.get("prompt_id", ""),
        score=data.get("score", 0.0),
    )
    if result is None:
        return jsonify({"error": "prompt not found"}), 404
    return jsonify(result)


@app.route("/api/v1/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    config_dict = data.get("config")
    config = None
    if config_dict:
        config = LLMOpsConfig(**{
            k: v for k, v in config_dict.items()
            if hasattr(LLMOpsConfig, k)
        })
    _guardian.reset(config=config)
    return jsonify({"status": "ok"})


@app.route("/api/v1/status", methods=["GET"])
def status():
    return jsonify(_guardian.get_status())


@app.route("/api/v1/prompts", methods=["GET"])
def prompts():
    return jsonify({"prompts": _guardian.prompt_registry.list_all()})


@app.route("/api/v1/lineage", methods=["GET"])
def lineage():
    return jsonify(_guardian.lineage_tracker.get_full_lineage())


@app.route("/metrics", methods=["GET"])
def metrics():
    return _guardian.get_metrics(), 200, {"Content-Type": "text/plain; charset=utf-8"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UC-162 LLMOps Guardian API")
    parser.add_argument("--port", type=int, default=5162)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
