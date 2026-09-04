"""UC-313 — Workspace Global (GWT) explícito.

Este módulo envuelve la funcionalidad GWT ya implementada en SAM
(`SituationalAwarenessMiddleware`) para exponer una API nominal alineada con el
diagrama brain.png:

- Workspace Global compite, selecciona y difunde contenido.
- El broadcast llega a Self-Model, Memoria Episódica, Hipótesis y al Monitor
  Metacognitivo.
- Se persiste el contenido seleccionado en memoria episódica/vectorial.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from memory_router import IntelligentMemoryRouter
from sam import SituationalAwarenessMiddleware


class GlobalWorkspace:
    """Workspace Global (GWT) que integra percepción, memoria y self-model."""

    def __init__(
        self,
        memory_router: Optional[IntelligentMemoryRouter] = None,
        agent_identity: str = "UC313.GWT",
        max_memory_items: int = 7,
    ) -> None:
        self.sam = SituationalAwarenessMiddleware(
            agent_identity=agent_identity,
            max_memory_items=max_memory_items,
        )
        self.memory_router = memory_router or IntelligentMemoryRouter()

    def build_workspace(
        self,
        request: Any,
        snapshots: Dict[str, Any],
        signals: List[Dict[str, Any]],
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        alerts: Optional[List[str]] = None,
    ) -> Any:
        """Construye el Workspace Global a partir de percepción, memoria y self-model."""
        return self.sam.build_workspace(
            request=request,
            snapshots=snapshots,
            signals=signals,
            hypotheses=hypotheses,
            alerts=alerts,
        )

    def broadcast(
        self,
        workspace: Any,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Difunde el contenido seleccionado a los módulos suscritos y lo persiste."""
        messages = self.sam.broadcast_to_modules(workspace)
        selected = workspace.selected_hypothesis

        if persist and selected:
            # Persistir hipótesis seleccionada como episodio de memoria
            self.memory_router.store_episode(
                f"GWT selected hypothesis: {selected}",
                metadata={
                    "source": "global_workspace",
                    "broadcast_flags": workspace.broadcast.get("flags", []),
                    "self_model_confidence": workspace.self_model.get("confidence_level"),
                },
            )
            # Guardar en notepad de corto plazo como memoria de trabajo
            self.memory_router.store_working_memory(
                f"GWT broadcast: {selected.get('name', 'selection')}",
                note_type="gwt_broadcast",
                metadata={"flags": workspace.broadcast.get("flags", [])},
            )

        return {
            "messages": messages,
            "selected": selected,
            "flags": workspace.broadcast.get("flags", []),
        }

    def recall_relevant(
        self,
        query: str,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Recupera memorias relevantes para poblar el workspace."""
        return self.memory_router.retrieve(query).to_dict()
