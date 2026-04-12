# api/offer_inventory/repository.py
"""
Repository Layer — সব DB query এখানে।
View বা Service সরাসরি ORM ব্যবহার করবে না।
"""
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Avg, Prefetch
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import timedelta
from typing import Optional, List

from .models import (
    Offer, OfferNetwork, OfferCategory, Click, Conversion,
    ConversionStatus, PostbackLog, BlacklistedIP, UserRiskProfile,
    FraudAttempt, FraudRule, DailyStat, NetworkStat,
    WithdrawalRequest, WalletTransaction, PayoutBatch,
    UserProfile, SubID, SmartLink, OfferCap,
    DuplicateConversionFilter, RevenueShare, WalletAudit,
    ReferralCommission, Notification, MasterSwitch,
    ActivityHeatmap, ChurnRecord, GeoData,
)
from .constants import (
    CACHE_TTL_OFFER_LIST, CACHE_TTL_OFFER_DETAIL,
    CACHE_TTL_DAILY_STATS,
)


# ══════════════════════════════════════════════════════
# OFFER REPOSITORY
# ══════════════════════════════════════════════════════

class OfferRepository:

    @staticmethod
    def get_active_offers(tenant=None, country=None, device=None,
                          category=None, page=1, page_size=20) -> List[Offer]:
        """Active + available অফার list।"""
        now = timezone.now()
        qs = Offer.objects.select_related('network', 'category').prefetch_related('tags', 'caps')

        qs = qs.filter(status='active')
        qs = qs.filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

        if tenant:
            qs = qs.filter(tenant=tenant)
        if category:
            qs = qs.filter(category__slug=category)
        if country:
            qs = qs.filter(
                Q(visibility_rules__isnull=True) |
                Q(visibility_rules__rule_type='country',
                  visibility_rules__operator='include',
                  visibility_rules__values__contains=[country])
            )

        start = (page - 1) * page_size
        return list(qs.order_by('-is_featured', '-reward_amount')[start:start + page_size])

    @staticmethod
    def get_offer_by_id(offer_id: str, tenant=None) -> Optional[Offer]:
        """Single offer fetch by UUID।"""
        try:
            qs = Offer.objects.select_related('network', 'category').prefetch_related(
                'caps', 'creatives', 'landing_pages', 'tags'
            )
            if tenant:
                qs = qs.filter(tenant=tenant)
            return qs.get(id=offer_id)
        except Offer.DoesNotExist:
            return None

    @staticmethod
    def increment_offer_completions(offer_id: str):
        """Atomic increment — race condition নেই।"""
        Offer.objects.filter(id=offer_id).update(
            total_completions=F('total_completions') + 1
        )

    @staticmethod
    def get_offers_by_network(network_id: str) -> List[Offer]:
        return list(Offer.objects.filter(network_id=network_id, status='active'))

    @staticmethod
    def auto_expire_offers():
        """Expired অফার status update।"""
        now = timezone.now()
        count = Offer.objects.filter(
            status='active', expires_at__lt=now
        ).update(status='expired')
        return count


# ══════════════════════════════════════════════════════
# CLICK REPOSITORY
# ══════════════════════════════════════════════════════

class ClickRepository:

    @staticmethod
    def create_click(data: dict) -> Click:
        return Click.objects.create(**data)

    @staticmethod
    def get_by_token(token: str) -> Optional[Click]:
        try:
            return Click.objects.select_related('offer', 'user').get(click_token=token)
        except Click.DoesNotExist:
            return None

    @staticmethod
    def count_recent_clicks(ip: str, minutes: int = 60) -> int:
        since = timezone.now() - timedelta(minutes=minutes)
        return Click.objects.filter(ip_address=ip, created_at__gte=since).count()

    @staticmethod
    def count_user_clicks_today(user_id, offer_id) -> int:
        today = timezone.now().date()
        return Click.objects.filter(
            user_id=user_id,
            offer_id=offer_id,
            created_at__date=today
        ).count()

    @staticmethod
    def mark_as_fraud(click_id: str, reason: str):
        Click.objects.filter(id=click_id).update(
            is_fraud=True, fraud_reason=reason
        )

    @staticmethod
    def mark_as_converted(click_id: str):
        Click.objects.filter(id=click_id).update(converted=True)


