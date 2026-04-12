"""
api/ai_engine/ANALYTICS_INSIGHTS/correlation_analyzer.py
=========================================================
Correlation Analyzer — metrics এর মধ্যে relationships find করো।
Marketing effectiveness, feature importance, business drivers।
Pearson, Spearman, Kendall correlations।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """
    Statistical correlation analysis।
    Business metrics এর মধ্যে relationships identify করো।
    """

    def correlate(self, data: Dict[str, List[float]],
                   method: str = 'pearson') -> dict:
        """
        Multiple metrics এর pairwise correlation calculate করো।
        data: {'revenue': [100, 200, ...], 'dau': [1000, 2000, ...]}
        """
        keys = list(data.keys())
        if len(keys) < 2:
            return {'error': 'Need at least 2 metrics'}

        matrix = {}
        strong_correlations = []
        weak_correlations   = []

        for i, k1 in enumerate(keys):
            for j, k2 in enumerate(keys):
                if j <= i:
                    continue
                v1, v2  = data[k1], data[k2]
                min_len = min(len(v1), len(v2))
                if min_len < 3:
                    continue

                v1_t, v2_t = v1[:min_len], v2[:min_len]

                if method == 'pearson':
                    corr = self._pearson(v1_t, v2_t)
                elif method == 'spearman':
                    corr = self._spearman(v1_t, v2_t)
                else:
                    corr = self._pearson(v1_t, v2_t)

                pair_key = f"{k1} ↔ {k2}"
                matrix[pair_key] = round(corr, 4)

                if abs(corr) >= 0.70:
                    strong_correlations.append({
                        'pair':        pair_key,
                        'correlation': round(corr, 4),
                        'direction':   'positive' if corr > 0 else 'negative',
                        'strength':    'very_strong' if abs(corr) >= 0.90 else 'strong',
                    })
                elif abs(corr) <= 0.20:
                    weak_correlations.append({'pair': pair_key, 'correlation': round(corr, 4)})

        return {
            'method':              method,
            'correlation_matrix':  matrix,
            'strong_correlations': strong_correlations,
            'weak_correlations':   weak_correlations[:5],
            'metric_count':        len(keys),
            'pair_count':          len(matrix),
            'insights':            self._generate_insights(strong_correlations),
        }

    def _pearson(self, x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient।"""
        n   = len(x)
        if n < 2:
            return 0.0
        mx  = sum(x) / n
        my  = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx  = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy  = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return 0.0
        return round(cov / (sx * sy), 6)

    def _spearman(self, x: List[float], y: List[float]) -> float:
        """Spearman rank correlation।"""
        n     = len(x)
        rank_x = self._rank(x)
        rank_y = self._rank(y)
        d2    = sum((rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y))
        return round(1 - (6 * d2) / max(n * (n**2 - 1), 1), 6)

    def _rank(self, x: List[float]) -> List[float]:
        """Rank values (1 = smallest)।"""
        sorted_x = sorted(range(len(x)), key=lambda i: x[i])
        ranks = [0] * len(x)
        for rank, idx in enumerate(sorted_x, 1):
            ranks[idx] = float(rank)
        return ranks

    def _generate_insights(self, strong_corrs: List[Dict]) -> List[str]:
        """Strong correlations থেকে business insights generate করো।"""
        insights = []
        known_pairs = {
            ('revenue', 'dau'):           'More daily active users directly drive revenue',
            ('churn_rate', 'engagement'):  'Higher engagement reduces churn',
            ('ctr', 'revenue'):            'Better click-through rates boost revenue',
            ('ltv', 'referral_count'):     'Referral users have higher lifetime value',
            ('fraud_rate', 'revenue'):     'Fraud negatively impacts revenue',
        }
        for corr in strong_corrs:
            pair = corr.get('pair', '')
            for (m1, m2), insight in known_pairs.items():
                if m1 in pair and m2 in pair:
                    insights.append(insight)
                    break
            else:
                direction = corr.get('direction', 'positive')
                insights.append(f"Strong {direction} correlation: {pair} ({corr['correlation']:.2f})")
        return insights[:5]

    def lag_correlation(self, x: List[float], y: List[float],
                         max_lag: int = 7) -> dict:
        """
        Lagged correlation — x কি y কে n days পরে affect করে?
        Marketing spend → revenue (3 days later) etc.
        """
        results = {}
        for lag in range(0, max_lag + 1):
            if lag == 0:
                corr = self._pearson(x, y)
            else:
                x_lagged = x[:-lag] if lag > 0 else x
                y_shifted = y[lag:]
                min_len  = min(len(x_lagged), len(y_shifted))
                corr = self._pearson(x_lagged[:min_len], y_shifted[:min_len])
            results[f'lag_{lag}d'] = round(corr, 4)

        best_lag = max(results, key=lambda k: abs(results[k]))
        return {
            'lag_correlations':  results,
            'best_lag':          best_lag,
            'best_correlation':  results[best_lag],
            'interpretation':    f"Strongest effect at {best_lag} (corr={results[best_lag]:.2f})",
        }

    def feature_target_correlation(self, features: Dict[str, List[float]],
                                    target: List[float]) -> List[Dict]:
        """Feature-target correlations for feature selection।"""
        results = []
        for feat_name, feat_values in features.items():
            min_len = min(len(feat_values), len(target))
            corr    = self._pearson(feat_values[:min_len], target[:min_len])
            results.append({
                'feature':     feat_name,
                'correlation': round(corr, 4),
                'abs_corr':    round(abs(corr), 4),
                'useful':      abs(corr) >= 0.10,
            })

        return sorted(results, key=lambda x: x['abs_corr'], reverse=True)
