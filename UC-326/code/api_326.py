"""
UC-326 — API REST Flask para MAQRI (Memory-Augmented Query Refinement Iterative).

Expone el sistema de memoria y búsqueda inteligente como servicio REST.
Puerto por defecto: 5326
"""

from flask import Flask, request, jsonify
import importlib

_mod = importlib.import_module("UC-326")
UCMaqriLayer = _mod.UCMaqriLayer
default_kb = _mod.default_kb

from maqri_models import MaqriConfig  # noqa: E402

app = Flask(__name__)

# Capa global con knowledge base sembrada
layer = UCMaqriLayer(seed_kb=default_kb())

# ─── INPUT/OUTPUT CARDS ────────────────────────────────────────────────────────

INPUT_CARDS = {
    "POST /api/v1/maqri/search": {
        "description": "Ejecuta una búsqueda MAQRI iterativa con memoria.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Consulta en lenguaje natural.",
                "example": "How does MAQRI improve iterative query refinement?",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Contexto adicional de la tarea actual.",
            },
            "domain": {
                "type": "string",
                "required": False,
                "default": "general",
                "description": "Dominio del conocimiento (agi, trading, reservations).",
            },
            "max_iterations": {
                "type": "integer",
                "required": False,
                "default": 5,
                "description": "Máximo de iteraciones de refinamiento (1-10).",
            },
        },
    },
    "POST /api/v1/maqri/documents": {
        "description": "Indexa documentos en la memoria semántica.",
        "parameters": {
            "documents": {
                "type": "array",
                "required": True,
                "description": "Lista de documentos a indexar.",
                "items": {
                    "content": "string (texto del documento)",
                    "source": "string (fuente, default 'api')",
                    "metadata": "object (opcional)",
                },
            },
            "source": {
                "type": "string",
                "required": False,
                "default": "api",
                "description": "Fuente por defecto de los documentos.",
            },
        },
    },
    "POST /api/v1/maqri/experience": {
        "description": "Agrega una experiencia a la memoria episódica.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query original de la experiencia.",
            },
            "refined_query": {
                "type": "string",
                "required": True,
                "description": "Query refinado que se usó.",
            },
            "relevance_score": {
                "type": "number",
                "required": False,
                "default": 0.5,
                "description": "Score de relevancia obtenido (0-1).",
            },
            "missing_info": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Información que faltaba.",
            },
            "failure_reason": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Razón de fracaso si aplica.",
            },
            "success": {
                "type": "boolean",
                "required": False,
                "default": False,
                "description": "Si la búsqueda fue exitosa.",
            },
        },
    },
    "POST /api/v1/maqri/critic": {
        "description": "Evalúa calidad de documentos contra un query.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query de referencia.",
            },
            "documents": {
                "type": "array",
                "required": True,
                "description": "Lista de textos de documentos.",
                "items": "string",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Contexto de trabajo acumulado.",
            },
        },
    },
    "POST /api/v1/maqri/refine": {
        "description": "Refina un query usando memoria y estrategias de divergencia.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query a refinar.",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Contexto de la tarea.",
            },
            "failed_approaches": {
                "type": "array",
                "required": False,
                "default": [],
                "description": "Lista de razones de fracaso previas.",
                "items": "string",
            },
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/maqri/search": {
        "description": "Resultado de una búsqueda MAQRI.",
        "fields": {
            "query": "string — Query original.",
            "trace_id": "string — UUID de traza.",
            "final_query": "string — Query final refinado.",
            "verdict": "string — converged | max_iterations | insufficient_data.",
            "success": "bool — True si la búsqueda completó.",
            "iterations_executed": "int — Iteraciones ejecutadas.",
            "final_score": "float — Score de confianza final (0-1).",
            "total_docs": "int — Total de documentos únicos devueltos.",
            "unique_facts": "int — Hechos únicos acumulados.",
            "duration_ms": "float — Duración total en ms.",
            "docs": "array — Top documentos recuperados.",
            "iterations": "array — Detalle por iteración.",
            "episodes": "array — Episodios guardados en memoria.",
            "working_memory": "object — Memoria de trabajo final.",
        },
    },
    "POST /api/v1/maqri/documents": {
        "description": "Confirmación de indexación.",
        "fields": {
            "indexed": "int — Número de documentos indexados.",
            "doc_ids": "array — IDs de los documentos indexados.",
            "source": "string — Fuente asignada.",
            "semantic_stats": "object — Estadísticas de la memoria semántica.",
        },
    },
    "POST /api/v1/maqri/experience": {
        "description": "Episodio guardado.",
        "fields": {
            "episode_id": "string — ID del episodio.",
            "query": "string — Query original.",
            "refined_query": "string — Query refinado.",
            "relevance_score": "float — Score de relevancia.",
            "success": "bool — Si fue exitoso.",
            "timestamp": "float — Timestamp.",
        },
    },
    "POST /api/v1/maqri/critic": {
        "description": "Evaluación del Critic.",
        "fields": {
            "relevance_score": "float — Relevancia (0-1).",
            "coverage_score": "float — Cobertura (0-1).",
            "novelty_score": "float — Novedad (0-1).",
            "overall_score": "float — Score compuesto.",
            "confidence": "float — Confianza.",
            "missing_info": "string — Información faltante.",
            "failure_reason": "string — Razón de fracaso.",
        },
    },
    "POST /api/v1/maqri/refine": {
        "description": "Queries refinados generados.",
        "fields": {
            "original_query": "string — Query original.",
            "variants": "array — Variantes de query generadas.",
            "num_variants": "int — Cantidad de variantes.",
        },
    },
}

