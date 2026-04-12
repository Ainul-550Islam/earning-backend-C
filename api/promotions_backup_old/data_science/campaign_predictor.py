# =============================================================================
# api/promotions/data_science/campaign_predictor.py
# Campaign Success Prediction — ML দিয়ে কোন campaign সফল হবে predict করে
# =============================================================================

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('data_science.campaign_predictor')


@dataclass
class CampaignPrediction:
    campaign_id:        int
    success_probability: float   # 0.0 - 1.0
    predicted_fill_rate: float   # % slots filled
    predicted_approval_rate: float
    predicted_revenue:   float   # USD
    confidence:          float   # model confidence
    risk_factors:        list
    recommendations:     list


class CampaignPredictor:
    """
    Campaign সফলতা predict করে।
    Features: budget, slot_count, category, reward_rate, country_targeting, platform।
    Algorithm: Gradient Boosting (XGBoost) অথবা Random Forest।
    """

    FEATURE_NAMES = [
        'total_budget_usd', 'total_slots', 'reward_rate_usd',
        'profit_margin', 'category_encoded', 'platform_encoded',
        'n_countries_targeted', 'n_steps', 'has_bonus_policy',
        'historical_avg_approval', 'historical_avg_fill',
    ]

    def predict(self, campaign_id: int) -> CampaignPrediction:
        """Campaign এর success predict করে।"""
        features = self._extract_features(campaign_id)
        if not features:
            return self._default_prediction(campaign_id)

        try:
            return self._predict_with_model(campaign_id, features)
        except Exception as e:
            logger.warning(f'ML prediction failed, using heuristic: {e}')
            return self._heuristic_prediction(campaign_id, features)

    def _extract_features(self, campaign_id: int) -> Optional[dict]:
        """Campaign থেকে features extract করে।"""
        from api.promotions.models import Campaign, CampaignAnalytics
        from django.db.models import Avg

        try:
            c = Campaign.objects.select_related(
                'category', 'platform', 'targeting', 'limits'
            ).prefetch_related('steps', 'bonus_policies').get(pk=campaign_id)

            # Historical performance for this category + platform
            hist = CampaignAnalytics.objects.filter(
                campaign__category=c.category,
                campaign__platform=c.platform,
            ).aggregate(
                avg_approval = Avg('approved_count') / (Avg('total_submissions') + 0.001) * 100,
                avg_fill     = Avg('total_submissions') / (c.total_slots + 0.001) * 100,
            )

            # Category / Platform encode করো (simple label encoding)
            cat_map  = {'social': 1, 'apps': 2, 'web': 3, 'surveys': 4}
            plat_map = {'youtube': 1, 'facebook': 2, 'tiktok': 3, 'instagram': 4,
                        'play_store': 5, 'app_store': 6}

            n_countries = len(getattr(getattr(c, 'targeting', None), 'countries', []) or [])
            reward = self._get_avg_reward(c)

            return {
                'total_budget_usd':         float(c.total_budget_usd),
                'total_slots':              c.total_slots,
                'reward_rate_usd':          reward,
                'profit_margin':            float(c.profit_margin or 30),
                'category_encoded':         cat_map.get(c.category.name, 0),
                'platform_encoded':         plat_map.get(c.platform.name, 0),
                'n_countries_targeted':     n_countries,
                'n_steps':                  c.steps.count(),
                'has_bonus_policy':         int(c.bonus_policies.filter(is_active=True).exists()),
                'historical_avg_approval':  float(hist.get('avg_approval') or 75),
                'historical_avg_fill':      float(hist.get('avg_fill') or 60),
            }
        except Exception as e:
            logger.exception(f'Feature extraction failed for campaign #{campaign_id}: {e}')
            return None

    def _predict_with_model(self, campaign_id: int, features: dict) -> CampaignPrediction:
        """Trained ML model দিয়ে predict করে।"""
        import numpy as np
        # Model load করো (pretrained model থাকলে)
        # from joblib import load
        # model = load('path/to/campaign_model.joblib')
        # X = np.array([[features[k] for k in self.FEATURE_NAMES]])
        # prob = model.predict_proba(X)[0][1]

        # Demo: heuristic দিয়ে
        return self._heuristic_prediction(campaign_id, features)

    def _heuristic_prediction(self, campaign_id: int, features: dict) -> CampaignPrediction:
        """Rule-based prediction (ML model না থাকলে)।"""
        score        = 0.5
        risk_factors = []
        recommendations = []

        # Reward rate check
        reward = features.get('reward_rate_usd', 0)
        if reward < 0.05:
            score -= 0.15
            risk_factors.append('very_low_reward_rate')
            recommendations.append('Reward rate বাড়ান — কমপক্ষে $0.05')
        elif reward > 0.20:
            score += 0.10

        # Steps count check
        n_steps = features.get('n_steps', 1)
        if n_steps > 5:
            score -= 0.10
            risk_factors.append('too_many_steps')
            recommendations.append('Task steps কমান — সর্বোচ্চ ৩-৪টি ভালো')
        elif n_steps <= 3:
            score += 0.05

        # Budget adequacy
        budget_per_slot = features['total_budget_usd'] / max(features['total_slots'], 1)
        if budget_per_slot < reward * 1.2:
            score -= 0.20
            risk_factors.append('insufficient_budget_for_slots')
            recommendations.append('Budget বাড়ান অথবা slots কমান')

        # Historical performance
        hist_approval = features.get('historical_avg_approval', 75)
        if hist_approval < 60:
            score -= 0.05
        elif hist_approval > 85:
            score += 0.10

        # Bonus policy
        if features.get('has_bonus_policy'):
            score += 0.08
        else:
            recommendations.append('Bonus policy যোগ করুন — worker engagement বাড়বে')

        # Country targeting
        if features.get('n_countries_targeted', 0) > 10:
            score -= 0.05
            risk_factors.append('too_broad_targeting')
            recommendations.append('Targeting আরো নির্দিষ্ট করুন')

        score = max(0.05, min(0.97, score))

        predicted_fill_rate     = min(95, score * 100 * 1.1)
        predicted_approval_rate = min(98, hist_approval * (1 + (score - 0.5) * 0.2))
        predicted_revenue       = (
            features['total_budget_usd'] *
            (features.get('profit_margin', 30) / 100) *
            (predicted_fill_rate / 100)
        )

        return CampaignPrediction(
            campaign_id              = campaign_id,
            success_probability      = round(score, 3),
            predicted_fill_rate      = round(predicted_fill_rate, 1),
            predicted_approval_rate  = round(predicted_approval_rate, 1),
            predicted_revenue        = round(predicted_revenue, 2),
            confidence               = 0.72,  # heuristic model এর confidence
            risk_factors             = risk_factors,
            recommendations          = recommendations,
        )

    def _default_prediction(self, campaign_id: int) -> CampaignPrediction:
        return CampaignPrediction(
            campaign_id=campaign_id, success_probability=0.5,
            predicted_fill_rate=50.0, predicted_approval_rate=75.0,
            predicted_revenue=0.0, confidence=0.3,
            risk_factors=['insufficient_data'],
            recommendations=['আরো historical data দরকার'],
        )

    @staticmethod
    def _get_avg_reward(campaign) -> float:
        from api.promotions.models import RewardPolicy
        policy = RewardPolicy.objects.filter(
            category=campaign.category, is_active=True
        ).first()
        return float(policy.rate_usd) if policy else 0.10


