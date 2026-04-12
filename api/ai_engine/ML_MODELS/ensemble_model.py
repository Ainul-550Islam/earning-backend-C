"""
api/ai_engine/ML_MODELS/ensemble_model.py
==========================================
Ensemble Model — multiple models combine করে better performance।
Voting, stacking, blending, bagging। 
Fraud detection, churn prediction এ extra accuracy এর জন্য।
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class EnsembleModel:
    """
    Ensemble learning engine।
    Combine multiple base models for superior performance।
    """

    METHODS = ['voting', 'averaging', 'stacking', 'blending', 'max_voting']

    def __init__(self, models: List[Any] = None, method: str = 'voting',
                 weights: List[float] = None):
        self.models    = models or []
        self.method    = method
        self.weights   = weights  # For weighted voting/averaging
        self.meta_model = None    # For stacking

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        """All base models train করো।"""
        for i, model in enumerate(self.models):
            try:
                model.fit(X_train, y_train)
                logger.info(f"Ensemble model {i+1}/{len(self.models)} trained")
            except Exception as e:
                logger.error(f"Model {i+1} training failed: {e}")

        # Stacking: train meta-model on validation predictions
        if self.method == 'stacking' and X_val is not None:
            self._train_meta_model(X_val, y_val)

        logger.info(f"Ensemble ({self.method}) training complete — {len(self.models)} base models")
        return self

    def predict(self, X) -> List:
        """Ensemble prediction করো।"""
        if not self.models:
            return []

        try:
            if self.method == 'stacking' and self.meta_model:
                return self._stack_predict(X)
            elif self.method in ('voting', 'max_voting'):
                return self._vote_predict(X)
            elif self.method in ('averaging', 'blending'):
                return self._average_predict(X)
            else:
                return self._vote_predict(X)
        except Exception as e:
            logger.error(f"Ensemble predict error: {e}")
            return self.models[0].predict(X).tolist() if self.models else []

    def predict_proba(self, X) -> Optional[Any]:
        """Probability predictions from ensemble।"""
        try:
            import numpy as np
            probas = []
            for model in self.models:
                if hasattr(model, 'predict_proba'):
                    probas.append(model.predict_proba(X))

            if not probas:
                return None

            # Weighted average of probabilities
            if self.weights and len(self.weights) == len(probas):
                w = [wi / sum(self.weights) for wi in self.weights]
                return np.average(probas, axis=0, weights=w)
            return np.mean(probas, axis=0)

        except Exception as e:
            logger.error(f"Ensemble proba error: {e}")
            return None

    def _vote_predict(self, X) -> List:
        """Majority voting।"""
        import numpy as np
        from scipy import stats

        all_preds = []
        for model in self.models:
            try:
                preds = model.predict(X)
                all_preds.append(preds)
            except Exception as e:
                logger.warning(f"Model predict skipped: {e}")

        if not all_preds:
            return []

        all_preds_arr = np.array(all_preds)
        # Majority vote
        voted, _ = stats.mode(all_preds_arr, axis=0, keepdims=False)
        return voted.flatten().tolist()

    def _average_predict(self, X) -> List:
        """Averaged predictions (for regression or probability-based)।"""
        import numpy as np
        all_probas = self.predict_proba(X)
        if all_probas is not None:
            return (all_probas[:, 1] >= 0.5).astype(int).tolist()

        all_preds = [model.predict(X) for model in self.models if hasattr(model, 'predict')]
        if not all_preds:
            return []
        return np.mean(all_preds, axis=0).round().astype(int).tolist()

    def _stack_predict(self, X) -> List:
        """Stacking with meta-model।"""
        import numpy as np
        meta_features = self._get_meta_features(X)
        return self.meta_model.predict(meta_features).tolist()

    def _get_meta_features(self, X):
        """Base model predictions → meta features।"""
        import numpy as np
        meta = []
        for model in self.models:
            try:
                if hasattr(model, 'predict_proba'):
                    preds = model.predict_proba(X)[:, 1]
                else:
                    preds = model.predict(X).astype(float)
                meta.append(preds)
            except Exception as e:
                logger.warning(f"Meta feature error: {e}")
        return np.column_stack(meta) if meta else X

    def _train_meta_model(self, X_val, y_val):
        """Meta-model (level-2) train করো।"""
        try:
            from sklearn.linear_model import LogisticRegression
            meta_features  = self._get_meta_features(X_val)
            self.meta_model = LogisticRegression(random_state=42, max_iter=200)
            self.meta_model.fit(meta_features, y_val)
            logger.info("Stacking meta-model trained")
        except Exception as e:
            logger.error(f"Meta-model training error: {e}")

    def add_model(self, model, weight: float = 1.0):
        """Runtime এ নতুন model add করো।"""
        self.models.append(model)
        if self.weights is not None:
            self.weights.append(weight)
        logger.info(f"Model added to ensemble. Total: {len(self.models)}")

    def evaluate(self, X_test, y_test) -> dict:
        """Ensemble performance evaluate করো।"""
        try:
            from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
            import numpy as np

            y_pred  = self.predict(X_test)
            y_proba = self.predict_proba(X_test)
            y_prob  = y_proba[:, 1] if y_proba is not None else np.array(y_pred, dtype=float)

            return {
                'accuracy':  round(float(accuracy_score(y_test, y_pred)), 4),
                'f1_score':  round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
                'auc_roc':   round(float(roc_auc_score(y_test, y_prob)), 4),
                'n_models':  len(self.models),
                'method':    self.method,
            }
        except Exception as e:
            return {'error': str(e)}

    def compare_individual_vs_ensemble(self, X_test, y_test) -> dict:
        """Individual models vs ensemble performance compare করো।"""
        try:
            from sklearn.metrics import f1_score

            individual_scores = []
            for i, model in enumerate(self.models):
                preds = model.predict(X_test)
                score = f1_score(y_test, preds, zero_division=0)
                individual_scores.append({'model_index': i, 'f1': round(score, 4)})

            ensemble_preds = self.predict(X_test)
            ensemble_f1    = f1_score(y_test, ensemble_preds, zero_division=0)

            best_individual = max(individual_scores, key=lambda x: x['f1'])

            return {
                'ensemble_f1':       round(ensemble_f1, 4),
                'best_individual':   best_individual,
                'individual_scores': individual_scores,
                'ensemble_wins':     ensemble_f1 > best_individual['f1'],
                'lift_over_best':    round((ensemble_f1 - best_individual['f1']) * 100, 2),
            }
        except Exception as e:
            return {'error': str(e)}
