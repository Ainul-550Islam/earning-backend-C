# api/support/viewsets/DepartmentViewSet.py  — WORLD #1
"""
DepartmentViewSet: CRUD
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    DepartmentViewSet — CRUD
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from api.support.models import Department
        return Department.objects.all()

    def get_serializer_class(self):
        try:
            from api.support.serializers import DepartmentSerializer
            return DepartmentSerializer
        except ImportError:
            from rest_framework import serializers
            return serializers.Serializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]