# =============================================================================
# api/promotions/data_science/churn_prediction.py
# Churn Prediction — কোন user ছেড়ে চলে যাবে আগে থেকেই বলে
# =============================================================================

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

logger = logging.getLogger('data_science.churn_prediction')


@dataclass
class ChurnScore:
    user_id:          int
    churn_probability: float   # 0.0 = stay, 1.0 = leave
    risk_level:       str      # low, medium, high, critical
    days_to_churn:    Optional[int]
    churn_reasons:    list
    retention_actions: list


class ChurnPredictor:
    """
    User churn predict করে।

    Churn definition: ৩০ দিনের বেশি inactive + সাম্প্রতিক rejection rate বেশি।

    Features:
    - days_since_last_submission
    - recent_rejection_rate (last 30 days)
    - trend in submission frequency
    - trust_score change
    - dispute_rate
    - avg_reward_earned
    """

    CHURN_THRESHOLD_DAYS = 30

    def predict_user_churn(self, user_id: int) -> ChurnScore:
        """একটি user এর churn probability বের করে।"""
        features = self._extract_churn_features(user_id)
        return self._calculate_churn_score(user_id, features)

    def get_at_risk_users(self, threshold: float = 0.6, limit: int = 100) -> list[ChurnScore]:
        """High churn risk এর users list করে।"""
        from api.promotions.models import UserReputation
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=self.CHURN_THRESHOLD_DAYS)
        at_risk_reps = UserReputation.objects.filter(
            total_submissions__gte=3,
        ).filter(
            last_active_at__lt=cutoff,
        ).order_by('-trust_score')[:limit * 2]

        scores = []
        for rep in at_risk_reps:
            score = self.predict_user_churn(rep.user_id)
            if score.churn_probability >= threshold:
                scores.append(score)

        return sorted(scores, key=lambda s: s.churn_probability, reverse=True)[:limit]

    def _extract_churn_features(self, user_id: int) -> dict:
        from api.promotions.models import TaskSubmission, UserReputation
        from api.promotions.choices import SubmissionStatus
        from django.db.models import Count, Q
        from django.utils import timezone

        now    = timezone.now()
        rep    = None
        try:
            rep = UserReputation.objects.get(user_id=user_id)
        except UserReputation.DoesNotExist:
            pass

        last_30 = now - timedelta(days=30)
        last_90 = now - timedelta(days=90)

        recent_stats = TaskSubmission.objects.filter(
            worker_id=user_id, submitted_at__gte=last_30
        ).aggregate(
            total=Count('id'),
            rejected=Count('id', filter=Q(status=SubmissionStatus.REJECTED)),
            approved=Count('id', filter=Q(status=SubmissionStatus.APPROVED)),
        )

        older_stats = TaskSubmission.objects.filter(
            worker_id=user_id,
            submitted_at__gte=last_90,
            submitted_at__lt=last_30,
        ).aggregate(total=Count('id'))

        last_submission = TaskSubmission.objects.filter(
            worker_id=user_id
        ).order_by('-submitted_at').first()

        days_inactive = (
            (now - last_submission.submitted_at).days
            if last_submission else 999
        )

        recent_total    = recent_stats['total'] or 0
        recent_rejected = recent_stats['rejected'] or 0
        older_total     = older_stats['total'] or 0
        frequency_trend = recent_total - older_total  # positive = improving

        return {
            'days_inactive':       days_inactive,
            'recent_submissions':  recent_total,
            'recent_rejection_rate': (recent_rejected / recent_total * 100) if recent_total > 0 else 0,
            'frequency_trend':     frequency_trend,
            'trust_score':         float(rep.trust_score) if rep else 50,
            'success_rate':        float(rep.success_rate) if rep else 0,
            'total_lifetime_submissions': rep.total_submissions if rep else 0,
        }

    def _calculate_churn_score(self, user_id: int, features: dict) -> ChurnScore:
        score   = 0.0
        reasons = []
        actions = []

        # Inactivity
        days = features['days_inactive']
        if days > 60:
            score += 0.40; reasons.append('long_inactivity')
            actions.append('Special incentive campaign দিন')
        elif days > 30:
            score += 0.25; reasons.append('moderate_inactivity')
            actions.append('Re-engagement notification পাঠান')
        elif days > 14:
            score += 0.10

        # Recent rejection rate
        rr = features['recent_rejection_rate']
        if rr > 50:
            score += 0.30; reasons.append('high_recent_rejection_rate')
            actions.append('Quality improvement tips পাঠান')
        elif rr > 30:
            score += 0.15; reasons.append('moderate_rejection_rate')

        # Frequency trend (declining)
        if features['frequency_trend'] < -5:
            score += 0.15; reasons.append('declining_submission_frequency')

        # Low trust score
        if features['trust_score'] < 30:
            score += 0.15; reasons.append('low_trust_score')
            actions.append('Trust building program এ enroll করুন')

        score = min(1.0, score)

        risk_level = (
            'critical' if score >= 0.8 else
            'high'     if score >= 0.6 else
            'medium'   if score >= 0.4 else
            'low'
        )

        days_to_churn = None
        if score > 0.5:
            days_to_churn = max(1, int((1 - score) * 30))

        return ChurnScore(
            user_id           = user_id,
            churn_probability = round(score, 3),
            risk_level        = risk_level,
            days_to_churn     = days_to_churn,
            churn_reasons     = reasons,
            retention_actions = actions,
        )


