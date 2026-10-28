"""
NEW FILE — Read-only Audit Log viewset.

Exposes the AuditLog model (see models/audit.py) over the API so admins
can review who changed what flag and when. Part of Missing Component #3
(Audit Trail).
"""
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models.audit import AuditLog
from ..serializers.audit_serializer import AuditLogSerializer
from ..permissions import IsAuthenticated, CanViewFlags


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for browsing the audit trail. Never writable via API —
    entries are created exclusively by the system (see signals.py)."""

    queryset = AuditLog.objects.select_related('user', 'flag').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanViewFlags]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['flag', 'action', 'user']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
