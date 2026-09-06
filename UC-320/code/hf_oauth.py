"""UC-320 — OAuth Login con Hugging Face.

Implementa el flujo OAuth 2.0 con Hugging Face para que los usuarios
se autentiquen en UTRON.AI con su cuenta de HF.

Registro de aplicación:
  1. Settings > OAuth Apps en huggingface.co
  2. Registrar URL de callback: https://utron.ai/auth/callback
  3. Solicitar scopes requeridos

Scopes solicitados:
  - openid profile email: autenticar al usuario y obtener datos básicos
  - read-repos: leer repos privados del usuario
  - inference-api: realizar inferencia a nombre del usuario
  - write-repos: push de modelos adaptados (opcional)
  - compute: acceso a GPUs (cargos al usuario)

Flujo OAuth:
  1. Usuario → GET /api/v1/auth/oauth/login
  2. Redirect a https://huggingface.co/oauth/authorize?client_id=...&scope=...
  3. Usuario autoriza en HF
  4. HF redirect a /api/v1/auth/oauth/callback?code=...
  5. UTRON intercambia code por access_token
  6. Guarda token en sesión, redirige al usuario
"""
from __future__ import annotations

import os
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests


HF_OAUTH_AUTHORIZE = "https://huggingface.co/oauth/authorize"
HF_OAUTH_TOKEN = "https://huggingface.co/oauth/token"
HF_OAUTH_USERINFO = "https://huggingface.co/oauth/userinfo"


# Scopes requeridos por UTRON.AI
REQUIRED_SCOPES = [
    "openid",
    "profile",
    "email",
    "read-repos",
    "inference-api",
]

# Scopes opcionales (para push de modelos y compute)
OPTIONAL_SCOPES = [
    "write-repos",
    "compute",
]


@dataclass
class OAuthState:
    """Estado de una transacción OAuth (anti-CSRF)."""
    state: str
    redirect_uri: str = ""
    created_at: float = field(default_factory=time.time)
    scopes: List[str] = field(default_factory=list)

    def is_valid(self, ttl: int = 600) -> bool:
        return time.time() - self.created_at < ttl


@dataclass
class OAuthUserInfo:
    """Información del usuario obtenida via OAuth."""
    hf_username: str
    hf_name: str = ""
    hf_email: str = ""
    hf_sub: str = ""  # subject ID único
    access_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 3600
    scopes_granted: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hf_username": self.hf_username,
            "hf_name": self.hf_name,
            "hf_email": self.hf_email,
            "hf_sub": self.hf_sub,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scopes_granted": self.scopes_granted,
            # No exponer el access_token en la respuesta API
        }


