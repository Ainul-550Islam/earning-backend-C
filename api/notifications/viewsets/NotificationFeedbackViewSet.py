# earning_backend/api/notifications/viewsets/NotificationFeedbackViewSet.py
"""
NotificationFeedbackViewSet — split from views.py.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg

from notifications.models import NotificationFeedback
from notifications.serializers import NotificationFeedbackSerializer


class NotificationFeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationFeedback model.

    Endpoints:
      GET    /feedbacks/           — list (admin=all, user=own)
      POST   /feedbacks/           — create feedback
      GET    /feedbacks/{id}/      — retrieve
      GET    /feedbacks/summary/   — aggregate feedback stats (admin)
    """

    serializer_class = NotificationFeedbackSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['comment', 'notification__title']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'summary']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return NotificationFeedback.objects.all().select_related('user', 'notification')
        return NotificationFeedback.objects.filter(user=user).select_related('notification')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Aggregate feedback statistics."""
        qs = self.get_queryset()
        agg = qs.aggregate(
            total=Count('id'),
            avg_rating=Avg('rating') if hasattr(NotificationFeedback, 'rating') else None,
        )
        by_type = list(
            qs.values('feedback_type').annotate(count=Count('id')).order_by('-count')
        ) if hasattr(NotificationFeedback, 'feedback_type') else []
        return Response({
            'total': agg['total'],
            'avg_rating': round(agg.get('avg_rating') or 0, 2),
            'by_type': by_type,
        })
