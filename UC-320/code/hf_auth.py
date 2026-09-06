"""UC-320 — AAA: Autenticación, Autorización y Acceso con Hugging Face.

Los usuarios se autentican en UTRON.AI con su cuenta de Hugging Face.
El token HF del usuario viene en el header `Authorization: Bearer hf_xxx`
de cada request API REST.

UTRON.AI accede directamente con el catálogo de modelos, datasets y
spaces de Hugging Face sin imponer restricciones. Los usuarios pueden
descargar, adaptar y reentrenar pesos. Si el usuario utiliza GPUs de
Hugging Face para entrenamiento, los cargos van a la cuenta HF del
usuario, no a UTRON.AI.

Integración oficial: Hugging Face Hub SDK (huggingface_hub).
  - whoami() para validar token y obtener usuario
  - InferenceClient(token=user_token) para inferencia
  - HfApi(token=user_token) para endpoints, datasets, spaces, model cards
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, request, g


# ---------------------------------------------------------------------------
# Roles y permisos
# ---------------------------------------------------------------------------
class HFRole(str, Enum):
    """Roles de usuario en UTRON.AI (mapeados desde HF)."""
    VIEWER = "viewer"        # Solo lectura: explorar catálogo, inferencia read-only
    USER = "user"            # Inferencia + descargar modelos + adaptar pesos
    DEVELOPER = "developer"  # + Entrenar, crear endpoints, spaces, PEFT
    ADMIN = "admin"          # + Eliminar endpoints, spaces, promover modelos


# Permisos por rol
ROLE_PERMISSIONS: Dict[HFRole, Set[str]] = {
    HFRole.VIEWER: {
        "inference:read",
        "catalog:browse",
        "models:download",
        "datasets:read",
        "spaces:read",
        "model_cards:read",
    },
    HFRole.USER: {
        "inference:read",
        "catalog:browse",
        "models:download",
        "models:adapt",          # PEFT / LoRA
        "datasets:read",
        "datasets:load",
        "spaces:read",
        "spaces:create",
        "model_cards:read",
        "benchmark:run",
    },
    HFRole.DEVELOPER: {
        "inference:read",
        "catalog:browse",
        "models:download",
        "models:adapt",
        "models:train",          # Trainer
        "models:push",           # Push al Hub
        "datasets:read",
        "datasets:load",
        "datasets:transform",
        "endpoints:create",
        "endpoints:stop",
        "endpoints:health",
        "spaces:read",
        "spaces:create",
        "spaces:stop",
        "model_cards:read",
        "model_cards:create",
        "model_cards:approve",
        "model_cards:push",
        "benchmark:run",
        "evaluate:compute",
    },
    HFRole.ADMIN: {
        # Admin tiene todos los permisos
        "inference:read",
        "catalog:browse",
        "models:download",
        "models:adapt",
        "models:train",
        "models:push",
        "datasets:read",
        "datasets:load",
        "datasets:transform",
        "endpoints:create",
        "endpoints:stop",
        "endpoints:delete",
        "endpoints:health",
        "spaces:read",
        "spaces:create",
        "spaces:stop",
        "spaces:delete",
        "model_cards:read",
        "model_cards:create",
        "model_cards:approve",
        "model_cards:push",
        "benchmark:run",
        "evaluate:compute",
        "training:promote",
    },
}

# Mapeo endpoint -> permiso requerido
ENDPOINT_PERMISSIONS: Dict[str, str] = {
    # Inference
    "POST /api/v1/sentiment": "inference:read",
    "POST /api/v1/embedding": "inference:read",
    "POST /api/v1/classify": "inference:read",
    "POST /api/v1/benchmark": "benchmark:run",
    # Models
    "GET /api/v1/models": "catalog:browse",
    # Templates
    "GET /api/v1/templates": "catalog:browse",
    "GET /api/v1/templates/<template_id>": "catalog:browse",
    # Endpoints
    "GET /api/v1/endpoints": "catalog:browse",
    "POST /api/v1/endpoints": "endpoints:create",
    "GET /api/v1/endpoints/<endpoint_id>/health": "endpoints:health",
    "POST /api/v1/endpoints/<endpoint_id>/stop": "endpoints:stop",
    "DELETE /api/v1/endpoints/<endpoint_id>": "endpoints:delete",
    # Datasets
    "GET /api/v1/datasets": "datasets:read",
    "POST /api/v1/datasets/load": "datasets:load",
    "POST /api/v1/datasets/validate": "datasets:read",
    "POST /api/v1/datasets/transform": "datasets:transform",
    # Trainer
    "POST /api/v1/trainer/train": "models:train",
    "GET /api/v1/trainer/jobs": "models:train",
    "POST /api/v1/training/submit": "models:train",
    "POST /api/v1/training/run": "models:train",
    "POST /api/v1/training/promote": "training:promote",
    "GET /api/v1/training/jobs": "models:train",
    # PEFT
    "GET /api/v1/peft/adapters": "models:adapt",
    "POST /api/v1/peft/adapters": "models:adapt",
    "POST /api/v1/peft/adapters/<adapter_id>/save": "models:push",
    # Evaluate
    "POST /api/v1/evaluate/compute": "evaluate:compute",
    "POST /api/v1/evaluate/compare": "evaluate:compute",
    "GET /api/v1/evaluate/results": "evaluate:compute",
    # Spaces
    "GET /api/v1/spaces": "spaces:read",
    "POST /api/v1/spaces": "spaces:create",
    "POST /api/v1/spaces/<space_id>/stop": "spaces:stop",
    "DELETE /api/v1/spaces/<space_id>": "spaces:delete",
    # Model Cards
    "GET /api/v1/model-cards": "model_cards:read",
    "POST /api/v1/model-cards": "model_cards:create",
    "GET /api/v1/model-cards/<path:model_id>": "model_cards:read",
    "GET /api/v1/model-cards/<path:model_id>/markdown": "model_cards:read",
    "POST /api/v1/model-cards/<path:model_id>/approve": "model_cards:approve",
    "POST /api/v1/model-cards/<path:model_id>/push": "model_cards:push",
    # Audit
    "GET /api/v1/audit": "catalog:browse",
}


# ---------------------------------------------------------------------------
# Sesión de usuario
# ---------------------------------------------------------------------------
@dataclass
class UserSession:
    """Sesión de usuario autenticado via Hugging Face."""

    session_id: str
    hf_token: str
    hf_username: str
    hf_name: str = ""
    hf_email: str = ""
    hf_orgs: List[str] = field(default_factory=list)
    role: HFRole = HFRole.USER
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    token_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "hf_username": self.hf_username,
            "hf_name": self.hf_name,
            "hf_orgs": self.hf_orgs,
            "role": self.role.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "token_hash": self.token_hash,
        }

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    def is_expired(self) -> bool:
        return time.time() > self.expires_at if self.expires_at else False


# ---------------------------------------------------------------------------
# Mock de usuarios HF para tests (sin red)
# ---------------------------------------------------------------------------
MOCK_HF_USERS: Dict[str, Dict[str, Any]] = {
    "hf_mock_token_viewer": {
        "username": "mock_viewer",
        "name": "Mock Viewer",
        "email": "viewer@mock.ai",
        "orgs": [],
        "role": HFRole.VIEWER,
    },
    "hf_mock_token_user": {
        "username": "mock_user",
        "name": "Mock User",
        "email": "user@mock.ai",
        "orgs": ["mock-org"],
        "role": HFRole.USER,
    },
    "hf_mock_token_developer": {
        "username": "mock_developer",
        "name": "Mock Developer",
        "email": "dev@mock.ai",
        "orgs": ["mock-org", "dev-team"],
        "role": HFRole.DEVELOPER,
    },
    "hf_mock_token_admin": {
        "username": "mock_admin",
        "name": "Mock Admin",
        "email": "admin@mock.ai",
        "orgs": ["mock-org", "admin-team"],
        "role": HFRole.ADMIN,
    },
}


# ---------------------------------------------------------------------------
# HFAuth — Autenticación con Hugging Face
# ---------------------------------------------------------------------------
class HFAuth:
    """Autenticación con Hugging Face via Hub SDK.

    En producción usa huggingface_hub.whoami(token) para validar el token
    del usuario y obtener su identidad. En modo mock usa tokens
    deterministas para tests.

    El token del usuario se pasa a todos los servicios HF para que:
      - Los cargos de GPU vayan a la cuenta del usuario
      - El acceso a repos privados del usuario funcione
      - UTRON.AI no necesite un token propio
    """

    SESSION_TTL = 3600  # 1 hora

    def __init__(self, backend: str = "mock") -> None:
        self.backend = backend
        self._sessions: Dict[str, UserSession] = {}  # session_id -> session
        self._token_to_session: Dict[str, str] = {}  # token_hash -> session_id

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def authenticate(self, hf_token: str) -> Tuple[bool, Optional[UserSession], str]:
        """Autentica un token de HF y retorna la sesión del usuario.

        Returns: (success, session, error_message)
        """
        if not hf_token:
            return False, None, "Missing Hugging Face token"

        token_hash = self._hash_token(hf_token)

        # Sesión existente válida
        existing_sid = self._token_to_session.get(token_hash)
        if existing_sid:
            session = self._sessions.get(existing_sid)
            if session and not session.is_expired():
                return True, session, ""

        # Validar token con HF
        if self.backend == "huggingface":
            try:
                from huggingface_hub import whoami
                user_info = whoami(token=hf_token)
                username = user_info.get("name", "")
                name = user_info.get("fullname", "") or username
                email = user_info.get("email", "")
                orgs = [o.get("name", "") for o in user_info.get("orgs", [])] if isinstance(user_info.get("orgs"), list) else []
                # Determinar rol: si es pro/enterprise → developer, si tiene orgs → user, sino viewer
                role = HFRole.USER
                if orgs:
                    role = HFRole.DEVELOPER
                # Admin se asigna manualmente via UTRON config
            except Exception as exc:
                return False, None, f"HF authentication failed: {exc}"
        else:
            # Mock: tokens deterministas
            mock_user = MOCK_HF_USERS.get(hf_token)
            if not mock_user:
                return False, None, "Invalid Hugging Face token (mock mode)"
            username = mock_user["username"]
            name = mock_user["name"]
            email = mock_user["email"]
            orgs = mock_user["orgs"]
            role = mock_user["role"]

        # Crear sesión
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = UserSession(
            session_id=session_id,
            hf_token=hf_token,
            hf_username=username,
            hf_name=name,
            hf_email=email,
            hf_orgs=orgs,
            role=role,
            created_at=time.time(),
            expires_at=time.time() + self.SESSION_TTL,
            token_hash=token_hash,
        )
        self._sessions[session_id] = session
        self._token_to_session[token_hash] = session_id
        return True, session, ""

    def get_session(self, session_id: str) -> Optional[UserSession]:
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            self._token_to_session.pop(session.token_hash, None)
            return None
        return session

    def logout(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            self._token_to_session.pop(session.token_hash, None)
            return True
        return False

    def authorize(self, session: UserSession, permission: str) -> bool:
        """Verifica si el usuario tiene el permiso requerido."""
        return session.has_permission(permission)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values() if not s.is_expired()]

    def set_role(self, session_id: str, role: HFRole) -> bool:
        """Admin puede cambiar el rol de un usuario (UTRON governance)."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.role = role
        return True


