"""Configuración compartida para los tests de UC-259."""
import os

os.environ.setdefault("UC259_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC259_WORLD_SEED", "123")
os.environ.setdefault("UC259_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
os.environ.setdefault("UC259_ENABLE_PROMPT_INJECTION_CHECK", "true")
os.environ.setdefault("UC259_ENABLE_PII_REDACTION", "true")
