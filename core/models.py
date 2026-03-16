from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
from django.core.exceptions import ValidationError


class BaseModel(models.Model):
    """
    Abstract base model with UUID primary key.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID')
    )

    class Meta:
        abstract = True


class TimeStampedModel(BaseModel):
    """
    Abstract model with created and modified timestamps.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']


# SystemSettings Model
    def save(self, *args, **kwargs):
        # Ensure only one SystemSettings instance exists
        if not self.pk and SystemSettings.objects.exists():
            raise ValidationError("Only one SystemSettings instance is allowed")
        return super().save(*args, **kwargs)