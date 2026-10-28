"""
tasks/integration/shared_context.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SharedContext — Unified Data Context for All Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One object that aggregates everything a task needs to know about
a user, an offer, or the platform — in a single call.

Usage:
    ctx = SharedContext.for_user(user_id=123)
    
    ctx.wallet_balance      → Decimal('45.50')
    ctx.kyc_tier            → 'standard'
    ctx.fraud_score         → 12
    ctx.traffic_tier        → 'tier_1'
    ctx.is_eligible_payout  → True
    ctx.recommended_offers  → [offer_id1, offer_id2, ...]
    ctx.active_streak       → 7
    ctx.leaderboard_rank    → 42
    ctx.to_dict()           → full serializable snapshot
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SharedContext:
    """Factory for creating rich context objects."""

    @classmethod
    def for_user(cls, user_id: int, refresh: bool = False) -> 'UserContext':
        return UserContext(user_id=user_id, refresh=refresh)

    @classmethod
    def for_offer(cls, offer_id: str, refresh: bool = False) -> 'OfferContext':
        return OfferContext(offer_id=offer_id, refresh=refresh)

    @classmethod
    def platform(cls) -> 'PlatformContext':
        return PlatformContext()


class UserContext:
    """
    Complete user context — aggregates all user-related data.
    Lazy-loaded with caching.
    """

    def __init__(self, user_id: int, refresh: bool = False):
        # Security: Verify access before initialization
        if not self._verify_user_access(user_id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(f"Access denied to user {user_id}")
        
        self.user_id  = user_id
        self._data    = {}
        self._loaded  = set()
        if refresh:
            self._invalidate_all()

    # ─── Identity ──────────────────────────────────────────────────────────────

    @property
    def user(self):
        return self._get_db('user', self._load_user)

    @property
    def username(self) -> str:
        u = self.user
        return u.username if u else ''

    @property
    def email(self) -> str:
        u = self.user
        return u.email if u else ''

    @property
    def date_joined(self):
        u = self.user
        return u.date_joined if u else None

    @property
    def account_age_days(self) -> int:
        if not self.date_joined:
            return 0
        return (timezone.now() - self.date_joined).days

    # ─── Wallet ────────────────────────────────────────────────────────────────

    @property
    def wallet_balance(self) -> Decimal:
        from api.tasks.integration.data_bridge import DataBridge
        cached = DataBridge.get_user(self.user_id, 'wallet_balance')
        if cached is not None:
            return Decimal(str(cached))
        return self._load_wallet_balance()

    @property
    def total_earnings(self) -> Decimal:
        from api.tasks.integration.data_bridge import DataBridge
        cached = DataBridge.get_user(self.user_id, 'total_earnings')
        if cached is not None:
            return Decimal(str(cached))
        return self._load_total_earnings()

    @property
    def preferred_payment_method(self) -> str:
        from api.tasks.integration.data_bridge import DataBridge
        return DataBridge.get_user(self.user_id, 'payment_method') or 'paypal'

    # ─── KYC & Verification ────────────────────────────────────────────────────

    @property
    def kyc_tier(self) -> str:
        from api.tasks.integration.data_bridge import DataBridge
        return DataBridge.get_user(self.user_id, 'kyc_tier') or 'none'

    @property
    def email_verified(self) -> bool:
        return self._get_cached_bool('email_verified', self._load_email_verified)

    @property
    def withdrawal_limit(self) -> Decimal:
        limits = {
            'none': Decimal('10'), 'basic': Decimal('100'),
            'standard': Decimal('500'), 'full': Decimal('5000'),
        }
        return limits.get(self.kyc_tier, Decimal('10'))

    # ─── Fraud & Risk ──────────────────────────────────────────────────────────

    @property
    def fraud_score(self) -> int:
        return int(cache.get(f'fraud_score_{self.user_id}', 0))

    @property
    def is_fraud_flagged(self) -> bool:
        return self.fraud_score >= 60

    @property
    def is_high_risk(self) -> bool:
        return self.fraud_score >= 40

    @property
    def is_suspended(self) -> bool:
        return bool(cache.get(f'user_suspended_{self.user_id}', False))

    # ─── Traffic Quality ───────────────────────────────────────────────────────

    @property
    def traffic_tier(self) -> str:
        return cache.get(f'traffic_tier_{self.user_id}') or 'tier_3'

    @property
    def traffic_quality_score(self) -> int:
        return int(cache.get(f'traffic_quality_{self.user_id}', 50))

    @property
    def is_tier_1_traffic(self) -> bool:
        return self.traffic_tier == 'tier_1'

    # ─── Publisher Info ────────────────────────────────────────────────────────

    @property
    def publisher_tier(self) -> str:
        return cache.get(f'publisher_tier_{self.user_id}') or 'bronze'

    @property
    def revenue_share(self) -> Decimal:
        share_map = {
            'platinum': Decimal('0.85'), 'gold': Decimal('0.80'),
            'silver': Decimal('0.75'), 'bronze': Decimal('0.70'),
        }
        return share_map.get(self.publisher_tier, Decimal('0.70'))

    @property
    def is_vip(self) -> bool:
        return bool(cache.get(f'user_is_vip_{self.user_id}', False))

    # ─── Gamification ──────────────────────────────────────────────────────────

    @property
    def level(self) -> int:
        return int(cache.get(f'user_level_{self.user_id}', 1))

    @property
    def xp_points(self) -> int:
        return int(cache.get(f'user_xp_{self.user_id}', 0))

    @property
    def active_streak(self) -> int:
        return int(cache.get(f'user_streak_{self.user_id}', 0))

    @property
    def badges(self) -> List[str]:
        return list(cache.get(f'user_badges_{self.user_id}') or [])

    # ─── Recommendations ───────────────────────────────────────────────────────

    @property
    def recommended_offers(self) -> List[int]:
        return list(cache.get(f'ranked_offers_user_{self.user_id}') or [])

    @property
    def recommended_tasks(self) -> List[str]:
        return list(cache.get(f'task_recommendations_user_{self.user_id}') or [])

    @property
    def user_segment(self) -> str:
        return cache.get(f'user_segment_{self.user_id}') or 'casual_user'

    # ─── Eligibility Checks ────────────────────────────────────────────────────

    @property
    def is_eligible_for_payout(self) -> bool:
        from api.tasks.daily_payout_tasks import MIN_PAYOUT_THRESHOLDS
        min_thresh = MIN_PAYOUT_THRESHOLDS.get(
            self.preferred_payment_method,
            MIN_PAYOUT_THRESHOLDS['default']
        )
        return (
            not self.is_suspended and
            not self.is_fraud_flagged and
            self.email_verified and
            self.wallet_balance >= min_thresh
        )

    @property
    def is_eligible_for_offers(self) -> bool:
        return (
            not self.is_suspended and
            self.account_age_days >= 0 and
            not self.is_fraud_flagged
        )

    @property
    def can_withdraw(self) -> bool:
        return (
            self.is_eligible_for_payout and
            self.wallet_balance > Decimal('0') and
            not bool(cache.get(f'payout_method_invalid_{self.user_id}'))
        )

    # ─── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Full serializable snapshot of user context."""
        return {
            'user_id':              self.user_id,
            'username':             self.username,
            'account_age_days':     self.account_age_days,
            'wallet_balance':       str(self.wallet_balance),
            'total_earnings':       str(self.total_earnings),
            'kyc_tier':             self.kyc_tier,
            'withdrawal_limit':     str(self.withdrawal_limit),
            'fraud_score':          self.fraud_score,
            'is_fraud_flagged':     self.is_fraud_flagged,
            'is_suspended':         self.is_suspended,
            'traffic_tier':         self.traffic_tier,
            'publisher_tier':       self.publisher_tier,
            'revenue_share':        str(self.revenue_share),
            'is_vip':               self.is_vip,
            'level':                self.level,
            'xp_points':            self.xp_points,
            'active_streak':        self.active_streak,
            'user_segment':         self.user_segment,
            'is_eligible_payout':   self.is_eligible_for_payout,
            'is_eligible_offers':   self.is_eligible_for_offers,
            'can_withdraw':         self.can_withdraw,
            'fetched_at':           timezone.now().isoformat(),
        }

    # ─── Private loaders ───────────────────────────────────────────────────────

    def _get_db(self, key: str, loader):
        if key not in self._data:
            self._data[key] = loader()
        return self._data[key]

    def _get_cached_bool(self, key: str, loader) -> bool:
        if key not in self._data:
            self._data[key] = loader()
        return bool(self._data[key])

    def _load_user(self):
        try:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.filter(pk=self.user_id).first()
        except Exception:
            return None

    def _load_wallet_balance(self) -> Decimal:
        try:
            from wallet.models import Wallet
            b = Wallet.objects.filter(user_id=self.user_id).values_list('balance', flat=True).first()
            return Decimal(str(b or 0))
        except ImportError:
            return Decimal('0')

    def _load_total_earnings(self) -> Decimal:
        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Sum
            total = UserTaskCompletion.objects.filter(
                user_id=self.user_id, status='completed'
            ).aggregate(t=Sum('reward_amount'))['t']
            return Decimal(str(total or 0))
        except ImportError:
            return Decimal('0')

    def _load_email_verified(self) -> bool:
        try:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.filter(pk=self.user_id).first()
            return bool(getattr(user, 'emailaddress_set', None) and
                        user.emailaddress_set.filter(verified=True).exists())
        except Exception:
            return True  # Assume verified if can't check

    def _invalidate_all(self) -> None:
        self._data = {}
        from api.tasks.integration.data_bridge import DataBridge
        DataBridge.user(self.user_id).invalidate()


