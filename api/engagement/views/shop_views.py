# engagement/views/shop_views.py
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import ShopService, GamificationEngine
from ..models.shop import ShopItem
from ..serializers import ShopItemSerializer, ShopPurchaseSerializer, UserInventorySerializer
from ..utils.throttling import ShopPurchaseThrottle
from ..utils.decorators import engagement_endpoint
from ..utils.cache import get_shop_cache, set_shop_cache, invalidate_shop_cache


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shop_items(request):
    """GET /engagement/shop/ — available items in the coin shop."""
    tenant    = getattr(request.user, "tenant", None)
    tenant_id = getattr(tenant, "pk", None)
    cached    = get_shop_cache(tenant_id)
    if cached:
        return Response(cached)

    items     = ShopService.available_items(tenant)
    data      = ShopItemSerializer(items, many=True).data
    set_shop_cache(data, tenant_id)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ShopPurchaseThrottle])
@engagement_endpoint
def purchase_item(request):
    """POST /engagement/shop/purchase/ — buy an item."""
    slug     = request.data.get("item_slug")
    quantity = int(request.data.get("quantity", 1))
    if not slug:
        return Response({"error": "item_slug required"}, status=400)

    tenant = getattr(request.user, "tenant", None)
    result = ShopService.purchase(request.user, slug, quantity, tenant=tenant)
    GamificationEngine.on_purchase(request.user, result["purchase"], tenant=tenant)
    result_safe = {k: v for k, v in result.items() if k not in ("purchase", "item")}
    return Response({"success": True, **result_safe})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_inventory(request):
    """GET /engagement/shop/inventory/ — user's active items."""
    inventory = ShopService.inventory(request.user)
    return Response(UserInventorySerializer(inventory, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def shop_admin_list(request):
    """Admin: manage shop items."""
    if request.method == "GET":
        return Response(ShopItemSerializer(ShopItem.objects.all().order_by("order"), many=True).data)
    s = ShopItemSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    s.save()
    invalidate_shop_cache()
    return Response(s.data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def shop_admin_detail(request, pk):
    try:
        item = ShopItem.objects.get(pk=pk)
    except ShopItem.DoesNotExist:
        return Response(status=404)
    if request.method == "GET":
        return Response(ShopItemSerializer(item).data)
    if request.method == "PATCH":
        s = ShopItemSerializer(item, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        invalidate_shop_cache(getattr(item.tenant, "pk", None))
        return Response(s.data)
    item.delete()
    invalidate_shop_cache()
    return Response(status=204)
