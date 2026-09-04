"""Configuración compartida de tests para UC-296."""
from __future__ import annotations

import os
import sys

# Añadir al path los módulos de UC-296 y UC-295 para reutilizar código heredado.
UC296_CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UC295_CODE = os.path.abspath(os.path.join(UC296_CODE, "..", "UC-295", "code"))
sys.path.insert(0, UC296_CODE)
sys.path.insert(0, UC295_CODE)

import pytest


@pytest.fixture
def client():
    from api import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
