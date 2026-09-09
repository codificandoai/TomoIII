"""Validación de esquemas de entrada/salida para invocaciones de herramientas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class SchemaValidator:
    """
    Valida diccionarios de entrada y salida contra esquemas declarativos.
    Soporta tipos simples, listas, campos requeridos y prohibidos.
    """

    VALID_TYPES = {"str", "int", "float", "bool", "list", "dict"}

    def __init__(self) -> None:
        self._input_schemas: Dict[str, Dict[str, Any]] = {}
        self._output_schemas: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        tool_name: str,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        if input_schema:
            self._input_schemas[tool_name] = input_schema
        if output_schema:
            self._output_schemas[tool_name] = output_schema

    def validate_input(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        schema = self._input_schemas.get(tool_name)
        if not schema:
            return {"valid": True, "errors": []}
        return self._validate(schema, params)

    def validate_output(self, tool_name: str, output: Any) -> Dict[str, Any]:
        schema = self._output_schemas.get(tool_name)
        if not schema:
            return {"valid": True, "errors": []}
        return self._validate(schema, output)

    def _validate(self, schema: Dict[str, Any], data: Any) -> Dict[str, Any]:
        errors: List[str] = []
        if not isinstance(data, dict):
            return {"valid": False, "errors": ["data must be a dict"]}

        required = schema.get("required", [])
        forbidden = schema.get("forbidden", [])
        types = schema.get("types", {})
        allowed_keys = schema.get("allowed_keys")

        for key in required:
            if key not in data:
                errors.append(f"missing required field: {key}")

        for key in forbidden:
            if key in data:
                errors.append(f"forbidden field present: {key}")

        for key, expected in types.items():
            if key in data:
                if expected.startswith("list["):
                    inner = expected[5:-1]
                    if not isinstance(data[key], list):
                        errors.append(f"{key} must be list")
                    else:
                        for i, item in enumerate(data[key]):
                            if inner in self.VALID_TYPES and not self._type_check(item, inner):
                                errors.append(f"{key}[{i}] must be {inner}")
                elif not self._type_check(data[key], expected):
                    errors.append(f"{key} must be {expected}")

        if allowed_keys is not None:
            extra = set(data.keys()) - set(allowed_keys)
            if extra:
                errors.append(f"extra keys not allowed: {sorted(extra)}")

        return {"valid": not errors, "errors": errors}

    def _type_check(self, value: Any, expected: str) -> bool:
        if expected == "str":
            return isinstance(value, str)
        if expected == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "bool":
            return isinstance(value, bool)
        if expected == "list":
            return isinstance(value, list)
        if expected == "dict":
            return isinstance(value, dict)
        return True
