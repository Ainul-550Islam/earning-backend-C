"""
marketplace/urls.py — Complete URL Configuration
==================================================
Installation in config/urls.py:
    from django.urls import path, include
    path("api/marketplace/", include("api.marketplace.urls")),

Full Endpoint Reference:
  GET    /api/marketplace/categories/                 → Category list (tree)
  GET    /api/marketplace/categories/{id}/subtree/    → Subtree of category
  GET    /api/marketplace/products/                   → Product list + filters
  POST   /api/marketplace/products/                   → Create product (seller)
  GET    /api/marketplace/products/{id}/              → Product detail
  GET    /api/marketplace/product-variants/           → Variant list
  GET    /api/marketplace/inventory/                  → Inventory status
  GET    /api/marketplace/sellers/                    → Seller directory
  POST   /api/marketplace/sellers/                    → Register as seller
  GET    /api/marketplace/seller-verification/        → KYC status
  POST   /api/marketplace/seller-verification/        → Submit KYC
  GET    /api/marketplace/seller-payouts/             → Payout history
  GET    /api/marketplace/commission-configs/         → Commission rates
  GET    /api/marketplace/cart/                       → View cart
  POST   /api/marketplace/cart/{id}/add_item/         → Add to cart
  POST   /api/marketplace/cart/{id}/remove_item/      → Remove from cart
  POST   /api/marketplace/cart/{id}/apply_coupon/     → Apply coupon
  POST   /api/marketplace/cart/{id}/checkout/         → Place order
  GET    /api/marketplace/orders/                     → Order history
  GET    /api/marketplace/orders/{id}/                → Order detail
  POST   /api/marketplace/orders/{id}/confirm/        → Seller confirms
  POST   /api/marketplace/orders/{id}/ship/           → Mark shipped
  POST   /api/marketplace/orders/{id}/deliver/        → Mark delivered
  POST   /api/marketplace/orders/{id}/cancel/         → Cancel order
  GET    /api/marketplace/transactions/               → Payment history
  GET    /api/marketplace/escrow/                     → Escrow holdings
  GET    /api/marketplace/refunds/                    → Refund requests
  POST   /api/marketplace/refunds/                    → Request refund
  GET    /api/marketplace/coupons/                    → Active coupons
  POST   /api/marketplace/coupons/validate/           → Validate coupon
  GET    /api/marketplace/reviews/                    → Reviews
  POST   /api/marketplace/reviews/                    → Submit review
  GET    /api/marketplace/promotions/                 → Active campaigns
  GET    /api/marketplace/search/                     → Full-text search
  GET    /api/marketplace/search/autocomplete/        → Autocomplete
  GET    /api/marketplace/search/trending/            → Trending queries
  GET    /api/marketplace/search/filters/             → Available filters
  GET    /api/marketplace/checkout-session/           → Get checkout session
  POST   /api/marketplace/checkout-session/           → Create session
  PUT    /api/marketplace/checkout-session/           → Update step
  GET    /api/marketplace/address-book/               → Saved addresses
  POST   /api/marketplace/address-book/               → Save address
  GET    /api/marketplace/loyalty/                    → Loyalty points
  GET    /api/marketplace/referral/                   → Referral code
  POST   /api/marketplace/referral/                   → Apply referral
  GET    /api/marketplace/disputes/                   → My disputes
  POST   /api/marketplace/disputes/                   → Raise dispute
  GET    /api/marketplace/disputes/{pk}/              → Dispute detail
  POST   /api/marketplace/disputes/{pk}/respond/      → Seller response
  POST   /api/marketplace/disputes/{pk}/escalate/     → Escalate
  POST   /api/marketplace/disputes/{pk}/arbitrate/    → Admin arbitrate
  POST   /api/marketplace/disputes/{pk}/evidence/     → Upload evidence
  GET    /api/marketplace/vendor/inventory/           → Inventory export
  PUT    /api/marketplace/vendor/inventory/           → Bulk update stock
  GET    /api/marketplace/vendor/orders/              → Seller orders
  POST   /api/marketplace/vendor/orders/              → Confirm/ship
  GET    /api/marketplace/vendor/products/            → My products
  GET    /api/marketplace/vendor/dashboard/           → KPI dashboard
  POST   /api/marketplace/vendor/bulk-upload/         → Bulk product upload
  GET    /api/marketplace/vendor/export/              → Export CSV/Excel
  GET    /api/marketplace/mobile-sync/                → Offline manifest
  GET    /api/marketplace/device-tokens/              → My push tokens
  POST   /api/marketplace/device-tokens/              → Register token
  DELETE /api/marketplace/device-tokens/              → Remove token
  GET    /api/marketplace/app-config/                 → Remote app config
  POST   /api/marketplace/payment-webhook/<gateway>/  → bKash/Nagad callback
  POST   /api/marketplace/shipping-webhook/<carrier>/ → Steadfast/Pathao callback
"""

