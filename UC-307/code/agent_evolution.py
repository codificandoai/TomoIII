"""Operadores evolutivos para ADN de agentes: mutación, cruza y población.

Cada agente se representa como un diccionario de hiperparámetros
(`learning_rate`, `temperature`, etc.) que el orquestador puede modificar
para mejorar, mutar o reproducir agentes.
"""
from __future__ import annotations

import copy
import random
from typing import Dict, List, Optional

from config import EVOLUTION
from models import AgentDNA, DecisionAction


class DNAOperators:
    """Operadores genéticos sobre un `AgentDNA`."""

    def __init__(self, config=EVOLUTION):
        self.cfg = config

    def default_dna(self, agent_id: Optional[str] = None) -> AgentDNA:
        """Genera un ADN con los hiperparámetros por defecto."""
        params = dict(self.cfg.default_hyperparams)
        return AgentDNA(
            agent_id=agent_id or f"agent_{random.randint(1000, 9999)}",
            version=1,
            hyperparams=params,
        )

    def mutate(self, dna: AgentDNA) -> AgentDNA:
        """Crea una nueva versión del ADN perturbando hiperparámetros."""
        new_params = copy.deepcopy(dna.hyperparams)
        for key, value in new_params.items():
            if random.random() < self.cfg.mutation_probability and key in self.cfg.param_bounds:
                lo, hi = self.cfg.param_bounds[key]
                delta = random.uniform(-1, 1) * self.cfg.mutation_strength * (hi - lo)
                new_value = max(lo, min(hi, value + delta))
                new_params[key] = round(new_value, 6)
        return AgentDNA(
            agent_id=dna.agent_id,
            version=dna.version + 1,
            hyperparams=new_params,
            parent_ids=dna.parent_ids + [dna.agent_id],
        )

    def crossover(self, parent_a: AgentDNA, parent_b: AgentDNA) -> AgentDNA:
        """Produce un hijo mezclando los hiperparámetros de dos progenitores."""
        child_params: Dict[str, float] = {}
        blend = self.cfg.crossover_blend
        keys = set(parent_a.hyperparams) | set(parent_b.hyperparams)
        for key in keys:
            a = parent_a.hyperparams.get(key)
            b = parent_b.hyperparams.get(key)
            if a is not None and b is not None:
                child_params[key] = round(blend * a + (1 - blend) * b, 6)
            elif a is not None:
                child_params[key] = a
            elif b is not None:
                child_params[key] = b

        # Aplicar límites
        for key in child_params:
            if key in self.cfg.param_bounds:
                lo, hi = self.cfg.param_bounds[key]
                child_params[key] = max(lo, min(hi, child_params[key]))

        return AgentDNA(
            agent_id=f"child_{random.randint(1000, 9999)}",
            version=1,
            hyperparams=child_params,
            parent_ids=[parent_a.agent_id, parent_b.agent_id],
        )

    def adjust_params(self, dna: AgentDNA, reason: str = "") -> AgentDNA:
        """Ajusta hiperparámetros de forma heurística según el tipo de problema.

        Por ejemplo: si el problema es de calidad baja se reduce `temperature`
        para hacer al agente más determinista; si es de eficiencia se reduce
        `max_iterations` y se sube `learning_rate` ligeramente.
        """
        new_params = copy.deepcopy(dna.hyperparams)
        lowered = False
        if "calidad" in reason.lower() or "quality" in reason.lower():
            if "temperature" in new_params:
                new_params["temperature"] = max(0.1, new_params["temperature"] * 0.9)
            if "top_p" in new_params:
                new_params["top_p"] = max(0.1, new_params["top_p"] * 0.95)
            lowered = True
        if "eficiencia" in reason.lower() or "efficiency" in reason.lower():
            if "max_iterations" in new_params:
                new_params["max_iterations"] = max(1.0, new_params["max_iterations"] * 0.85)
            if "exploration_factor" in new_params:
                new_params["exploration_factor"] = max(0.0, new_params["exploration_factor"] * 0.9)
            lowered = True
        if not lowered:
            # Ajuste genérico: reducir ligeramente todos los factores de consumo
            for key in ["temperature", "max_iterations", "exploration_factor"]:
                if key in new_params and key in self.cfg.param_bounds:
                    lo, hi = self.cfg.param_bounds[key]
                    new_params[key] = max(lo, new_params[key] * 0.95)
        return AgentDNA(
            agent_id=dna.agent_id,
            version=dna.version + 1,
            hyperparams=new_params,
            parent_ids=dna.parent_ids + [dna.agent_id],
        )

    def apply_action(
        self,
        action: DecisionAction,
        dna: AgentDNA,
        mate_dna: Optional[AgentDNA] = None,
        reason: str = "",
    ) -> Optional[AgentDNA]:
        """Aplica una acción evolutiva y devuelve el ADN resultante o None si se elimina."""
        if action == DecisionAction.MUTATE:
            return self.mutate(dna)
        if action == DecisionAction.ADJUST_PARAMS:
            return self.adjust_params(dna, reason)
        if action == DecisionAction.GROW_CROSSOVER and mate_dna is not None:
            return self.crossover(dna, mate_dna)
        if action == DecisionAction.GROW_RANDOM:
            return self.default_dna()
        # PERSIST, RETRAIN, ELIMINATE no alteran el ADN
        return dna


class AgentPopulation:
    """Población de agentes con operaciones de registro, eliminación y cruza."""

    def __init__(self, operators: Optional[DNAOperators] = None):
        self.agents: Dict[str, AgentDNA] = {}
        self.operators = operators or DNAOperators()

    def register(self, dna: AgentDNA) -> None:
        self.agents[dna.agent_id] = dna

    def get(self, agent_id: str) -> Optional[AgentDNA]:
        return self.agents.get(agent_id)

    def eliminate(self, agent_id: str) -> bool:
        return self.agents.pop(agent_id, None) is not None

    def size(self) -> int:
        return len(self.agents)

    def select_mate(self, agent_id: str) -> Optional[AgentDNA]:
        """Selecciona otro agente distinto para cruza."""
        others = [a for aid, a in self.agents.items() if aid != agent_id]
        if not others:
            return None
        return random.choice(others)

    def evolve_one(
        self,
        agent_id: str,
        action: DecisionAction,
        reason: str = "",
        mate_id: Optional[str] = None,
    ) -> Optional[AgentDNA]:
        """Aplica una acción sobre un agente registrado y actualiza la población."""
        dna = self.agents.get(agent_id)
        if dna is None:
            return None

        mate_dna = self.agents.get(mate_id) if mate_id else None

        if action == DecisionAction.ELIMINATE:
            self.eliminate(agent_id)
            return None

        new_dna = self.operators.apply_action(action, dna, mate_dna=mate_dna, reason=reason)
        if new_dna is None:
            return None

        self.register(new_dna)
        return new_dna
