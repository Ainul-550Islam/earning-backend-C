"""views.py – Non-viewset views for the inventory module."""
import logging
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RewardItem
from .serializers import RewardItemListSerializer, UserInventorySerializer
from .services import get_active_items

logger = logging.getLogger(__name__)


class PublicItemCatalogView(APIView):
    """GET /api/inventory/catalog/ – public item listing for reward store."""
    permission_classes = [AllowAny]

    def get(self, request):
        item_type = request.query_params.get("type")
        items = get_active_items(item_type=item_type)
        serializer = RewardItemListSerializer(items, many=True, context={"request": request})
        return Response({"items": serializer.data, "count": len(serializer.data)})


class MyInventoryView(APIView):
    """GET /api/inventory/mine/ – authenticated user's full inventory."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import UserInventory
        inv = UserInventory.objects.for_user(request.user).with_item()
        serializer = UserInventorySerializer(inv, many=True, context={"request": request})
        return Response({"items": serializer.data, "count": len(serializer.data)})
