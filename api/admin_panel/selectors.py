# api/admin_panel/selectors.py
"""
Admin Panel Selectors — Clean Architecture read-only query layer.
ALL DB reads for admin_panel go through here.
No writes, no side effects — pure SELECT functions.
Other modules call these instead of writing raw ORM queries.

Principle: "Selector = thin query, no business logic"
Reference pattern from kyc/selectors.py (world #1 style).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, QuerySet
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


# ===========================================================================
# USER SELECTORS
# ===========================================================================

def get_user_by_id(user_id: Any) -> Optional[User]:
    try:
        return User.objects.select_related().get(pk=user_id)
    except User.DoesNotExist:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    try:
        return User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return None


def get_user_by_email(email: str) -> Optional[User]:
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None


def get_users_list(
    is_active: Optional[bool] = None,
    is_staff: Optional[bool] = None,
    search: str = '',
    date_from=None,
    date_to=None,
    order_by: str = '-date_joined',
    limit: int = 100,
    offset: int = 0,
) -> QuerySet:
    qs = User.objects.all()
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if is_staff is not None:
        qs = qs.filter(is_staff=is_staff)
    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    if date_from:
        qs = qs.filter(date_joined__date__gte=date_from)
    if date_to:
        qs = qs.filter(date_joined__date__lte=date_to)
    return qs.order_by(order_by)[offset:offset + limit]


def get_user_count(is_active: Optional[bool] = None) -> int:
    qs = User.objects.all()
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs.count()


def get_new_users_count(days: int = 7) -> int:
    cutoff = timezone.now() - timedelta(days=days)
    return User.objects.filter(date_joined__gte=cutoff).count()


def get_users_registration_trend(days: int = 30) -> List[Dict]:
    from django.db.models.functions import TruncDate
    cutoff = timezone.now() - timedelta(days=days)
    return list(
        User.objects.filter(date_joined__gte=cutoff)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )


def get_suspicious_users(limit: int = 100) -> QuerySet:
    """Users with fraud flags, multiple failed logins, etc."""
    try:
        from api.fraud_detection.models import FraudAttempt
        last_7d = timezone.now() - timedelta(days=7)
        fraud_user_ids = FraudAttempt.objects.filter(
            created_at__gte=last_7d,
            fraud_score__gte=60
        ).values_list('user_id', flat=True).distinct()
        return User.objects.filter(pk__in=fraud_user_ids).order_by('-date_joined')[:limit]
    except Exception:
        return User.objects.none()


# ===========================================================================
# WALLET SELECTORS
# ===========================================================================

def get_wallet_by_user(user_id: Any):
    try:
        from api.wallet.models import Wallet
        return Wallet.objects.get(user_id=user_id)
    except Exception:
        return None


def get_wallet_overview() -> Dict:
    try:
        from api.wallet.models import Wallet
        return Wallet.objects.aggregate(
            total_wallets=Count('id'),
            total_balance=Sum('current_balance'),
            avg_balance=Avg('balance'),
            max_balance=Max('balance'),
            frozen_count=Count('id', filter=Q(is_locked=True)),
            active_count=Count('id', filter=Q(balance__gt=0, is_locked=False)),
        )
    except Exception:
        return {}


def get_top_earners(limit: int = 20) -> List[Dict]:
    try:
        from api.wallet.models import Wallet
        return list(
            Wallet.objects.select_related('user')
            .filter(is_locked=False)
            .values('user_id', 'user__username', 'balance')
            .order_by('-balance')[:limit]
        )
    except Exception:
        return []


def get_frozen_wallets(limit: int = 100) -> QuerySet:
    try:
        from api.wallet.models import Wallet
        return Wallet.objects.filter(is_locked=True).select_related('user').order_by('-balance')[:limit]
    except Exception:
        return []


def get_wallet_transactions(user_id: Any, limit: int = 50, tx_type: str = '') -> List[Dict]:
    try:
        from api.wallet.models import WalletTransaction
        qs = WalletTransaction.objects.filter(wallet__user_id=user_id)
        if tx_type:
            qs = qs.filter(transaction_type=tx_type)
        return list(qs.values(
            'id', 'amount', 'transaction_type', 'description',
            'status', 'reference', 'created_at'
        ).order_by('-created_at')[:limit])
    except Exception:
        return []


# ===========================================================================
# PAYOUT SELECTORS
# ===========================================================================

def get_pending_payouts(limit: int = 100, gateway: str = '') -> QuerySet:
    try:
        from api.payout_queue.models import PayoutItem
        qs = PayoutItem.objects.filter(status='QUEUED').select_related('user')
        if gateway:
            qs = qs.filter(gateway=gateway)
        return qs.order_by('created_at')[:limit]
    except Exception:
        return []


def get_payout_stats(days: int = 7) -> Dict:
    try:
        from api.payout_queue.models import PayoutItem
        cutoff = timezone.now() - timedelta(days=days)
        qs = PayoutItem.objects.filter(created_at__gte=cutoff)
        return qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='QUEUED')),
            approved=Count('id', filter=Q(status='SUCCESS')),
            paid=Count('id', filter=Q(status='SUCCESS')),
            rejected=Count('id', filter=Q(status='FAILED')),
            total_paid_amount=Sum('amount', filter=Q(status='SUCCESS')),
            total_pending_amount=Sum('amount', filter=Q(status='QUEUED')),
        )
    except Exception:
        return {}


def get_payout_gateway_breakdown(days: int = 30) -> List[Dict]:
    try:
        from api.payout_queue.models import PayoutItem
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            PayoutItem.objects.filter(created_at__gte=cutoff, status='SUCCESS')
            .values('gateway')
            .annotate(count=Count('id'), total=Sum('gross_amount'))
            .order_by('-total')
        )
    except Exception:
        return []


# ===========================================================================
# FRAUD SELECTORS
# ===========================================================================

def get_fraud_stats(days: int = 7) -> Dict:
    try:
        from api.fraud_detection.models import FraudAttempt, FraudRule
        cutoff = timezone.now() - timedelta(days=days)
        qs = FraudAttempt.objects.filter(created_at__gte=cutoff)
        return {
            'total': qs.count(),
            'critical': qs.filter(fraud_score__gte=90).count(),
            'high': qs.filter(fraud_score__gte=70, fraud_score__lt=90).count(),
            'by_type': list(qs.values('attempt_type').annotate(count=Count('id')).order_by('-count')[:10]),
            'top_attempt_types': list(qs.values('attempt_type').annotate(count=Count('id')).order_by('-count')[:10]),
            'active_rules': FraudRule.objects.filter(is_active=True).count(),
        }
    except Exception:
        return {}


def get_blocked_ips(limit: int = 200) -> List[Dict]:
    try:
        from api.fraud_detection.models import BlockedIP
        return list(BlockedIP.objects.values(
            'id', 'ip_address', 'reason', 'is_permanent', 'created_at'
        ).order_by('-created_at')[:limit])
    except Exception:
        return []


def get_fraud_attempts(
    user_id: Any = None,
    ip: str = '',
    min_score: int = 0,
    days: int = 7,
    limit: int = 100,
) -> List[Dict]:
    try:
        from api.fraud_detection.models import FraudAttempt
        cutoff = timezone.now() - timedelta(days=days)
        qs = FraudAttempt.objects.filter(created_at__gte=cutoff, fraud_score__gte=min_score)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if ip:
            qs = qs.filter(ip_address=ip)
        return list(qs.values(
            'id', 'user_id', 'ip_address', 'attempt_type', 'fraud_score', 'created_at'
        ).order_by('-fraud_score')[:limit])
    except Exception:
        return []


# ===========================================================================
# OFFER / PROMOTIONS SELECTORS
# ===========================================================================

def get_active_offers(limit: int = 100, category: str = '') -> List[Dict]:
    try:
        from api.offer_inventory.models import Offer
        qs = Offer.objects.filter(is_active=True)
        if category:
            qs = qs.filter(category__name=category)
        return list(qs.values(
            'id', 'title', 'offer_type', 'payout', 'currency',
            'total_conversions', 'is_active', 'created_at'
        ).order_by('-total_conversions')[:limit])
    except Exception:
        return []


def get_offer_stats(offer_id: Any) -> Dict:
    try:
        from api.promotions.models import TaskSubmission
        qs = TaskSubmission.objects.filter(campaign_id=offer_id)
        return qs.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='SUCCESS')),
            pending=Count('id', filter=Q(status='QUEUED')),
            rejected=Count('id', filter=Q(status='FAILED')),
            total_payout=Sum('reward_amount', filter=Q(status='SUCCESS')),
        )
    except Exception:
        return {}


def get_top_campaigns(days: int = 7, limit: int = 20) -> List[Dict]:
    try:
        from api.promotions.models import Campaign
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            Campaign.objects.filter(status='active', created_at__gte=cutoff)
            .values('id', 'title', 'status', 'payout_type')
            .order_by('-created_at')[:limit]
        )
    except Exception:
        return []


# ===========================================================================
# ADMIN_PANEL OWN MODEL SELECTORS
# ===========================================================================

def get_system_config(key: str, default: Any = None) -> Any:
    try:
        from api.admin_panel.models.config import SystemConfig
        obj = SystemConfig.objects.get(key=key)
        return obj.get_typed_value()
    except Exception:
        return default


def get_system_configs_by_group(group: str) -> Dict[str, Any]:
    try:
        from api.admin_panel.models.config import SystemConfig
        return {
            obj.key: obj.get_typed_value()
            for obj in SystemConfig.objects.filter(group=group)
        }
    except Exception:
        return {}


def get_feature_flag(flag_key: str) -> Optional[bool]:
    try:
        from api.admin_panel.models.config import FeatureFlag
        flag = FeatureFlag.objects.get(flag_key=flag_key)
        return flag.is_enabled
    except Exception:
        return None


def get_all_feature_flags() -> Dict[str, bool]:
    try:
        from api.admin_panel.models.config import FeatureFlag
        return {f.flag_key: f.is_enabled for f in FeatureFlag.objects.all()}
    except Exception:
        return {}


def get_active_maintenance_window():
    try:
        from api.admin_panel.models.config import MaintenanceWindow
        now = timezone.now()
        return MaintenanceWindow.objects.filter(
            is_active=True, start_at__lte=now, end_at__gte=now
        ).first()
    except Exception:
        return None


def get_recent_admin_activity(actor=None, days: int = 1, limit: int = 50) -> List[Dict]:
    try:
        from api.admin_panel.models.activity import AdminActivity
        cutoff = timezone.now() - timedelta(days=days)
        qs = AdminActivity.objects.filter(created_at__gte=cutoff).select_related('actor')
        if actor:
            qs = qs.filter(actor=actor)
        return list(qs.values(
            'id', 'actor__username', 'action', 'model_name',
            'status', 'ip', 'created_at'
        ).order_by('-created_at')[:limit])
    except Exception:
        return []


def get_admin_sessions_active() -> List[Dict]:
    try:
        from api.admin_panel.models.activity import AdminSession
        return list(
            AdminSession.objects.filter(is_active=True)
            .select_related('user')
            .values('id', 'user__username', 'ip', 'user_agent', 'started_at', 'last_seen')
            .order_by('-last_seen')[:50]
        )
    except Exception:
        return []


def get_unread_insights(limit: int = 20) -> List[Dict]:
    try:
        from api.admin_panel.models.reports import AdminInsight
        return list(
            AdminInsight.objects.filter(is_read=False, is_dismissed=False)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .values('id', 'type', 'title', 'body', 'priority', 'created_at')
            .order_by('-priority', '-created_at')[:limit]
        )
    except Exception:
        return []


def get_pending_reports(limit: int = 20) -> List[Dict]:
    try:
        from api.admin_panel.models.reports import ReportExport
        return list(
            ReportExport.objects.filter(status__in=['queued', 'generating'])
            .values('id', 'report__name', 'format', 'status', 'created_at')
            .order_by('created_at')[:limit]
        )
    except Exception:
        return []


# ===========================================================================
# KYC SELECTORS
# ===========================================================================

def get_pending_kyc(limit: int = 100) -> List[Dict]:
    try:
        from api.kyc.models import KYC
        return list(
            KYC.objects.filter(status='QUEUED')
            .select_related('user')
            .values('id', 'user__username', 'user__email', 'document_type', 'created_at')
            .order_by('created_at')[:limit]
        )
    except Exception:
        return []


def get_kyc_by_user(user_id: Any):
    try:
        from api.kyc.models import KYC
        return KYC.objects.filter(user_id=user_id).select_related('user').first()
    except Exception:
        return None


def get_kyc_stats() -> Dict:
    try:
        from api.kyc.models import KYC
        return KYC.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='QUEUED')),
            approved=Count('id', filter=Q(status='SUCCESS')),
            rejected=Count('id', filter=Q(status='FAILED')),
        )
    except Exception:
        return {}


# ===========================================================================
# SMARTLINK SELECTORS
# ===========================================================================

def get_smartlink_stats(smartlink_id: Any = None, days: int = 7) -> Dict:
    try:
        from api.smartlink.models.click import Click
        cutoff = timezone.now() - timedelta(days=days)
        qs = Click.objects.filter(created_at__gte=cutoff)
        if smartlink_id:
            qs = qs.filter(smartlink_id=smartlink_id)
        return qs.aggregate(
            total_clicks=Count('id'),
            unique_clicks=Count('ip', distinct=True),
            conversions=Count('id', filter=Q(converted=True)),
        )
    except Exception:
        return {}


# ===========================================================================
# NOTIFICATION SELECTORS
# ===========================================================================

def get_active_site_notifications() -> List[Dict]:
    try:
        from api.admin_panel.models.core import SiteNotification
        now = timezone.now()
        return list(
            SiteNotification.objects.filter(
                is_active=True, start_date__lte=now
            ).filter(Q(end_date__gte=now) | Q(end_date__isnull=True))
            .values('id', 'title', 'message', 'notification_type', 'priority')
            .order_by('-priority')[:10]
        )
    except Exception:
        return []


# ===========================================================================
# ANALYTICS SELECTORS
# ===========================================================================

def get_daily_revenue(days: int = 30) -> List[Dict]:
    try:
        from api.analytics.models import RevenueAnalytics
        from django.db.models.functions import TruncDate
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            RevenueAnalytics.objects.filter(created_at__gte=cutoff)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Sum('gross_amount'))
            .order_by('day')
        )
    except Exception:
        return []


def get_platform_summary() -> Dict:
    """Single comprehensive platform summary for dashboard."""
    today = timezone.now().date()
    last_7d = timezone.now() - timedelta(days=7)
    summary = {}
    try:
        summary['users'] = {
            'total': User.objects.count(),
            'active': User.objects.filter(is_active=True).count(),
            'new_today': User.objects.filter(date_joined__date=today).count(),
            'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
        }
    except Exception:
        summary['users'] = {}
    try:
        from api.wallet.models import Wallet
        agg = Wallet.objects.aggregate(total=Sum('current_balance'), frozen=Count('id', filter=Q(is_locked=True)))
        summary['wallet'] = {'total_balance': float(agg['total'] or 0), 'frozen_wallets': agg['frozen'] or 0}
    except Exception:
        summary['wallet'] = {}
    try:
        from api.payout_queue.models import PayoutItem
        pa = PayoutItem.objects.filter(status='QUEUED').aggregate(count=Count('id'), amount=Sum('gross_amount'))
        summary['pending_payouts'] = {'count': pa['count'] or 0, 'amount': float(pa['amount'] or 0)}
    except Exception:
        summary['pending_payouts'] = {}
    summary['timestamp'] = timezone.now().isoformat()
    return summary