"""UC-320 — Exploración y sincronización del catálogo de Hugging Face.

Conecta directamente con los endpoints públicos de la API REST de
Hugging Face para listar, filtrar y mostrar modelos, datasets y spaces
en la interfaz de UTRON.AI.

Endpoints públicos consultados:
  - GET https://huggingface.co/api/models
  - GET https://huggingface.co/api/datasets
  - GET https://huggingface.co/api/spaces

Parámetros de filtrado soportados:
  - task: filtrar por tarea (text-generation, sentiment, embeddings, ...)
  - search: búsqueda por etiquetas/keywords (financial, spanish, ...)
  - license: filtrar por licencia (mit, apache-2.0, ...)
  - author: filtrar por autor/organización
  - sort: ordenar (downloads, likes, created, modified)
  - direction: asc/desc
  - limit: número de resultados
  - full: incluir metadatos completos

En modo mock retorna datos deterministas para tests.
En modo huggingface usa huggingface_hub.HfApi o requests directos.
"""
from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests


HF_API_BASE = "https://huggingface.co/api"


@dataclass
class CatalogItem:
    """Item del catálogo de HF (modelo, dataset o space)."""
    id: str
    type: str  # model, dataset, space
    author: str = ""
    downloads: int = 0
    likes: int = 0
    created_at: str = ""
    last_modified: str = ""
    tags: List[str] = field(default_factory=list)
    pipeline_tag: str = ""  # task: text-generation, sentiment, etc.
    license: str = ""
    gated: bool = False
    private: bool = False
    siblings: List[str] = field(default_factory=list)  # archivos del repo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "author": self.author,
            "downloads": self.downloads,
            "likes": self.likes,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "tags": self.tags,
            "pipeline_tag": self.pipeline_tag,
            "license": self.license,
            "gated": self.gated,
            "private": self.private,
            "siblings": self.siblings,
        }


# Catálogo mock determinista para tests
_MOCK_MODELS = [
    CatalogItem(id="ProsusAI/finbert", type="model", author="ProsusAI",
                downloads=500000, likes=320, pipeline_tag="text-classification",
                license="MIT", tags=["finance", "sentiment", "en"],
                siblings=["config.json", "pytorch_model.bin", "tokenizer.json"]),
    CatalogItem(id="sentence-transformers/all-MiniLM-L6-v2", type="model",
                author="sentence-transformers", downloads=5000000, likes=850,
                pipeline_tag="feature-extraction", license="Apache-2.0",
                tags=["embeddings", "en"], siblings=["config.json", "model.safetensors"]),
    CatalogItem(id="meta-llama/Meta-Llama-3-8B", type="model", author="meta-llama",
                downloads=100000, likes=1200, pipeline_tag="text-generation",
                license="llama3", gated=True, tags=["llama", "text-generation", "en"],
                siblings=["config.json", "model-00001-of-00004.safetensors"]),
    CatalogItem(id="mistralai/Mistral-7B-Instruct-v0.3", type="model",
                author="mistralai", downloads=800000, likes=950,
                pipeline_tag="text-generation", license="apache-2.0",
                tags=["mistral", "instruct", "en"]),
    CatalogItem(id="BAAI/bge-m3", type="model", author="BAAI",
                downloads=300000, likes=420, pipeline_tag="feature-extraction",
                license="MIT", tags=["embeddings", "multilingual"]),
    CatalogItem(id="stabilityai/stable-diffusion-xl-base-1.0", type="model",
                author="stabilityai", downloads=2000000, likes=2100,
                pipeline_tag="text-to-image", license="openrail++",
                gated=False, tags=["diffusion", "image-generation"]),
]

_MOCK_DATASETS = [
    CatalogItem(id="financial_phrasebank", type="dataset", author="takala",
                downloads=100000, likes=180, license="CC-BY-NC-4.0",
                tags=["finance", "sentiment", "en"]),
    CatalogItem(id="imdb", type="dataset", author="stanfordnlp",
                downloads=5000000, likes=890, license="Apache-2.0",
                tags=["sentiment", "movies", "en"]),
    CatalogItem(id="squad", type="dataset", author="rajpurkar",
                downloads=3000000, likes=650, license="CC-BY-SA-4.0",
                tags=["qa", "reading-comprehension", "en"]),
]

