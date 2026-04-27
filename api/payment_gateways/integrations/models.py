# api/payment_gateways/integrations/models.py
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class AdvertiserTrackerIntegration(TimeStampedModel):
    """Links an advertiser's offer to their 3rd party tracker account."""

    TRACKERS = (
        ('appsflyer', 'AppsFlyer'),
        ('adjust',    'Adjust'),
        ('kochava',   'Kochava'),
        ('singular',  'Singular'),
        ('branch',    'Branch'),
    )

    advertiser      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='tracker_integrations')
    offer           = models.OneToOneField('offerwall.Offer', on_delete=models.CASCADE,
                       related_name='tracker_integration')
    tracker         = models.CharField(max_length=20, choices=TRACKERS)
    app_id          = models.CharField(max_length=200, help_text='App ID in tracker dashboard')
    dev_key         = models.CharField(max_length=200, blank=True,
                       help_text='Dev key / API key for tracker')
    is_active       = models.BooleanField(default=True)
    postback_url    = models.URLField(max_length=2000, blank=True,
                       help_text='Postback URL to enter in tracker dashboard')

    class Meta:
        verbose_name = 'Advertiser Tracker Integration'

    def __str__(self):
        return f'{self.advertiser.username} — {self.tracker} — {self.offer.name}'

    def get_postback_url(self):
        from .AppsFlyer import ThirdPartyTrackerService
        return ThirdPartyTrackerService().get_postback_template(self.tracker, self.offer_id)
