# api/support/integrations/project_specific/proactive_support.py
"""
Proactive Support — trigger support based on user behavior signals.

Integrates with behavior_analytics to detect:
  - User stuck on offer completion → auto-create ticket
  - Payment failure → proactive outreach
  - Multiple failed login attempts → security ticket
  - Long session without conversion → chat trigger
"""
import logging
logger = logging.getLogger(__name__)


class ProactiveSupportEngine:
    """Trigger proactive support based on behavioral signals."""

    def trigger_chat_for_stuck_user(self, user, context: dict = None) -> bool:
        """
        Trigger proactive chat when user seems stuck.
        Called from behavior_analytics signals.
        """
        try:
            from api.support.models import SupportSettings, ChatSession
            settings_obj, _ = SupportSettings.objects.get_or_create(id=1)
            if not settings_obj.chat_widget_enabled:
                return False

            # Don't trigger if user already has active chat
            if ChatSession.objects.filter(user=user, status__in=["waiting","active"]).exists():
                return False

            # Trigger via notification
            from api.support.integrations.integ_adapter import notifications_adapter
            notifications_adapter.send(
                user,
                "Need help? 💬",
                "It looks like you might need assistance. Our support team is here to help!",
                notification_type="proactive_chat",
                data={"action": "open_chat", "context": context or {}},
            )
            logger.info(f"Proactive chat triggered for user {user.id}")
            return True
        except Exception as e:
            logger.debug(f"ProactiveSupportEngine.trigger_chat_for_stuck_user: {e}")
            return False

    def auto_create_ticket_on_payment_failure(self, user, payment_data: dict) -> object:
        """
        Auto-create support ticket when payment/withdrawal fails.
        Integrate with payment_gateways webhook.
        """
        try:
            from api.support.services import ticket_service
            ticket = ticket_service.create(user, {
                "subject":     f"Payment Issue: {payment_data.get('method','Unknown')}",
                "description": (
                    "AUTOMATED: Payment/withdrawal issue detected.\n"
                    "Transaction: {payment_data.get('transaction_id','')}\n"
                    "Amount: {payment_data.get('amount','')}\n"
                    "Error: {payment_data.get('error_message','Unknown error')}\n"
                    f"Please investigate and resolve."
                ),
                "category": "withdrawal",
                "priority":  "high",
                "channel":   "api",
            })
            logger.info(f"Auto-ticket created for payment failure: {ticket.ticket_id}")
            return ticket
        except Exception as e:
            logger.debug(f"auto_create_ticket_on_payment_failure: {e}")
            return None

    def schedule_follow_up(self, ticket, delay_hours: int = 48) -> bool:
        """
        Schedule a follow-up message after ticket resolution.
        Check if user is satisfied, offer additional help.
        """
        try:
            from celery import current_app
            current_app.send_task(
                "support.tasks.send_followup_message",
                args=[ticket.id],
                countdown=delay_hours * 3600,
            )
            return True
        except Exception as e:
            logger.debug(f"ProactiveSupportEngine.schedule_follow_up: {e}")
            return False

    def check_offer_abandonment(self, user, offer_id: str) -> bool:
        """
        Detect if user abandoned an offer halfway — proactive support.
        """
        try:
            from django.apps import apps
            # Check offer state in offerwall
            OfferConversion = apps.get_model("offerwall", "OfferConversion")
            incomplete = OfferConversion.objects.filter(
                user=user,
                offer_id=offer_id,
                status__in=["started","partial","abandoned"],
            ).exists()

            if incomplete:
                self.trigger_chat_for_stuck_user(user, {
                    "context_type": "offer_abandonment",
                    "offer_id":     offer_id,
                })
            return incomplete
        except Exception:
            return False


proactive_support = ProactiveSupportEngine()