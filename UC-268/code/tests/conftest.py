"""Configuración compartida para tests de UC-268."""
import os

os.environ.setdefault("UC268_JWT_SECRET", "test-secret")
os.environ.setdefault("UC268_TOKEN_TTL_MINUTES", "60")
os.environ.setdefault("UC268_REQUIRE_TLS", "false")
os.environ.setdefault("UC268_API_KEYS", "dev-api-key")
os.environ.setdefault("UC268_AGENT_URL", "http://localhost:5268")
os.environ.setdefault("UC268_PORT", "5268")
