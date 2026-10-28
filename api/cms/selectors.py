# api/cms/selectors.py
"""
CMS Selectors — read-only query functions.
Following Service/Selector pattern: Selectors = read, Services = write.
All DB queries for READ operations go here — ViewSets call selectors, not models directly.
"""
from django.db.models import QuerySet
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, FloatField
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Type Variables ─────────────────────────────────────

T = TypeVar('T')
ModelType = TypeVar('ModelType')


# ── Base Selector Classes ─────────────────────────────────────

class BaseSelector:
    """Base selector class with common functionality."""
    
    def __init__(self, cache_timeout: int = 300):
        """Initialize selector with cache timeout."""
        self.cache_timeout = cache_timeout
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key for selector."""
        key_parts = [self.__class__.__name__] + [str(arg) for arg in args]
        key_parts += [f"{k}:{v}" for k, v in sorted(kwargs.items())]
        return ":".join(key_parts)
    
    def get_cached(self, cache_key: str, default=None):
        """Get value from cache."""
        return cache.get(cache_key, default)
    
    def set_cache(self, cache_key: str, value, timeout: int = None):
        """Set value in cache."""
        timeout = timeout or self.cache_timeout
        cache.set(cache_key, value, timeout)
    
    def invalidate_cache(self, *args, **kwargs):
        """Invalidate cache for selector."""
        cache_key = self.get_cache_key(*args, **kwargs)
        cache.delete(cache_key)


# ── Original User Selectors (Enhanced) ─────────────────────────────────────

class UserSelector:
    """Enhanced user selector with additional functionality."""
    
    @staticmethod
    def get_by_id(user_id: int):
        """Get user by ID with related data."""
        try:
            return User.objects.select_related('profile', 'virtual_balance').get(id=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_by_subid(subid: str):
        """Resolve CPAlead subid to user. subid = user.id as string."""
        try:
            return User.objects.get(id=int(subid))
        except (User.DoesNotExist, ValueError, TypeError):
            return None

    @staticmethod
    def get_active_users(days: int = 30):
        """Get active users within specified days."""
        cutoff = timezone.now() - timedelta(days=days)
        return User.objects.filter(last_login__gte=cutoff, is_active=True)

    @staticmethod
    def get_top_earners(limit: int = 10) -> List[Dict]:
        """Get top earners based on completed surveys."""
        from api.cms.models_new.withdrawal import UserProfile
        return list(
            UserProfile.objects
            .select_related('user')
            .filter(show_on_leaderboard=True, is_suspended=False)
            .order_by('-total_earned_usd')
            .values('user__username', 'total_earned_usd', 'level')[:limit]
        )
    
    @staticmethod
    def get_user_stats(user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics."""
        try:
            user = User.objects.get(id=user_id)
            
            stats = {
                'total_surveys': user.survey_completions.count(),
                'completed_surveys': user.survey_completions.filter(status='completed').count(),
                'total_earned': user.reward_transactions.filter(
                    transaction_type='earned', status='completed'
                ).aggregate(total=Sum('amount'))['total'] or 0,
                'profile_completeness': getattr(user.userprofile, 'completeness_percentage', 0),
                'last_login': user.last_login,
                'date_joined': user.date_joined
            }
            
            return stats
            
        except User.DoesNotExist:
            return {}
    
    @staticmethod
    def search_users(query: str, limit: int = 20) -> List[User]:
        """Search users by username or email."""
        queryset = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query),
            is_active=True
        )[:limit]
        
        return list(queryset)


# ════════════════════════════════════════════════════════════════
# VIRTUAL CURRENCY SELECTORS
# ════════════════════════════════════════════════════════════════

