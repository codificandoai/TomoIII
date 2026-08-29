"""FastAPI entrypoint: the Atlas demo console + JSON API for the four demos."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel

from . import __version__, agent, data, guardrails, tools
from .config import Guardrails, settings

BASE = Path(__file__).parent
app = FastAPI(title="Atlas — agent-security demo", version=__version__)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def _guardrails(overrides: dict | None) -> Guardrails:
    return settings.guardrails.merged(overrides)


# --- Models ----------------------------------------------------------------------------

class InboxRequest(BaseModel):
    message_id: str = "msg-82"
    guardrails: dict | None = None


class CodeRequest(BaseModel):
    task: str = "Summarize yesterday's transactions"
    guardrails: dict | None = None


class FinanceRequest(BaseModel):
    amount_usd: float = 5000.0
    to_account: str = "4471"
    identity: str | None = None       # e.g. "spiffe://atlas/planner", "spiffe://atlas/rogue", None
    token_preset: str | None = None   # "valid", "untrusted_signature", "expired", "wrong_audience", "none"
    token: str | None = None          # raw cryptographic JWT / SVID token
    guardrails: dict | None = None


# --- UI --------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def console(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "version": __version__,
            "inbox": data.INBOX,
            "flags": settings.guardrails.as_dict(),
            "trusted_identity": settings.finance_trusted_identity,
        },
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
def config():
    return {
        "project_id": settings.project_id or "(unset)",
        "location": settings.location,
        "model_name": settings.model_name,
        "use_llm": settings.use_llm,
        "model_armor_template": settings.model_armor_template or "(heuristic fallback)",
        "allowed_egress_hosts": list(settings.allowed_egress_hosts),
        "finance_trusted_identity": settings.finance_trusted_identity,
        "default_guardrails": settings.guardrails.as_dict(),
    }


# --- Demo 1: inbox / prompt injection + BOLA -------------------------------------------

@app.post("/api/inbox/process")
def inbox_process(req: InboxRequest):
    tools.OUTBOX.clear()
    result = agent.process_inbox(req.message_id, _guardrails(req.guardrails))
    result["outbox"] = list(tools.OUTBOX)
    return JSONResponse(result)


# --- Demo 2: code interpreter egress ---------------------------------------------------

@app.post("/api/code/run")
def code_run(req: CodeRequest):
    g = _guardrails(req.guardrails)
    result = tools.run_code(req.task, g)
    result["guardrails"] = g.as_dict()
    result["outcome"] = "exfiltrated" if result["exfiltrated"] else (
        "token_stolen" if result["token_stolen"] else "contained"
    )
    return JSONResponse(result)


# --- Demo 3: finance transfer / agent identity -----------------------------------------

@app.post("/api/finance/transfer")
def finance_transfer(req: FinanceRequest, request: Request):
    g = _guardrails(req.guardrails)

    # 1. Resolve token: raw body parameter, Authorization header, Gateway header, or simulated preset
    token = req.token
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Agent-Identity-Token" in request.headers:
            token = request.headers["X-Agent-Identity-Token"].strip()

    if not token and (req.identity is not None or req.token_preset is not None):
        token = guardrails.issue_token_for_preset(req.token_preset, req.identity)

    presented_id = req.identity
    if not presented_id and token:
        parsed = guardrails.verify_agent_token(token)
        presented_id = parsed.get("subject")

    try:
        result = tools.finance_transfer(
            req.amount_usd, req.to_account, presented_id, g, token=token
        )
        result["outcome"] = "authorized"
    except tools.ToolDenied as denied:
        verification = guardrails.verify_agent_token(token, presented_identity=presented_id)
        result = {
            "outcome": "denied",
            "label": denied.label,
            "detail": denied.detail,
            "verification": verification,
        }

    result["guardrails"] = g.as_dict()
    result["presented_identity"] = presented_id
    result["token_attached"] = bool(token)
    return JSONResponse(result)
