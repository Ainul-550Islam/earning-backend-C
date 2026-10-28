# api/cms/models_new/user_profile.py
"""
User profile and segment models for CMS.
UserProfile is re-exported from withdrawal.py (where the full definition lives).
UserSegment is defined here.
"""
from typing import Dict, List, Any, Optional
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

# Re-export UserProfile from withdrawal where it's fully defined
from .withdrawal import UserProfile  # noqa

User = get_user_model()


class UserSegment(models.Model):
    """User segmentation for CMS content targeting."""
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    criteria    = models.JSONField(default=dict)
    uuid        = models.UUIDField(default=__import__('uuid').uuid4, unique=True, editable=False)
    is_active   = models.BooleanField(default=True)
    # Age range — single canonical pair; "min_age"/"max_age" used throughout.
    # (Previous code had both age_min/age_max *and* min_age/max_age defined,
    # which produced duplicate columns in the migration and confused ORM filters.)
    min_age     = models.IntegerField(null=True, blank=True)
    max_age     = models.IntegerField(null=True, blank=True)
    countries   = models.JSONField(default=list)
    interests   = models.JSONField(default=list)
    # cached_user_count is a DB field for storing the last-computed count.
    # A @property named "user_count" was previously defined *after* the field
    # definition, silently shadowing it and making any queryset that filtered
    # or updated via ".update(user_count=...)" raise a Django FieldError.
    # Renamed the DB column so the property can keep its public name.
    cached_user_count = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'cms'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def user_count(self) -> int:
        """Number of users matching this segment (approximate cached value)."""
        return self.cached_user_count

    def get_matching_users(self):
        """Return UserProfile queryset matching this segment's criteria.

        Services iterate this queryset and call .values_list('user', flat=True)
        or access .user on each profile.  Returning a User queryset (as before)
        caused FieldError because User has no 'user' field.
        """
        from .withdrawal import UserProfile
        qs = UserProfile.objects.select_related('user').filter(user__is_active=True)
        # Apply basic demographic filters if set on the segment
        if self.min_age is not None:
            from django.utils import timezone
            import datetime
            cutoff = timezone.now().date() - datetime.timedelta(days=self.min_age * 365)
            qs = qs.filter(date_of_birth__lte=cutoff)
        if self.max_age is not None:
            from django.utils import timezone
            import datetime
            cutoff = timezone.now().date() - datetime.timedelta(days=self.max_age * 365)
            qs = qs.filter(date_of_birth__gte=cutoff)
        if self.countries:
            qs = qs.filter(country__in=self.countries)
        return qs

    def update_user_count(self) -> int:
        """Refresh cached user_count and return it."""
        count = self.get_matching_users().count()
        UserSegment.objects.filter(pk=self.pk).update(cached_user_count=count)
        self.cached_user_count = count
        return count

    def matches_user(self, user) -> bool:
        """Check if a user matches this segment's criteria."""
        return self.get_matching_users().filter(user=user).exists()


__all__ = ['UserProfile', 'UserSegment']