from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter as DefaultRouter

# ── Core ViewSets ─────────────────────────────────────────────────────────────
from .views import (
    CategoryViewSet,
    ProductViewSet,
    ProductVariantViewSet,
    ProductInventoryViewSet,
    SellerProfileViewSet,
    SellerVerificationViewSet,
    SellerPayoutViewSet,
    CommissionConfigViewSet,
    CartViewSet,
    OrderViewSet,
    PaymentTransactionViewSet,
    EscrowHoldingViewSet,
    RefundRequestViewSet,
    CouponViewSet,
    ProductReviewViewSet,
    PromotionCampaignViewSet,
)

app_name = "marketplace"

# ── DRF Router ────────────────────────────────────────────────────────────────
router = DefaultRouter()

# Products & Categories
router.register(r"categories",       CategoryViewSet,          basename="marketplace-category")
router.register(r"products",         ProductViewSet,           basename="marketplace-product")
router.register(r"product-variants", ProductVariantViewSet,    basename="marketplace-variant")
router.register(r"inventory",        ProductInventoryViewSet,  basename="marketplace-inventory")

# Sellers
router.register(r"sellers",             SellerProfileViewSet,      basename="marketplace-seller")
router.register(r"seller-verification", SellerVerificationViewSet, basename="marketplace-verification")
router.register(r"seller-payouts",      SellerPayoutViewSet,       basename="marketplace-payout")
router.register(r"commission-configs",  CommissionConfigViewSet,   basename="marketplace-commission")

# Cart & Orders
router.register(r"cart",   CartViewSet,  basename="marketplace-cart")
router.register(r"orders", OrderViewSet, basename="marketplace-order")

# Payment
router.register(r"transactions", PaymentTransactionViewSet, basename="marketplace-transaction")
router.register(r"escrow",       EscrowHoldingViewSet,      basename="marketplace-escrow")
router.register(r"refunds",      RefundRequestViewSet,      basename="marketplace-refund")

# Marketing
router.register(r"coupons",    CouponViewSet,            basename="marketplace-coupon")
router.register(r"reviews",    ProductReviewViewSet,     basename="marketplace-review")
router.register(r"promotions", PromotionCampaignViewSet, basename="marketplace-promotion")


@api_view(["GET"])
@permission_classes([AllowAny])
def search_view(request):
    """
    GET /api/marketplace/search/?q=<query>
    Optional filters: category, min_price, max_price, min_rating, in_stock, sort
    sort options: relevance | price_asc | price_desc | rating | newest | popular
    """
    from .SEARCH_DISCOVERY.search_engine import SearchEngine, SearchQuery
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response({"error": "Tenant not found"}, status=400)

    q = SearchQuery(
        query=request.query_params.get("q", ""),
        category_slug=request.query_params.get("category"),
        min_price=request.query_params.get("min_price"),
        max_price=request.query_params.get("max_price"),
        min_rating=request.query_params.get("min_rating"),
        in_stock=request.query_params.get("in_stock") == "true",
        sort_by=request.query_params.get("sort", "relevance"),
        page=int(request.query_params.get("page", 1)),
        page_size=int(request.query_params.get("page_size", 20)),
        attributes=dict(request.query_params),
    )
    engine = SearchEngine(tenant)
    return Response(engine.search(q))


@api_view(["GET"])
@permission_classes([AllowAny])
def autocomplete_view(request):
    """GET /api/marketplace/search/autocomplete/?q=<query>"""
    from .SEARCH_DISCOVERY.autocomplete import autocomplete_suggestions
    tenant = getattr(request, "tenant", None)
    query = request.query_params.get("q", "")
    return Response({"suggestions": autocomplete_suggestions(tenant, query)})


@api_view(["GET"])
@permission_classes([AllowAny])
def trending_search_view(request):
    """GET /api/marketplace/search/trending/"""
    from .SEARCH_DISCOVERY.autocomplete import trending_searches
    tenant = getattr(request, "tenant", None)
    return Response({"trending": trending_searches(tenant)})


