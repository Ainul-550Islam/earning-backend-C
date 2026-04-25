# api/payment_gateways/integrations_adapters/NotificationAdapter.py
# Bridge between payment_gateways and api.notifications

import logging

logger = logging.getLogger(__name__)


class NotificationAdapter:
    """
    Sends notifications via your existing api.notifications app.
    Falls back to payment_gateways EmailNotifier if unavailable.
    """

    def send_deposit_completed(self, user, deposit):
        """Notify user of successful deposit."""
        try:
            from api.notifications.services import NotificationService
            NotificationService().send(
                user=user,
                template='payment_deposit_completed',
                context={
                    'amount':       str(deposit.net_amount),
                    'currency':     deposit.currency,
                    'gateway':      deposit.gateway,
                    'reference_id': deposit.reference_id,
                }
            )
            return True
        except ImportError:
            return self._fallback_email(user, 'Deposit Completed',
                f'Your deposit of {deposit.net_amount} {deposit.currency} has been credited.')

    def send_withdrawal_processed(self, user, payout):
        """Notify user that their withdrawal was processed."""
        try:
            from api.notifications.services import NotificationService
            NotificationService().send(
                user=user,
                template='payment_withdrawal_processed',
                context={
                    'amount':      str(payout.net_amount),
                    'method':      payout.payout_method,
                    'reference_id':payout.reference_id,
                }
            )
            return True
        except ImportError:
            return self._fallback_email(user, 'Withdrawal Processed',
                f'Your withdrawal of {payout.net_amount} has been processed.')

    def send_conversion_credited(self, user, conversion):
        """Notify publisher of new conversion earnings."""
        try:
            from api.notifications.services import NotificationService
            NotificationService().send(
                user=user,
                template='payment_conversion_earned',
                context={
                    'payout':   str(conversion.payout),
                    'offer':    conversion.offer.name if conversion.offer else '',
                    'currency': conversion.currency,
                }
            )
            return True
        except ImportError:
            return self._fallback_email(user, 'New Conversion Earned',
                f'You earned {conversion.payout} {conversion.currency} from a conversion.')

    def _fallback_email(self, user, subject: str, message: str) -> bool:
        """Fallback: direct email if notifications app unavailable."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
            return True
        except Exception as e:
            logger.warning(f'Fallback email failed: {e}')
            return False
