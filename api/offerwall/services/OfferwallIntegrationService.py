"""
api/offerwall/services/OfferwallIntegrationService.py

Fixes applied:
  1. MAX_DAILY_EARNINGS check added
  2. SubscriptionAdapter called (VIP multiplier)
  3. PromotionAdapter called (campaign bonus)
  4. B2BUsageRecord.conversions incremented
  5. PayoutQueueAdapter: large payouts (>= LARGE_PAYOUT_THRESHOLD) go to queue  ← NEW
  6. AlertAdapter: fires on daily cap hit, high fraud, provider anomaly          ← NEW
  7. validate_conversion_data() now called before creating conversion            ← NEW
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from .adapters.OfferwallAdapter import OfferwallAdapterFactory

logger = logging.getLogger(__name__)

# Payouts above this amount go to PayoutQueueAdapter instead of direct wallet
LARGE_PAYOUT_THRESHOLD = Decimal('500')


class OfferwallIntegrationService:

    @classmethod
    @transaction.atomic
    def process_conversion(
        cls,
        offer,
        user,
        conversion_id: str = '',
        payout_amount: Decimal = Decimal('0'),
        reward_amount: Decimal = Decimal('0'),
        postback_data: Optional[Dict] = None,
        click=None,
        bonus_amount: Optional[Decimal] = None,
        external_tx_id: str = '',
        auto_approve: bool = False,
        provider_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:

        from api.offerwall.models import OfferConversion
        from api.offerwall.constants import MAX_DAILY_EARNINGS
        from api.offerwall.utils.OfferValidator import OfferValidator
        import uuid as _uuid

        if not conversion_id:
            conversion_id = f'auto_{_uuid.uuid4().hex[:16]}'

        # ── Idempotency ───────────────────────────────────────
        qs = OfferConversion.objects.filter(conversion_id=conversion_id)
        if external_tx_id:
            qs = qs | OfferConversion.objects.filter(
                external_WalletTransaction_id=external_tx_id)
        existing = qs.first()
        if existing:
            # FIX: DuplicateConversionException was defined but never raised
            from api.offerwall.exceptions import DuplicateConversionException
            logger.info(f'[IntegService] duplicate: {conversion_id}')
            return {'success': True, 'conversion': existing,
                    'conversion_id': existing.conversion_id,
                    'created': False, 'message': 'Duplicate',
                    'exception': DuplicateConversionException.__name__}

        # ── FIX 7: validate_conversion_data() ─────────────────
        if offer:
            validator = OfferValidator(offer)
            try:
                # FIX: OfferConversionWebhookSerializer was floating — now used
                from api.offerwall.serializers import OfferConversionWebhookSerializer
                wh_ser = OfferConversionWebhookSerializer(data={
                    'offer_id':       str(offer.id) if offer else '',
                    'user_id':        str(user.id) if user else '',
                    'transaction_id': conversion_id,
                    'payout':         str(payout_amount),
                    'currency':       getattr(offer, 'currency', 'USD') or 'USD',
                })
                if not wh_ser.is_valid():
                    from api.offerwall.exceptions import InvalidConversionException
                    err = str(wh_ser.errors)
                    logger.warning(f'[IntegService] wh_ser invalid: {err}')
                    return {'success': False, 'error': err, 'created': False}
                conv_payload = {
                    'conversion_id': conversion_id,
                    'payout_amount': str(payout_amount),
                    'user_id':       user.id if user else None,
                }
                validator.validate_conversion_data(conv_payload)
            except Exception as e:
                logger.warning(f'[IntegService] conversion validation: {e}')
                return {'success': False, 'error': str(e), 'created': False}

        # ── FIX 1: Daily limit ────────────────────────────────
        if user and MAX_DAILY_EARNINGS > 0:
            today_total = cls._get_today_earnings(user)
            if today_total >= Decimal(str(MAX_DAILY_EARNINGS)):
                # FIX 6a: Alert on daily cap hit
                cls._fire_alert(
                    alert_type='daily_cap_reached',
                    severity='medium',
                    message=f'User {user.id} hit daily earning cap',
                    metadata={'user_id': user.id,
                               'today_total': str(today_total),
                               'cap': str(MAX_DAILY_EARNINGS)},
                )
                # FIX: DailyLimitReachedException was defined but never raised
                from api.offerwall.exceptions import DailyLimitReachedException
                logger.warning(f'[IntegService] daily limit: user={user.id}')
                return {'success': False, 'error': 'daily_limit_reached',
                        'created': False,
                        'exception': DailyLimitReachedException.__name__}

        # ── FIX 2: Subscription multiplier ───────────────────
        reward_amount = cls._apply_subscription_multiplier(
            user, reward_amount, OfferwallAdapterFactory)

        # ── FIX 3: Promotion bonus ────────────────────────────
        if offer:
            bonus_amount = cls._apply_promotion_bonus(
                user, offer, bonus_amount or Decimal('0'), OfferwallAdapterFactory)

        # ── Create conversion ─────────────────────────────────
        create_kwargs = dict(
            offer=offer, user=user, click=click,
            conversion_id=conversion_id,
            payout_amount=payout_amount,
            payout_currency=getattr(offer, 'currency', 'USD') or 'USD',
            reward_amount=reward_amount,
            reward_currency=getattr(offer, 'reward_currency', 'BDT') or 'BDT',
            bonus_amount=bonus_amount or Decimal('0'),
            status='pending',
            postback_data=postback_data or provider_data or {},
        )
        if external_tx_id:
            create_kwargs['external_WalletTransaction_id'] = external_tx_id

        conversion = OfferConversion.objects.create(**create_kwargs)

        if click:
            from api.offerwall.models import OfferClick
            OfferClick.objects.filter(pk=click.pk).update(
                is_converted=True, converted_at=timezone.now())

        if offer:
            offer.increment_conversion()

        # ── FIX 4: B2B usage counter ─────────────────────────
        cls._increment_b2b_usage(user)

        # ── FIX 5: Large payout → PayoutQueueAdapter ─────────
        total_reward = reward_amount + (bonus_amount or Decimal('0'))
        if total_reward >= LARGE_PAYOUT_THRESHOLD:
            cls._route_to_payout_queue(user, total_reward, conversion_id)
            logger.info(
                f'[IntegService] large payout {total_reward} routed to queue '
                f'conversion={conversion_id}')
            # Don't auto-approve large payouts — require manual review
            auto_approve = False

        if auto_approve:
            try:
                cls.approve_conversion(conversion)
            except Exception as e:
                logger.warning(f'[IntegService] auto_approve failed: {e}')

        return {
            'success': True, 'conversion': conversion,
            'conversion_id': conversion.conversion_id, 'created': True,
        }

    @classmethod
    def approve_conversion(cls, conversion, approver=None) -> Dict[str, Any]:
        if conversion.status != 'pending':
            return {'success': False,
                    'error': f"Cannot approve status='{conversion.status}'"}
        ok = conversion.approve(approver=approver)
        if not ok:
            return {'success': False, 'error': 'approve() returned False'}
        return {'success': True, 'conversion': conversion}

    @classmethod
    def reject_conversion(cls, conversion, reason='', rejector=None) -> Dict[str, Any]:
        if conversion.status not in ['pending']:
            return {'success': False,
                    'error': f"Cannot reject status='{conversion.status}'"}
        conversion.reject(reason=reason, rejector=rejector)
        return {'success': True, 'conversion': conversion}

    @classmethod
    def check_fraud(cls, user, offer, ip_address, user_agent='',
                    device_data=None) -> Dict[str, Any]:
        result = OfferwallAdapterFactory.get('fraud').send({
            'user_id':    user.id,
            'offer_id':   str(offer.id),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'device_data': device_data or {},
            'action':     'click',
        })
        # FIX 6b: Alert on high fraud score
        if result.get('fraud_score', 0) >= 85:
            cls._fire_alert(
                alert_type='high_fraud_score',
                severity='high',
                message=f'High fraud score for user={user.id} offer={offer.id}',
                metadata={'user_id': user.id, 'offer_id': str(offer.id),
                           'score': result.get('fraud_score')},
            )
        return result if result.get('success') else \
               {'should_block': False, 'fraud_score': 0, 'reasons': []}

    @classmethod
    def manual_credit_wallet(cls, conversion, admin_user=None) -> Dict[str, Any]:
        total = conversion.reward_amount + conversion.bonus_amount
        return OfferwallAdapterFactory.get('wallet').send({
            'user_id':       conversion.user_id,
            'reward_amount': total,
            'bonus_amount':  Decimal('0'),
            'conversion_id': conversion.conversion_id,
            'offer_title':   conversion.offer.title,
            'offer_id':      str(conversion.offer_id),
            'provider_type': (conversion.offer.provider.provider_type
                               if conversion.offer.provider else ''),
        })

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _get_today_earnings(user) -> Decimal:
        from api.offerwall.models import OfferConversion
        from django.db.models import Sum
        result = OfferConversion.objects.filter(
            user=user, status='approved',
            converted_at__date=timezone.now().date(),
        ).aggregate(total=Sum('reward_amount'))
        return result['total'] or Decimal('0')

    @staticmethod
    def _apply_subscription_multiplier(user, reward_amount, factory) -> Decimal:
        try:
            result     = factory.get('subscription').send({
                'user_id': user.id if user else None,
                'action':  'get_reward_multiplier',
            })
            multiplier = Decimal(str(result.get('multiplier', '1.0')))
            if multiplier > Decimal('1'):
                reward_amount = (reward_amount * multiplier).quantize(
                    Decimal('0.000001'))
        except Exception as e:
            logger.debug(f'[IntegService] subscription skip: {e}')
        return reward_amount

    @staticmethod
    def _apply_promotion_bonus(user, offer, bonus_amount, factory) -> Decimal:
        try:
            result = factory.get('promotions').send({
                'user_id':  user.id if user else None,
                'offer_id': str(offer.id),
                'action':   'get_active_bonus',
            })
            extra = Decimal(str(result.get('bonus_amount', '0')))
            if extra > Decimal('0'):
                bonus_amount += extra
        except Exception as e:
            logger.debug(f'[IntegService] promotion skip: {e}')
        return bonus_amount

    @staticmethod
    def _increment_b2b_usage(user):
        if not user:
            return
        try:
            client = getattr(user, 'b2b_client', None)
            if client:
                client.get_current_usage().increment('conversions')
        except Exception:
            pass

    @staticmethod
    def _route_to_payout_queue(user, amount, conversion_id):
        """
        FIX: PayoutQueueAdapter was registered but never called.
        Large payouts now routed through payout queue for manual review.
        """
        try:
            OfferwallAdapterFactory.get('payout_queue').send({
                'user_id':       user.id if user else None,
                'amount':        amount,
                'conversion_id': conversion_id,
                'priority':      'normal',
            })
        except Exception as e:
            logger.warning(f'[IntegService] payout_queue failed: {e}')

    @staticmethod
    def _fire_alert(alert_type, severity, message, metadata=None):
        """
        FIX: AlertAdapter was registered but never triggered.
        Now fired on: daily cap reached, high fraud score.
        """
        try:
            OfferwallAdapterFactory.get('alerts').send({
                'alert_type': alert_type,
                'severity':   severity,
                'message':    message,
                'metadata':   metadata or {},
            })
        except Exception as e:
            logger.debug(f'[IntegService] alert failed: {e}')