@api_view(["GET"])
@permission_classes([AllowAny])
def search_filters_view(request):
    """GET /api/marketplace/search/filters/?category=<id>"""
    from .SEARCH_DISCOVERY.filter_manager import get_available_filters
    tenant = getattr(request, "tenant", None)
    category_id = request.query_params.get("category")
    return Response(get_available_filters(tenant, category_id=category_id))


# ============================================================================
# CHECKOUT SESSION & ADDRESS BOOK
# ============================================================================

@api_view(["GET", "POST", "PUT"])
@permission_classes([IsAuthenticated])
def checkout_session_view(request):
    """
    GET  /api/marketplace/checkout-session/?session_id=<id>
    POST /api/marketplace/checkout-session/ {cart_id}
    PUT  /api/marketplace/checkout-session/ {session_id, step, address|payment_method}
    """
    from .CART_CHECKOUT.checkout_session import (
        get_checkout_session, create_checkout_session, get_session_progress,
    )
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        session_id = (request.query_params.get("session_id")
                      or request.session.get("checkout_session_id"))
        if not session_id:
            return Response({"session": None})
        session = get_checkout_session(session_id)
        if not session:
            return Response({"session": None, "expired": True})
        return Response({"session": session.to_dict(), "progress": get_session_progress(session)})

    if request.method == "POST":
        cart_id = request.data.get("cart_id")
        if not cart_id:
            return Response({"error": "cart_id required"}, status=400)
        session = create_checkout_session(request.user.id, int(cart_id), getattr(tenant, "id", 0))
        request.session["checkout_session_id"] = session.session_id
        return Response({"session": session.to_dict(), "progress": get_session_progress(session)}, status=201)

    if request.method == "PUT":
        session_id = request.data.get("session_id")
        session = get_checkout_session(session_id)
        if not session:
            return Response({"error": "Session not found or expired"}, status=404)

        step = request.data.get("step")
        if step == "address" and request.data.get("address"):
            session.set_shipping_address(request.data["address"])
            session.advance_step("payment")
        elif step == "payment" and request.data.get("payment_method"):
            session.set_payment_method(request.data["payment_method"])
            if request.data.get("coupon_code"):
                session.set_coupon(request.data["coupon_code"])
            session.advance_step("review")
        elif step == "review":
            session.advance_step("processing")

        return Response({"session": session.to_dict(), "progress": get_session_progress(session)})


@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def address_book_view(request):
    """
    GET    /api/marketplace/address-book/
    POST   /api/marketplace/address-book/         {full_name, phone, address_line, city, ...}
    PUT    /api/marketplace/address-book/?id=<n>  {fields to update}
    DELETE /api/marketplace/address-book/?id=<n>
    """
    from .CART_CHECKOUT.address_book import (
        get_user_addresses, save_address, update_address,
        delete_address, validate_address,
    )
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        return Response(get_user_addresses(request.user, tenant))

    if request.method == "POST":
        validation = validate_address(request.data)
        if not validation["valid"]:
            return Response({"errors": validation["errors"]}, status=400)
        addr = save_address(request.user, tenant, request.data)
        return Response({"id": addr.pk, "success": True}, status=201)

    if request.method == "PUT":
        addr_id = request.query_params.get("id") or request.data.get("id")
        if not addr_id:
            return Response({"error": "id required"}, status=400)
        result = update_address(int(addr_id), request.user, request.data)
        return Response(result)

    if request.method == "DELETE":
        addr_id = request.query_params.get("id")
        if not addr_id:
            return Response({"error": "id required"}, status=400)
        from .CART_CHECKOUT.address_book import delete_address as del_addr
        deleted = del_addr(int(addr_id), request.user)
        return Response({"deleted": deleted})


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def saved_payments_view(request):
    """
    GET    /api/marketplace/saved-payments/
    DELETE /api/marketplace/saved-payments/?id=<n>
    """
    from .CART_CHECKOUT.saved_payment import get_saved_methods, delete_saved_method
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        return Response(get_saved_methods(request.user, tenant))
    addr_id = request.query_params.get("id")
    if not addr_id:
        return Response({"error": "id required"}, status=400)
    deleted = delete_saved_method(request.user, int(addr_id))
    return Response({"deleted": deleted})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def loyalty_view(request):
    """GET /api/marketplace/loyalty/"""
    from .PROMOTION_MARKETING.loyalty_reward import LoyaltyService
    tenant = getattr(request, "tenant", None)
    return Response(LoyaltyService.get_summary(request.user, tenant))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def referral_view(request):
    """
    GET  /api/marketplace/referral/        → My code + stats
    POST /api/marketplace/referral/ {code} → Apply referral code
    """
    from .PROMOTION_MARKETING.referral_coupon import ReferralService
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        code = ReferralService.get_or_create_code(request.user, tenant)
        stats = ReferralService.stats(request.user, tenant)
        return Response({"referral_code": code, "stats": stats})

    code = request.data.get("code", "").strip()
    if not code:
        return Response({"error": "code required"}, status=400)
    return Response(ReferralService.apply_referral_code(request.user, tenant, code))


