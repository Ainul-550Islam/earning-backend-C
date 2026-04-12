"""
api/ai_engine/ML_MODELS/feature_importance.py
=============================================
Feature Importance Analyzer — model feature contribution analysis।
SHAP, permutation importance, built-in importance।
Feature selection ও model explanation এর জন্য।
Marketing platform এর fraud ও churn models এর জন্য।
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FeatureImportanceAnalyzer:
    """
    Feature importance analysis for ML models।
    Multiple methods: tree-based, SHAP, permutation।
    """

    def analyze(self, model, feature_names: List[str],
                 method: str = 'auto') -> Dict:
        """
        Feature importance analyze করো।
        method: 'tree', 'shap', 'permutation', 'auto'
        """
        if method == 'auto':
            # Best available method auto-select
            if hasattr(model, 'feature_importances_'):
                method = 'tree'
            else:
                method = 'permutation'

        if method == 'tree':
            return self._tree_importance(model, feature_names)
        elif method == 'shap':
            return self._shap_importance(model, feature_names)
        elif method == 'permutation':
            return self._permutation_importance(model, feature_names)
        return self._tree_importance(model, feature_names)

    def _tree_importance(self, model, feature_names: List[str]) -> Dict:
        """Tree-based feature importance (Gini / Information Gain)।"""
        try:
            importance = model.feature_importances_
            n = min(len(feature_names), len(importance))
            pairs = sorted(
                zip(feature_names[:n], [round(float(i), 6) for i in importance[:n]]),
                key=lambda x: x[1], reverse=True,
            )
            total = sum(v for _, v in pairs)
            cumulative = 0.0
            ranked = []
            for rank, (feat, imp) in enumerate(pairs, 1):
                cumulative += imp
                ranked.append({
                    'rank':         rank,
                    'feature':      feat,
                    'importance':   imp,
                    'importance_pct': round(imp / max(total, 0.001) * 100, 2),
                    'cumulative_pct': round(cumulative / max(total, 0.001) * 100, 2),
                })

            return {
                'method':           'tree_importance',
                'features':         ranked,
                'top_5':            ranked[:5],
                'top_10':           ranked[:10],
                'total_features':   len(ranked),
                'top5_explains_pct': ranked[4]['cumulative_pct'] if len(ranked) >= 5 else 100.0,
            }
        except AttributeError:
            logger.warning("Model does not have feature_importances_")
            return {'error': 'Model does not support tree importance', 'method': 'tree_importance'}

    def _shap_importance(self, model, feature_names: List[str],
                          X_sample=None) -> Dict:
        """SHAP-based feature importance।"""
        try:
            import shap
            import numpy as np

            if X_sample is None:
                X_sample = np.random.randn(50, len(feature_names))

            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]

            mean_abs = [round(float(abs(shap_values[:, i]).mean()), 6)
                        for i in range(min(len(feature_names), shap_values.shape[1]))]

            pairs = sorted(
                zip(feature_names, mean_abs),
                key=lambda x: x[1], reverse=True,
            )
            total = sum(v for _, v in pairs)

            return {
                'method':   'shap',
                'features': [
                    {'rank': i+1, 'feature': f, 'shap_value': v,
                     'importance_pct': round(v / max(total, 0.001) * 100, 2)}
                    for i, (f, v) in enumerate(pairs)
                ],
                'top_5': dict(pairs[:5]),
            }
        except ImportError:
            logger.warning("SHAP not installed. pip install shap — falling back to tree importance")
            return self._tree_importance(model, feature_names)
        except Exception as e:
            return {'error': str(e), 'method': 'shap'}

    def _permutation_importance(self, model, feature_names: List[str],
                                  X_test=None, y_test=None) -> Dict:
        """Permutation-based feature importance (model-agnostic)।"""
        try:
            from sklearn.inspection import permutation_importance
            import numpy as np

            if X_test is None:
                X_test = np.random.randn(100, len(feature_names))
                y_test = np.random.randint(0, 2, 100)

            result = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=42)
            importances = result.importances_mean

            pairs = sorted(
                zip(feature_names, [round(float(i), 6) for i in importances]),
                key=lambda x: x[1], reverse=True,
            )
            return {
                'method':   'permutation',
                'features': [{'rank': i+1, 'feature': f, 'importance': v}
                             for i, (f, v) in enumerate(pairs)],
                'top_5':    dict(pairs[:5]),
            }
        except Exception as e:
            logger.error(f"Permutation importance error: {e}")
            return {'error': str(e), 'method': 'permutation'}

    def select_top_features(self, model, feature_names: List[str],
                             threshold: float = 0.01,
                             max_features: int = None) -> List[str]:
        """
        Importance threshold এর উপরে থাকা features select করো।
        Feature selection এর জন্য।
        """
        result = self.analyze(model, feature_names)
        features = result.get('features', [])

        selected = []
        for item in features:
            imp = item.get('importance', item.get('shap_value', 0))
            if imp >= threshold:
                selected.append(item['feature'])

        if max_features:
            selected = selected[:max_features]

        return selected

    def plot_importance(self, model, feature_names: List[str],
                         top_n: int = 20) -> dict:
        """Chart data generate করো (frontend এ render করার জন্য)।"""
        result = self.analyze(model, feature_names)
        features = result.get('features', [])[:top_n]

        return {
            'chart_type': 'horizontal_bar',
            'labels':     [f['feature'] for f in features],
            'values':     [f.get('importance', f.get('shap_value', 0)) for f in features],
            'title':      f'Top {len(features)} Feature Importances',
            'x_label':    'Importance Score',
        }

    def compare_feature_sets(self, model_a, model_b,
                              feature_names: List[str]) -> dict:
        """Two model এর feature importance compare করো।"""
        imp_a = self.analyze(model_a, feature_names)
        imp_b = self.analyze(model_b, feature_names)

        features_a = {f['feature']: f.get('importance', 0)
                      for f in imp_a.get('features', [])}
        features_b = {f['feature']: f.get('importance', 0)
                      for f in imp_b.get('features', [])}

        comparison = []
        for feat in feature_names:
            a = features_a.get(feat, 0)
            b = features_b.get(feat, 0)
            comparison.append({
                'feature':    feat,
                'model_a':    round(a, 6),
                'model_b':    round(b, 6),
                'difference': round(a - b, 6),
                'winner':     'A' if a > b else 'B' if b > a else 'tie',
            })

        return {
            'comparison':    sorted(comparison, key=lambda x: abs(x['difference']), reverse=True),
            'model_a_wins':  sum(1 for c in comparison if c['winner'] == 'A'),
            'model_b_wins':  sum(1 for c in comparison if c['winner'] == 'B'),
        }

    def feature_drift_detection(self, reference_importance: Dict[str, float],
                                  current_importance: Dict[str, float],
                                  threshold: float = 0.20) -> dict:
        """
        Feature importance drift detect করো।
        Model behavior পরিবর্তন হয়েছে কিনা।
        """
        drifted = []
        for feat in reference_importance:
            ref = reference_importance.get(feat, 0)
            cur = current_importance.get(feat, 0)
            if ref == 0:
                continue
            change = abs(cur - ref) / ref
            if change > threshold:
                drifted.append({
                    'feature':     feat,
                    'reference':   round(ref, 6),
                    'current':     round(cur, 6),
                    'change_pct':  round(change * 100, 2),
                    'direction':   'increased' if cur > ref else 'decreased',
                })

        return {
            'drift_detected':  len(drifted) > 0,
            'drifted_features': sorted(drifted, key=lambda x: x['change_pct'], reverse=True),
            'drift_count':     len(drifted),
            'total_features':  len(reference_importance),
            'drift_rate':      round(len(drifted) / max(len(reference_importance), 1), 4),
            'recommendation':  'Investigate feature drift — possible data or model issue' if drifted else 'Stable',
        }
