# earning_backend/api/notifications/viewset.py
"""
Viewset — Base ViewSet classes for notification endpoints.
Provides pre-configured base classes that all notification viewsets inherit from.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .mixins import (NotificationOwnerMixin, SoftDeleteMixin, AuditMixin,
                     NotificationPaginationMixin, StatusActionMixin)
from .pagination import NotificationPagination
from .throttling import NotificationCreateThrottle


class NotificationBaseViewSet(
    NotificationOwnerMixin,
    AuditMixin,
    NotificationPaginationMixin,
    viewsets.ModelViewSet,
):
    """
    Base ViewSet for notification-related models.
    Provides: ownership filter, audit logging, standard pagination,
    DRF filter backends, and throttling.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ['-created_at']
    throttle_classes = []


class NotificationReadOnlyViewSet(
    NotificationOwnerMixin,
    NotificationPaginationMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only base ViewSet for analytics and log endpoints."""
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ['-created_at']


class NotificationAdminViewSet(
    AuditMixin,
    NotificationPaginationMixin,
    StatusActionMixin,
    viewsets.ModelViewSet,
):
    """
    Admin-only base ViewSet. Exposes all records (no user filter).
    Adds system_status action for monitoring.
    """
    from rest_framework.permissions import IsAdminUser
    permission_classes = [IsAdminUser]
    pagination_class = NotificationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ['-created_at']
