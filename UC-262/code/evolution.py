"""Motor evolutivo para UC-262: agentes con genoma, evaluación, selección y mutación."""
from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional, Tuple

from config import EvolutionConfig
from models import AgentCandidate, PlanEvaluation, PolicyGenome, TravelRequest
from planner import build_plan, default_weights
from world_simulator import WorldSimulator


GENOME_KEYS = ["cost", "time", "comfort", "loyalty", "risk"]


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(abs(weights.get(k, 0.0)) for k in GENOME_KEYS)
    if total <= 0:
        return default_weights()
    return {k: max(0.0, weights.get(k, 0.0)) / total for k in GENOME_KEYS}


def create_random_genome(agent_id: str, generation: int = 0, rng: Optional[random.Random] = None) -> PolicyGenome:
    rng = rng or random.Random()
    raw = {k: max(0.0, rng.gauss(0.2, 0.15)) for k in GENOME_KEYS}
    weights = normalize_weights(raw)
    return PolicyGenome(
        agent_id=agent_id,
        generation=generation,
        weights=weights,
        mutation_rate=max(0.05, min(0.5, rng.gauss(0.15, 0.05))),
        lineage=[agent_id],
    )


def mutate_genome(genome: PolicyGenome, rng: random.Random, mutation_rate: Optional[float] = None) -> PolicyGenome:
    rate = mutation_rate if mutation_rate is not None else genome.mutation_rate
    weights = copy.deepcopy(genome.weights)
    for k in GENOME_KEYS:
        if rng.random() < rate:
            delta = rng.gauss(0, 0.1)
            weights[k] = max(0.0, weights.get(k, 0.0) + delta)
    weights = normalize_weights(weights)
    new_mutation_rate = max(0.05, min(0.5, genome.mutation_rate + rng.gauss(0, 0.02)))
    return PolicyGenome(
        agent_id=f"{genome.agent_id}-m",
        generation=genome.generation + 1,
        weights=weights,
        mutation_rate=new_mutation_rate,
        lineage=genome.lineage + [genome.agent_id],
    )


def crossover(parent_a: PolicyGenome, parent_b: PolicyGenome, rng: random.Random) -> PolicyGenome:
    weights = {}
    for k in GENOME_KEYS:
        alpha = rng.random()
        weights[k] = alpha * parent_a.weights.get(k, 0.0) + (1 - alpha) * parent_b.weights.get(k, 0.0)
    weights = normalize_weights(weights)
    return PolicyGenome(
        agent_id=f"x-{parent_a.agent_id}-{parent_b.agent_id}",
        generation=max(parent_a.generation, parent_b.generation) + 1,
        weights=weights,
        mutation_rate=(parent_a.mutation_rate + parent_b.mutation_rate) / 2.0,
        lineage=parent_a.lineage + parent_b.lineage,
    )


