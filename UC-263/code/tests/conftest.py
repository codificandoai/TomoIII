"""Configuración compartida para los tests de UC-263."""
import os

os.environ.setdefault("UC263_SEED", "123")
os.environ.setdefault("UC263_MEMORY_PATH", "")
os.environ.setdefault("UC263_EMBEDDING_DIM", "8")
os.environ.setdefault("UC263_ALPHA", "0.2")
os.environ.setdefault("UC263_GAMMA", "0.9")
os.environ.setdefault("UC263_EPSILON", "0.0")
os.environ.setdefault("UC263_EPISODES", "10")
