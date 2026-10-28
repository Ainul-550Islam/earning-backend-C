# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Public Inbound Webhook Receiver
inbound_receiver.py  (NEW FILE)

Business context:
    bKash, Nagad, Stripe, PayPal and other payment gateways send
    webhooks TO this system. This is the single public-facing entry
    point they POST to.

    Previously PayloadParser + SignatureVerifier existed but were
    "floating" — no public HTTP endpoint received external payloads
    and routed them through those services.

URL pattern (registered in urls.py):
    POST /webhooks/receive/<str:source>/
        source: bkash | nagad | stripe | paypal | <custom>

Processing pipeline:
    1. Signature verification   → SignatureVerifier
    2. Payload normalisation    → PayloadParser
    3. Async dispatch           → InboundWebhookService
    4. Event routing            → InboundEventRouter (inside service)
"""

import json
import logging
import time

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("ainul.webhooks.inbound_receiver")


@method_decorator(csrf_exempt, name="dispatch")
class InboundWebhookReceiverView(View):
    """
    Public CSRF-exempt endpoint that receives webhooks from external providers.

    POST /webhooks/receive/<source>/

    Authentication is via payload signature — not DRF session/token.
    Always returns 200 to the caller to prevent secret enumeration.
    """

    def post(self, request, source: str):
        t0 = time.monotonic()

        # 1. Capture raw body before any framework parsing
        raw_body = request.body
        meta     = request.META
        headers  = {k: v for k, v in meta.items() if k.startswith("HTTP_")}
        signature = (
            headers.get("HTTP_X_WEBHOOK_SIGNATURE")
            or headers.get("HTTP_STRIPE_SIGNATURE")
            or headers.get("HTTP_X_BKASH_SIGNATURE")
            or headers.get("HTTP_X_NAGAD_SIGNATURE")
            or headers.get("HTTP_X_HUB_SIGNATURE_256", "")
        )
        ip = (
            meta.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or meta.get("REMOTE_ADDR", "unknown")
        )

        logger.info("InboundReceiver source=%s ip=%s sig=%s", source, ip, bool(signature))

        # 2. Lookup InboundWebhook config
        try:
            from .models import InboundWebhook
            inbound = InboundWebhook.objects.filter(
                source=source, is_active=True
            ).select_related("owner").first()
            if not inbound:
                logger.warning("InboundReceiver: no active config for source=%s", source)
                return self._ok()
        except Exception:
            logger.exception("InboundReceiver: model lookup error")
            return self._ok()

        # 3. Parse raw body → dict
        try:
            raw_payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            raw_payload = {"_raw": raw_body.decode("utf-8", errors="replace")}

        # 4. PayloadParser — normalise to unified schema
        try:
            from .services.inbound.PayloadParser import PayloadParser
            parsed = PayloadParser().parse_payload(source=source, raw_payload=raw_payload)
        except Exception as exc:
            logger.error("InboundReceiver: PayloadParser error source=%s: %s", source, exc)
            parsed = raw_payload  # fallback: pass raw

        # 5. SignatureVerifier — reject invalid signatures
        try:
            from .services.inbound.SignatureVerifier import SignatureVerifier
            valid = SignatureVerifier().verify_signature(
                source=source,
                payload=parsed,
                signature=signature,
                secret=inbound.secret or "",
            )
            if not valid:
                logger.warning("InboundReceiver: bad signature source=%s ip=%s", source, ip)
                # Timing-safe: pad to 100 ms so response time doesn't leak secret validity
                time.sleep(max(0.0, 0.10 - (time.monotonic() - t0)))
                return self._ok()   # silent 200 — no info leak
        except Exception as exc:
            logger.error("InboundReceiver: SignatureVerifier error: %s", exc)

        # 6. InboundWebhookService — persist log, fire Celery task, route
        try:
            from .services.inbound.InboundWebhookService import InboundWebhookService
            InboundWebhookService().process_inbound_webhook(
                inbound=inbound,
                payload=parsed,
                headers=headers,
                signature=signature,
                ip_address=ip,
            )
        except Exception:
            logger.exception("InboundReceiver: service error source=%s", source)

        return self._ok()

    @staticmethod
    def _ok():
        return JsonResponse({"received": True}, status=200)