# ============================================================================
# DISPUTES
# ============================================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def dispute_list_view(request):
    """
    GET  /api/marketplace/disputes/
    POST /api/marketplace/disputes/ {order_item_id, dispute_type, description}
    """
    from .DISPUTE_RESOLUTION.dispute_resolution import DisputeResolutionService
    from .DISPUTE_RESOLUTION.dispute_model import Dispute
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        qs = Dispute.objects.filter(tenant=tenant, raised_by=request.user).order_by("-created_at")
        return Response({
            "disputes": [
                {
                    "id": d.pk,
                    "order_number": d.order.order_number if d.order else "",
                    "dispute_type": d.dispute_type,
                    "status": d.status,
                    "description": d.description[:100],
                    "created_at": d.created_at.isoformat(),
                }
                for d in qs
            ],
            "count": qs.count(),
        })

    order_item_id = request.data.get("order_item_id")
    if not order_item_id:
        return Response({"error": "order_item_id required"}, status=400)

    from .models import OrderItem
    try:
        order_item = OrderItem.objects.get(pk=order_item_id, order__user=request.user)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found"}, status=404)

    result = DisputeResolutionService.raise_dispute(
        order_item=order_item,
        raised_by=request.user,
        dispute_type=request.data.get("dispute_type", "other"),
        description=request.data.get("description", ""),
        tenant=tenant,
    )
    return Response(result, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dispute_detail_view(request, pk: int):
    """GET /api/marketplace/disputes/{pk}/"""
    from .DISPUTE_RESOLUTION.dispute_model import Dispute
    from .DISPUTE_RESOLUTION.dispute_communication import get_thread
    from .DISPUTE_RESOLUTION.dispute_evidence import get_evidence
    tenant = getattr(request, "tenant", None)
    try:
        dispute = Dispute.objects.get(pk=pk, tenant=tenant)
    except Dispute.DoesNotExist:
        return Response({"error": "Dispute not found"}, status=404)
    return Response({
        "id": dispute.pk,
        "order_number": dispute.order.order_number if dispute.order else "",
        "dispute_type": dispute.dispute_type,
        "status": dispute.status,
        "description": dispute.description,
        "messages": get_thread(dispute),
        "evidence": get_evidence(dispute),
        "created_at": dispute.created_at.isoformat(),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dispute_respond_view(request, pk: int):
    """POST /api/marketplace/disputes/{pk}/respond/ {response}"""
    from .DISPUTE_RESOLUTION.dispute_resolution import DisputeResolutionService
    tenant = getattr(request, "tenant", None)
    result = DisputeResolutionService.seller_respond(
        dispute_id=pk,
        seller_user=request.user,
        response_text=request.data.get("response", ""),
        tenant=tenant,
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dispute_escalate_view(request, pk: int):
    """POST /api/marketplace/disputes/{pk}/escalate/"""
    from .DISPUTE_RESOLUTION.dispute_model import Dispute
    from .enums import DisputeStatus
    tenant = getattr(request, "tenant", None)
    try:
        dispute = Dispute.objects.get(pk=pk, tenant=tenant, raised_by=request.user)
        dispute.status = DisputeStatus.ESCALATED
        dispute.save(update_fields=["status"])
        return Response({"success": True, "status": "escalated"})
    except Dispute.DoesNotExist:
        return Response({"error": "Dispute not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dispute_arbitrate_view(request, pk: int):
    """POST /api/marketplace/disputes/{pk}/arbitrate/ {verdict, notes, refund_percent}"""
    if not request.user.is_staff:
        return Response({"error": "Admin access required"}, status=403)
    from .DISPUTE_RESOLUTION.dispute_resolution import DisputeResolutionService
    tenant = getattr(request, "tenant", None)
    result = DisputeResolutionService.admin_arbitrate(
        dispute_id=pk,
        admin_user=request.user,
        verdict=request.data.get("verdict", "buyer_wins"),
        notes=request.data.get("notes", ""),
        refund_percent=float(request.data.get("refund_percent", 100)),
        tenant=tenant,
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dispute_evidence_view(request, pk: int):
    """POST /api/marketplace/disputes/{pk}/evidence/ {file, caption}"""
    from .DISPUTE_RESOLUTION.dispute_model import Dispute
    from .DISPUTE_RESOLUTION.dispute_evidence import add_evidence
    tenant = getattr(request, "tenant", None)
    try:
        dispute = Dispute.objects.get(pk=pk, tenant=tenant)
    except Dispute.DoesNotExist:
        return Response({"error": "Dispute not found"}, status=404)

    file = request.FILES.get("file")
    if not file:
        return Response({"error": "file required"}, status=400)

    # Determine role
    is_seller = (
        hasattr(dispute, "against_seller") and
        dispute.against_seller is not None and
        hasattr(dispute.against_seller, "user") and
        dispute.against_seller.user == request.user
    )
    role = "seller" if is_seller else "buyer"
    result = add_evidence(dispute, request.user, role, file, request.data.get("caption", ""))
    return Response(result)


# ============================================================================
# VENDOR TOOLS
# ============================================================================

def _get_seller(request):
    from .models import SellerProfile
    try:
        return SellerProfile.objects.get(user=request.user, tenant=getattr(request, "tenant", None))
    except SellerProfile.DoesNotExist:
        return None


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def vendor_inventory_view(request):
    """
    GET /api/marketplace/vendor/inventory/
    PUT /api/marketplace/vendor/inventory/ {file: CSV} or {items: [{sku, quantity}]}
    """
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)
    from .VENDOR_TOOLS.inventory_sync import InventorySyncService
    svc = InventorySyncService(seller, getattr(request, "tenant", None))

    if request.method == "GET":
        low_stock = request.query_params.get("low_stock") == "true"
        if low_stock:
            threshold = int(request.query_params.get("threshold", 10))
            return Response({"items": svc.get_low_stock_report(threshold)})
        return Response({"inventory": svc.get_full_inventory_export()})

    if request.FILES.get("file"):
        result = svc.sync_from_csv(request.FILES["file"].read())
    elif request.data.get("items"):
        result = svc.sync_from_dict(request.data["items"])
    else:
        return Response({"error": "Provide 'file' (CSV) or 'items' (JSON list)"}, status=400)
    return Response(result.to_dict())


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def vendor_orders_view(request):
    """
    GET  /api/marketplace/vendor/orders/  ?status=pending&page=1&q=<search>
    POST /api/marketplace/vendor/orders/  {action: confirm|ship, order_number, courier?, tracking_number?}
    """
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)
    from .VENDOR_TOOLS.order_management_tool import SellerOrderManager
    mgr = SellerOrderManager(seller, getattr(request, "tenant", None))

    if request.method == "GET":
        return Response(mgr.get_orders(
            status=request.query_params.get("status"),
            from_date=request.query_params.get("from"),
            to_date=request.query_params.get("to"),
            search=request.query_params.get("q"),
            page=int(request.query_params.get("page", 1)),
        ))

    action = request.data.get("action")
    order_number = request.data.get("order_number", "")
    if not action or not order_number:
        return Response({"error": "action and order_number required"}, status=400)
    if action == "confirm":
        return Response(mgr.confirm_order(order_number))
    elif action == "ship":
        return Response(mgr.mark_shipped(
            order_number,
            request.data.get("courier", ""),
            request.data.get("tracking_number", ""),
        ))
    elif action == "bulk_confirm":
        order_numbers = request.data.get("order_numbers", [])
        return Response(mgr.bulk_confirm(order_numbers))
    return Response({"error": "Unknown action. Use: confirm | ship | bulk_confirm"}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_products_view(request):
    """GET /api/marketplace/vendor/products/ ?status=active"""
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)
    from .models import Product
    qs = Product.objects.filter(seller=seller, tenant=getattr(request, "tenant", None))
    status_f = request.query_params.get("status")
    if status_f:
        qs = qs.filter(status=status_f)
    from .schemas import ProductListSerializer
    return Response({"products": ProductListSerializer(qs[:100], many=True).data, "total": qs.count()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_dashboard_view(request):
    """GET /api/marketplace/vendor/dashboard/"""
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)
    from .VENDOR_TOOLS.vendor_dashboard import get_full_dashboard
    return Response(get_full_dashboard(seller, getattr(request, "tenant", None)))


@api_view(["POST", "GET"])
@permission_classes([IsAuthenticated])
def vendor_bulk_upload_view(request):
    """
    POST /api/marketplace/vendor/bulk-upload/ {file: CSV/Excel}
         Returns {job_id, status}
    GET  /api/marketplace/vendor/bulk-upload/?job_id=<id>
         Returns {status, progress, completed, errors}
    """
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)
    from .VENDOR_TOOLS.bulk_upload import BulkUploadService
    svc = BulkUploadService(seller, getattr(request, "tenant", None))

    if request.method == "GET":
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"error": "job_id required"}, status=400)
        return Response(svc.get_progress(job_id))

    file = request.FILES.get("file")
    if not file:
        return Response({"error": "file required"}, status=400)
    result = svc.start_upload(file)
    return Response(result, status=202)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendor_export_view(request):
    """
    GET /api/marketplace/vendor/export/?format=csv|xlsx&type=products|orders
    Optional: from=YYYY-MM-DD&to=YYYY-MM-DD (for orders)
    """
    seller = _get_seller(request)
    if not seller:
        return Response({"error": "Not a registered seller"}, status=403)

    from django.http import HttpResponse
    tenant = getattr(request, "tenant", None)
    fmt = request.query_params.get("format", "csv")
    export_type = request.query_params.get("type", "products")

    if export_type == "products":
        from .VENDOR_TOOLS.product_export import export_products_csv, export_products_xlsx
        if fmt == "xlsx":
            content = export_products_xlsx(seller, tenant)
            resp = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            resp["Content-Disposition"] = 'attachment; filename="products.xlsx"'
        else:
            content = export_products_csv(seller, tenant)
            resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
            resp["Content-Disposition"] = 'attachment; filename="products.csv"'
        return resp

    elif export_type == "orders":
        from .VENDOR_TOOLS.product_export import export_orders_csv
        content = export_orders_csv(
            seller, tenant,
            from_date=request.query_params.get("from"),
            to_date=request.query_params.get("to"),
        )
        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="orders.csv"'
        return resp

    return Response({"error": "Unknown type. Use: products | orders"}, status=400)


# ============================================================================
# MOBILE
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mobile_sync_view(request):
    """GET /api/marketplace/mobile-sync/"""
    from .MOBILE_MARKETPLACE.offline_sync import generate_sync_manifest
    tenant = getattr(request, "tenant", None)
    return Response(generate_sync_manifest(tenant, request.user))


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def device_token_view(request):
    """
    GET    /api/marketplace/device-tokens/
    POST   /api/marketplace/device-tokens/ {token, platform, device_name, app_version}
    DELETE /api/marketplace/device-tokens/?token=<t>
    """
    from .MOBILE_MARKETPLACE.push_notification import DeviceToken
    tenant = getattr(request, "tenant", None)

    if request.method == "GET":
        tokens = DeviceToken.objects.filter(user=request.user, tenant=tenant, is_active=True)
        return Response([{
            "id": t.pk, "platform": t.platform,
            "device_name": t.device_name, "app_version": t.app_version,
        } for t in tokens])

    if request.method == "POST":
        token_str = request.data.get("token", "").strip()
        if not token_str:
            return Response({"error": "token required"}, status=400)
        token, created = DeviceToken.objects.update_or_create(
            token=token_str,
            defaults={
                "user": request.user, "tenant": tenant,
                "platform": request.data.get("platform", "android"),
                "device_name": request.data.get("device_name", ""),
                "app_version": request.data.get("app_version", ""),
                "is_active": True,
            }
        )
        return Response({"id": token.pk, "registered": True}, status=201 if created else 200)

    token_str = request.query_params.get("token", "")
    if token_str:
        DeviceToken.objects.filter(token=token_str, user=request.user).update(is_active=False)
    return Response({"deleted": bool(token_str)})


@api_view(["GET"])
@permission_classes([AllowAny])
def app_config_view(request):
    """GET /api/marketplace/app-config/?platform=android|ios|all"""
    from .MOBILE_MARKETPLACE.mobile_app_config import get_app_config
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response({})
    platform = request.query_params.get("platform", "all")
    return Response(get_app_config(tenant, platform))


# ============================================================================
# INBOUND WEBHOOKS
# ============================================================================

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def payment_webhook_view(request, gateway: str):
    """
    POST /api/marketplace/payment-webhook/bkash/
    POST /api/marketplace/payment-webhook/nagad/
    POST /api/marketplace/payment-webhook/rocket/
    POST /api/marketplace/payment-webhook/card/
    """
    from .INTEGRATIONS.payment_gateway_integration import handle_gateway_webhook
    tenant = getattr(request, "tenant", None)
    result = handle_gateway_webhook(gateway, request.data, tenant)
    return Response(result)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def shipping_webhook_view(request, carrier: str):
    """
    POST /api/marketplace/shipping-webhook/steadfast/
    POST /api/marketplace/shipping-webhook/pathao/
    POST /api/marketplace/shipping-webhook/redx/
    POST /api/marketplace/shipping-webhook/ecourier/
    """
    from .WEBHOOKS.shipping_webhook import handle_shipping_webhook
    tenant = getattr(request, "tenant", None)
    result = handle_shipping_webhook(carrier, request.data, tenant)
    return Response(result)
urlpatterns = [
    # ── Main Router ───────────────────────────────────────────────────────────
    path("", include(router.urls)),

    # ── Search ────────────────────────────────────────────────────────────────
    path("search/",              search_view,          name="marketplace-search"),
    path("search/autocomplete/", autocomplete_view,    name="marketplace-autocomplete"),
    path("search/trending/",     trending_search_view, name="marketplace-trending"),
    path("search/filters/",      search_filters_view,  name="marketplace-filters"),

    # ── Checkout & Cart Extras ────────────────────────────────────────────────
    path("checkout-session/", checkout_session_view, name="marketplace-checkout-session"),
    path("address-book/",     address_book_view,     name="marketplace-address-book"),
    path("saved-payments/",   saved_payments_view,   name="marketplace-saved-payments"),
    path("loyalty/",          loyalty_view,          name="marketplace-loyalty"),
    path("referral/",         referral_view,         name="marketplace-referral"),

    # ── Disputes ──────────────────────────────────────────────────────────────
    path("disputes/",                        dispute_list_view,     name="marketplace-dispute-list"),
    path("disputes/<int:pk>/",               dispute_detail_view,   name="marketplace-dispute-detail"),
    path("disputes/<int:pk>/respond/",       dispute_respond_view,  name="marketplace-dispute-respond"),
    path("disputes/<int:pk>/escalate/",      dispute_escalate_view, name="marketplace-dispute-escalate"),
    path("disputes/<int:pk>/arbitrate/",     dispute_arbitrate_view,name="marketplace-dispute-arbitrate"),
    path("disputes/<int:pk>/evidence/",      dispute_evidence_view, name="marketplace-dispute-evidence"),

    # ── Vendor Tools ──────────────────────────────────────────────────────────
    path("vendor/inventory/",   vendor_inventory_view,   name="marketplace-vendor-inventory"),
    path("vendor/orders/",      vendor_orders_view,      name="marketplace-vendor-orders"),
    path("vendor/products/",    vendor_products_view,    name="marketplace-vendor-products"),
    path("vendor/dashboard/",   vendor_dashboard_view,   name="marketplace-vendor-dashboard"),
    path("vendor/bulk-upload/", vendor_bulk_upload_view, name="marketplace-vendor-bulk-upload"),
    path("vendor/export/",      vendor_export_view,      name="marketplace-vendor-export"),

    # ── Mobile ────────────────────────────────────────────────────────────────
    path("mobile-sync/",    mobile_sync_view,   name="marketplace-mobile-sync"),
    path("device-tokens/",  device_token_view,  name="marketplace-device-token"),
    path("app-config/",     app_config_view,    name="marketplace-app-config"),

    # ── Inbound Webhooks ──────────────────────────────────────────────────────
    path("payment-webhook/<str:gateway>/",  payment_webhook_view,  name="marketplace-payment-webhook"),
    path("shipping-webhook/<str:carrier>/", shipping_webhook_view, name="marketplace-shipping-webhook"),
]


# ============================================================================
# SEARCH VIEWS
# ============================================================================