# ══════════════════════════════════════════════════════
# CONVERSION REPOSITORY
# ══════════════════════════════════════════════════════

class ConversionRepository:

    @staticmethod
    @transaction.atomic
    def create_conversion(data: dict) -> Conversion:
        status_obj = ConversionStatus.objects.get(name='pending')
        data['status'] = status_obj
        return Conversion.objects.create(**data)

    @staticmethod
    def get_by_id(conversion_id: str) -> Optional[Conversion]:
        try:
            return Conversion.objects.select_related(
                'offer', 'user', 'click', 'status'
            ).get(id=conversion_id)
        except Conversion.DoesNotExist:
            return None

    @staticmethod
    def get_user_conversions(user_id, page=1, page_size=20) -> List[Conversion]:
        qs = Conversion.objects.filter(user_id=user_id).select_related('offer', 'status')
        start = (page - 1) * page_size
        return list(qs[start:start + page_size])

    @staticmethod
    @transaction.atomic
    def approve_conversion(conversion_id: str) -> bool:
        status_obj = ConversionStatus.objects.get(name='approved')
        updated = Conversion.objects.filter(
            id=conversion_id, status__name='pending'
        ).update(status=status_obj, approved_at=timezone.now())
        return updated > 0

    @staticmethod
    @transaction.atomic
    def reject_conversion(conversion_id: str, reason: str) -> bool:
        status_obj = ConversionStatus.objects.get(name='rejected')
        updated = Conversion.objects.filter(
            id=conversion_id, status__name='pending'
        ).update(status=status_obj, rejected_at=timezone.now(), reject_reason=reason)
        return updated > 0

    @staticmethod
    def check_duplicate(user_id, offer_id, fingerprint: str) -> bool:
        return DuplicateConversionFilter.objects.filter(
            user_id=user_id, offer_id=offer_id,
            fingerprint=fingerprint, is_blocked=True
        ).exists()

    @staticmethod
    def get_pending_postbacks(limit: int = 100) -> List[Conversion]:
        return list(
            Conversion.objects.filter(
                status__name='approved',
                postback_sent=False
            ).select_related('offer__network')[:limit]
        )

    @staticmethod
    def mark_postback_sent(conversion_id: str):
        Conversion.objects.filter(id=conversion_id).update(
            postback_sent=True, postback_at=timezone.now()
        )


# ══════════════════════════════════════════════════════
# FRAUD REPOSITORY
# ══════════════════════════════════════════════════════

class FraudRepository:

    @staticmethod
    def is_ip_blocked(ip: str, tenant=None) -> bool:
        cache_key = f'ip_blocked:{ip}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        now = timezone.now()
        qs = BlacklistedIP.objects.filter(ip_address=ip)
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if tenant:
            qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

        result = qs.exists()
        cache.set(cache_key, result, 300)
        return result

    @staticmethod
    def block_ip(ip: str, reason: str, tenant=None, permanent=False):
        BlacklistedIP.objects.get_or_create(
            ip_address=ip,
            defaults={
                'reason': reason,
                'tenant': tenant,
                'is_permanent': permanent,
                'source': 'auto',
            }
        )
        cache.delete(f'ip_blocked:{ip}')

    @staticmethod
    def get_user_risk_profile(user_id) -> Optional[UserRiskProfile]:
        try:
            return UserRiskProfile.objects.get(user_id=user_id)
        except UserRiskProfile.DoesNotExist:
            return None

    @staticmethod
    def update_risk_score(user_id, score_delta: float, flag=True):
        profile, _ = UserRiskProfile.objects.get_or_create(user_id=user_id)
        profile.risk_score = min(100.0, profile.risk_score + score_delta)
        if flag:
            profile.total_flags = F('total_flags') + 1
            profile.last_flagged_at = timezone.now()
        if profile.risk_score >= 90:
            profile.risk_level = 'critical'
        elif profile.risk_score >= 75:
            profile.risk_level = 'high'
        elif profile.risk_score >= 40:
            profile.risk_level = 'medium'
        profile.save()

    @staticmethod
    def log_fraud_attempt(rule_id, user_id, ip: str, description: str, evidence: dict):
        return FraudAttempt.objects.create(
            rule_id=rule_id,
            user_id=user_id,
            ip_address=ip,
            description=description,
            evidence=evidence,
        )

    @staticmethod
    def get_active_rules() -> List[FraudRule]:
        cache_key = 'fraud_rules:active'
        rules = cache.get(cache_key)
        if rules is None:
            rules = list(FraudRule.objects.filter(is_active=True).order_by('-severity'))
            cache.set(cache_key, rules, 600)
        return rules


