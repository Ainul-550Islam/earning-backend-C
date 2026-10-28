"""
NEW FILE — Approval workflow model.

Implements Missing Component #4 (Approval/Review Workflows): previously
any user with API access could push a change straight to a live flag
with no review step. This adds an optional request -> review -> deploy
pipeline for teams that want governance over production flag changes.
"""
from django.conf import settings
from django.db import models

from .base import BaseModel
from .feature_flag import FeatureFlag


class FlagChangeRequest(BaseModel):
    """A proposed change to a flag, awaiting approval before being applied."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        DEPLOYED = 'deployed', 'Deployed'

    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='change_requests')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='requested_flag_changes'
    )
    requested_changes = models.JSONField(help_text='Partial dict of field -> new value.')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_flag_changes'
    )
    review_comment = models.TextField(blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)
    deployed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Flag Change Request'
        verbose_name_plural = 'Flag Change Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['flag', 'status'], name='changereq_flag_status_idx'),
            models.Index(fields=['status', '-created_at'], name='changereq_status_created_idx'),
        ]

    def __str__(self):
        return f"ChangeRequest({self.flag.name}, {self.status})"