# =============================================================================
# api/promotions/data_science/price_elasticity.py
# Price Elasticity — দাম বাড়ালে কাজ কেমন কমবে তার মডেল
# =============================================================================

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('data_science.price_elasticity')


@dataclass
class ElasticityResult:
    campaign_id:      int
    current_rate_usd: float
    elasticity:       float   # Price elasticity of demand (typically negative)
    optimal_rate_usd: float
    expected_volume_change: float  # % change in submissions
    revenue_impact:   float        # USD change
    recommendation:   str


class PriceElasticityAnalyzer:
    """
    Reward rate পরিবর্তনে submission volume কেমন পরিবর্তন হয় তা model করে।

    Formula: E = (ΔQ/Q) / (ΔP/P)
    যেখানে Q = submission volume, P = reward rate

    Elastic: |E| > 1 (দাম বাড়ালে volume অনেক কমে)
    Inelastic: |E| < 1 (দাম বাড়ালে volume কম কমে)
    """

    def analyze_elasticity(self, campaign_id: int) -> ElasticityResult:
        """Campaign এর price elasticity বের করে।"""
        data = self._get_rate_volume_data(campaign_id)
        if len(data) < 3:
            return self._default_elasticity(campaign_id)

        elasticity = self._calculate_arc_elasticity(data)
        return self._build_result(campaign_id, data, elasticity)

    def optimal_rate(
        self,
        current_rate: float,
        current_volume: int,
        elasticity: float,
        target: str = 'revenue',  # 'revenue' or 'volume'
    ) -> dict:
        """
        Revenue maximize করার জন্য optimal rate বের করে।

        Revenue = Rate × Volume
        dRevenue/dRate = Volume + Rate × dVolume/dRate
        = Volume(1 + E)  [যেখানে E = elasticity]

        Revenue maximize হয় যখন E = -1
        """
        if target == 'revenue':
            # Revenue maximizing: optimal হলো যেখানে elasticity = -1
            if elasticity < -1:  # Elastic — rate কমালে revenue বাড়ে
                optimal = current_rate * 0.9
                action  = 'rate কমান ১০% — revenue বাড়বে'
            elif elasticity > -1:  # Inelastic — rate বাড়ালে revenue বাড়ে
                optimal = current_rate * 1.1
                action  = 'rate বাড়ান ১০% — revenue বাড়বে'
            else:
                optimal = current_rate
                action  = 'current rate optimal আছে'
        else:
            optimal = current_rate * 1.2
            action  = 'volume বাড়াতে rate বাড়ান'

        new_volume = current_volume * (1 + elasticity * ((optimal - current_rate) / current_rate))
        return {
            'current_rate':    current_rate,
            'optimal_rate':    round(optimal, 4),
            'elasticity':      elasticity,
            'volume_change_pct': round((new_volume - current_volume) / current_volume * 100, 2),
            'recommendation':  action,
        }

    def _get_rate_volume_data(self, campaign_id: int) -> list[dict]:
        """Historical rate-volume data load করে।"""
        from api.promotions.models import CampaignAnalytics, RewardPolicy
        from django.db.models import Avg

        analytics = CampaignAnalytics.objects.filter(
            campaign_id=campaign_id
        ).order_by('date').values('date', 'total_submissions', 'total_spent_usd', 'approved_count')

        result = []
        for row in analytics:
            if row['approved_count'] and row['approved_count'] > 0 and row['total_spent_usd']:
                implied_rate = float(row['total_spent_usd']) / float(row['approved_count'])
                result.append({
                    'rate':   implied_rate,
                    'volume': row['total_submissions'],
                    'date':   row['date'],
                })
        return result

    @staticmethod
    def _calculate_arc_elasticity(data: list[dict]) -> float:
        """Arc elasticity method দিয়ে elasticity calculate করে।"""
        if len(data) < 2:
            return -1.0  # Default unit elastic

        elasticities = []
        for i in range(1, len(data)):
            p1, q1 = data[i-1]['rate'], data[i-1]['volume']
            p2, q2 = data[i]['rate'],   data[i]['volume']

            if p1 == p2 or q1 == 0:
                continue

            # Arc elasticity: midpoint method
            dQ = q2 - q1
            dP = p2 - p1
            avg_q = (q1 + q2) / 2
            avg_p = (p1 + p2) / 2

            if avg_p == 0 or avg_q == 0:
                continue

            e = (dQ / avg_q) / (dP / avg_p)
            elasticities.append(e)

        return round(sum(elasticities) / len(elasticities), 3) if elasticities else -1.0

    def _build_result(
        self, campaign_id: int, data: list[dict], elasticity: float
    ) -> ElasticityResult:
        current = data[-1]
        optimal_info = self.optimal_rate(
            current['rate'], current['volume'], elasticity
        )

        volume_change = current['volume'] * elasticity * 0.1  # 10% rate change
        revenue_impact = (optimal_info['optimal_rate'] - current['rate']) * current['volume']

        if abs(elasticity) > 1:
            rec = f'Elastic demand (E={elasticity:.2f}) — rate কমালে volume ও revenue বাড়বে'
        elif abs(elasticity) < 1:
            rec = f'Inelastic demand (E={elasticity:.2f}) — rate বাড়ানো safe'
        else:
            rec = f'Unit elastic (E={elasticity:.2f}) — rate change neutral'

        return ElasticityResult(
            campaign_id=campaign_id, current_rate_usd=current['rate'],
            elasticity=elasticity, optimal_rate_usd=optimal_info['optimal_rate'],
            expected_volume_change=round(volume_change, 1),
            revenue_impact=round(revenue_impact, 2), recommendation=rec,
        )

    def _default_elasticity(self, campaign_id: int) -> ElasticityResult:
        return ElasticityResult(
            campaign_id=campaign_id, current_rate_usd=0.0, elasticity=-1.0,
            optimal_rate_usd=0.0, expected_volume_change=0.0,
            revenue_impact=0.0, recommendation='Insufficient data for analysis',
        )


