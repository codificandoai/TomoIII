"""Configuración compartida para los tests de UC-292."""
import os

os.environ.setdefault("UC292_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC292_WORLD_SEED", "123")
os.environ.setdefault("UC292_NUM_CANDIDATE_STRATEGIES", "4")
os.environ.setdefault("UC292_MC_SIMULATIONS_PER_STRATEGY", "5")
os.environ.setdefault("UC292_MCTS_ITERATIONS", "10")
os.environ.setdefault("UC292_REQUIRE_CONFIRMATION", "true")
