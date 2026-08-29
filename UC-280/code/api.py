"""Flask REST API and input/output card views for UC-280."""
from __future__ import annotations

from flask import Flask, jsonify, request

from models import PlannerType
from orchestrator import GoalOrchestrator
from store import GoalStore

app = Flask(__name__)
orchestrator = GoalOrchestrator()

INPUT_CARDS = [
    {"endpoint": "POST /api/v1/goals", "description": "Decompose an abstract objective", "parameters": [
        {"name": "description", "type": "string", "required": True},
        {"name": "planner", "type": "string", "required": False, "default": "langgraph", "enum": [p.value for p in PlannerType]},
        {"name": "context", "type": "object", "required": False}]},
    {"endpoint": "POST /api/v1/goals/{goal_id}/execute", "description": "Execute ready tasks in parallel DAG waves", "parameters": [
        {"name": "goal_id", "type": "path:string", "required": True}]},
]
OUTPUT_CARDS = [
    {"endpoint": "POST /api/v1/goals", "fields": [
        {"name": "goal", "type": "object"}, {"name": "waves", "type": "array<array<task_id>>"}]},
    {"endpoint": "POST /api/v1/goals/{goal_id}/execute", "fields": [
        {"name": "status", "type": "string"}, {"name": "completed", "type": "integer"},
        {"name": "failed", "type": "integer"}, {"name": "blocked", "type": "integer"},
        {"name": "events", "type": "array"}, {"name": "audit_hash", "type": "sha256"}]},
]


def ok(data, status=200):
    return jsonify({"status": "ok", "data": data}), status


def error(message, status=400):
    return jsonify({"status": "error", "message": message}), status


@app.errorhandler(ValueError)
def value_error(exc):
    return error(str(exc))


@app.errorhandler(KeyError)
def key_error(exc):
    return error(str(exc).strip("'"), 404)


@app.get("/health")
def health():
    return ok({"service": "uc280-goal-decomposition", "ready": True})


@app.get("/api/v1/schema")
def schema():
    return ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.post("/api/v1/goals")
def create_goal():
    data = request.get_json(silent=True) or {}
    if not data.get("description"):
        return error("description is required")
    goal = orchestrator.create_plan(data["description"], data.get("context", {}),
                                    PlannerType(data.get("planner", "langgraph")))
    view = orchestrator.plan_view(goal.id)
    return ok(view, 201)


@app.get("/api/v1/goals")
def list_goals():
    return ok([goal.public_dict() for goal in orchestrator.store.list()])


@app.get("/api/v1/goals/<goal_id>")
def get_goal(goal_id):
    return ok(orchestrator.plan_view(goal_id))


@app.post("/api/v1/goals/<goal_id>/execute")
def execute_goal(goal_id):
    summary = orchestrator.execute(goal_id)
    data = summary.public_dict()
    data["audit_hash"] = summary.audit_hash()
    return ok(data)


@app.get("/api/v1/goals/<goal_id>/events")
def goal_events(goal_id):
    orchestrator.store.get(goal_id)
    return ok(orchestrator.store.events(goal_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5280, debug=False)