# =============================================================================
# api/promotions/data_science/ab_test_analyzer.py
# A/B Test Results Analysis — Statistical Significance Testing
# =============================================================================

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('data_science.ab_test')


@dataclass
class ABTestResult:
    test_id:            str
    variant_a:          dict
    variant_b:          dict
    winning_variant:    Optional[str]   # 'A', 'B', or None (inconclusive)
    p_value:            float
    confidence_level:   float
    is_significant:     bool
    relative_improvement: float         # % improvement of B over A
    sample_size_adequate: bool
    recommendation:     str


class ABTestAnalyzer:
    """
    A/B Test statistical significance analyze করে।

    Tests:
    - Chi-square test for conversion rates
    - Z-test for continuous metrics (revenue, reward)
    - Bayesian A/B test (optional)

    Minimum sample size calculation অন্তর্ভুক্ত।
    """

    SIGNIFICANCE_LEVEL = 0.05   # 95% confidence

    def analyze(
        self,
        control_conversions:   int,
        control_total:         int,
        treatment_conversions: int,
        treatment_total:       int,
        test_id:               str = 'ab_test',
    ) -> ABTestResult:
        """
        Conversion rate A/B test analyze করে।

        Args:
            control_conversions:   Variant A তে approved submissions
            control_total:         Variant A তে total submissions
            treatment_conversions: Variant B তে approved
            treatment_total:       Variant B তে total
        """
        if control_total < 30 or treatment_total < 30:
            return self._insufficient_data_result(test_id, control_total, treatment_total)

        rate_a = control_conversions / control_total
        rate_b = treatment_conversions / treatment_total

        # Z-test for proportions
        p_value, z_score = self._two_proportion_z_test(
            control_conversions, control_total,
            treatment_conversions, treatment_total,
        )

        is_significant    = p_value < self.SIGNIFICANCE_LEVEL
        confidence        = (1 - p_value) * 100
        relative_improve  = ((rate_b - rate_a) / rate_a * 100) if rate_a > 0 else 0.0

        # Sample size adequacy check
        min_sample        = self._minimum_sample_size(rate_a, rate_b)
        adequate          = min(control_total, treatment_total) >= min_sample

        if is_significant:
            winner = 'B' if rate_b > rate_a else 'A'
        else:
            winner = None

        rec = self._generate_recommendation(
            is_significant, winner, relative_improve, adequate, p_value
        )

        return ABTestResult(
            test_id                = test_id,
            variant_a              = {'conversions': control_conversions, 'total': control_total, 'rate': round(rate_a, 4)},
            variant_b              = {'conversions': treatment_conversions, 'total': treatment_total, 'rate': round(rate_b, 4)},
            winning_variant        = winner,
            p_value                = round(p_value, 6),
            confidence_level       = round(confidence, 2),
            is_significant         = is_significant,
            relative_improvement   = round(relative_improve, 2),
            sample_size_adequate   = adequate,
            recommendation         = rec,
        )

    @staticmethod
    def _two_proportion_z_test(c1: int, n1: int, c2: int, n2: int) -> tuple[float, float]:
        """Two-proportion Z-test।"""
        p1 = c1 / n1
        p2 = c2 / n2
        p_pool = (c1 + c2) / (n1 + n2)

        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return 1.0, 0.0

        z = (p2 - p1) / se

        # Two-tailed p-value approximation (Normal CDF)
        # Abramowitz and Stegun approximation
        a1, a2, a3 = 0.4361836, -0.1201676, 0.9372980
        t          = 1 / (1 + 0.33267 * abs(z))
        phi        = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
        cdf        = 1 - phi * (a1*t + a2*t**2 + a3*t**3)
        p_value    = 2 * (1 - cdf) if z > 0 else 2 * cdf

        return max(0.0001, min(1.0, p_value)), round(z, 4)

    @staticmethod
    def _minimum_sample_size(p1: float, p2: float, alpha: float = 0.05, power: float = 0.80) -> int:
        """Minimum sample size calculate করে (power analysis)।"""
        if p1 == p2:
            return 1000
        z_alpha = 1.96   # 95% confidence
        z_beta  = 0.84   # 80% power
        p_avg   = (p1 + p2) / 2
        n = (
            (z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) +
             z_beta  * math.sqrt(p1 * (1-p1) + p2 * (1-p2))) ** 2
        ) / (p2 - p1) ** 2
        return max(30, int(n))

    @staticmethod
    def _generate_recommendation(
        is_significant: bool, winner: Optional[str],
        relative_improve: float, adequate: bool, p_value: float,
    ) -> str:
        if not adequate:
            return 'আরো data collect করুন — sample size এখনো যথেষ্ট নয়।'
        if not is_significant:
            return f'Inconclusive (p={p_value:.3f}) — Test চালিয়ে যান।'
        if winner == 'B':
            return (
                f'Variant B জিতেছে ({relative_improve:+.1f}% improvement, p={p_value:.4f}). '
                f'Variant B কে production এ deploy করুন।'
            )
        return (
            f'Variant A এগিয়ে ({-relative_improve:.1f}% better, p={p_value:.4f}). '
            f'Current version রাখুন।'
        )

    def _insufficient_data_result(self, test_id: str, n1: int, n2: int) -> ABTestResult:
        return ABTestResult(
            test_id=test_id, variant_a={'total': n1}, variant_b={'total': n2},
            winning_variant=None, p_value=1.0, confidence_level=0.0,
            is_significant=False, relative_improvement=0.0,
            sample_size_adequate=False,
            recommendation=f'Minimum 30 samples needed. Current: A={n1}, B={n2}',
        )