class VirtualCurrencySelector:
    @staticmethod
    def get_active_currency():
        cache_key = 'sel_virtual_currency_active'
        cached = cache.get(cache_key)
        if cached is None:
            from api.cms.models_new.cpalead import VirtualCurrency
            cached = VirtualCurrency.get_active()
            cache.set(cache_key, cached, 300)
        return cached

    @staticmethod
    def get_user_balance(user) -> Decimal:
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            bal = UserVirtualBalance.objects.get(user=user)
            return bal.balance
        except Exception:
            return Decimal('0')

    @staticmethod
    def get_user_transaction_history(user, limit: int = 50) -> List[Dict]:
        try:
            from api.cms.models_new.cpalead import VirtualTransaction
            txns = (VirtualTransaction.objects
                    .filter(user=user)
                    .order_by('-created_at')[:limit])
            return [{
                'id': t.id,
                'type': t.tx_type,
                'amount': float(t.amount),
                'balance_after': float(t.balance_after),
                'description': t.description,
                'created_at': t.created_at.isoformat(),
            } for t in txns]
        except Exception:
            return []


# ══════════════════════════════════════════════════════════════════
# VIRTUAL CURRENCY SELECTORS
# ══════════════════════════════════════════════════════════════════

class VirtualCurrencySelector:
    @staticmethod
    def get_active_currency():
        cache_key = 'sel_virtual_currency_active'
        cached = cache.get(cache_key)
        if cached is None:
            from api.cms.models_new.cpalead import VirtualCurrency
            cached = VirtualCurrency.get_active()
            cache.set(cache_key, cached, 300)
        return cached

    @staticmethod
    def get_user_balance(user) -> Decimal:
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            bal = UserVirtualBalance.objects.get(user=user)
            return bal.balance
        except Exception:
            return Decimal('0')

    @staticmethod
    def get_user_transaction_history(user, limit: int = 50) -> List[Dict]:
        try:
            from api.cms.models_new.cpalead import VirtualTransaction
            txns = (VirtualTransaction.objects
                    .filter(user=user)
                    .order_by('-created_at')[:limit])
            return [{
                'id': t.id,
                'type': t.tx_type,
                'amount': float(t.amount),
                'balance_after': float(t.balance_after),
                'description': t.description,
                'created_at': t.created_at.isoformat(),
            } for t in txns]
        except Exception:
            return []

    @staticmethod
    def get_user_today_earnings(user) -> Decimal:
        try:
            from api.cms.services_new.CPALeadService import EarningCapService
            return EarningCapService.get_today_earnings(user)
        except Exception:
            return Decimal('0')


# ══════════════════════════════════════════════════════════════════
# CONVERSION / POSTBACK SELECTORS
# ══════════════════════════════════════════════════════════════════

class ConversionSelector:
    @staticmethod
    def lead_id_exists(lead_id: str) -> bool:
        """Fast dedup check for CPAlead postback."""
        from api.cms.models_new.cpalead import ConversionLog
        return ConversionLog.objects.filter(lead_id=lead_id).exists()

    @staticmethod
    def get_user_conversions(user, status: str = None, limit: int = 50) -> QuerySet:
        from api.cms.models_new.cpalead import ConversionLog
        qs = ConversionLog.objects.filter(user=user)
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def get_conversion_stats(days: int = 30) -> Dict:
        from api.cms.models_new.cpalead import ConversionLog
        import datetime
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return ConversionLog.objects.filter(created_at__gte=cutoff).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            total_payout=Sum('payout_usd', filter=Q(status='approved')),
            avg_payout=Avg('payout_usd', filter=Q(status='approved')),
        )

    @staticmethod
    def get_daily_conversions(days: int = 30) -> List[Dict]:
        from api.cms.models_new.cpalead import ConversionLog
        from django.db.models import TruncDate
        import datetime
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            ConversionLog.objects
            .filter(status='approved', created_at__gte=cutoff)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'), total_usd=Sum('payout_usd'))
            .order_by('date')
        )


# ══════════════════════════════════════════════════════════════════
# OFFER / OFFERWALL SELECTORS
# ══════════════════════════════════════════════════════════════════

