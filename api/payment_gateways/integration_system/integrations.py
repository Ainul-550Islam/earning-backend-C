# api/payment_gateways/integration_system/integrations.py
# Concrete integration classes for each external app

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class WalletIntegration:
    """Handles wallet balance changes for all payment events."""

    def on_deposit_completed(self, user, deposit, amount, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter
            WalletAdapter().credit_deposit(user, amount, deposit.gateway, deposit.reference_id)
        except Exception as e:
            logger.error(f'WalletIntegration.on_deposit_completed: {e}')

    def on_withdrawal_processed(self, user, payout_request, amount, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter
            WalletAdapter().debit_withdrawal(user, amount, payout_request.payout_method, payout_request.reference_id)
        except Exception as e:
            logger.error(f'WalletIntegration.on_withdrawal_processed: {e}')

    def on_conversion_approved(self, conversion, publisher, payout, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter
            WalletAdapter().credit_conversion(publisher, payout, conversion.offer.name if conversion.offer else 'Offer', conversion.conversion_id)
        except Exception as e:
            logger.error(f'WalletIntegration.on_conversion_approved: {e}')

    def on_conversion_reversed(self, conversion, publisher, amount, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter
            WalletAdapter().debit_withdrawal(publisher, amount, 'reversal', conversion.conversion_id)
        except Exception as e:
            logger.error(f'WalletIntegration.on_conversion_reversed: {e}')


class NotificationIntegration:
    """Handles all user notifications for payment events."""

    def on_deposit_completed(self, user, deposit, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter
            NotificationAdapter().send_deposit_completed(user, deposit)
        except Exception as e:
            logger.warning(f'NotificationIntegration.on_deposit_completed: {e}')

    def on_deposit_failed(self, user, deposit, error='', **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter
            NotificationAdapter()._fallback_email(user, 'Deposit Failed', f'Your deposit failed: {error}')
        except Exception as e:
            logger.warning(f'NotificationIntegration.on_deposit_failed: {e}')

    def on_withdrawal_processed(self, user, payout_request, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter
            NotificationAdapter().send_withdrawal_processed(user, payout_request)
        except Exception as e:
            logger.warning(f'NotificationIntegration.on_withdrawal_processed: {e}')

    def on_withdrawal_failed(self, user, payout_request, error='', **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter
            NotificationAdapter()._fallback_email(user, 'Withdrawal Failed', f'Your withdrawal could not be processed: {error}')
        except Exception as e:
            logger.warning(f'NotificationIntegration.on_withdrawal_failed: {e}')

    def on_fraud_detected(self, user, transaction, risk_score=0, reasons=None, **kwargs):
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
            send_mail(
                f'[FRAUD ALERT] Risk {risk_score}/100 — user {user.id}',
                f'User: {user.email}\nScore: {risk_score}\nReasons: {reasons}',
                settings.DEFAULT_FROM_EMAIL, [admin_email],
            )
        except Exception as e:
            logger.warning(f'NotificationIntegration.on_fraud_detected: {e}')


class FraudIntegration:
    """Handles fraud events — calls your existing fraud_detection app."""

    def on_fraud_detected(self, user, transaction, risk_score=0, reasons=None, **kwargs):
        try:
            from api.fraud_detection.models import FraudEvent
            FraudEvent.objects.create(user=user, risk_score=risk_score, reasons=reasons or [])
        except ImportError:
            pass  # api.fraud_detection not available
        except Exception as e:
            logger.warning(f'FraudIntegration: {e}')


class PostbackIntegration:
    """Fires outgoing publisher postbacks after conversions."""

    def on_conversion_approved(self, conversion, **kwargs):
        try:
            from api.payment_gateways.integrations_adapters.PostbackAdapter import PostbackAdapter
            PostbackAdapter().fire_publisher_postback(conversion)
        except Exception as e:
            logger.warning(f'PostbackIntegration: {e}')


class ReferralIntegration:
    """Credits referral commissions after deposits."""

    def on_deposit_completed(self, user, deposit, amount, **kwargs):
        try:
            from api.payment_gateways.referral.ReferralEngine import ReferralEngine
            ReferralEngine().credit_commission(user, amount, deposit.reference_id)
        except Exception as e:
            logger.debug(f'ReferralIntegration: {e}')


class GamificationIntegration:
    """Awards badges/achievements for payment milestones."""

    def on_deposit_completed(self, user, deposit, amount, **kwargs):
        try:
            from api.gamification.services import AchievementService
            AchievementService().check_deposit_milestones(user, amount)
        except ImportError:
            pass

    def on_conversion_approved(self, conversion, publisher, payout, **kwargs):
        try:
            from api.gamification.services import AchievementService
            AchievementService().check_conversion_milestones(publisher, payout)
        except ImportError:
            pass


class AnalyticsIntegration:
    """Sends payment events to your analytics app."""

    def track_event(self, **kwargs):
        try:
            from api.analytics.services import AnalyticsService
            AnalyticsService().track('payment_event', kwargs)
        except ImportError:
            pass