# ---------------------------------------------------------------------------
# Flask middleware
# ---------------------------------------------------------------------------
def extract_hf_token() -> Optional[str]:
    """Extrae el token HF del header Authorization."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # También aceptar header X-HF-Token
    return request.headers.get("X-HF-Token")


def init_auth(app: Flask, auth: HFAuth) -> None:
    """Inicializa el middleware de autenticación en la app Flask."""

    @app.before_request
    def _authenticate_request():
        # Endpoints públicos (no requieren auth)
        public_endpoints = {
            "/health",
            "/api/v1/schema",
            "/api/v1/auth/login",
            "/api/v1/auth/status",
            "/api/v1/auth/oauth/login",
            "/api/v1/auth/oauth/callback",
            "/api/v1/auth/oauth/scopes",
        }
        if request.path in public_endpoints:
            return None

        # Extraer token
        hf_token = extract_hf_token()
        if not hf_token:
            return jsonify({
                "error": "unauthorized",
                "message": "Hugging Face token required. Send 'Authorization: Bearer hf_xxx' or 'X-HF-Token: hf_xxx'",
            }), 401

        # Autenticar
        success, session, error = auth.authenticate(hf_token)
        if not success:
            return jsonify({"error": "unauthorized", "message": error}), 401

        # Guardar sesión en el contexto de la request
        g.user_session = session
        g.hf_token = hf_token
        return None


def require_permission(permission: str) -> Callable:
    """Decorator para verificar permisos del usuario autenticado."""
    def decorator(f: Callable) -> Callable:
        def wrapped(*args, **kwargs):
            session = getattr(g, "user_session", None)
            if not session:
                return jsonify({"error": "unauthorized", "message": "No authenticated session"}), 401
            if not session.has_permission(permission):
                return jsonify({
                    "error": "forbidden",
                    "message": f"Permission '{permission}' required. Your role: {session.role.value}",
                    "your_role": session.role.value,
                    "required_permission": permission,
                }), 403
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator


def get_user_token() -> Optional[str]:
    """Retorna el token HF del usuario de la request actual."""
    return getattr(g, "hf_token", None)


def get_user_session() -> Optional[UserSession]:
    """Retorna la sesión del usuario de la request actual."""
    return getattr(g, "user_session", None)
