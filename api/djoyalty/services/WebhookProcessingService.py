# api/djoyalty/services/WebhookProcessingService.py
"""
WebhookProcessingService -- Extracted webhook business logic।

AUDIT FIX (Architecture -- High): WebhookReceiverView in views.py contained
inline business logic in its _handle_*() methods:
  - Customer.objects.filter() ORM calls
  - PointsEngine.process_earn() calls
  - EarnRuleEngine calls
  - RedemptionService calls
  - WalletBridgeService calls

All of this is now in this dedicated service so that:
  1. views.py only handles HTTP concerns (parse JSON, verify signature, route)
  2. Business logic is unit-testable without a full HTTP request context
  3. "One task, one owner" architecture principle is maintained

WebhookReceiverView._handle_*() methods now call WebhookProcessingService
instead of calling services directly।
"""
import logging

logger = logging.getLogger(__name__)


class WebhookProcessingService:
    """
    Processes inbound webhook payloads from partner systems।
    Each handle_*() method is the single owner of its event's business logic।
    """

    @staticmethod
    def handle_payment(payload: dict) -> dict:
        """
        payment.completed -> trigger earn points flow for the customer।
        Extracts customer_id, amount, and reference_id from payload।
        """
        try:
            from .points.PointsEngine import PointsEngine
            from ..models.core import Customer

            customer_id = payload.get('customer_id')
            amount      = payload.get('amount', 0)
            reference   = payload.get('reference_id', '')

            if not customer_id or not amount:
                logger.info('handle_payment: skipped -- missing customer_id or amount')
                return {'status': 'skipped', 'reason': 'missing customer_id or amount'}

            customer = Customer.objects.filter(id=customer_id).first()
            if not customer:
                logger.warning('handle_payment: customer %s not found', customer_id)
                return {'status': 'skipped', 'reason': f'customer {customer_id} not found'}

            PointsEngine.process_earn(
                customer=customer,
                transaction_value=amount,
                source='webhook_payment',
                source_id=reference,
            )

            logger.info(
                'handle_payment: earn processed -- customer=%s amount=%s ref=%s',
                customer.code, amount, reference,
            )
            return {'status': 'points_processed', 'customer': customer.code}

        except Exception as e:
            logger.error('handle_payment error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_payment_failed(payload: dict) -> dict:
        """
        payment.failed -> release any reserved points for this transaction।
        Uses reference_id to find and release the PointsReservation।
        """
        try:
            from .points.PointsReservationService import PointsReservationService

            reference = payload.get('reference_id', '')
            if not reference:
                return {'status': 'skipped', 'reason': 'no reference_id'}

            PointsReservationService.release_by_reference(reference=reference)
            logger.info('handle_payment_failed: reservation released for ref=%s', reference)
            return {'status': 'reservation_released', 'reference': reference}

        except Exception as e:
            logger.error('handle_payment_failed error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_partner_earn(payload: dict) -> dict:
        """
        partner.points.earn -> coalition earn event from a partner merchant।
        Finds customer by code, processes coalition earn via EarnRuleEngine।
        """
        try:
            from .earn.EarnRuleEngine import EarnRuleEngine
            from ..models.core import Customer

            customer_code = payload.get('customer_code', '')
            partner_id    = payload.get('partner_id')
            amount        = payload.get('amount', 0)

            if not customer_code or not partner_id:
                return {'status': 'skipped', 'reason': 'missing customer_code or partner_id'}

            customer = Customer.objects.filter(code=customer_code).first()
            if not customer:
                logger.warning('handle_partner_earn: customer %s not found', customer_code)
                return {'status': 'skipped', 'reason': f'customer {customer_code} not found'}

            EarnRuleEngine.process_partner_earn(
                customer=customer,
                partner_id=partner_id,
                spend_amount=amount,
                metadata=payload,
            )

            logger.info(
                'handle_partner_earn: processed -- customer=%s partner=%s amount=%s',
                customer_code, partner_id, amount,
            )
            return {'status': 'partner_earn_processed', 'customer': customer_code}

        except Exception as e:
            logger.error('handle_partner_earn error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_partner_redeem(payload: dict) -> dict:
        """
        partner.points.redeem -> redemption confirmed by a partner system।
        Finalizes a pending redemption by reference_id।
        """
        try:
            from .redemption.RedemptionService import RedemptionService

            reference   = payload.get('reference_id', '')
            redeem_status = payload.get('status', '')

            if not reference:
                return {'status': 'skipped', 'reason': 'no reference_id'}

            if redeem_status != 'confirmed':
                logger.info('handle_partner_redeem: non-confirmed status=%s -- skipping', redeem_status)
                return {'status': 'skipped', 'reason': f'status={redeem_status} not confirmed'}

            RedemptionService.confirm_partner_redeem(reference=reference)
            logger.info('handle_partner_redeem: confirmed -- ref=%s', reference)
            return {'status': 'redeem_confirmed', 'reference': reference}

        except Exception as e:
            logger.error('handle_partner_redeem error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_cashout_completed(payload: dict) -> dict:
        """
        cashout.completed -> payment gateway confirmed the cashout was paid।
        Marks the CashoutRequest as completed via WalletBridgeService।
        """
        try:
            from .points.WalletBridgeService import WalletBridgeService

            reference   = payload.get('reference', '')
            payment_ref = payload.get('payment_reference', '')

            if not reference:
                return {'status': 'skipped', 'reason': 'no reference'}

            WalletBridgeService.confirm_cashout(
                reference=reference,
                payment_reference=payment_ref,
            )

            logger.info('handle_cashout_completed: confirmed -- ref=%s pay_ref=%s', reference, payment_ref)
            return {'status': 'cashout_confirmed', 'reference': reference}

        except Exception as e:
            logger.error('handle_cashout_completed error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_cashout_failed(payload: dict) -> dict:
        """
        cashout.failed -> payment gateway failed to process the cashout।
        Refunds the points via WalletBridgeService.fail_cashout()।
        """
        try:
            from .points.WalletBridgeService import WalletBridgeService

            reference = payload.get('reference', '')
            reason    = payload.get('reason', 'payment_failed')

            if not reference:
                return {'status': 'skipped', 'reason': 'no reference'}

            WalletBridgeService.fail_cashout(reference=reference, reason=reason)
            logger.info('handle_cashout_failed: refunded -- ref=%s reason=%s', reference, reason)
            return {'status': 'cashout_refunded', 'reference': reference}

        except Exception as e:
            logger.error('handle_cashout_failed error: %s', e)
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def handle_sms_status(payload: dict) -> dict:
        """
        sms.delivered -> delivery status update from SMS gateway।
        Logging only -- no business logic required।
        """
        sms_status = payload.get('status', 'unknown')
        message_id = payload.get('message_id', '')
        logger.info('handle_sms_status: status=%s message_id=%s', sms_status, message_id)
        return {'status': 'logged', 'sms_status': sms_status}

    @staticmethod
    def handle_push_status(payload: dict) -> dict:
        """
        push.delivered -> delivery status update from push notification gateway।
        Logging only -- no business logic required।
        """
        push_status = payload.get('status', 'unknown')
        device_id   = payload.get('device_id', '')
        logger.info('handle_push_status: status=%s device_id=%s', push_status, device_id)
        return {'status': 'logged', 'push_status': push_status}
