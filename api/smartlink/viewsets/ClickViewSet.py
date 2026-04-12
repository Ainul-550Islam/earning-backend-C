from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from ..models import Click
from ..serializers.ClickSerializer import ClickSerializer
from ..filters import ClickFilter
from ..pagination import SmartLinkCursorPagination
from ..permissions import IsPublisher


class ClickViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only click history for a SmartLink.
    Publishers see their own clicks only.
    """
    serializer_class = ClickSerializer
    permission_classes = [IsAuthenticated, IsPublisher]
    pagination_class = SmartLinkCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ClickFilter

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        user = self.request.user
        qs = Click.objects.filter(smartlink_id=sl_pk).select_related('offer')
        if not user.is_staff:
            qs = qs.filter(smartlink__publisher=user)
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        """GET click summary stats for this SmartLink."""
        from django.db.models import Count, Sum, Q
        qs = self.get_queryset()
        agg = qs.aggregate(
            total=Count('id'),
            unique=Count('id', filter=Q(is_unique=True)),
            fraud=Count('id', filter=Q(is_fraud=True)),
            bot=Count('id', filter=Q(is_bot=True)),
            converted=Count('id', filter=Q(is_converted=True)),
            revenue=Sum('payout'),
        )
        return Response(agg)
