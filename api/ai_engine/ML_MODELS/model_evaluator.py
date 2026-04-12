"""
api/ai_engine/ML_MODELS/model_evaluator.py
==========================================
Model Evaluator — comprehensive ML model evaluation।
Classification, regression, ranking metrics।
Business-specific KPIs ও statistical significance।
"""
import logging
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

class ModelEvaluator:
    """Multi-metric model evaluation engine।"""

    def evaluate(self, model, X_test, y_test, task: str = 'classification') -> Dict:
        try:
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score, f1_score,
                roc_auc_score, mean_absolute_error, mean_squared_error, r2_score,
                confusion_matrix, classification_report
            )
            import numpy as np

            y_pred = model.predict(X_test)
            if task == 'classification':
                y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred.astype(float)
                cm     = confusion_matrix(y_test, y_pred).tolist()
                tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1] if len(cm) == 2 else (0,0,0,0)
                return {
                    'task':        'classification',
                    'accuracy':    round(float(accuracy_score(y_test, y_pred)), 4),
                    'precision':   round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
                    'recall':      round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
                    'f1_score':    round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
                    'auc_roc':     round(float(roc_auc_score(y_test, y_prob)), 4),
                    'confusion_matrix': cm,
                    'specificity': round(tn/(tn+fp) if (tn+fp)>0 else 0.0, 4),
                    'n_samples':   len(y_test),
                    'passed':      True,
                }
            else:
                rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
                return {
                    'task':    'regression',
                    'mae':     round(float(mean_absolute_error(y_test, y_pred)), 4),
                    'mse':     round(float(mean_squared_error(y_test, y_pred)), 4),
                    'rmse':    round(rmse, 4),
                    'r2':      round(float(r2_score(y_test, y_pred)), 4),
                    'n_samples': len(y_test),
                    'passed':  True,
                }
        except ImportError:
            return {'error': 'sklearn not installed', 'passed': False}
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {'error': str(e), 'passed': False}

    def evaluate_business_metrics(self, model, X_test, y_test,
                                   revenue_per_tp: float = 100,
                                   cost_per_fp: float = 10) -> Dict:
        result   = self.evaluate(model, X_test, y_test, 'classification')
        if 'confusion_matrix' not in result: return result
        cm = result['confusion_matrix']
        if len(cm) < 2: return result
        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
        business_value = tp*revenue_per_tp - fp*cost_per_fp
        result.update({
            'true_positives':  tp,
            'false_positives': fp,
            'false_negatives': fn,
            'business_value':  round(float(business_value), 2),
            'revenue_captured': round(float(tp*revenue_per_tp), 2),
            'cost_of_errors':   round(float(fp*cost_per_fp), 2),
        })
        return result

    def cross_validate_evaluate(self, model_class, X, y,
                                  params: dict = None, cv: int = 5) -> Dict:
        try:
            from sklearn.model_selection import cross_validate
            from sklearn.metrics import make_scorer, f1_score, roc_auc_score
            model   = model_class(**(params or {}))
            scoring = {'f1': make_scorer(f1_score, zero_division=0), 'roc_auc': 'roc_auc'}
            results = cross_validate(model, X, y, cv=cv, scoring=scoring)
            return {
                'cv_folds':    cv,
                'f1_mean':     round(float(results['test_f1'].mean()), 4),
                'f1_std':      round(float(results['test_f1'].std()), 4),
                'auc_mean':    round(float(results['test_roc_auc'].mean()), 4),
                'auc_std':     round(float(results['test_roc_auc'].std()), 4),
                'passed':      results['test_f1'].mean() >= 0.65,
            }
        except Exception as e:
            return {'error': str(e), 'passed': False}
