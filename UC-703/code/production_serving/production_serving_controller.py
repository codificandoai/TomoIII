"""Controller de arquitectura de producción de serving de LLM."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from production_serving.feedback_loop import FeedbackLoop
from production_serving.guardrails import Guardrails
from production_serving.models_serving import InferenceRequest, InferenceResponse, ServingSession
from production_serving.observability_adapter import ObservabilityAdapter
from production_serving.rbac_middleware import RBACMiddleware
from production_serving.vllm_engine import VLLMInferenceEngine


class ProductionServingController:
    """
    Orquesta serving de producción de un LLM ajustado y cuantizado:
    vLLM, RBAC en endpoints, guardrails, observabilidad completa,
    integración empresarial y ciclo de retroalimentación/re-evaluación.
    """

    def __init__(
        self,
        engine: Optional[VLLMInferenceEngine] = None,
        rbac: Optional[RBACMiddleware] = None,
        guardrails: Optional[Guardrails] = None,
        observability: Optional[ObservabilityAdapter] = None,
        feedback: Optional[FeedbackLoop] = None,
    ) -> None:
        self.engine = engine or VLLMInferenceEngine()
        self.rbac = rbac or RBACMiddleware()
        self.guardrails = guardrails or Guardrails()
        self.observability = observability or ObservabilityAdapter()
        self.feedback = feedback or FeedbackLoop()
        self._sessions: Dict[str, ServingSession] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def create_session(self, principal_id: str, model_id: str, channel: str = "api") -> ServingSession:
        session = ServingSession(principal_id=principal_id, model_id=model_id, channel=channel)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ServingSession]:
        return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # Inference endpoint
    # ------------------------------------------------------------------
    def chat(
        self,
        token: str,
        prompt: str,
        model_id: str = "",
        session_id: str = "",
        params: Optional[Dict[str, Any]] = None,
        origin: str = "api",
    ) -> Dict[str, Any]:
        auth = self.rbac.authenticate(token)
        if not auth:
            return {"error": "unauthorized", "allowed": False}

        if not self.rbac.rate_limit(token):
            return {"error": "rate_limit_exceeded", "allowed": False}

        authz = self.rbac.authorize(token, "execute", "model", model_id or self.engine.default_model)
        if not authz["allowed"]:
            return {"error": "forbidden", "reason": authz["reason"], "allowed": False}

        params = params or {}

        session: Optional[ServingSession] = None
        if session_id:
            session = self._sessions.get(session_id)
        if not session:
            session = self.create_session(auth["principal_id"], model_id or self.engine.default_model, origin)

        request = InferenceRequest(
            session_id=session.session_id,
            principal_id=auth["principal_id"],
            prompt=prompt,
            model_id=model_id or session.model_id,
            params=params or {},
            trace_id=f"trace-{time.time()}",
        )
        session.requests.append(request.request_id)

        # Input guardrails
        input_guard = self.guardrails.evaluate(prompt)
        if input_guard.blocked:
            response = InferenceResponse(
                request_id=request.request_id,
                session_id=session.session_id,
                model_id=request.model_id,
                generated_text="",
                guardrails=input_guard,
            )
            self.observability.emit(request, response, origin=origin)
            return {"allowed": True, "blocked": True, "guardrails": input_guard.to_dict(), "response": response.to_dict()}

        response = self.engine.generate(request, max_tokens=params.get("max_tokens", 128))
        output_guard = self.guardrails.filter(prompt, response.generated_text)
        response.guardrails = output_guard
        if output_guard.blocked:
            response.generated_text = "[blocked by guardrails]"

        self.observability.emit(request, response, origin=origin)
        return {"allowed": True, "blocked": False, "response": response.to_dict(), "session_id": session.session_id}

    # ------------------------------------------------------------------
    # Enterprise connectors
    # ------------------------------------------------------------------
    def enterprise_chat(self, token: str, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return self.chat(token, prompt, origin="chat", **kwargs)

    def crm_connector(self, token: str, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return self.chat(token, prompt, origin="crm", **kwargs)

    def erp_connector(self, token: str, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return self.chat(token, prompt, origin="erp", **kwargs)

    # ------------------------------------------------------------------
    # Feedback and re-evaluation
    # ------------------------------------------------------------------
    def submit_feedback(
        self,
        request_id: str,
        session_id: str,
        principal_id: str,
        signal_type: str,
        value: Any,
        comment: str = "",
    ) -> Dict[str, Any]:
        fb = self.feedback.collect_from_api(request_id, session_id, principal_id, signal_type, value, comment)
        return fb.to_dict()

    def re_evaluate_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        # Find telemetry record by request_id and re-evaluate
        records = [r for r in self.observability._records if r.request_id == request_id]
        if not records:
            return None
        record = records[0]
        request = InferenceRequest(
            request_id=record.request_id,
            session_id=record.trace_id,
            principal_id=record.principal_id,
            prompt=record.prompt,
            model_id=record.model_id,
            trace_id=record.trace_id,
        )
        from production_serving.models_serving import InferenceResponse, TokenUsage
        response = InferenceResponse(
            request_id=record.request_id,
            session_id=record.trace_id,
            model_id=record.model_id,
            generated_text=record.response,
            usage=record.token_usage,
            latency_ms=record.latency_ms,
            guardrails=record.guardrails,
        )
        result = self.feedback.re_evaluate(request, response)
        return result.to_dict()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def dashboard(self) -> Dict[str, Any]:
        return {
            "sessions": len(self._sessions),
            "inferences": len(self.observability._records),
            "metrics": self.observability.get_metrics(),
            "feedback_summary": self.feedback.feedback_summary(),
            "loaded_models": list(self.engine._loaded_models.keys()),
        }
