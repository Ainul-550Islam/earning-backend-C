"""
SmartLink Click Quality Score System
World #1 Feature: Multi-dimensional click quality assessment.

Goes beyond fraud detection to measure click VALUE:
- Quality Score 0-100 (100 = perfect high-value click)
- Publisher quality tier assignment
- Automatic traffic quality reporting
- Click scrubbing for advertisers
"""
import logging
from django.core.cache import cache
from django.utils import timezone
import datetime

logger = logging.getLogger('smartlink.antifraud.quality')


class ClickQualityScore:
    """
    Assigns a Quality Score (0–100) to every click.
    Score factors:
    - Uniqueness (is this a fresh user?)
    - Device quality (real device signals)
    - Engagement signals (referrer, session depth)
    - Geographic value (tier-1/2/3 country)
    - Historical publisher quality
    - Time-of-day value (prime hours)
    """

    # Country tiers by conversion value
    GEO_TIERS = {
        'T1': {'US', 'GB', 'CA', 'AU', 'NZ', 'DE', 'FR', 'CH', 'SE', 'NO', 'DK', 'NL', 'FI'},
        'T2': {'BD', 'IN', 'PK', 'PH', 'ID', 'MY', 'TH', 'VN', 'BR', 'MX', 'AR', 'ZA', 'NG', 'AE'},
        'T3': set(),  # All others
    }

    GEO_SCORES = {'T1': 40, 'T2': 25, 'T3': 10}

    def calculate(self, click_context: dict) -> dict:
        """
        Calculate full quality score for a click.

        Returns:
            {
                'score': int (0-100),
                'tier': str ('premium' | 'standard' | 'low'),
                'breakdown': dict,
                'recommendation': str
            }
        """
        breakdown = {}
        total = 0

        # ── 1. Uniqueness (20 pts) ───────────────────────────────────
        is_unique = click_context.get('is_unique', True)
        unique_score = 20 if is_unique else 5
        breakdown['uniqueness'] = unique_score
        total += unique_score

        # ── 2. Geo value (40 pts) ────────────────────────────────────
        country = click_context.get('country', '').upper()
        geo_tier = self._get_geo_tier(country)
        geo_score = self.GEO_SCORES.get(geo_tier, 10)
        breakdown['geo_value'] = geo_score
        breakdown['geo_tier'] = geo_tier
        total += geo_score

        # ── 3. Device quality (15 pts) ───────────────────────────────
        device_score = self._score_device(click_context)
        breakdown['device_quality'] = device_score
        total += device_score

        # ── 4. Referrer quality (10 pts) ─────────────────────────────
        referrer_score = self._score_referrer(click_context.get('referrer', ''))
        breakdown['referrer_quality'] = referrer_score
        total += referrer_score

        # ── 5. Time-of-day value (5 pts) ─────────────────────────────
        tod_score = self._score_time_of_day(country)
        breakdown['time_of_day'] = tod_score
        total += tod_score

        # ── 6. Publisher historical quality (10 pts) ─────────────────
        pub_score = self._score_publisher_history(click_context.get('publisher_id', 0))
        breakdown['publisher_history'] = pub_score
        total += pub_score

        # ── Determine tier ────────────────────────────────────────────
        if total >= 75:
            tier = 'premium'
        elif total >= 45:
            tier = 'standard'
        else:
            tier = 'low'

        recommendation = self._get_recommendation(total, breakdown)

        return {
            'score':          total,
            'tier':           tier,
            'breakdown':      breakdown,
            'recommendation': recommendation,
        }

    def get_publisher_quality_report(self, publisher_id: int, days: int = 7) -> dict:
        """
        Generate publisher quality report.
        Used for publisher tier assignment and payout adjustments.
        """
        from ...models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)
        clicks = Click.objects.filter(
            smartlink__publisher_id=publisher_id,
            created_at__gte=cutoff,
        )
        total = clicks.count()
        if total == 0:
            return {'total': 0, 'quality_rate': 0, 'tier': 'unknown'}

        fraud   = clicks.filter(is_fraud=True).count()
        bot     = clicks.filter(is_bot=True).count()
        unique  = clicks.filter(is_unique=True).count()
        converted = clicks.filter(is_converted=True).count()

        quality_rate = (total - fraud - bot) / total * 100 if total > 0 else 0
        unique_rate  = unique / total * 100 if total > 0 else 0
        cr           = converted / total * 100 if total > 0 else 0

        # Publisher tier
        if quality_rate >= 95 and unique_rate >= 80:
            pub_tier = 'gold'
        elif quality_rate >= 85 and unique_rate >= 60:
            pub_tier = 'silver'
        elif quality_rate >= 70:
            pub_tier = 'bronze'
        else:
            pub_tier = 'under_review'

        return {
            'publisher_id':  publisher_id,
            'period_days':   days,
            'total_clicks':  total,
            'fraud_clicks':  fraud,
            'bot_clicks':    bot,
            'unique_clicks': unique,
            'conversions':   converted,
            'quality_rate':  round(quality_rate, 2),
            'unique_rate':   round(unique_rate, 2),
            'conversion_rate': round(cr, 2),
            'publisher_tier':  pub_tier,
        }

    # ── Private ─────────────────────────────────────────────────────

    def _get_geo_tier(self, country: str) -> str:
        for tier, countries in self.GEO_TIERS.items():
            if country in countries:
                return tier
        return 'T3'

    def _score_device(self, context: dict) -> int:
        device_type = context.get('device_type', 'unknown')
        os_type     = context.get('os', '')
        browser     = context.get('browser', '')
        ua          = context.get('user_agent', '')

        score = 0
        if device_type in ('mobile', 'tablet'):
            score += 8
        elif device_type == 'desktop':
            score += 6

        if os_type in ('android', 'ios'):
            score += 4
        elif os_type in ('windows', 'mac'):
            score += 3

        if browser in ('chrome', 'safari'):
            score += 3
        elif browser in ('firefox', 'edge'):
            score += 2

        return min(score, 15)

    def _score_referrer(self, referrer: str) -> int:
        if not referrer:
            return 2  # No referrer — slightly suspicious but common

        trusted_domains = [
            'google.com', 'facebook.com', 'instagram.com', 'tiktok.com',
            'twitter.com', 'x.com', 'youtube.com', 'bing.com',
        ]
        for domain in trusted_domains:
            if domain in referrer:
                return 10

        return 5  # Unknown referrer

    def _score_time_of_day(self, country: str) -> int:
        """Higher score during business hours in the target country's timezone."""
        now_hour = timezone.now().hour  # UTC
        # For simplicity: 8am-10pm UTC is prime time
        if 8 <= now_hour <= 22:
            return 5
        return 2

    def _score_publisher_history(self, publisher_id: int) -> int:
        if not publisher_id:
            return 5

        cache_key = f'pub_quality:{publisher_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            report = self.get_publisher_quality_report(publisher_id, days=7)
            tier_scores = {'gold': 10, 'silver': 7, 'bronze': 5, 'under_review': 2, 'unknown': 5}
            score = tier_scores.get(report.get('publisher_tier', 'unknown'), 5)
            cache.set(cache_key, score, 1800)
            return score
        except Exception:
            return 5

    def _get_recommendation(self, score: int, breakdown: dict) -> str:
        if score >= 75:
            return 'High-quality click — prioritize in rotation'
        if score < 45:
            weak = min(breakdown, key=lambda k: breakdown[k] if isinstance(breakdown[k], (int, float)) else 999)
            return f'Low-quality click — investigate {weak}'
        return 'Standard quality click'
