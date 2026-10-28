# =============================================================================
# fraud_detection/models_tenant.py  — MULTI-TENANT ORGANISATION MODEL
# DRY: All tenant isolation goes through Organisation FK on existing models.
# =============================================================================
from __future__ import annotations
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Organisation(models.Model):
    """Root tenant entity. All fraud data is scoped to an organisation."""

    class Plan(models.TextChoices):
        FREE       = "free",       "Free"
        STARTER    = "starter",    "Starter"
        GROWTH     = "growth",     "Growth"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        ACTIVE    = "active",    "Active"
        SUSPENDED = "suspended", "Suspended"
        TRIAL     = "trial",     "Trial"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=255, unique=True)
    slug         = models.SlugField(max_length=100, unique=True)
    plan         = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    api_key      = models.CharField(max_length=64, unique=True, db_index=True)
    max_users    = models.PositiveIntegerField(default=5)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    metadata     = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label  = "fraud_detection"
        db_table   = "fraud_organisation"
        ordering   = ["name"]
        indexes    = [models.Index(fields=["slug"]), models.Index(fields=["api_key"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.plan})"

    def is_active(self) -> bool:
        return self.status in (self.Status.ACTIVE, self.Status.TRIAL)

    @classmethod
    def get_by_api_key(cls, api_key: str) -> "Organisation | None":
        try:
            return cls.objects.select_related().get(api_key=api_key, status__in=["active", "trial"])
        except cls.DoesNotExist:
            return None


class OrganisationMember(models.Model):
    """Maps Django User → Organisation with a role."""

    class Role(models.TextChoices):
        OWNER   = "owner",   "Owner"
        ADMIN   = "admin",   "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER  = "viewer",  "Viewer"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE,
                                     related_name="members")
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="org_memberships")
    role         = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    joined_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label     = "fraud_detection"
        db_table      = "fraud_org_member"
        unique_together = [("organisation", "user")]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organisation.name} ({self.role})"

    def can_write(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.ANALYST)

    def is_admin(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN)
