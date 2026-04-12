from django.db import models
from django.contrib.auth import get_user_model
from .advertiser_model import Advertiser
from ..models import AdvertiserPortalBaseModel

User = get_user_model()

class BusinessRegistration(AdvertiserPortalBaseModel):
    """Business registration model for advertisers."""
    
    advertiser = models.OneToOneField(
        Advertiser, on_delete=models.CASCADE, related_name='business_registration'
    )
    business_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True)
    legal_structure = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default='pending')
    verified_at = models.DateTimeField(null=True, blank=True)
    registered_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='registered_businesses'
    )
    notes = models.TextField(blank=True)

    class Meta:
        app_label = 'advertiser_portal'

    def __str__(self):
        return self.business_name


class BusinessMetric(AdvertiserPortalBaseModel):
    """Business metrics model for advertisers."""
    
    business = models.ForeignKey(
        BusinessRegistration, on_delete=models.CASCADE, related_name='metrics'
    )
    metric_name = models.CharField(max_length=100)
    metric_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'advertiser_portal'

    def __str__(self):
        return f"{self.business} - {self.metric_name}"