class OfferSelector:
    @staticmethod
    def get_active_offers(country: str = '', device: str = '', limit: int = 20) -> List[Dict]:
        try:
            from api.cms.models_new.cpalead import OfferCache
            qs = OfferCache.objects.filter(is_active=True)
            if country:
                qs = qs.filter(Q(countries=[]) | Q(countries__contains=country.upper()))
            if device:
                qs = qs.filter(Q(devices=[]) | Q(devices__contains=device.lower()))
            qs = qs.order_by('-is_featured', '-payout_usd')[:limit]
            return [{
                'offer_id': o.offer_id,
                'title': o.title,
                'description': o.description,
                'payout_usd': float(o.payout_usd),
                'payout_virtual': float(o.payout_virtual),
                'offer_type': o.offer_type,
                'is_featured': o.is_featured,
                'is_quiz': o.is_quiz,
                'icon_url': o.icon_url,
                'offer_url': o.offer_url,
                'countries': o.countries,
                'devices': o.devices,
            } for o in qs]
        except Exception:
            return []

    @staticmethod
    def get_offerwall_config():
        cache_key = 'sel_offerwall_config'
        cached = cache.get(cache_key)
        if cached is None:
            try:
                from api.cms.models_new.cpalead import OfferWallConfig
                cached = OfferWallConfig.objects.select_related('currency').filter(is_active=True).first()
            except Exception:
                cached = None
            cache.set(cache_key, cached, 300)
        return cached

    @staticmethod
    def get_offer_by_id(offer_id: str) -> Optional[Any]:
        try:
            from api.cms.models_new.cpalead import OfferCache
            return OfferCache.objects.get(offer_id=offer_id, is_active=True)
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════
# CONTENT LOCKER SELECTORS
# ══════════════════════════════════════════════════════════════════

class LockerSelector:
    @staticmethod
    def get_locker(locker_id: int) -> Optional[Any]:
        try:
            from api.cms.models_new.cpalead import ContentLocker
            return ContentLocker.objects.get(id=locker_id, is_active=True)
        except Exception:
            return None

    @staticmethod
    def is_unlocked_for_user(locker_id: int, user=None, session_key: str = '') -> bool:
        try:
            from api.cms.models_new.cpalead import LockerUnlock
            qs = LockerUnlock.objects.filter(locker_id=locker_id, is_valid=True)
            if user and user.is_authenticated:
                return qs.filter(user=user).exists()
            elif session_key:
                return qs.filter(session_key=session_key).exists()
            return False
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════
# REFERRAL SELECTORS
# ══════════════════════════════════════════════════════════════════

class ReferralSelector:
    @staticmethod
    def get_referral_code(user) -> Optional[str]:
        try:
            from api.cms.models_new.referral import ReferralCode
            rc = ReferralCode.objects.get(user=user, is_active=True)
            return rc.code
        except Exception:
            return None

    @staticmethod
    def get_relationship(referred_user) -> Optional[Any]:
        try:
            from api.cms.models_new.referral import ReferralRelationship
            return ReferralRelationship.objects.select_related('referrer').get(
                referred=referred_user, is_active=True
            )
        except Exception:
            return None

    @staticmethod
    def get_referral_earnings(user, limit: int = 50) -> List[Dict]:
        try:
            from api.cms.models_new.referral import ReferralEarning
            earnings = ReferralEarning.objects.filter(referrer=user).order_by('-created_at')[:limit]
            return [{
                'id': e.id,
                'referred_username': e.referred.username,
                'source': e.source,
                'bonus_usd': float(e.bonus_usd),
                'bonus_coins': float(e.bonus_coins),
                'created_at': e.created_at.isoformat(),
            } for e in earnings]
        except Exception:
            return []


# ══════════════════════════════════════════════════════════════════
# LEADERBOARD SELECTORS
# ══════════════════════════════════════════════════════════════════

