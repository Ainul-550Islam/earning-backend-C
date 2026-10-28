# api/support/viewsets/ChatSessionViewSet.py  — WORLD #1
"""
ChatSessionViewSet: start, end, list
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    ChatSessionViewSet — start, end, list
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from api.support.models import ChatSession
        return ChatSession.objects.all()

    def get_serializer_class(self):
        try:
            from api.support.serializers import ChatSessionSerializer
            return ChatSessionSerializer
        except ImportError:
            from rest_framework import serializers
            return serializers.Serializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]