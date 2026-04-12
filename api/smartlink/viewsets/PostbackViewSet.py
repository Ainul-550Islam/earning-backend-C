"""
PostbackLog ViewSet — view all postbacks for admin/publisher
"""
from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models.postback_log import PostbackLog
from ..permissions import IsPublisher


class PostbackLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PostbackLog
        fields = [
            'id', 'click_id', 'offer_id', 'event',
            'payout', 'currency', 'transaction_id',
            'sub1', 'ip', 'is_duplicate', 'is_attributed',
            'created_at',
        ]
        read_only_fields = fields


class PostbackLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/smartlink/postback-logs/        → list all postbacks (admin)
    GET /api/smartlink/postback-logs/{id}/   → detail
    GET /api/smartlink/postback-logs/stats/  → aggregate stats
    """
    serializer_class   = PostbackLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = PostbackLog.objects.all().order_by('-created_at')
        offer_id = self.request.query_params.get('offer_id')
        event    = self.request.query_params.get('event')
        if offer_id:
            qs = qs.filter(offer_id=offer_id)
        if event:
            qs = qs.filter(event=event)
        return qs

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Aggregate postback stats."""
        from django.db.models import Count, Sum
        agg = PostbackLog.objects.aggregate(
            total       = Count('id'),
            duplicates  = Count('id', filter=__import__('django').db.models.Q(is_duplicate=True)),
            attributed  = Count('id', filter=__import__('django').db.models.Q(is_attributed=True)),
            total_payout= Sum('payout'),
        )
        return Response(agg)

    @action(detail=False, methods=['get'], url_path='generate-token')
    def generate_token(self, request):
        """Generate HMAC token for a specific offer (admin tool)."""
        import hmac, hashlib
        from django.conf import settings
        offer_id  = request.query_params.get('offer_id', '')
        click_id  = request.query_params.get('click_id', '')
        secret    = getattr(settings, 'SMARTLINK_POSTBACK_SECRET', 'change-me')
        payload   = f"{offer_id}:{click_id}"
        token     = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        return Response({
            'offer_id':  offer_id,
            'click_id':  click_id,
            'token':     token,
            'example_url': (
                f"/postback/?click_id={click_id or '{click_id}'}"
                f"&offer_id={offer_id}"
                f"&payout={{payout}}"
                f"&token={token}"
            ),
        })
