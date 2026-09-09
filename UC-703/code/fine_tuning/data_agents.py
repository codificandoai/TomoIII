"""
UC-703 fine_tuning — Data curation, leakage audit y versionado de datasets.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fine_tuning.models_ft import CurationResult, DatasetVersion, LeakageReport


class DataCurationAgent:
    """
    Limpia, deduplica, valida chat templates y muestrea casos dudosos para HITL.

    En producción delegaría a un pipeline de ETL/LLM; aquí usa heurísticas
    deterministas y reproducibles para tests.
    """

    def __init__(self, template: str = "default-chat-template") -> None:
        self.template = template

    def curate(
        self,
        raw_samples: List[Dict[str, Any]],
        dataset_id: str = "",
        output_uri: str = "s3://uc703/curated/{dataset_id}",
    ) -> CurationResult:
        seen = set()
        cleaned = []
        duplicates = 0
        hitl_flagged = []
        for idx, sample in enumerate(raw_samples):
            text = json.dumps(sample, sort_keys=True)
            if text in seen:
                duplicates += 1
                continue
            seen.add(text)
            # Marcar como dudoso si el sample carece de instrucción clara o es muy corto.
            instruction = str(sample.get("instruction", "")).strip()
            if len(instruction) < 10:
                hitl_flagged.append({"index": idx, "reason": "instruction_too_short"})
            cleaned.append(sample)
        result = CurationResult(
            dataset_id=dataset_id,
            cleaned_samples=len(cleaned),
            duplicates_removed=duplicates,
            hitl_flagged_samples=hitl_flagged,
            template_valid=bool(self.template),
            output_uri=output_uri.format(dataset_id=dataset_id) if dataset_id else output_uri,
        )
        return result


class LeakageAuditAgent:
    """
    Detecta solapamiento train/eval mediante n-grams simples y similitud por
    embeddings simulados (hash/shingles).
    """

    def __init__(self, ngram_threshold: float = 0.05, embedding_threshold: float = 0.85) -> None:
        self.ngram_threshold = ngram_threshold
        self.embedding_threshold = embedding_threshold

    def _shingles(self, text: str, n: int = 4) -> set:
        text = text.lower()
        return set(text[i:i+n] for i in range(len(text)-n+1)) if len(text) >= n else set()

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, dict):
            return " ".join(LeakageAuditAgent._extract_text(v) for v in value.values())
        if isinstance(value, list):
            return " ".join(LeakageAuditAgent._extract_text(v) for v in value)
        if isinstance(value, str):
            return value
        return str(value)

    def audit(
        self,
        train_samples: List[Dict[str, Any]],
        eval_samples: List[Dict[str, Any]],
        dataset_id: str = "",
    ) -> LeakageReport:
        train_texts = [self._extract_text(s) for s in train_samples]
        eval_texts = [self._extract_text(s) for s in eval_samples]
        leaked = []
        max_ngram = 0.0
        max_emb = 0.0
        for et in eval_texts:
            es = self._shingles(et)
            if not es:
                continue
            for tt in train_texts:
                ts = self._shingles(tt)
                if not ts:
                    continue
                inter = len(es & ts)
                union = len(es | ts)
                ngram_sim = inter / union if union else 0.0
                # Simulación de embedding similarity basada en proporción de shingles compartidos escalada.
                emb_sim = ngram_sim * 1.2 if ngram_sim < 0.85 else ngram_sim
                emb_sim = min(emb_sim, 1.0)
                if ngram_sim > max_ngram:
                    max_ngram = ngram_sim
                if emb_sim > max_emb:
                    max_emb = emb_sim
                if ngram_sim > self.ngram_threshold or emb_sim > self.embedding_threshold:
                    leaked.append({
                        "eval_sample": et[:200],
                        "train_sample": tt[:200],
                        "ngram_similarity": round(ngram_sim, 4),
                        "embedding_similarity": round(emb_sim, 4),
                    })
        passed = max_ngram <= self.ngram_threshold and max_emb <= self.embedding_threshold
        return LeakageReport(
            dataset_id=dataset_id,
            ngram_overlap_score=max_ngram,
            embedding_overlap_score=max_emb,
            leaked_samples=leaked[:10],
            passed=passed,
        )


class DatasetVersionRegistry:
    """
    Registro atómico de versiones de dataset: datos + prompt template + seed.
    """

    def __init__(self) -> None:
        self._versions: Dict[str, DatasetVersion] = {}

    def _hash(self, version: DatasetVersion) -> str:
        payload = {
            "dataset_id": version.dataset_id,
            "version": version.version,
            "prompt_template": version.prompt_template,
            "seed": version.seed,
            "splits": {k: v for k, v in sorted(version.splits.items())},
            "num_samples": version.num_samples,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def register(
        self,
        dataset_id: str,
        prompt_template: str,
        seed: int,
        splits: Dict[str, str],
        num_samples: int,
        version: str = "v1",
    ) -> DatasetVersion:
        dv = DatasetVersion(
            dataset_id=dataset_id,
            version=version,
            prompt_template=prompt_template,
            seed=seed,
            splits=splits,
            num_samples=num_samples,
        )
        dv.audit_hash = self._hash(dv)
        self._versions[dv.dataset_id] = dv
        return dv

    def get(self, dataset_id: str) -> Optional[DatasetVersion]:
        return self._versions.get(dataset_id)

    def verify_template_matches(self, dataset_id: str, expected_template: str) -> bool:
        dv = self._versions.get(dataset_id)
        if not dv:
            return False
        return dv.prompt_template == expected_template
