"""
Mock Advertiser model for testing when advertiser_portal is not available.
In production, this should be replaced with the actual advertiser_portal.Advertiser model.
"""
from django.db import models


class Advertiser(models.Model):
    """
    Minimal Advertiser model for testing/CI purposes.
    Maps to external advertiser_portal.Advertiser in production.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(default='advertiser@test.local')
    
    class Meta:
        app_label = 'smartlink'
        
    def __str__(self):
        return self.name
