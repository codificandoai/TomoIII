"""
UC-290 — API REST Flask para HITL con Razonamiento Transparente.

Expone el guardian HITL como servicio REST.
Puerto por defecto: 5290
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, List

from models_290 import (
    HITLConfig,
    DecisionInput,
    HumanAction,
    ReasoningStep,
    ReasoningStepType,
)
from hitl_guardian import HITLGuardian

app = Flask(__name__)

_guardian: HITLGuardian = HITLGuardian()

# ---------------------------------------------------------------------------
# INPUT Cards
# ---------------------------------------------------------------------------

INPUT_CARDS = {
    "POST /api/v1/process-decision": {
        "description": "Procesa una decisión de UC-315 a través del pipeline HITL.",
        "parameters": {
            "decision_id": {"type": "string", "required": False, "default": ""},
            "trace_id": {"type": "string", "required": False, "default": ""},
            "context": {"type": "object", "required": False, "default": {}, "description": "Datos del contexto (current_price, predicted_move, volume, etc.)."},
            "ai_suggestion": {"type": "string", "required": True, "description": "Sugerencia de la IA (UC-315)."},
            "ai_confidence": {"type": "number", "required": True, "description": "Confianza de la IA (0-1)."},
            "ai_reasoning_steps": {"type": "array", "required": False, "default": [], "description": "Lista de pasos de razonamiento {step_type, description, evidence, confidence, source}."},
            "uc087_integrity_passed": {"type": "boolean", "required": False, "default": False, "description": "UC-087 validó integridad criptográfica."},
            "uc087_integrity_details": {"type": "object", "required": False, "default": {}},
            "uc162_llmops_passed": {"type": "boolean", "required": False, "default": False, "description": "UC-162 validó gobernanza LLMOps."},
            "uc162_llmops_details": {"type": "object", "required": False, "default": {}},
            "uc325_reflection_score": {"type": "number", "required": False, "default": 0.0, "description": "Score de auto-reflexión UC-325 (0-1)."},
            "uc325_reflection_details": {"type": "object", "required": False, "default": {}},
            "uc322_conflict_detected": {"type": "boolean", "required": False, "default": False},
            "uc322_conflict_details": {"type": "object", "required": False, "default": {}},
            "uc329_graph_paths": {"type": "array", "required": False, "default": []},
            "source_agent": {"type": "string", "required": False, "default": "uc315"},
        },
    },
    "POST /api/v1/submit-review": {
        "description": "Registra la revisión humana de un expediente escalado.",
        "parameters": {
            "dossier_id": {"type": "string", "required": True, "description": "ID del expediente pendiente."},
            "reviewer_id": {"type": "string", "required": True, "description": "ID del revisor humano."},
            "action": {"type": "string", "required": True, "description": "approve | modify | reject | request_more_info | delegate"},
            "modified_suggestion": {"type": "string", "required": False, "default": "", "description": "Sugerencia modificada (si action=modify)."},
            "override_reason": {"type": "string", "required": False, "default": ""},
            "review_notes": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/reset": {
        "description": "Reinicia el guardian con configuración opcional.",
        "parameters": {
            "config": {"type": "object", "required": False},
        },
    },
    "GET /api/v1/pending-reviews": {
        "description": "Lista expedientes pendientes de revisión humana.",
        "parameters": {},
    },
    "GET /api/v1/dossier/:id": {
        "description": "Obtiene un expediente por ID.",
        "parameters": {"id": {"type": "string", "required": True, "in": "path"}},
    },
    "GET /api/v1/present/:id": {
        "description": "Presenta un expediente para revisión humana (formato estructurado).",
        "parameters": {"id": {"type": "string", "required": True, "in": "path"}},
    },
    "GET /api/v1/audit-trail": {
        "description": "Obtiene entradas del trail de auditoría (filtrable por dossier_id o trace_id).",
        "parameters": {
            "dossier_id": {"type": "string", "required": False},
            "trace_id": {"type": "string", "required": False},
        },
    },
    "GET /api/v1/status": {
        "description": "Estado del guardian HITL.",
        "parameters": {},
    },
    "GET /api/v1/schema": {
        "description": "INPUT/OUTPUT cards de la API.",
        "parameters": {},
    },
    "GET /api/v1/results": {
        "description": "Lista todos los resultados del pipeline HITL.",
        "parameters": {},
    },
    "GET /metrics": {
        "description": "Métricas Prometheus del guardian.",
        "parameters": {},
    },
}

# ---------------------------------------------------------------------------
# OUTPUT Cards
# ---------------------------------------------------------------------------

OUTPUT_CARDS = {
    "POST /api/v1/process-decision": {
        "fields": {
            "trace_id": "string",
            "dossier_id": "string",
            "decision": "string (auto_execute|escalate|approved|modified|rejected|timeout|blocked)",
            "final_action": "string",
            "dossier": "object (expediente completo)",
            "risk_level": "string (none|low|medium|high|critical)",
            "risk_score": "float",
            "confidence_score": "float",
            "escalated": "boolean",
            "escalation_reasons": "array",
            "issues": "array",
            "duration_ms": "float",
        },
    },
    "POST /api/v1/submit-review": {
        "fields": {
            "dossier_id": "string",
            "status": "string (approved|modified|rejected|pending_review)",
            "decision": "string",
            "ai_suggestion": "string",
            "human_review": "object",
            "content_hash": "string",
        },
    },
    "POST /api/v1/reset": {"fields": {"status": "string"}},
    "GET /api/v1/pending-reviews": {"fields": {"pending": "array", "count": "int"}},
    "GET /api/v1/dossier/:id": {"fields": {"dossier": "object"}},
    "GET /api/v1/present/:id": {"fields": {"presentation": "string", "dossier": "object", "available_actions": "array", "instructions": "string"}},
    "GET /api/v1/audit-trail": {"fields": {"entries": "array", "count": "int"}},
    "GET /api/v1/status": {"fields": {"config": "object", "dossiers_total": "int", "pending_reviews": "int", "completed_reviews": "int", "audit_entries": "int", "audit_chain_verified": "boolean", "observability": "object"}},
    "GET /api/v1/schema": {"fields": {"input_cards": "object", "output_cards": "object"}},
    "GET /api/v1/results": {"fields": {"results": "array", "count": "int"}},
    "GET /metrics": {"fields": {"text": "string"}},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decision_input(data: Dict[str, Any]) -> DecisionInput:
    """Convierte un dict JSON a DecisionInput."""
    reasoning_steps = []
    for s in data.get("ai_reasoning_steps", []):
        if isinstance(s, dict):
            reasoning_steps.append(ReasoningStep(
                step_number=s.get("step_number", len(reasoning_steps) + 1),
                step_type=ReasoningStepType(s.get("step_type", "inference")),
                description=s.get("description", ""),
                evidence=s.get("evidence", ""),
                confidence=s.get("confidence", 0.0),
                source=s.get("source", "uc315"),
            ))

    return DecisionInput(
        decision_id=data.get("decision_id", ""),
        trace_id=data.get("trace_id", ""),
        context=data.get("context", {}),
        ai_suggestion=data.get("ai_suggestion", ""),
        ai_confidence=float(data.get("ai_confidence", 0.0)),
        ai_reasoning_steps=reasoning_steps,
        uc087_integrity_passed=data.get("uc087_integrity_passed", False),
        uc087_integrity_details=data.get("uc087_integrity_details", {}),
        uc162_llmops_passed=data.get("uc162_llmops_passed", False),
        uc162_llmops_details=data.get("uc162_llmops_details", {}),
        uc325_reflection_score=float(data.get("uc325_reflection_score", 0.0)),
        uc325_reflection_details=data.get("uc325_reflection_details", {}),
        uc322_conflict_detected=data.get("uc322_conflict_detected", False),
        uc322_conflict_details=data.get("uc322_conflict_details", {}),
        uc329_graph_paths=data.get("uc329_graph_paths", []),
        source_agent=data.get("source_agent", "uc315"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-290 HITL Guardian"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-290 — HITL Guardian con Razonamiento Transparente",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/process-decision"},
            {"method": "POST", "path": "/api/v1/submit-review"},
            {"method": "GET", "path": "/api/v1/pending-reviews"},
            {"method": "GET", "path": "/api/v1/dossier/<id>"},
            {"method": "GET", "path": "/api/v1/present/<id>"},
            {"method": "GET", "path": "/api/v1/audit-trail"},
            {"method": "GET", "path": "/api/v1/status"},
            {"method": "GET", "path": "/api/v1/results"},
            {"method": "POST", "path": "/api/v1/reset"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/process-decision", methods=["POST"])
def process_decision():
    data = request.get_json(force=True)
    decision_input = _to_decision_input(data)
    result = _guardian.process_decision(decision_input)
    return jsonify(result.to_dict())


@app.route("/api/v1/submit-review", methods=["POST"])
def submit_review():
    data = request.get_json(force=True)
    dossier_id = data.get("dossier_id", "")
    action_str = data.get("action", "approve")
    try:
        action = HumanAction(action_str)
    except ValueError:
        return jsonify({"error": f"invalid action: {action_str}"}), 400

    result = _guardian.submit_human_review(
        dossier_id=dossier_id,
        reviewer_id=data.get("reviewer_id", ""),
        action=action,
        modified_suggestion=data.get("modified_suggestion", ""),
        override_reason=data.get("override_reason", ""),
        review_notes=data.get("review_notes", ""),
    )
    if result is None:
        return jsonify({"error": "dossier not found or not pending"}), 404
    return jsonify(result)


@app.route("/api/v1/pending-reviews", methods=["GET"])
def pending_reviews():
    pending = _guardian.get_pending_reviews()
    return jsonify({"pending": pending, "count": len(pending)})


@app.route("/api/v1/dossier/<dossier_id>", methods=["GET"])
def get_dossier(dossier_id):
    dossier = _guardian.get_dossier(dossier_id)
    if dossier is None:
        return jsonify({"error": "dossier not found"}), 404
    return jsonify({"dossier": dossier})


@app.route("/api/v1/present/<dossier_id>", methods=["GET"])
def present_dossier(dossier_id):
    presentation = _guardian.present_dossier(dossier_id)
    if presentation is None:
        return jsonify({"error": "dossier not found"}), 404
    return jsonify(presentation)


@app.route("/api/v1/audit-trail", methods=["GET"])
def audit_trail():
    dossier_id = request.args.get("dossier_id")
    trace_id = request.args.get("trace_id")
    entries = _guardian.get_audit_trail(dossier_id=dossier_id, trace_id=trace_id)
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/v1/status", methods=["GET"])
def status():
    return jsonify(_guardian.get_status())


@app.route("/api/v1/results", methods=["GET"])
def results():
    return jsonify({"results": _guardian.get_results(), "count": len(_guardian.get_results())})


@app.route("/api/v1/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    config_dict = data.get("config")
    config = None
    if config_dict:
        config = HITLConfig(**{
            k: v for k, v in config_dict.items()
            if hasattr(HITLConfig, k)
        })
    _guardian.reset(config=config)
    return jsonify({"status": "ok"})


@app.route("/metrics", methods=["GET"])
def metrics():
    return _guardian.get_metrics(), 200, {"Content-Type": "text/plain; charset=utf-8"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UC-290 HITL Guardian API")
    parser.add_argument("--port", type=int, default=5290)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
