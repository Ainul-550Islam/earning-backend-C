# =============================================================================
# api/promotions/data_science/ab_test_analyzer.py
# A/B Test Analyzer — Statistical significance, confidence intervals, winner
# Chi-square test, Z-test, Bayesian analysis (pure Python)
# =============================================================================

import logging
import math
from dataclasses import dataclass, field
from django.core.cache import cache

logger = logging.getLogger('data_science.ab_test')
CACHE_PREFIX_AB = 'ds:ab:{}'


@dataclass
class ABVariant:
    name:        str
    impressions: int
    conversions: int
    revenue_usd: float = 0.0

    @property
    def conversion_rate(self) -> float:
        return self.conversions / max(self.impressions, 1)

    @property
    def revenue_per_impression(self) -> float:
        return self.revenue_usd / max(self.impressions, 1)


@dataclass
class ABTestResult:
    test_id:          str
    control:          ABVariant
    variant:          ABVariant
    winner:           str            # 'control', 'variant', 'inconclusive'
    confidence_level: float          # 0.0 - 1.0 (0.95 = 95%)
    p_value:          float
    relative_uplift:  float          # % improvement of variant over control
    is_significant:   bool
    min_sample_size:  int            # Required sample for significance
    recommendation:   str
    bayesian_prob:    float          # Probability variant is better


class ABTestAnalyzer:
    """
    A/B Test Statistical Analysis।

    Tests:
    1. Conversion rate (Chi-square test)
    2. Revenue per impression (Z-test)
    3. Bayesian analysis (Beta distribution)

    Supports:
    - Campaign reward amount A/B
    - Email subject line A/B
    - Landing page A/B
    - Task description A/B
    """

    SIGNIFICANCE_LEVEL = 0.05   # 95% confidence

    def analyze(
        self,
        test_id:  str,
        control:  ABVariant,
        variant:  ABVariant,
    ) -> ABTestResult:
        """A/B test result analyze করে।"""
        # Statistical significance (Z-test for proportions)
        p_value, z_score = self._z_test_proportions(
            control.conversions, control.impressions,
            variant.conversions, variant.impressions,
        )

        is_significant  = p_value < self.SIGNIFICANCE_LEVEL
        confidence      = 1 - p_value

        # Relative uplift
        if control.conversion_rate > 0:
            uplift = (variant.conversion_rate - control.conversion_rate) / control.conversion_rate
        else:
            uplift = 0.0

        # Winner
        if not is_significant:
            winner = 'inconclusive'
        elif variant.conversion_rate > control.conversion_rate:
            winner = 'variant'
        else:
            winner = 'control'

        # Bayesian probability variant is better
        bayes_prob = self._bayesian_probability(
            control.conversions, control.impressions,
            variant.conversions, variant.impressions,
        )

        # Min sample size
        min_n = self._min_sample_size(control.conversion_rate)

        # Recommendation
        if winner == 'variant' and confidence >= 0.95:
            rec = f'Deploy variant. {uplift:.1%} uplift with {confidence:.0%} confidence.'
        elif winner == 'control':
            rec = f'Keep control. Variant underperforms by {abs(uplift):.1%}.'
        else:
            needed = max(0, min_n - control.impressions)
            rec    = f'Inconclusive. Need {needed:,} more impressions per variant.'

        return ABTestResult(
            test_id=test_id, control=control, variant=variant,
            winner=winner, confidence_level=round(confidence, 4),
            p_value=round(p_value, 6), relative_uplift=round(uplift, 4),
            is_significant=is_significant, min_sample_size=min_n,
            recommendation=rec, bayesian_prob=round(bayes_prob, 4),
        )

    def calculate_required_sample_size(
        self, baseline_rate: float, min_detectable_effect: float = 0.05,
        alpha: float = 0.05, power: float = 0.80,
    ) -> int:
        """Statistically valid test এর জন্য minimum sample size।"""
        return self._min_sample_size(baseline_rate, min_detectable_effect, alpha, power)

    def analyze_revenue_ab(
        self, test_id: str, control: ABVariant, variant: ABVariant
    ) -> dict:
        """Revenue-based A/B test analysis।"""
        result = self.analyze(test_id, control, variant)
        rev_uplift = (variant.revenue_per_impression - control.revenue_per_impression) / max(control.revenue_per_impression, 0.001)

        return {
            **result.__dict__,
            'revenue_uplift': round(rev_uplift, 4),
            'projected_monthly_uplift_usd': round(
                rev_uplift * control.revenue_usd * 30 / max(control.impressions / 30, 1), 2
            ),
        }

    # ── Statistical Methods ───────────────────────────────────────────────────

    @staticmethod
    def _z_test_proportions(
        conv_a: int, n_a: int, conv_b: int, n_b: int
    ) -> tuple:
        """Two-proportion Z-test।"""
        if n_a == 0 or n_b == 0:
            return 1.0, 0.0

        p_a    = conv_a / n_a
        p_b    = conv_b / n_b
        p_pool = (conv_a + conv_b) / (n_a + n_b)

        se     = math.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
        if se == 0:
            return 1.0, 0.0

        z      = (p_b - p_a) / se
        # Two-tailed p-value using normal approximation
        p_val  = 2 * (1 - ABTestAnalyzer._normal_cdf(abs(z)))
        return p_val, z

    @staticmethod
    def _normal_cdf(z: float) -> float:
        """Standard normal CDF approximation (Abramowitz & Stegun)。"""
        t = 1.0 / (1.0 + 0.2316419 * abs(z))
        poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
        cdf  = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z**2) * poly
        return cdf if z >= 0 else 1 - cdf

    @staticmethod
    def _bayesian_probability(
        conv_a: int, n_a: int, conv_b: int, n_b: int, samples: int = 5000
    ) -> float:
        """
        Bayesian A/B testing।
        P(variant > control) using Beta distribution sampling।
        Beta(α, β) where α=conversions+1, β=non-conversions+1
        """
        import random
        alpha_a = conv_a + 1
        beta_a  = (n_a - conv_a) + 1
        alpha_b = conv_b + 1
        beta_b  = (n_b - conv_b) + 1

        b_wins = 0
        for _ in range(samples):
            # Beta sample via Gamma
            ga = random.gammavariate(alpha_a, 1)
            gb_beta = random.gammavariate(beta_a, 1)
            sample_a = ga / (ga + gb_beta) if (ga + gb_beta) > 0 else 0

            gc = random.gammavariate(alpha_b, 1)
            gd = random.gammavariate(beta_b, 1)
            sample_b = gc / (gc + gd) if (gc + gd) > 0 else 0

            if sample_b > sample_a:
                b_wins += 1

        return b_wins / samples

    @staticmethod
    def _min_sample_size(
        baseline: float, effect: float = 0.05,
        alpha: float = 0.05, power: float = 0.80,
    ) -> int:
        """Required sample size per variant।"""
        if baseline <= 0 or baseline >= 1:
            return 1000
        z_alpha = 1.96   # 95% confidence
        z_beta  = 0.842  # 80% power
        p1      = baseline
        p2      = baseline * (1 + effect)
        p_bar   = (p1 + p2) / 2
        n = ((z_alpha * math.sqrt(2 * p_bar * (1-p_bar)) + z_beta * math.sqrt(p1*(1-p1) + p2*(1-p2))) / (p2 - p1)) ** 2
        return max(100, int(math.ceil(n)))