# =============================================================================
# api/promotions/data_science/recommendation_engine.py
# Task Recommendation — ইউজারকে কোন কাজ দেখালে বেশি করবে
# =============================================================================

import logging
from dataclasses import dataclass

logger = logging.getLogger('data_science.recommendation')


@dataclass
class CampaignRecommendation:
    campaign_id:      int
    score:            float
    reasons:          list
    predicted_success: float


class RecommendationEngine:
    """
    Collaborative Filtering + Content-Based হাইব্রিড recommendation।

    ইউজারকে সবচেয়ে উপযুক্ত campaign recommend করে।
    Factors:
    - Historical success rate by category/platform
    - Country match
    - Reward rate preference
    - Time-of-day preference
    - Similar user behavior (collaborative)
    """

    def recommend_for_user(
        self,
        user_id: int,
        limit: int = 10,
        exclude_campaign_ids: list = None,
    ) -> list[CampaignRecommendation]:
        """User এর জন্য personalized campaign recommendations।"""
        from api.promotions.models import Campaign, TaskSubmission, UserReputation
        from api.promotions.choices import CampaignStatus, SubmissionStatus
        from django.db.models import Count, Avg, Q

        exclude = set(exclude_campaign_ids or [])

        # User এর past submissions
        past_submissions = TaskSubmission.objects.filter(worker_id=user_id)
        exclude.update(past_submissions.values_list('campaign_id', flat=True))

        # User এর successful category ও platform
        preferred_categories = (
            past_submissions.filter(status=SubmissionStatus.APPROVED)
            .values('campaign__category_id')
            .annotate(success_count=Count('id'))
            .order_by('-success_count')
            .values_list('campaign__category_id', flat=True)[:3]
        )
        preferred_platforms = (
            past_submissions.filter(status=SubmissionStatus.APPROVED)
            .values('campaign__platform_id')
            .annotate(success_count=Count('id'))
            .order_by('-success_count')
            .values_list('campaign__platform_id', flat=True)[:3]
        )

        # User reputation
        try:
            rep = UserReputation.objects.get(user_id=user_id)
            user_level    = rep.level
            user_country  = self._get_user_country(user_id)
        except UserReputation.DoesNotExist:
            user_level    = 1
            user_country  = 'US'

        # Active campaigns যা user এর জন্য eligible
        active_campaigns = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
        ).exclude(
            id__in=exclude,
        ).select_related('category', 'platform', 'targeting')

        recommendations = []
        for campaign in active_campaigns[:50]:  # Top 50 candidates
            score, reasons = self._score_campaign(
                campaign, user_level, user_country,
                preferred_categories, preferred_platforms,
            )
            recommendations.append(CampaignRecommendation(
                campaign_id=campaign.id, score=score, reasons=reasons,
                predicted_success=min(0.95, score * 0.9),
            ))

        # Sort by score, return top N
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:limit]

    def _score_campaign(
        self,
        campaign,
        user_level: int,
        user_country: str,
        preferred_categories: list,
        preferred_platforms: list,
    ) -> tuple[float, list]:
        score   = 0.5
        reasons = []

        # Category preference match
        if campaign.category_id in preferred_categories:
            idx   = list(preferred_categories).index(campaign.category_id)
            bonus = 0.20 - idx * 0.05
            score += bonus
            reasons.append(f'preferred_category_rank_{idx+1}')

        # Platform preference match
        if campaign.platform_id in preferred_platforms:
            score += 0.10
            reasons.append('preferred_platform')

        # Country match
        targeting = getattr(campaign, 'targeting', None)
        if targeting and targeting.countries:
            if user_country in targeting.countries:
                score += 0.15
                reasons.append('country_match')
            elif targeting.countries:
                score -= 0.20  # User এর country target নয়
                reasons.append('country_mismatch')

        # Level requirement match
        if targeting:
            if user_level < targeting.min_user_level:
                score -= 0.30  # User eligible নয়
                reasons.append('level_too_low')
            elif user_level >= targeting.min_user_level:
                score += 0.05
                reasons.append('level_eligible')

        # Budget remaining (full campaign এ কাজের সুযোগ আছে)
        if campaign.fill_percentage < 50:
            score += 0.10
            reasons.append('many_slots_available')
        elif campaign.fill_percentage > 90:
            score -= 0.10
            reasons.append('almost_full')

        # Bonus policy আছে কিনা
        if hasattr(campaign, 'bonus_policies') and campaign.bonus_policies.filter(is_active=True).exists():
            score += 0.05
            reasons.append('has_bonus')

        return round(max(0.0, min(1.0, score)), 3), reasons

    @staticmethod
    def _get_user_country(user_id: int) -> str:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            return getattr(getattr(user, 'profile', None), 'country_code', 'US') or 'US'
        except Exception:
            return 'US'


