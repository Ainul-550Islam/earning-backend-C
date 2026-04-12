"""
api/ai_engine/OPTIMIZATION_ENGINES/timing_optimizer.py
======================================================
Timing Optimizer — best time to send offers/notifications।
"""

import logging
logger = logging.getLogger(__name__)


class TimingOptimizer:
    PEAK_HOURS_BD = [8, 9, 10, 13, 18, 19, 20, 21]

    def optimal_send_time(self, user_activity_hours: list = None,
                           timezone: str = 'Asia/Dhaka') -> dict:
        if user_activity_hours:
            peak = max(set(user_activity_hours), key=user_activity_hours.count)
            return {'optimal_hour': peak, 'source': 'user_history'}
        return {'optimal_hour': 19, 'source': 'default_peak', 'peak_hours': self.PEAK_HOURS_BD}


"""
api/ai_engine/OPTIMIZATION_ENGINES/placement_optimizer.py
==========================================================
Placement Optimizer — best position/slot for offers/ads।
"""


class PlacementOptimizer:
    def optimize(self, items: list, positions: int = 5) -> list:
        scored = sorted(items, key=lambda x: x.get('score', 0) * x.get('ctr', 0.05), reverse=True)
        return [
            {**item, 'position': i + 1, 'expected_ctr': round(0.12 * (0.85 ** i), 4)}
            for i, item in enumerate(scored[:positions])
        ]


"""
api/ai_engine/OPTIMIZATION_ENGINES/inventory_optimizer.py
==========================================================
Inventory Optimizer — offer/ad inventory management।
"""


class InventoryOptimizer:
    def optimize_allocation(self, offers: list, total_budget: float) -> list:
        if not offers or total_budget <= 0:
            return offers

        total_priority = sum(o.get('priority_score', 1.0) for o in offers) or 1
        result = []
        for offer in offers:
            share = offer.get('priority_score', 1.0) / total_priority
            result.append({**offer, 'allocated_budget': round(total_budget * share, 2)})
        return result


"""
api/ai_engine/OPTIMIZATION_ENGINES/supply_chain_optimizer.py
=============================================================
Supply Chain Optimizer (placeholder for digital supply chains)。
"""


class SupplyChainOptimizer:
    def optimize(self, supply_data: dict) -> dict:
        return {'status': 'optimized', 'recommendation': 'maintain_current_supply'}


"""
api/ai_engine/OPTIMIZATION_ENGINES/route_optimizer.py
======================================================
Route Optimizer — user journey optimization。
"""


class RouteOptimizer:
    def optimize_journey(self, user_journey: list) -> dict:
        if not user_journey:
            return {'optimized': False}
        # Identify drop-off points
        drop_offs = [step for i, step in enumerate(user_journey) if i > 0 and step.get('completed') is False]
        return {
            'total_steps':   len(user_journey),
            'drop_offs':     drop_offs,
            'completion_rate': round((len(user_journey) - len(drop_offs)) / max(len(user_journey), 1), 4),
            'optimization':  'simplify_step_3' if len(drop_offs) > 0 else 'no_action',
        }


"""
api/ai_engine/OPTIMIZATION_ENGINES/resource_allocator.py
=========================================================
Resource Allocator — AI compute resource allocation।
"""


class ResourceAllocator:
    def allocate(self, tasks: list, total_capacity: float) -> list:
        if not tasks:
            return []
        total_priority = sum(t.get('priority', 1) for t in tasks) or 1
        return [
            {**t, 'allocated': round(total_capacity * t.get('priority', 1) / total_priority, 2)}
            for t in tasks
        ]


"""
api/ai_engine/OPTIMIZATION_ENGINES/multivariate_optimizer.py
=============================================================
Multivariate Test Optimizer।
"""


class MultivariateOptimizer:
    def analyze(self, variants: list) -> dict:
        if not variants:
            return {}
        best = max(variants, key=lambda v: v.get('conversion_rate', 0))
        return {
            'best_variant':   best.get('name', 'unknown'),
            'best_cvr':       best.get('conversion_rate', 0),
            'all_variants':   variants,
        }


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


"""
api/ai_engine/OPTIMIZATION_ENGINES/gradient_boosting.py
========================================================
Gradient Boosting Wrapper — unified GBM interface।
"""


class GradientBoostingOptimizer:
    def __init__(self, library: str = 'auto'):
        self.library = library
        self.model   = None

    def build(self, task: str = 'classification', params: dict = None) -> object:
        params = params or {}
        try:
            if self.library in ('xgboost', 'auto'):
                from ..INTEGRATIONS.sklearn_integration import XGBoostIntegration
                return XGBoostIntegration().build_classifier(params)
        except Exception:
            pass
        try:
            if self.library in ('lightgbm', 'auto'):
                from ..INTEGRATIONS.sklearn_integration import LightGBMIntegration
                return LightGBMIntegration().build_classifier(params)
        except Exception:
            pass
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier(**params)


"""
api/ai_engine/OPTIMIZATION_ENGINES/bayesian_optimizer.py
=========================================================
Bayesian Optimizer — Gaussian Process based optimization。
"""


class BayesianOptimizer:
    def optimize(self, objective_fn, param_bounds: dict,
                 n_calls: int = 20) -> dict:
        try:
            from skopt import gp_minimize
            from skopt.space import Real, Integer

            space = []
            keys  = list(param_bounds.keys())
            for k in keys:
                lo, hi = param_bounds[k]
                space.append(Real(lo, hi) if isinstance(lo, float) else Integer(lo, hi))

            result = gp_minimize(
                lambda x: -objective_fn(dict(zip(keys, x))),
                space, n_calls=n_calls, random_state=42
            )
            return {
                'best_params': dict(zip(keys, result.x)),
                'best_score':  round(-result.fun, 4),
                'n_calls':     n_calls,
            }
        except ImportError:
            logger.warning("scikit-optimize not installed. pip install scikit-optimize")
            # Fallback: random search
            best_score = -float('inf')
            best_params = {}
            for _ in range(n_calls):
                params = {
                    k: random.uniform(lo, hi) if isinstance(lo, float) else random.randint(lo, hi)
                    for k, (lo, hi) in param_bounds.items()
                }
                score = objective_fn(params)
                if score > best_score:
                    best_score, best_params = score, params
            return {'best_params': best_params, 'best_score': round(best_score, 4), 'method': 'random_fallback'}
