# api/offer_inventory/user_behavior_analysis/activity_heatmap.py
"""
User Behavior Analysis — all 8 modules in one package.
Activity heatmap, churn prediction, retention, loyalty, segmentation,
session replay, engagement score, referral chain.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. ACTIVITY HEATMAP
# ════════════════════════════════════════════════════════

class ActivityHeatmapService:
    """Track and visualize when users are most active."""

    @staticmethod
    def update_heatmap(user, click_time=None):
        """Update heatmap for a user based on click time."""
        from api.offer_inventory.models import ActivityHeatmap
        from django.db.models import F

        now  = click_time or timezone.now()
        day  = now.weekday()   # 0=Monday
        hour = now.hour

        obj, created = ActivityHeatmap.objects.get_or_create(
            user=user, day_of_week=day, hour_of_day=hour,
            defaults={'click_count': 1, 'activity_score': 1.0}
        )
        if not created:
            ActivityHeatmap.objects.filter(id=obj.id).update(
                click_count   =F('click_count') + 1,
                activity_score=F('activity_score') + 0.1,
            )

    @staticmethod
    def get_user_heatmap(user) -> list:
        """Get user's activity heatmap data."""
        from api.offer_inventory.models import ActivityHeatmap
        return list(
            ActivityHeatmap.objects.filter(user=user)
            .values('day_of_week', 'hour_of_day', 'click_count', 'activity_score')
            .order_by('day_of_week', 'hour_of_day')
        )

    @staticmethod
    def get_best_send_time(user) -> dict:
        """Find the best time to send notifications to a user."""
        from api.offer_inventory.models import ActivityHeatmap
        best = ActivityHeatmap.objects.filter(user=user).order_by('-activity_score').first()
        if not best:
            return {'day': 1, 'hour': 9, 'confidence': 'low'}  # Default: Tuesday 9AM
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return {
            'day'       : days[best.day_of_week],
            'hour'      : best.hour_of_day,
            'score'     : float(best.activity_score),
            'confidence': 'high' if best.click_count > 10 else 'medium',
        }

    @staticmethod
    def get_platform_heatmap() -> list:
        """Platform-wide activity heatmap (all users aggregated)."""
        from api.offer_inventory.models import Click
        return list(
            Click.objects.filter(is_fraud=False)
            .annotate(
                dow=__import__('django.db.models.functions', fromlist=['ExtractWeekDay']).ExtractWeekDay('created_at'),
                hour=__import__('django.db.models.functions', fromlist=['ExtractHour']).ExtractHour('created_at'),
            )
            .values('dow', 'hour')
            .annotate(count=Count('id'))
            .order_by('dow', 'hour')
        )


# ════════════════════════════════════════════════════════
# 2. CHURN PREDICTION
# ════════════════════════════════════════════════════════

