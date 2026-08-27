"""Configuración compartida para los tests de UC-264."""
import os

os.environ.setdefault("UC264_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC264_WORLD_SEED", "123")
os.environ.setdefault("UC264_NUM_CANDIDATE_PLANS", "8")
os.environ.setdefault("UC264_MC_SIMULATIONS_PER_PLAN", "50")
os.environ.setdefault("UC264_MC_BUDGET_SAMPLES", "20")
os.environ.setdefault("UC264_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
