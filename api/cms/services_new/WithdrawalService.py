# api/cms/services_new/WithdrawalService.py
"""Withdrawal / Payout Service — CMS owns this."""
import logging
from decimal import Decimal
from typing import Dict, Any, List
from django.db import transaction as db_transaction
from django.db.models import F, Sum, Count, Q
from django.core.cache import cache
logger = logging.getLogger(__name__)

MIN_WITHDRAWAL = {
    'paypal':   Decimal('1.00'),
    'payoneer': Decimal('1.00'),
    'usdt':     Decimal('25.00'),  # CPAlead USDT: $25 minimum (Jul 2025)
    'bitcoin':  Decimal('10.00'),
    'wire':     Decimal('100.00'),
    'ach':      Decimal('10.00'),
    'bank':     Decimal('50.00'),
}


class WithdrawalService:

    @staticmethod
    def get_user_methods(user) -> List[Dict]:
        from api.cms.models_new.withdrawal import PayoutMethod
        methods = PayoutMethod.objects.filter(user=user)
        return [{
            'id': m.id, 'method': m.method,
            'method_display': m.get_method_display(),
            'account_id': m.account_id[:6] + '****',
            'account_name': m.account_name,
            'is_default': m.is_default,
            'is_verified': m.is_verified,
        } for m in methods]

    @staticmethod
    def add_method(user, method: str, account_id: str,
                   account_name: str = '', set_default: bool = False) -> Dict:
        from api.cms.models_new.withdrawal import PayoutMethod
        if method not in dict(PayoutMethod._meta.get_field('method').choices):
            return {'success': False, 'error': 'Invalid payment method'}
        pm, created = PayoutMethod.objects.get_or_create(
            user=user, method=method, account_id=account_id,
            defaults={'account_name': account_name, 'is_default': set_default}
        )
        if not created and set_default:
            pm.is_default = True
            pm.save(update_fields=['is_default'])
        return {'success': True, 'method_id': pm.id, 'created': created}

    @staticmethod
    def request_withdrawal(user, method: str, account_id: str,
                            coins_amount: Decimal) -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest, PayoutMethod
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency

        # Get virtual balance with row lock
        try:
            with db_transaction.atomic():
             balance = UserVirtualBalance.objects.select_for_update().select_related('currency').get(user=user)
             vc = balance.currency
        except UserVirtualBalance.DoesNotExist:
            return {'success': False, 'error': 'No virtual balance found'}

        if balance.balance < coins_amount:
            return {'success': False, 'error': f'Insufficient balance ({float(balance.balance)} coins)'}

        # Convert coins → USD
        usd_amount = vc.virtual_to_usd(coins_amount)
        min_usd = MIN_WITHDRAWAL.get(method, Decimal('1.00'))
        if usd_amount < min_usd:
            return {
                'success': False,
                'error': f'Minimum withdrawal for {method} is ${min_usd} (you requested ${usd_amount:.2f})'
            }

        # Fee: 2% or $0 (configurable)
        fee = (usd_amount * Decimal('0.02')).quantize(Decimal('0.0001'))
        net = (usd_amount - fee).quantize(Decimal('0.0001'))

        # Deduct coins first
        if not balance.spend_coins(coins_amount):
            return {'success': False, 'error': 'Failed to deduct balance'}

        # Create request
        wr = WithdrawalRequest.objects.create(
            user=user, method=method, account_id=account_id,
            requested_coins=coins_amount,
            requested_usd=usd_amount, fee_usd=fee, net_usd=net,
            exchange_rate=vc.usd_ratio,
        )

        # Log transaction
        from api.cms.models_new.cpalead import VirtualTransaction
        VirtualTransaction.objects.create(
            user=user, tx_type='spend_withdrawal',
            amount=coins_amount, balance_after=balance.balance,
            usd_equivalent=usd_amount,
            description=f"Withdrawal request #{wr.id} via {method}",
            source_type='withdrawal', source_id=str(wr.id),
        )

        # ── Gateway dispatch (auto-approve fast-pay eligible amounts) ──
        try:
            from api.cms.payment_gateway_bridge import PaymentGatewayDispatcher
            # BDT conversion for bKash/Nagad (approx: 1 USD = 110 BDT)
            BDT_RATE = Decimal('110')
            amount_bdt = (net * BDT_RATE).quantize(Decimal('0.01'))
            gw_result = PaymentGatewayDispatcher.process(
                method=method,
                account_id=account_id,
                amount_usd=net,
                amount_bdt=amount_bdt,
                reference=f"WR{wr.id}",
            )
            if gw_result.success:
                wr.status = 'processing'
                wr.gateway_transaction_id = gw_result.transaction_id
                wr.save(update_fields=['status', 'gateway_transaction_id', 'updated_at'])
                logger.info(f"[Withdrawal] Gateway accepted: WR#{wr.id} txn={gw_result.transaction_id}")
            else:
                logger.warning(f"[Withdrawal] Gateway declined: WR#{wr.id} error={gw_result.error}")
        except Exception as gw_err:
            logger.error(f"[Withdrawal] Gateway dispatch failed: {gw_err}")

        # ── Push notification ─────────────────────────────────────
        try:
            from api.cms.notifications_push import CMSPushNotificationService
            CMSPushNotificationService.notify_withdrawal_update(user, float(net), 'approved')
        except Exception:
            pass

        # ── In-app notification ───────────────────────────────────
        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_withdrawal(user, float(net), status='requested')
        except Exception:
            pass

        return {
            'success': True,
            'request_id': wr.id,
            'coins_deducted': float(coins_amount),
            'usd_amount': float(usd_amount),
            'fee_usd': float(fee),
            'net_usd': float(net),
            'method': method,
            'status': 'pending',
            'message': f'Withdrawal request submitted. You will receive ${float(net):.2f} via {method}.',
        }

    @staticmethod
    def get_history(user, limit: int = 50) -> List[Dict]:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        reqs = WithdrawalRequest.objects.filter(user=user).order_by('-created_at')[:limit]
        return [{
            'id': r.id, 'uuid': str(r.uuid),
            'method': r.method, 'method_display': r.get_method_display(),
            'account_id': r.account_id[:6] + '****',
            'requested_coins': float(r.requested_coins),
            'requested_usd': float(r.requested_usd),
            'net_usd': float(r.net_usd),
            'status': r.status,
            'created_at': r.created_at.isoformat(),
            'paid_at': r.paid_at.isoformat() if r.paid_at else None,
        } for r in reqs]

    @staticmethod
    def get_withdrawal_stats(user) -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        from django.db.models import Sum, Count, Q
        stats = WithdrawalRequest.objects.filter(user=user).aggregate(
            total_requests=Count('id'),
            total_paid=Sum('net_usd', filter=Q(status='paid')),
            total_pending=Count('id', filter=Q(status__in=['pending', 'approved', 'processing'])),
        )
        return {
            'total_requests': stats['total_requests'] or 0,
            'total_paid_usd': float(stats['total_paid'] or 0),
            'pending_count': stats['total_pending'] or 0,
        }


