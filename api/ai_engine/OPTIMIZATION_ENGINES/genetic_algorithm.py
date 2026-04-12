"""
api/ai_engine/OPTIMIZATION_ENGINES/genetic_algorithm.py
========================================================
Genetic Algorithm — evolutionary optimization for complex params。
"""

import random


class GeneticOptimizer:
    def __init__(self, param_ranges: dict, population_size: int = 20,
                 generations: int = 10):
        self.param_ranges  = param_ranges
        self.population_size = population_size
        self.generations   = generations

    def optimize(self, fitness_fn) -> dict:
        population = [self._random_individual() for _ in range(self.population_size)]
        best       = None

        for gen in range(self.generations):
            scored = [(ind, fitness_fn(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)
            best   = scored[0][0]

            # Selection + crossover + mutation
            elite   = [ind for ind, _ in scored[:self.population_size // 2]]
            new_pop = elite.copy()
            while len(new_pop) < self.population_size:
                p1, p2 = random.choices(elite, k=2)
                child  = self._crossover(p1, p2)
                child  = self._mutate(child)
                new_pop.append(child)
            population = new_pop

        return best or {}

    def _random_individual(self) -> dict:
        return {
            k: random.uniform(lo, hi) if isinstance(lo, float) else random.randint(lo, hi)
            for k, (lo, hi) in self.param_ranges.items()
        }

    def _crossover(self, p1: dict, p2: dict) -> dict:
        return {k: p1[k] if random.random() > 0.5 else p2[k] for k in p1}

    def _mutate(self, ind: dict, rate: float = 0.1) -> dict:
        result = dict(ind)
        for k, (lo, hi) in self.param_ranges.items():
            if random.random() < rate:
                result[k] = random.uniform(lo, hi) if isinstance(lo, float) else random.randint(lo, hi)
        return result
