"""
Feature Flag model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .base import BaseModel


class FeatureFlag(BaseModel):
    """
    Model for feature flags.
    """

    class FlagType(models.TextChoices):
        BOOLEAN = 'boolean', 'Boolean'
        STRING = 'string', 'String'
        NUMBER = 'number', 'Number'
        JSON = 'json', 'JSON'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        ARCHIVED = 'archived', 'Archived'

    class Environment(models.TextChoices):
        DEVELOPMENT = 'development', 'Development'
        STAGING = 'staging', 'Staging'
        PRODUCTION = 'production', 'Production'

    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    flag_type = models.CharField(max_length=50, choices=FlagType.choices, default=FlagType.BOOLEAN)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.DRAFT)

    # Default value when flag is disabled
    default_value = models.JSONField(default=dict)

    # Percentage rollout (0-100)
    rollout_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Targeting rules
    targeting_rules = models.JSONField(default=list)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Tags for organization
    tags = models.JSONField(default=list)

    # Owner information
    owner = models.CharField(max_length=255, blank=True)
    team = models.CharField(max_length=255, blank=True)

    # Environment-specific settings
    # FIX (multi-environment support): flags are now unique per (name, environment)
    # instead of globally unique, so the same flag name can exist across
    # development / staging / production independently.
    environment = models.CharField(
        max_length=50,
        choices=Environment.choices,
        default=Environment.PRODUCTION,
        db_index=True,
    )

    # NEW (Missing Component: Team/Organization isolation). Nullable so
    # existing single-tenant deployments are unaffected; multi-tenant
    # deployments set this and rely on IsOrganizationMember (permissions.py)
    # + FeatureFlagViewSet.get_queryset() filtering for data isolation.
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='flags',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'
        ordering = ['-created_at']
        unique_together = [['name', 'environment']]
        indexes = [
            models.Index(fields=['name'], name='flag_name_idx'),
            models.Index(fields=['status'], name='flag_status_idx'),
            models.Index(fields=['flag_type'], name='flag_type_idx'),
            models.Index(fields=['environment'], name='flag_env_idx'),
            models.Index(fields=['created_at'], name='flag_created_idx'),
            models.Index(fields=['environment', 'status'], name='flag_env_status_idx'),
        ]

    def __str__(self):
        return f"{self.name} [{self.environment}] ({self.status})"

    def clean(self):
        """Model-level validation (runs on full_clean(), e.g. from DRF/ModelForm)."""
        super().clean()
        if self.rollout_percentage is not None and not (0 <= self.rollout_percentage <= 100):
            raise ValidationError({'rollout_percentage': 'Rollout percentage must be between 0 and 100.'})
        if not self.name:
            raise ValidationError({'name': 'Flag name is required.'})

    def is_enabled(self, context: dict = None) -> bool:
        """
        Check if the flag is enabled for the given context.

        Args:
            context: Optional context dictionary

        Returns:
            True if flag is enabled
        """
        if self.status != self.Status.ACTIVE:
            return False

        # FIX: was `from .flag_engine import FlagEngine` which is WRONG —
        # flag_engine.py lives at the `feature_flags` package root, not inside
        # `models/`, so this raised ModuleNotFoundError on every call.
        if self.targeting_rules and context:
            from feature_flags.flag_engine import FlagEngine
            engine = FlagEngine()
            return engine.evaluate_rules(self, context)

        # FIX: was `from .utils import get_user_hash` — same bug, utils.py is
        # at the package root.
        if self.rollout_percentage > 0 and context:
            from feature_flags.utils import get_user_hash
            user_hash = get_user_hash(context.get('user_id', ''))
            return (user_hash % 100) < self.rollout_percentage

        return self.rollout_percentage == 100

    def get_value(self, context: dict = None):
        """
        Get the flag value for the given context.

        Args:
            context: Optional context dictionary

        Returns:
            Flag value
        """
        if not self.is_enabled(context):
            return self.default_value

        # Check for variants (this one was already correct — flag_variant.py
        # IS inside models/, so the relative import is fine).
        from .flag_variant import FlagVariant
        variants = FlagVariant.objects.filter(flag=self, is_active=True)

        if variants.exists():
            # FIX: same wrong relative import as above.
            from feature_flags.utils import get_user_hash
            context = context or {}
            user_hash = get_user_hash(context.get('user_id', ''))
            total_weight = sum(v.weight for v in variants)

            if total_weight > 0:
                threshold = (user_hash % 100) / 100 * total_weight
                current_weight = 0

                for variant in variants:
                    current_weight += variant.weight
                    if threshold <= current_weight:
                        return variant.value

        return self.default_value
