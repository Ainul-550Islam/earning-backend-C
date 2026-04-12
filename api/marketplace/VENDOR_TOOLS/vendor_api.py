"""
VENDOR_TOOLS/vendor_api.py — External Vendor API (REST endpoints for sellers)
==============================================================================
Provides a lightweight API layer that external seller systems (ERPs, POS, apps)
can call to sync products, update stock, fetch orders, etc.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.authentication import TokenAuthentication


class VendorAPIBase(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_seller(self, request):
        from api.marketplace.models import SellerProfile
        try:
            return SellerProfile.objects.get(user=request.user, tenant=request.tenant)
        except SellerProfile.DoesNotExist:
            return None


class VendorInventoryAPIView(VendorAPIBase):
    """GET/PUT /api/vendor/inventory/"""

    def get(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        from api.marketplace.VENDOR_TOOLS.inventory_sync import InventorySyncService
        svc  = InventorySyncService(seller, request.tenant)
        data = svc.get_full_inventory_export()
        return Response({"inventory": data, "count": len(data)})

    def put(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        items = request.data.get("items", [])
        if not items:
            return Response({"error": "items list required"}, status=400)
        from api.marketplace.VENDOR_TOOLS.inventory_sync import InventorySyncService
        svc    = InventorySyncService(seller, request.tenant)
        result = svc.sync_from_dict(items)
        return Response(result)


class VendorOrderAPIView(VendorAPIBase):
    """GET /api/vendor/orders/"""

    def get(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        from api.marketplace.VENDOR_TOOLS.order_management_tool import SellerOrderManager
        mgr    = SellerOrderManager(seller, request.tenant)
        result = mgr.get_orders(
            status=request.query_params.get("status"),
            page=int(request.query_params.get("page", 1)),
        )
        return Response(result)

    def post(self, request):
        """Confirm / ship an order."""
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)

        action       = request.data.get("action")
        order_number = request.data.get("order_number")
        from api.marketplace.VENDOR_TOOLS.order_management_tool import SellerOrderManager
        mgr = SellerOrderManager(seller, request.tenant)

        if action == "confirm":
            return Response(mgr.confirm_order(order_number))
        elif action == "ship":
            return Response(mgr.mark_shipped(
                order_number,
                request.data.get("courier", ""),
                request.data.get("tracking_number", ""),
            ))
        return Response({"error": "Unknown action"}, status=400)


class VendorProductAPIView(VendorAPIBase):
    """CRUD for seller products via API key."""

    def get(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        from api.marketplace.models import Product
        from api.marketplace.schemas import ProductListSerializer
        qs = Product.objects.filter(seller=seller, tenant=request.tenant)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        serializer = ProductListSerializer(qs[:100], many=True)
        return Response({"products": serializer.data, "total": qs.count()})


class VendorDashboardAPIView(VendorAPIBase):
    """GET /api/vendor/dashboard/ — full dashboard in one call."""

    def get(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        from api.marketplace.VENDOR_TOOLS.vendor_dashboard import get_full_dashboard
        return Response(get_full_dashboard(seller, request.tenant))


class VendorWebhookRegistrationView(VendorAPIBase):
    """Register a webhook URL for order events."""

    def post(self, request):
        seller = self._get_seller(request)
        if not seller:
            return Response({"error": "Not a seller"}, status=403)
        url = request.data.get("url", "")
        events = request.data.get("events", ["order.placed","order.shipped","order.delivered"])
        if not url:
            return Response({"error": "url required"}, status=400)
        # Store in seller profile (extend model as needed)
        return Response({"registered": True, "url": url, "events": events})
