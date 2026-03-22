"""
views.py – Non-ViewSet views for the subscription module.
Includes webhook endpoint, pricing page API, and admin dashboard summary.
"""
import json
import logging
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from api.tenants.mixins import TenantMixin
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import WebhookAuthentication
from .models import SubscriptionPayment, SubscriptionPlan, UserSubscription
from .serializers import SubscriptionPlanListSerializer, UserSubscriptionSerializer
from .services import get_active_plans, expire_overdue_subscriptions
from .throttling import WebhookThrottle

logger = logging.getLogger(__name__)


class PricingPageView(APIView):
    """
    GET /api/subscriptions/pricing/
    Returns all active plans optimised for a public pricing page.
    No authentication required.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        plans = get_active_plans()
        serializer = SubscriptionPlanListSerializer(
            plans, many=True, context={"request": request}
        )
        return Response({"plans": serializer.data})


class MySubscriptionView(APIView):
    """
    GET /api/subscriptions/my-subscription/
    Convenience endpoint returning the caller's active subscription.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = UserSubscription.objects.get_active_for_user(request.user)
        if not sub:
            return Response(
                {"detail": "No active subscription."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = UserSubscriptionSerializer(sub, context={"request": request})
        return Response(serializer.data)


class PaymentWebhookView(APIView):
    """
    POST /api/subscriptions/webhooks/payment/
    Entry point for payment gateway callbacks (Stripe, PayPal, etc.).
    Signature verification is handled by WebhookAuthentication.
    """
    authentication_classes = [WebhookAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [WebhookThrottle]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON payload."}, status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get("type", "")
        logger.info("Received webhook event: %s", event_type)

        handler = self._get_handler(event_type)
        if handler:
            try:
                handler(payload)
            except Exception as exc:
                logger.exception("Webhook handler error for event %s: %s", event_type, exc)
                return Response({"detail": "Webhook processing error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Always return 200 to acknowledge receipt
        return Response({"status": "received"})

    def _get_handler(self, event_type):
        handlers = {
            "payment.succeeded": self._handle_payment_succeeded,
            "payment.failed": self._handle_payment_failed,
            "subscription.cancelled": self._handle_subscription_cancelled,
        }
        return handlers.get(event_type)

    def _handle_payment_succeeded(self, payload):
        transaction_id = payload.get("data", {}).get("transaction_id")
        try:
            payment = SubscriptionPayment.objects.get(transaction_id=transaction_id)
            payment.mark_succeeded(gateway_response=payload)
        except SubscriptionPayment.DoesNotExist:
            logger.warning("Webhook: Payment not found for transaction_id=%s", transaction_id)

    def _handle_payment_failed(self, payload):
        transaction_id = payload.get("data", {}).get("transaction_id")
        try:
            payment = SubscriptionPayment.objects.get(transaction_id=transaction_id)
            payment.mark_failed(
                code=payload.get("data", {}).get("error_code", ""),
                message=payload.get("data", {}).get("error_message", ""),
                gateway_response=payload,
            )
        except SubscriptionPayment.DoesNotExist:
            logger.warning("Webhook: Payment not found for transaction_id=%s", transaction_id)

    def _handle_subscription_cancelled(self, payload):
        ext_id = payload.get("data", {}).get("subscription_id")
        try:
            sub = UserSubscription.objects.get(external_subscription_id=ext_id)
            sub.cancel(reason="other", comment="Cancelled via gateway webhook.")
        except UserSubscription.DoesNotExist:
            logger.warning("Webhook: Subscription not found for external_id=%s", ext_id)


class AdminDashboardSummaryView(APIView):
    """
    GET /api/subscriptions/admin/summary/
    Quick revenue + subscriber stats for the admin dashboard.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.db.models import Count, Sum, Q
        from .choices import SubscriptionStatus, PaymentStatus

        plan_stats = (
            SubscriptionPlan.objects.active()
            .annotate(
                subscriber_count=Count(
                    "subscriptions",
                    filter=Q(subscriptions__status__in=[
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                    ]),
                )
            )
            .values("name", "price", "currency", "subscriber_count")
        )

        total_revenue = SubscriptionPayment.objects.total_revenue()
        active_subs = UserSubscription.objects.active().count()
        trialing_subs = UserSubscription.objects.trialing().count()
        past_due_subs = UserSubscription.objects.past_due().count()

        return Response({
            "active_subscriptions": active_subs,
            "trialing_subscriptions": trialing_subs,
            "past_due_subscriptions": past_due_subs,
            "total_revenue": str(total_revenue),
            "plans": list(plan_stats),
        })