# ══════════════════════════════════════════════════════
# WALLET / FINANCE REPOSITORY
# ══════════════════════════════════════════════════════

class WalletRepository:

    @staticmethod
    @transaction.atomic
    def credit_user(user_id, amount: Decimal, source: str, source_id: str, description: str):
        """User wallet-এ credit — atomic।"""
        from api.wallet.models import Wallet
        wallet = Wallet.objects.select_for_update().get(user_id=user_id)

        if wallet.is_locked:
            from .exceptions import WalletLockedException
            raise WalletLockedException()

        before = wallet.current_balance
        wallet.current_balance = F('current_balance') + amount
        wallet.total_earned    = F('total_earned')    + amount
        wallet.save(update_fields=['current_balance', 'total_earned', 'updated_at'])

        # Audit log
        WalletAudit.objects.create(
            user_id=user_id,
            transaction_type='credit',
            amount=amount,
            balance_before=before,
            balance_after=before + amount,
            reference_id=source_id,
            reference_type=source,
            note=description,
        )

        WalletTransaction.objects.create(
            user_id=user_id,
            tx_type='credit',
            amount=amount,
            description=description,
            source=source,
            source_id=source_id,
            balance_snapshot=before + amount,
        )

    @staticmethod
    @transaction.atomic
    def debit_user(user_id, amount: Decimal, source: str, source_id: str, description: str):
        """User wallet থেকে debit — insufficient balance check সহ।"""
        from api.wallet.models import Wallet
        from .exceptions import InsufficientBalanceException
        wallet = Wallet.objects.select_for_update().get(user_id=user_id)

        if wallet.is_locked:
            from .exceptions import WalletLockedException
            raise WalletLockedException()

        available = wallet.current_balance - wallet.frozen_balance
        if available < amount:
            raise InsufficientBalanceException()

        before = wallet.current_balance
        wallet.current_balance  = F('current_balance')  - amount
        wallet.total_withdrawn  = F('total_withdrawn') + amount
        wallet.save(update_fields=['current_balance', 'total_withdrawn', 'updated_at'])

        WalletAudit.objects.create(
            user_id=user_id,
            transaction_type='debit',
            amount=amount,
            balance_before=before,
            balance_after=before - amount,
            reference_id=source_id,
            reference_type=source,
            note=description,
        )

        WalletTransaction.objects.create(
            user_id=user_id,
            tx_type='debit',
            amount=amount,
            description=description,
            source=source,
            source_id=source_id,
            balance_snapshot=before - amount,
        )

    @staticmethod
    def get_withdrawal_requests(tenant=None, status=None, page=1, page_size=20):
        qs = WithdrawalRequest.objects.select_related('user', 'payment_method')
        if tenant:
            qs = qs.filter(tenant=tenant)
        if status:
            qs = qs.filter(status=status)
        start = (page - 1) * page_size
        return list(qs[start:start + page_size])

    @staticmethod
    def get_user_withdrawal_total_this_month(user_id) -> Decimal:
        now = timezone.now()
        result = WithdrawalRequest.objects.filter(
            user_id=user_id,
            status__in=['approved', 'processing', 'completed'],
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum('amount'))['total']
        return result or Decimal('0')