class LeaderboardSelector:
    @staticmethod
    def get_top(period_type: str = 'weekly', category: str = 'earnings',
                limit: int = 10) -> List[Dict]:
        cache_key = f'sel_leaderboard_{period_type}_{category}_{limit}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService
            result = LeaderboardService.get_top(period_type, category, limit)
            cache.set(cache_key, result, 3600)
            return result
        except Exception:
            return []

    @staticmethod
    def get_user_rank(user, period_type: str = 'weekly') -> Dict:
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService
            return LeaderboardService.get_user_rank(user, period_type)
        except Exception:
            return {'rank': 0, 'score': 0}

    @staticmethod
    def get_streak(user) -> Dict:
        try:
            from api.cms.services_new.LeaderboardService import StreakService
            return StreakService.get_streak_info(user)
        except Exception:
            return {'current_streak': 0, 'multiplier': 1.0}


# ══════════════════════════════════════════════════════════════════
# BLOG SELECTORS
# ══════════════════════════════════════════════════════════════════

class BlogSelector:
    @staticmethod
    def get_published(limit: int = 10, category_slug: str = '', tag: str = '') -> QuerySet:
        try:
            from api.cms.models_new.blog import BlogPost
            qs = BlogPost.objects.filter(status='published').select_related('author')
            if category_slug:
                qs = qs.filter(category__slug=category_slug)
            if tag:
                qs = qs.filter(tags__slug=tag)
            return qs.order_by('-published_at')[:limit]
        except Exception:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.none()

    @staticmethod
    def get_by_slug(slug: str) -> Optional[Any]:
        try:
            from api.cms.models_new.blog import BlogPost
            return BlogPost.objects.select_related('author').get(slug=slug, status='published')
        except Exception:
            return None

    @staticmethod
    def get_related(post, limit: int = 3) -> QuerySet:
        try:
            from api.cms.models_new.blog import BlogPost
            qs = BlogPost.objects.filter(status='published').exclude(id=post.id)
            if hasattr(post, 'category') and post.category:
                qs = qs.filter(category=post.category)
            return qs.order_by('-published_at')[:limit]
        except Exception:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.none()


# ══════════════════════════════════════════════════════════════════
# WITHDRAWAL SELECTORS
# ══════════════════════════════════════════════════════════════════

class WithdrawalSelector:
    @staticmethod
    def get_pending_admin() -> QuerySet:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(
            status='pending'
        ).select_related('user', 'payout_method').order_by('created_at')

    @staticmethod
    def get_user_summary(user) -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        from api.cms.models_new.cpalead import UserVirtualBalance
        summary = WithdrawalRequest.objects.filter(user=user).aggregate(
            total_requested=Count('id'),
            total_paid=Sum('net_usd', filter=Q(status='paid')),
            total_pending=Count('id', filter=Q(status__in=['pending', 'approved', 'processing'])),
        )
        balance = Decimal('0')
        try:
            bal = UserVirtualBalance.objects.get(user=user)
            balance = bal.balance
        except Exception:
            pass
        return {
            'balance_coins': float(balance),
            'total_requests': summary['total_requested'] or 0,
            'total_paid_usd': float(summary['total_paid'] or 0),
            'pending_count': summary['total_pending'] or 0,
        }


# ══════════════════════════════════════════════════════════════════
# SITE CONFIG SELECTORS
# ══════════════════════════════════════════════════════════════════

class SiteConfigSelector:
    @staticmethod
    def get_public_config(domain: str = '') -> Dict:
        from api.cms.services_new.WithdrawalService import SiteConfigService
        return SiteConfigService.get_config(domain)

    @staticmethod
    def is_feature_enabled(feature: str, domain: str = '') -> bool:
        config = SiteConfigSelector.get_public_config(domain)
        return config.get('features', {}).get(feature, True)

    @staticmethod
    def get_min_withdrawal() -> Dict:
        config = SiteConfigSelector.get_public_config()
        return {
            'min_coins': config.get('min_withdrawal_coins', 1000),
            'min_usd': config.get('min_withdrawal_usd', 10),
        }
