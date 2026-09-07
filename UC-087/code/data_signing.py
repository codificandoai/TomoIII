"""
UC-087 — Firma y provenancia de datos de entrenamiento.

Calcula hashes criptográficos, genera firmas HMAC simples y valida la
integridad y autenticidad de lotes de datos.
"""

import hashlib
import hmac
import json
import time
from typing import Dict, List, Any, Optional


class DataSigning:
    """
    Gestiona hashes y firmas HMAC para batches de datos de entrenamiento.

    En producción, la clave secreta debe provenir de un vault (UC-324 / KMS).
    """

    def __init__(self, secret_key: Optional[bytes] = None, algorithm: str = "sha256"):
        self.secret_key = secret_key or b"uc087-default-secret-change-in-prod"
        self.algorithm = algorithm

    def _canonical(self, data: Any) -> bytes:
        """Serializa datos de forma determinista."""
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def hash_batch(self, data: Any) -> str:
        """Calcula hash SHA-256 de un batch de datos."""
        return hashlib.new(self.algorithm, self._canonical(data)).hexdigest()

    def sign_batch(self, data: Any, timestamp: Optional[float] = None) -> Dict[str, str]:
        """Genera firma HMAC de un batch con timestamp."""
        ts = str(int(timestamp or time.time()))
        payload = self._canonical({"data": data, "timestamp": ts})
        signature = hmac.new(self.secret_key, payload, self.algorithm).hexdigest()
        return {
            "hash": self.hash_batch(data),
            "signature": signature,
            "timestamp": ts,
            "algorithm": self.algorithm,
        }

    def verify_hash(self, data: Any, expected_hash: str) -> bool:
        """Verifica que el hash de los datos coincida."""
        return self.hash_batch(data) == expected_hash

    def verify_signature(self, data: Any, envelope: Dict[str, str]) -> bool:
        """Verifica firma HMAC y timestamp."""
        try:
            expected = self.sign_batch(data, timestamp=float(envelope.get("timestamp", 0)))
            if not hmac.compare_digest(expected["signature"], envelope.get("signature", "")):
                return False
            if expected["hash"] != envelope.get("hash", ""):
                return False
            return True
        except Exception:
            return False

    def hash_file(self, file_path: str) -> str:
        """Calcula hash de un archivo binario."""
        h = hashlib.new(self.algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def record_lineage(
        self,
        source: str,
        dataset_hash: str,
        transformations: List[str],
    ) -> Dict[str, Any]:
        """Registra lineage básico de un dataset."""
        return {
            "source": source,
            "dataset_hash": dataset_hash,
            "transformations": transformations,
            "recorded_at": time.time(),
        }