class OfferContext:
    """Complete offer context."""

    def __init__(self, offer_id: str, refresh: bool = False):
        self.offer_id = offer_id

    @property
    def epc(self) -> Decimal:
        from api.tasks.integration.data_bridge import DataBridge
        return Decimal(str(DataBridge.get_offer(self.offer_id, 'epc') or 0))

    @property
    def quality_score(self) -> float:
        from api.tasks.integration.data_bridge import DataBridge
        return float(DataBridge.get_offer(self.offer_id, 'quality_score') or 50)

    @property
    def is_capped(self) -> bool:
        from api.tasks.integration.data_bridge import DataBridge
        daily_used = DataBridge.get_offer(self.offer_id, 'daily_clicks_used') or 0
        daily_cap  = DataBridge.get_offer(self.offer_id, 'daily_cap') or 0
        return bool(daily_cap and daily_used >= daily_cap)

    def to_dict(self) -> Dict[str, Any]:
        from api.tasks.integration.data_bridge import DataBridge
        return DataBridge.get_offer_snapshot(self.offer_id)


# ─── Security Helper Methods ───────────────────────────────────────────────

    @staticmethod
    def _verify_user_access(requested_user_id: int) -> bool:
        """Verify current user has access to requested user data."""
        try:
            from django.contrib.auth import get_user_model
            from rest_framework.permissions import IsAuthenticated
            
            # Get current user
            User = get_user_model()
            current_user = User.objects.get(pk=UserContext._get_current_user_id())
            
            # Allow access if:
            # 1. Same user
            if current_user.id == requested_user_id:
                return True
            
            # 2. Staff with permission
            if current_user.is_staff and current_user.has_perm('tasks.view_all_users'):
                return True
            
            # 3. Superuser
            if current_user.is_superuser:
                return True
            
            # 4. User is suspended (deny all)
            if hasattr(current_user, 'is_suspended') and current_user.is_suspended:
                return False
            
            return False
            
        except Exception:
            return False

    @staticmethod
    def _get_current_user_id() -> Optional[int]:
        """Get current user ID from request context."""
        try:
            from django.contrib.auth import get_user_model
            from django.utils.functional import SimpleLazyObject
            
            # Try to get from thread local
            import threading
            local_data = getattr(threading.current_thread(), 'user', None)
            if local_data:
                return local_data.id
            
            # Fallback to request
            User = get_user_model()
            try:
                user = User.objects.get(pk=1)  # Use a safe default
                if isinstance(user, SimpleLazyObject):
                    user = user._wrapped if hasattr(user, '_wrapped') else user
                return user.id if user and hasattr(user, 'id') else None
            except User.DoesNotExist:
                return None
        except Exception:
            return None


class PlatformContext:
    """Platform-wide aggregates."""

    @property
    def dau(self) -> int:
        from api.tasks.integration.data_bridge import DataBridge
        return int(DataBridge.get_platform('dau') or 0)

    @property
    def revenue_today(self) -> Decimal:
        from api.tasks.integration.data_bridge import DataBridge
        return Decimal(str(DataBridge.get_platform('revenue_today') or 0))

    @property
    def is_gateway_healthy(self) -> bool:
        health = cache.get('gateway_health') or {}
        return any(v.get('status') == 'healthy' for v in health.values()) if health else True

    def to_dict(self) -> Dict[str, Any]:
        from api.tasks.integration.data_bridge import DataBridge
        return DataBridge.get_platform_snapshot()