class ChurnPredictor:
    """Predict which users are likely to churn."""

    CHURN_WEIGHTS = {
        'days_since_last_click'      : 0.35,
        'days_since_last_conversion' : 0.30,
        'declining_frequency'        : 0.20,
        'low_earnings'               : 0.15,
    }

    @classmethod
    def predict_score(cls, user) -> float:
        """
        Calculate churn probability (0.0–1.0).
        Higher = more likely to churn.
        """
        from api.offer_inventory.models import Click, Conversion

        score = 0.0
        now   = timezone.now()

        # Days since last click
        last_click = Click.objects.filter(user=user, is_fraud=False).order_by('-created_at').first()
        if last_click:
            days_since = (now - last_click.created_at).days
            score += min(1.0, days_since / 30) * cls.CHURN_WEIGHTS['days_since_last_click']
        else:
            score += cls.CHURN_WEIGHTS['days_since_last_click']  # Never clicked

        # Days since last conversion
        last_conv = Conversion.objects.filter(user=user, status__name='approved').order_by('-created_at').first()
        if last_conv:
            days_since = (now - last_conv.created_at).days
            score += min(1.0, days_since / 45) * cls.CHURN_WEIGHTS['days_since_last_conversion']
        else:
            score += cls.CHURN_WEIGHTS['days_since_last_conversion']

        # Declining activity frequency
        week1 = Click.objects.filter(user=user, created_at__gte=now - timedelta(days=7)).count()
        week2 = Click.objects.filter(
            user=user,
            created_at__gte=now - timedelta(days=14),
            created_at__lt=now - timedelta(days=7)
        ).count()
        if week2 > 0 and week1 < week2 * 0.5:
            score += cls.CHURN_WEIGHTS['declining_frequency']

        return min(1.0, score)

    @classmethod
    def update_all_churn_scores(cls, limit: int = 5000) -> int:
        """Batch update churn scores for all users."""
        from api.offer_inventory.models import ChurnRecord
        from django.contrib.auth import get_user_model
        User = get_user_model()

        count = 0
        for user in User.objects.filter(is_active=True)[:limit]:
            score = cls.predict_score(user)
            last_click = (
                __import__('api.offer_inventory.models', fromlist=['Click']).Click
                .objects.filter(user=user).order_by('-created_at').first()
            )
            days_inactive = (timezone.now() - last_click.created_at).days if last_click else 999

            ChurnRecord.objects.update_or_create(
                user=user,
                defaults={
                    'churn_probability': score,
                    'days_inactive'    : days_inactive,
                    'last_active'      : last_click.created_at if last_click else None,
                    'is_churned'       : score > 0.8,
                }
            )
            count += 1
        return count


# ════════════════════════════════════════════════════════
# 3. RETENTION ENGINE
# ════════════════════════════════════════════════════════

class RetentionEngine:
    """User retention analysis and improvement."""

    @staticmethod
    def get_day_n_retention(cohort_date, n_days: int) -> float:
        """
        Day-N retention: % of users who returned on day N.
        cohort_date: date when users first signed up.
        """
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import Click
        User = get_user_model()

        cohort_end  = cohort_date + timedelta(days=1)
        cohort_users = User.objects.filter(
            date_joined__date__gte=cohort_date,
            date_joined__date__lt=cohort_end,
        ).values_list('id', flat=True)

        if not cohort_users:
            return 0.0

        target_start = cohort_date + timedelta(days=n_days)
        target_end   = target_start + timedelta(days=1)

        returned = Click.objects.filter(
            user_id__in=cohort_users,
            created_at__date__gte=target_start,
            created_at__date__lt=target_end,
        ).values('user_id').distinct().count()

        return round(returned / len(cohort_users) * 100, 1)

    @staticmethod
    def get_retention_curve(cohort_date, days: int = 30) -> list:
        """Full retention curve for a cohort."""
        return [
            {'day': d, 'retention_pct': RetentionEngine.get_day_n_retention(cohort_date, d)}
            for d in [1, 3, 7, 14, 30][:days]
        ]


# ════════════════════════════════════════════════════════
# 4. LOYALTY POINTS (separate analytics service)
# ════════════════════════════════════════════════════════

class LoyaltyPointsAnalytics:
    """Analytics for the loyalty program."""

    @staticmethod
    def get_points_distribution() -> list:
        """Distribution of total_points across users."""
        from api.offer_inventory.models import UserProfile
        return list(
            UserProfile.objects.filter(total_points__gt=0)
            .values('loyalty_level__name')
            .annotate(user_count=Count('id'), avg_points=Avg('total_points'))
            .order_by('-avg_points')
        )

    @staticmethod
    def get_top_point_earners(limit: int = 20) -> list:
        from api.offer_inventory.models import UserProfile
        return list(
            UserProfile.objects.select_related('user', 'loyalty_level')
            .order_by('-total_points')
            .values('user__username', 'total_points', 'loyalty_level__name')
            [:limit]
        )

    @staticmethod
    def get_points_velocity(days: int = 7) -> float:
        """Average points earned per day across all users."""
        from api.offer_inventory.models import UserProfile
        total = UserProfile.objects.aggregate(s=Sum('total_points'))['s'] or 0
        from django.contrib.auth import get_user_model
        user_count = get_user_model().objects.filter(is_active=True).count()
        return round(total / max(user_count, 1) / days, 2)


