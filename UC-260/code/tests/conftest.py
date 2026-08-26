"""Configuración compartida para los tests de UC-260."""
import os

os.environ.setdefault("UC260_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC260_WORLD_SEED", "123")
os.environ.setdefault("UC260_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
os.environ.setdefault("UC260_ENABLE_PROMPT_INJECTION_CHECK", "true")
os.environ.setdefault("UC260_ENABLE_PII_REDACTION", "true")
os.environ.setdefault("UC260_ENABLE_LEARNING", "true")
