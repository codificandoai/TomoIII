"""
UC-308 — Golden Dataset versionado, hasheado y firmado.

Incluye casos públicos y secretos para detectar múltiples tipos de deriva:
- API contract / schema drift
- HTML / interface drift
- Data distribution drift
- Tool operational drift (latencia, errores, recursos)
- Behavioral drift
- Quality drift
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models_308 import GoldenCase, GoldenDataset


def build_default_golden_dataset(version: str = "1.0.0") -> GoldenDataset:
    """Construye el golden dataset de demostración de UC-308."""
    cases: List[GoldenCase] = [
        # ------------------------------------------------------------------
        # Casos PÚBLICOS
        # ------------------------------------------------------------------
        GoldenCase(
            id="G001",
            name="Obtener precio competidor",
            description="Llamada REST a endpoint de precios. Detecta API schema drift.",
            tool="api_call",
            environment="default",
            agent_version="1.0.0",
            input_payload={"endpoint": "/api/v1/prices", "method": "GET", "params": {"sku": "SKU-001"}},
            expected_schema_keys=["price", "currency", "sku", "updated_at"],
            expected_output={"price": 120.50, "currency": "USD", "sku": "SKU-001", "updated_at": "2024-01-01T00:00:00Z"},
            tags=["contract", "public"],
        ),
        GoldenCase(
            id="G002",
            name="Extraer stock del sitio web",
            description="Scrape HTML para obtener stock. Detecta HTML selector drift.",
            tool="web_scrape",
            environment="default",
            agent_version="1.0.0",
            input_payload={"url": "https://example.com/products/SKU-001", "selectors": ["div.price", "span.stock"]},
            expected_html_selectors=["div.price", "span.stock"],
            expected_output={"price": "120.50", "stock": "42"},
            tags=["html", "public"],
        ),
        GoldenCase(
            id="G003",
            name="Consultar margen histórico",
            description="Consulta a base de datos simulada.",
            tool="db_query",
            environment="default",
            agent_version="1.0.0",
            input_payload={"query": "SELECT margin FROM history WHERE sku = 'SKU-001'"},
            expected_schema_keys=["margin", "sku"],
            expected_output={"margin": 0.25, "sku": "SKU-001"},
            tags=["contract", "public"],
        ),
        GoldenCase(
            id="G004",
            name="Distribución de precios",
            description="Caso para detectar data distribution drift en una variable numérica.",
            tool="data_distribution",
            environment="default",
            agent_version="1.0.0",
            input_payload={"variable": "price", "samples": 100},
            distribution_config={
                "type": "numeric",
                "baseline_mean": 120.0,
                "baseline_std": 10.0,
                "categories": None,
            },
            expected_output={"mean": 120.0, "std": 10.0},
            tags=["distribution", "public"],
        ),
        GoldenCase(
            id="G005",
            name="Categorías de producto",
            description="Caso para detectar data distribution drift categórico.",
            tool="data_distribution",
            environment="default",
            agent_version="1.0.0",
            input_payload={"variable": "category", "samples": 200},
            distribution_config={
                "type": "categorical",
                "categories": ["electronics", "home", "sports"],
                "baseline_probs": [0.50, 0.30, 0.20],
            },
            expected_output={"dominant": "electronics"},
            tags=["distribution", "public"],
        ),
        GoldenCase(
            id="G006",
            name="Actualización de inventario",
            description="Caso que expone behavioral drift: pasos, reintentos y escalaciones.",
            tool="inventory_update",
            environment="default",
            agent_version="1.0.0",
            input_payload={"sku": "SKU-001", "new_stock": 100},
            expected_schema_keys=["status", "sku", "new_stock"],
            expected_output={"status": "ok", "sku": "SKU-001", "new_stock": 100},
            tags=["behavioral", "public"],
        ),
        # ------------------------------------------------------------------
        # Casos SECRETOS (no se exponen en /datasets sin credenciales)
        # ------------------------------------------------------------------
        GoldenCase(
            id="S001",
            name="Endpoint interno de costos",
            description="API interna cuyo esquema es sensible.",
            tool="api_call",
            environment="internal",
            agent_version="1.0.0",
            input_payload={"endpoint": "/internal/v1/costs", "method": "GET"},
            expected_schema_keys=["cost", "currency", "sku"],
            expected_output={"cost": 90.0, "currency": "USD", "sku": "SKU-001"},
            secret=True,
            tags=["contract", "secret"],
        ),
        GoldenCase(
            id="S002",
            name="Selector crítico de stock",
            description="Selector HTML crítico de stock que no debe filtrarse.",
            tool="web_scrape",
            environment="internal",
            agent_version="1.0.0",
            input_payload={"url": "https://internal.example.com/stock", "selectors": ["div.critical-stock"]},
            expected_html_selectors=["div.critical-stock"],
            expected_output={"stock": "15"},
            secret=True,
            tags=["html", "secret"],
        ),
    ]

    dataset = GoldenDataset(version=version, cases=cases)
    return dataset


def load_golden_dataset_from_dict(data: Dict[str, Any]) -> GoldenDataset:
    """Carga un golden dataset desde un diccionario JSON."""
    cases = []
    for item in data.get("cases", []):
        cases.append(GoldenCase(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            tool=item["tool"],
            environment=item.get("environment", "default"),
            agent_version=item.get("agent_version", "1.0.0"),
            input_payload=item.get("input_payload", {}),
            expected_schema_keys=item.get("expected_schema_keys"),
            expected_html_selectors=item.get("expected_html_selectors"),
            expected_output=item.get("expected_output"),
            distribution_config=item.get("distribution_config"),
            secret=item.get("secret", False),
            tags=item.get("tags", []),
            metadata=item.get("metadata", {}),
        ))
    return GoldenDataset(
        version=data["version"],
        cases=cases,
        public_case_ids=data.get("public_case_ids", []),
        secret_case_ids=data.get("secret_case_ids", []),
        created_at=data.get("created_at", 0.0),
    )


def get_public_cases(dataset: GoldenDataset) -> List[GoldenCase]:
    """Retorna solo los casos públicos."""
    return [c for c in dataset.cases if c.id in dataset.public_case_ids]


def get_secret_cases(dataset: GoldenDataset) -> List[GoldenCase]:
    """Retorna solo los casos secretos."""
    return [c for c in dataset.cases if c.id in dataset.secret_case_ids]


if __name__ == "__main__":
    ds = build_default_golden_dataset()
    key = "uc308-demo-secret-key"
    ds.sign(key)
    print("Dataset version:", ds.version)
    print("Cases:", len(ds.cases))
    print("Public:", len(ds.public_case_ids))
    print("Secret:", len(ds.secret_case_ids))
    print("Hash:", ds.signature.content_hash)
    print("Signature valid:", ds.verify_signature(key))