class SiteConfigService:

    @staticmethod
    def get_config(domain: str = '') -> Dict:
        from api.cms.models_new.site_config import SiteConfig
        config = SiteConfig.get_active(domain)
        if not config:
            return {
                'site_name': 'Earning Site',
                'primary_color': '#007bff',
                'maintenance_mode': False,
                'features': {'offerwall': True, 'leaderboard': True, 'quiz': True},
            }
        return {
            'site_name': config.site_name,
            'site_tagline': config.site_tagline,
            'logo_url': config.logo_url,
            'favicon_url': config.favicon_url,
            'primary_color': config.primary_color,
            'secondary_color': config.secondary_color,
            'font_family': config.font_family,
            'maintenance_mode': config.maintenance_mode,
            'maintenance_message': config.maintenance_message,
            'contact_email': config.contact_email,
            'cookie_notice': config.cookie_notice_enabled,
            'google_analytics_id': config.google_analytics_id,
            'features': {
                'registration': config.registration_enabled,
                'referral': config.referral_enabled,
                'leaderboard': config.leaderboard_enabled,
                'quiz': config.quiz_enabled,
                'offerwall': config.offerwall_enabled,
                'blog': config.blog_enabled,
            },
            'min_withdrawal_coins': float(config.min_withdrawal_coins),
            'min_withdrawal_usd': float(config.min_withdrawal_usd),
        }

    @staticmethod
    def is_maintenance(ip: str = '', domain: str = '') -> bool:
        from api.cms.models_new.site_config import SiteConfig
        config = SiteConfig.get_active(domain)
        if not config or not config.maintenance_mode:
            return False
        allowed = config.get_maintenance_ips()
        if ip and allowed and ip in allowed:
            return False
        return True


class UserProfileService:

    @staticmethod
    def get_or_create(user):
        from api.cms.models_new.withdrawal import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_dashboard(user) -> Dict:
        from api.cms.models_new.withdrawal import UserProfile
        profile = UserProfileService.get_or_create(user)
        return profile.get_full_dashboard()

    @staticmethod
    def update_level(user) -> int:
        """Auto-calculate user level from total earnings."""
        from api.cms.models_new.withdrawal import UserProfile
        profile = UserProfileService.get_or_create(user)
        usd = float(profile.total_earned_usd)
        if usd >= 1000:   level = 7
        elif usd >= 500:  level = 6
        elif usd >= 200:  level = 5
        elif usd >= 100:  level = 4
        elif usd >= 50:   level = 3
        elif usd >= 10:   level = 2
        else:             level = 1
        if profile.level != level:
            profile.level = level
            profile.save(update_fields=['level', 'updated_at'])
        return level