# =============================================================================
# api/promotions/data_science/fraud_prediction.py
# Fraud Prediction — Submission আসার আগেই ধরার চেষ্টা
# =============================================================================

import logging
from dataclasses import dataclass

logger = logging.getLogger('data_science.fraud_prediction')


@dataclass
class FraudPrediction:
    user_id:          int
    fraud_probability: float
    risk_level:       str
    fraud_indicators: list
    predicted_type:   str
    action:           str   # allow, flag, challenge, block


class FraudPredictor:
    """
    Pre-submission fraud prediction।
    Submission আসার আগেই user কে fraud এর জন্য score করে।

    Features:
    - Account age
    - Historical fraud reports
    - Device fingerprint anomalies
    - IP reputation
    - Behavioral velocity
    - Similar pattern to known fraudsters
    """

    def predict(self, user_id: int, campaign_id: int, request=None) -> FraudPrediction:
        """Submission এর আগেই fraud probability বের করে।"""
        features = self._extract_features(user_id, campaign_id, request)
        return self._calculate_fraud_score(user_id, features)

    def _extract_features(self, user_id: int, campaign_id: int, request=None) -> dict:
        from api.promotions.models import (
            UserReputation, FraudReport, TaskSubmission, DeviceFingerprint
        )
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        # Past fraud reports
        fraud_count = FraudReport.objects.filter(user_id=user_id).count()
        banned_fraud = FraudReport.objects.filter(
            user_id=user_id, action_taken='banned'
        ).count()

        # Device anomalies
        flagged_devices = DeviceFingerprint.objects.filter(
            user_id=user_id, is_flagged=True
        ).count()
        multi_account_devices = DeviceFingerprint.objects.filter(
            user_id=user_id, linked_account_count__gt=1
        ).count()

        # Reputation
        try:
            rep = UserReputation.objects.get(user_id=user_id)
            trust_score  = float(rep.trust_score)
            success_rate = float(rep.success_rate)
        except UserReputation.DoesNotExist:
            trust_score  = 50.0
            success_rate = 0.0

        # Recent submission velocity
        last_hour = timezone.now() - timedelta(hours=1)
        recent_submissions = TaskSubmission.objects.filter(
            worker_id=user_id, submitted_at__gte=last_hour
        ).count()

        # IP reputation (from blacklist + VPN check)
        ip = None
        if request:
            xff = request.META.get('HTTP_X_FORWARDED_FOR')
            ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')

        from api.promotions.models import Blacklist
        ip_blacklisted = Blacklist.is_blacklisted('ip', ip) if ip else False

        return {
            'fraud_report_count':      fraud_count,
            'banned_fraud_count':      banned_fraud,
            'flagged_device_count':    flagged_devices,
            'multi_account_devices':   multi_account_devices,
            'trust_score':             trust_score,
            'success_rate':            success_rate,
            'recent_submissions_1h':   recent_submissions,
            'ip_blacklisted':          ip_blacklisted,
        }

    def _calculate_fraud_score(self, user_id: int, features: dict) -> FraudPrediction:
        score      = 0.0
        indicators = []
        pred_type  = 'none'

        if features['ip_blacklisted']:
            score += 0.70; indicators.append('blacklisted_ip'); pred_type = 'ip_fraud'

        if features['banned_fraud_count'] > 0:
            score += 0.60; indicators.append('previous_ban'); pred_type = 'repeat_offender'

        if features['fraud_report_count'] > 2:
            score += 0.25 + features['fraud_report_count'] * 0.05
            indicators.append(f'fraud_reports:{features["fraud_report_count"]}')

        if features['multi_account_devices'] > 0:
            score += 0.35; indicators.append('multi_account_device'); pred_type = 'account_farming'

        if features['flagged_device_count'] > 0:
            score += 0.25; indicators.append('flagged_device')

        if features['recent_submissions_1h'] > 15:
            score += 0.30; indicators.append('high_velocity'); pred_type = 'bot_activity'

        if features['trust_score'] < 20:
            score += 0.15; indicators.append('very_low_trust')

        score      = min(1.0, score)
        risk_level = (
            'critical' if score >= 0.8 else
            'high'     if score >= 0.6 else
            'medium'   if score >= 0.4 else
            'low'
        )
        action     = (
            'block'     if score >= 0.8 else
            'challenge' if score >= 0.5 else
            'flag'      if score >= 0.3 else
            'allow'
        )

        return FraudPrediction(
            user_id=user_id, fraud_probability=round(score, 3),
            risk_level=risk_level, fraud_indicators=indicators,
            predicted_type=pred_type or 'generic', action=action,
        )


