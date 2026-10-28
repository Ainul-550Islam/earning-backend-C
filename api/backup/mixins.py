"""
Backup Module Mixins
Reusable mixin classes for backup models and views.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class TimestampMixin(models.Model):
    """Adds created_at and updated_at fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Adds soft-delete capability"""
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])

    class Meta:
        abstract = True


class AuditMixin(models.Model):
    """Adds audit trail fields"""
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True


class StatusMixin(models.Model):
    """Adds status tracking with history"""
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_changed_at = models.DateTimeField(null=True, blank=True)

    def set_status(self, new_status: str):
        self.status = new_status
        self.status_changed_at = timezone.now()
        self.save(update_fields=["status", "status_changed_at"])

    @property
    def is_completed(self) -> bool:
        return self.status == self.STATUS_COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == self.STATUS_FAILED

    @property
    def is_running(self) -> bool:
        return self.status == self.STATUS_RUNNING

    class Meta:
        abstract = True


class SizeMixin(models.Model):
    """Adds size tracking and human-readable size"""
    size_bytes = models.BigIntegerField(null=True, blank=True)

    @property
    def size_human(self) -> str:
        if self.size_bytes is None:
            return "N/A"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} PB"

    class Meta:
        abstract = True


class TagsMixin(models.Model):
    """Adds JSON-based tagging"""
    tags = models.JSONField(default=dict, blank=True)

    def add_tag(self, key: str, value: str):
        self.tags[key] = value
        self.save(update_fields=["tags"])

    def remove_tag(self, key: str):
        self.tags.pop(key, None)
        self.save(update_fields=["tags"])

    def get_tag(self, key: str, default: Any = None) -> Any:
        return self.tags.get(key, default)

    class Meta:
        abstract = True


class APIResponseMixin:
    """Mixin for DRF views — standard response helpers"""

    def success_response(self, data: Any, status_code: int = 200):
        from rest_framework.response import Response
        return Response({"success": True, "data": data}, status=status_code)

    def error_response(self, message: str, status_code: int = 400, errors: Optional[Dict] = None):
        from rest_framework.response import Response
        payload = {"success": False, "message": message}
        if errors:
            payload["errors"] = errors
        return Response(payload, status=status_code)

    def paginated_response(self, queryset, serializer_class, request):
        from rest_framework.response import Response
        from api.backup.pagination import BackupPagination
        paginator = BackupPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = serializer_class(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)
        serializer = serializer_class(queryset, many=True, context={"request": request})
        return Response(serializer.data)
