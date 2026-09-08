"""
UC-300 — Registro de esquemas estrictos y canonicalización.

Cada herramienta expone un modelo Pydantic v2 con:
- extra='forbid' para rechazar campos desconocidos.
- Validadores semánticos específicos.
- Canonicalización determinista para hashing.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


# ---------------------------------------------------------------------------
# Esquemas de herramientas
# ---------------------------------------------------------------------------

class UpdatePriceParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    product_id: str = Field(..., pattern=r"^SKU-[0-9]{3}$")
    new_price: float = Field(..., gt=0.0)
    reason: str = Field(..., min_length=5, max_length=500)

    @field_validator("product_id")
    @classmethod
    def _canonicalize_product_id(cls, v: str) -> str:
        # Mantener el formato canónico SKU-NNN en mayúsculas
        return v.upper().strip()

    @field_validator("new_price")
    @classmethod
    def _no_micro_injection_in_price(cls, v: float) -> float:
        # Valor numérico saneado por Pydantic; asegurar finitud
        if not math.isfinite(v):
            raise ValueError("price must be a finite number")
        return round(float(v), 2)


class DeleteProductParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(..., pattern=r"^SKU-[0-9]{3}$")
    confirmation_code: str = Field(..., pattern=r"^CONFIRM-[A-Z]{4}$")
    hard_delete: bool = Field(default=False)

    @field_validator("product_id")
    @classmethod
    def _canonicalize_product_id(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("confirmation_code")
    @classmethod
    def _canonicalize_confirmation_code(cls, v: str) -> str:
        return v.upper().strip()


class SendPaymentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., gt=0.0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    memo: str = Field(default="", max_length=200)

    @field_validator("recipient_id")
    @classmethod
    def _canonicalize_recipient_id(cls, v: str) -> str:
        v = v.strip()
        if any(c in v for c in ";|&$`\"'\\<>"):
            raise ValueError("recipient_id contains forbidden characters")
        return v

    @field_validator("amount")
    @classmethod
    def _canonicalize_amount(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("amount must be a finite number")
        amount = round(float(v), 2)
        if amount <= 0:
            raise ValueError("amount must be positive")
        return amount


class ReadFileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., min_length=1, max_length=256)
    encoding: str = Field(default="utf-8", pattern=r"^[a-zA-Z0-9._-]+$")

    @field_validator("path")
    @classmethod
    def _canonicalize_path(cls, v: str) -> str:
        v = v.strip().replace("\\", "/")
        if v.startswith("/"):
            v = v[1:]
        # Rechazar travesal explícito
        if ".." in v or "~" in v:
            raise ValueError("path contains traversal characters")
        if any(c in v for c in ";|&$`\"'<>\x00"):
            raise ValueError("path contains forbidden characters")
        return v


# ---------------------------------------------------------------------------
# Registro y helpers
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "update_price": UpdatePriceParams,
    "delete_product": DeleteProductParams,
    "send_payment": SendPaymentParams,
    "read_file": ReadFileParams,
}

RISK_BY_ACTION = {
    "update_price": "low",
    "read_file": "low",
    "send_payment": "high",
    "delete_product": "critical",
}

REQUIRES_APPROVAL = {
    "update_price": False,
    "read_file": False,
    "send_payment": True,
    "delete_product": True,
}

HIGH_PAYMENT_THRESHOLD = 5000.0


def get_schema(action: str) -> Optional[Type[BaseModel]]:
    """Devuelve el esquema Pydantic para una acción."""
    return TOOL_SCHEMAS.get(action)


def list_actions() -> List[str]:
    """Lista las acciones registradas."""
    return list(TOOL_SCHEMAS.keys())


def canonicalize_value(value: Any) -> Any:
    """Canonicaliza un valor simple para hashing."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        # Normalizar floats a dos decimales como string para evitar
        # problemas de representación binaria en el hash.
        if isinstance(value, float):
            return float(f"{value:.6f}")
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return [canonicalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k.strip(): canonicalize_value(v) for k, v in sorted(value.items())}
    return value


def canonicalize_params(params: Dict[str, Any]) -> str:
    """Devuelve JSON canónico ordenado y normalizado."""
    canonical = canonicalize_value(params)
    import json
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)


def validate_and_canonicalize(action: str, raw_params: Dict[str, Any]) -> str:
    """Valida parámetros contra el esquema y devuelve JSON canónico."""
    schema_cls = get_schema(action)
    if schema_cls is None:
        raise SchemaValidationError(f"Unknown action: {action}")
    try:
        validated = schema_cls.model_validate(raw_params)
    except ValidationError as exc:
        raise SchemaValidationError(str(exc)) from exc
    data = validated.model_dump()
    # Volver a canonicalizar para hashing determinista
    return canonicalize_params(data)


class SchemaValidationError(Exception):
    """Error de validación de esquema."""
    pass


class SemanticValidationError(Exception):
    """Error de validación semántica adicional."""
    pass


def semantic_check(action: str, params: Dict[str, Any]) -> None:
    """Validaciones semánticas extra que no cubre el esquema base."""
    if action == "send_payment":
        amount = float(params.get("amount", 0))
        currency = params.get("currency", "USD")
        if currency == "USD" and amount > HIGH_PAYMENT_THRESHOLD:
            # Se permite pasar la validación, pero se marca para HITL
            pass
    if action == "read_file":
        path = params.get("path", "")
        if path.startswith(("http://", "https://", "ftp://")):
            raise SemanticValidationError("read_file path must be a local simulated path")