_MOCK_SPACES = [
    CatalogItem(id="gradio/hello_world", type="space", author="gradio",
                downloads=0, likes=120, license="Apache-2.0",
                tags=["gradio", "demo"]),
    CatalogItem(id="microsoft/LLM-2-LLM-Playground", type="space", author="microsoft",
                downloads=0, likes=340, license="MIT",
                tags=["llm", "playground", "gradio"]),
]


class HFCatalogBrowser:
    """Exploración del catálogo público de Hugging Face.

    Modo mock: retorna datos deterministas.
    Modo huggingface: consulta directa a https://huggingface.co/api/*
    """

    def __init__(self, backend: str = "mock", token: Optional[str] = None) -> None:
        self.backend = backend
        self.token = token
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self._cache_ttl = 300  # 5 min

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "UTRON-AI/UC-320"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _fetch(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Consulta directa a la API REST de Hugging Face."""
        url = f"{HF_API_BASE}/{endpoint}"
        resp = requests.get(url, params=params, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _filter_mock(
        self, items: List[CatalogItem], task: str, search: str,
        license_filter: str, author: str, limit: int,
    ) -> List[CatalogItem]:
        result = items
        if task:
            result = [i for i in result if i.pipeline_tag == task or task in i.tags]
        if search:
            s = search.lower()
            result = [i for i in result if s in i.id.lower() or any(s in t.lower() for t in i.tags)]
        if license_filter:
            result = [i for i in result if i.license.lower() == license_filter.lower()]
        if author:
            result = [i for i in result if i.author.lower() == author.lower()]
        return result[:limit]

    def list_models(
        self, task: str = "", search: str = "", license: str = "",
        author: str = "", sort: str = "downloads", direction: str = "desc",
        limit: int = 50, full: bool = False,
    ) -> List[Dict[str, Any]]:
        """Lista modelos del catálogo HF con filtros."""
        cache_key = f"models:{task}:{search}:{license}:{author}:{sort}:{direction}:{limit}:{full}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        if self.backend == "huggingface":
            params = {
                "sort": sort, "direction": direction, "limit": limit,
            }
            if task:
                params["filter"] = task
            if search:
                params["search"] = search
            if author:
                params["author"] = author
            if full:
                params["full"] = "true"
            try:
                raw = self._fetch("models", params)
                items = []
                for m in raw:
                    item = CatalogItem(
                        id=m.get("id", ""), type="model",
                        author=m.get("author", ""),
                        downloads=m.get("downloads", 0),
                        likes=m.get("likes", 0),
                        created_at=m.get("createdAt", ""),
                        last_modified=m.get("lastModified", ""),
                        tags=m.get("tags", []),
                        pipeline_tag=m.get("pipeline_tag", ""),
                        gated=m.get("gated", False),
                        private=m.get("private", False),
                        siblings=[s.get("rfilename", "") for s in m.get("siblings", [])],
                    )
                    # Extraer licencia de tags
                    for tag in item.tags:
                        if tag.startswith("license:"):
                            item.license = tag.split(":", 1)[1]
                            break
                    items.append(item.to_dict())
                self._cache[cache_key] = (items, time.time())
                return items
            except Exception:
                # Fallback a mock si la API no está disponible
                pass

        # Mock
        filtered = self._filter_mock(_MOCK_MODELS, task, search, license, author, limit)
        items = [i.to_dict() for i in filtered]
        self._cache[cache_key] = (items, time.time())
        return items

    def list_datasets(
        self, search: str = "", license: str = "", author: str = "",
        sort: str = "downloads", direction: str = "desc", limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lista datasets del catálogo HF con filtros."""
        cache_key = f"datasets:{search}:{license}:{author}:{sort}:{direction}:{limit}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        if self.backend == "huggingface":
            params = {"sort": sort, "direction": direction, "limit": limit}
            if search:
                params["search"] = search
            if author:
                params["author"] = author
            try:
                raw = self._fetch("datasets", params)
                items = []
                for d in raw:
                    item = CatalogItem(
                        id=d.get("id", ""), type="dataset",
                        author=d.get("author", ""),
                        downloads=d.get("downloads", 0),
                        likes=d.get("likes", 0),
                        created_at=d.get("createdAt", ""),
                        last_modified=d.get("lastModified", ""),
                        tags=d.get("tags", []),
                        private=d.get("private", False),
                    )
                    for tag in item.tags:
                        if tag.startswith("license:"):
                            item.license = tag.split(":", 1)[1]
                            break
                    items.append(item.to_dict())
                self._cache[cache_key] = (items, time.time())
                return items
            except Exception:
                pass

        filtered = self._filter_mock(_MOCK_DATASETS, "", search, license, author, limit)
        items = [i.to_dict() for i in filtered]
        self._cache[cache_key] = (items, time.time())
        return items

    def list_spaces(
        self, search: str = "", author: str = "",
        sort: str = "likes", direction: str = "desc", limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lista spaces del catálogo HF con filtros."""
        cache_key = f"spaces:{search}:{author}:{sort}:{direction}:{limit}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        if self.backend == "huggingface":
            params = {"sort": sort, "direction": direction, "limit": limit}
            if search:
                params["search"] = search
            if author:
                params["author"] = author
            try:
                raw = self._fetch("spaces", params)
                items = []
                for s in raw:
                    item = CatalogItem(
                        id=s.get("id", ""), type="space",
                        author=s.get("author", ""),
                        likes=s.get("likes", 0),
                        created_at=s.get("createdAt", ""),
                        last_modified=s.get("lastModified", ""),
                        tags=s.get("tags", []),
                        private=s.get("private", False),
                        siblings=[si.get("rfilename", "") for si in s.get("siblings", [])],
                    )
                    items.append(item.to_dict())
                self._cache[cache_key] = (items, time.time())
                return items
            except Exception:
                pass

        filtered = self._filter_mock(_MOCK_SPACES, "", search, "", author, limit)
        items = [i.to_dict() for i in filtered]
        self._cache[cache_key] = (items, time.time())
        return items

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos de un modelo específico."""
        if self.backend == "huggingface":
            try:
                resp = requests.get(
                    f"{HF_API_BASE}/models/{model_id}",
                    headers=self._headers(), timeout=30,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        # Mock
        for m in _MOCK_MODELS:
            if m.id == model_id:
                return m.to_dict()
        return None

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos de un dataset específico."""
        if self.backend == "huggingface":
            try:
                resp = requests.get(
                    f"{HF_API_BASE}/datasets/{dataset_id}",
                    headers=self._headers(), timeout=30,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        for d in _MOCK_DATASETS:
            if d.id == dataset_id:
                return d.to_dict()
        return None

    def get_space(self, space_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos de un space específico."""
        if self.backend == "huggingface":
            try:
                resp = requests.get(
                    f"{HF_API_BASE}/spaces/{space_id}",
                    headers=self._headers(), timeout=30,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        for s in _MOCK_SPACES:
            if s.id == space_id:
                return s.to_dict()
        return None

    def check_gated(self, model_id: str) -> Dict[str, Any]:
        """Verifica si un modelo es gated (requiere aceptación de términos).

        Para modelos gated (ej. Llama 3, Gemma), el usuario debe haber
        aceptado los términos en huggingface.co. Si el usuario tiene token,
        se verifica si tiene acceso.
        """
        model = self.get_model(model_id)
        if not model:
            return {"model_id": model_id, "exists": False, "gated": False}
        gated = model.get("gated", False)
        if not gated:
            return {"model_id": model_id, "exists": True, "gated": False, "access": True}
        # Es gated: verificar si el usuario tiene acceso
        if self.backend == "huggingface" and self.token:
            try:
                # Intentar acceder a los archivos del modelo
                resp = requests.get(
                    f"https://huggingface.co/api/models/{model_id}/tree/main",
                    headers=self._headers(), timeout=15,
                )
                has_access = resp.status_code == 200
                return {
                    "model_id": model_id, "exists": True, "gated": True,
                    "access": has_access,
                    "message": "Access granted" if has_access else
                        "You must accept the model license at https://huggingface.co/" + model_id,
                }
            except Exception:
                pass
        return {
            "model_id": model_id, "exists": True, "gated": True,
            "access": False,
            "message": f"Gated model. Accept terms at https://huggingface.co/{model_id}",
        }

    def search_all(
        self, query: str, limit: int = 20,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Búsqueda global en modelos, datasets y spaces."""
        return {
            "models": self.list_models(search=query, limit=limit),
            "datasets": self.list_datasets(search=query, limit=limit),
            "spaces": self.list_spaces(search=query, limit=limit),
        }
