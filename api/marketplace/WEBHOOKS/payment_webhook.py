"""WEBHOOKS/payment_webhook.py — Payment gateway inbound webhook handlers"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger(__name__)


class BkashWebhookView(APIView):
    """Receives bKash IPN (Instant Payment Notification)"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        logger.info("bKash webhook received: %s", data)
        payment_id = data.get("paymentID")
        status = data.get("transactionStatus")
        if status == "Completed" and payment_id:
            from api.marketplace.models import PaymentTransaction
            from api.marketplace.enums import PaymentStatus
            tx = PaymentTransaction.objects.filter(
                gateway_transaction_id=payment_id
            ).first()
            if tx:
                tx.mark_success(gateway_id=payment_id, response=data)
        return Response({"status": "received"})


class NagadWebhookView(APIView):
    """Receives Nagad IPN"""
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("Nagad webhook received: %s", request.data)
        return Response({"status": "received"})