# ════════════════════════════════════════════════════════
# 5. USER SEGMENTATION
# ════════════════════════════════════════════════════════

class UserSegmentationService:
    """Dynamic user segmentation for targeting."""

    BUILT_IN_SEGMENTS = {
        'high_earners'  : {'min_earnings': 1000},
        'new_users'     : {'joined_days': 7},
        'churning'      : {'inactive_days': 14, 'max_inactive': 30},
        'loyal'         : {'min_conversions': 10},
        'kyc_approved'  : {'has_kyc': True},
        'power_users'   : {'min_daily_offers': 5},
    }

    @classmethod
    def compute_segment(cls, segment_name: str) -> list:
        """Get user IDs for a built-in segment."""
        criteria = cls.BUILT_IN_SEGMENTS.get(segment_name, {})
        if not criteria:
            return []
        from api.offer_inventory.marketing.campaign_manager import MarketingCampaignService
        return MarketingCampaignService.build_audience(criteria)

    @classmethod
    def update_segment_counts(cls):
        """Update user_count for all UserSegment records."""
        from api.offer_inventory.models import UserSegment
        for seg in UserSegment.objects.filter(is_dynamic=True):
            try:
                from api.offer_inventory.marketing.campaign_manager import MarketingCampaignService
                ids   = MarketingCampaignService.build_audience(seg.criteria or {})
                UserSegment.objects.filter(id=seg.id).update(
                    user_count  =len(ids),
                    last_computed=timezone.now(),
                )
            except Exception as e:
                logger.error(f'Segment update error {seg.id}: {e}')


# ════════════════════════════════════════════════════════
# 6. SESSION REPLAY LOGGER
# ════════════════════════════════════════════════════════

class SessionReplayLogger:
    """
    Lightweight session event recorder.
    NOT a full session replay (no video/screenshots).
    Records click events, page views, and offer interactions.
    """

    SESSION_TTL = 3600 * 2  # 2 hours

    @staticmethod
    def start_session(user_id, session_id: str, meta: dict = None):
        """Start recording a user session."""
        session = {
            'user_id'   : str(user_id),
            'session_id': session_id,
            'started_at': timezone.now().isoformat(),
            'events'    : [],
            'meta'      : meta or {},
        }
        cache.set(f'session_replay:{session_id}', session, SessionReplayLogger.SESSION_TTL)

    @staticmethod
    def record_event(session_id: str, event_type: str, data: dict = None):
        """Record an event in a session."""
        key     = f'session_replay:{session_id}'
        session = cache.get(key)
        if not session:
            return
        session['events'].append({
            'type'     : event_type,
            'data'     : data or {},
            'timestamp': timezone.now().isoformat(),
        })
        # Keep last 200 events per session
        session['events'] = session['events'][-200:]
        cache.set(key, session, SessionReplayLogger.SESSION_TTL)

    @staticmethod
    def get_session(session_id: str) -> dict:
        return cache.get(f'session_replay:{session_id}', {})

    @staticmethod
    def end_session(session_id: str) -> dict:
        key     = f'session_replay:{session_id}'
        session = cache.get(key) or {}
        cache.delete(key)
        return session


# ════════════════════════════════════════════════════════
# 7. ENGAGEMENT SCORE
# ════════════════════════════════════════════════════════