# =============================================================================
# api/promotions/data_science/ltv_calculator.py
# Lifetime Value Calculation
# =============================================================================

import logging
from dataclasses import dataclass

logger = logging.getLogger('data_science.ltv')


@dataclass
class UserLTV:
    user_id:             int
    historical_ltv:      float   # Actual earnings so far
    predicted_ltv_30d:   float   # Next 30 days
    predicted_ltv_90d:   float   # Next 90 days
    predicted_ltv_365d:  float   # Next year
    avg_monthly_revenue: float
    user_segment:        str     # whale, regular, casual, dormant
    acquisition_roi:     float   # LTV / acquisition cost


class LTVCalculator:
    """
    User Lifetime Value calculate করে।
    Platform এর perspective থেকে — admin commission earnings।
    """

    def calculate(self, user_id: int) -> UserLTV:
        from api.promotions.models import AdminCommissionLog
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        # Historical commission from this user's submissions
        hist = AdminCommissionLog.objects.filter(
            submission__worker_id=user_id
        ).aggregate(
            total=Sum('commission_usd'),
            count=Count('id'),
        )

        total_commission   = float(hist['total'] or 0)
        total_submissions  = hist['count'] or 0

        # Account age in months
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user        = User.objects.get(pk=user_id)
            account_age = max(1, (timezone.now() - user.date_joined).days / 30)
        except Exception:
            account_age = 1

        avg_monthly = total_commission / account_age

        # Recent trend (last 30 days)
        recent_30d = float(AdminCommissionLog.objects.filter(
            submission__worker_id=user_id,
            created_at__gte=timezone.now() - timedelta(days=30),
        ).aggregate(total=Sum('commission_usd'))['total'] or 0)

        # Churn probability থেকে survival factor
        survival_30d  = 0.90
        survival_90d  = 0.75
        survival_365d = 0.50

        ltv_30d   = recent_30d * survival_30d
        ltv_90d   = avg_monthly * 3 * survival_90d
        ltv_365d  = avg_monthly * 12 * survival_365d

        # Segment
        if avg_monthly > 10:
            segment = 'whale'
        elif avg_monthly > 2:
            segment = 'regular'
        elif avg_monthly > 0.5:
            segment = 'casual'
        else:
            segment = 'dormant'

        # ROI (assuming $0.50 acquisition cost)
        acq_cost = 0.50
        roi      = (ltv_365d / acq_cost * 100) if acq_cost > 0 else 0

        return UserLTV(
            user_id=user_id, historical_ltv=round(total_commission, 4),
            predicted_ltv_30d=round(ltv_30d, 4), predicted_ltv_90d=round(ltv_90d, 4),
            predicted_ltv_365d=round(ltv_365d, 4), avg_monthly_revenue=round(avg_monthly, 4),
            user_segment=segment, acquisition_roi=round(roi, 2),
        )


