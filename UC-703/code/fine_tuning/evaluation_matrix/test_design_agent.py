"""Diseño y versionado de pruebas reproducibles."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.evaluation_matrix.models_cem import (
    Checkpoint,
    GoldenSet,
    StaticPrompt,
    TestCell,
)


class TestDesignAgent:
    """
    Diseña y versiona conjuntos de pruebas reproducibles: prompts estáticos,
    golden sets y celdas A/B/C.
    """

    VALID_CATEGORIES = {"use_case", "edge_case", "adversarial", "safety", "fairness"}
    VALID_RISKS = {"low", "medium", "high", "critical"}

    def __init__(self) -> None:
        self._prompts: Dict[str, StaticPrompt] = {}
        self._golden_sets: Dict[str, GoldenSet] = {}
        self._cells: Dict[str, TestCell] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}

    def create_static_prompt(
        self,
        name: str,
        prompt: str,
        category: str = "use_case",
        risk_level: str = "medium",
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> StaticPrompt:
        if category not in self.VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")
        if risk_level not in self.VALID_RISKS:
            raise ValueError(f"Invalid risk_level: {risk_level}")
        sp = StaticPrompt(
            name=name,
            prompt=prompt,
            category=category,
            risk_level=risk_level,
            version=version,
            tags=tags or [],
        )
        self._prompts[sp.prompt_id] = sp
        return sp

    def create_golden_set(
        self,
        name: str,
        records: List[Dict[str, Any]],
        version: str = "1.0.0",
    ) -> GoldenSet:
        gs = GoldenSet(name=name, version=version, records=records)
        self._golden_sets[gs.set_id] = gs
        return gs

    def create_test_cell(
        self,
        name: str,
        model_version: str,
        traffic_pct: float,
        prompt_ids: Optional[List[str]] = None,
        golden_set_id: str = "",
    ) -> TestCell:
        prompts = [self._prompts[pid] for pid in (prompt_ids or []) if pid in self._prompts]
        cell = TestCell(
            name=name,
            model_version=model_version,
            traffic_pct=traffic_pct,
            prompts=prompts,
            golden_set_id=golden_set_id,
        )
        self._cells[cell.cell_id] = cell
        return cell

    def create_checkpoint(
        self,
        name: str,
        prompt_ids: Optional[List[str]] = None,
        golden_set_ids: Optional[List[str]] = None,
        cell_ids: Optional[List[str]] = None,
        risk_signals: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> Checkpoint:
        prompts = [self._prompts[pid] for pid in (prompt_ids or []) if pid in self._prompts]
        golden_sets = [self._golden_sets[gid] for gid in (golden_set_ids or []) if gid in self._golden_sets]
        cells = [self._cells[cid] for cid in (cell_ids or []) if cid in self._cells]
        cp = Checkpoint(
            name=name,
            version=version,
            static_prompts=prompts,
            golden_sets=golden_sets,
            test_cells=cells,
            risk_signals=risk_signals or [],
        )
        self._checkpoints[cp.checkpoint_id] = cp
        return cp

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(checkpoint_id)

    def list_checkpoints(self) -> List[Checkpoint]:
        return list(self._checkpoints.values())

    def evolve_checkpoint(
        self,
        checkpoint_id: str,
        new_prompts: Optional[List[StaticPrompt]] = None,
        new_risk_signals: Optional[List[str]] = None,
    ) -> Optional[Checkpoint]:
        old = self._checkpoints.get(checkpoint_id)
        if not old:
            return None
        # Add new prompts and risk signals; bump minor version
        current_version = old.version.split(".")
        current_version[1] = str(int(current_version[1]) + 1)
        new_version = ".".join(current_version)
        prompts = list(old.static_prompts) + list(new_prompts or [])
        risk_signals = list(old.risk_signals) + list(new_risk_signals or [])
        cp = Checkpoint(
            name=old.name,
            version=new_version,
            static_prompts=prompts,
            golden_sets=old.golden_sets,
            test_cells=old.test_cells,
            risk_signals=risk_signals,
        )
        self._checkpoints[cp.checkpoint_id] = cp
        return cp