# ─── ENDPOINTS ─────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    """Estado del servicio."""
    return jsonify({"status": "ok", "service": "UC-326 MAQRI Memory & Search Layer"})


@app.route("/", methods=["GET"])
def index():
    """Información del servicio."""
    return jsonify({
        "service": "UC-326 — MAQRI: Sistema de Memoria y Búsqueda Inteligente",
        "version": "1.0.0",
        "description": (
            "Capa de memoria y búsqueda que alimenta a UC-325 con retrieval "
            "inteligente, iterativo y con memoria episódica/semántica."
        ),
        "endpoints": [
            {"method": "GET", "path": "/health", "description": "Estado del servicio"},
            {"method": "GET", "path": "/api/v1/schema", "description": "INPUT/OUTPUT cards"},
            {"method": "POST", "path": "/api/v1/maqri/search", "description": "Búsqueda MAQRI iterativa"},
            {"method": "POST", "path": "/api/v1/maqri/documents", "description": "Indexar documentos"},
            {"method": "POST", "path": "/api/v1/maqri/experience", "description": "Agregar experiencia"},
            {"method": "POST", "path": "/api/v1/maqri/critic", "description": "Evaluar retrieval con Critic"},
            {"method": "POST", "path": "/api/v1/maqri/refine", "description": "Refinar query"},
            {"method": "GET", "path": "/api/v1/maqri/history", "description": "Historial de búsquedas"},
            {"method": "GET", "path": "/api/v1/maqri/stats", "description": "Estadísticas de memoria"},
            {"method": "GET", "path": "/api/v1/maqri/logs", "description": "Logs estructurados"},
            {"method": "GET", "path": "/api/v1/maqri/spans", "description": "Trazas (spans)"},
            {"method": "GET", "path": "/metrics", "description": "Métricas Prometheus"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    """Retorna schemas INPUT/OUTPUT cards."""
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/maqri/search", methods=["POST"])
def maqri_search():
    """Ejecuta una búsqueda MAQRI iterativa."""
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    context = data.get("context", "")
    domain = data.get("domain", "general")
    max_iterations = data.get("max_iterations")
    if max_iterations is not None:
        max_iterations = min(max(int(max_iterations), 1), 10)

    result = layer.retrieve_with_context(
        query=query,
        context=context,
        domain=domain,
        max_iterations=max_iterations,
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/maqri/documents", methods=["POST"])
def maqri_documents():
    """Indexa documentos en memoria semántica."""
    data = request.get_json(force=True)
    documents = data.get("documents", [])
    source = data.get("source", "api")

    if not documents:
        return jsonify({"error": "documents array is required"}), 400
    if not isinstance(documents, list):
        return jsonify({"error": "documents must be an array"}), 400

    indexed = layer.add_documents(documents, source=source)
    return jsonify({
        "indexed": len(indexed),
        "doc_ids": [d.doc_id for d in indexed],
        "source": source,
        "semantic_stats": layer.engine.semantic.get_stats(),
    })


@app.route("/api/v1/maqri/experience", methods=["POST"])
def maqri_experience():
    """Agrega una experiencia a la memoria episódica."""
    data = request.get_json(force=True)
    query = data.get("query")
    refined_query = data.get("refined_query")

    if not query or not refined_query:
        return jsonify({"error": "query and refined_query are required"}), 400

    from maqri_models import SearchEpisode, RetrievedDocument

    docs_raw = data.get("documents", [])
    docs = []
    for d in docs_raw:
        if isinstance(d, str):
            docs.append(RetrievedDocument(content=d, source="api"))
        elif isinstance(d, dict):
            docs.append(RetrievedDocument(
                content=d.get("content", ""),
                source=d.get("source", "api"),
                score=float(d.get("score", 0.5)),
            ))

    episode = layer.add_experience(
        query=query,
        refined_query=refined_query,
        docs=docs,
        relevance_score=float(data.get("relevance_score", 0.5)),
        missing_info=data.get("missing_info", ""),
        failure_reason=data.get("failure_reason", ""),
    )
    return jsonify(episode.to_dict())


@app.route("/api/v1/maqri/critic", methods=["POST"])
def maqri_critic():
    """Evalúa documentos contra un query con el Critic."""
    data = request.get_json(force=True)
    query = data.get("query")
    documents = data.get("documents", [])
    context = data.get("context", "")

    if not query:
        return jsonify({"error": "query is required"}), 400
    if not documents:
        return jsonify({"error": "documents array is required"}), 400

    from critic_evaluator import CriticEvaluator
    from maqri_models import RetrievedDocument, WorkingMemory

    critic = CriticEvaluator()
    docs = [RetrievedDocument(content=d, source="api") for d in documents]
    wm = WorkingMemory(accumulated_facts=[context] if context else [])
    assessment = critic.evaluate(query=query, docs=docs, working_memory=wm)
    return jsonify(assessment.to_dict())


@app.route("/api/v1/maqri/refine", methods=["POST"])
def maqri_refine():
    """Refina un query usando memoria y divergencia."""
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    context = data.get("context", "")
    failed_approaches = data.get("failed_approaches", [])

    variants = layer.engine.refiner.generate_variants(
        query=query,
        context=context,
        failed_approaches=failed_approaches,
    )

    return jsonify({
        "original_query": query,
        "variants": [v.to_dict() for v in variants],
        "num_variants": len(variants),
    })


@app.route("/api/v1/maqri/history", methods=["GET"])
def maqri_history():
    """Historial de búsquedas MAQRI."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"history": layer.engine.get_history(limit)})


@app.route("/api/v1/maqri/stats", methods=["GET"])
def maqri_stats():
    """Estadísticas de memoria."""
    return jsonify(layer.get_stats())


@app.route("/api/v1/maqri/logs", methods=["GET"])
def maqri_logs():
    """Logs estructurados."""
    level = request.args.get("level")
    trace_id = request.args.get("trace_id")
    limit = request.args.get("limit", 100, type=int)
    return jsonify({
        "logs": layer.engine.observability.get_logs(level=level, trace_id=trace_id, limit=limit)
    })


@app.route("/api/v1/maqri/spans", methods=["GET"])
def maqri_spans():
    """Trazas (spans)."""
    trace_id = request.args.get("trace_id")
    return jsonify({
        "spans": layer.engine.observability.get_spans(trace_id=trace_id)
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    """Métricas Prometheus."""
    return layer.engine.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


# ─── SERVER ──────────────────────────────────────────────────────────────────

def run_server(port: int = 5326) -> None:
    """Inicia el servidor Flask."""
    print(f"UC-326 MAQRI API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