# =============================================================================
# api/promotions/data_science/cohort_analysis.py
# Cohort Analysis — Retention Tracking
# =============================================================================

import logging
from dataclasses import dataclass
from datetime import date, timedelta

logger = logging.getLogger('data_science.cohort')


@dataclass
class CohortRow:
    cohort_month:    str       # '2024-01'
    cohort_size:     int
    retention:       dict      # {month_0: 100%, month_1: 60%, ...}


@dataclass
class CohortReport:
    cohorts:         list[CohortRow]
    avg_retention:   dict       # average across all cohorts
    best_cohort:     str
    worst_cohort:    str


class CohortAnalyzer:
    """
    Monthly cohort analysis — কোন মাসের user গুলো কতদিন active থাকে।
    Retention curve visualize করতে সাহায্য করে।
    """

    def analyze(self, months_back: int = 12) -> CohortReport:
        """Cohort analysis চালায়।"""
        from django.contrib.auth import get_user_model
        from api.promotions.models import TaskSubmission
        from django.db.models import Min, Count

        User = get_user_model()
        today = date.today()

        # প্রতি cohort month এর user গুলো
        cohort_rows = []
        for m in range(months_back, 0, -1):
            cohort_start = (today.replace(day=1) - timedelta(days=m*30)).replace(day=1)
            cohort_end   = (cohort_start + timedelta(days=32)).replace(day=1)

            cohort_users = list(
                User.objects.filter(
                    date_joined__gte=cohort_start,
                    date_joined__lt=cohort_end,
                ).values_list('id', flat=True)
            )

            if not cohort_users:
                continue

            cohort_size  = len(cohort_users)
            retention    = {}

            for period in range(min(m, 6)):  # সর্বোচ্চ ৬ মাস retention
                period_start = cohort_start + timedelta(days=period * 30)
                period_end   = period_start + timedelta(days=30)

                active_users = TaskSubmission.objects.filter(
                    worker_id__in=cohort_users,
                    submitted_at__date__gte=period_start,
                    submitted_at__date__lt=period_end,
                ).values('worker_id').distinct().count()

                retention[f'month_{period}'] = round(active_users / cohort_size * 100, 1)

            cohort_rows.append(CohortRow(
                cohort_month = cohort_start.strftime('%Y-%m'),
                cohort_size  = cohort_size,
                retention    = retention,
            ))

        if not cohort_rows:
            return CohortReport([], {}, '', '')

        # Average retention
        all_periods = set()
        for row in cohort_rows:
            all_periods.update(row.retention.keys())

        avg_retention = {}
        for period in sorted(all_periods):
            values = [row.retention[period] for row in cohort_rows if period in row.retention]
            avg_retention[period] = round(sum(values) / len(values), 1) if values else 0.0

        # Best and worst cohort (by month_1 retention)
        with_m1 = [r for r in cohort_rows if 'month_1' in r.retention]
        if with_m1:
            best   = max(with_m1, key=lambda r: r.retention.get('month_1', 0)).cohort_month
            worst  = min(with_m1, key=lambda r: r.retention.get('month_1', 0)).cohort_month
        else:
            best = worst = ''

        return CohortReport(
            cohorts=cohort_rows, avg_retention=avg_retention,
            best_cohort=best, worst_cohort=worst,
        )
