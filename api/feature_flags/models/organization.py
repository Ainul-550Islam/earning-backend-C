"""
NEW FILE — Organization / Team isolation (lightweight).

Implements Missing Component #2 (Team/Organization Isolation) from the
audit: previously every flag was globally visible/editable by anyone
with API access, with no concept of tenant boundaries.

Design note: `FeatureFlag.organization` (added in models/feature_flag.py)
is nullable, so existing single-tenant deployments keep working
unchanged; multi-tenant deployments set it and use
`IsOrganizationMember` (permissions.py) plus
`FeatureFlagViewSet.get_queryset()` filtering to enforce isolation.
"""
from django.conf import settings
from django.db import models

from .base import BaseModel


class Organization(BaseModel):
    """A tenant. Flags, experiments, and rules can optionally be scoped to one."""

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='feature_flag_organizations')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='OrganizationMember', related_name='organizations')

    class Meta:
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['name']

    def __str__(self):
        return self.name


class OrganizationMember(BaseModel):
    """Membership + role of a user within an organization."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        EDITOR = 'editor', 'Editor'
        VIEWER = 'viewer', 'Viewer'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        verbose_name = 'Organization Member'
        verbose_name_plural = 'Organization Members'
        unique_together = [['organization', 'user']]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class Team(BaseModel):
    """An optional sub-grouping within an Organization."""

    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='teams')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='feature_flag_teams', blank=True)

    class Meta:
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'
        unique_together = [['organization', 'name']]

    def __str__(self):
        return f"{self.organization.name}/{self.name}"
