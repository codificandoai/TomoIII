"""
UC-325 — API REST Flask para el Motor de Razonamiento Autorreflexivo.

Expone el pipeline de razonamiento iterativo como servicio REST
con card views de entrada/salida para cada endpoint.

Puerto por defecto: 5325
"""

from flask import Flask, request, jsonify
import importlib

_mod = importlib.import_module("UC-325")
ReasoningLoopEngine = _mod.ReasoningLoopEngine

from reasoning_models import ReasoningConfig  # noqa: E402

app = Flask(__name__)

engine = ReasoningLoopEngine()

# ─── INPUT/OUTPUT CARDS ──────────────────────────────────────────────────────

INPUT_CARDS = {
    "POST /api/v1/reasoning/run": {
        "description": "Ejecuta el bucle de razonamiento autorreflexivo completo.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Consulta en lenguaje natural a razonar.",
                "example": "¿Cómo mejoran los bucles de razonamiento la precisión en la recuperación?",
            },
            "domain": {
                "type": "string",
                "required": False,
                "default": "general",
                "description": "Dominio del razonamiento (general, trading, agi, reservations).",
            },
            "max_rounds": {
                "type": "integer",
                "required": False,
                "default": 5,
                "description": "Máximo de iteraciones del bucle (1-10).",
            },
        },
    },
    "POST /api/v1/reasoning/evaluate": {
        "description": "Evalúa calidad de chunks contra un query sin ejecutar el bucle completo.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query de referencia para evaluar relevancia.",
            },
            "chunks": {
                "type": "array",
                "required": True,
                "description": "Lista de chunks a evaluar.",
                "items": {
                    "content": "string (texto del chunk)",
                    "source": "string (fuente)",
                    "score": "float (score de retrieval 0-1)",
                },
            },
        },
    },
    "POST /api/v1/reasoning/detect-hallucinations": {
        "description": "Detecta alucinaciones en un conjunto de hipótesis vs evidencia.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query original.",
            },
            "hypotheses": {
                "type": "array",
                "required": True,
                "description": "Lista de hipótesis a verificar.",
                "items": {
                    "statement": "string (afirmación)",
                    "confidence": "float (confianza 0-1)",
                    "supporting_evidence": "array of strings (textos de soporte)",
                },
            },
            "evidence": {
                "type": "array",
                "required": True,
                "description": "Lista de textos de evidencia disponible.",
                "items": "string",
            },
        },
    },
    "POST /api/v1/reasoning/refine-query": {
        "description": "Genera variantes refinadas de un query para mejorar retrieval.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Query a refinar.",
            },
            "domain": {
                "type": "string",
                "required": False,
                "default": "general",
                "description": "Dominio para contextualizar refinamientos.",
            },
            "strategy": {
                "type": "string",
                "required": False,
                "default": "expand",
                "description": "Estrategia: expand, specialize, verify, generalize.",
            },
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/reasoning/run": {
        "description": "Resultado completo del razonamiento.",
        "fields": {
            "query": "string — Query original.",
            "domain": "string — Dominio utilizado.",
            "trace_id": "string — UUID de traza para correlacionar logs/spans.",
            "answer": "string | null — Respuesta sintetizada.",
            "confidence": "float — Confianza final (0-1).",
            "verdict": "string — converged | max_rounds | stalled | insufficient_data | hallucination_detected.",
            "success": "bool — True si convergió o alcanzó max_rounds con respuesta.",
            "rounds_executed": "int — Iteraciones ejecutadas.",
            "citations": "array — Fuentes citadas con chunk_id, source, score.",
            "quality_scores": "array — Score de calidad por ronda (relevance, coverage, consistency, confidence, novelty).",
            "hypotheses": "array — Hipótesis generadas con status y confianza.",
            "gaps_remaining": "array — Gaps de conocimiento no llenados.",
            "hallucination_reports": "array — Reportes de alucinaciones por ronda.",
            "convergence_trajectory": "array of float — Trayectoria de confianza por ronda.",
            "total_chunks_retrieved": "int — Total de chunks recuperados.",
            "duration_ms": "float — Duración total en milisegundos.",
        },
    },
    "POST /api/v1/reasoning/evaluate": {
        "description": "Evaluación de calidad de retrieval.",
        "fields": {
            "avg_relevance": "float — Relevancia promedio al query.",
            "coverage": "float — Cobertura temática estimada.",
            "redundancy": "float — Ratio de chunks redundantes.",
            "quality_score": "float — Score compuesto (0-1).",
            "should_requery": "bool — Si se recomienda re-recuperar.",
        },
    },
    "POST /api/v1/reasoning/detect-hallucinations": {
        "description": "Reporte de alucinaciones detectadas.",
        "fields": {
            "detected": "bool — Si se detectaron alucinaciones.",
            "hallucination_type": "string | null — Tipo principal detectado.",
            "unsupported_claims": "array — Claims sin evidencia.",
            "fabricated_sources": "array — Fuentes fabricadas.",
            "confidence_inflation": "float — Grado de inflación de confianza.",
            "severity": "float — Severidad agregada (0-1).",
            "recommendation": "string — Acción recomendada.",
        },
    },
    "POST /api/v1/reasoning/refine-query": {
        "description": "Queries refinados generados.",
        "fields": {
            "original_query": "string — Query original.",
            "refined_queries": "array of string — Variantes generadas.",
            "strategy_used": "string — Estrategia aplicada.",
            "stats": "object — Estadísticas de refinamiento.",
        },
    },
}

