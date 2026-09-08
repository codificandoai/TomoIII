"""Flask API for UC-309 with INPUT/OUTPUT cards and RBAC."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from flask import Flask, request, Response, jsonify

from models_309 import CanonicalEvent
from observability_orchestrator import ObservabilityOrchestrator
from trace_store import has_permission

INPUT_CARDS: Dict[str, Any] = {
    "event": {
        "trace_id": "str (required)",
        "span_id": "str (required)",
        "parent_span_id": "str?",
        "execution_id": "str?",
        "session_id": "str? (not used as label)",
        "agent_id": "str?",
        "agent_version": "str?",
        "step": "int",
        "event_type": "str (enum)",
        "model_request_meta": "{model, model_provider, max_tokens, temperature, tools_declared}",
        "model_completion_meta": "{model, finish_reason, tool_calls_proposed}",
        "structured_reasoning_summary": "str? (no raw chain-of-thought)",
        "action_proposed": "dict?",
        "action_proposed_hash": "str?",
        "uc300": "{tool_name, tool_params, policy_verdict, authorized, toctou_check, approved_action_hash}",
        "uc290": "{decision_id, risk_score, override, escalation, human_in_the_loop}",
        "uc324": "{containment_type, contained_action}",
        "tool_name": "str?",
        "tool_result_status": "str?",
        "observation_summary": "str?",
        "observed_action_hash": "str?",
        "error": "str?",
        "final_outcome": "str?",
        "latency_ms": "float?",
        "input_tokens": "int",
        "output_tokens": "int",
        "estimated_cost_usd": "float?",
        "retries": "int",
        "loop_count": "int",
        "labels": "dict[str,str]?",
    },
    "batch": {"events": ["list of event cards"]},
    "retention": {"max_records": "int?", "retention_seconds": "int?", "role": "admin"},
    "alert_ack": {"alert_id": "str", "user": "str?", "role": "analyst or admin"},
}

OUTPUT_CARDS: Dict[str, Any] = {
    "health": {"status": "ok"},
    "schema": {"input": INPUT_CARDS, "output": "per-endpoint"},
    "event_response": {"canonical_event": "CanonicalEvent as dict", "redacted": "bool", "stored": "bool"},
    "trace": {"trace_id": "str", "events": ["..."], "role": "str"},
    "validation": {"trace_id": "str", "valid": "bool", "issues": ["..."]},
    "metrics": {"counters": "dict", "gauges": "dict", "last_update": "float"},
    "alerts": ["alert dicts"],
    "status": ["events", "traces", "alerts", "active_alerts"],
}


def _get_role(req) -> Optional[str]:
    header = req.headers.get("X-UC309-Role")
    if header:
        return header
    body = req.get_json(silent=True, force=True)
    if body and isinstance(body, dict):
        return body.get("role")
    return None


def _safe_json(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=True, sort_keys=True)


def create_app(orchestrator: Optional[ObservabilityOrchestrator] = None) -> Flask:
    app = Flask(__name__)
    orch = orchestrator or ObservabilityOrchestrator()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/schema", methods=["GET"])
    def schema():
        return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})

    @app.route("/events", methods=["POST"])
    def events():
        body = request.get_json(silent=True, force=True)
        if not body:
            return jsonify({"error": "JSON body required"}), 400
        try:
            ev = orch.emit(body)
            return jsonify({"canonical_event": ev.to_dict() if ev else None, "stored": ev is not None})
        except Exception as e:
            return jsonify({"error": str(e)}), 422

    @app.route("/batch", methods=["POST"])
    def batch():
        body = request.get_json(silent=True, force=True)
        if not body or not isinstance(body, list):
            return jsonify({"error": "JSON array required"}), 400
        out = []
        for raw in body:
            try:
                ev = orch.emit(raw)
                out.append({"ok": True, "canonical_event": ev.to_dict() if ev else None})
            except Exception as e:
                out.append({"ok": False, "error": str(e)})
        return jsonify(out)

    @app.route("/traces", methods=["GET"])
    def traces():
        role = _get_role(request)
        try:
            return jsonify({"traces": orch.store.list_traces(role=role)})
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route("/traces/<trace_id>", methods=["GET"])
    @app.route("/trace/<trace_id>", methods=["GET"])
    def trace(trace_id: str):
        role = _get_role(request)
        try:
            return jsonify({"trace_id": trace_id, "events": orch.get_trace(trace_id, role=role)})
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route("/traces/<trace_id>/validate", methods=["POST", "GET"])
    def validate_trace(trace_id: str):
        role = _get_role(request)
        try:
            return jsonify(orch.validate_trace(trace_id, role=role))
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route("/metrics", methods=["GET"])
    def metrics():
        return Response(orch.export_prometheus_text(), mimetype="text/plain; version=0.0.4")

    @app.route("/logs", methods=["GET"])
    def logs():
        role = _get_role(request)
        if not role or not has_permission(role, "logs"):
            return jsonify({"error": "insufficient role for logs"}), 403
        return Response("\n".join(orch.export_loki()), mimetype="application/x-ndjson")

    @app.route("/spans", methods=["GET"])
    def spans():
        role = _get_role(request)
        if not role or not has_permission(role, "traces"):
            return jsonify({"error": "insufficient role for spans"}), 403
        return jsonify(orch.export_tempo())

    @app.route("/alerts", methods=["GET"])
    def alerts():
        role = _get_role(request)
        if not role or not has_permission(role, "alerts"):
            return jsonify({"error": "insufficient role for alerts"}), 403
        ack = request.args.get("acknowledged")
        if ack is not None:
            ack = ack.lower() in ("true", "1", "yes")
        return jsonify(orch.get_alerts(acknowledged=ack))

    @app.route("/alerts/<alert_id>/ack", methods=["POST"])
    def ack_alert(alert_id: str):
        role = _get_role(request)
        if not role or not has_permission(role, "alerts"):
            return jsonify({"error": "insufficient role for alert acknowledgement"}), 403
        body = request.get_json(silent=True, force=True) or {}
        user = body.get("user")
        ok = orch.acknowledge_alert(alert_id, user)
        return jsonify({"acknowledged": ok, "alert_id": alert_id})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify(orch.status())

    @app.route("/retention", methods=["POST"])
    def retention():
        body = request.get_json(silent=True, force=True) or {}
        role = body.get("role") or _get_role(request)
        try:
            orch.retention(
                max_records=body.get("max_records"),
                retention_seconds=body.get("retention_seconds"),
                role=role,
            )
            return jsonify({"ok": True})
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route("/reset", methods=["POST"])
    def reset():
        body = request.get_json(silent=True, force=True) or {}
        role = body.get("role") or _get_role(request)
        try:
            orch.reset(role=role)
            return jsonify({"ok": True})
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    return app


def main():
    port = int(os.environ.get("UC309_API_PORT", "8500"))
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
