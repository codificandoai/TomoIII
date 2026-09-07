"""UC-325 — Configuración de pytest."""

import sys
import os

# Asegurar que el directorio code/ está en sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
