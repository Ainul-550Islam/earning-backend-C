# api/payment_gateways/locker/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from core.views import BaseViewSet
from .models import ContentLocker, OfferWall, UserVirtualBalance
from .serializers import (ContentLockerSerializer, OfferWallSerializer,
                           UserVirtualBalanceSerializer, VirtualRewardSerializer)
from .LockerEngine import LockerEngine, OfferWallEngine


class ContentLockerViewSet(BaseViewSet):
    """Publisher content locker management."""
    queryset           = ContentLocker.objects.all().order_by('-created_at')
    serializer_class   = ContentLockerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(publisher=self.request.user)

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny],
            url_path='show/(?P<locker_key>[A-Z0-9]+)')
    def show(self, request, locker_key=None):
        """Public: show locker to visitor."""
        engine = LockerEngine()
        ip     = request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip() \
                 or request.META.get('REMOTE_ADDR','')
        ua     = request.META.get('HTTP_USER_AGENT','')
        result = engine.show(
            locker_key=locker_key, visitor_ip=ip, user_agent=ua,
            country=request.GET.get('country',''),
            device=request.GET.get('device','desktop'),
        )
        return Response(result)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny],
            url_path='unlock')
    def unlock(self, request):
        """Public: unlock content after offer completion."""
        engine      = LockerEngine()
        locker_key  = request.data.get('locker_key','')
        click_id    = request.data.get('click_id','')
        result      = engine.unlock(locker_key, click_id)
        return Response(result)


class OfferWallViewSet(BaseViewSet):
    """Publisher offer wall management."""
    queryset           = OfferWall.objects.all().order_by('-created_at')
    serializer_class   = OfferWallSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(publisher=self.request.user)

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny],
            url_path='offers/(?P<wall_key>[A-Z0-9]+)')
    def get_offers(self, request, wall_key=None):
        """Public API: get offers for an offerwall (called by publisher's app)."""
        engine  = OfferWallEngine()
        user_id = request.GET.get('user_id','')
        result  = engine.get_offers(
            wall_key=wall_key, user_id=user_id,
            country=request.GET.get('country',''),
            device=request.GET.get('device','mobile'),
        )
        return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_virtual_balances(request):
    """Get user's virtual currency balances across all offerwalls."""
    balances = UserVirtualBalance.objects.filter(user=request.user).select_related('offer_wall')
    from .serializers import UserVirtualBalanceSerializer
    return Response({'success': True, 'data': UserVirtualBalanceSerializer(balances, many=True).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_rewards_history(request):
    """Get user's virtual reward history."""
    from .models import VirtualReward
    rewards = VirtualReward.objects.filter(user=request.user).order_by('-created_at')[:100]
    return Response({'success': True, 'data': VirtualRewardSerializer(rewards, many=True).data})
