# api/support/viewsets/TicketMergeViewSet.py  — WORLD #1
"""
TicketMergeViewSet: merge action
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class TicketMergeViewSet(viewsets.ModelViewSet):
    """
    TicketMergeViewSet — merge action
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from api.support.models import TicketMerge
        return TicketMerge.objects.all()

    def get_serializer_class(self):
        try:
            from api.support.serializers import TicketMergeSerializer
            return TicketMergeSerializer
        except ImportError:
            from rest_framework import serializers
            return serializers.Serializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]