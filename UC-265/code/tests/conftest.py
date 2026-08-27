"""Configuración compartida para los tests de UC-265."""
import os

os.environ.setdefault("UC265_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC265_WORLD_SEED", "123")
os.environ.setdefault("UC265_NUM_CANDIDATE_PLANS", "8")
os.environ.setdefault("UC265_MC_SIMULATIONS_PER_PLAN", "30")
os.environ.setdefault("UC265_MCTS_ITERATIONS", "50")
os.environ.setdefault("UC265_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
os.environ.setdefault("UC265_PARTIAL_OBSERVABILITY", "true")
