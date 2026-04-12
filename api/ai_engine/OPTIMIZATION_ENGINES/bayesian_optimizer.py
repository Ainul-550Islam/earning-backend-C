"""
api/ai_engine/OPTIMIZATION_ENGINES/bayesian_optimizer.py
=========================================================
Bayesian Optimizer — Gaussian Process based hyperparameter optimization।
scikit-optimize, Optuna, custom implementation।
Hyperparameter tuning, campaign budget allocation, pricing optimization।
"""

import logging
import math
import random
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BayesianOptimizer:
    """
    Bayesian optimization using Gaussian Process surrogate model।
    Efficient optimization with fewer function evaluations।
    """

    def __init__(self, n_initial_points: int = 5, xi: float = 0.01):
        self.n_initial_points = n_initial_points
        self.xi               = xi  # Exploration-exploitation tradeoff
        self.X_observed: List[List[float]] = []
        self.y_observed: List[float]       = []

    def optimize(self, objective_fn: Callable, param_bounds: Dict,
                  n_calls: int = 20, maximize: bool = True) -> dict:
        """
        Objective function optimize করো।
        
        Args:
            objective_fn: function to optimize — takes dict, returns float
            param_bounds: {"lr": (0.001, 0.1), "n_estimators": (50, 500)}
            n_calls:      total function evaluations
            maximize:     True = maximize, False = minimize
        """
        # Try scikit-optimize first
        try:
            return self._skopt_optimize(objective_fn, param_bounds, n_calls, maximize)
        except ImportError:
            pass

        # Try Optuna
        try:
            return self._optuna_optimize(objective_fn, param_bounds, n_calls, maximize)
        except ImportError:
            pass

        # Fallback: random search with UCB
        return self._random_search(objective_fn, param_bounds, n_calls, maximize)

    def _skopt_optimize(self, objective_fn, param_bounds, n_calls, maximize) -> dict:
        """scikit-optimize Gaussian Process।"""
        from skopt import gp_minimize
        from skopt.space import Real, Integer

        keys   = list(param_bounds.keys())
        space  = []
        for k in keys:
            lo, hi = param_bounds[k]
            space.append(
                Real(lo, hi, name=k) if isinstance(lo, float)
                else Integer(int(lo), int(hi), name=k)
            )

        sign = -1 if maximize else 1

        def wrapped(x):
            params = dict(zip(keys, x))
            return sign * objective_fn(params)

        result = gp_minimize(
            wrapped, space, n_calls=n_calls,
            n_initial_points=self.n_initial_points,
            random_state=42, xi=self.xi,
        )

        best_params = dict(zip(keys, result.x))
        best_score  = sign * result.fun

        return {
            "best_params":  best_params,
            "best_score":   round(best_score, 6),
            "n_calls":      n_calls,
            "method":       "bayesian_gp",
            "all_scores":   [round(sign * y, 6) for y in result.func_vals],
            "convergence":  "converged" if len(result.func_vals) >= n_calls else "incomplete",
        }

    def _optuna_optimize(self, objective_fn, param_bounds, n_calls, maximize) -> dict:
        """Optuna TPE optimization।"""
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        direction = "maximize" if maximize else "minimize"

        def optuna_objective(trial):
            params = {}
            for k, (lo, hi) in param_bounds.items():
                if isinstance(lo, float):
                    params[k] = trial.suggest_float(k, lo, hi)
                else:
                    params[k] = trial.suggest_int(k, int(lo), int(hi))
            return objective_fn(params)

        study = optuna.create_study(direction=direction)
        study.optimize(optuna_objective, n_trials=n_calls, show_progress_bar=False)

        return {
            "best_params":  study.best_params,
            "best_score":   round(study.best_value, 6),
            "n_calls":      n_calls,
            "method":       "bayesian_optuna_tpe",
            "n_trials":     len(study.trials),
        }

    def _random_search(self, objective_fn, param_bounds, n_calls, maximize) -> dict:
        """Random search fallback।"""
        best_score  = -float("inf") if maximize else float("inf")
        best_params = {}
        all_scores  = []

        for _ in range(n_calls):
            params = {}
            for k, (lo, hi) in param_bounds.items():
                if isinstance(lo, float):
                    params[k] = lo + random.random() * (hi - lo)
                else:
                    params[k] = random.randint(int(lo), int(hi))

            score = objective_fn(params)
            all_scores.append(round(score, 6))

            if maximize and score > best_score:
                best_score, best_params = score, dict(params)
            elif not maximize and score < best_score:
                best_score, best_params = score, dict(params)

        return {
            "best_params": best_params,
            "best_score":  round(best_score, 6),
            "n_calls":     n_calls,
            "method":      "random_search_fallback",
            "all_scores":  all_scores,
        }

    def optimize_campaign_budget(self, channels: List[Dict],
                                  total_budget: float,
                                  roi_history: Dict[str, List[float]] = None) -> dict:
        """
        Marketing campaign budget Bayesian optimization করো।
        
        channels: [{"name": "facebook", "min": 1000, "max": 50000}]
        roi_history: historical ROI per channel
        """
        roi_history = roi_history or {}

        def budget_objective(allocation: dict) -> float:
            """Estimated total ROI for a given budget allocation।"""
            total_roi = 0.0
            for ch in channels:
                name    = ch["name"]
                budget  = allocation.get(name, 0)
                hist    = roi_history.get(name, [1.5])
                avg_roi = sum(hist) / len(hist)
                # Diminishing returns model
                adj_roi = avg_roi * (1 - 0.1 * math.log1p(budget / total_budget))
                total_roi += budget * adj_roi
            return total_roi / max(total_budget, 1)

        bounds = {ch["name"]: (ch.get("min", 0.0), float(ch.get("max", total_budget))) for ch in channels}

        result = self.optimize(budget_objective, bounds, n_calls=30, maximize=True)

        # Normalize to total budget
        raw_total = sum(result["best_params"].values())
        if raw_total > 0:
            scale  = total_budget / raw_total
            result["best_params"] = {k: round(v * scale, 2) for k, v in result["best_params"].items()}

        result["total_budget"]       = total_budget
        result["expected_roi"]       = round(result["best_score"], 4)
        result["optimization_type"]  = "campaign_budget"

        return result

    def optimize_ml_hyperparams(self, model_class, X_train, y_train,
                                  param_space: Dict = None) -> dict:
        """ML hyperparameters Bayesian optimize করো।"""
        from sklearn.model_selection import cross_val_score
        import numpy as np

        param_space = param_space or {
            "n_estimators": (50, 500),
            "max_depth":    (3, 12),
            "learning_rate": (0.01, 0.30),
        }

        def ml_objective(params) -> float:
            try:
                int_params = ["n_estimators", "max_depth", "min_samples_split", "n_neighbors"]
                for p in int_params:
                    if p in params:
                        params[p] = int(params[p])

                model  = model_class(**params)
                scores = cross_val_score(model, X_train, y_train, cv=3,
                                          scoring="f1_weighted", n_jobs=-1)
                return float(scores.mean())
            except Exception as e:
                logger.debug(f"ML objective error: {e}")
                return 0.0

        result = self.optimize(ml_objective, param_space, n_calls=25, maximize=True)

        # Convert int params
        int_params = ["n_estimators", "max_depth"]
        for p in int_params:
            if p in result["best_params"]:
                result["best_params"][p] = int(result["best_params"][p])

        result["optimization_type"] = "ml_hyperparameters"
        return result