class EvolutionEngine:
    """Gestiona una población de agentes candidatos y su evolución."""

    def __init__(
        self,
        world: WorldSimulator,
        config: EvolutionConfig,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.world = world
        self.config = config
        self.rng = rng or random.Random(config.population_size + config.generations)

    def seed_population(self, size: Optional[int] = None) -> List[PolicyGenome]:
        size = size or self.config.population_size
        return [
            create_random_genome(f"ag-{i:03d}", generation=0, rng=self.rng)
            for i in range(size)
        ]

    def evaluate(
        self,
        genome: PolicyGenome,
        request: TravelRequest,
        memory_rules: Optional[List[str]] = None,
    ) -> Tuple[AgentCandidate, Optional[PlanEvaluation]]:
        memory_rules = memory_rules or []
        itinerary, reasoning, missing_info = build_plan(request, self.world, genome.to_dict(), memory_rules)
        evaluation = PlanEvaluation(agent_id=genome.agent_id)
        if not itinerary:
            evaluation.violations.extend(missing_info)
            evaluation.fitness = 0.0
            return (
                AgentCandidate(
                    agent_id=genome.agent_id,
                    genome=genome.to_dict(),
                    plan=[],
                    evaluation=evaluation.to_dict(),
                    reasoning=reasoning,
                    alive=False,
                ),
                evaluation,
            )

        total_cost = sum(i.get("cost", 0.0) for i in itinerary)
        budget = request.budget or 1e9
        cost_score = 1.0 if total_cost <= budget else max(0.0, budget / total_cost)

        flight_durations = [
            i["details"].get("duration_minutes", 120) for i in itinerary if i["item_type"] == "flight"
        ]
        time_score = 1.0 - (sum(flight_durations) / max(len(flight_durations) * 300.0, 1))

        comfort_score = sum(
            1.0 if i.get("details", {}).get("direct") else 0.5 for i in itinerary
        ) / max(len(itinerary), 1)

        # Riesgo: número de escalas inferido por no directo
        risk_penalty = sum(
            0.2 for i in itinerary if i["item_type"] == "flight" and not i["details"].get("direct")
        )
        risk_score = max(0.0, 1.0 - risk_penalty)

        # Alineación con objetivos de largo plazo
        goal_alignment = 0.5
        goals = [g.lower() for g in (request.long_term_goals or [])]
        if "platino" in " ".join(goals) or "status" in " ".join(goals):
            # Placeholder: aerolínea preferida con status
            pref_airline = (request.preferences or {}).get("airline", "")
            if any(i["details"].get("airline") == pref_airline for i in itinerary if i["item_type"] == "flight"):
                goal_alignment += 0.3
        goal_alignment = min(1.0, goal_alignment)

        # Reglas de memoria violadas reducen fitness drásticamente
        rule_penalty = 0.0
        for i in itinerary:
            if i["item_type"] == "flight":
                for rule in memory_rules:
                    if "escala" in rule.lower() and "menores a 90" in rule:
                        if not i["details"].get("direct") and i["details"].get("duration_minutes", 120) < 90:
                            rule_penalty += 0.5
                            evaluation.violations.append(rule)

        weights = genome.weights
        fitness = (
            weights.get("cost", 0.0) * cost_score
            + weights.get("time", 0.0) * time_score
            + weights.get("comfort", 0.0) * comfort_score
            + weights.get("risk", 0.0) * risk_score
            + 0.2 * goal_alignment
            - rule_penalty
        )
        fitness = round(max(0.0, min(1.0, fitness)), 4)

        evaluation.fitness = fitness
        evaluation.cost_score = round(cost_score, 4)
        evaluation.time_score = round(time_score, 4)
        evaluation.comfort_score = round(comfort_score, 4)
        evaluation.risk_score = round(risk_score, 4)
        evaluation.goal_alignment = round(goal_alignment, 4)

        candidate = AgentCandidate(
            agent_id=genome.agent_id,
            genome=genome.to_dict(),
            plan=itinerary,
            evaluation=evaluation.to_dict(),
            reasoning=reasoning,
            alive=True,
        )
        return candidate, evaluation

    def evolve(
        self,
        request: TravelRequest,
        memory_rules: Optional[List[str]] = None,
        population: Optional[List[PolicyGenome]] = None,
    ) -> Tuple[List[AgentCandidate], Dict[str, Any]]:
        memory_rules = memory_rules or []
        stats = {
            "generations": self.config.generations,
            "population_size": self.config.population_size,
            "history": [],
        }

        pop = population or self.seed_population()
        best_overall: Optional[AgentCandidate] = None

        for generation in range(1, self.config.generations + 1):
            candidates = [self.evaluate(g, request, memory_rules)[0] for g in pop]
            candidates = sorted(candidates, key=lambda c: c.evaluation.get("fitness", 0.0), reverse=True)

            if candidates and candidates[0].alive:
                if best_overall is None or candidates[0].evaluation.get("fitness", 0.0) > best_overall.evaluation.get("fitness", 0.0):
                    best_overall = candidates[0]

            gen_stats = {
                "generation": generation,
                "best_fitness": candidates[0].evaluation.get("fitness", 0.0) if candidates else 0.0,
                "avg_fitness": round(
                    sum(c.evaluation.get("fitness", 0.0) for c in candidates) / max(len(candidates), 1), 4
                ),
                "alive": sum(1 for c in candidates if c.alive),
            }
            stats["history"].append(gen_stats)

            if generation == self.config.generations:
                break

            # Selección elitista + ruleta
            elite_count = max(1, int(self.config.elite_ratio * len(candidates)))
            elites = candidates[:elite_count]

            # Culling: eliminar los peores
            cull_count = max(0, int(self.config.cull_ratio * len(candidates)))
            survivors = candidates[:-cull_count] if cull_count < len(candidates) else candidates

            # Crear nueva población
            new_pop: List[PolicyGenome] = []
            for c in elites:
                genome = PolicyGenome(**c.genome)
                genome.generation = generation
                new_pop.append(genome)

            while len(new_pop) < self.config.population_size:
                op = self.rng.random()
                if op < 0.6 and len(survivors) >= 2:
                    parent_a, parent_b = self.rng.sample(survivors, 2)
                    child = crossover(
                        PolicyGenome(**parent_a.genome),
                        PolicyGenome(**parent_b.genome),
                        self.rng,
                    )
                elif survivors:
                    parent = self.rng.choice(survivors)
                    child = mutate_genome(PolicyGenome(**parent.genome), self.rng)
                else:
                    child = create_random_genome(f"rnd-{len(new_pop)}", generation, self.rng)
                new_pop.append(child)

            pop = new_pop[: self.config.population_size]

        final_candidates = [self.evaluate(g, request, memory_rules)[0] for g in pop]
        final_candidates = sorted(
            final_candidates,
            key=lambda c: c.evaluation.get("fitness", 0.0),
            reverse=True,
        )
        if best_overall is not None:
            # Asegurar que el mejor histórico esté presente
            if not any(c.agent_id == best_overall.agent_id for c in final_candidates):
                final_candidates.append(best_overall)
            final_candidates = sorted(
                final_candidates,
                key=lambda c: c.evaluation.get("fitness", 0.0),
                reverse=True,
            )
        return final_candidates, stats