class EngagementScoreCalculator:
    """
    Calculate user engagement score (0–100).
    Based on: recency, frequency, monetary value, loyalty.
    RFM model.
    """

    @classmethod
    def calculate(cls, user) -> dict:
        """Full engagement score breakdown."""
        from api.offer_inventory.models import Click, Conversion

        now    = timezone.now()
        scores = {}

        # Recency (R) — days since last activity
        last = Click.objects.filter(user=user, is_fraud=False).order_by('-created_at').first()
        if last:
            days_ago = (now - last.created_at).days
            scores['recency'] = max(0, 100 - days_ago * 3)
        else:
            scores['recency'] = 0

        # Frequency (F) — clicks/conversions in last 30 days
        since30 = now - timedelta(days=30)
        freq    = Click.objects.filter(user=user, created_at__gte=since30, is_fraud=False).count()
        scores['frequency'] = min(100, freq * 5)

        # Monetary (M) — earnings in last 30 days
        earnings = Conversion.objects.filter(
            user=user, created_at__gte=since30, status__name='approved'
        ).aggregate(t=Sum('reward_amount'))['t'] or Decimal('0')
        scores['monetary'] = min(100, float(earnings) * 10)

        # Loyalty (L) — loyalty tier bonus
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.select_related('loyalty_level').get(user=user)
            tier_bonus = {'Bronze': 10, 'Silver': 25, 'Gold': 50, 'Platinum': 80}
            scores['loyalty'] = tier_bonus.get(
                profile.loyalty_level.name if profile.loyalty_level else '', 0
            )
        except Exception:
            scores['loyalty'] = 0

        # Weighted total
        total = (
            scores['recency']   * 0.30 +
            scores['frequency'] * 0.25 +
            scores['monetary']  * 0.30 +
            scores['loyalty']   * 0.15
        )

        return {
            'total'     : round(total, 1),
            'grade'     : cls._grade(total),
            'breakdown' : scores,
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 80: return 'A'
        if score >= 60: return 'B'
        if score >= 40: return 'C'
        if score >= 20: return 'D'
        return 'F'


# ════════════════════════════════════════════════════════
# 8. REFERRAL CHAIN
# ════════════════════════════════════════════════════════

class ReferralChainAnalyzer:
    """Analyze multi-level referral chains."""

    @staticmethod
    def get_chain(user, max_depth: int = 5) -> dict:
        """Get full referral chain for a user (upward)."""
        from api.offer_inventory.models import UserReferral

        chain = []
        current = user
        for _ in range(max_depth):
            try:
                ref = UserReferral.objects.select_related('referrer').get(referred=current)
                chain.append({
                    'user'    : ref.referrer.username,
                    'level'   : len(chain) + 1,
                    'earnings': float(ref.total_earnings_generated),
                })
                current = ref.referrer
            except UserReferral.DoesNotExist:
                break

        return {'chain': chain, 'depth': len(chain)}

    @staticmethod
    def get_downline_stats(user) -> dict:
        """Stats for all users referred by this user (downline)."""
        from api.offer_inventory.models import UserReferral, Conversion

        direct = UserReferral.objects.filter(referrer=user)
        direct_count = direct.count()
        converted    = direct.filter(is_converted=True).count()

        # Total earnings generated by downline
        total_gen = direct.aggregate(t=Sum('total_earnings_generated'))['t'] or Decimal('0')

        return {
            'direct_referrals'  : direct_count,
            'converted'         : converted,
            'conversion_rate_pct': round(converted / max(direct_count, 1) * 100, 1),
            'total_earnings_generated': float(total_gen),
        }

    @staticmethod
    def detect_referral_fraud(user) -> dict:
        """Detect if referral chain looks fraudulent."""
        from api.offer_inventory.models import UserReferral

        refs     = UserReferral.objects.filter(referrer=user)
        count    = refs.count()
        if count < 5:
            return {'suspicious': False, 'reason': 'insufficient_data'}

        # Check if all referrals registered within 24h of each other
        from django.db.models import Max, Min
        time_agg = refs.aggregate(
            earliest=Min('created_at'), latest=Max('created_at')
        )
        if time_agg['earliest'] and time_agg['latest']:
            span_hours = (time_agg['latest'] - time_agg['earliest']).total_seconds() / 3600
            if count >= 10 and span_hours < 2:
                return {'suspicious': True, 'reason': f'{count} referrals in {span_hours:.1f}h'}

        return {'suspicious': False, 'reason': 'ok'}
