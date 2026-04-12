from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from ..models import RedirectLog
from ..serializers.RedirectLogSerializer import RedirectLogSerializer
from ..pagination import LargeResultsPagination
from ..permissions import IsPublisher


class RedirectLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only redirect log for a SmartLink."""
    serializer_class = RedirectLogSerializer
    permission_classes = [IsAuthenticated, IsPublisher]
    pagination_class = LargeResultsPagination
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        user = self.request.user
        qs = RedirectLog.objects.filter(smartlink_id=sl_pk)
        if not user.is_staff:
            qs = qs.filter(smartlink__publisher=user)
        return qs.order_by('-created_at')
