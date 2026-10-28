# api/admin_panel/INTEGRATION_SYSTEM/bridge.py
"""
AdminBridge — High-level bridge API for admin_panel to control all apps.

Single point of truth: every admin control operation goes through AdminBridge.
It uses IntegrationHandler under the hood, adds caching, rate limiting, enrichment.

Usage:
    from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge

    # Ban a user — propagates to wallet, payout, fraud
    result = AdminBridge.user.ban(user_id=123, reason='Multi-account', actor=request.user)

    # Approve withdrawal — propagates to wallet credit
    result = AdminBridge.payout.approve(item_id=456, actor=request.user)

    # Get full system status
    status = AdminBridge.system.health()
"""
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from .integ_handler import IntegrationHandler
from .integ_signals import fire_event
from .integ_constants import INTEGRATION_EVENTS, TIMEOUTS

logger = logging.getLogger(__name__)


class UserBridge:
    """Bridge for all user management operations."""

    @staticmethod
    def ban(user_id: Any, reason: str = '', actor=None, freeze_wallet: bool = True) -> Dict:
        """Ban user + freeze wallet + cancel pending payouts."""
        result = IntegrationHandler.execute(
            app='users', action='ban',
            payload={'user_id': user_id, 'reason': reason},
            actor=actor,
        )
        if result.get('success') and freeze_wallet:
            IntegrationHandler.execute(
                app='wallet', action='freeze',
                payload={'user_id': user_id, 'reason': f'User banned: {reason}'},
            )
            # Cancel pending payouts
            try:
                from api.payout_queue.models import PayoutItem
                PayoutItem.objects.filter(user_id=user_id, status='QUEUED').update(status='CANCELLED')
            except Exception as e:
                logger.debug(f"[UserBridge.ban] Payout cancel failed: {e}")

        fire_event('admin_panel', INTEGRATION_EVENTS['USER_BANNED'], {
            'user_id': user_id, 'reason': reason, 'by': actor.username if actor else 'system'
        })
        return result

    @staticmethod
    def unban(user_id: Any, unfreeze_wallet: bool = True, actor=None) -> Dict:
        """Unban user and optionally unfreeze wallet."""
        result = IntegrationHandler.execute(
            app='users', action='unban',
            payload={'user_id': user_id},
            actor=actor,
        )
        if result.get('success') and unfreeze_wallet:
            try:
                from api.wallet.models import Wallet
                Wallet.objects.filter(user_id=user_id).update(is_locked=False)
            except Exception:
                pass
        fire_event('admin_panel', INTEGRATION_EVENTS['USER_UNBANNED'], {'user_id': user_id})
        return result

    @staticmethod
    def get_full_profile(user_id: Any) -> Dict:
        """Get complete user profile — cached."""
        cache_key = f'admin_panel:user_profile:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return {'success': True, 'data': cached, 'from_cache': True}

        data = {}
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            data['user'] = {'id': user.pk, 'username': user.username, 'email': user.email, 'is_active': user.is_active}
        except Exception as e:
            return {'success': False, 'error': str(e)}

        for model_source, model_name in [('wallet', 'Wallet'), ('kyc', 'KYC')]:
            try:
                result = IntegrationHandler.read(model_source, model_name, filters={'user_id': user_id}, limit=1)
                if result.get('success') and result.get('data'):
                    data[model_source] = result['data'][0]
            except Exception:
                pass

        cache.set(cache_key, data, TIMEOUTS['CACHE_TTL_SHORT'])
        return {'success': True, 'data': data}


