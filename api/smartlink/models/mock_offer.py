"""
Mock Offer model for testing when offer_inventory is not available.
In production, this should be replaced with the actual offer_inventory.Offer model.
"""
from django.db import models


class Offer(models.Model):
    """
    Minimal Offer model for testing/CI purposes.
    Maps to external offer_inventory.Offer in production.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    advertiser_id = models.BigIntegerField(default=0)
    
    class Meta:
        app_label = 'smartlink'
        
    def __str__(self):
        return self.name
