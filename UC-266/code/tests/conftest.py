"""Configuración compartida para los tests de UC-266."""
import os

os.environ.setdefault("UC266_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC266_WORLD_SEED", "123")
os.environ.setdefault("UC266_NUM_CANDIDATE_PLANS", "8")
os.environ.setdefault("UC266_MC_SIMULATIONS_PER_PLAN", "30")
os.environ.setdefault("UC266_MCTS_ITERATIONS", "50")
os.environ.setdefault("UC266_REQUIRE_CONFIRMATION_IRREVERSIBLE", "false")
os.environ.setdefault("UC266_PARTIAL_OBSERVABILITY", "true")
os.environ.setdefault("UC266_VECTOR_BACKEND", "simple")
os.environ.setdefault("UC266_TORCH_EPOCHS", "10")
os.environ.setdefault("UC266_TORCH_DEVICE", "cpu")
