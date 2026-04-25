# earning_backend/api/notifications/viewsets/NotificationRuleViewSet.py
"""
NotificationRuleViewSet — split from views.py (lines 1256-1415).
Full code preserved. Admin-only.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from api.notifications.models import NotificationRule
from api.notifications.serializers import (
    NotificationRuleSerializer,
    CreateRuleSerializer,
    RuleActionSerializer,
)


class NotificationRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationRule model — admin-only automation rules.

    Endpoints:
      GET    /rules/            — list all rules
      POST   /rules/            — create rule
      GET    /rules/{id}/       — retrieve
      PUT    /rules/{id}/       — update
      DELETE /rules/{id}/       — destroy
      POST   /rules/{id}/start/ — activate rule
      POST   /rules/{id}/pause/ — deactivate rule
      POST   /rules/{id}/test/  — test rule with sample data
      GET    /rules/active/     — list only active rules
    """

    serializer_class = NotificationRuleSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['trigger_type', 'action_type', 'target_type', 'is_active', 'is_enabled']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at', 'trigger_count']
    ordering = ['name']

    def get_queryset(self):
        return NotificationRule.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateRuleSerializer
        elif self.action in ['user_action', 'test']:
            return RuleActionSerializer
        return NotificationRuleSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """Activate a rule."""
        rule = self.get_object()
        rule.is_active = True
        rule.is_enabled = True
        rule.save(update_fields=['is_active', 'is_enabled', 'updated_at'])
        return Response(self.get_serializer(rule).data)

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Deactivate a rule."""
        rule = self.get_object()
        rule.is_active = False
        rule.save(update_fields=['is_active', 'updated_at'])
        return Response(self.get_serializer(rule).data)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test rule with sample data without actually sending."""
        rule = self.get_object()
        try:
            from api.notifications.services import rule_service
            result = rule_service.test_rule(rule, context=request.data.get('context', {}))
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List only active/enabled rules."""
        qs = self.get_queryset().filter(is_active=True, is_enabled=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def user_action(self, request, pk=None):
        """Perform a custom action on a rule."""
        rule = self.get_object()
        serializer = RuleActionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