# ══════════════════════════════════════════════════════
# ANALYTICS REPOSITORY
# ══════════════════════════════════════════════════════

class AnalyticsRepository:

    @staticmethod
    def get_daily_stats(tenant=None, days: int = 30) -> List[DailyStat]:
        since = timezone.now().date() - timedelta(days=days)
        qs = DailyStat.objects.filter(date__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by('date'))

    @staticmethod
    @transaction.atomic
    def upsert_daily_stat(date, tenant=None, **kwargs):
        """Daily stat upsert — idempotent।"""
        obj, created = DailyStat.objects.get_or_create(
            date=date, tenant=tenant, defaults=kwargs
        )
        if not created:
            for field, value in kwargs.items():
                current = getattr(obj, field, 0)
                setattr(obj, field, current + value)
            obj.save()
        return obj

    @staticmethod
    def get_top_offers(tenant=None, days=7, limit=10) -> list:
        since = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            created_at__gte=since,
            status__name='approved'
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('offer__title', 'offer_id')
              .annotate(count=Count('id'), revenue=Sum('payout_amount'))
              .order_by('-revenue')[:limit]
        )

    @staticmethod
    def get_network_performance(days=7) -> list:
        since = timezone.now() - timedelta(days=days)
        return list(
            NetworkStat.objects.filter(date__gte=since.date())
                .values('network__name')
                .annotate(
                    total_clicks=Sum('clicks'),
                    total_conversions=Sum('conversions'),
                    total_revenue=Sum('revenue'),
                    avg_cvr=Avg('cvr'),
                )
                .order_by('-total_revenue')
        )


# ══════════════════════════════════════════════════════
# NOTIFICATION REPOSITORY
# ══════════════════════════════════════════════════════

class NotificationRepository:

    @staticmethod
    def create(user_id, notif_type: str, title: str, body: str,
               action_url: str = '', metadata: dict = None):
        return Notification.objects.create(
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            body=body,
            action_url=action_url,
            metadata=metadata or {},
        )

    @staticmethod
    def get_unread(user_id, limit=20) -> list:
        return list(
            Notification.objects.filter(
                user_id=user_id, is_read=False
            ).order_by('-created_at')[:limit]
        )

    @staticmethod
    def mark_all_read(user_id):
        Notification.objects.filter(user_id=user_id, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

    @staticmethod
    def unread_count(user_id) -> int:
        cache_key = f'notif_unread:{user_id}'
        count = cache.get(cache_key)
        if count is None:
            count = Notification.objects.filter(user_id=user_id, is_read=False).count()
            cache.set(cache_key, count, 60)
        return count


# ══════════════════════════════════════════════════════
# MASTER SWITCH REPOSITORY
# ══════════════════════════════════════════════════════

class FeatureFlagRepository:

    @staticmethod
    def is_enabled(feature: str, tenant=None) -> bool:
        cache_key = f'feature:{tenant}:{feature}'
        val = cache.get(cache_key)
        if val is not None:
            return val
        try:
            switch = MasterSwitch.objects.get(feature=feature, tenant=tenant)
            result = switch.is_enabled
        except MasterSwitch.DoesNotExist:
            result = True  # Default: enabled
        cache.set(cache_key, result, 120)
        return result

    @staticmethod
    def set_feature(feature: str, enabled: bool, tenant=None, user=None):
        obj, _ = MasterSwitch.objects.update_or_create(
            feature=feature, tenant=tenant,
            defaults={'is_enabled': enabled, 'toggled_by': user}
        )
        cache.delete(f'feature:{tenant}:{feature}')
        return obj
