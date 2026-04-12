"""
api/users/referral/referral_tracker.py
Referral tracking bridge — users app-এ referral summary দেখানোর জন্য।
Full tracking, commission — api.referral-এর কাজ।
"""
import logging

logger = logging.getLogger(__name__)


class ReferralTracker:
    """
    users app-এ profile page বা dashboard-এ
    referral summary দরকার হলে এই bridge use করো।
    api.referral-এর model-এ সরাসরি query করো না।
    """

    def get_user_summary(self, user) -> dict:
        """
        User-এর referral summary।
        Profile page বা dashboard-এ দেখাবে।
        """
        try:
            from django.apps import apps
            Referral = apps.get_model('referral', 'Referral')

            total   = Referral.objects.filter(referrer=user).count()
            active  = Referral.objects.filter(referrer=user, status='qualified').count()
            pending = Referral.objects.filter(referrer=user, status='pending').count()

            from django.db.models import Sum
            earned  = Referral.objects.filter(
                referrer=user, status='rewarded'
            ).aggregate(total=Sum('reward_amount'))['total'] or 0

            from ..constants import UserTier, ReferralConstants
            tier        = getattr(user, 'tier', 'FREE')
            bonus_rate  = UserTier.REFERRAL_BONUS.get(tier, 5)

            return {
                'total_referrals':   total,
                'active_referrals':  active,
                'pending_referrals': pending,
                'total_earned':      float(earned),
                'bonus_rate_pct':    bonus_rate,
                'referral_code':     getattr(user, 'referral_code', ''),
            }

        except Exception as e:
            logger.warning(f'Referral summary from api.referral failed: {e}')
            return self._fallback_summary(user)

    def get_referral_list(self, user, limit: int = 10) -> list:
        """Referred users list — profile page-এর জন্য"""
        try:
            from django.apps import apps
            Referral = apps.get_model('referral', 'Referral')
            return list(
                Referral.objects.filter(referrer=user)
                .select_related('referred_user')
                .order_by('-created_at')
                .values(
                    'referred_user__username',
                    'referred_user__date_joined',
                    'status',
                    'reward_amount',
                    'created_at',
                )[:limit]
            )
        except Exception as e:
            logger.warning(f'Referral list failed: {e}')
            return self._fallback_list(user, limit)

    def get_referral_stats_for_dashboard(self, user) -> dict:
        """Dashboard widget-এর জন্য compact stats"""
        summary = self.get_user_summary(user)
        return {
            'count':  summary.get('total_referrals', 0),
            'earned': summary.get('total_earned', 0.0),
            'code':   summary.get('referral_code', ''),
        }

    def record_referral_click(self, referral_code: str, ip: str, user_agent: str) -> None:
        """
        Referral link click হলে record করো।
        Cookie set করার আগে।
        api.referral-কে signal দাও।
        """
        try:
            logger.info(f'Referral click: code={referral_code}, ip={ip}')
            # api.referral.signals.referral_link_clicked.send(...)
        except Exception as e:
            logger.warning(f'Referral click record failed: {e}')

    # ─────────────────────────────────────
    # FALLBACK — api.referral না থাকলে
    # ─────────────────────────────────────
    def _fallback_summary(self, user) -> dict:
        """api.referral app না থাকলে User model থেকে"""
        try:
            from django.contrib.auth import get_user_model
            User   = get_user_model()
            count  = User.objects.filter(referred_by=user).count()
            return {
                'total_referrals':   count,
                'active_referrals':  0,
                'pending_referrals': 0,
                'total_earned':      0.0,
                'bonus_rate_pct':    5,
                'referral_code':     getattr(user, 'referral_code', ''),
            }
        except Exception:
            return {
                'total_referrals': 0,
                'total_earned':    0.0,
                'referral_code':   getattr(user, 'referral_code', ''),
            }

    def _fallback_list(self, user, limit: int) -> list:
        """api.referral app না থাকলে User model থেকে"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return list(
                User.objects.filter(referred_by=user)
                .order_by('-date_joined')
                .values('username', 'date_joined', 'is_active')[:limit]
            )
        except Exception:
            return []


# Singleton
referral_tracker = ReferralTracker()
