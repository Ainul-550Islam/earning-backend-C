"""WEBHOOKS/shipping_webhook.py — Inbound Shipping/Courier Webhook Handler"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger(__name__)


class SteadfastWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        consignment_id = data.get("consignment_id","")
        status = data.get("delivery_status","")
        logger.info("[Webhook:Steadfast] %s → %s", consignment_id, status)

        if consignment_id and status:
            from api.marketplace.SHIPPING_LOGISTICS.shipping_label import ShippingLabel
            from api.marketplace.models import OrderTracking
            from api.marketplace.enums import TrackingEvent
            label = ShippingLabel.objects.filter(tracking_number=consignment_id).select_related("order__tenant").first()
            if label:
                event = TrackingEvent.DELIVERED if status.lower() in ("delivered","success") else TrackingEvent.IN_TRANSIT
                OrderTracking.objects.create(
                    tenant=label.order.tenant, order=label.order,
                    event=event, description=f"Steadfast: {status}",
                    courier_name="Steadfast", tracking_number=consignment_id,
                )
        return Response({"status": "received"})


class PathaoWebhookView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        logger.info("[Webhook:Pathao] %s", request.data)
        return Response({"status": "received"})
