# api/admin_panel/logic.py
"""
Admin Panel Business Logic Layer.
Pure functions — no HTTP, no models, only business rules.
Keeps ViewSets thin. All complex decisions live here.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone
from datetime import timedelta


def should_auto_approve_withdrawal(amount: Decimal, user_id: Any, gateway: str) -> Tuple[bool, str]:
    """
    Business rule: should this withdrawal be auto-approved?
    Returns: (should_approve: bool, reason: str)
    """
    try:
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        auto_limit = Decimal(str(SystemConfigService.get('withdrawal_auto_approve_limit', default=100)))
        new_user_delay = int(SystemConfigService.get('new_user_withdrawal_delay_days', default=3))

        # Rule 1: Amount check
        if amount > auto_limit:
            return False, f'Amount {amount} exceeds auto-approve limit {auto_limit}'

        # Rule 2: New user check
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        days_since_joined = (timezone.now() - user.date_joined).days
        if days_since_joined < new_user_delay:
            return False, f'User account is only {days_since_joined} days old (minimum: {new_user_delay})'

        # Rule 3: Fraud check
        from api.fraud_detection.models import FraudAttempt
        recent_fraud = FraudAttempt.objects.filter(
            user_id=user_id,
            created_at__gte=timezone.now() - timedelta(days=7),
            fraud_score__gte=50,
        ).count()
        if recent_fraud > 0:
            return False, f'User has {recent_fraud} recent fraud flags'

        return True, 'Passed all auto-approve checks'
    except Exception as e:
        return False, f'Auto-approve check failed: {e}'


def calculate_user_fraud_score(user_id: Any, ip: str = '') -> Dict:
    """
    Calculate real-time risk score for a user.
    Returns: {score: int, level: str, signals: list}
    """
    score = 0
    signals = []

    # Fraud attempts
    try:
        from api.fraud_detection.models import FraudAttempt
        count = FraudAttempt.objects.filter(
            user_id=user_id,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        if count > 0:
            score += min(40, count * 10)
            signals.append({'signal': 'fraud_attempts', 'count': count, 'weight': min(40, count * 10)})
    except Exception:
        pass

    # VPN/Proxy check
    if ip:
        try:
            from api.proxy_intelligence.models import VPNDetectionLog
            vpn = VPNDetectionLog.objects.filter(ip_address=ip, is_vpn=True).exists()
            if vpn:
                score += 30
                signals.append({'signal': 'vpn_detected', 'ip': ip, 'weight': 30})
        except Exception:
            pass

    # Account age
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        days_old = (timezone.now() - user.date_joined).days
        if days_old < 1:
            score += 20
            signals.append({'signal': 'very_new_account', 'days': days_old, 'weight': 20})
        if not user.is_active:
            score = 100
            signals.append({'signal': 'banned_account', 'weight': 100})
    except Exception:
        pass

    score = min(100, score)
    level = 'critical' if score >= 80 else 'high' if score >= 60 else 'medium' if score >= 30 else 'low'
    return {'score': score, 'level': level, 'signals': signals, 'user_id': user_id}


def get_dashboard_kpi_snapshot() -> Dict:
    """Build complete dashboard KPI snapshot."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    today = timezone.now().date()
    last_24h = timezone.now() - timedelta(hours=24)
    last_7d = timezone.now() - timedelta(days=7)

    kpis = {}
    try:
        kpis['users'] = {
            'total': User.objects.count(),
            'active': User.objects.filter(is_active=True).count(),
            'new_today': User.objects.filter(date_joined__date=today).count(),
            'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
        }
    except Exception:
        kpis['users'] = {}

    try:
        from api.wallet.models import Wallet
        from django.db.models import Sum
        kpis['wallet'] = {
            'total_balance': float(Wallet.objects.aggregate(t=Sum('current_balance'))['t'] or 0),
            'frozen_wallets': Wallet.objects.filter(is_locked=True).count(),
        }
    except Exception:
        kpis['wallet'] = {}

    try:
        from api.payout_queue.models import PayoutItem
        from django.db.models import Sum, Count
        pending = PayoutItem.objects.filter(status='QUEUED').aggregate(
            count=Count('id'), amount=Sum('gross_amount')
        )
        kpis['withdrawals'] = {
            'pending_count': pending['count'] or 0,
            'pending_amount': float(pending['amount'] or 0),
        }
    except Exception:
        kpis['withdrawals'] = {}

    kpis['timestamp'] = timezone.now().isoformat()
    return kpis


def determine_maintenance_impact() -> Dict:
    """Calculate how many users will be affected by maintenance."""
    try:
        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        User = get_user_model()
        active_sessions = cache.get('admin:users_online', 0)
        total_active = User.objects.filter(is_active=True).count()
        return {
            'active_sessions': active_sessions,
            'total_users': total_active,
            'impact': 'high' if active_sessions > 100 else 'medium' if active_sessions > 10 else 'low',
        }
    except Exception:
        return {'impact': 'unknown'}