class WalletBridge:
    """Bridge for wallet operations."""

    @staticmethod
    def adjust(user_id: Any, amount: float, reason: str, actor=None) -> Dict:
        result = IntegrationHandler.execute(
            app='wallet', action='adjust_balance',
            payload={'user_id': user_id, 'amount': amount, 'reason': reason},
            actor=actor,
        )
        if result.get('success') and amount > 0:
            fire_event('wallet', INTEGRATION_EVENTS['WALLET_CREDITED'],
                       {'user_id': user_id, 'amount': amount, 'reason': reason})
        return result

    @staticmethod
    def freeze(user_id: Any, reason: str = '', actor=None) -> Dict:
        result = IntegrationHandler.execute(
            app='wallet', action='freeze',
            payload={'user_id': user_id, 'reason': reason},
            actor=actor,
        )
        fire_event('wallet', INTEGRATION_EVENTS['WALLET_FROZEN'], {'user_id': user_id})
        return result

    @staticmethod
    def overview() -> Dict:
        cache_key = 'admin_panel:wallet_overview'
        cached = cache.get(cache_key)
        if cached:
            return {'success': True, 'data': cached}
        try:
            from api.wallet.models import Wallet
            from django.db.models import Sum, Count, Avg
            data = Wallet.objects.aggregate(
                total_wallets=Count('id'),
                total_balance=Sum('current_balance'),
                avg_balance=Avg('balance'),
                frozen=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_locked=True)),
            )
            data = {k: float(v) if v is not None else 0 for k, v in data.items()}
            cache.set(cache_key, data, 60)
            return {'success': True, 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class FraudBridge:
    """Bridge for fraud management."""

    @staticmethod
    def block_ip(ip: str, reason: str, actor=None) -> Dict:
        result = IntegrationHandler.execute(
            app='fraud_detection', action='block_ip',
            payload={'ip': ip, 'reason': reason},
            actor=actor, capability_required='block_ip',
        )
        fire_event('fraud_detection', INTEGRATION_EVENTS['IP_BLOCKED'], {'ip': ip, 'reason': reason})
        return result

    @staticmethod
    def get_fraud_score(user_id: Any, ip: str = '') -> Dict:
        """Calculate real-time risk score for a user."""
        score = 0
        signals = []
        try:
            from api.fraud_detection.models import FraudAttempt
            recent = FraudAttempt.objects.filter(
                user_id=user_id,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            if recent > 0:
                score += min(50, recent * 10)
                signals.append({'type': 'fraud_attempts', 'count': recent})
        except Exception:
            pass
        level = 'critical' if score >= 80 else 'high' if score >= 60 else 'medium' if score >= 30 else 'low'
        return {'success': True, 'data': {'score': score, 'level': level, 'signals': signals}}


class SystemBridge:
    """Bridge for system-level operations."""

    @staticmethod
    def health() -> Dict:
        """Get health status of all registered apps."""
        from .integ_registry import registry
        return {
            'success': True,
            'data': registry.health_check_all(),
            'overall': registry.get_system_status(),
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def fire_maintenance(message: str, duration_minutes: int = 60, actor=None) -> Dict:
        """Enable maintenance mode across the system."""
        try:
            from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
            result = MaintenanceModeService.enable(message=message, duration_minutes=duration_minutes)
            fire_event('admin_panel', INTEGRATION_EVENTS['MAINTENANCE_STARTED'],
                       {'message': message, 'duration': duration_minutes})
            return {'success': result, 'message': message}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def end_maintenance() -> Dict:
        try:
            from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
            result = MaintenanceModeService.disable()
            fire_event('admin_panel', INTEGRATION_EVENTS['MAINTENANCE_ENDED'], {})
            return {'success': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_kpis() -> Dict:
        """Real-time KPIs from all major apps."""
        cache_key = 'admin_panel:system_kpis'
        cached = cache.get(cache_key)
        if cached:
            return {'success': True, 'data': cached, 'from_cache': True}

        from django.contrib.auth import get_user_model
        User = get_user_model()
        today = timezone.now().date()
        kpis = {}

        # Users
        try:
            kpis['users'] = {
                'total': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'new_today': User.objects.filter(date_joined__date=today).count(),
            }
        except Exception:
            kpis['users'] = {}

        # Wallet
        try:
            from api.wallet.models import Wallet
            from django.db.models import Sum, Count
            kpis['wallet'] = Wallet.objects.aggregate(
                total_balance=Sum('current_balance'), total_wallets=Count('id')
            )
        except Exception:
            kpis['wallet'] = {}

        # Conversions
        try:
            from api.promotions.models import Conversion
            kpis['conversions'] = {
                'today': Conversion.objects.filter(created_at__date=today).count(),
                'pending': Conversion.objects.filter(status='QUEUED').count(),
            }
        except Exception:
            kpis['conversions'] = {}

        # Withdrawals
        try:
            from api.payout_queue.models import PayoutItem
            kpis['withdrawals'] = {
                'pending': PayoutItem.objects.filter(status='QUEUED').count(),
                'pending_amount': float(
                    PayoutItem.objects.filter(status='QUEUED').aggregate(t=Sum('gross_amount'))['t'] or 0
                ),
            }
        except Exception:
            kpis['withdrawals'] = {}

        cache.set(cache_key, kpis, 60)
        return {'success': True, 'data': kpis}


class AdminBridge:
    """
    Master bridge — single import point for all admin operations.

    Usage:
        from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge

        AdminBridge.user.ban(user_id=123)
        AdminBridge.wallet.adjust(user_id=123, amount=50)
        AdminBridge.fraud.block_ip('1.2.3.4', reason='Bot traffic')
        AdminBridge.system.health()
        AdminBridge.system.get_kpis()
    """
    user = UserBridge()
    wallet = WalletBridge()
    fraud = FraudBridge()
    system = SystemBridge()