# ─── ENDPOINTS ───────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    """Estado del servicio."""
    return jsonify({"status": "ok", "service": "UC-325 Reasoning Loop Engine"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    """Retorna schemas INPUT/OUTPUT cards."""
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/", methods=["GET"])
def index():
    """Información del servicio."""
    return jsonify({
        "service": "UC-325 — Motor de Bucles de Razonamiento Autorreflexivos",
        "version": "1.0.0",
        "description": (
            "Capa de razonamiento iterativo que verifica la calidad del "
            "razonamiento ANTES de decidir. Se inserta entre MP-04 (ReAct+ToT) "
            "y MP-05 (Decisión BDI)."
        ),
        "endpoints": [
            {"method": "GET", "path": "/health", "description": "Estado del servicio"},
            {"method": "GET", "path": "/api/v1/schema", "description": "INPUT/OUTPUT cards"},
            {"method": "POST", "path": "/api/v1/reasoning/run", "description": "Ejecutar bucle de razonamiento"},
            {"method": "POST", "path": "/api/v1/reasoning/evaluate", "description": "Evaluar calidad de retrieval"},
            {"method": "POST", "path": "/api/v1/reasoning/detect-hallucinations", "description": "Detectar alucinaciones"},
            {"method": "POST", "path": "/api/v1/reasoning/refine-query", "description": "Refinar queries"},
            {"method": "GET", "path": "/api/v1/reasoning/history", "description": "Historial de razonamientos"},
            {"method": "GET", "path": "/api/v1/observability/summary", "description": "Resumen de métricas"},
            {"method": "GET", "path": "/api/v1/observability/logs", "description": "Logs estructurados"},
            {"method": "GET", "path": "/api/v1/observability/spans", "description": "Trazas (spans)"},
            {"method": "GET", "path": "/metrics", "description": "Métricas Prometheus"},
        ],
    })


@app.route("/api/v1/reasoning/run", methods=["POST"])
def reasoning_run():
    """Ejecuta el bucle de razonamiento autorreflexivo completo."""
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    domain = data.get("domain", "general")
    max_rounds = data.get("max_rounds")

    if max_rounds is not None:
        max_rounds = min(max(int(max_rounds), 1), 10)

    result = engine.reason(query=query, domain=domain, max_rounds=max_rounds)
    return jsonify(result.to_dict())


@app.route("/api/v1/reasoning/evaluate", methods=["POST"])
def reasoning_evaluate():
    """Evalúa calidad de chunks contra un query."""
    data = request.get_json(force=True)
    query = data.get("query")
    chunks_data = data.get("chunks", [])

    if not query:
        return jsonify({"error": "query is required"}), 400
    if not chunks_data:
        return jsonify({"error": "chunks array is required"}), 400

    from reasoning_models import RetrievedChunk as RC
    from retrieval_evaluator import RetrievalEvaluator

    evaluator = RetrievalEvaluator()
    chunks = []
    for c in chunks_data:
        chunks.append(RC(
            content=c.get("content", ""),
            source=c.get("source", "api"),
            score=float(c.get("score", 0.5)),
        ))

    result = evaluator.evaluate_chunks(query, chunks)
    return jsonify(result)


@app.route("/api/v1/reasoning/detect-hallucinations", methods=["POST"])
def reasoning_detect_hallucinations():
    """Detecta alucinaciones en hipótesis vs evidencia."""
    data = request.get_json(force=True)
    query = data.get("query")
    hypotheses_data = data.get("hypotheses", [])
    evidence_data = data.get("evidence", [])

    if not query:
        return jsonify({"error": "query is required"}), 400

    from reasoning_models import ReasoningState, RetrievedChunk as RC, Hypothesis as H
    from hallucination_detector import HallucinationDetector

    detector = HallucinationDetector()

    state = ReasoningState(query=query)

    for i, ev in enumerate(evidence_data):
        chunk = RC(content=ev, source=f"evidence_{i}", score=0.7)
        state.all_chunks[chunk.chunk_id] = chunk

    chunk_ids = list(state.all_chunks.keys())

    for hd in hypotheses_data:
        hyp = H(
            statement=hd.get("statement", ""),
            confidence=float(hd.get("confidence", 0.5)),
            supporting_chunks=chunk_ids[:2] if chunk_ids else [],
        )
        state.hypotheses[hyp.hypothesis_id] = hyp

    report = detector.detect(state)
    return jsonify(report.to_dict())


@app.route("/api/v1/reasoning/refine-query", methods=["POST"])
def reasoning_refine_query():
    """Genera variantes refinadas de un query."""
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    domain = data.get("domain", "general")
    strategy = data.get("strategy", "expand")

    from query_refiner import QueryRefiner

    refiner = QueryRefiner()

    if strategy == "expand":
        refined = refiner.expand_initial(query, domain)
    elif strategy == "generalize":
        refined = refiner.generalize(query, [])
    else:
        refined = refiner.expand_initial(query, domain)

    return jsonify({
        "original_query": query,
        "refined_queries": refined,
        "strategy_used": strategy,
        "stats": refiner.get_stats(),
    })


@app.route("/api/v1/reasoning/history", methods=["GET"])
def reasoning_history():
    """Historial de razonamientos."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"history": engine.get_history(limit)})


@app.route("/api/v1/observability/summary", methods=["GET"])
def observability_summary():
    """Resumen de métricas de observabilidad."""
    return jsonify(engine.get_observability_summary())


@app.route("/api/v1/observability/logs", methods=["GET"])
def observability_logs():
    """Logs estructurados."""
    level = request.args.get("level")
    trace_id = request.args.get("trace_id")
    limit = request.args.get("limit", 100, type=int)
    return jsonify({
        "logs": engine.observability.get_logs(level=level, trace_id=trace_id, limit=limit)
    })


@app.route("/api/v1/observability/spans", methods=["GET"])
def observability_spans():
    """Trazas (spans)."""
    trace_id = request.args.get("trace_id")
    return jsonify({
        "spans": engine.observability.get_spans(trace_id=trace_id)
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    """Endpoint de métricas Prometheus."""
    return engine.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


# ─── SERVER ──────────────────────────────────────────────────────────────────

def run_server(port: int = 5325) -> None:
    """Inicia el servidor Flask."""
    print(f"UC-325 Reasoning Loop Engine API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
