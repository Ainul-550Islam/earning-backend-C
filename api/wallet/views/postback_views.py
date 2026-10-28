# views/postback_views.py
"""
Postback Views — S2S conversion postback endpoints.
"এক কাজের জন্য একটাই মালিক।"
This file owns: HTTP handling for all platform postbacks.
Platform logic is delegated to OfferwallRegistry.

URLs (add to wallet/urls.py):
  path("postback/<str:platform>/", PostbackView.as_view(), name="wallet-postback"),

Supported:
  /api/wallet/postback/ogads/
  /api/wallet/postback/adgate/
  /api/wallet/postback/offertoro/
  /api/wallet/postback/monlix/
  /api/wallet/postback/cpalead/
"""
import logging

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..services.offerwall.registry import OfferwallRegistry

logger = logging.getLogger("wallet.postback")


@method_decorator(csrf_exempt, name="dispatch")
class PostbackView(View):
    """
    Universal postback endpoint — routes to the correct platform adapter.
    Responds with "1" (success) or "0" (error) to satisfy most network
    requirements. Also returns JSON for debugging.
    """

    def get(self, request, platform: str):
        return self._handle(request, platform, request.GET.dict())

    def post(self, request, platform: str):
        try:
            import json
            body = json.loads(request.body)
        except Exception:
            body = request.POST.dict()
        return self._handle(request, platform, body)

    def _handle(self, request, platform: str, data: dict):
        # Inject IP if not provided by the network
        if not data.get("ip"):
            data["ip"] = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", "")
            )

        sig = data.get("sig") or data.get("hash") or data.get("signature") or ""

        logger.info(
            f"[postback] platform={platform} "
            f"click_id={data.get('click_id') or data.get('txid') or data.get('transid', '')} "
            f"ip={data.get('ip', '')}"
        )

        result = OfferwallRegistry.route_postback(platform, data, sig)

        status = result.get("status", "error")
        ok     = status in ("credited", "duplicate")

        if ok:
            # Most networks expect plain "1" response
            return HttpResponse("1", content_type="text/plain", status=200)
        else:
            logger.warning(
                f"[postback] {platform} failed: "
                f"{result.get('error', 'unknown')} | data={data}"
            )
            return HttpResponse("0", content_type="text/plain", status=200)


# ── Offer Wall API View ────────────────────────────────────────────────────

class OfferwallListView(View):
    """
    GET /api/wallet/offers/?platform=all&country=BD&device=desktop&vertical=gaming
    Returns aggregated offer list from all or specified platforms.
    """

    def get(self, request):
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.decorators import permission_classes

        country  = request.GET.get("country", "BD").upper()
        device   = request.GET.get("device", "desktop")
        platform = request.GET.get("platform", "")
        vertical = request.GET.get("vertical", "")
        min_pay  = float(request.GET.get("min_payout", 0))

        platforms = [platform] if platform and platform != "all" else None

        try:
            offers = OfferwallRegistry.get_all_offers(
                country_code        = country,
                device_type         = device,
                platforms           = platforms,
                vertical            = vertical,
                min_payout_usd      = min_pay,
                limit_per_platform  = 30,
            )
            data = [
                {
                    "offer_id":    o.offer_id,
                    "title":       o.title,
                    "payout_usd":  str(o.payout_usd),
                    "payout_bdt":  str(o.payout_bdt),
                    "offer_type":  o.offer_type,
                    "platform":    o.platform,
                    "url":         o.url,
                    "icon_url":    o.icon_url,
                    "description": o.description,
                    "is_mobile":   o.is_mobile,
                    "is_desktop":  o.is_desktop,
                    "category":    o.category,
                    "vertical":    o.vertical,
                }
                for o in offers
            ]
            return JsonResponse({"success": True, "count": len(data), "offers": data})

        except Exception as exc:
            logger.error(f"[OfferwallListView] Error: {exc}", exc_info=True)
            return JsonResponse({"success": False, "error": str(exc)}, status=500)


class SmartwallUrlView(View):
    """
    GET /api/wallet/smartwall-urls/
    Returns smartwall embed URLs for all configured platforms.
    Requires authentication.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        sub_id = str(request.user.id)
        urls   = OfferwallRegistry.get_smartwall_urls(request.user.id, sub_id)
        return JsonResponse({"success": True, "urls": urls})
