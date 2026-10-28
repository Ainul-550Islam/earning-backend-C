# api/support/viewsets/ChatMessageViewSet.py  — WORLD #1
"""
ChatMessageViewSet: list messages per session
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class ChatMessageViewSet(viewsets.ModelViewSet):
    """
    ChatMessageViewSet — list messages per session
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from api.support.models import ChatMessage
        return ChatMessage.objects.all()

    def get_serializer_class(self):
        try:
            from api.support.serializers import ChatMessageSerializer
            return ChatMessageSerializer
        except ImportError:
            from rest_framework import serializers
            return serializers.Serializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]