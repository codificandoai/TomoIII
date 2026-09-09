"""Versionado de prompts con trazabilidad regulatoria tipo Git."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from compliance_as_code.models_compliance import PromptVersion


class PromptVersionControl:
    """
    Gestiona versiones de prompts con author, diff, approvals y flag de
    cambio regulatorio. Simula Git URIs sin depender de git CLI.
    """

    def __init__(self) -> None:
        self._versions: Dict[str, List[PromptVersion]] = {}

    def commit(
        self,
        prompt_name: str,
        content: str,
        author: str,
        commit_message: str = "",
        regulatory_change: bool = False,
        approved_by: Optional[List[str]] = None,
    ) -> PromptVersion:
        versions = self._versions.setdefault(prompt_name, [])
        parent_id = versions[-1].version_id if versions else ""
        prev_content = versions[-1].content if versions else ""
        diff_summary = self._diff(prev_content, content)
        pv = PromptVersion(
            prompt_name=prompt_name,
            content=content,
            author=author,
            parent_version_id=parent_id,
            commit_message=commit_message,
            regulatory_change=regulatory_change,
            approved_by=approved_by or [],
            diff_summary=diff_summary,
        )
        versions.append(pv)
        return pv

    def get_version(self, prompt_name: str, version_id: str) -> Optional[PromptVersion]:
        for v in self._versions.get(prompt_name, []):
            if v.version_id == version_id:
                return v
        return None

    def latest(self, prompt_name: str) -> Optional[PromptVersion]:
        versions = self._versions.get(prompt_name, [])
        return versions[-1] if versions else None

    def history(self, prompt_name: str) -> List[PromptVersion]:
        return list(self._versions.get(prompt_name, []))

    def list_prompts(self) -> List[str]:
        return list(self._versions.keys())

    def approve(self, prompt_name: str, version_id: str, approver: str) -> Optional[PromptVersion]:
        v = self.get_version(prompt_name, version_id)
        if v and approver not in v.approved_by:
            v.approved_by.append(approver)
        return v

    def _diff(self, old: str, new: str) -> str:
        if old == new:
            return "no changes"
        # Simple diff summary
        old_words = set(old.split())
        new_words = set(new.split())
        added = new_words - old_words
        removed = old_words - new_words
        parts: List[str] = []
        if added:
            parts.append(f"+{len(added)} words")
        if removed:
            parts.append(f"-{len(removed)} words")
        return ", ".join(parts) if parts else "content changed"