class HFOAuth:
    """Maneja el flujo OAuth 2.0 con Hugging Face.

    En producción requiere:
      - HF_OAUTH_CLIENT_ID (env)
      - HF_OAUTH_CLIENT_SECRET (env)
      - HF_OAUTH_REDIRECT_URI (env, ej: https://utron.ai/api/v1/auth/oauth/callback)

    En modo mock simula el flujo para tests.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        backend: str = "mock",
    ) -> None:
        self.client_id = client_id or os.environ.get("HF_OAUTH_CLIENT_ID", "mock_client_id")
        self.client_secret = client_secret or os.environ.get("HF_OAUTH_CLIENT_SECRET", "mock_secret")
        self.redirect_uri = redirect_uri or os.environ.get(
            "HF_OAUTH_REDIRECT_URI",
            "http://localhost:5320/api/v1/auth/oauth/callback",
        )
        self.backend = backend
        self._states: Dict[str, OAuthState] = {}

    def get_authorization_url(
        self,
        scopes: Optional[List[str]] = None,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Genera URL de autorización para redirigir al usuario a HF.

        Returns dict with:
          - authorization_url: URL a la que redirigir al usuario
          - state: token anti-CSRF que debe validarse en el callback
        """
        requested_scopes = scopes or REQUIRED_SCOPES.copy()
        state = secrets.token_urlsafe(32)
        oauth_state = OAuthState(
            state=state,
            redirect_uri=redirect_uri or self.redirect_uri,
            scopes=requested_scopes,
        )
        self._states[state] = oauth_state

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "scope": " ".join(requested_scopes),
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{HF_OAUTH_AUTHORIZE}?{urllib.parse.urlencode(params)}"

        return {
            "authorization_url": auth_url,
            "state": state,
            "scopes_requested": requested_scopes,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "instructions": "Redirect the user to authorization_url. After authorization, HF will redirect to redirect_uri with code and state.",
        }

    def exchange_code(
        self,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """Intercambia el código de autorización por un access_token.

        Returns dict with:
          - success: bool
          - user_info: OAuthUserInfo if success
          - error: str if failed
        """
        # Validar state (anti-CSRF)
        oauth_state = self._states.pop(state, None)
        if not oauth_state or not oauth_state.is_valid():
            return {"success": False, "error": "Invalid or expired OAuth state"}

        if self.backend == "huggingface":
            try:
                resp = requests.post(
                    HF_OAUTH_TOKEN,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": oauth_state.redirect_uri,
                    },
                    timeout=30,
                )
                if resp.status_code != 200:
                    return {"success": False, "error": f"Token exchange failed: {resp.text}"}

                token_data = resp.json()
                access_token = token_data.get("access_token", "")

                # Obtener info del usuario
                user_resp = requests.get(
                    HF_OAUTH_USERINFO,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30,
                )
                if user_resp.status_code != 200:
                    return {"success": False, "error": "Failed to get user info"}

                user_data = user_resp.json()
                user_info = OAuthUserInfo(
                    hf_username=user_data.get("preferred_username", user_data.get("name", "")),
                    hf_name=user_data.get("name", ""),
                    hf_email=user_data.get("email", ""),
                    hf_sub=user_data.get("sub", ""),
                    access_token=access_token,
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_in=token_data.get("expires_in", 3600),
                    scopes_granted=oauth_state.scopes,
                )
                return {"success": True, "user_info": user_info}

            except Exception as exc:
                return {"success": False, "error": f"OAuth exchange error: {exc}"}

        # Mock: simular intercambio exitoso
        if code.startswith("mock_code_"):
            user_info = OAuthUserInfo(
                hf_username=f"oauth_user_{code[-4:]}",
                hf_name="OAuth Test User",
                hf_email=f"oauth_{code[-4:]}@mock.ai",
                hf_sub=f"sub_{code[-8:]}",
                access_token=f"hf_oauth_token_{code[-8:]}",
                scopes_granted=oauth_state.scopes,
            )
            return {"success": True, "user_info": user_info}

        return {"success": False, "error": "Invalid authorization code (mock mode)"}

    def validate_scopes(self, granted: List[str], required: List[str]) -> Dict[str, Any]:
        """Verifica que el usuario concedió todos los scopes requeridos."""
        missing = [s for s in required if s not in granted]
        return {
            "valid": len(missing) == 0,
            "granted": granted,
            "required": required,
            "missing": missing,
            "message": "All scopes granted" if not missing else f"Missing scopes: {missing}",
        }

    def get_scopes_info(self) -> Dict[str, Any]:
        """Retorna información sobre los scopes requeridos y opcionales."""
        scope_descriptions = {
            "openid": "Authenticate user (OpenID Connect)",
            "profile": "Access user profile (name, username)",
            "email": "Access user email",
            "read-repos": "Read user's private repositories",
            "inference-api": "Run inference on behalf of the user (uses their quota)",
            "write-repos": "Push adapted models to user's repos",
            "compute": "Access GPU compute (charges to user's HF account)",
        }
        return {
            "required": [
                {"scope": s, "description": scope_descriptions.get(s, s)}
                for s in REQUIRED_SCOPES
            ],
            "optional": [
                {"scope": s, "description": scope_descriptions.get(s, s)}
                for s in OPTIONAL_SCOPES
            ],
            "billing_note": "With 'inference-api' and 'compute' scopes, GPU charges go to the user's HF account, not UTRON.AI",
        }

    def cleanup_expired_states(self) -> int:
        """Elimina estados OAuth expirados. Retorna cuántos se eliminaron."""
        expired = [s for s, st in self._states.items() if not st.is_valid()]
        for s in expired:
            del self._states[s]
        return len(expired)
